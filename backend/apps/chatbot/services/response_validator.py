from typing import Any, Dict, List, Optional

from apps.chatbot.services.response_formatter import ResponseFormatter


class ResponseValidator:
    """
    Final public-response validation layer.

    Runs near the end of the Farmer Voice AI pipeline.

    Responsibilities
    ----------------
    1. Validate final answer structure.
    2. Normalize confidence.
    3. Validate and deduplicate sources.
    4. Enforce success/failure consistency.
    5. Preserve multilingual responses.
    6. Remove internal/debug information.
    7. Provide safe language-aware fallbacks.

    IMPORTANT
    ---------
    This service does NOT determine agricultural correctness.

    Agricultural grounding belongs to:
    - RetrieverService
    - RelevanceService
    - EvidenceSelector
    - GenerationService
    - AnswerGuard
    """

    MIN_ANSWER_LENGTH = 2
    MAX_ANSWER_LENGTH = 10000
    MAX_SOURCES = 5

    PUBLIC_FIELDS = {
        "success",
        "answer",
        "confidence",
        "confidence_label",
        "match_type",
        "sources",
        "language",
        "conversation_id",
        "message_id",
        "intent",
        "fallback_used",
        "fallback_source",
    }

    VALID_MATCH_TYPES = {
        "exact",
        "semantic",
        "hybrid",
        "keyword",
        "bm25",
        "fuzzy",
        "fallback",
        "irrelevant",
        "none",
        "greeting",
        "context",
        "error",
    }

    def __init__(self):
        self.formatter = ResponseFormatter()

    # =========================================================
    # Helpers
    # =========================================================

    @staticmethod
    def _clean_text(value: Any) -> str:

        if value is None:
            return ""

        return " ".join(str(value).replace("\x00", " ").strip().split())

    @staticmethod
    def _safe_float(
        value: Any,
        default: float = 0.0,
    ) -> float:

        try:
            return float(value)

        except (TypeError, ValueError):
            return default

    @staticmethod
    def _safe_bool(value: Any) -> bool:

        if isinstance(value, bool):
            return value

        if value is None:
            return False

        if isinstance(value, str):

            return value.strip().lower() in {
                "true",
                "1",
                "yes",
                "y",
            }

        return bool(value)

    @staticmethod
    def _unique(values: List[Any]) -> List[Any]:

        result = []

        for value in values:

            if value not in result:
                result.append(value)

        return result

    # =========================================================
    # Language
    # =========================================================

    def _normalize_language(self, language) -> str:

        return self.formatter._normalize_language(language)

    # =========================================================
    # Confidence
    # =========================================================

    def _normalize_confidence(
        self,
        value: Any,
    ) -> float:
        """
        Public confidence is always 0-100.

        Examples:
            0.84 -> 84.0
            84   -> 84.0
            84.6 -> 84.6
        """

        confidence = self._safe_float(
            value,
            0.0,
        )

        if 0.0 <= confidence <= 1.0:
            confidence *= 100.0

        confidence = max(
            0.0,
            min(
                confidence,
                100.0,
            ),
        )

        return round(
            confidence,
            2,
        )

    @staticmethod
    def _confidence_label(
        confidence: float,
    ) -> str:

        if confidence >= 90:
            return "very_high"

        if confidence >= 80:
            return "high"

        if confidence >= 65:
            return "medium"

        if confidence >= 45:
            return "low"

        return "very_low"

    # =========================================================
    # Answer Validation
    # =========================================================

    def _validate_answer(
        self,
        answer: Any,
    ) -> Dict:

        answer = self._clean_text(answer)

        if not answer:

            return {
                "valid": False,
                "answer": "",
                "reason": "Final answer is empty.",
            }

        if len(answer) < self.MIN_ANSWER_LENGTH:

            return {
                "valid": False,
                "answer": answer,
                "reason": "Final answer is too short.",
            }

        if len(answer) > self.MAX_ANSWER_LENGTH:

            return {
                "valid": False,
                "answer": answer,
                "reason": "Final answer exceeds maximum length.",
            }

        return {
            "valid": True,
            "answer": answer,
            "reason": "Final answer is valid.",
        }

    # =========================================================
    # Source Validation
    # =========================================================

    def _validate_source(
        self,
        source: Any,
    ) -> Optional[Dict]:

        if not isinstance(source, dict):
            return None

        name = self._clean_text(
            source.get(
                "name",
                source.get(
                    "display_name",
                    "",
                ),
            )
        )

        citation = self._clean_text(
            source.get(
                "citation",
                "",
            )
        )

        source_type = self._clean_text(
            source.get(
                "type",
                source.get(
                    "source_type",
                    "",
                ),
            )
        )

        crop = self._clean_text(
            source.get(
                "crop",
                "",
            )
        )

        category = self._clean_text(
            source.get(
                "category",
                "",
            )
        )

        matched_question = self._clean_text(
            source.get(
                "matched_question",
                "",
            )
        )

        if not name and not citation:
            return None

        if not name:
            name = citation

        if not citation:
            citation = name

        cleaned = {
            "name": name,
            "citation": citation,
        }

        if source_type:
            cleaned["type"] = source_type

        if crop:
            cleaned["crop"] = crop

        if category:
            cleaned["category"] = category

        if matched_question:
            cleaned["matched_question"] = matched_question

        page_number = source.get("page_number")

        if page_number is not None:

            try:
                page_number = int(page_number)

                if page_number > 0:
                    cleaned["page_number"] = page_number

            except (TypeError, ValueError):
                pass

        return cleaned

    @staticmethod
    def _source_identity(
        source: Dict,
    ):

        return (
            source.get(
                "citation",
                "",
            ).lower(),
            source.get(
                "matched_question",
                "",
            ).lower(),
            source.get(
                "page_number",
            ),
        )

    def _validate_sources(
        self,
        sources: Any,
    ) -> List[Dict]:

        if not isinstance(
            sources,
            (list, tuple),
        ):
            return []

        cleaned_sources = []
        seen = set()

        for source in sources:

            cleaned = self._validate_source(source)

            if not cleaned:
                continue

            identity = self._source_identity(cleaned)

            if identity in seen:
                continue

            seen.add(identity)

            cleaned_sources.append(cleaned)

            if len(cleaned_sources) >= self.MAX_SOURCES:
                break

        return cleaned_sources

    # =========================================================
    # Match Type
    # =========================================================

    def _normalize_match_type(
        self,
        value: Any,
        success: bool,
    ) -> str:

        value = self._clean_text(value).lower()

        if value in self.VALID_MATCH_TYPES:
            return value

        if success:
            return "hybrid"

        return "irrelevant"

    # =========================================================
    # Main Validation
    # =========================================================

    def validate(
        self,
        response: Optional[Dict],
    ) -> Dict:

        errors = []
        warnings = []

        if not isinstance(response, dict):

            failure = self.build_failure()

            return {
                "is_valid": False,
                "response": failure,
                "errors": ["Response must be a dictionary."],
                "warnings": [],
            }

        # =====================================================
        # Language First
        # =====================================================

        language = self._normalize_language(response.get("language"))

        # =====================================================
        # Basic State
        # =====================================================

        success = self._safe_bool(
            response.get(
                "success",
                False,
            )
        )

        answer_result = self._validate_answer(response.get("answer"))

        answer = answer_result["answer"]

        confidence = self._normalize_confidence(
            response.get(
                "confidence",
                0,
            )
        )

        sources = self._validate_sources(
            response.get(
                "sources",
                [],
            )
        )

        fallback_used = self._safe_bool(
            response.get(
                "fallback_used",
                False,
            )
        )

        fallback_source = self._clean_text(
            response.get(
                "fallback_source",
                "",
            )
        )

        match_type = self._normalize_match_type(
            response.get("match_type"),
            success=success,
        )

        # =====================================================
        # Invalid Answer
        # =====================================================

        if not answer_result["valid"]:

            errors.append(answer_result["reason"])

            success = False

            answer = self.formatter.get_fallback_message(language)

            confidence = 0.0
            sources = []
            match_type = "irrelevant"
            fallback_used = True
            fallback_source = "safe_fallback"

        # =====================================================
        # Failure Consistency
        # =====================================================

        if not success:

            confidence = 0.0

            if match_type not in {
                "irrelevant",
                "none",
                "fallback",
                "error",
            }:

                match_type = "irrelevant"

            if match_type in {
                "irrelevant",
                "none",
                "error",
            }:

                sources = []

            if not answer:

                answer = self.formatter.get_fallback_message(language)

                fallback_used = True

                if not fallback_source:
                    fallback_source = "safe_fallback"

        # =====================================================
        # Success Consistency
        # =====================================================

        if success and not sources:

            # Greeting/context responses legitimately have
            # no knowledge citations.

            if match_type not in {
                "greeting",
                "context",
            }:

                warnings.append(
                    "Successful knowledge response has " "no public source metadata."
                )

        if (
            success
            and confidence <= 0
            and match_type
            not in {
                "greeting",
                "context",
            }
        ):

            warnings.append("Successful knowledge response has " "zero confidence.")

        # =====================================================
        # Confidence Label
        # =====================================================

        confidence_label = self._confidence_label(confidence)

        # =====================================================
        # Normalized Public Response
        # =====================================================

        normalized = {
            "success": success,
            "answer": answer,
            "confidence": confidence,
            "confidence_label": confidence_label,
            "match_type": match_type,
            "sources": sources,
            "language": language,
            "fallback_used": fallback_used,
            "fallback_source": (fallback_source or None),
        }

        # =====================================================
        # Optional Public Metadata
        # =====================================================

        for field in (
            "conversation_id",
            "message_id",
            "intent",
        ):

            value = response.get(field)

            if value is None:
                continue

            value = self._clean_text(value)

            if value:
                normalized[field] = value

        # =====================================================
        # Final Validation State
        # =====================================================

        return {
            "is_valid": len(errors) == 0,
            "response": normalized,
            "errors": self._unique(errors),
            "warnings": self._unique(warnings),
        }

    # =========================================================
    # Public Sanitizer
    # =========================================================

    def sanitize(
        self,
        response: Optional[Dict],
    ) -> Dict:

        return self.validate(response)["response"]

    # =========================================================
    # Failure Builder
    # =========================================================

    def build_failure(
        self,
        answer: Optional[str] = None,
        language: Optional[str] = None,
        conversation_id: Optional[Any] = None,
        intent: Optional[str] = None,
        match_type: str = "irrelevant",
        fallback_source: str = "safe_fallback",
    ) -> Dict:

        language = self._normalize_language(language)

        answer = self._clean_text(answer)

        if not answer:

            answer = self.formatter.get_fallback_message(language)

        response = {
            "success": False,
            "answer": answer,
            "confidence": 0.0,
            "confidence_label": "very_low",
            "match_type": self._normalize_match_type(
                match_type,
                success=False,
            ),
            "sources": [],
            "language": language,
            "fallback_used": True,
            "fallback_source": fallback_source,
        }

        if conversation_id is not None:

            response["conversation_id"] = str(conversation_id)

        if intent:

            response["intent"] = self._clean_text(intent)

        return response

    # =========================================================
    # Success Builder
    # =========================================================

    def build_success(
        self,
        answer: str,
        confidence: Any,
        sources: Optional[List[Dict]] = None,
        language: Optional[str] = None,
        conversation_id: Optional[Any] = None,
        intent: Optional[str] = None,
        match_type: str = "hybrid",
        fallback_used: bool = False,
        fallback_source: Optional[str] = None,
    ) -> Dict:

        response = {
            "success": True,
            "answer": answer,
            "confidence": confidence,
            "match_type": match_type,
            "sources": sources or [],
            "language": self._normalize_language(language),
            "fallback_used": fallback_used,
            "fallback_source": fallback_source,
        }

        if conversation_id is not None:

            response["conversation_id"] = str(conversation_id)

        if intent:

            response["intent"] = intent

        return self.sanitize(response)

    # =========================================================
    # Internal Field Removal
    # =========================================================

    def remove_internal_fields(
        self,
        response: Dict,
    ) -> Dict:

        if not isinstance(
            response,
            dict,
        ):
            return {}

        return {
            key: value for key, value in response.items() if key in self.PUBLIC_FIELDS
        }

    # =========================================================
    # Debug
    # =========================================================

    def debug(
        self,
        response: Dict,
    ) -> Dict:

        result = self.validate(response)

        print("\n" + "=" * 80)
        print("RESPONSE VALIDATOR")
        print("=" * 80)

        print(
            "Valid    :",
            result["is_valid"],
        )

        print(
            "Errors   :",
            result["errors"],
        )

        print(
            "Warnings :",
            result["warnings"],
        )

        print("-" * 80)

        print(
            "Response :",
            result["response"],
        )

        print("=" * 80 + "\n")

        return result
