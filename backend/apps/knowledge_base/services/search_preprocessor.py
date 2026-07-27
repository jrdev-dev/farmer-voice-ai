import re
from typing import Any, Dict, List

from .normalizer import QuestionNormalizer


class SearchPreprocessor:
    """
    Centralized preprocessing for Farmer Voice AI retrieval.

    Used by:
    - Keyword Search
    - BM25
    - Fuzzy Search
    - Semantic Search preparation
    - Hybrid retrieval
    - Query analysis helpers

    Responsibilities:
    - Normalize multilingual agricultural queries
    - Remove low-information grammatical words
    - Preserve crop/agriculture terminology
    - Preserve useful numbers, percentages and ranges
    - Generate lexical retrieval tokens
    - Generate unique tokens while preserving order

    IMPORTANT:
    This class does NOT maintain a fixed crop list.

    Crop identification/resolution belongs to CropResolver and
    VocabularyService. Therefore arbitrary crops introduced by
    future datasets remain searchable.
    """

    # =========================================================
    # Stop Words
    # =========================================================

    STOP_WORDS = {
        # -----------------------------------------------------
        # Hindi grammatical words
        # -----------------------------------------------------
        "में",
        "की",
        "का",
        "के",
        "को",
        "से",
        "और",
        "या",
        "पर",
        "लिए",
        "तक",
        "भी",
        "ही",
        "द्वारा",
        "साथ",
        "बारे",
        "बारेमें",
        # -----------------------------------------------------
        # Hindi question words
        # -----------------------------------------------------
        "क्या",
        "कौन",
        "कौनसा",
        "कौनसी",
        "कौनसे",
        "कैसे",
        "कैसा",
        "कैसी",
        # -----------------------------------------------------
        # Hindi helping verbs
        # -----------------------------------------------------
        "है",
        "हैं",
        "था",
        "थी",
        "थे",
        "हो",
        "हूँ",
        "हूं",
        "होगा",
        "होगी",
        "होंगे",
        # -----------------------------------------------------
        # Generic Hindi words
        # -----------------------------------------------------
        "तो",
        "सा",
        "सी",
        "वाला",
        "वाली",
        "वाले",
        "मुझे",
        "मेरे",
        "मेरी",
        "हम",
        "हमारे",
        "आप",
        "आपके",
        # -----------------------------------------------------
        # Roman Hindi / Hinglish
        # -----------------------------------------------------
        "me",
        "mein",
        "mai",
        "main",
        "ki",
        "ka",
        "ke",
        "ko",
        "se",
        "par",
        "liye",
        "tak",
        "hai",
        "hain",
        "ho",
        "tha",
        "thi",
        "the",
        "hoga",
        "hogi",
        "honge",
        "kya",
        "kaun",
        "kaunsa",
        "kaunsi",
        "kaunse",
        "kaise",
        "kaisa",
        "kaisi",
        "aur",
        "or",
        "ya",
        "to",
        "bhi",
        "hi",
        "mujhe",
        "mera",
        "meri",
        "mere",
        "ham",
        "hum",
        "aap",
        # -----------------------------------------------------
        # English grammatical words
        # -----------------------------------------------------
        "a",
        "an",
        "the",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "of",
        "in",
        "on",
        "at",
        "to",
        "for",
        "from",
        "with",
        "and",
        "or",
        "by",
        "about",
        "into",
        "which",
        "what",
        "how",
        "when",
        "where",
        "who",
        "whom",
        "whose",
        "should",
        "would",
        "could",
        "can",
        "may",
        "might",
        "do",
        "does",
        "did",
        "my",
        "your",
        "our",
        "their",
        "i",
        "we",
        "you",
    }

    # =========================================================
    # Important agricultural action words
    # =========================================================
    #
    # These are intentionally NOT stop words.
    #
    # Example:
    # "soybean fertilizer डालें"
    #
    # डालें provides useful intent/retrieval information.
    # =========================================================

    PRESERVED_ACTION_WORDS = {
        "डालें",
        "देना",
        "करना",
        "लगाना",
        "बचाना",
        "रोकना",
        "लेना",
        "रखना",
        "बुवाई",
        "कटाई",
        "सिंचाई",
        "छिड़काव",
        "उपचार",
        "fertilizer",
        "seed",
        "soil",
        "disease",
        "pest",
        "irrigation",
        "harvest",
        "storage",
        "spray",
        "treatment",
    }

    # =========================================================
    # Numeric Pattern
    # =========================================================

    NUMBER_PATTERN = re.compile(r"^\d+(?:\.\d+)?" r"(?:-\d+(?:\.\d+)?)?" r"%?$")

    # =========================================================
    # Initialization
    # =========================================================

    def __init__(self):
        self.normalizer = QuestionNormalizer()

    # =========================================================
    # Main Preprocessing
    # =========================================================

    def preprocess(
        self,
        text: Any,
    ) -> Dict[str, Any]:
        """
        Normalize text and produce retrieval-ready information.

        Returns:
        {
            "original": str,
            "normalized": str,
            "tokens": list[str],
            "unique_tokens": list[str],
            "numbers": list[str],
            "token_count": int
        }

        Backward compatibility:
        Existing code using:

            result["normalized"]
            result["tokens"]

        continues to work.
        """

        if text is None:
            return self._empty_result()

        original_text = str(text).strip()

        if not original_text:
            return self._empty_result()

        # =====================================================
        # 1. Normalize
        # =====================================================

        normalized_text = self.normalizer.normalize(original_text)

        if not normalized_text:
            return {
                "original": original_text,
                "normalized": "",
                "tokens": [],
                "unique_tokens": [],
                "numbers": [],
                "token_count": 0,
            }

        # =====================================================
        # 2. Tokenize
        # =====================================================

        raw_tokens = normalized_text.split()

        tokens: List[str] = []
        numbers: List[str] = []

        for raw_word in raw_tokens:

            word = self._clean_token(raw_word)

            if not word:
                continue

            # -------------------------------------------------
            # Preserve agricultural numeric information
            # -------------------------------------------------

            if self._is_number_token(word):

                tokens.append(word)
                numbers.append(word)

                continue

            # -------------------------------------------------
            # Ignore meaningless one-character lexical tokens
            # -------------------------------------------------

            if len(word) < 2:
                continue

            # -------------------------------------------------
            # Important agricultural actions must survive
            # stop-word filtering.
            # -------------------------------------------------

            if word in self.PRESERVED_ACTION_WORDS:

                tokens.append(word)

                continue

            # -------------------------------------------------
            # Stop-word filtering
            # -------------------------------------------------

            if word in self.STOP_WORDS:
                continue

            tokens.append(word)

        # =====================================================
        # 3. Unique Tokens
        # =====================================================
        #
        # Do NOT replace `tokens` with unique tokens.
        #
        # BM25 may benefit from term frequency in some future
        # configurations.
        #
        # Existing code previously received deduplicated tokens,
        # so for compatibility we return unique tokens as
        # `tokens` and expose lexical sequence separately.
        # =====================================================

        unique_tokens = self._unique(tokens)

        unique_numbers = self._unique(numbers)

        return {
            "original": original_text,
            "normalized": normalized_text,
            # Backward-compatible retrieval tokens
            "tokens": unique_tokens,
            # Explicit alias for newer services
            "unique_tokens": unique_tokens,
            # Full filtered token sequence
            "lexical_tokens": tokens,
            # Numeric agricultural evidence
            "numbers": unique_numbers,
            "token_count": len(unique_tokens),
        }

    # =========================================================
    # Token Cleaning
    # =========================================================

    def _clean_token(
        self,
        token: Any,
    ) -> str:
        """
        Safely clean a single normalized token.
        """

        if token is None:
            return ""

        token = str(token)

        token = self.normalizer.normalize_unicode(token)

        token = token.casefold().strip()

        # Remove accidental surrounding punctuation while
        # preserving numeric %, decimal and range characters.
        token = token.strip(".,!?;:\"'`()[]{}<>।")

        return token.strip()

    # =========================================================
    # Numeric Detection
    # =========================================================

    def _is_number_token(
        self,
        token: str,
    ) -> bool:
        """
        Detect useful numeric tokens.

        Examples:
            5
            2.5
            10%
            15-20
            15.5-20.5
        """

        if not token:
            return False

        return bool(self.NUMBER_PATTERN.fullmatch(token))

    # =========================================================
    # Unique Helper
    # =========================================================

    @staticmethod
    def _unique(
        values: List[str],
    ) -> List[str]:
        """
        Remove duplicates while preserving original order.
        """

        return list(dict.fromkeys(values))

    # =========================================================
    # Empty Result
    # =========================================================

    @staticmethod
    def _empty_result() -> Dict[str, Any]:

        return {
            "original": "",
            "normalized": "",
            "tokens": [],
            "unique_tokens": [],
            "lexical_tokens": [],
            "numbers": [],
            "token_count": 0,
        }

    # =========================================================
    # Convenience Methods
    # =========================================================

    def get_tokens(
        self,
        text: Any,
    ) -> List[str]:
        """
        Return retrieval tokens only.
        """

        return self.preprocess(text)["tokens"]

    def get_lexical_tokens(
        self,
        text: Any,
    ) -> List[str]:
        """
        Return full filtered lexical token sequence.
        """

        return self.preprocess(text)["lexical_tokens"]

    def get_normalized_text(
        self,
        text: Any,
    ) -> str:
        """
        Return normalized query only.
        """

        return self.preprocess(text)["normalized"]

    def get_numbers(
        self,
        text: Any,
    ) -> List[str]:
        """
        Extract normalized numeric search tokens.
        """

        return self.preprocess(text)["numbers"]
