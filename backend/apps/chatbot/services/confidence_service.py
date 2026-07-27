from typing import Any, Dict, List, Optional


class ConfidenceService:
    """
    Calculates final confidence for Farmer Voice AI responses.

    Confidence is based on retrieval evidence rather than
    arbitrary LLM confidence.

    Main signals:
    - Semantic similarity
    - BM25 score
    - Keyword score
    - Fuzzy score
    - Multi-retriever agreement
    - Relevance guard result
    - Answer validation result
    - Trusted fallback usage
    - Number of supporting documents

    Important:
    Confidence represents how strongly the system's retrieved
    evidence supports the answer.

    It does NOT represent scientific certainty.
    """

    # =========================================================
    # Weights
    # =========================================================

    SEMANTIC_WEIGHT = 0.40
    BM25_WEIGHT = 0.20
    KEYWORD_WEIGHT = 0.15
    FUZZY_WEIGHT = 0.15
    AGREEMENT_WEIGHT = 0.10

    # =========================================================
    # Raw score normalization limits
    # =========================================================

    # Semantic scores are normally 0-1.
    SEMANTIC_MAX = 1.0

    # BM25 and keyword scores do not naturally have a fixed
    # maximum. These values represent strong evidence levels,
    # after which the normalized contribution is capped at 1.
    BM25_STRONG_SCORE = 5.0
    KEYWORD_STRONG_SCORE = 10.0

    # Fuzzy score is normally 0-100.
    FUZZY_MAX = 100.0

    # =========================================================
    # Confidence penalties
    # =========================================================

    INVALID_ANSWER_MULTIPLIER = 0.0

    IRRELEVANT_MULTIPLIER = 0.0

    FALLBACK_MULTIPLIER = 0.85

    SINGLE_DOCUMENT_MULTIPLIER = 0.95

    # =========================================================
    # Confidence labels
    # =========================================================

    VERY_HIGH_THRESHOLD = 0.90
    HIGH_THRESHOLD = 0.80
    MEDIUM_THRESHOLD = 0.65
    LOW_THRESHOLD = 0.45

    # =========================================================
    # Helpers
    # =========================================================

    @staticmethod
    def _safe_float(
        value: Any,
        default: float = 0.0,
    ) -> float:

        try:
            return float(value)

        except (
            TypeError,
            ValueError,
        ):
            return default

    @staticmethod
    def _clamp(
        value: float,
        minimum: float = 0.0,
        maximum: float = 1.0,
    ) -> float:

        return max(
            minimum,
            min(
                value,
                maximum,
            ),
        )

    def _normalize(
        self,
        value: Any,
        maximum: float,
    ) -> float:

        value = self._safe_float(value)

        if maximum <= 0:
            return 0.0

        return self._clamp(value / maximum)

    # =========================================================
    # Extract raw retrieval scores
    # =========================================================

    def _extract_scores(
        self,
        result: Optional[Dict],
    ) -> Dict[str, float]:

        result = result or {}

        # Support both current raw-score keys and nested score
        # dictionaries so this service remains reusable.
        nested_scores = result.get(
            "scores",
            {},
        )

        if not isinstance(
            nested_scores,
            dict,
        ):
            nested_scores = {}

        semantic = self._safe_float(
            result.get(
                "semantic_raw_score",
                nested_scores.get(
                    "semantic_raw",
                    0.0,
                ),
            )
        )

        bm25 = self._safe_float(
            result.get(
                "bm25_raw_score",
                nested_scores.get(
                    "bm25_raw",
                    0.0,
                ),
            )
        )

        keyword = self._safe_float(
            result.get(
                "keyword_raw_score",
                nested_scores.get(
                    "keyword_raw",
                    0.0,
                ),
            )
        )

        fuzzy = self._safe_float(
            result.get(
                "fuzzy_raw_score",
                nested_scores.get(
                    "fuzzy_raw",
                    0.0,
                ),
            )
        )

        return {
            "semantic_raw": semantic,
            "bm25_raw": bm25,
            "keyword_raw": keyword,
            "fuzzy_raw": fuzzy,
        }

    # =========================================================
    # Retriever agreement
    # =========================================================

    def _agreement_score(
        self,
        scores: Dict[str, float],
    ) -> Dict:

        signals = []

        # These are evidence-presence thresholds, not final
        # relevance thresholds.
        if scores["semantic_raw"] >= 0.60:
            signals.append("semantic")

        if scores["bm25_raw"] >= 1.0:
            signals.append("bm25")

        if scores["keyword_raw"] >= 1.0:
            signals.append("keyword")

        if scores["fuzzy_raw"] >= 60.0:
            signals.append("fuzzy")

        agreement = len(signals) / 4.0

        return {
            "score": self._clamp(agreement),
            "signals": signals,
            "count": len(signals),
        }

    # =========================================================
    # Base confidence
    # =========================================================

    def _base_confidence(
        self,
        scores: Dict[str, float],
    ) -> Dict:

        semantic = self._normalize(
            scores["semantic_raw"],
            self.SEMANTIC_MAX,
        )

        bm25 = self._normalize(
            scores["bm25_raw"],
            self.BM25_STRONG_SCORE,
        )

        keyword = self._normalize(
            scores["keyword_raw"],
            self.KEYWORD_STRONG_SCORE,
        )

        fuzzy = self._normalize(
            scores["fuzzy_raw"],
            self.FUZZY_MAX,
        )

        agreement_result = self._agreement_score(scores)

        agreement = agreement_result["score"]

        confidence = (
            semantic * self.SEMANTIC_WEIGHT
            + bm25 * self.BM25_WEIGHT
            + keyword * self.KEYWORD_WEIGHT
            + fuzzy * self.FUZZY_WEIGHT
            + agreement * self.AGREEMENT_WEIGHT
        )

        return {
            "confidence": self._clamp(confidence),
            "normalized_scores": {
                "semantic": round(
                    semantic,
                    4,
                ),
                "bm25": round(
                    bm25,
                    4,
                ),
                "keyword": round(
                    keyword,
                    4,
                ),
                "fuzzy": round(
                    fuzzy,
                    4,
                ),
                "agreement": round(
                    agreement,
                    4,
                ),
            },
            "agreement": agreement_result,
        }

    # =========================================================
    # Confidence label
    # =========================================================

    def get_label(
        self,
        confidence: float,
    ) -> str:

        confidence = self._clamp(self._safe_float(confidence))

        if confidence >= self.VERY_HIGH_THRESHOLD:
            return "very_high"

        if confidence >= self.HIGH_THRESHOLD:
            return "high"

        if confidence >= self.MEDIUM_THRESHOLD:
            return "medium"

        if confidence >= self.LOW_THRESHOLD:
            return "low"

        return "very_low"

    # =========================================================
    # Percentage
    # =========================================================

    def to_percentage(
        self,
        confidence: float,
    ) -> int:

        confidence = self._clamp(self._safe_float(confidence))

        return int(round(confidence * 100))

    # =========================================================
    # Main evaluation
    # =========================================================

    def evaluate(
        self,
        best_result: Optional[Dict] = None,
        relevance_result: Optional[Dict] = None,
        answer_valid: bool = True,
        fallback_used: bool = False,
        supporting_documents: int = 1,
    ) -> Dict:
        """
        Calculate final confidence.

        Returns:
        {
            "confidence": 0.0-1.0,
            "percentage": 0-100,
            "label": "...",
            "raw_scores": {...},
            "normalized_scores": {...},
            "agreement": {...},
            "adjustments": [...],
        }
        """

        best_result = best_result or {}

        relevance_result = relevance_result or {}

        raw_scores = self._extract_scores(best_result)

        base_result = self._base_confidence(raw_scores)

        confidence = base_result["confidence"]

        adjustments: List[str] = []

        # =====================================================
        # Relevance guard
        # =====================================================

        relevance_known = "is_relevant" in relevance_result

        if relevance_known:

            if not relevance_result.get(
                "is_relevant",
                False,
            ):

                confidence *= self.IRRELEVANT_MULTIPLIER

                adjustments.append("Rejected by relevance guard.")

        # =====================================================
        # Answer Guard
        # =====================================================

        if not answer_valid:

            confidence *= self.INVALID_ANSWER_MULTIPLIER

            adjustments.append("Generated answer failed validation.")

        # =====================================================
        # Trusted fallback
        # =====================================================

        if fallback_used and answer_valid and confidence > 0:

            confidence *= self.FALLBACK_MULTIPLIER

            adjustments.append("Trusted fallback answer used.")

        # =====================================================
        # Supporting documents
        # =====================================================

        try:
            document_count = int(supporting_documents)

        except (
            TypeError,
            ValueError,
        ):
            document_count = 0

        if document_count <= 0:

            confidence = 0.0

            adjustments.append("No supporting documents.")

        elif document_count == 1:

            confidence *= self.SINGLE_DOCUMENT_MULTIPLIER

            adjustments.append("Only one supporting document.")

        elif document_count >= 3:

            # Small bonus only. Retrieval scores remain the
            # dominant source of confidence.
            confidence = min(
                1.0,
                confidence + 0.03,
            )

            adjustments.append("Multiple supporting documents.")

        # =====================================================
        # Final clamp
        # =====================================================

        confidence = self._clamp(confidence)

        percentage = self.to_percentage(confidence)

        label = self.get_label(confidence)

        return {
            "confidence": round(
                confidence,
                4,
            ),
            "percentage": percentage,
            "label": label,
            "raw_scores": {
                key: round(
                    value,
                    4,
                )
                for key, value in raw_scores.items()
            },
            "normalized_scores": (base_result["normalized_scores"]),
            "agreement": (base_result["agreement"]),
            "adjustments": adjustments,
        }

    # =========================================================
    # Convenience method
    # =========================================================

    def calculate(
        self,
        best_result: Optional[Dict] = None,
        relevance_result: Optional[Dict] = None,
        answer_valid: bool = True,
        fallback_used: bool = False,
        supporting_documents: int = 1,
    ) -> float:

        result = self.evaluate(
            best_result=best_result,
            relevance_result=relevance_result,
            answer_valid=answer_valid,
            fallback_used=fallback_used,
            supporting_documents=supporting_documents,
        )

        return result["confidence"]

    # =========================================================
    # Farmer-facing percentage
    # =========================================================

    def calculate_percentage(
        self,
        best_result: Optional[Dict] = None,
        relevance_result: Optional[Dict] = None,
        answer_valid: bool = True,
        fallback_used: bool = False,
        supporting_documents: int = 1,
    ) -> int:

        result = self.evaluate(
            best_result=best_result,
            relevance_result=relevance_result,
            answer_valid=answer_valid,
            fallback_used=fallback_used,
            supporting_documents=supporting_documents,
        )

        return result["percentage"]

    # =========================================================
    # Debug
    # =========================================================

    def debug(
        self,
        best_result: Optional[Dict] = None,
        relevance_result: Optional[Dict] = None,
        answer_valid: bool = True,
        fallback_used: bool = False,
        supporting_documents: int = 1,
    ) -> Dict:

        result = self.evaluate(
            best_result=best_result,
            relevance_result=relevance_result,
            answer_valid=answer_valid,
            fallback_used=fallback_used,
            supporting_documents=supporting_documents,
        )

        print("\n" + "=" * 80)

        print("CONFIDENCE SERVICE")

        print("=" * 80)

        print(
            "Raw Scores        :",
            result["raw_scores"],
        )

        print(
            "Normalized Scores :",
            result["normalized_scores"],
        )

        print(
            "Agreement         :",
            result["agreement"],
        )

        print(
            "Adjustments       :",
            result["adjustments"],
        )

        print(
            "Confidence        :",
            result["confidence"],
        )

        print(
            "Percentage        :",
            result["percentage"],
        )

        print(
            "Label             :",
            result["label"],
        )

        print("=" * 80 + "\n")

        return result
