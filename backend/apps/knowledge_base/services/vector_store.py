import json
from pathlib import Path
from typing import Any, Dict, List, Optional


import threading


import faiss
import numpy as np

from apps.knowledge_base.models import Knowledge

from .embedding_service import EmbeddingService


class VectorStore:
    """
    FAISS vector store for Farmer Voice AI knowledge.

    Responsibilities
    ----------------
    1. Build embeddings for active knowledge records.
    2. Build a FAISS inner-product index.
    3. Persist FAISS index + Knowledge IDs.
    4. Safely load an existing index.
    5. Search semantically similar knowledge.
    6. Handle stale/deleted Knowledge records safely.
    7. Avoid hardcoded crop/domain assumptions.
    8. Preserve raw semantic similarity scores.

    IMPORTANT
    ---------
    Crop safety is handled by SemanticSearch.

    VectorStore is intentionally crop-agnostic because its job
    is candidate retrieval, not final agricultural relevance
    validation.
    """

    # =========================================================
    # Storage
    # =========================================================

    VECTOR_DIR = Path("vector_db")

    INDEX_FILE = VECTOR_DIR / "knowledge.index"

    IDS_FILE = VECTOR_DIR / "knowledge_ids.npy"

    META_FILE = VECTOR_DIR / "knowledge_meta.json"
    # =========================================================
    # Process-Level FAISS Cache
    # =========================================================

    _shared_index = None
    _shared_knowledge_ids: List[int] = []
    _shared_dimension: Optional[int] = None
    _shared_metadata: Dict[str, Any] = {}

    _cache_loaded = False
    _cache_lock = threading.RLock()

    # =========================================================
    # Initialization
    # =========================================================

    def __init__(self):

        self.embedding_service = EmbeddingService()

        cls = type(self)

        self.index = cls._shared_index

        self.knowledge_ids = cls._shared_knowledge_ids

        self.dimension = cls._shared_dimension

        self.metadata = cls._shared_metadata


        # =========================================================
    # Shared Cache Helpers
    # =========================================================

    def _sync_from_shared_cache(self):
        """
        Copy process-level cached FAISS state into this instance.
        """

        cls = type(self)

        self.index = cls._shared_index
        self.knowledge_ids = cls._shared_knowledge_ids
        self.dimension = cls._shared_dimension
        self.metadata = cls._shared_metadata

    def _sync_to_shared_cache(self):
        """
        Publish this instance's FAISS state to the process cache.
        """

        cls = type(self)

        cls._shared_index = self.index
        cls._shared_knowledge_ids = self.knowledge_ids
        cls._shared_dimension = self.dimension
        cls._shared_metadata = self.metadata
        cls._shared_mtime = self.INDEX_FILE.stat().st_mtime if self.INDEX_FILE.exists() else 0.0

        cls._cache_loaded = self.index is not None

    @classmethod
    def invalidate_cache(cls):
        """
        Clear in-memory FAISS cache.

        Rebuild/load can repopulate it afterwards.
        """

        with cls._cache_lock:

            cls._shared_index = None
            cls._shared_knowledge_ids = []
            cls._shared_dimension = None
            cls._shared_metadata = {}
            cls._cache_loaded = False

    # =========================================================
    # Build Searchable Document
    # =========================================================

    def build_document(
        self,
        knowledge: Knowledge,
    ) -> str:
        """
        Build semantic embedding text from trusted Knowledge
        fields.

        Structured agricultural metadata is intentionally
        included so semantic retrieval can understand:

        - Crop
        - Category
        - Subcategory
        - Domain
        - Growth stage
        - Question
        - Answer
        - Keywords

        No crop names are hardcoded.
        """

        fields = [
            (
                "Crop",
                knowledge.crop,
            ),
            (
                "Category",
                knowledge.category,
            ),
            (
                "Subcategory",
                knowledge.subcategory,
            ),
            (
                "Domain",
                knowledge.domain,
            ),
            (
                "Stage",
                knowledge.stage,
            ),
            (
                "Question",
                knowledge.question,
            ),
            (
                "Answer",
                knowledge.answer,
            ),
            (
                "Keywords",
                knowledge.keywords,
            ),
        ]

        parts = []

        for label, value in fields:

            if value is None:
                continue

            value = str(value).strip()

            if not value:
                continue

            parts.append(f"{label}: {value}")

        return "\n".join(parts)

    # =========================================================
    # Normalize Embedding
    # =========================================================

    @staticmethod
    def _prepare_vector(
        vector: Any,
    ) -> np.ndarray:
        """
        Convert an embedding into normalized float32 vector.

        IndexFlatIP + L2-normalized vectors behaves like cosine
        similarity.
        """

        vector = np.asarray(
            vector,
            dtype=np.float32,
        )

        # Flatten accidental shapes such as (1, 768).
        vector = vector.reshape(-1)

        if vector.size == 0:

            raise ValueError("Embedding service returned an empty vector.")

        if not np.all(np.isfinite(vector)):

            raise ValueError("Embedding contains NaN or infinite values.")

        norm = np.linalg.norm(vector)

        if norm > 0:

            vector = vector / norm

        return vector.astype(
            np.float32,
            copy=False,
        )

    # =========================================================
    # Encode
    # =========================================================

    def _encode(
        self,
        text: str,
    ) -> np.ndarray:
        """
        Encode and normalize text consistently for both index
        construction and query search.
        """

        vector = self.embedding_service.encode(text)

        return self._prepare_vector(vector)

    # =========================================================
    # Build Index
    # =========================================================

    def build_index(self):
        """
        Build FAISS index using all ACTIVE knowledge records.

        Embedding dimension is detected dynamically from the
        embedding model rather than being hardcoded.
        """

        queryset = Knowledge.objects.filter(is_active=True).order_by("id")

        embeddings = []

        knowledge_ids = []

        expected_dimension = None

        skipped_records = 0

        for item in queryset:

            document = self.build_document(item)

            if not document.strip():

                skipped_records += 1
                continue

            try:

                vector = self._encode(document)

            except Exception as exc:

                skipped_records += 1

                print(
                    "VECTOR INDEX SKIP:",
                    item.id,
                    str(exc),
                )

                continue

            if expected_dimension is None:

                expected_dimension = int(vector.shape[0])

            elif vector.shape[0] != expected_dimension:

                raise ValueError(
                    "Embedding dimension mismatch while "
                    f"building index. Expected "
                    f"{expected_dimension}, received "
                    f"{vector.shape[0]} for Knowledge "
                    f"ID {item.id}."
                )

            embeddings.append(vector)

            knowledge_ids.append(int(item.id))

        if not embeddings:

            self.index = None

            self.knowledge_ids = []

            self.dimension = None

            self.metadata = {
                "document_count": 0,
                "dimension": None,
                "skipped_records": (skipped_records),
            }

            raise ValueError("No active Knowledge records could be " "indexed.")
            self._sync_to_shared_cache()

        embedding_matrix = np.vstack(embeddings).astype(
            np.float32,
            copy=False,
        )

        self.dimension = int(embedding_matrix.shape[1])

        self.index = faiss.IndexFlatIP(self.dimension)

        self.index.add(embedding_matrix)

        self.knowledge_ids = knowledge_ids

        self.metadata = {
            "document_count": len(knowledge_ids),
            "dimension": self.dimension,
            "skipped_records": skipped_records,
            "index_type": "IndexFlatIP",
            "normalized_embeddings": True,
        }

        self._sync_to_shared_cache()

        print("\n" + "=" * 80)

        print("FAISS INDEX CREATED")

        print("=" * 80)

        print(
            "Documents :",
            len(self.knowledge_ids),
        )

        print(
            "Dimension :",
            self.dimension,
        )

        print(
            "Skipped   :",
            skipped_records,
        )

        print("=" * 80 + "\n")

        return {
            "success": True,
            "documents": len(self.knowledge_ids),
            "dimension": (self.dimension),
            "skipped_records": (skipped_records),
        }

    # =========================================================
    # Save Index
    # =========================================================

    def save(self):
        """
        Persist FAISS index, Knowledge IDs and metadata.
        """

        if self.index is None:

            raise ValueError(
                "Cannot save vector index because no " "index has been built."
            )

        if not self.knowledge_ids:

            raise ValueError(
                "Cannot save vector index because Knowledge " "ID mapping is empty."
            )

        if self.index.ntotal != len(self.knowledge_ids):

            raise ValueError("FAISS index and Knowledge ID mapping are " "out of sync.")

        self.VECTOR_DIR.mkdir(
            parents=True,
            exist_ok=True,
        )

        faiss.write_index(
            self.index,
            str(self.INDEX_FILE),
        )

        np.save(
            self.IDS_FILE,
            np.asarray(
                self.knowledge_ids,
                dtype=np.int64,
            ),
        )

        metadata = dict(self.metadata)

        metadata.update(
            {
                "document_count": int(self.index.ntotal),
                "dimension": int(self.index.d),
            }
        )

        with self.META_FILE.open(
            "w",
            encoding="utf-8",
        ) as file:

            json.dump(
                metadata,
                file,
                ensure_ascii=False,
                indent=2,
            )

        self.metadata = metadata

        print("\n" + "=" * 80)

        print("FAISS INDEX SAVED")

        print("=" * 80)

        print(
            "Index File :",
            self.INDEX_FILE,
        )

        print(
            "IDs File   :",
            self.IDS_FILE,
        )

        print(
            "Meta File  :",
            self.META_FILE,
        )

        print(
            "Documents  :",
            self.index.ntotal,
        )

        print("=" * 80 + "\n")

        return True

    # =========================================================
    # Load Index
    # =========================================================

    def load(
        self,
        auto_build: bool = False,
    ) -> bool:
        """
        Safely load persisted FAISS index.

        If files are unavailable:

        auto_build=False
            Return False.

        auto_build=True
            Build and save a fresh index.
        """
        cls = type(self)

        current_mtime = self.INDEX_FILE.stat().st_mtime if self.INDEX_FILE.exists() else 0.0
        last_mtime = getattr(cls, "_shared_mtime", 0.0)

        # Another VectorStore instance already loaded FAISS and index file has not changed.
        # Reuse it instead of reading index files again.
        if cls._cache_loaded and cls._shared_index is not None and last_mtime == current_mtime:

            self._sync_from_shared_cache()

            return True

        if cls._cache_loaded and last_mtime != current_mtime:
            cls.invalidate_cache()

        index_exists = self.INDEX_FILE.exists()

        ids_exist = self.IDS_FILE.exists()

        if not index_exists or not ids_exist:

            self.index = None

            self.knowledge_ids = []

            self.dimension = None

            if auto_build:

                self.build_index()

                self.save()

                return True

            print("\n" + "=" * 80)

            print("FAISS INDEX NOT FOUND")

            print("=" * 80)

            print(
                "Index File Exists :",
                index_exists,
            )

            print(
                "IDs File Exists   :",
                ids_exist,
            )

            print("=" * 80 + "\n")

            return False

        try:

            index = faiss.read_index(str(self.INDEX_FILE))

            knowledge_ids = (
                np.load(
                    self.IDS_FILE,
                    allow_pickle=False,
                )
                .astype(np.int64)
                .tolist()
            )

        except Exception as exc:

            self.index = None

            self.knowledge_ids = []

            self.dimension = None

            print(
                "FAISS LOAD ERROR:",
                str(exc),
            )

            if auto_build:

                self.build_index()

                self.save()

                return True

            return False

        if index.ntotal != len(knowledge_ids):

            self.index = None

            self.knowledge_ids = []

            self.dimension = None

            print("FAISS INDEX INVALID: " "index vectors and Knowledge IDs differ.")

            if auto_build:

                self.build_index()

                self.save()

                return True

            return False

        self.index = index

        self.knowledge_ids = [int(value) for value in knowledge_ids]

        self.dimension = int(index.d)

        self.metadata = self._load_metadata()

        self._sync_to_shared_cache()

        print("\n" + "=" * 80)

        print("FAISS INDEX LOADED")

        print("=" * 80)

        print(
            "Documents :",
            self.index.ntotal,
        )

        print(
            "Dimension :",
            self.dimension,
        )

        print("=" * 80 + "\n")

        return True

    # =========================================================
    # Metadata
    # =========================================================

    def _load_metadata(
        self,
    ) -> Dict[str, Any]:

        if not self.META_FILE.exists():

            return {
                "document_count": (len(self.knowledge_ids)),
                "dimension": (self.dimension),
            }

        try:

            with self.META_FILE.open(
                "r",
                encoding="utf-8",
            ) as file:

                data = json.load(file)

            if isinstance(
                data,
                dict,
            ):

                return data

        except Exception:

            pass

        return {
            "document_count": (len(self.knowledge_ids)),
            "dimension": (self.dimension),
        }

    # =========================================================
    # Search
    # =========================================================

    def search(
        self,
        question: str,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Search FAISS and return semantic candidates.

        Raw score is cosine-like similarity because both stored
        embeddings and query embeddings are L2-normalized before
        IndexFlatIP comparison.

        Returns:
        [
            {
                "knowledge": Knowledge,
                "score": float,
                "semantic_raw_score": float,
                "vector_position": int
            }
        ]
        """

        if not question or not str(question).strip():

            return []

        if self.index is None:

            loaded = self.load()

            if not loaded:
                return []

        if not self.knowledge_ids:

            return []

        if self.index.ntotal <= 0:

            return []

        # =====================================================
        # Query Embedding
        # =====================================================

        try:

            vector = self._encode(str(question).strip())

        except Exception as exc:

            print(
                "VECTOR SEARCH ENCODING ERROR:",
                str(exc),
            )

            return []

        # =====================================================
        # Dimension Safety
        # =====================================================

        if vector.shape[0] != self.index.d:

            raise ValueError(
                "Query embedding dimension does not match "
                "the FAISS index. "
                f"Query={vector.shape[0]}, "
                f"Index={self.index.d}. "
                "Rebuild the vector index if the embedding "
                "model has changed."
            )

        # =====================================================
        # Top K Safety
        # =====================================================

        try:

            top_k = int(top_k)

        except (
            TypeError,
            ValueError,
        ):

            top_k = 5

        top_k = max(
            1,
            top_k,
        )

        top_k = min(
            top_k,
            int(self.index.ntotal),
        )

        query_vector = np.expand_dims(
            vector,
            axis=0,
        ).astype(
            np.float32,
            copy=False,
        )

        # =====================================================
        # FAISS Search
        # =====================================================

        scores, indexes = self.index.search(
            query_vector,
            top_k,
        )

        # =====================================================
        # Resolve Knowledge IDs Efficiently
        # =====================================================

        candidates = []

        requested_ids = []

        for score, vector_index in zip(
            scores[0],
            indexes[0],
        ):

            vector_index = int(vector_index)

            if vector_index < 0:
                continue

            if vector_index >= len(self.knowledge_ids):

                continue

            knowledge_id = int(self.knowledge_ids[vector_index])

            candidates.append(
                {
                    "knowledge_id": (knowledge_id),
                    "vector_position": (vector_index),
                    "score": float(score),
                }
            )

            requested_ids.append(knowledge_id)

        if not candidates:

            return []

        knowledge_map = Knowledge.objects.filter(
            id__in=requested_ids,
            is_active=True,
        ).in_bulk()

        # =====================================================
        # Build Results
        # =====================================================

        results = []

        stale_records = 0

        for candidate in candidates:

            knowledge = knowledge_map.get(candidate["knowledge_id"])

            # Record may have been deleted/deactivated after
            # the FAISS index was created.
            if knowledge is None:

                stale_records += 1

                continue

            raw_score = float(candidate["score"])

            results.append(
                {
                    "knowledge": (knowledge),
                    # Backward compatibility
                    "score": raw_score,
                    # Explicit raw semantic evidence
                    "semantic_raw_score": (raw_score),
                    "vector_position": (candidate["vector_position"]),
                }
            )

        if stale_records:

            print(
                "FAISS STALE RECORDS SKIPPED:",
                stale_records,
            )

        return results

    # =========================================================
    # Rebuild
    # =========================================================

    def rebuild(
        self,
    ) -> Dict[str, Any]:
        """
        Rebuild and persist the complete vector index.
        """

        result = self.build_index()

        self.save()

        return result

    # =========================================================
    # Status
    # =========================================================

    def status(
        self,
    ) -> Dict[str, Any]:
        """
        Return current vector-store state.
        """

        return {
            "loaded": (self.index is not None),
            "index_exists": (self.INDEX_FILE.exists()),
            "ids_exists": (self.IDS_FILE.exists()),
            "metadata_exists": (self.META_FILE.exists()),
            "dimension": (self.dimension),
            "indexed_documents": (
                int(self.index.ntotal) if self.index is not None else 0
            ),
            "knowledge_ids": len(self.knowledge_ids),
            "metadata": (self.metadata),
        }
