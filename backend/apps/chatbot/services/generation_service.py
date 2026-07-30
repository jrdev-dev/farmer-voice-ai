from typing import Any, Dict, List, Optional

from apps.chatbot.services.prompt_builder import PromptBuilder
from apps.chatbot.services.llm_service import LLMService
from apps.chatbot.services.answer_guard import AnswerGuard


class GenerationService:
    """
    Final grounded generation service.

    Pipeline
    --------
    Selected trusted evidence
        -> PromptBuilder
        -> Local LLM
        -> AnswerGuard
        -> Valid LLM answer
             OR
           trusted KB fallback
             OR
           safe fallback

    Safety guarantees
    -----------------
    1. Only selected evidence is used.
    2. LLM failure never crashes the chat pipeline.
    3. Empty LLM output is rejected.
    4. Unsupported LLM output is never returned directly.
    5. Trusted KB fallback is not rewritten by the LLM.
    6. No answer is generated when no usable evidence exists.
    """

    SAFE_FALLBACK_HI = (
        "मुझे उपलब्ध कृषि ज्ञान में इसका विश्वसनीय उत्तर नहीं मिला। "
        "कृपया कृषि विशेषज्ञ या कृषि विज्ञान केंद्र (KVK) से संपर्क करें।"
    )

    SAFE_FALLBACK_EN = (
        "I could not find a reliable answer in the available "
        "agricultural knowledge. Please contact an agriculture "
        "expert or Krishi Vigyan Kendra (KVK)."
    )

    def __init__(self):

        self.prompt_builder = PromptBuilder()

        self.llm = LLMService()

        self.answer_guard = AnswerGuard()

    # =========================================================
    # Main Generation
    # =========================================================

    def generate(
        self,
        question,
        retrieved_documents,
        conversation_context="",
    ) -> Dict[str, Any]:

        question = self._clean_text(question)

        retrieved_documents = (
            retrieved_documents
            if isinstance(
                retrieved_documents,
                list,
            )
            else []
        )

        # =====================================================
        # 1. No Trusted Evidence
        # =====================================================

        if not retrieved_documents:

            return self._build_result(
                answer=self.SAFE_FALLBACK_HI,
                raw_answer="",
                answer_valid=False,
                guard_reason=("No trusted evidence documents were provided."),
                fallback_used=True,
                fallback_source="safe_fallback",
                prompt="",
                evidence_count=0,
                generation_error=None,
            )

        # =====================================================
        # 2. Collect Trusted Evidence
        # =====================================================

        evidence_texts = self._collect_evidence(retrieved_documents)

        if not evidence_texts:

            return self._build_result(
                answer=self.SAFE_FALLBACK_HI,
                raw_answer="",
                answer_valid=False,
                guard_reason=(
                    "Retrieved documents contained no usable " "trusted evidence."
                ),
                fallback_used=True,
                fallback_source="safe_fallback",
                prompt="",
                evidence_count=0,
                generation_error=None,
            )

        # =====================================================
        # 3. Build Grounded Prompt
        # =====================================================

        try:

            prompt = self.prompt_builder.build(
                question=question,
                retrieved_documents=(retrieved_documents),
                conversation_context=(conversation_context),
            )

        except Exception as exc:

            print(
                "PROMPT BUILD ERROR:",
                str(exc),
            )

            trusted_answer = self._build_trusted_fallback(retrieved_documents)

            if trusted_answer:

                return self._build_result(
                    answer=trusted_answer,
                    raw_answer="",
                    answer_valid=False,
                    guard_reason=(
                        "Prompt construction failed; " "trusted KB fallback used."
                    ),
                    fallback_used=True,
                    fallback_source="knowledge_base",
                    prompt="",
                    evidence_count=len(evidence_texts),
                    generation_error=str(exc),
                )

            return self._build_result(
                answer=self.SAFE_FALLBACK_HI,
                raw_answer="",
                answer_valid=False,
                guard_reason=(
                    "Prompt construction failed and no "
                    "trusted fallback was available."
                ),
                fallback_used=True,
                fallback_source="safe_fallback",
                prompt="",
                evidence_count=len(evidence_texts),
                generation_error=str(exc),
            )

        # =====================================================
        # 4. Generate Using Local LLM
        # =====================================================

        raw_answer = ""

        generation_error = None

        try:

            raw_answer = self.llm.generate(prompt)

            raw_answer = self._clean_text(raw_answer)

        except Exception as exc:

            generation_error = str(exc)

            print(
                "LLM GENERATION ERROR:",
                generation_error,
            )

        # =====================================================
        # 5. LLM Failure / Empty Output
        # =====================================================

        if not raw_answer:

            trusted_answer = self._build_trusted_fallback(retrieved_documents)

            if trusted_answer:

                result = self._build_result(
                    answer=trusted_answer,
                    raw_answer="",
                    answer_valid=False,
                    guard_reason=(
                        "LLM returned no usable answer; " "trusted KB fallback used."
                    ),
                    fallback_used=True,
                    fallback_source="knowledge_base",
                    prompt=prompt,
                    evidence_count=len(evidence_texts),
                    generation_error=(generation_error),
                )

            else:

                result = self._build_result(
                    answer=self.SAFE_FALLBACK_HI,
                    raw_answer="",
                    answer_valid=False,
                    guard_reason=(
                        "LLM returned no usable answer and "
                        "no trusted KB fallback was available."
                    ),
                    fallback_used=True,
                    fallback_source="safe_fallback",
                    prompt=prompt,
                    evidence_count=len(evidence_texts),
                    generation_error=(generation_error),
                )

            self._debug(
                question=question,
                documents=retrieved_documents,
                evidence_texts=evidence_texts,
                result=result,
            )

            return result

        # =====================================================
        # 6. AnswerGuard Validation
        # =====================================================

        try:

            guard_result = self.answer_guard.validate(
                answer=raw_answer,
                evidence_texts=(evidence_texts),
            )

        except Exception as exc:

            print(
                "ANSWER GUARD ERROR:",
                str(exc),
            )

            guard_result = {
                "is_valid": False,
                "answer": (self.SAFE_FALLBACK_HI),
                "reason": ("AnswerGuard validation failed: " + str(exc)),
            }

        # =====================================================
        # 7. Normalize Guard Result
        # =====================================================

        if not isinstance(
            guard_result,
            dict,
        ):

            guard_result = {
                "is_valid": False,
                "answer": (self.SAFE_FALLBACK_HI),
                "reason": ("AnswerGuard returned an invalid result."),
            }

        guard_valid = bool(
            guard_result.get(
                "is_valid",
                False,
            )
        )

        guarded_answer = self._clean_text(
            guard_result.get(
                "answer",
                "",
            )
        )

        guard_reason = (
            self._clean_text(
                guard_result.get(
                    "reason",
                    "",
                )
            )
            or "No validation reason provided."
        )

        # =====================================================
        # 8. Decide Final Answer
        # =====================================================

        fallback_used = False

        fallback_source = None

        # -----------------------------------------------------
        # Valid grounded LLM answer
        # -----------------------------------------------------

        if guard_valid and guarded_answer:

            answer = guarded_answer

            answer_valid = True

        else:

            answer_valid = False

            # -------------------------------------------------
            # Unsupported LLM answer.
            #
            # Do NOT return raw LLM output.
            #
            # Use trusted selected KB evidence instead.
            # -------------------------------------------------

            trusted_answer = self._build_trusted_fallback(retrieved_documents)

            if trusted_answer:

                answer = trusted_answer

                fallback_used = True

                fallback_source = "knowledge_base"

            else:

                answer = guarded_answer or self.SAFE_FALLBACK_HI

                fallback_used = True

                fallback_source = "safe_fallback"

        # =====================================================
        # 9. Final Empty-Answer Protection & Hindi Terminology Sanitization
        # =====================================================

        answer = self._clean_text(answer)
        answer = self._sanitize_hindi_terminology(answer)

        if not answer:

            answer = self.SAFE_FALLBACK_HI

            answer_valid = False

            fallback_used = True

            fallback_source = "safe_fallback"

        # =====================================================
        # 10. Build Result
        # =====================================================

        result = self._build_result(
            answer=answer,
            raw_answer=raw_answer,
            answer_valid=answer_valid,
            guard_reason=guard_reason,
            fallback_used=fallback_used,
            fallback_source=fallback_source,
            prompt=prompt,
            evidence_count=len(evidence_texts),
            generation_error=(generation_error),
        )

        # =====================================================
        # 11. Debug
        # =====================================================

        self._debug(
            question=question,
            documents=retrieved_documents,
            evidence_texts=evidence_texts,
            result=result,
        )

        return result

    # =========================================================
    # Trusted Evidence Collection
    # =========================================================

    def _collect_evidence(
        self,
        retrieved_documents,
    ) -> List[str]:
        """
        Collect actual trusted Knowledge fields used by
        AnswerGuard.

        search_text is intentionally excluded because it may
        contain normalized/generated retrieval text rather than
        original factual evidence.
        """

        evidence_texts = []

        for item in retrieved_documents:

            if not isinstance(
                item,
                dict,
            ):
                continue

            knowledge = item.get("knowledge")

            if knowledge is None:
                continue

            fields = [
                getattr(
                    knowledge,
                    "crop",
                    "",
                ),
                getattr(
                    knowledge,
                    "category",
                    "",
                ),
                getattr(
                    knowledge,
                    "subcategory",
                    "",
                ),
                getattr(
                    knowledge,
                    "domain",
                    "",
                ),
                getattr(
                    knowledge,
                    "stage",
                    "",
                ),
                getattr(
                    knowledge,
                    "question",
                    "",
                ),
                getattr(
                    knowledge,
                    "answer",
                    "",
                ),
                getattr(
                    knowledge,
                    "keywords",
                    "",
                ),
            ]

            for value in fields:

                value = self._clean_text(value)

                if value:

                    evidence_texts.append(value)

        # Remove duplicates while preserving order.

        return list(dict.fromkeys(evidence_texts))

    # =========================================================
    # Trusted Knowledge Base Fallback
    # =========================================================

    def _build_trusted_fallback(
        self,
        retrieved_documents,
    ) -> Optional[str]:
        """
        Return the first usable answer from selected trusted
        Knowledge records.

        IMPORTANT
        ---------
        retrieved_documents must already come from
        EvidenceSelector.

        The LLM never rewrites this fallback.
        """

        if not retrieved_documents:

            return None

        for item in retrieved_documents:

            if not isinstance(
                item,
                dict,
            ):
                continue

            knowledge = item.get("knowledge")

            if knowledge is None:
                continue

            knowledge_answer = self._clean_text(
                getattr(
                    knowledge,
                    "answer",
                    "",
                )
            )

            if knowledge_answer:

                return knowledge_answer

        return None

    # =========================================================
    # Result Builder
    # =========================================================

    @staticmethod
    def _build_result(
        answer,
        raw_answer,
        answer_valid,
        guard_reason,
        fallback_used,
        fallback_source,
        prompt,
        evidence_count,
        generation_error,
    ) -> Dict[str, Any]:

        return {
            "answer": answer,
            "raw_answer": raw_answer,
            "answer_valid": bool(answer_valid),
            "guard_reason": (guard_reason),
            "fallback_used": bool(fallback_used),
            "fallback_source": (fallback_source),
            "prompt": prompt,
            "evidence_count": int(evidence_count),
            "generation_error": (generation_error),
        }

    # =========================================================
    # Text Helper
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

    # =========================================================
    # Debug
    # =========================================================

    def _debug(
        self,
        question,
        documents,
        evidence_texts,
        result,
    ):

        print("\n" + "=" * 80)

        print("GENERATION SERVICE")

        print("=" * 80)

        print(
            "Question        :",
            question,
        )

        print(
            "Documents       :",
            len(documents),
        )

        print(
            "Evidence Count  :",
            len(evidence_texts),
        )

        print("-" * 80)

        print(
            "Raw Answer      :",
            result.get(
                "raw_answer",
                "",
            ),
        )

        print(
            "Valid           :",
            result.get(
                "answer_valid",
                False,
            ),
        )

        print(
            "Reason          :",
            result.get(
                "guard_reason",
                "",
            ),
        )

        print(
            "Fallback Used   :",
            result.get(
                "fallback_used",
                False,
            ),
        )

        print(
            "Fallback Source :",
            result.get(
                "fallback_source",
            ),
        )

        print(
            "Generation Error:",
            result.get(
                "generation_error",
            ),
        )

        print(
            "Final Answer    :",
            result.get(
                "answer",
                "",
            ),
        )

        print("=" * 80 + "\n")

    @staticmethod
    def _sanitize_hindi_terminology(text: str) -> str:
        """
        Universal Softcoded Agricultural Language Converter.
        Converts English agricultural phrases & transliterated words in Hindi responses
        into pure, natural Devanagari Hindi agricultural terminology.
        """
        if not text:
            return ""

        import re

        universal_phrase_mappings = [
            # Soil Types & Attributes
            (r"friable\s+loam\s+(?:and\s+)?well-drained\s+fertile\s+soil", "अच्छे जल निकास वाली भुरभुरी दोमट मिट्टी"),
            (r"friable\s+loamy?\s+soil", "भुरभुरी दोमट मिट्टी"),
            (r"friable\s+loam", "भुरभुरी दोमट मिट्टी"),
            (r"sandy\s+loamy?\s+soil", "बलुई दोमट मिट्टी"),
            (r"sandy\s+loam", "बलुई दोमट मिट्टी"),
            (r"clay\s+loamy?\s+soil", "चिकनी दोमट मिट्टी"),
            (r"clay\s+loam", "चिकनी दोमट मिट्टी"),
            (r"silt\s+loamy?\s+soil", "गाद दोमट मिट्टी"),
            (r"loamy?\s+soil", "दोमट मिट्टी"),
            (r"black\s+soil", "काली मिट्टी"),
            (r"red\s+soil", "लाल मिट्टी"),
            (r"alluvial\s+soil", "जलोढ़ मिट्टी"),
            (r"well[- ]drained\s+soil", "अच्छे जल निकास वाली मिट्टी"),
            (r"well[- ]drained", "अच्छे जल निकास वाली"),
            (r"rich\s+in\s+organic\s+matter", "जीवांश (कार्बनिक पदार्थ) से भरपूर"),

            # Transliteration Fixes
            (r"फ़्रिबल\s+लोम\s+और\s+सामूचा\s+जड़ेवान\s+रुचिर\s+मिट्टी", "अच्छे जल निकास वाली भुरभुरी दोमट मिट्टी"),
            (r"फ़्रिबल\s+लोम", "भुरभुरी दोमट मिट्टी"),
            (r"फ्रीबल\s+लोम", "भुरभुरी दोमट मिट्टी"),
            (r"फ्रिबल\s+लोम", "भुरभुरी दोमट मिट्टी"),
            (r"फ़्रिबल", "भुरभुरी"),
            (r"सामूचा\s+जड़ेवान", "अच्छे जल निकास वाली"),
            (r"रुचिर\s+मिट्टी", "उपजाऊ दोमट मिट्टी"),
            (r"सेंडी\s+लोम", "बलुई दोमट मिट्टी"),
            (r"सैंडी\s+लोम", "बलुई दोमट मिट्टी"),
            (r"क्ले\s+लोम", "चिकनी दोमट मिट्टी"),

            # Agronomic Practices & Terms
            (r"sowing\s+time", "बुवाई का समय"),
            (r"sowing\s+season", "बुवाई का मौसम"),
            (r"seed\s+rate", "बीज दर"),
            (r"seed\s+treatment", "बीज उपचार"),
            (r"irrigation\s+schedule", "सिंचाई का समय"),
            (r"pest\s+management", "कीट प्रबंधन"),
            (r"disease\s+control", "रोग नियंत्रण"),
            (r"weed\s+control", "खरपतवार नियंत्रण"),
            (r"organic\s+manure", "जैविक खाद"),
            (r"vermicompost", "वर्मीकंपोस्ट"),
            (r"harvesting\s+time", "कटाई का समय"),
        ]

        sanitized = text
        for pattern, replacement in universal_phrase_mappings:
            sanitized = re.sub(pattern, replacement, sanitized, flags=re.IGNORECASE)

        return sanitized
