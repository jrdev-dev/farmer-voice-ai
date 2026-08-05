import re
from typing import Dict


class LanguageService:
    """
    Multilingual language detector for Farmer Voice AI.

    Supported languages
    -------------------
    hi       -> Hindi
    en       -> English
    hinglish -> Roman Hindi / Hinglish
    gu       -> Gujarati
    mr       -> Marathi
    pa       -> Punjabi
    ta       -> Tamil
    te       -> Telugu

    Design
    ------
    1. Detect strong script-specific languages first.
    2. Distinguish Hindi and Marathi inside Devanagari.
    3. Detect Roman Hindi / Hinglish using conversational words.
    4. Default Latin-script text to English.

    IMPORTANT
    ---------
    Crop names are intentionally not used as primary language
    signals because crop names may occur across languages.
    """

    # =========================================================
    # Unicode Script Patterns
    # =========================================================

    DEVANAGARI_PATTERN = re.compile(r"[\u0900-\u097F]")

    GUJARATI_PATTERN = re.compile(r"[\u0A80-\u0AFF]")

    GURMUKHI_PATTERN = re.compile(r"[\u0A00-\u0A7F]")

    TAMIL_PATTERN = re.compile(r"[\u0B80-\u0BFF]")

    TELUGU_PATTERN = re.compile(r"[\u0C00-\u0C7F]")

    LATIN_WORD_PATTERN = re.compile(r"[a-zA-Z]+")

    # =========================================================
    # Hinglish Indicators
    # =========================================================

    HINGLISH_WORDS = {
        # Conversation
        "kya",
        "kyu",
        "kyun",
        "kaun",
        "kaunsa",
        "kaunsi",
        "konsa",
        "konsi",
        "kab",
        "kaha",
        "kahan",
        "kaise",
        "kitna",
        "kitni",
        "kitne",
        # Pronouns / context
        "mai",
        "main",
        "mera",
        "mere",
        "meri",
        "mujhe",
        "isme",
        "ismein",
        "iski",
        "iska",
        "iske",
        "usme",
        "usmein",
        "uski",
        "uska",
        "uske",
        # Grammar
        "hai",
        "hain",
        "nahi",
        "nahin",
        "ko",
        "se",
        "me",
        "mein",
        "par",
        "ke",
        "ki",
        "ka",
        # Agriculture
        "khet",
        "fasal",
        "khad",
        "khaad",
        "urvarak",
        "pani",
        "beej",
        "bij",
        "dawa",
        "dawai",
        "sinchai",
        "buwai",
        "buvai",
        "keet",
        "kida",
        "rog",
        "bimari",
        "mitti",
        "kharpatwar",
        "upaj",
        # Actions
        "dalna",
        "dalu",
        "dalun",
        "daalu",
        "dena",
        "du",
        "dun",
        "karna",
        "karu",
        "karun",
        "kare",
        "lagana",
        "lagau",
        "batao",
        "bataye",
        "bachaye",
        "btao",
        "kb",
        "bou",
        "aalu",
        "alu",
        "m",
        "me",
        "pe",
        "kr",
        "kar",
        "karo",
        "raha",
        "rhi",
        "rha",
        "ho",
        "hu",
        "hoon",
        "hun",
        # Greetings
        "namaste",
        "namaskar",
        "dhanyavad",
        "dhanyawaad",
        "shukriya",
    }

    # =========================================================
    # Marathi Indicators
    # =========================================================
    #
    # Hindi and Marathi both use Devanagari.
    # These common Marathi conversational markers help
    # distinguish Marathi farmer messages.
    # =========================================================

    MARATHI_WORDS = {
        "आहे",
        "आहेत",
        "नाही",
        "काय",
        "कसे",
        "कशी",
        "कसा",
        "कोणते",
        "कोणती",
        "किती",
        "कधी",
        "कुठे",
        "माझ्या",
        "माझी",
        "माझे",
        "मला",
        "यात",
        "त्यात",
        "करावे",
        "करू",
        "द्यावे",
        "टाकावे",
        "शेतात",
        "शेत",
        "पीक",
        "पिकाला",
        "पिकात",
        "खत",
        "पाणी",
        "फवारणी",
    }

    # =========================================================
    # Hindi Indicators
    # =========================================================

    HINDI_WORDS = {
        "है",
        "हैं",
        "नहीं",
        "क्या",
        "कैसे",
        "कैसा",
        "कैसी",
        "कौन",
        "कौनसी",
        "कौनसा",
        "कितना",
        "कितनी",
        "कितने",
        "कब",
        "कहाँ",
        "क्यों",
        "मुझे",
        "मेरे",
        "मेरी",
        "मेरा",
        "इसमें",
        "उसमें",
        "करूं",
        "करूँ",
        "डालूं",
        "डालूँ",
        "बताओ",
        "बताइए",
        "खेत",
        "फसल",
        "खाद",
        "दवा",
        "सिंचाई",
        "बीज",
    }

    # =========================================================
    # Main Detection
    # =========================================================

    def detect(
        self,
        text: str,
    ) -> str:
        """
        Detect primary language.

        Returns one of:
        hi, en, hinglish, gu, mr, pa, ta, te
        """

        text = self._normalize(text)

        if not text:
            return "hi"

        # Explicit language request check (e.g. "hindi m btao", "in hindi")
        lower_text = text.lower()
        if re.search(r"\b(hindi|hindhi|hinglish)\b", lower_text) or re.search(r"हिंदी|हिन्दी", text):
            return "hi"

        # =====================================================
        # 1. Script-Specific Languages
        # =====================================================

        script_counts = self._script_counts(text)

        # Gujarati
        if script_counts["gu"] > 0:
            return "gu"

        # Punjabi / Gurmukhi
        if script_counts["pa"] > 0:
            return "pa"

        # Tamil
        if script_counts["ta"] > 0:
            return "ta"

        # Telugu
        if script_counts["te"] > 0:
            return "te"

        # =====================================================
        # 2. Devanagari -> Hindi / Marathi
        # =====================================================

        if script_counts["devanagari"] > 0:

            return self._detect_devanagari_language(text)

        # =====================================================
        # 3. Latin -> Hinglish / English
        # =====================================================

        return self._detect_latin_language(text)

    # =========================================================
    # Detailed Detection
    # =========================================================

    def detect_details(
        self,
        text: str,
    ) -> Dict:
        """
        Return diagnostic language information.

        Useful for testing/debugging.
        """

        normalized = self._normalize(text)

        language = self.detect(normalized)

        script_counts = self._script_counts(normalized)

        latin_words = set(
            word.lower() for word in self.LATIN_WORD_PATTERN.findall(normalized)
        )

        hinglish_matches = sorted(latin_words.intersection(self.HINGLISH_WORDS))

        return {
            "language": language,
            "normalized_text": normalized,
            "script_counts": script_counts,
            "hinglish_matches": hinglish_matches,
        }

    # =========================================================
    # Devanagari Detection
    # =========================================================

    def _detect_devanagari_language(
        self,
        text,
    ) -> str:
        """
        Distinguish Hindi from Marathi.

        Because both use Devanagari, lexical evidence is used.
        """

        words = set(self._word_tokens(text))

        marathi_score = len(words.intersection(self.MARATHI_WORDS))

        hindi_score = len(words.intersection(self.HINDI_WORDS))

        if marathi_score > hindi_score and marathi_score > 0:
            return "mr"

        # Hindi is the default for ambiguous Devanagari
        # messages in the current application.

        return "hi"

    # =========================================================
    # Latin Detection
    # =========================================================

    def _detect_latin_language(
        self,
        text,
    ) -> str:
        """
        Distinguish Hinglish from normal English.
        """

        words = {word.lower() for word in self.LATIN_WORD_PATTERN.findall(text)}

        if not words:
            return "hi"

        matches = words.intersection(self.HINGLISH_WORDS)

        if not matches:
            return "en"

        # -----------------------------------------------------
        # Strong Hinglish Evidence
        # -----------------------------------------------------

        if len(matches) >= 2:
            return "hinglish"

        # -----------------------------------------------------
        # Single Strong Conversational Marker
        # -----------------------------------------------------

        strong_markers = {
            "kya",
            "kyu",
            "kyun",
            "kaise",
            "kaunsi",
            "kaunsa",
            "konsi",
            "konsa",
            "mujhe",
            "mere",
            "meri",
            "mera",
            "isme",
            "ismein",
            "usme",
            "usmein",
            "batao",
            "bataye",
            "dalu",
            "dalun",
            "karu",
            "karun",
        }

        if matches.intersection(strong_markers):
            return "hinglish"

        # -----------------------------------------------------
        # Ratio Check
        # -----------------------------------------------------

        ratio = len(matches) / max(
            len(words),
            1,
        )

        if ratio >= 0.30:
            return "hinglish"

        return "en"

    # =========================================================
    # Script Counts
    # =========================================================

    def _script_counts(
        self,
        text,
    ) -> Dict[str, int]:

        return {
            "devanagari": len(self.DEVANAGARI_PATTERN.findall(text)),
            "gu": len(self.GUJARATI_PATTERN.findall(text)),
            "pa": len(self.GURMUKHI_PATTERN.findall(text)),
            "ta": len(self.TAMIL_PATTERN.findall(text)),
            "te": len(self.TELUGU_PATTERN.findall(text)),
        }

    # =========================================================
    # Word Tokenization
    # =========================================================

    @staticmethod
    def _word_tokens(
        text,
    ):

        return re.findall(
            r"[\w\u0900-\u097F]+",
            text.lower(),
            flags=re.UNICODE,
        )

    # =========================================================
    # Normalize
    # =========================================================

    @staticmethod
    def _normalize(
        text,
    ) -> str:

        if text is None:
            return ""

        text = str(text).replace(
            "\x00",
            " ",
        )

        return " ".join(text.strip().lower().split())
