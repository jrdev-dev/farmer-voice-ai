import os

from rest_framework import serializers


class VoiceChatSerializer(serializers.Serializer):
    """
    Validate Farmer Voice AI audio requests.

    Supported application languages:
    - Hindi
    - English
    - Hinglish
    - Marathi
    - Gujarati
    - Punjabi
    - Tamil
    - Telugu

    Language is optional. When omitted, the speech/chat
    pipeline performs automatic language detection.
    """

    # =========================================================
    # Supported Languages
    # =========================================================

    LANGUAGE_CHOICES = (
        ("hi", "Hindi"),
        ("en", "English"),
        ("hinglish", "Hinglish"),
        ("mr", "Marathi"),
        ("gu", "Gujarati"),
        ("pa", "Punjabi"),
        ("ta", "Tamil"),
        ("te", "Telugu"),
    )

    # =========================================================
    # Supported Audio Formats
    # =========================================================

    ALLOWED_EXTENSIONS = {
        ".wav",
        ".mp3",
        ".m4a",
        ".ogg",
        ".webm",
        ".mp4",
        ".mpeg",
        ".mpga",
    }

    # 25 MB
    MAX_AUDIO_SIZE = 25 * 1024 * 1024

    # =========================================================
    # Fields
    # =========================================================

    audio = serializers.FileField(
        required=True,
        allow_empty_file=False,
    )

    language = serializers.ChoiceField(
        choices=LANGUAGE_CHOICES,
        required=False,
        allow_blank=True,
        allow_null=True,
    )

    # =========================================================
    # Audio Validation
    # =========================================================

    def validate_audio(
        self,
        audio,
    ):
        """
        Validate uploaded farmer audio.
        """

        filename = getattr(
            audio,
            "name",
            "",
        )

        if not filename:
            raise serializers.ValidationError("Audio filename is missing.")

        extension = os.path.splitext(filename)[1].lower()

        # -----------------------------------------------------
        # Extension validation
        # -----------------------------------------------------

        if extension not in self.ALLOWED_EXTENSIONS:

            allowed = ", ".join(
                sorted(
                    extension.lstrip(".").upper()
                    for extension in self.ALLOWED_EXTENSIONS
                )
            )

            raise serializers.ValidationError(
                ("Unsupported audio format. " f"Allowed formats: {allowed}.")
            )

        # -----------------------------------------------------
        # Empty audio validation
        # -----------------------------------------------------

        size = getattr(
            audio,
            "size",
            0,
        )

        if not size or size <= 0:

            raise serializers.ValidationError("Audio file cannot be empty.")

        # -----------------------------------------------------
        # Maximum file size
        # -----------------------------------------------------

        if size > self.MAX_AUDIO_SIZE:

            raise serializers.ValidationError("Audio file must be smaller than 25 MB.")

        return audio

    # =========================================================
    # Language Validation
    # =========================================================

    def validate_language(
        self,
        value,
    ):
        """
        Return None when language is not explicitly supplied.

        This allows automatic language detection downstream.
        """

        if value is None:
            return None

        value = str(value).strip().lower()

        if not value:
            return None

        return value
