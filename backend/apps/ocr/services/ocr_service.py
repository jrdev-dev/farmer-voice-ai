import logging
from pathlib import Path

import easyocr

logger = logging.getLogger(__name__)


class OCRService:
    """
    Multilingual OCR service for Farmer Voice AI.

    Responsibilities
    ----------------
    1. Read text from uploaded agricultural images.
    2. Support multiple Indian languages.
    3. Return extracted text with OCR confidence.
    4. Keep OCR independent from the Knowledge Base.

    Important
    ---------
    OCR output is untrusted extracted text.

    This service does NOT automatically insert OCR text
    into the trusted agricultural Knowledge Base.
    """

    # =========================================================
    # Application Language -> EasyOCR Language
    # =========================================================

    LANGUAGE_MAP = {
        "hi": "hi",
        "en": "en",
        "mr": "mr",
        "gu": "gu",
        "pa": "pa",
        "ta": "ta",
        "te": "te",
        "hinglish": "hi",
    }

    # =========================================================
    # Reader Cache
    # =========================================================
    #
    # EasyOCR model loading is expensive.
    # Readers are cached and reused between requests.
    # =========================================================

    _readers = {}

    # =========================================================
    # Constructor
    # =========================================================

    def __init__(
        self,
        gpu=False,
    ):

        self.gpu = gpu

    # =========================================================
    # Language Normalization
    # =========================================================

    def _normalize_language(
        self,
        language,
    ):

        if language is None:
            return None

        value = str(language).strip().lower()

        if not value:
            return None

        value = value.replace(
            "_",
            "-",
        )

        aliases = {
            "hindi": "hi",
            "english": "en",
            "marathi": "mr",
            "gujarati": "gu",
            "punjabi": "pa",
            "tamil": "ta",
            "telugu": "te",
            "hinglish": "hinglish",
            "hi-in": "hi",
            "en-in": "en",
            "mr-in": "mr",
            "gu-in": "gu",
            "pa-in": "pa",
            "ta-in": "ta",
            "te-in": "te",
        }

        value = aliases.get(
            value,
            value,
        )

        if value in self.LANGUAGE_MAP:
            return value

        prefix = value.split(
            "-",
            1,
        )[0]

        if prefix in self.LANGUAGE_MAP:
            return prefix

        return None

    # =========================================================
    # EasyOCR Languages
    # =========================================================

    def _get_reader_languages(
        self,
        language,
    ):
        """
        Build EasyOCR language configuration.

        English is included with supported Indian languages
        because agricultural documents frequently contain
        mixed English terminology, numbers and product text.
        """

        language = self._normalize_language(language)

        if language is None:
            # Default project language.
            return [
                "hi",
                "en",
            ]

        easyocr_language = self.LANGUAGE_MAP[language]

        if easyocr_language == "en":
            return [
                "en",
            ]

        return [
            easyocr_language,
            "en",
        ]

    # =========================================================
    # Reader
    # =========================================================

    def _get_reader(
        self,
        languages,
    ):
        """
        Get or create cached EasyOCR reader.
        """

        key = (
            tuple(languages),
            bool(self.gpu),
        )

        if key not in self._readers:

            logger.info(
                "Loading EasyOCR reader. languages=%s gpu=%s",
                languages,
                self.gpu,
            )

            self._readers[key] = easyocr.Reader(
                languages,
                gpu=self.gpu,
            )

        return self._readers[key]

    # =========================================================
    # Extract Text
    # =========================================================

    def extract_text(
        self,
        image_path,
        language=None,
    ):
        """
        Extract text from an image.

        Returns
        -------
        {
            "success": bool,
            "text": str,
            "language": str | None,
            "confidence": float,
            "lines": [...]
        }
        """

        # -----------------------------------------------------
        # Validate Image
        # -----------------------------------------------------

        if not image_path:

            raise ValueError("Image path is required.")

        image_path = Path(image_path)

        if not image_path.exists():

            raise FileNotFoundError(f"Image file not found: {image_path}")

        if not image_path.is_file():

            raise ValueError("Image path must point to a file.")

        if image_path.stat().st_size <= 0:

            raise ValueError("Image file is empty.")

        # -----------------------------------------------------
        # Resolve Language
        # -----------------------------------------------------

        normalized_language = self._normalize_language(language)

        reader_languages = self._get_reader_languages(normalized_language)

        reader = self._get_reader(reader_languages)

        # -----------------------------------------------------
        # OCR
        # -----------------------------------------------------

        results = reader.readtext(
            str(image_path),
            detail=1,
            paragraph=False,
        )

        # -----------------------------------------------------
        # Process OCR Results
        # -----------------------------------------------------

        lines = []

        text_parts = []

        confidence_values = []

        for result in results:

            if (
                not isinstance(
                    result,
                    (list, tuple),
                )
                or len(result) < 3
            ):
                continue

            _, detected_text, confidence = (
                result[0],
                result[1],
                result[2],
            )

            detected_text = self._clean_text(detected_text)

            if not detected_text:
                continue

            confidence = self._safe_confidence(confidence)

            text_parts.append(detected_text)

            confidence_values.append(confidence)

            lines.append(
                {
                    "text": detected_text,
                    "confidence": round(
                        confidence * 100,
                        2,
                    ),
                }
            )

        # -----------------------------------------------------
        # Final Text
        # -----------------------------------------------------

        extracted_text = " ".join(text_parts).strip()

        # -----------------------------------------------------
        # Average OCR Confidence
        # -----------------------------------------------------

        if confidence_values:

            average_confidence = sum(confidence_values) / len(confidence_values)

        else:

            average_confidence = 0.0

        average_confidence = round(
            average_confidence * 100,
            2,
        )

        success = bool(extracted_text)

        logger.info(
            ("OCR completed. language=%s " "lines=%s confidence=%.2f"),
            normalized_language,
            len(lines),
            average_confidence,
        )

        return {
            "success": success,
            "text": extracted_text,
            "language": normalized_language,
            "confidence": average_confidence,
            "lines": lines,
        }

    # =========================================================
    # Helpers
    # =========================================================

    @staticmethod
    def _clean_text(
        value,
    ):

        if value is None:
            return ""

        value = str(value).replace(
            "\x00",
            " ",
        )

        return " ".join(value.strip().split())

    @staticmethod
    def _safe_confidence(
        value,
    ):

        try:

            value = float(value)

        except (
            TypeError,
            ValueError,
        ):

            return 0.0

        return max(
            0.0,
            min(
                1.0,
                value,
            ),
        )
