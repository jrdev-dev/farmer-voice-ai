from typing import Any, Dict, List, Optional

from .vector_store import VectorStore
from .normalizer import QuestionNormalizer
from .crop_resolver import CropResolver


class SemanticSearch:
    """
    Universal crop-aware semantic search using FAISS.

    Responsibilities
    ----------------
    1. Normalize multilingual farmer queries.
    2. Search FAISS vector database.
    3. Resolve crop dynamically.
    4. Prevent cross-crop semantic leakage.
    5. Preserve crop-independent/general knowledge.
    6. Retrieve a wider candidate pool before filtering.
    7. Preserve raw semantic similarity scores.
    8. Support future crops without hardcoded crop lists.

    IMPORTANT
    ---------
    Semantic similarity alone must not override crop identity.

    No fixed crop list is maintained here.
    """

    # =========================================================
    # Configuration
    # =========================================================

    DEFAULT_TOP_K = 5
    MAX_TOP_K = 50

    # Retrieve more candidates before crop filtering.
    CANDIDATE_MULTIPLIER = 5
    MIN_CANDIDATE_POOL = 20
    MAX_CANDIDATE_POOL = 100

    # Small ranking bonus only.
    # Raw semantic score remains untouched.
    CROP_MATCH_BONUS = 0.02

    # =========================================================
    # Initialization
    # =========================================================

    def __init__(self):
        self.vector_store = VectorStore()
        self.normalizer = QuestionNormalizer()

        try:
            self.crop_resolver = CropResolver()
        except Exception as exc:
            print(
                "SEMANTIC CROP RESOLVER INITIALIZATION ERROR:",
                str(exc),
            )
            self.crop_resolver = None

        # Load existing FAISS index.
        self.vector_store.load()

    # =========================================================
    # Main Search
    # =========================================================

    def search(
        self,
        question: str,
        top_k: int = DEFAULT_TOP_K,
        language: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Search semantically similar knowledge while enforcing
        crop safety.

        Returns
        -------
        {
            "match_type": "semantic" | "none",
            "results": [...],
            "query_metadata": {...}
        }
        """

        top_k = self._normalize_top_k(top_k)

        # =====================================================
        # 1. Validate Query
        # =====================================================

        if not question or not str(question).strip():
            return self._empty_response(reason="Empty semantic query.")

        original_question = str(question).strip()

        # =====================================================
        # 2. Normalize Query
        # =====================================================

        try:
            normalized_question = self.normalizer.normalize(original_question)
        except Exception as exc:
            print(
                "SEMANTIC QUERY NORMALIZATION ERROR:",
                str(exc),
            )
            normalized_question = original_question

        if not normalized_question:
            return self._empty_response(
                original_question=original_question,
                reason="Query became empty after normalization.",
            )

        normalized_question = str(normalized_question).strip()

        # =====================================================
        # 3. Resolve Crop
        # =====================================================

        crop_info = self._resolve_crop(
            question=original_question,
            normalized_question=normalized_question,
        )

        query_crop = crop_info.get("crop")
        crop_detected = bool(query_crop)

        # =====================================================
        # 4. Candidate Pool
        # =====================================================

        candidate_k = max(
            self.MIN_CANDIDATE_POOL,
            top_k * self.CANDIDATE_MULTIPLIER,
        )

        candidate_k = min(
            candidate_k,
            self.MAX_CANDIDATE_POOL,
        )

        # =====================================================
        # 5. Debug Header
        # =====================================================

        print("\n" + "=" * 80)
        print("SEMANTIC SEARCH")
        print("=" * 80)

        print(
            "Original Question   :",
            original_question,
        )
        print(
            "Normalized Question :",
            normalized_question,
        )
        print(
            "Resolved Crop       :",
            query_crop,
        )
        print(
            "Crop Resolution     :",
            crop_info,
        )
        print(
            "Requested Top K     :",
            top_k,
        )
        print(
            "FAISS Candidate K   :",
            candidate_k,
        )

        print("-" * 80)

        # =====================================================
        # 6. Vector Search
        # =====================================================

        try:
            raw_results = self.vector_store.search(
                question=normalized_question,
                top_k=candidate_k,
            )
        except Exception as exc:
            print(
                "VECTOR STORE SEARCH ERROR:",
                str(exc),
            )
            print("=" * 80 + "\n")

            return self._empty_response(
                original_question=original_question,
                normalized_question=normalized_question,
                crop_info=crop_info,
                reason=f"Vector search failed: {exc}",
            )

        raw_results = self._extract_results(raw_results)

        if not raw_results:
            print("No semantic candidates found.")
            print("=" * 80 + "\n")

            return self._empty_response(
                original_question=original_question,
                normalized_question=normalized_question,
                crop_info=crop_info,
                reason="Vector store returned no results.",
            )

        # =====================================================
        # 7. Crop-Safe Filtering
        # =====================================================

        safe_results: List[Dict[str, Any]] = []

        crop_mismatches_filtered = 0
        invalid_results_filtered = 0

        for result in raw_results:

            if not isinstance(result, dict):
                invalid_results_filtered += 1
                continue

            knowledge = result.get("knowledge")

            if knowledge is None:
                invalid_results_filtered += 1
                continue

            knowledge_crop = str(
                getattr(
                    knowledge,
                    "crop",
                    "",
                )
                or ""
            ).strip()

            crop_match = None

            # -------------------------------------------------
            # Crop Safety
            # -------------------------------------------------

            if crop_detected and knowledge_crop:

                crop_match = self._crop_matches(
                    query_crop,
                    knowledge_crop,
                )

                if not crop_match:
                    crop_mismatches_filtered += 1
                    continue

            # -------------------------------------------------
            # Semantic Raw Score
            # -------------------------------------------------

            semantic_raw_score = self._extract_semantic_score(result)

            # -------------------------------------------------
            # Ranking Score
            # -------------------------------------------------

            ranking_score = semantic_raw_score

            if crop_match is True:
                ranking_score += self.CROP_MATCH_BONUS

            if 0.0 <= semantic_raw_score <= 1.0:
                ranking_score = min(
                    1.0,
                    ranking_score,
                )

            # -------------------------------------------------
            # Language Metadata
            # -------------------------------------------------

            language_match = None

            if language:
                knowledge_language = str(
                    getattr(
                        knowledge,
                        "language",
                        "",
                    )
                    or ""
                ).casefold()

                language_match = knowledge_language == str(language).casefold()

            # -------------------------------------------------
            # Preserve Existing Result Metadata
            # -------------------------------------------------

            safe_result = dict(result)

            safe_result["knowledge"] = knowledge

            safe_result["semantic_raw_score"] = float(semantic_raw_score)

            safe_result["score"] = float(ranking_score)

            safe_result["crop_match"] = crop_match
            safe_result["language_match"] = language_match

            # Useful downstream metadata.
            safe_result["query_crop"] = query_crop
            safe_result["query_crop_resolution"] = crop_info

            safe_results.append(safe_result)

        # =====================================================
        # 8. Sort Safe Results
        # =====================================================

        safe_results.sort(
            key=self._sort_key,
            reverse=True,
        )

        final_results = safe_results[:top_k]

        # =====================================================
        # 9. Debug Results
        # =====================================================

        print(
            "Raw FAISS Results       :",
            len(raw_results),
        )

        print(
            "Crop Mismatches Removed :",
            crop_mismatches_filtered,
        )

        print(
            "Invalid Results Removed :",
            invalid_results_filtered,
        )

        print(
            "Safe Semantic Results   :",
            len(safe_results),
        )

        print("-" * 80)

        if not safe_results:
            print("No crop-safe semantic results.")

        for result in safe_results[:10]:

            knowledge = result["knowledge"]

            print(
                "Raw Score  :",
                round(
                    result.get(
                        "semantic_raw_score",
                        0.0,
                    ),
                    4,
                ),
            )

            print(
                "Rank Score :",
                round(
                    result.get(
                        "score",
                        0.0,
                    ),
                    4,
                ),
            )

            print(
                "Crop       :",
                getattr(
                    knowledge,
                    "crop",
                    "",
                ),
            )

            print(
                "Crop Match :",
                result.get("crop_match"),
            )

            print(
                "Question   :",
                getattr(
                    knowledge,
                    "question",
                    "",
                ),
            )

            print("-" * 80)

        print("=" * 80 + "\n")

        # =====================================================
        # 10. Return
        # =====================================================

        return {
            "match_type": ("semantic" if final_results else "none"),
            "results": final_results,
            "query_metadata": {
                "original_question": original_question,
                "normalized_question": normalized_question,
                "crop": query_crop,
                "crop_detected": crop_detected,
                "crop_resolution": crop_info,
                "requested_top_k": top_k,
                "candidate_k": candidate_k,
                "raw_candidate_count": len(raw_results),
                "crop_mismatches_filtered": (crop_mismatches_filtered),
                "invalid_results_filtered": (invalid_results_filtered),
                "safe_candidate_count": len(safe_results),
            },
        }

    # =========================================================
    # Extract Vector Store Results
    # =========================================================

    @staticmethod
    def _extract_results(
        value: Any,
    ) -> List[Dict[str, Any]]:
        """
        Support both:

            [{...}, {...}]

        and:

            {"results": [...]}
        """

        if value is None:
            return []

        if isinstance(value, list):
            return value

        if isinstance(value, tuple):
            return list(value)

        if isinstance(value, dict):
            results = value.get("results")

            if isinstance(results, list):
                return results

            if isinstance(results, tuple):
                return list(results)

        return []

    # =========================================================
    # Extract Semantic Score
    # =========================================================

    @staticmethod
    def _extract_semantic_score(
        result: Dict[str, Any],
    ) -> float:
        """
        Extract raw semantic similarity from VectorStore result.

        Supports common score field names while preserving
        compatibility with the existing VectorStore.
        """

        possible_keys = (
            "semantic_raw_score",
            "similarity",
            "similarity_score",
            "score",
        )

        for key in possible_keys:

            value = result.get(key)

            if value is None:
                continue

            try:
                return float(value)

            except (
                TypeError,
                ValueError,
            ):
                continue

        return 0.0

    # =========================================================
    # Crop Resolution
    # =========================================================

    def _resolve_crop(
        self,
        question: str,
        normalized_question: str,
    ) -> Dict[str, Any]:
        """
        Resolve crop dynamically from a complete farmer query.

        Priority
        --------
        1. resolve_query()
        2. detect()
        3. resolve_crop()
        4. extract()
        5. resolve()

        No crop-specific hardcoding is maintained here.
        """

        if self.crop_resolver is None:
            return {
                "crop": None,
                "resolved": False,
                "source": "unavailable",
            }

        # =====================================================
        # 1. Preferred Full Query Resolution
        # =====================================================

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

                    parsed["source"] = parsed.get("source") or "resolve_query"

                    return parsed

            except Exception as exc:
                print(
                    "SEMANTIC CROP RESOLUTION ERROR:",
                    str(exc),
                )

        # =====================================================
        # 2. Dynamic Detection
        # =====================================================

        detect = getattr(
            self.crop_resolver,
            "detect",
            None,
        )

        if callable(detect):

            try:
                result = detect(question)

                parsed = self._parse_crop_result(result)

                if parsed.get("crop"):

                    parsed["source"] = parsed.get("source") or "detect"

                    return parsed

            except Exception as exc:
                print(
                    "SEMANTIC CROP DETECTION ERROR:",
                    str(exc),
                )

        # =====================================================
        # 3. Compatibility Fallbacks
        # =====================================================

        for method_name in (
            "resolve_crop",
            "extract",
            "resolve",
        ):

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

                parsed["source"] = parsed.get("source") or method_name

                return parsed

        # =====================================================
        # 4. Nothing Resolved
        # =====================================================

        return {
            "crop": None,
            "resolved": False,
            "source": "crop_resolver",
        }

    # =========================================================
    # Parse Crop Resolver Result
    # =========================================================

    @staticmethod
    def _parse_crop_result(
        result: Any,
    ) -> Dict[str, Any]:

        if result is None:
            return {
                "crop": None,
                "resolved": False,
            }

        # -----------------------------------------------------
        # String result
        # -----------------------------------------------------

        if isinstance(result, str):

            crop = result.strip()

            return {
                "crop": crop or None,
                "resolved": bool(crop),
                "raw": result,
            }

        # -----------------------------------------------------
        # Dictionary result
        # -----------------------------------------------------

        if isinstance(result, dict):

            crop = None

            for key in (
                "crop",
                "resolved_crop",
                "canonical_crop",
                "name",
            ):

                value = result.get(key)

                if value:
                    crop = str(value).strip()
                    break

            # Some resolvers may return multiple crops.
            if not crop:

                crops = result.get("crops")

                if isinstance(
                    crops,
                    (list, tuple, set),
                ):

                    for value in crops:

                        if value:
                            crop = str(value).strip()
                            break

            parsed = dict(result)

            parsed["crop"] = crop or None
            parsed["resolved"] = bool(crop)

            return parsed

        # -----------------------------------------------------
        # Collection result
        # -----------------------------------------------------

        if isinstance(
            result,
            (list, tuple, set),
        ):

            crops = [
                str(value).strip() for value in result if value and str(value).strip()
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
        crop: Any,
    ) -> str:

        if crop is None:
            return ""

        crop = str(crop).strip()

        if not crop:
            return ""

        try:
            normalized = self.normalizer.normalize(crop)

            if normalized:
                return str(normalized).casefold().strip()

        except Exception:
            pass

        return crop.casefold()

    # =========================================================
    # Crop Matching
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

        # Exact canonical match.
        if query_crop == knowledge_crop:
            return True

        # Token-set equality supports normalized multi-word
        # crop names without substring false positives.
        query_tokens = set(query_crop.split())

        knowledge_tokens = set(knowledge_crop.split())

        if query_tokens and knowledge_tokens and query_tokens == knowledge_tokens:
            return True

        return False

    # =========================================================
    # Sort Key
    # =========================================================

    @staticmethod
    def _sort_key(
        result: Dict[str, Any],
    ):

        knowledge = result.get("knowledge")

        priority = 0

        if knowledge is not None:

            try:
                priority = int(
                    getattr(
                        knowledge,
                        "priority",
                        0,
                    )
                    or 0
                )

            except (
                TypeError,
                ValueError,
            ):
                priority = 0

        try:
            score = float(
                result.get(
                    "score",
                    0.0,
                )
            )
        except (
            TypeError,
            ValueError,
        ):
            score = 0.0

        try:
            semantic_raw = float(
                result.get(
                    "semantic_raw_score",
                    0.0,
                )
            )
        except (
            TypeError,
            ValueError,
        ):
            semantic_raw = 0.0

        return (
            score,
            semantic_raw,
            priority,
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
        original_question="",
        normalized_question="",
        crop_info=None,
        reason="",
    ) -> Dict[str, Any]:

        crop_info = crop_info or {}

        return {
            "match_type": "none",
            "results": [],
            "query_metadata": {
                "original_question": original_question,
                "normalized_question": normalized_question,
                "crop": crop_info.get("crop"),
                "crop_detected": bool(crop_info.get("crop")),
                "crop_resolution": crop_info,
                "reason": reason,
            },
        }
