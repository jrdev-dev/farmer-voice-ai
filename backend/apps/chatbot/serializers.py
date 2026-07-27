from rest_framework import serializers


class ChatRequestSerializer(serializers.Serializer):
    """
    Validates Farmer Voice AI chat requests.

    Language is optional.

    If language is not supplied, ChatService automatically
    detects it from the farmer's message.
    """

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

    message = serializers.CharField(
        required=True,
        allow_blank=False,
        trim_whitespace=True,
        max_length=5000,
    )

    language = serializers.CharField(
        required=False,
        allow_blank=False,
        allow_null=True,
        max_length=20,
    )

    # =========================================================
    # Message Validation
    # =========================================================

    def validate_message(self, value):

        value = self._clean_text(value)

        if not value:
            raise serializers.ValidationError("Message cannot be empty.")

        return value

    # =========================================================
    # Language Validation
    # =========================================================

    def validate_language(self, value):
        """
        Normalize explicitly supplied language.

        Examples
        --------
        Hindi    -> hi
        English  -> en
        Gujarati -> gu

        If language is omitted entirely, this validator is not
        called and ChatService receives None.
        """

        if value is None:
            return None

        language = self._clean_text(value).lower()

        if not language:
            return None

        language = self.LANGUAGE_ALIASES.get(
            language,
            language,
        )

        if language not in self.SUPPORTED_LANGUAGES:
            raise serializers.ValidationError(
                (
                    "Unsupported language. Supported language "
                    "codes are: hi, en, hinglish, gu, mr, pa, "
                    "ta, te."
                )
            )

        return language

    # =========================================================
    # Helpers
    # =========================================================

    @staticmethod
    def _clean_text(value):

        if value is None:
            return ""

        value = str(value).replace(
            "\x00",
            " ",
        )

        return " ".join(value.strip().split())
