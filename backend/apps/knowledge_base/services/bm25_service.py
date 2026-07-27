import threading
from typing import Any, Dict, List, Optional

from rank_bm25 import BM25Okapi

from apps.knowledge_base.models import Knowledge

from .search_preprocessor import SearchPreprocessor
from .crop_resolver import CropResolver


class BM25Service:
    """
    Universal crop-aware BM25 retrieval service.

    Responsibilities
    ----------------
    1. Load active knowledge records.
    2. Build BM25 index.
    3. Normalize/tokenize multilingual queries.
    4. Resolve crop dynamically.
    5. Prevent cross-crop retrieval leakage.
    6. Allow crop-independent/general knowledge.
    7. Return raw BM25 scores for hybrid ranking.
    8. Support future crops without hardcoded crop lists.

    IMPORTANT
    ---------
    No fixed crop list is maintained here.

    Crop identification is delegated to CropResolver.
    """

    # =========================================================
    # Configuration
    # =========================================================

    DEFAULT_TOP_K = 5

    MAX_TOP_K = 50

    MIN_SCORE = 0.0

    # =========================================================
    # Process-Level BM25 Cache
    # =========================================================

    _shared_documents: List[List[str]] = []
    _shared_knowledge_objects: List[Knowledge] = []
    _shared_bm25: Optional[BM25Okapi] = None

    _cache_ready = False

    _cache_lock = threading.RLock()

    # Small ranking bonus for exact crop agreement.
    #
    # Raw BM25 score remains untouched in bm25_raw_score.
    CROP_MATCH_BONUS = 0.25

    # =========================================================
    # Initialization
    # =========================================================

    def __init__(self):

        self.preprocessor = SearchPreprocessor()

        try:
            self.crop_resolver = CropResolver()

        except Exception:
            self.crop_resolver = None

        self.documents: List[List[str]] = []

        self.knowledge_objects: List[Knowledge] = []

        self.bm25: Optional[BM25Okapi] = None

        self._initialize_index()

    # =========================================================
    # Shared Index Initialization
    # =========================================================

    def _initialize_index(self):
        """
        Reuse the process-level BM25 index when available.

        The database corpus is tokenized and indexed only once
        per Django process unless refresh_index() is called.
        """

        cls = type(self)

        if cls._cache_ready:

            self._sync_from_shared_cache()

            return

        with cls._cache_lock:

            if cls._cache_ready:

                self._sync_from_shared_cache()

                return

            self.build_index()

    def _sync_from_shared_cache(self):
        """
        Attach cached BM25 data to this service instance.
        """

        cls = type(self)

        self.documents = cls._shared_documents
        self.knowledge_objects = cls._shared_knowledge_objects
        self.bm25 = cls._shared_bm25

    def _sync_to_shared_cache(self):
        """
        Publish the current BM25 index to process-level cache.
        """

        cls = type(self)

        cls._shared_documents = self.documents
        cls._shared_knowledge_objects = self.knowledge_objects
        cls._shared_bm25 = self.bm25
        cls._cache_ready = True

    @classmethod
    def invalidate_cache(cls):
        """
        Clear cached BM25 state.

        A future BM25Service instance will rebuild the index.
        """

        with cls._cache_lock:

            cls._shared_documents = []
            cls._shared_knowledge_objects = []
            cls._shared_bm25 = None
            cls._cache_ready = False

    # =========================================================
    # Tokenization
    # =========================================================

    def tokenize(
        self,
        text: Any,
    ) -> List[str]:
        """
        Preprocess text and return BM25 lexical tokens.

        We prefer lexical_tokens because BM25 can use repeated
        terms. If unavailable, fall back to tokens.
        """

        processed = self.preprocessor.preprocess(text)

        lexical_tokens = processed.get("lexical_tokens")

        if lexical_tokens is not None:
            return lexical_tokens

        return processed.get(
            "tokens",
            [],
        )

    # =========================================================
    # Document Text
    # =========================================================

    def _build_document_text(
        self,
        knowledge: Knowledge,
    ) -> str:
        """
        Build BM25 document text from trusted Knowledge fields.

        search_text remains useful, but including structured
        metadata improves retrieval for category/domain/stage
        queries.

        No crop vocabulary is hardcoded here.
        """

        fields = [
            knowledge.crop,
            knowledge.category,
            knowledge.subcategory,
            knowledge.domain,
            knowledge.stage,
            knowledge.question,
            knowledge.answer,
            knowledge.keywords,
            knowledge.search_text,
        ]

        values = []

        for value in fields:

            if value:
                values.append(str(value))

        return " ".join(values)

    # =========================================================
    # Build Index
    # =========================================================

    def build_index(self):
        """
        Build/rebuild BM25 index from all active knowledge.

        Call this after importing/updating large knowledge sets
        if the BM25Service instance remains alive.
        """

        queryset = Knowledge.objects.filter(is_active=True).order_by("id")

        knowledge_objects = []

        documents = []

        for obj in queryset:

            document_text = self._build_document_text(obj)

            tokens = self.tokenize(document_text)

            # Empty documents should not enter the BM25 corpus.
            if not tokens:
                continue

            knowledge_objects.append(obj)

            documents.append(tokens)

        self.knowledge_objects = knowledge_objects

        self.documents = documents

        if self.documents:

            self.bm25 = BM25Okapi(self.documents)

        else:

            self.bm25 = None

        # Publish the newly built index so every future
        # BM25Service instance can reuse it.
        self._sync_to_shared_cache()

        print("\n" + "=" * 80)

        print("BM25 INDEX CREATED")

        print("=" * 80)

        print(
            "Documents :",
            len(self.documents),
        )

        print("=" * 80 + "\n")

    # =========================================================
    # Refresh Alias
    # =========================================================

    def refresh_index(self):
        """
        Explicitly rebuild the shared BM25 index.

        Call this after importing/updating/deleting knowledge.
        """

        cls = type(self)

        with cls._cache_lock:

            self.build_index()

        return True

    # =========================================================
    # Search
    # =========================================================

    def search(
        self,
        question: str,
        top_k: int = DEFAULT_TOP_K,
        language: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Search knowledge using crop-safe BM25 ranking.

        Returns:
        {
            "match_type": "bm25" | "none",
            "results": [...],
            "query_metadata": {...}
        }
        """

        top_k = self._normalize_top_k(top_k)

        # =====================================================
        # 1. Validate Index
        # =====================================================

        if self.bm25 is None or not self.knowledge_objects:

            return self._empty_response(
                question=question,
                reason="BM25 index is empty.",
            )

        # =====================================================
        # 2. Preprocess Query
        # =====================================================

        processed = self.preprocessor.preprocess(question)

        normalized_question = processed.get(
            "normalized",
            "",
        )

        query_tokens = processed.get("lexical_tokens")

        if query_tokens is None:
            query_tokens = processed.get(
                "tokens",
                [],
            )

        if not query_tokens:

            return self._empty_response(
                question=question,
                normalized_question=(normalized_question),
                reason=("Query contains no searchable tokens."),
            )

        # =====================================================
        # 3. Resolve Query Crop
        # =====================================================

        crop_info = self._resolve_crop(
            question=question,
            normalized_question=(normalized_question),
        )

        query_crop = crop_info.get("crop")

        crop_detected = bool(query_crop)

        # =====================================================
        # 4. BM25 Scores
        # =====================================================

        scores = self.bm25.get_scores(query_tokens)

        ranked = []

        filtered_crop_mismatch = 0

        for score, knowledge in zip(
            scores,
            self.knowledge_objects,
        ):

            raw_score = float(score)

            # -------------------------------------------------
            # Ignore non-positive BM25 results.
            # -------------------------------------------------

            if raw_score <= self.MIN_SCORE:
                continue

            knowledge_crop = knowledge.crop or ""

            crop_match = None

            # -------------------------------------------------
            # Crop Safety
            # -------------------------------------------------
            #
            # If query explicitly resolves to a crop:
            #
            # MATCHING CROP  -> allowed
            # BLANK CROP     -> allowed as general knowledge
            # DIFFERENT CROP -> rejected
            #
            # Example:
            #
            # Query = Wheat fertilizer
            # Record = Soybean fertilizer
            #
            # Generic word "fertilizer" must not make the
            # Soybean record eligible.
            # -------------------------------------------------

            if crop_detected:

                if not knowledge_crop.strip():

                    crop_match = None

                else:

                    crop_match = self._crop_matches(
                        query_crop,
                        knowledge_crop,
                    )

                    if not crop_match:

                        filtered_crop_mismatch += 1

                        continue

            # -------------------------------------------------
            # Language Preference
            # -------------------------------------------------

            language_match = None

            if language:

                language_match = (
                    str(knowledge.language or "").casefold() == str(language).casefold()
                )

            # -------------------------------------------------
            # Ranking Score
            # -------------------------------------------------
            #
            # Keep raw BM25 score separately.
            # Hybrid/Relevance services must use raw score,
            # not metadata bonuses.
            # -------------------------------------------------

            ranking_score = raw_score

            if crop_match is True:

                ranking_score += self.CROP_MATCH_BONUS

            ranked.append(
                {
                    "knowledge": knowledge,
                    # Backward compatibility
                    "score": float(ranking_score),
                    # Critical raw retrieval signal
                    "bm25_raw_score": float(raw_score),
                    "crop_match": crop_match,
                    "language_match": (language_match),
                }
            )

        # =====================================================
        # 5. Sort
        # =====================================================

        ranked.sort(
            key=self._sort_key,
            reverse=True,
        )

        results = ranked[:top_k]

        # =====================================================
        # 6. Debug
        # =====================================================

        self._debug_search(
            question=question,
            normalized_question=(normalized_question),
            query_tokens=query_tokens,
            crop_info=crop_info,
            filtered_crop_mismatch=(filtered_crop_mismatch),
            results=ranked,
        )

        # =====================================================
        # 7. Return
        # =====================================================

        return {
            "match_type": ("bm25" if results else "none"),
            "results": results,
            "query_metadata": {
                "normalized_question": (normalized_question),
                "tokens": list(dict.fromkeys(query_tokens)),
                "crop": query_crop,
                "crop_detected": (crop_detected),
                "crop_resolution": (crop_info),
                "crop_mismatches_filtered": (filtered_crop_mismatch),
            },
        }

    # =========================================================
    # Crop Resolution
    # =========================================================
    def _resolve_crop(
        self,
        question: str,
        normalized_question: str,
    ) -> Dict[str, Any]:
        """
        Resolve crop from a complete farmer question.
        """

        if self.crop_resolver is None:

            return {
                "crop": None,
                "resolved": False,
                "source": "unavailable",
            }

        # Full questions should use resolve_query first.
        resolve_query = getattr(
            self.crop_resolver,
            "resolve_query",
            None,
        )

        if callable(resolve_query):

            try:

                result = resolve_query(question)

                parsed = self._parse_crop_result(result)

                if parsed.get("crop"):

                    parsed["source"] = (
                        parsed.get("source")
                        or "resolve_query"
                    )

                    return parsed

            except Exception as exc:

                print(
                    "BM25 CROP RESOLUTION ERROR:",
                    str(exc),
                )

        # Fallback for resolver interface variations.
        for method_name in [
            "detect",
            "resolve_crop",
            "extract",
            "resolve",
        ]:

            method = getattr(
                self.crop_resolver,
                method_name,
                None,
            )

            if not callable(method):
                continue

            try:

                result = method(normalized_question)

            except Exception:
                continue

            parsed = self._parse_crop_result(result)

            if parsed.get("crop"):

                parsed["source"] = (
                    parsed.get("source")
                    or method_name
                )

                return parsed

        return {
            "crop": None,
            "resolved": False,
            "source": "crop_resolver",
        }


    # =========================================================
    # Crop Result Parser
    # =========================================================

    def _parse_crop_result(
        self,
        result: Any,
    ) -> Dict[str, Any]:

        if result is None:

            return {
                "crop": None,
                "resolved": False,
            }

        if isinstance(
            result,
            str,
        ):

            crop = result.strip()

            return {
                "crop": crop or None,
                "resolved": bool(crop),
                "raw": result,
            }

        if isinstance(
            result,
            dict,
        ):

            crop = None

            for key in [
                "crop",
                "resolved_crop",
                "canonical_crop",
                "name",
            ]:

                value = result.get(key)

                if value:

                    crop = str(value).strip()

                    break

            parsed = dict(result)

            parsed["crop"] = crop or None

            parsed["resolved"] = bool(crop)

            return parsed

        if isinstance(
            result,
            (
                list,
                tuple,
                set,
            ),
        ):

            crops = [str(value).strip() for value in result if value]

            if crops:

                return {
                    "crop": crops[0],
                    "crops": crops,
                    "resolved": True,
                    "raw": result,
                }

        return {
            "crop": None,
            "resolved": False,
            "raw": result,
        }

    # =========================================================
    # Crop Normalization
    # =========================================================

    def _normalize_crop(
        self,
        crop: Any,
    ) -> str:

        if crop is None:
            return ""

        crop = str(crop).strip()

        if not crop:
            return ""

        try:

            return self.preprocessor.normalizer.normalize(crop).casefold().strip()

        except Exception:

            return crop.casefold()

    # =========================================================
    # Crop Match
    # =========================================================

    def _crop_matches(
        self,
        query_crop: Any,
        knowledge_crop: Any,
    ) -> bool:

        query_crop = self._normalize_crop(query_crop)

        knowledge_crop = self._normalize_crop(knowledge_crop)

        if not query_crop or not knowledge_crop:

            return False

        if query_crop == knowledge_crop:

            return True

        # QuestionNormalizer/CropResolver may already have
        # converted aliases to a canonical crop name.
        return query_crop in knowledge_crop or knowledge_crop in query_crop

    # =========================================================
    # Sort Key
    # =========================================================

    @staticmethod
    def _sort_key(
        result: Dict[str, Any],
    ):

        knowledge = result["knowledge"]

        return (
            float(
                result.get(
                    "score",
                    0.0,
                )
            ),
            float(
                result.get(
                    "bm25_raw_score",
                    0.0,
                )
            ),
            int(
                getattr(
                    knowledge,
                    "priority",
                    0,
                )
                or 0
            ),
            -len(
                getattr(
                    knowledge,
                    "question",
                    "",
                )
                or ""
            ),
        )

    # =========================================================
    # Normalize Top K
    # =========================================================

    def _normalize_top_k(
        self,
        value: Any,
    ) -> int:

        try:

            value = int(value)

        except (
            TypeError,
            ValueError,
        ):

            value = self.DEFAULT_TOP_K

        return max(
            1,
            min(
                value,
                self.MAX_TOP_K,
            ),
        )

    # =========================================================
    # Empty Response
    # =========================================================

    @staticmethod
    def _empty_response(
        question="",
        normalized_question="",
        reason="",
    ) -> Dict[str, Any]:

        return {
            "match_type": "none",
            "results": [],
            "query_metadata": {
                "original_question": (question),
                "normalized_question": (normalized_question),
                "crop": None,
                "crop_detected": False,
                "reason": reason,
            },
        }

    # =========================================================
    # Debug
    # =========================================================

    @staticmethod
    def _debug_search(
        question,
        normalized_question,
        query_tokens,
        crop_info,
        filtered_crop_mismatch,
        results,
    ):

        print("\n" + "=" * 80)

        print("BM25 SEARCH")

        print("=" * 80)

        print(
            "Question            :",
            question,
        )

        print(
            "Normalized Question :",
            normalized_question,
        )

        print(
            "Tokens              :",
            query_tokens,
        )

        print(
            "Resolved Crop       :",
            crop_info.get("crop"),
        )

        print(
            "Crop Resolution     :",
            crop_info,
        )

        print(
            "Crop Mismatch Removed:",
            filtered_crop_mismatch,
        )

        print("-" * 80)

        if not results:

            print("No valid BM25 results.")

        for result in results[:10]:

            knowledge = result["knowledge"]

            print(
                "Raw Score :",
                round(
                    result.get(
                        "bm25_raw_score",
                        0.0,
                    ),
                    4,
                ),
            )

            print(
                "Rank Score:",
                round(
                    result.get(
                        "score",
                        0.0,
                    ),
                    4,
                ),
            )

            print(
                "Crop      :",
                knowledge.crop,
            )

            print(
                "Crop Match:",
                result.get("crop_match"),
            )

            print(
                "Question  :",
                knowledge.question,
            )

            print("-" * 80)

        print("=" * 80 + "\n")
