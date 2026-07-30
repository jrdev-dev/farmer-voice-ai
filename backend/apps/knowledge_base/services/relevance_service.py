import math
from typing import Any, Dict, Optional

from apps.knowledge_base.services.normalizer import (
    QuestionNormalizer,
)
from apps.knowledge_base.services.crop_resolver import (
    CropResolver,
)


class RelevanceService:
    """
    Final retrieval relevance and safety gate.

    Responsibilities
    ----------------
    1. Validate RAW retrieval evidence.
    2. Reject explicit cross-crop retrieval.
    3. Support dynamically resolved crops.
    4. Prevent weak retrieval from reaching the LLM.
    5. Preserve explainable relevance decisions.
    6. Handle malformed retrieval scores safely.

    IMPORTANT
    ---------
    Hybrid score is NOT used as proof of relevance.

    Relevance decisions are based on independent RAW signals:

        keyword_raw_score
        bm25_raw_score
        fuzzy_raw_score
        semantic_raw_score
        question_raw_score

    This prevents normalization, ranking bonuses and crop
    bonuses from accidentally becoming relevance evidence.
    """

    # =========================================================
    # Retrieval Thresholds
    # =========================================================

    MIN_SEMANTIC_SCORE = 0.72
    STRONG_SEMANTIC_SCORE = 0.82

    MIN_BM25_SCORE = 1.0
    STRONG_BM25_SCORE = 2.0

    MIN_KEYWORD_SCORE = 5.0

    MIN_FUZZY_SCORE = 65.0
    STRONG_FUZZY_SCORE = 82.0

    MIN_QUESTION_SCORE = 0.60
    STRONG_QUESTION_SCORE = 0.78

    # Minimum independent retrieval evidence.
    MIN_EVIDENCE_COUNT = 2

    def __init__(self):

        self.normalizer = QuestionNormalizer()

        try:
            self.crop_resolver = CropResolver()

        except Exception as exc:

            print(
                "CROP RESOLVER INITIALIZATION ERROR:",
                str(exc),
            )

            self.crop_resolver = None

    # =========================================================
    # Main Evaluation
    # =========================================================

    def evaluate(
        self,
        best_result: dict,
        question: str = "",
    ) -> Dict[str, Any]:
        """
        Evaluate the best retrieved candidate.

        Returns
        -------
        {
            "is_relevant": bool,
            "reason": str,
            "evidence_count": int,
            "evidence": list,
            "scores": {...},
            "crop_validation": {...}
        }
        """

        if (
            not isinstance(
                best_result,
                dict,
            )
            or not best_result
        ):

            return self._empty_response("No retrieval result.")

        # =====================================================
        # 1. Raw Retrieval Evidence
        # =====================================================

        keyword_raw = self._safe_float(
            best_result.get(
                "keyword_raw_score",
                0.0,
            )
        )

        bm25_raw = self._safe_float(
            best_result.get(
                "bm25_raw_score",
                0.0,
            )
        )

        fuzzy_raw = self._safe_float(
            best_result.get(
                "fuzzy_raw_score",
                0.0,
            )
        )

        semantic_raw = self._safe_float(
            best_result.get(
                "semantic_raw_score",
                0.0,
            )
        )

        question_raw = self._safe_float(
            best_result.get(
                "question_raw_score",
                0.0,
            )
        )

        # Negative retrieval values must never count as
        # positive relevance evidence.

        keyword_raw = max(
            0.0,
            keyword_raw,
        )

        bm25_raw = max(
            0.0,
            bm25_raw,
        )

        fuzzy_raw = max(
            0.0,
            fuzzy_raw,
        )

        semantic_raw = max(
            0.0,
            semantic_raw,
        )

        question_raw = max(
            0.0,
            question_raw,
        )

        # =====================================================
        # 2. Crop Safety
        # =====================================================

        crop_guard = self._check_crop_consistency(
            question=question,
            best_result=best_result,
        )

        if not crop_guard["is_valid"]:

            return self._response(
                is_relevant=False,
                reason=crop_guard["reason"],
                evidence=[],
                keyword_raw=keyword_raw,
                bm25_raw=bm25_raw,
                fuzzy_raw=fuzzy_raw,
                semantic_raw=semantic_raw,
                question_raw=question_raw,
                crop_validation=crop_guard,
            )

        # =====================================================
        # 3. Independent Evidence
        # =====================================================

        evidence = []

        if keyword_raw >= self.MIN_KEYWORD_SCORE:

            evidence.append("keyword")

        if bm25_raw >= self.MIN_BM25_SCORE:

            evidence.append("bm25")

        if fuzzy_raw >= self.MIN_FUZZY_SCORE:

            evidence.append("fuzzy")

        if semantic_raw >= self.MIN_SEMANTIC_SCORE:

            evidence.append("semantic")

        if question_raw >= self.MIN_QUESTION_SCORE:

            evidence.append("question_similarity")

        evidence_count = len(evidence)

        # =====================================================
        # 4. Strong Lexical / Question Match (Universal)
        # =====================================================

        if (
            question_raw >= 0.80
            or fuzzy_raw >= 75.0
            or keyword_raw >= 15.0
            or (keyword_raw >= 8.0 and fuzzy_raw >= 60.0)
        ):

            return self._response(
                is_relevant=True,
                reason="Strong exact or high lexical relevance.",
                evidence=evidence,
                keyword_raw=keyword_raw,
                bm25_raw=bm25_raw,
                fuzzy_raw=fuzzy_raw,
                semantic_raw=semantic_raw,
                question_raw=question_raw,
                crop_validation=crop_guard,
            )

        # =====================================================
        # 5. Strong Semantic + Lexical
        # =====================================================

        if semantic_raw >= self.STRONG_SEMANTIC_SCORE and (
            bm25_raw >= self.MIN_BM25_SCORE or keyword_raw >= self.MIN_KEYWORD_SCORE
        ):

            return self._response(
                is_relevant=True,
                reason=("Strong semantic and lexical relevance."),
                evidence=evidence,
                keyword_raw=keyword_raw,
                bm25_raw=bm25_raw,
                fuzzy_raw=fuzzy_raw,
                semantic_raw=semantic_raw,
                question_raw=question_raw,
                crop_validation=crop_guard,
            )

        # =====================================================
        # 6. Strong BM25 + Semantic
        # =====================================================

        if (
            bm25_raw >= self.STRONG_BM25_SCORE
            and semantic_raw >= self.MIN_SEMANTIC_SCORE
        ):

            return self._response(
                is_relevant=True,
                reason=("Strong BM25 and semantic relevance."),
                evidence=evidence,
                keyword_raw=keyword_raw,
                bm25_raw=bm25_raw,
                fuzzy_raw=fuzzy_raw,
                semantic_raw=semantic_raw,
                question_raw=question_raw,
                crop_validation=crop_guard,
            )

        # =====================================================
        # 7. Strong Question + Semantic
        # =====================================================

        if (
            question_raw >= self.STRONG_QUESTION_SCORE
            and semantic_raw >= self.MIN_SEMANTIC_SCORE
        ):

            return self._response(
                is_relevant=True,
                reason=("Strong question and semantic similarity."),
                evidence=evidence,
                keyword_raw=keyword_raw,
                bm25_raw=bm25_raw,
                fuzzy_raw=fuzzy_raw,
                semantic_raw=semantic_raw,
                question_raw=question_raw,
                crop_validation=crop_guard,
            )

        # =====================================================
        # 8. Strong Fuzzy + Semantic
        # =====================================================

        if (
            fuzzy_raw >= self.STRONG_FUZZY_SCORE
            and semantic_raw >= self.MIN_SEMANTIC_SCORE
        ):

            return self._response(
                is_relevant=True,
                reason=("Strong fuzzy and semantic relevance."),
                evidence=evidence,
                keyword_raw=keyword_raw,
                bm25_raw=bm25_raw,
                fuzzy_raw=fuzzy_raw,
                semantic_raw=semantic_raw,
                question_raw=question_raw,
                crop_validation=crop_guard,
            )

        # =====================================================
        # 9. Multi-Retriever Agreement
        # =====================================================

        if evidence_count >= self.MIN_EVIDENCE_COUNT:

            return self._response(
                is_relevant=True,
                reason=("Multiple independent retrieval methods agree."),
                evidence=evidence,
                keyword_raw=keyword_raw,
                bm25_raw=bm25_raw,
                fuzzy_raw=fuzzy_raw,
                semantic_raw=semantic_raw,
                question_raw=question_raw,
                crop_validation=crop_guard,
            )

        # =====================================================
        # 10. Reject Weak Retrieval
        # =====================================================

        return self._response(
            is_relevant=False,
            reason=("Insufficient independent raw retrieval evidence."),
            evidence=evidence,
            keyword_raw=keyword_raw,
            bm25_raw=bm25_raw,
            fuzzy_raw=fuzzy_raw,
            semantic_raw=semantic_raw,
            question_raw=question_raw,
            crop_validation=crop_guard,
        )

    # =========================================================
    # Crop Consistency Guard
    # =========================================================

    def _check_crop_consistency(
        self,
        question: str,
        best_result: dict,
    ) -> Dict[str, Any]:
        """
        Prevent cross-crop retrieval.

        Crop resolution priority
        ------------------------
        1. RetrieverService query_crop metadata.
        2. RetrieverService crop-resolution metadata.
        3. Dynamic CropResolver.
        4. Legacy alias detection as compatibility fallback.

        No fixed crop list is maintained here.
        """

        knowledge = best_result.get("knowledge")

        if knowledge is None:

            return {
                "is_valid": False,
                "reason": ("Retrieved result has no Knowledge object."),
                "query_crop": None,
                "document_crop": None,
            }

        document_crop = str(
            getattr(
                knowledge,
                "crop",
                "",
            )
            or ""
        ).strip()

        # Crop-neutral/general agricultural knowledge.
        if not document_crop:

            return {
                "is_valid": True,
                "reason": ("Retrieved knowledge is crop-neutral."),
                "query_crop": None,
                "document_crop": None,
            }

        query_crop = self._extract_query_crop(
            question=question,
            best_result=best_result,
        )

        # No crop was explicitly identified.
        #
        # Example:
        # "खाद कितनी डालें?"
        #
        # Conversation memory may provide crop context later
        # in ChatService/ContextBuilder.
        if not query_crop:

            return {
                "is_valid": True,
                "reason": (
                    "No explicit crop could be resolved " "from the current query."
                ),
                "query_crop": None,
                "document_crop": document_crop,
            }

        if self._crop_matches(
            query_crop,
            document_crop,
        ):

            return {
                "is_valid": True,
                "reason": (
                    "Question crop matches retrieved "
                    f"knowledge crop: {document_crop}."
                ),
                "query_crop": query_crop,
                "document_crop": document_crop,
            }

        return {
            "is_valid": False,
            "reason": (
                "Crop mismatch: question refers to "
                f"'{query_crop}', but retrieved knowledge "
                f"belongs to '{document_crop}'."
            ),
            "query_crop": query_crop,
            "document_crop": document_crop,
        }

    # =========================================================
    # Extract Query Crop
    # =========================================================

    def _extract_query_crop(
        self,
        question: str,
        best_result: dict,
    ) -> Optional[str]:
        """
        Determine crop without maintaining a hardcoded crop
        list inside RelevanceService.
        """

        # -----------------------------------------------------
        # 1. RetrieverService already resolved it
        # -----------------------------------------------------

        query_crop = best_result.get("query_crop")

        if query_crop:

            return str(query_crop).strip()

        # -----------------------------------------------------
        # 2. Crop-resolution metadata
        # -----------------------------------------------------

        resolution = best_result.get("query_crop_resolution")

        if isinstance(
            resolution,
            dict,
        ):

            for key in (
                "crop",
                "resolved_crop",
                "canonical_crop",
                "name",
            ):

                value = resolution.get(key)

                if value:

                    return str(value).strip()

        # -----------------------------------------------------
        # 3. Dynamic CropResolver
        # -----------------------------------------------------

        if question and self.crop_resolver is not None:

            crop = self._resolve_crop(question)

            if crop:
                return crop

        # -----------------------------------------------------
        # 4. Legacy Compatibility Fallback
        # -----------------------------------------------------
        #
        # This is NOT the primary universal crop system.
        # It only keeps older Normalizer aliases working.
        # -----------------------------------------------------

        if question:

            crop = self._legacy_crop_detection(question)

            if crop:
                return crop

        return None

    # =========================================================
    # Dynamic Crop Resolver
    # =========================================================

    def _resolve_crop(
        self,
        question: str,
    ) -> Optional[str]:

        if not self.crop_resolver:

            return None

        for method_name in (
            "resolve",
            "resolve_crop",
            "extract",
        ):

            method = getattr(
                self.crop_resolver,
                method_name,
                None,
            )

            if not callable(method):
                continue

            try:

                result = method(question)

            except Exception as exc:

                print(
                    "CROP RESOLUTION ERROR:",
                    str(exc),
                )

                continue

            crop = self._parse_crop_result(result)

            if crop:
                return crop

        return None

    # =========================================================
    # Parse Crop Resolver Output
    # =========================================================

    @staticmethod
    def _parse_crop_result(
        result,
    ) -> Optional[str]:

        if result is None:
            return None

        if isinstance(
            result,
            str,
        ):

            result = result.strip()

            return result or None

        if isinstance(
            result,
            dict,
        ):

            for key in (
                "crop",
                "resolved_crop",
                "canonical_crop",
                "name",
            ):

                value = result.get(key)

                if value:

                    return str(value).strip()

            crops = result.get("crops")

            if (
                isinstance(
                    crops,
                    (list, tuple, set),
                )
                and crops
            ):

                return str(list(crops)[0]).strip()

        if isinstance(
            result,
            (list, tuple, set),
        ):

            for value in result:

                if value:

                    return str(value).strip()

        return None

    # =========================================================
    # Legacy Crop Detection
    # =========================================================

    def _legacy_crop_detection(
        self,
        question: str,
    ) -> Optional[str]:

        crop_aliases = getattr(
            self.normalizer,
            "crop_aliases",
            {},
        )

        if not isinstance(
            crop_aliases,
            dict,
        ):

            return None

        try:

            normalized_question = self.normalizer.normalize(question).casefold()

        except Exception:

            normalized_question = str(question).casefold()

        for canonical_crop in crop_aliases.keys():

            try:

                normalized_crop = (
                    self.normalizer.normalize(str(canonical_crop)).casefold().strip()
                )

            except Exception:

                normalized_crop = str(canonical_crop).casefold().strip()

            if normalized_crop and self._contains_token(
                normalized_question,
                normalized_crop,
            ):

                return str(canonical_crop).strip()

        return None

    # =========================================================
    # Crop Matching
    # =========================================================

    def _crop_matches(
        self,
        query_crop: str,
        document_crop: str,
    ) -> bool:

        query_crop = self._normalize_crop(query_crop)

        document_crop = self._normalize_crop(document_crop)

        if not query_crop or not document_crop:

            return False

        if query_crop == document_crop:

            return True

        # Multi-word/alias normalized forms.
        query_tokens = set(query_crop.split())

        document_tokens = set(document_crop.split())

        if query_tokens and document_tokens and query_tokens == document_tokens:

            return True

        return False

    # =========================================================
    # Normalize Crop
    # =========================================================

    def _normalize_crop(
        self,
        crop: str,
    ) -> str:

        if not crop:
            return ""

        try:

            return self.normalizer.normalize(str(crop)).casefold().strip()

        except Exception:

            return str(crop).casefold().strip()

    # =========================================================
    # Token Matching
    # =========================================================

    @staticmethod
    def _contains_token(
        text: str,
        token: str,
    ) -> bool:

        if not text or not token:
            return False

        text_tokens = text.split()

        token_tokens = token.split()

        if len(token_tokens) == 1:

            return token in set(text_tokens)

        token_length = len(token_tokens)

        for index in range(len(text_tokens) - token_length + 1):

            if text_tokens[index : index + token_length] == token_tokens:

                return True

        return False

    # =========================================================
    # Safe Float
    # =========================================================

    @staticmethod
    def _safe_float(
        value,
        default: float = 0.0,
    ) -> float:

        try:

            value = float(value)

        except (
            TypeError,
            ValueError,
        ):

            return float(default)

        if not math.isfinite(value):

            return float(default)

        return value

    # =========================================================
    # Empty Response
    # =========================================================

    @staticmethod
    def _empty_response(
        reason: str,
    ) -> Dict[str, Any]:

        return {
            "is_relevant": False,
            "reason": reason,
            "evidence_count": 0,
            "evidence": [],
            "scores": {
                "keyword_raw": 0.0,
                "bm25_raw": 0.0,
                "fuzzy_raw": 0.0,
                "semantic_raw": 0.0,
                "question_raw": 0.0,
            },
            "crop_validation": {
                "is_valid": False,
                "reason": reason,
                "query_crop": None,
                "document_crop": None,
            },
        }

    # =========================================================
    # Response Builder
    # =========================================================

    @staticmethod
    def _response(
        is_relevant,
        reason,
        evidence,
        keyword_raw,
        bm25_raw,
        fuzzy_raw,
        semantic_raw,
        question_raw,
        crop_validation,
    ) -> Dict[str, Any]:

        return {
            "is_relevant": bool(is_relevant),
            "reason": str(reason),
            "evidence_count": len(evidence),
            "evidence": list(evidence),
            "scores": {
                "keyword_raw": round(
                    keyword_raw,
                    4,
                ),
                "bm25_raw": round(
                    bm25_raw,
                    4,
                ),
                "fuzzy_raw": round(
                    fuzzy_raw,
                    4,
                ),
                "semantic_raw": round(
                    semantic_raw,
                    4,
                ),
                "question_raw": round(
                    question_raw,
                    4,
                ),
            },
            "crop_validation": (crop_validation),
        }
