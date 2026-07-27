import threading
from typing import Any, Dict, List, Optional

from apps.knowledge_base.services.search_engine import (
    KnowledgeSearchEngine,
)
from apps.knowledge_base.services.bm25_service import (
    BM25Service,
)
from apps.knowledge_base.services.fuzzy_service import (
    FuzzyService,
)
from apps.knowledge_base.services.semantic_search import (
    SemanticSearch,
)
from apps.knowledge_base.services.hybrid_ranker import (
    HybridRanker,
)
from apps.knowledge_base.services.crop_resolver import (
    CropResolver,
)


class RetrieverService:
    """
    Production hybrid retrieval orchestrator.

    Retrieval pipeline
    ------------------
    1. Keyword Search
    2. BM25 Search
    3. Fuzzy Search
    4. Semantic Search
    5. Hybrid Ranking
    6. Final crop-safety validation
    7. Final top-k selection

    Performance
    -----------
    RetrieverService can be reused as one shared instance
    inside the current Django process.

    This prevents repeatedly constructing:
    - KnowledgeSearchEngine
    - BM25Service
    - FuzzyService
    - SemanticSearch
    - HybridRanker
    - CropResolver

    Goals
    -----
    - Universal crop support
    - Multilingual retrieval
    - Cross-crop leakage prevention
    - Graceful retriever failure handling
    - Raw score preservation
    - Stable output contract
    - Fast repeated requests
    """

    DEFAULT_TOP_K = 5
    MAX_TOP_K = 20

    # Retrieve slightly more candidates from individual
    # retrievers before hybrid ranking.
    RETRIEVER_MULTIPLIER = 3

    # =========================================================
    # Shared Service Instance
    # =========================================================

    _shared_instance = None
    _instance_lock = threading.Lock()

    @classmethod
    def get_instance(cls):
        """
        Return one shared RetrieverService instance
        for the current Django process.

        Thread-safe double-checked initialization prevents
        multiple simultaneous requests from constructing
        duplicate retriever dependency graphs.
        """

        if cls._shared_instance is None:

            with cls._instance_lock:

                if cls._shared_instance is None:

                    print()
                    print("=" * 80)
                    print("INITIALIZING RETRIEVER SERVICE")
                    print("=" * 80)

                    cls._shared_instance = cls()

                    print("=" * 80)
                    print("RETRIEVER SERVICE READY")
                    print("=" * 80)
                    print()

        return cls._shared_instance

    @classmethod
    def reset_instance(cls):
        """
        Clear the shared RetrieverService instance.

        Primarily useful for tests or explicit runtime
        reinitialization.

        This does not automatically clear BM25, FAISS or
        embedding caches maintained by those services.
        """

        with cls._instance_lock:
            cls._shared_instance = None

    # =========================================================
    # Initialization
    # =========================================================

    def __init__(self):

        self.keyword = KnowledgeSearchEngine()

        self.bm25 = BM25Service()

        self.fuzzy = FuzzyService()

        self.semantic = SemanticSearch()

        self.hybrid = HybridRanker()

        try:
            self.crop_resolver = CropResolver()

        except Exception as exc:

            print(
                "CROP RESOLVER INITIALIZATION ERROR:",
                str(exc),
            )

            self.crop_resolver = None

    # =========================================================
    # Main Retrieval
    # =========================================================

    def retrieve(
        self,
        question: str,
        language: Optional[str] = None,
        top_k: int = DEFAULT_TOP_K,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve and rank trusted knowledge candidates.

        IMPORTANT
        ---------
        Backward-compatible return type remains:

            List[dict]

        so existing ChatService / RelevanceService code does
        not need to change merely because this orchestrator
        became more robust.
        """

        # =====================================================
        # 1. Validate Input
        # =====================================================

        if not question or not str(question).strip():
            return []

        question = str(question).strip()

        top_k = self._normalize_top_k(top_k)

        retriever_top_k = min(
            self.MAX_TOP_K,
            max(
                top_k,
                top_k * self.RETRIEVER_MULTIPLIER,
            ),
        )

        # =====================================================
        # 2. Resolve Query Crop
        # =====================================================

        crop_info = self._resolve_crop(question)

        query_crop = crop_info.get("crop")

        # =====================================================
        # 3. Keyword Search
        # =====================================================

        keyword_result = self._safe_search(
            name="keyword",
            service=self.keyword,
            question=question,
            language=language,
            top_k=retriever_top_k,
        )

        # =====================================================
        # 4. BM25 Search
        # =====================================================

        bm25_result = self._safe_search(
            name="bm25",
            service=self.bm25,
            question=question,
            language=language,
            top_k=retriever_top_k,
        )

        # =====================================================
        # 5. Fuzzy Search
        # =====================================================

        fuzzy_result = self._safe_search(
            name="fuzzy",
            service=self.fuzzy,
            question=question,
            language=language,
            top_k=retriever_top_k,
        )

        # =====================================================
        # 6. Semantic Search
        # =====================================================

        semantic_result = self._safe_search(
            name="semantic",
            service=self.semantic,
            question=question,
            language=language,
            top_k=retriever_top_k,
        )

        # =====================================================
        # 7. Hybrid Ranking
        # =====================================================

        try:

            ranked = self.hybrid.rank(
                question=question,
                keyword_result=keyword_result,
                bm25_result=bm25_result,
                fuzzy_result=fuzzy_result,
                semantic_result=semantic_result,
            )

        except Exception as exc:

            print(
                "HYBRID RANKING ERROR:",
                str(exc),
            )

            ranked = []

        # =====================================================
        # 8. Final Crop Safety
        # =====================================================

        safe_ranked = []

        crop_mismatches_removed = 0

        seen_ids = set()

        for result in ranked:

            if not isinstance(result, dict):
                continue

            knowledge = result.get("knowledge")

            if knowledge is None:
                continue

            knowledge_id = getattr(
                knowledge,
                "id",
                None,
            )

            if knowledge_id is None:
                continue

            # ---------------------------------------------
            # Duplicate Protection
            # ---------------------------------------------

            if knowledge_id in seen_ids:
                continue

            # ---------------------------------------------
            # Crop Protection
            # ---------------------------------------------

            knowledge_crop = str(
                getattr(
                    knowledge,
                    "crop",
                    "",
                )
                or ""
            ).strip()

            if query_crop and knowledge_crop:

                if not self._crop_matches(
                    query_crop,
                    knowledge_crop,
                ):

                    crop_mismatches_removed += 1

                    continue

            seen_ids.add(knowledge_id)

            # ---------------------------------------------
            # Preserve Query Metadata
            # ---------------------------------------------

            result = dict(result)

            result["query_crop"] = query_crop

            result["query_crop_resolution"] = crop_info

            safe_ranked.append(result)

        # =====================================================
        # 9. Final Sort
        # =====================================================

        safe_ranked.sort(
            key=lambda item: float(
                item.get(
                    "score",
                    0.0,
                )
            ),
            reverse=True,
        )

        final_results = safe_ranked[:top_k]

        # =====================================================
        # 10. Debug
        # =====================================================

        self._debug(
            question=question,
            language=language,
            crop_info=crop_info,
            keyword_result=keyword_result,
            bm25_result=bm25_result,
            fuzzy_result=fuzzy_result,
            semantic_result=semantic_result,
            ranked=ranked,
            final_results=final_results,
            crop_mismatches_removed=(
                crop_mismatches_removed
            ),
        )

        return final_results

    # =========================================================
    # Safe Retriever Execution
    # =========================================================

    def _safe_search(
        self,
        name,
        service,
        question,
        language,
        top_k,
    ) -> Dict[str, Any]:
        """
        Execute one retriever without allowing a single
        retrieval failure to crash the complete RAG pipeline.
        """

        try:

            # New retriever interface.
            try:

                result = service.search(
                    question=question,
                    language=language,
                    top_k=top_k,
                )

            except TypeError:

                # Backward compatibility for services that
                # don't yet accept language.
                result = service.search(
                    question=question,
                    top_k=top_k,
                )

            return self._normalize_result(
                result,
                name,
            )

        except Exception as exc:

            print(
                f"{name.upper()} SEARCH ERROR:",
                str(exc),
            )

            return {
                "match_type": "none",
                "results": [],
                "error": str(exc),
            }

    # =========================================================
    # Normalize Retriever Result
    # =========================================================

    @staticmethod
    def _normalize_result(
        result,
        name,
    ) -> Dict[str, Any]:
        """
        Convert retriever output into a common structure.
        """

        if result is None:

            return {
                "match_type": "none",
                "results": [],
            }

        if isinstance(
            result,
            list,
        ):

            return {
                "match_type": name,
                "results": result,
            }

        if isinstance(
            result,
            dict,
        ):

            results = result.get(
                "results",
                [],
            )

            if not isinstance(
                results,
                list,
            ):
                results = []

            normalized = dict(result)

            normalized["results"] = results

            return normalized

        return {
            "match_type": "none",
            "results": [],
        }

    # =========================================================
    # Crop Resolution
    # =========================================================

    def _resolve_crop(
        self,
        question: str,
    ) -> Dict[str, Any]:
        """
        Resolve crop from a complete farmer question.

        resolve_query() is intentionally preferred because
        the input is a complete natural-language question,
        not merely a crop name.
        """

        if self.crop_resolver is None:

            return {
                "crop": None,
                "resolved": False,
                "source": "unavailable",
            }

        # =====================================================
        # Preferred Full-Query Resolution
        # =====================================================

        try:

            result = self.crop_resolver.resolve_query(
                question
            )

            parsed = self._parse_crop_result(
                result
            )

            if parsed.get("crop"):

                parsed["source"] = (
                    parsed.get("source")
                    or "resolve_query"
                )

                return parsed

        except Exception as exc:

            print(
                "CROP RESOLUTION ERROR:",
                str(exc),
            )

        # =====================================================
        # Optional Detection Fallback
        # =====================================================

        detect = getattr(
            self.crop_resolver,
            "detect",
            None,
        )

        if callable(detect):

            try:

                result = detect(question)

                parsed = self._parse_crop_result(
                    result
                )

                if parsed.get("crop"):

                    parsed["source"] = (
                        parsed.get("source")
                        or "detect"
                    )

                    return parsed

            except Exception:
                pass

        return {
            "crop": None,
            "resolved": False,
            "source": "crop_resolver",
        }

    # =========================================================
    # Parse Crop Result
    # =========================================================

    @staticmethod
    def _parse_crop_result(
        result,
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

            crops = [
                str(value).strip()
                for value in result
                if value
            ]

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
        crop,
    ) -> str:

        if crop is None:
            return ""

        crop = str(crop).strip()

        if not crop:
            return ""

        # Reuse the same normalizer already attached to the
        # keyword search preprocessor where available.

        try:

            normalizer = (
                self.keyword
                .preprocessor
                .normalizer
            )

            return (
                normalizer
                .normalize(crop)
                .casefold()
                .strip()
            )

        except Exception:

            return crop.casefold()

    # =========================================================
    # Crop Matching
    # =========================================================

    def _crop_matches(
        self,
        query_crop,
        knowledge_crop,
    ) -> bool:

        query_crop = self._normalize_crop(
            query_crop
        )

        knowledge_crop = self._normalize_crop(
            knowledge_crop
        )

        if not query_crop or not knowledge_crop:
            return False

        if query_crop == knowledge_crop:
            return True

        return (
            query_crop in knowledge_crop
            or knowledge_crop in query_crop
        )

    # =========================================================
    # Normalize Top K
    # =========================================================

    def _normalize_top_k(
        self,
        value,
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
    # Result Count
    # =========================================================

    @staticmethod
    def _result_count(
        result,
    ) -> int:

        if not isinstance(
            result,
            dict,
        ):
            return 0

        results = result.get(
            "results",
            [],
        )

        if not isinstance(
            results,
            list,
        ):
            return 0

        return len(results)

    # =========================================================
    # Debug
    # =========================================================

    def _debug(
        self,
        question,
        language,
        crop_info,
        keyword_result,
        bm25_result,
        fuzzy_result,
        semantic_result,
        ranked,
        final_results,
        crop_mismatches_removed,
    ):

        print("\n" + "=" * 80)

        print("RETRIEVER SERVICE")

        print("=" * 80)

        print(
            "Question       :",
            question,
        )

        print(
            "Language       :",
            language,
        )

        print(
            "Resolved Crop  :",
            crop_info.get("crop"),
        )

        print(
            "Crop Resolution:",
            crop_info,
        )

        print("-" * 80)

        print(
            "Keyword Results :",
            self._result_count(
                keyword_result
            ),
        )

        print(
            "BM25 Results    :",
            self._result_count(
                bm25_result
            ),
        )

        print(
            "Fuzzy Results   :",
            self._result_count(
                fuzzy_result
            ),
        )

        print(
            "Semantic Results:",
            self._result_count(
                semantic_result
            ),
        )

        print(
            "Hybrid Results  :",
            len(ranked),
        )

        print(
            "Crop Removed    :",
            crop_mismatches_removed,
        )

        print(
            "Final Results   :",
            len(final_results),
        )

        print("-" * 80)

        for index, result in enumerate(
            final_results,
            start=1,
        ):

            knowledge = result.get(
                "knowledge"
            )

            print(
                f"#{index}"
            )

            print(
                "Score :",
                round(
                    float(
                        result.get(
                            "score",
                            0.0,
                        )
                    ),
                    4,
                ),
            )

            print(
                "Crop  :",
                getattr(
                    knowledge,
                    "crop",
                    "",
                ),
            )

            print(
                "Ques  :",
                getattr(
                    knowledge,
                    "question",
                    "",
                ),
            )

            print(
                "Raw   :",
                {
                    "keyword": round(
                        float(
                            result.get(
                                "keyword_raw_score",
                                0.0,
                            )
                        ),
                        4,
                    ),
                    "bm25": round(
                        float(
                            result.get(
                                "bm25_raw_score",
                                0.0,
                            )
                        ),
                        4,
                    ),
                    "fuzzy": round(
                        float(
                            result.get(
                                "fuzzy_raw_score",
                                0.0,
                            )
                        ),
                        4,
                    ),
                    "semantic": round(
                        float(
                            result.get(
                                "semantic_raw_score",
                                0.0,
                            )
                        ),
                        4,
                    ),
                },
            )

            print("-" * 80)

        print(
            "=" * 80 + "\n"
        )