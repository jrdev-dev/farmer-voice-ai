from pathlib import Path
from typing import Any, Dict, List


class PromptBuilder:
    """
    Production RAG prompt builder for Farmer Voice AI.

    Responsibilities
    ----------------
    1. Load the central system prompt.
    2. Convert selected Knowledge records into structured evidence.
    3. Include relevant conversation context.
    4. Clearly separate trusted evidence from user-controlled text.
    5. Force evidence-grounded agricultural answers.
    6. Reduce hallucinations and prompt-injection risk.
    7. Support multilingual farmer questions.
    """

    MAX_DOCUMENTS = 3

    MAX_CONVERSATION_CONTEXT = 800

    MAX_FIELD_LENGTH = 1800

    def __init__(self):

        prompt_path = (
            Path(__file__).resolve().parent.parent / "prompts" / "system_prompt.txt"
        )

        if not prompt_path.exists():
            raise FileNotFoundError(f"System prompt file not found: {prompt_path}")

        self.system_prompt = prompt_path.read_text(encoding="utf-8").strip()

        if not self.system_prompt:
            raise ValueError("system_prompt.txt is empty.")

    # =========================================================
    # Helpers
    # =========================================================

    @staticmethod
    def _clean(value: Any) -> str:
        """
        Convert values into safe normalized text.
        """

        if value is None:
            return ""

        return " ".join(str(value).replace("\x00", " ").strip().split())

    def _limit(
        self,
        value: Any,
        maximum: int = None,
    ) -> str:

        text = self._clean(value)

        if maximum is None:
            maximum = self.MAX_FIELD_LENGTH

        if len(text) <= maximum:
            return text

        return text[:maximum].rstrip() + "..."

    @staticmethod
    def _get(
        obj: Any,
        field: str,
        default="",
    ):

        if obj is None:
            return default

        if isinstance(obj, dict):
            return obj.get(field, default)

        return getattr(
            obj,
            field,
            default,
        )

    # =========================================================
    # Source Metadata
    # =========================================================

    def _build_source_metadata(
        self,
        knowledge,
    ) -> List[str]:

        source = self._get(
            knowledge,
            "knowledge_source",
            None,
        )

        if source is None:
            return []

        fields = []

        source_name = self._limit(
            self._get(
                source,
                "source_name",
                "",
            )
        )

        title = self._limit(
            self._get(
                source,
                "title",
                "",
            )
        )

        source_type = self._limit(
            self._get(
                source,
                "source_type",
                "",
            )
        )

        version = self._limit(
            self._get(
                source,
                "version",
                "",
            )
        )

        if source_name:
            fields.append(f"Source Name: {source_name}")

        if title:
            fields.append(f"Source Title: {title}")

        if source_type:
            fields.append(f"Source Type: {source_type}")

        if version:
            fields.append(f"Source Version: {version}")

        return fields

    # =========================================================
    # Build One Evidence Document
    # =========================================================

    def _build_document(
        self,
        item: Dict,
        index: int,
    ) -> str:

        knowledge = item.get("knowledge")

        if knowledge is None:
            return ""

        lines = [f"[TRUSTED_DOCUMENT_{index}]"]

        # -----------------------------------------------------
        # Structured agricultural metadata
        # -----------------------------------------------------

        field_mapping = [
            ("Crop", "crop"),
            ("Category", "category"),
            ("Subcategory", "subcategory"),
            ("Domain", "domain"),
            ("Stage", "stage"),
            ("Language", "language"),
        ]

        for label, field in field_mapping:

            value = self._limit(
                self._get(
                    knowledge,
                    field,
                    "",
                )
            )

            if value:
                lines.append(f"{label}: {value}")

        # -----------------------------------------------------
        # Trusted Question
        # -----------------------------------------------------

        question = self._limit(
            self._get(
                knowledge,
                "question",
                "",
            )
        )

        if question:

            lines.extend(
                [
                    "",
                    "Knowledge Question:",
                    question,
                ]
            )

        # -----------------------------------------------------
        # Trusted Answer
        # -----------------------------------------------------

        answer = self._limit(
            self._get(
                knowledge,
                "answer",
                "",
            )
        )

        if answer:

            lines.extend(
                [
                    "",
                    "Trusted Answer:",
                    answer,
                ]
            )

        # -----------------------------------------------------
        # Keywords
        # -----------------------------------------------------

        keywords = self._limit(
            self._get(
                knowledge,
                "keywords",
                "",
            )
        )

        if keywords:

            lines.extend(
                [
                    "",
                    "Keywords:",
                    keywords,
                ]
            )

        # -----------------------------------------------------
        # Source metadata
        # -----------------------------------------------------

        source_fields = self._build_source_metadata(knowledge)

        if source_fields:

            lines.append("")

            lines.extend(source_fields)

        # -----------------------------------------------------
        # Retrieval metadata
        #
        # Useful context for debugging/model prioritization.
        # These scores are NOT agricultural facts.
        # -----------------------------------------------------



        # hybrid_score = item.get("score")

        # semantic_score = item.get("semantic_raw_score")

        # question_score = item.get(
        #     "question_raw_score",
        #     item.get("question_score"),
        # )

        # retrieval_lines = []

        # try:
        #     if hybrid_score is not None:
        #         retrieval_lines.append(f"Hybrid Score: {float(hybrid_score):.4f}")
        # except (TypeError, ValueError):
        #     pass

        # try:
        #     if semantic_score is not None:
        #         retrieval_lines.append(f"Semantic Score: {float(semantic_score):.4f}")
        # except (TypeError, ValueError):
        #     pass

        # try:
        #     if question_score is not None:
        #         retrieval_lines.append(
        #             f"Question Similarity: {float(question_score):.4f}"
        #         )
        # except (TypeError, ValueError):
        #     pass

        # if retrieval_lines:

        #     lines.extend(
        #         [
        #             "",
        #             "Retrieval Metadata:",
        #             *retrieval_lines,
        #         ]
        #     )

        lines.append(f"[/TRUSTED_DOCUMENT_{index}]")
        return "\n".join(lines)

    # =========================================================
    # Build Knowledge Context
    # =========================================================

    def _build_knowledge_context(
        self,
        retrieved_documents,
    ) -> str:

        if not retrieved_documents:
            return "NO_TRUSTED_KNOWLEDGE_AVAILABLE"

        documents = []

        for index, item in enumerate(
            retrieved_documents[: self.MAX_DOCUMENTS],
            start=1,
        ):

            if not isinstance(
                item,
                dict,
            ):
                continue

            document = self._build_document(
                item=item,
                index=index,
            )

            if document:
                documents.append(document)

        if not documents:

            return "NO_TRUSTED_KNOWLEDGE_AVAILABLE"

        return ("\n\n" + "=" * 60 + "\n\n").join(documents)

    # =========================================================
    # Main Prompt
    # =========================================================

    def build(
        self,
        question,
        retrieved_documents,
        conversation_context="",
        target_language="hi",
    ):
        """
        Build final grounded RAG prompt optimized for speed, cross-lingual accuracy, and grounding.
        """
        farmer_question = self._limit(question, 400)

        conversation_context = self._limit(
            conversation_context,
            300,
        )

        knowledge_context = self._build_knowledge_context(retrieved_documents)

        if not conversation_context:
            conversation_context = "None"

        language_names = {
            "hi": "Hindi (Devanagari)",
            "hinglish": "Hinglish (Roman Hindi)",
            "en": "English",
            "gu": "Gujarati",
            "mr": "Marathi",
            "pa": "Punjabi",
            "ta": "Tamil",
            "te": "Telugu",
        }
        lang_display = language_names.get(str(target_language).lower(), "Hindi (Devanagari)")

        prompt = f"""You are Krishi AI, an evidence-grounded agricultural expert for Indian farmers.
Answer the farmer's question accurately using ONLY the provided TRUSTED KNOWLEDGE.

RULES:
1. Base your answer strictly on the provided TRUSTED KNOWLEDGE.
2. Match farmer spelling/phonetic variations appropriately (e.g., गेहु/गेहूं, सचाई/सिंचाई, soyabin/soybean, pili ptti/yellow leaf).
3. Do NOT invent chemical names, fertilizer names, pesticide names, or exact dosages not present in the knowledge.
4. TARGET LANGUAGE REQUIREMENT:
   The answer MUST be delivered 100% in {lang_display}.
   Translate all knowledge details, crop names, soil types, district names, and agricultural practices naturally into {lang_display}.
   Never output half-English half-Hindi text or untranslated English jargon.
5. If trusted knowledge is absent or empty, use your general AI parametric knowledge to answer the question directly, accurately, and completely in {lang_display}.

CONVERSATION CONTEXT:
{conversation_context}

TRUSTED KNOWLEDGE:
{knowledge_context}

FARMER QUESTION ({lang_display}):
{farmer_question}

ANSWER ({lang_display}):"""
        return prompt.strip()
