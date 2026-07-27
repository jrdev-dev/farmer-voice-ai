from pathlib import Path

from rest_framework import serializers


class OCRRequestSerializer(serializers.Serializer):
    """
    Validate OCR upload requests.

    Supported image formats:
    - JPG / JPEG
    - PNG
    - WEBP
    - BMP
    - TIFF

    Language is optional.
    If omitted, the OCR service uses its default
    multilingual configuration.
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
    # Supported File Extensions
    # =========================================================

    ALLOWED_EXTENSIONS = {
        ".jpg",
        ".jpeg",
        ".png",
        ".webp",
        ".bmp",
        ".tif",
        ".tiff",
    }

    # 15 MB
    MAX_FILE_SIZE = 15 * 1024 * 1024

    # =========================================================
    # Fields
    # =========================================================

    image = serializers.FileField(
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
    # Image Validation
    # =========================================================

    def validate_image(
        self,
        image,
    ):
        """
        Validate uploaded OCR image.
        """

        filename = getattr(
            image,
            "name",
            "",
        )

        if not filename:

            raise serializers.ValidationError("Image filename is missing.")

        extension = Path(filename).suffix.lower()

        # -----------------------------------------------------
        # Extension Validation
        # -----------------------------------------------------

        if extension not in self.ALLOWED_EXTENSIONS:

            allowed_formats = ", ".join(
                sorted(item.lstrip(".").upper() for item in self.ALLOWED_EXTENSIONS)
            )

            raise serializers.ValidationError(
                ("Unsupported image format. " f"Allowed formats: {allowed_formats}.")
            )

        # -----------------------------------------------------
        # Empty File Validation
        # -----------------------------------------------------

        size = getattr(
            image,
            "size",
            0,
        )

        if not size or size <= 0:

            raise serializers.ValidationError("Image file cannot be empty.")

        # -----------------------------------------------------
        # Maximum File Size
        # -----------------------------------------------------

        if size > self.MAX_FILE_SIZE:

            raise serializers.ValidationError("Image file must be smaller than 15 MB.")

        return image

    # =========================================================
    # Language Validation
    # =========================================================

    def validate_language(
        self,
        value,
    ):
        """
        Return None when no language was explicitly supplied.
        """

        if value is None:
            return None

        value = str(value).strip().lower()

        if not value:
            return None

        return value
