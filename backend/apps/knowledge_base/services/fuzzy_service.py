from typing import Any, Dict, Optional

from rapidfuzz import fuzz

from apps.knowledge_base.models import Knowledge

from .search_preprocessor import SearchPreprocessor
from .crop_resolver import CropResolver


class FuzzyService:
    """
    Universal crop-aware fuzzy retrieval service.

    Responsibilities
    ----------------
    1. Normalize multilingual farmer queries.
    2. Compare query with knowledge questions.
    3. Compare query with searchable knowledge text.
    4. Dynamically resolve crops.
    5. Prevent cross-crop fuzzy leakage.
    6. Allow crop-independent/general knowledge.
    7. Return raw fuzzy similarity for relevance scoring.
    8. Support future crops without hardcoded crop lists.

    IMPORTANT
    ---------
    Crop similarity is contextual evidence only.

    Question/search similarity remains the primary fuzzy signal.

    If a crop is confidently resolved from the query, records
    belonging to a different crop are rejected.
    """

    # =========================================================
    # Configuration
    # =========================================================

    MIN_SCORE = 55.0

    MIN_QUESTION_SIGNAL = 30.0

    MIN_SEARCH_SIGNAL = 40.0

    QUESTION_WEIGHT = 0.70

    SEARCH_WEIGHT = 0.30

    CROP_BONUS = 5.0

    CROP_BONUS_MIN_QUESTION = 35.0

    CROP_BONUS_MIN_SIMILARITY = 80.0

    DEFAULT_TOP_K = 5

    MAX_TOP_K = 50

    # =========================================================
    # Initialization
    # =========================================================

    def __init__(self):

        self.preprocessor = SearchPreprocessor()

        try:
            self.crop_resolver = CropResolver()

        except Exception:
            self.crop_resolver = None

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
        Search active knowledge using fuzzy similarity.
        """

        top_k = self._normalize_top_k(top_k)

        # =====================================================
        # 1. Preprocess Query
        # =====================================================

        processed = self.preprocessor.preprocess(question)

        normalized_question = processed.get(
            "normalized",
            "",
        )

        query_tokens = processed.get(
            "tokens",
            [],
        )

        query_text = " ".join(query_tokens)

        # =====================================================
        # 2. Resolve Query Crop
        # =====================================================

        crop_info = self._resolve_crop(
            question=question,
            normalized_question=normalized_question,
        )

        query_crop = crop_info.get("crop")

        crop_detected = bool(query_crop)

        # =====================================================
        # 3. Debug Header
        # =====================================================

        print("\n" + "=" * 80)

        print("FUZZY SEARCH")

        print("=" * 80)

        print(
            "Original Question   :",
            question,
        )

        print(
            "Normalized Question :",
            normalized_question,
        )

        print(
            "Query Text          :",
            query_text,
        )

        print(
            "Resolved Crop       :",
            query_crop,
        )

        print(
            "Crop Resolution     :",
            crop_info,
        )

        print("-" * 80)

        # =====================================================
        # 4. Empty Query
        # =====================================================

        if not query_text:

            print("No searchable fuzzy query.")

            print("=" * 80 + "\n")

            return self._empty_response(
                normalized_question=normalized_question,
                crop_info=crop_info,
                reason="Query contains no searchable tokens.",
            )

        # =====================================================
        # 5. Compare Knowledge Records
        # =====================================================

        results = []

        crop_mismatches_filtered = 0

        queryset = Knowledge.objects.filter(is_active=True)

        for obj in queryset:

            knowledge_crop = (obj.crop or "").strip()

            crop_match = None

            # =================================================
            # Crop Safety
            # =================================================
            #
            # If query crop is known:
            #
            # Same crop      -> allowed
            # Blank crop     -> allowed as general knowledge
            # Different crop -> rejected
            #
            # This prevents:
            #
            # Wheat fertilizer query
            #       ↓
            # Soybean fertilizer record
            #
            # from becoming a fuzzy match simply because both
            # contain generic agricultural vocabulary.
            # =================================================

            if crop_detected:

                if knowledge_crop:

                    crop_match = self._crop_matches(
                        query_crop,
                        knowledge_crop,
                    )

                    if not crop_match:

                        crop_mismatches_filtered += 1

                        continue

            # =================================================
            # Preprocess Knowledge Fields
            # =================================================

            crop_text = self._prepare_text(obj.crop)

            db_question = self._prepare_text(obj.question)

            search_text = self._prepare_text(obj.search_text)

            # If search_text is missing, construct useful
            # searchable context from trusted fields.

            if not search_text:

                search_text = self._prepare_text(
                    " ".join(
                        str(value)
                        for value in [
                            obj.crop,
                            obj.category,
                            obj.subcategory,
                            obj.domain,
                            obj.stage,
                            obj.question,
                            obj.answer,
                            obj.keywords,
                        ]
                        if value
                    )
                )

            # =================================================
            # Question Similarity
            # =================================================

            question_score = 0.0

            if db_question:

                question_score = float(
                    fuzz.token_set_ratio(
                        query_text,
                        db_question,
                    )
                )

            # =================================================
            # Search Text Similarity
            # =================================================

            search_score = 0.0

            if search_text:

                search_score = float(
                    fuzz.token_set_ratio(
                        query_text,
                        search_text,
                    )
                )

            # =================================================
            # Crop Similarity
            # =================================================

            crop_score = 0.0

            if crop_text:

                crop_score = float(
                    fuzz.token_set_ratio(
                        query_text,
                        crop_text,
                    )
                )

            # =================================================
            # Reject Weak Semantic Text Matches
            # =================================================
            #
            # Crop alone must NEVER create a valid fuzzy match.
            # =================================================

            if (
                question_score < self.MIN_QUESTION_SIGNAL
                and search_score < self.MIN_SEARCH_SIGNAL
            ):
                continue

            # =================================================
            # Raw Fuzzy Score
            # =================================================
            #
            # This is the actual fuzzy evidence.
            #
            # RelevanceService should use this value rather
            # than metadata bonuses.
            # =================================================

            raw_fuzzy_score = (
                question_score * self.QUESTION_WEIGHT
                + search_score * self.SEARCH_WEIGHT
            )

            # =================================================
            # Crop Bonus
            # =================================================

            crop_bonus = 0.0

            if crop_match is True and question_score >= self.CROP_BONUS_MIN_QUESTION:

                crop_bonus = self.CROP_BONUS

            elif (
                not crop_detected
                and question_score >= self.CROP_BONUS_MIN_QUESTION
                and crop_score >= self.CROP_BONUS_MIN_SIMILARITY
            ):

                crop_bonus = self.CROP_BONUS

            # =================================================
            # Final Ranking Score
            # =================================================

            final_score = min(
                100.0,
                raw_fuzzy_score + crop_bonus,
            )

            # =================================================
            # Minimum Fuzzy Threshold
            # =================================================

            if raw_fuzzy_score < self.MIN_SCORE:
                continue

            # =================================================
            # Language Preference
            # =================================================

            language_match = None

            if language:

                language_match = (
                    str(obj.language or "").casefold() == str(language).casefold()
                )

            # =================================================
            # Add Result
            # =================================================

            results.append(
                {
                    "knowledge": obj,
                    # Ranking score including crop bonus.
                    "score": float(final_score),
                    # Raw signal consumed by relevance/hybrid
                    # logic.
                    "fuzzy_raw_score": float(raw_fuzzy_score),
                    "crop_score": float(crop_score),
                    "question_score": float(question_score),
                    "search_score": float(search_score),
                    "crop_bonus": float(crop_bonus),
                    "crop_match": (crop_match),
                    "language_match": (language_match),
                }
            )

        # =====================================================
        # 6. Sort Results
        # =====================================================

        results.sort(
            key=self._sort_key,
            reverse=True,
        )

        final_results = results[:top_k]

        # =====================================================
        # 7. Debug Results
        # =====================================================

        print(
            "Crop Mismatches Removed :",
            crop_mismatches_filtered,
        )

        print(
            "Valid Fuzzy Results      :",
            len(results),
        )

        print("-" * 80)

        if not results:

            print("No valid fuzzy results.")

        for result in results[:10]:

            knowledge = result["knowledge"]

            print(
                f"FINAL={result['score']:.2f} | "
                f"RAW={result['fuzzy_raw_score']:.2f} | "
                f"CROP={result['crop_score']:.2f} | "
                f"QUESTION={result['question_score']:.2f} | "
                f"SEARCH={result['search_score']:.2f}"
            )

            print(
                "Crop       :",
                knowledge.crop,
            )

            print(
                "Crop Match :",
                result.get("crop_match"),
            )

            print(
                "Crop Bonus :",
                result.get("crop_bonus"),
            )

            print(
                "Question   :",
                knowledge.question,
            )

            print("-" * 80)

        print("=" * 80 + "\n")

        # =====================================================
        # 8. Return
        # =====================================================

        return {
            "match_type": ("fuzzy" if final_results else "none"),
            "results": final_results,
            "query_metadata": {
                "normalized_question": (normalized_question),
                "tokens": query_tokens,
                "crop": query_crop,
                "crop_detected": (crop_detected),
                "crop_resolution": (crop_info),
                "crop_mismatches_filtered": (crop_mismatches_filtered),
            },
        }

    # =========================================================
    # Prepare Fuzzy Text
    # =========================================================

    def _prepare_text(
        self,
        text: Any,
    ) -> str:
        """
        Convert text into normalized fuzzy-comparison text.
        """

        if text is None:
            return ""

        processed = self.preprocessor.preprocess(str(text))

        tokens = processed.get(
            "tokens",
            [],
        )

        return " ".join(tokens)

    # =========================================================
    # Crop Resolution
    # =========================================================

    def _resolve_crop(
        self,
        question: str,
        normalized_question: str,
    ) -> Dict[str, Any]:
        """
        Dynamically resolve crop through CropResolver.
        """

        if self.crop_resolver is None:

            return {
                "crop": None,
                "resolved": False,
                "source": "unavailable",
            }

        method_names = [
            "resolve",
            "resolve_crop",
            "extract",
        ]

        for method_name in method_names:

            method = getattr(
                self.crop_resolver,
                method_name,
                None,
            )

            if not callable(method):
                continue

            try:

                result = method(question)

            except TypeError:

                try:

                    result = method(normalized_question)

                except Exception:
                    continue

            except Exception:
                continue

            parsed = self._parse_crop_result(result)

            if parsed.get("crop"):
                return parsed

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

        if query_crop == knowledge_crop:

            return True

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
                    "fuzzy_raw_score",
                    0.0,
                )
            ),
            float(
                result.get(
                    "question_score",
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
        normalized_question="",
        crop_info=None,
        reason="",
    ) -> Dict[str, Any]:

        crop_info = crop_info or {}

        return {
            "match_type": "none",
            "results": [],
            "query_metadata": {
                "normalized_question": (normalized_question),
                "crop": crop_info.get("crop"),
                "crop_detected": bool(crop_info.get("crop")),
                "crop_resolution": (crop_info),
                "reason": reason,
            },
        }
