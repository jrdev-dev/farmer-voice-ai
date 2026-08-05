from apps.chatbot.models import Message

from apps.knowledge_base.services.crop_resolver import CropResolver
from apps.knowledge_base.services.query_analyzer import QueryAnalyzer


class ContextBuilder:
    """
    Universal conversational context builder.

    Responsibilities
    ----------------
    1. Understand follow-up farmer questions.
    2. Recover crop context from recent conversation.
    3. Resolve crop names dynamically.
    4. Avoid hardcoded crop lists.
    5. Support Hindi, Hinglish and English conversation.
    6. Enrich ambiguous follow-up questions for retrieval.

    Example
    -------
    User:
        "मेरे खेत में सोयाबीन है"

    Follow-up:
        "इसमें कौन सी खाद डालूं?"

    Enriched:
        "सोयाबीन में कौन सी खाद डालूं?"

    IMPORTANT
    ---------
    Conversation context helps resolve references.

    It is NOT trusted agricultural evidence.

    Final agricultural facts must still come from the
    Knowledge Base and pass retrieval/relevance validation.
    """

    # =========================================================
    # Reference / Pronoun Terms
    # =========================================================

    REFERENCE_TERMS = {
        # Hindi
        "इसमें",
        "इसकी",
        "इसका",
        "इसके",
        "इसे",
        "इस पर",
        "उसमें",
        "उसकी",
        "उसका",
        "उसके",
        "उसे",
        "उस पर",
        "फसल में",
        "फसल को",
        # Hinglish
        "isme",
        "iski",
        "iska",
        "iske",
        "ise",
        "usme",
        "usmein",
        "uski",
        "uska",
        "uske",
        "use",
        "issme",
        "issmein",
        "isski",
        "isska",
        "isske",
        "fasal me",
        "fasal mein",
        # English
        "this crop",
        "that crop",
        "this plant",
        "that plant",
        "in it",
        "for it",
        "on it",
    }

    # =========================================================
    # Agriculture Follow-Up Indicators
    # =========================================================

    AGRICULTURE_KEYWORDS = {
        # Hindi
        "खाद",
        "उर्वरक",
        "दवा",
        "दवाई",
        "स्प्रे",
        "बीज",
        "बुवाई",
        "सिंचाई",
        "पानी",
        "रोग",
        "बीमारी",
        "कीट",
        "कीड़ा",
        "कीड़े",
        "खरपतवार",
        "फसल",
        "मिट्टी",
        "पोषक",
        "पोषण",
        "कटाई",
        "उत्पादन",
        "उपज",
        "इलाज",
        "उपचार",
        "नियंत्रण",
        "लक्षण",
        "पत्ते",
        "पत्ती",
        "जड़",
        "जड़ें",
        "फूल",
        "फल",
        "बुवाई",
        "बोना",
        # Hinglish
        "khad",
        "khaad",
        "urvarak",
        "dawa",
        "dawai",
        "spray",
        "beej",
        "bij",
        "buwai",
        "buvai",
        "sinchai",
        "pani",
        "rog",
        "bimari",
        "keet",
        "kida",
        "kide",
        "kharpatwar",
        "fasal",
        "mitti",
        "poshak",
        "katai",
        "utpadan",
        "upaj",
        "ilaj",
        "ilaaj",
        "upchar",
        "niyantran",
        "lakshan",
        # English
        "fertilizer",
        "fertiliser",
        "nutrient",
        "pesticide",
        "insecticide",
        "fungicide",
        "herbicide",
        "medicine",
        "chemical",
        "spray",
        "seed",
        "sowing",
        "irrigation",
        "water",
        "disease",
        "pest",
        "insect",
        "weed",
        "soil",
        "crop",
        "harvest",
        "yield",
        "production",
        "treatment",
        "control",
        "symptom",
        "leaf",
        "leaves",
        "root",
        "flower",
        "fruit",
    }

    # =========================================================
    # Init
    # =========================================================

    def __init__(self):

        self.crop_resolver = CropResolver()

        try:
            self.query_analyzer = QueryAnalyzer()

        except Exception:
            self.query_analyzer = None

    # =========================================================
    # Extract Crop From Text
    # =========================================================

    def extract_crop_from_text(
        self,
        text,
    ):
        """
        Resolve crop from arbitrary text using CropResolver.

        No fixed crop list is maintained here.
        """

        text = self._clean_text(text)

        if not text:
            return None

        try:

            result = self.crop_resolver.get_primary_crop(text)

        except Exception as exc:

            print(
                "CONTEXT CROP RESOLUTION ERROR:",
                str(exc),
            )

            return None

        return self._extract_crop_from_result(result)

    # =========================================================
    # Extract Crop From Conversation
    # =========================================================

    def extract_crop(
        self,
        conversation,
        limit=20,
    ):
        """
        Find the most recently mentioned crop from recent
        USER conversation history.

        Dynamic CropResolver is used instead of a hardcoded
        crop list.
        """

        if conversation is None:
            return None

        try:

            messages = conversation.messages.filter(role=Message.Role.USER).order_by(
                "-created_at"
            )[:limit]

        except Exception as exc:

            print(
                "CONTEXT HISTORY ERROR:",
                str(exc),
            )

            return None

        for message in messages:

            text = self._clean_text(
                getattr(
                    message,
                    "content",
                    "",
                )
            )

            if not text:
                continue

            crop = self.extract_crop_from_text(text)

            if crop:
                return crop

        return None

    # =========================================================
    # Detect Explicit Crop
    # =========================================================

    def question_crop(
        self,
        question,
    ):
        """
        Return crop explicitly present in current question.
        """

        return self.extract_crop_from_text(question)

    # =========================================================
    # Reference Detection
    # =========================================================

    def has_reference(
        self,
        question,
    ):
        """
        Detect whether the current message contains a
        contextual reference such as 'इसमें' or 'isme'.
        """

        text = self._clean_text(question).lower()

        if not text:
            return False

        for term in self.REFERENCE_TERMS:

            if term.lower() in text:
                return True

        return False

    # =========================================================
    # Agriculture Follow-Up Detection
    # =========================================================

    def is_agriculture_followup(
        self,
        question,
    ):
        """
        Determine whether a message appears to be an
        agriculture-related follow-up.

        QueryAnalyzer is used when available, while lexical
        indicators provide a compatibility fallback.
        """

        text = self._clean_text(question)

        if not text:
            return False

        # -----------------------------------------------------
        # QueryAnalyzer
        # -----------------------------------------------------

        if self.query_analyzer is not None:

            try:

                analysis = self.query_analyzer.analyze(text)

                if isinstance(
                    analysis,
                    dict,
                ):

                    # Different analyzer versions may expose
                    # different fields. Accept strong semantic
                    # indicators without tightly coupling this
                    # service to one exact schema.

                    for key in (
                        "is_agriculture",
                        "agriculture_related",
                        "is_agricultural",
                    ):

                        if analysis.get(key) is True:
                            return True

                    topics = analysis.get("topics")

                    if topics:
                        return True

                    topic = analysis.get("topic")

                    if topic:
                        return True

                    concepts = analysis.get("concepts")

                    if concepts:
                        return True

            except Exception as exc:

                print(
                    "CONTEXT QUERY ANALYZER ERROR:",
                    str(exc),
                )

        # -----------------------------------------------------
        # Lexical Fallback
        # -----------------------------------------------------

        lower_text = text.lower()

        return any(
            keyword.lower() in lower_text for keyword in self.AGRICULTURE_KEYWORDS
        )

    # =========================================================
    # Clean Contextual References
    # =========================================================

    def clean_question(
        self,
        question,
    ):
        """
        Remove contextual pronouns/references before attaching
        explicit crop context.

        Example:
            "इसमें कौन सी खाद डालूं?"
                ->
            "कौन सी खाद डालूं?"
        """

        cleaned = self._clean_text(question)

        if not cleaned:
            return ""

        # Longest first so phrases such as "इस पर" are removed
        # before shorter overlapping terms.

        terms = sorted(
            self.REFERENCE_TERMS,
            key=len,
            reverse=True,
        )

        for term in terms:

            cleaned = self._replace_case_insensitive(
                cleaned,
                term,
                " ",
            )

        return self._clean_text(cleaned)

    # =========================================================
    # Build Contextual Question
    # =========================================================

    def build_question(
        self,
        conversation,
        question,
    ):
        """
        Convert an ambiguous follow-up into a retrieval-ready
        contextual question.

        Rules
        -----
        1. Explicit crop in current question always wins.
        2. Never overwrite explicit current crop.
        3. Otherwise recover the latest crop from conversation.
        4. Attach crop only to agriculture-related/reference
           follow-up questions.
        5. Do not invent agricultural facts.
        """

        original_question = self._clean_text(question)

        if not original_question:
            return ""

        # =====================================================
        # 1. Current Question Has Explicit Crop
        # =====================================================

        explicit_crop = self.question_crop(original_question)

        if explicit_crop:

            print("\n" + "=" * 80)
            print("CONTEXT BUILDER")
            print("=" * 80)
            print(
                "Explicit Crop :",
                explicit_crop,
            )
            print("Action        : Current question preserved")
            print("=" * 80 + "\n")

            return original_question

        # =====================================================
        # 2. Recover Previous Crop
        # =====================================================

        previous_crop = self.extract_crop(conversation)

        if not previous_crop:
            return original_question

        # =====================================================
        # 3. Determine Whether Context Is Needed
        # =====================================================

        reference_present = self.has_reference(original_question)

        agriculture_followup = self.is_agriculture_followup(original_question)

        if not (reference_present or agriculture_followup):

            return original_question

        # =====================================================
        # 4. Clean Reference
        # =====================================================

        cleaned_question = self.clean_question(original_question)

        if not cleaned_question:
            cleaned_question = original_question

        # =====================================================
        # 5. Build Enriched Question
        # =====================================================

        enriched_question = self._attach_crop(
            crop=previous_crop,
            question=cleaned_question,
        )

        # =====================================================
        # 6. Debug
        # =====================================================

        print("\n" + "=" * 80)
        print("CONTEXT BUILDER")
        print("=" * 80)

        print(
            "Original Question :",
            original_question,
        )

        print(
            "Previous Crop     :",
            previous_crop,
        )

        print(
            "Reference Present :",
            reference_present,
        )

        print(
            "Agriculture Query :",
            agriculture_followup,
        )

        print(
            "Enriched Question :",
            enriched_question,
        )

        print("=" * 80 + "\n")

        return enriched_question

    # =========================================================
    # Attach Crop
    # =========================================================

    @staticmethod
    def _attach_crop(
        crop,
        question,
    ):
        """
        Attach resolved crop to follow-up query.

        Hindi/Hinglish queries use the natural 'में' connector.
        English queries use a simple crop prefix.
        """

        crop = ContextBuilder._clean_text(crop)

        question = ContextBuilder._clean_text(question)

        if not crop:
            return question

        if not question:
            return crop

        question_lower = question.lower()

        if crop.lower() in question_lower:
            return question

        if ContextBuilder._contains_devanagari(question):

            return f"{crop} में {question}"

        return f"{crop} {question}"

    # =========================================================
    # CropResolver Result Compatibility
    # =========================================================

    @staticmethod
    def _extract_crop_from_result(
        result,
    ):
        """
        Support common CropResolver return formats.

        Examples:
            "Soybean"

            {
                "crop": "Soybean"
            }

            {
                "canonical_crop": "Soybean"
            }

            {
                "resolved_crop": "Soybean"
            }
        """

        if result is None:
            return None

        if isinstance(
            result,
            str,
        ):

            value = result.strip()

            return value or None

        if isinstance(
            result,
            dict,
        ):

            for key in (
                "canonical_crop",
                "resolved_crop",
                "crop",
                "name",
            ):

                value = result.get(key)

                if value:

                    value = str(value).strip()

                    if value:
                        return value

        return None

    # =========================================================
    # Helpers
    # =========================================================

    @staticmethod
    def _clean_text(
        value,
    ):

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

    @staticmethod
    def _replace_case_insensitive(
        text,
        old,
        new,
    ):
        """
        Replace substring without changing the case of the
        remaining text.
        """

        if not text or not old:
            return text

        lower_text = text.lower()
        lower_old = old.lower()

        result = []
        start = 0

        while True:

            index = lower_text.find(
                lower_old,
                start,
            )

            if index == -1:

                result.append(text[start:])

                break

            result.append(text[start:index])

            result.append(new)

            start = index + len(old)

        return "".join(result)

    @staticmethod
    def _contains_devanagari(
        text,
    ):

        return any("\u0900" <= char <= "\u097f" for char in str(text))
