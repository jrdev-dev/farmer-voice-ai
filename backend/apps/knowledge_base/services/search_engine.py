from typing import Any, Dict, List, Optional

from django.db.models import Q

from apps.knowledge_base.models import Knowledge

from .search_preprocessor import SearchPreprocessor
from .crop_resolver import CropResolver


class KnowledgeSearchEngine:
    """
    Universal lexical search engine for Farmer Voice AI.

    Features
    --------
    1. Normalized exact matching
    2. Dynamic crop-aware retrieval
    3. Keyword candidate retrieval
    4. Weighted lexical ranking
    5. Crop mismatch protection
    6. Category/domain/stage awareness
    7. Priority-aware ranking
    8. Optional language preference
    9. Universal crop support
    10. Detailed retrieval metadata

    IMPORTANT
    ---------
    No fixed crop list is maintained here.

    Crop understanding is delegated to CropResolver, which may
    use the Knowledge database and VocabularyService.

    Therefore future crops can be added through knowledge imports
    without modifying this search engine.
    """

    # =========================================================
    # Ranking Weights
    # =========================================================

    CROP_EXACT_WEIGHT = 15.0

    QUESTION_WEIGHT = 6.0

    CATEGORY_WEIGHT = 5.0

    SUBCATEGORY_WEIGHT = 4.0

    DOMAIN_WEIGHT = 4.0

    STAGE_WEIGHT = 3.0

    KEYWORDS_WEIGHT = 3.0

    ANSWER_WEIGHT = 2.0

    SEARCH_TEXT_WEIGHT = 1.0

    PRIORITY_WEIGHT = 0.25

    LANGUAGE_BONUS = 1.0

    # =========================================================
    # Initialization
    # =========================================================

    def __init__(self):
        self.preprocessor = SearchPreprocessor()

        try:
            self.crop_resolver = CropResolver()

        except Exception:
            # Search should remain usable even if crop resolver
            # configuration temporarily fails.
            self.crop_resolver = None

    # =========================================================
    # Main Search
    # =========================================================

    def search(
        self,
        question: str,
        language: Optional[str] = None,
        top_k: int = 5,
    ) -> Dict[str, Any]:

        try:
            top_k = int(top_k)

        except (TypeError, ValueError):
            top_k = 5

        top_k = max(
            1,
            min(top_k, 50),
        )

        # =====================================================
        # 1. Preprocess Question
        # =====================================================

        processed = self.preprocessor.preprocess(question)

        normalized_question = processed.get(
            "normalized",
            "",
        )

        words = processed.get(
            "tokens",
            [],
        )

        # =====================================================
        # 2. Resolve Crop Dynamically
        # =====================================================

        crop_info = self._resolve_crop(
            question=question,
            normalized_question=normalized_question,
        )

        query_crop = crop_info.get("crop")

        crop_detected = bool(query_crop)

        # =====================================================
        # 3. Base QuerySet
        # =====================================================

        base_queryset = Knowledge.objects.filter(is_active=True)

        # Language is intentionally treated as a preference
        # later rather than a hard filter.
        #
        # Knowledge may be stored in Hindi while the user asks
        # the same agricultural question in Hinglish/English.

        # =====================================================
        # 4. Exact Match
        # =====================================================

        exact_queryset = base_queryset.filter(normalized_question=normalized_question)

        if crop_detected:

            crop_exact_queryset = self._filter_crop_queryset(
                exact_queryset,
                query_crop,
            )

            if crop_exact_queryset.exists():
                exact_queryset = crop_exact_queryset

            else:
                # If user explicitly refers to a crop and an
                # exact question exists only for another crop,
                # it must not be treated as a valid exact match.
                exact_queryset = exact_queryset.none()

        if exact_queryset.exists():

            knowledge = self._choose_best_exact(
                exact_queryset,
                language=language,
            )

            self._debug_exact(
                normalized_question=normalized_question,
                knowledge=knowledge,
                query_crop=query_crop,
            )

            return {
                "match_type": "exact",
                "results": [
                    {
                        "knowledge": knowledge,
                        "score": 100.0,
                        "keyword_raw_score": 100.0,
                        "matched_terms": ["exact_question"],
                        "crop_match": (
                            self._crop_matches(
                                query_crop,
                                knowledge.crop,
                            )
                            if crop_detected
                            else None
                        ),
                    }
                ],
                "query_metadata": {
                    "normalized_question": normalized_question,
                    "tokens": words,
                    "crop": query_crop,
                    "crop_detected": crop_detected,
                    "crop_resolution": crop_info,
                },
            }

        # =====================================================
        # 5. No Searchable Tokens
        # =====================================================

        if not words:

            return self._empty_response(
                normalized_question=normalized_question,
                words=words,
                crop_info=crop_info,
            )

        # =====================================================
        # 6. Candidate Retrieval
        # =====================================================

        lexical_query = Q()

        for word in words:

            lexical_query |= Q(search_text__icontains=word)

            lexical_query |= Q(normalized_question__icontains=word)

            lexical_query |= Q(question__icontains=word)

            lexical_query |= Q(keywords__icontains=word)

            lexical_query |= Q(category__icontains=word)

            lexical_query |= Q(subcategory__icontains=word)

            lexical_query |= Q(domain__icontains=word)

            lexical_query |= Q(stage__icontains=word)

        candidates = base_queryset.filter(lexical_query).distinct()

        # =====================================================
        # 7. Crop Safety Filter
        # =====================================================
        #
        # This is the critical cross-crop protection.
        #
        # Example:
        #
        # Query:
        #     गेहूं में कौन सी खाद डालूं?
        #
        # If query crop resolves to Wheat, Soybean-specific
        # records must not become lexical answers merely because
        # "fertilizer" / "डालें" matched.
        #
        # Generic records with blank crop remain eligible.
        # =====================================================

        before_crop_filter_count = candidates.count()

        if crop_detected:

            candidates = self._apply_crop_safety_filter(
                candidates,
                query_crop,
            )

        after_crop_filter_count = candidates.count()

        # =====================================================
        # 8. Weighted Ranking
        # =====================================================

        scored_results = []

        for item in candidates:

            ranking = self._score_item(
                item=item,
                words=words,
                query_crop=query_crop,
                language=language,
            )

            if ranking["score"] <= 0:
                continue

            scored_results.append(
                {
                    "knowledge": item,
                    "score": ranking["score"],
                    "keyword_raw_score": ranking["keyword_raw_score"],
                    "matched_terms": ranking["matched_terms"],
                    "crop_match": ranking["crop_match"],
                    "language_match": ranking["language_match"],
                }
            )

        # =====================================================
        # 9. Sort Results
        # =====================================================

        scored_results.sort(
            key=self._sort_key,
            reverse=True,
        )

        final_results = scored_results[:top_k]

        # =====================================================
        # 10. Debug
        # =====================================================

        self._debug_search(
            question=question,
            normalized_question=normalized_question,
            words=words,
            crop_info=crop_info,
            before_crop_filter_count=(before_crop_filter_count),
            after_crop_filter_count=(after_crop_filter_count),
            results=scored_results,
        )

        # =====================================================
        # 11. Return
        # =====================================================

        return {
            "match_type": ("keyword" if final_results else "none"),
            "results": final_results,
            "query_metadata": {
                "normalized_question": (normalized_question),
                "tokens": words,
                "crop": query_crop,
                "crop_detected": (crop_detected),
                "crop_resolution": crop_info,
                "candidate_count_before_crop_filter": (before_crop_filter_count),
                "candidate_count_after_crop_filter": (after_crop_filter_count),
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
        Resolve crop without assuming one specific CropResolver
        return format.

        This keeps the search engine tolerant while the new
        services are being integrated.
        """

        if self.crop_resolver is None:

            return {
                "crop": None,
                "resolved": False,
                "source": "unavailable",
            }

        resolver_methods = [
            "resolve",
            "resolve_crop",
            "extract",
        ]

        for method_name in resolver_methods:

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
    # Parse Crop Resolver Result
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

        if isinstance(result, str):

            crop = result.strip()

            return {
                "crop": crop or None,
                "resolved": bool(crop),
                "raw": result,
            }

        if isinstance(result, dict):

            possible_keys = [
                "crop",
                "resolved_crop",
                "canonical_crop",
                "name",
            ]

            crop = None

            for key in possible_keys:

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

            values = [str(value).strip() for value in result if value]

            if values:

                return {
                    "crop": values[0],
                    "crops": values,
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

        # Alias-aware normalizer may produce equivalent values.
        return query_crop in knowledge_crop or knowledge_crop in query_crop

    # =========================================================
    # Crop QuerySet Filter
    # =========================================================

    def _filter_crop_queryset(
        self,
        queryset,
        query_crop,
    ):

        if not query_crop:
            return queryset

        normalized_crop = self._normalize_crop(query_crop)

        crop_query = Q(crop__iexact=query_crop)

        if normalized_crop and normalized_crop != str(query_crop).casefold():
            crop_query |= Q(crop__iexact=normalized_crop)

        return queryset.filter(crop_query)

    # =========================================================
    # Crop Safety Filter
    # =========================================================

    def _apply_crop_safety_filter(
        self,
        queryset,
        query_crop,
    ):
        """
        Keep:

        1. Records matching the resolved crop.
        2. Crop-independent records where crop is blank.

        Reject:
        Crop-specific records belonging to other crops.
        """

        if not query_crop:
            return queryset

        normalized_crop = self._normalize_crop(query_crop)

        crop_query = Q(crop__iexact=query_crop) | Q(crop__isnull=True) | Q(crop="")

        if normalized_crop and normalized_crop != str(query_crop).casefold():
            crop_query |= Q(crop__iexact=normalized_crop)

        return queryset.filter(crop_query).distinct()

    # =========================================================
    # Score One Knowledge Item
    # =========================================================

    def _score_item(
        self,
        item,
        words: List[str],
        query_crop: Optional[str],
        language: Optional[str],
    ) -> Dict[str, Any]:

        score = 0.0

        lexical_score = 0.0

        matched_terms = []

        question_text = self._normalize_field(item.question)

        answer_text = self._normalize_field(item.answer)

        search_text = self._normalize_field(item.search_text)

        category_text = self._normalize_field(item.category)

        subcategory_text = self._normalize_field(item.subcategory)

        domain_text = self._normalize_field(item.domain)

        stage_text = self._normalize_field(item.stage)

        keywords_text = self._normalize_field(item.keywords)

        crop_match = None

        # -----------------------------------------------------
        # Crop score
        # -----------------------------------------------------

        if query_crop:

            crop_match = self._crop_matches(
                query_crop,
                item.crop,
            )

            if crop_match:

                score += self.CROP_EXACT_WEIGHT

                lexical_score += self.CROP_EXACT_WEIGHT

                matched_terms.append(
                    (f"{query_crop}" f"(crop:+{self.CROP_EXACT_WEIGHT:g})")
                )

        # -----------------------------------------------------
        # Lexical score
        # -----------------------------------------------------

        for word in words:

            normalized_word = self._normalize_field(word)

            if not normalized_word:
                continue

            if normalized_word in question_text:

                score += self.QUESTION_WEIGHT

                lexical_score += self.QUESTION_WEIGHT

                matched_terms.append(
                    (f"{word}" f"(question:+{self.QUESTION_WEIGHT:g})")
                )

            if normalized_word in category_text:

                score += self.CATEGORY_WEIGHT

                lexical_score += self.CATEGORY_WEIGHT

                matched_terms.append(
                    (f"{word}" f"(category:+{self.CATEGORY_WEIGHT:g})")
                )

            if normalized_word in subcategory_text:

                score += self.SUBCATEGORY_WEIGHT

                lexical_score += self.SUBCATEGORY_WEIGHT

                matched_terms.append(
                    (f"{word}" f"(subcategory:+{self.SUBCATEGORY_WEIGHT:g})")
                )

            if normalized_word in domain_text:

                score += self.DOMAIN_WEIGHT

                lexical_score += self.DOMAIN_WEIGHT

                matched_terms.append((f"{word}" f"(domain:+{self.DOMAIN_WEIGHT:g})"))

            if normalized_word in stage_text:

                score += self.STAGE_WEIGHT

                lexical_score += self.STAGE_WEIGHT

                matched_terms.append((f"{word}" f"(stage:+{self.STAGE_WEIGHT:g})"))

            if normalized_word in keywords_text:

                score += self.KEYWORDS_WEIGHT

                lexical_score += self.KEYWORDS_WEIGHT

                matched_terms.append(
                    (f"{word}" f"(keywords:+{self.KEYWORDS_WEIGHT:g})")
                )

            if normalized_word in answer_text:

                score += self.ANSWER_WEIGHT

                lexical_score += self.ANSWER_WEIGHT

                matched_terms.append((f"{word}" f"(answer:+{self.ANSWER_WEIGHT:g})"))

            if normalized_word in search_text:

                score += self.SEARCH_TEXT_WEIGHT

                lexical_score += self.SEARCH_TEXT_WEIGHT

                matched_terms.append(
                    (f"{word}" f"(search:+{self.SEARCH_TEXT_WEIGHT:g})")
                )

        # -----------------------------------------------------
        # Knowledge priority
        # -----------------------------------------------------

        try:
            priority = int(item.priority or 0)

        except (
            TypeError,
            ValueError,
        ):
            priority = 0

        if priority > 0:

            priority_bonus = priority * self.PRIORITY_WEIGHT

            score += priority_bonus

        # -----------------------------------------------------
        # Language preference
        # -----------------------------------------------------

        language_match = None

        if language:

            language_match = (
                str(item.language or "").casefold() == str(language).casefold()
            )

            if language_match:
                score += self.LANGUAGE_BONUS

        return {
            "score": round(
                score,
                4,
            ),
            # RelevanceService expects an absolute keyword
            # retrieval signal. Do not include tiny metadata
            # bonuses such as priority/language in this value.
            "keyword_raw_score": round(
                lexical_score,
                4,
            ),
            "matched_terms": (matched_terms),
            "crop_match": (crop_match),
            "language_match": (language_match),
        }

    # =========================================================
    # Normalize Knowledge Field
    # =========================================================

    def _normalize_field(
        self,
        value: Any,
    ) -> str:

        if value is None:
            return ""

        value = str(value).strip()

        if not value:
            return ""

        try:
            return self.preprocessor.normalizer.normalize(value).casefold()

        except Exception:
            return value.casefold()

    # =========================================================
    # Exact Match Selection
    # =========================================================

    def _choose_best_exact(
        self,
        queryset,
        language=None,
    ):

        items = list(queryset)

        if not items:
            return None

        if language:

            language_matches = [
                item
                for item in items
                if str(item.language or "").casefold() == str(language).casefold()
            ]

            if language_matches:
                items = language_matches

        items.sort(
            key=lambda item: (
                int(item.priority or 0),
                -int(item.id or 0),
            ),
            reverse=True,
        )

        return items[0]

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
                    "keyword_raw_score",
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
    # Empty Response
    # =========================================================

    def _empty_response(
        self,
        normalized_question,
        words,
        crop_info,
    ):

        return {
            "match_type": "none",
            "results": [],
            "query_metadata": {
                "normalized_question": (normalized_question),
                "tokens": words,
                "crop": crop_info.get("crop"),
                "crop_detected": bool(crop_info.get("crop")),
                "crop_resolution": (crop_info),
            },
        }

    # =========================================================
    # Exact Debug
    # =========================================================

    @staticmethod
    def _debug_exact(
        normalized_question,
        knowledge,
        query_crop,
    ):

        print("\n" + "=" * 80)

        print("EXACT MATCH FOUND")

        print("=" * 80)

        print(
            "Question   :",
            normalized_question,
        )

        print(
            "Query Crop :",
            query_crop,
        )

        print(
            "Matched    :",
            knowledge.question,
        )

        print(
            "Crop       :",
            knowledge.crop,
        )

        print("=" * 80 + "\n")

    # =========================================================
    # Search Debug
    # =========================================================

    @staticmethod
    def _debug_search(
        question,
        normalized_question,
        words,
        crop_info,
        before_crop_filter_count,
        after_crop_filter_count,
        results,
    ):

        print("\n" + "=" * 80)

        print("UNIVERSAL KEYWORD SEARCH")

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
            "Tokens              :",
            words,
        )

        print(
            "Resolved Crop       :",
            crop_info.get("crop"),
        )

        print(
            "Crop Resolution     :",
            crop_info,
        )

        print("-" * 80)

        print(
            "Candidates Before Crop Filter :",
            before_crop_filter_count,
        )

        print(
            "Candidates After Crop Filter  :",
            after_crop_filter_count,
        )

        print("-" * 80)

        print("TOP KEYWORD RESULTS")

        print("-" * 80)

        if not results:

            print("No valid keyword results.")

        for result in results[:10]:

            item = result["knowledge"]

            print(
                "Score       :",
                result.get("score"),
            )

            print(
                "Keyword Raw :",
                result.get("keyword_raw_score"),
            )

            print(
                "Crop        :",
                item.crop,
            )

            print(
                "Crop Match  :",
                result.get("crop_match"),
            )

            print(
                "Question    :",
                item.question,
            )

            print(
                "Matched     :",
                ", ".join(
                    result.get(
                        "matched_terms",
                        [],
                    )
                ),
            )

            print("-" * 80)

        print("=" * 80 + "\n")
