import re
import unicodedata
from typing import Optional, Set


class IntentService:
    """
    Conservative multilingual conversational intent router.

    Supported intents
    -----------------
    greeting
        Pure greeting/salutation.

    context
        A clear declarative statement whose primary purpose is
        to establish conversation context.

    question
        Any explicit or plausible farmer query, advice request,
        symptom/problem report, or uncertain utterance that
        should continue through query understanding/retrieval.

    Design principle
    ----------------
    Intent detection is NOT agricultural knowledge extraction.

    Crop, disease, fertilizer, pesticide and other domain entities
    belong to QueryAnalyzer / CropResolver / vocabulary services.

    This router deliberately prefers "question" for uncertain
    non-empty utterances. A false "context" classification is more
    damaging because ChatService may skip retrieval completely.
    """

    QUESTION_WORDS = {
        # Hindi
        "क्या",
        "कौन",
        "कौनसा",
        "कौनसी",
        "कौनसे",
        "कब",
        "कहाँ",
        "कहा",
        "कैसे",
        "कितना",
        "कितनी",
        "कितने",
        "क्यों",
        # Roman Hindi / Hinglish
        "kya",
        "ky",
        "kaun",
        "kon",
        "kaunsa",
        "kaunsi",
        "kaunse",
        "konsa",
        "konsi",
        "konse",
        "kab",
        "kaha",
        "kahan",
        "kaise",
        "kitna",
        "kitni",
        "kitne",
        "kyu",
        "kyun",
        # English
        "what",
        "which",
        "when",
        "where",
        "why",
        "how",
        "who",
    }

    ACTION_WORDS = {
        # Hindi
        "बताओ",
        "बताइए",
        "बताएं",
        "बताये",
        "करूं",
        "करूँ",
        "करें",
        "करना",
        "डालूं",
        "डालूँ",
        "डालें",
        "लगाऊं",
        "लगाऊँ",
        "लगाएँ",
        "दूं",
        "दूँ",
        "दें",
        "बचाएं",
        "बचाऊं",
        "रोकें",
        "उपचार",
        "इलाज",
        # Roman Hindi / Hinglish
        "batao",
        "bataye",
        "batayen",
        "karu",
        "karun",
        "kare",
        "karen",
        "dalu",
        "dalun",
        "dale",
        "lagau",
        "lagaun",
        "lagaye",
        "du",
        "dun",
        "de",
        "bachaye",
        "bachau",
        "roke",
        "ilaj",
        "ilaaj",
        # English
        "tell",
        "suggest",
        "recommend",
        "apply",
        "use",
        "treat",
        "control",
        "prevent",
        "solve",
        "help",
    }

    PROBLEM_WORDS = {
        # Hindi
        "रोग",
        "बीमारी",
        "कीट",
        "कीड़ा",
        "कीड़े",
        "खरपतवार",
        "पीला",
        "पीली",
        "पीले",
        "सूख",
        "सूखना",
        "सूखने",
        "मुरझा",
        "मुरझाना",
        "सड़",
        "सड़न",
        "धब्बे",
        "धब्बा",
        "नुकसान",
        "समस्या",
        "खराब",
        # Roman Hindi
        "rog",
        "bimari",
        "keet",
        "kida",
        "kide",
        "kharpatwar",
        "pila",
        "pili",
        "pile",
        "sukh",
        "sukhna",
        "murjha",
        "sadna",
        "dhabbe",
        "nuksan",
        "samasya",
        "kharab",
        # English
        "disease",
        "pest",
        "insect",
        "weed",
        "yellow",
        "dry",
        "drying",
        "wilt",
        "wilting",
        "rot",
        "spots",
        "damage",
        "problem",
        "dying",
    }

    AGRICULTURE_ADVICE_WORDS = {
        # Hindi
        "खाद",
        "उर्वरक",
        "दवा",
        "दवाई",
        "स्प्रे",
        "सिंचाई",
        "बीज",
        "बुवाई",
        "कीटनाशक",
        "फफूंदनाशक",
        "खरपतवारनाशी",
        "पोषक",
        "इलाज",
        "उपचार",
        # Roman Hindi
        "khad",
        "khaad",
        "urvarak",
        "dawa",
        "dawai",
        "spray",
        "sinchai",
        "beej",
        "bij",
        "buwai",
        "buvai",
        "keetnashak",
        "poshak",
        "ilaj",
        "ilaaj",
        # English
        "fertilizer",
        "fertiliser",
        "pesticide",
        "insecticide",
        "fungicide",
        "herbicide",
        "irrigation",
        "seed",
        "sowing",
        "nutrient",
        "treatment",
    }

    GREETINGS = {
        "नमस्ते",
        "नमस्कार",
        "राम राम",
        "hi",
        "hello",
        "hey",
        "hii",
        "hiii",
        "namaste",
        "namaskar",
        "ram ram",
        "good morning",
        "good afternoon",
        "good evening",
    }

    # These patterns are intentionally restricted to clear
    # context-establishing constructions.
    CONTEXT_PATTERNS = (
        # Hindi
        "मेरे खेत में",
        "मेरी फसल",
        "मेरे पास",
        "मैंने लगाया",
        "मैंने लगाई",
        "मैंने बोया",
        "मैंने बोई",
        # Roman Hindi / Hinglish
        "mere khet me",
        "mere khet mein",
        "meri fasal",
        "mere paas",
        "maine lagaya",
        "maine lagayi",
        "maine boya",
        "maine boyi",
        # English
        "my field has",
        "my crop is",
        "i planted",
        "i have planted",
        "i sowed",
        "i am growing",
    )

    # A clear context statement should usually contain a
    # declarative/state signal rather than merely a context prefix.
    CONTEXT_STATE_WORDS = {
        # Hindi
        "है",
        "हैं",
        "था",
        "थी",
        "थे",
        "लगी",
        "लगा",
        "लगाया",
        "लगाई",
        "बोया",
        "बोई",
        # Roman Hindi
        "hai",
        "hain",
        "h",
        "tha",
        "thi",
        "the",
        "lagi",
        "laga",
        "lagaya",
        "lagayi",
        "boya",
        "boyi",
        # English
        "is",
        "are",
        "has",
        "have",
        "planted",
        "sowed",
        "growing",
    }

    def detect(
        self,
        message: str,
        *,
        normalized_message: Optional[str] = None,
    ) -> str:
        """
        Detect routing intent.

        Important behavior:
        -------------------
        Unknown non-empty text defaults to ``question``.

        We only return ``context`` when the message is positively
        identified as a context-establishing statement.
        """

        raw_text = self._normalize(message)

        if not raw_text:
            return "context"

        semantic_text = self._normalize(
            normalized_message if normalized_message else raw_text
        )

        # Use both raw and normalized forms. ASR normalization may
        # recover useful question/action words while raw text may
        # preserve native-script information.
        combined_text = self._merge_text(
            raw_text,
            semantic_text,
        )

        greeting_text = self._remove_punctuation(combined_text)

        # -----------------------------------------------------
        # 1. Pure greeting
        # -----------------------------------------------------

        if greeting_text in self.GREETINGS:
            return "greeting"

        # -----------------------------------------------------
        # 2. Explicit question punctuation
        # -----------------------------------------------------

        if self._has_question_mark(combined_text):
            return "question"

        cleaned_text = self._remove_punctuation(combined_text)

        words = self._tokenize(cleaned_text)

        # -----------------------------------------------------
        # 3. Explicit question language
        # -----------------------------------------------------

        if words.intersection(self.QUESTION_WORDS):
            return "question"

        # -----------------------------------------------------
        # 4. Advice/action request
        # -----------------------------------------------------

        if words.intersection(self.ACTION_WORDS):
            return "question"

        # -----------------------------------------------------
        # 5. Agricultural symptom/problem report
        # -----------------------------------------------------

        if words.intersection(self.PROBLEM_WORDS):
            return "question"

        # -----------------------------------------------------
        # 6. Agricultural advice subject
        # -----------------------------------------------------
        #
        # A short utterance such as:
        #
        #   "soybean fertilizer"
        #   "गेहूं दवा"
        #
        # may be a perfectly valid voice query even when ASR has
        # lost the interrogative/action word.
        #
        # Therefore domain-advice terminology is enough to keep
        # the utterance in the query pipeline.
        # -----------------------------------------------------

        if words.intersection(self.AGRICULTURE_ADVICE_WORDS):
            return "question"

        # -----------------------------------------------------
        # 7. Clear context statement
        # -----------------------------------------------------

        if self._is_clear_context_statement(
            cleaned_text,
            words,
        ):
            return "context"

        # -----------------------------------------------------
        # 8. Conservative fallback
        # -----------------------------------------------------
        #
        # Do NOT silently classify uncertain ASR output as context.
        # Downstream QueryAnalyzer/RAG/relevance logic is better
        # positioned to decide whether useful agricultural evidence
        # exists.
        # -----------------------------------------------------

        return "question"

    def _is_clear_context_statement(
        self,
        text: str,
        words: Set[str],
    ) -> bool:
        """
        Return True only for positively identified context.

        A message that also looks like a question/advice request
        never becomes context.
        """

        if not text:
            return False

        if words.intersection(self.QUESTION_WORDS):
            return False

        if words.intersection(self.ACTION_WORDS):
            return False

        if words.intersection(self.PROBLEM_WORDS):
            return False

        if words.intersection(self.AGRICULTURE_ADVICE_WORDS):
            return False

        pattern_found = any(pattern in text for pattern in self.CONTEXT_PATTERNS)

        if not pattern_found:
            return False

        # Some native-script context patterns are already strongly
        # declarative, but requiring a state token further reduces
        # accidental routing.
        if words.intersection(self.CONTEXT_STATE_WORDS):
            return True

        # English patterns such as "i planted soybean" already
        # contain the state/action inside the phrase.
        strong_patterns = (
            "i planted",
            "i have planted",
            "i sowed",
            "i am growing",
            "मैंने लगाया",
            "मैंने लगाई",
            "मैंने बोया",
            "मैंने बोई",
            "maine lagaya",
            "maine lagayi",
            "maine boya",
            "maine boyi",
        )

        return any(pattern in text for pattern in strong_patterns)

    @staticmethod
    def _has_question_mark(
        text: str,
    ) -> bool:

        return any(marker in text for marker in ("?", "？"))

    @staticmethod
    def _tokenize(
        text: str,
    ) -> Set[str]:

        if not text:
            return set()

        return {token for token in text.split() if token}

    @staticmethod
    def _merge_text(
        first: str,
        second: str,
    ) -> str:
        """
        Combine raw and normalized forms without duplicating an
        identical string.
        """

        first = (first or "").strip()
        second = (second or "").strip()

        if not first:
            return second

        if not second:
            return first

        if first == second:
            return first

        return f"{first} {second}"

    @staticmethod
    def _normalize(
        message,
    ) -> str:

        if message is None:
            return ""

        text = str(message).replace(
            "\x00",
            " ",
        )

        text = unicodedata.normalize(
            "NFKC",
            text,
        )

        text = text.casefold()

        return " ".join(text.strip().split())

    @staticmethod
    def _remove_punctuation(
        text: str,
    ) -> str:

        if not text:
            return ""

        # Keep letters/numbers from every Unicode script.
        # Replace punctuation/symbol separators with spaces.
        text = re.sub(
            r"[?!？！.,،;:।]+",
            " ",
            text,
        )

        return " ".join(text.split())
