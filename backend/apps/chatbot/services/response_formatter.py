from typing import Any, Dict, List, Optional


class ResponseFormatter:
    """
    Central response formatter for Farmer Voice AI.

    Responsibilities
    ----------------
    - Produce a consistent public API response structure.
    - Normalize answer, confidence and sources.
    - Provide multilingual safe fallback responses.
    - Keep responses JSON-safe.
    - Prevent internal implementation details from leaking.

    Supported languages
    -------------------
    hi       Hindi
    en       English
    hinglish Roman Hindi / Hinglish
    gu       Gujarati
    mr       Marathi
    pa       Punjabi
    ta       Tamil
    te       Telugu
    """

    # =========================================================
    # Supported Languages
    # =========================================================

    SUPPORTED_LANGUAGES = {
        "hi",
        "en",
        "hinglish",
        "gu",
        "mr",
        "pa",
        "ta",
        "te",
    }

    LANGUAGE_ALIASES = {
        "hindi": "hi",
        "english": "en",
        "hinglish": "hinglish",
        "roman hindi": "hinglish",
        "roman_hindi": "hinglish",
        "gujarati": "gu",
        "marathi": "mr",
        "punjabi": "pa",
        "gurmukhi": "pa",
        "tamil": "ta",
        "telugu": "te",
    }

    # =========================================================
    # Safe Farmer-Facing Fallback Messages
    # =========================================================

    FALLBACK_MESSAGES = {
        "hi": (
            "मुझे उपलब्ध कृषि ज्ञान में इसका विश्वसनीय उत्तर नहीं मिला। "
            "कृपया कृषि विशेषज्ञ या कृषि विज्ञान केंद्र (KVK) से संपर्क करें।"
        ),
        "en": (
            "I could not find a reliable answer in the available "
            "agricultural knowledge. Please contact an agriculture "
            "expert or Krishi Vigyan Kendra (KVK)."
        ),
        "hinglish": (
            "Mujhe available krishi knowledge mein iska reliable answer "
            "nahi mila. Kripya agriculture expert ya Krishi Vigyan "
            "Kendra (KVK) se sampark karein."
        ),
        "gu": (
            "ઉપલબ્ધ કૃષિ જ્ઞાનમાં મને આ પ્રશ્નનો વિશ્વસનીય જવાબ મળ્યો નથી. "
            "કૃપા કરીને કૃષિ નિષ્ણાત અથવા કૃષિ વિજ્ઞાન કેન્દ્ર (KVK) નો સંપર્ક કરો."
        ),
        "mr": (
            "उपलब्ध कृषी ज्ञानामध्ये मला या प्रश्नाचे विश्वसनीय उत्तर मिळाले नाही. "
            "कृपया कृषी तज्ज्ञ किंवा कृषी विज्ञान केंद्र (KVK) यांच्याशी संपर्क साधा."
        ),
        "pa": (
            "ਉਪਲਬਧ ਖੇਤੀਬਾੜੀ ਜਾਣਕਾਰੀ ਵਿੱਚ ਮੈਨੂੰ ਇਸ ਸਵਾਲ ਦਾ ਭਰੋਸੇਯੋਗ ਜਵਾਬ ਨਹੀਂ ਮਿਲਿਆ। "
            "ਕਿਰਪਾ ਕਰਕੇ ਖੇਤੀਬਾੜੀ ਮਾਹਿਰ ਜਾਂ ਕ੍ਰਿਸ਼ੀ ਵਿਗਿਆਨ ਕੇਂਦਰ (KVK) ਨਾਲ ਸੰਪਰਕ ਕਰੋ।"
        ),
        "ta": (
            "கிடைக்கக்கூடிய வேளாண் அறிவில் இந்த கேள்விக்கான நம்பகமான பதில் "
            "எனக்கு கிடைக்கவில்லை. தயவுசெய்து வேளாண் நிபுணர் அல்லது "
            "கிருஷி விஞ்ஞான கேந்திரா (KVK)வை தொடர்பு கொள்ளவும்."
        ),
        "te": (
            "అందుబాటులో ఉన్న వ్యవసాయ జ్ఞానంలో ఈ ప్రశ్నకు నమ్మదగిన సమాధానం "
            "నాకు లభించలేదు. దయచేసి వ్యవసాయ నిపుణుడు లేదా కృషి విజ్ఞాన "
            "కేంద్రం (KVK)ను సంప్రదించండి."
        ),
    }

    # Backward compatibility

    DEFAULT_FALLBACK_HI = FALLBACK_MESSAGES["hi"]
    DEFAULT_FALLBACK_EN = FALLBACK_MESSAGES["en"]

    # =========================================================
    # Success Response
    # =========================================================

    def format_success(
        self,
        answer: str,
        confidence: Any = 0,
        sources: Optional[List[Dict[str, Any]]] = None,
        conversation_id: Any = None,
        language: Optional[str] = None,
        match_type: Optional[str] = None,
        fallback_used: bool = False,
        fallback_source: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:

        language = self._normalize_language(language)

        clean_answer = self._clean_text(answer)

        if not clean_answer:
            clean_answer = self.get_fallback_message(language)

        response = {
            "success": True,
            "answer": clean_answer,
            "confidence": self._normalize_confidence(confidence),
            "sources": self._normalize_sources(sources),
            "conversation_id": self._normalize_id(conversation_id),
            "language": language,
            "match_type": self._clean_optional_text(match_type),
            "fallback_used": bool(fallback_used),
            "fallback_source": self._clean_optional_text(fallback_source),
        }

        if metadata:
            response["metadata"] = self._make_json_safe(metadata)

        return response

    # =========================================================
    # No Reliable Knowledge
    # =========================================================

    def format_no_answer(
        self,
        conversation_id: Any = None,
        language: Optional[str] = None,
        match_type: str = "irrelevant",
        reason: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:

        language = self._normalize_language(language)

        response = {
            "success": False,
            "answer": self.get_fallback_message(language),
            "confidence": 0.0,
            "sources": [],
            "conversation_id": self._normalize_id(conversation_id),
            "language": language,
            "match_type": (self._clean_optional_text(match_type) or "irrelevant"),
            "fallback_used": True,
            "fallback_source": "safe_fallback",
        }

        if reason:
            response["reason"] = self._clean_text(reason)

        if metadata:
            response["metadata"] = self._make_json_safe(metadata)

        return response

    # =========================================================
    # Controlled Error Response
    # =========================================================

    def format_error(
        self,
        message: Optional[str] = None,
        conversation_id: Any = None,
        language: Optional[str] = None,
        error_code: Optional[str] = None,
    ) -> Dict[str, Any]:

        language = self._normalize_language(language)

        public_message = self._clean_text(message)

        if not public_message:
            public_message = self.get_fallback_message(language)

        return {
            "success": False,
            "answer": public_message,
            "confidence": 0.0,
            "sources": [],
            "conversation_id": self._normalize_id(conversation_id),
            "language": language,
            "match_type": "error",
            "fallback_used": True,
            "fallback_source": "error",
            "error_code": self._clean_optional_text(error_code),
        }

    # =========================================================
    # Generic Formatter
    # =========================================================

    def format(
        self,
        *,
        success: bool,
        answer: str,
        confidence: Any = 0,
        sources=None,
        conversation_id=None,
        language=None,
        match_type=None,
        fallback_used=False,
        fallback_source=None,
        metadata=None,
    ) -> Dict[str, Any]:

        language = self._normalize_language(language)

        clean_answer = self._clean_text(answer)

        if not clean_answer:
            clean_answer = self.get_fallback_message(language)

        response = {
            "success": bool(success),
            "answer": clean_answer,
            "confidence": self._normalize_confidence(confidence),
            "sources": self._normalize_sources(sources),
            "conversation_id": self._normalize_id(conversation_id),
            "language": language,
            "match_type": self._clean_optional_text(match_type),
            "fallback_used": bool(fallback_used),
            "fallback_source": self._clean_optional_text(fallback_source),
        }

        if metadata:
            response["metadata"] = self._make_json_safe(metadata)

        return response

    # =========================================================
    # Multilingual Fallback
    # =========================================================

    def get_fallback_message(
        self,
        language: Optional[str] = None,
    ) -> str:

        language = self._normalize_language(language)

        return self.FALLBACK_MESSAGES.get(
            language,
            self.FALLBACK_MESSAGES["hi"],
        )

    # =========================================================
    # Confidence Normalization
    # =========================================================

    @staticmethod
    def _normalize_confidence(
        value: Any,
    ) -> float:

        try:
            confidence = float(value)

        except (TypeError, ValueError):
            return 0.0

        # Accept both:
        # 0.87 -> 87
        # 87   -> 87

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

    # =========================================================
    # Source Normalization
    # =========================================================

    def _normalize_sources(
        self,
        sources,
    ) -> List[Dict[str, Any]]:

        if not sources:
            return []

        if not isinstance(
            sources,
            (list, tuple),
        ):
            sources = [sources]

        normalized = []

        for source in sources:

            if source is None:
                continue

            # -------------------------------------------------
            # Dictionary Source
            # -------------------------------------------------

            if isinstance(source, dict):

                clean_source = {}

                for key, value in source.items():

                    if value is None:
                        continue

                    clean_source[str(key)] = self._make_json_safe(value)

                if clean_source:
                    normalized.append(clean_source)

                continue

            # -------------------------------------------------
            # Legacy String Source
            # -------------------------------------------------

            text = self._clean_text(source)

            if text:

                normalized.append(
                    {
                        "name": text,
                    }
                )

        return normalized

    # =========================================================
    # JSON Safety
    # =========================================================

    def _make_json_safe(
        self,
        value,
    ):

        if value is None:
            return None

        if isinstance(
            value,
            (
                str,
                int,
                float,
                bool,
            ),
        ):
            return value

        if isinstance(
            value,
            dict,
        ):

            return {str(key): self._make_json_safe(item) for key, item in value.items()}

        if isinstance(
            value,
            (
                list,
                tuple,
                set,
            ),
        ):

            return [self._make_json_safe(item) for item in value]

        # UUID / Decimal / datetime / Django values

        return str(value)

    # =========================================================
    # Text Helpers
    # =========================================================

    @staticmethod
    def _clean_text(
        value,
    ) -> str:

        if value is None:
            return ""

        return " ".join(
            str(value)
            .replace(
                "\x00",
                " ",
            )
            .strip()
            .split()
        )

    def _clean_optional_text(
        self,
        value,
    ):

        text = self._clean_text(value)

        return text or None

    # =========================================================
    # ID Normalization
    # =========================================================

    @staticmethod
    def _normalize_id(
        value,
    ):

        if value is None:
            return None

        return str(value)

    # =========================================================
    # Language Normalization
    # =========================================================

    @classmethod
    def _normalize_language(
        cls,
        language,
    ):

        if not language:
            return "hi"

        language = str(language).strip().lower()

        language = cls.LANGUAGE_ALIASES.get(
            language,
            language,
        )

        # Unknown language should never leak arbitrary values
        # into the public API.

        if language not in cls.SUPPORTED_LANGUAGES:
            return "hi"

        return language
