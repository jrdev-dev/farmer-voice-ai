import sys

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from .memory_service import MemoryService
from .context_builder import ContextBuilder
from .generation_service import GenerationService
from .intent_service import IntentService
from .language_service import LanguageService
from .confidence_service import ConfidenceService
from .source_builder import SourceBuilder
from .response_validator import ResponseValidator
from .response_formatter import ResponseFormatter

from apps.knowledge_base.services.retriever_service import RetrieverService
from apps.knowledge_base.services.evidence_selector import EvidenceSelector
from apps.knowledge_base.services.relevance_service import RelevanceService


class ChatService:
    """
    Main Farmer Voice AI orchestration service.

    Pipeline
    --------
    User
        -> Language Detection
        -> Conversation Memory
        -> Intent Detection
        -> Context Resolution
        -> Hybrid Retrieval
        -> Relevance Validation
        -> Evidence Selection
        -> Grounded Generation
        -> Answer Guard
        -> Confidence Calculation
        -> Source Building
        -> Response Formatting
        -> Response Validation
        -> Public Response

    Safety
    ------
    - No relevant evidence -> LLM is not called.
    - Crop/topic mismatch -> LLM is not called.
    - Only selected evidence reaches generation.
    - Unsupported LLM output is rejected.
    - Trusted KB fallback is allowed.
    - Generic fallback has zero confidence.
    - Generic fallback exposes no supporting sources.
    """

    def __init__(self):

        # =====================================================
        # Retrieval
        # =====================================================

        self.retriever = RetrieverService.get_instance()
        self.relevance = RelevanceService()
        self.evidence_selector = EvidenceSelector()

        # =====================================================
        # Generation
        # =====================================================

        self.generator = GenerationService()

        # =====================================================
        # Conversation
        # =====================================================

        self.memory = MemoryService()
        self.context = ContextBuilder()

        # =====================================================
        # NLP
        # =====================================================

        self.intent = IntentService()
        self.language_service = LanguageService()

        # =====================================================
        # Response Pipeline
        # =====================================================

        self.confidence_service = ConfidenceService()
        self.source_builder = SourceBuilder()
        self.response_formatter = ResponseFormatter()
        self.response_validator = ResponseValidator()

    # =========================================================
    # Main Chat
    # =========================================================

    def chat(
        self,
        user,
        message: str,
        language: str = None,
    ):

        # =====================================================
        # 1. Clean Input
        # =====================================================

        message = self._clean_text(message)

        if not message:

            language = self._normalize_language(language)

            response = self.response_formatter.format_no_answer(
                conversation_id=None,
                language=language,
                match_type="none",
                reason="Empty user message.",
            )

            response["message_id"] = None

            return self._finalize(
                response,
                intent="unknown",
            )

        # =====================================================
        # 2. Conversation
        # =====================================================

        try:

            conversation = self.memory.get_or_create_conversation(user)

        except Exception as exc:

            self._debug_error(
                "CONVERSATION ERROR",
                exc,
            )

            language = self._normalize_language(language)

            response = self.response_formatter.format_error(
                message=self._fallback_answer(language),
                language=language,
                error_code="conversation_error",
            )

            response["message_id"] = None

            return self._finalize(
                response,
                intent="unknown",
            )

        # =====================================================
        # 3. Language Detection
        # =====================================================

        detected_language = None

        try:

            detected_language = self.language_service.detect(message)

        except Exception as exc:

            self._debug_error(
                "LANGUAGE DETECTION ERROR",
                exc,
            )

        language = self._resolve_language(
            requested=language,
            detected=detected_language,
        )

        self._debug_language(
            message,
            detected_language,
            language,
        )

        # =====================================================
        # 4. Save User Message
        # =====================================================

        try:

            self.memory.save_user_message(
                conversation,
                message,
            )

        except Exception as exc:

            self._debug_error(
                "USER MESSAGE SAVE ERROR",
                exc,
            )

        # =====================================================
        # 5. Intent Detection
        # =====================================================

        try:

            intent_type = self.intent.detect(message)

        except Exception as exc:

            self._debug_error(
                "INTENT DETECTION ERROR",
                exc,
            )

            intent_type = "question"

        intent_type = self._clean_text(intent_type).lower() or "question"

        self._debug_intent(
            conversation,
            message,
            intent_type,
        )

        # =====================================================
        # 6. Greeting
        # =====================================================

        if intent_type == "greeting":

            answer = self._greeting(language)

            assistant_message = self._save_assistant(
                conversation,
                answer,
            )

            response = self.response_formatter.format_success(
                answer=answer,
                confidence=100,
                sources=[],
                conversation_id=conversation.id,
                language=language,
                match_type="greeting",
                fallback_used=False,
                fallback_source=None,
            )

            response["intent"] = intent_type

            response["message_id"] = assistant_message.id if assistant_message else None

            return self._finalize(
                response,
                intent=intent_type,
            )

        # =====================================================
        # 7. Context Statement
        # =====================================================

        if intent_type == "context":

            answer = self._context_acknowledgement(language)

            assistant_message = self._save_assistant(
                conversation,
                answer,
            )

            print("\n" + "=" * 80)
            print("CONTEXT MESSAGE")
            print("=" * 80)
            print("Stored Context :", message)
            print("Retriever      : SKIPPED")
            print("Relevance      : SKIPPED")
            print("LLM            : SKIPPED")
            print("=" * 80 + "\n")

            response = self.response_formatter.format_success(
                answer=answer,
                confidence=100,
                sources=[],
                conversation_id=conversation.id,
                language=language,
                match_type="context",
                fallback_used=False,
                fallback_source=None,
            )

            response["intent"] = intent_type

            response["message_id"] = assistant_message.id if assistant_message else None

            return self._finalize(
                response,
                intent=intent_type,
            )

        # =====================================================
        # 8. Resolve Conversation Context
        # =====================================================

        original_question = message

        try:

            enriched_question = self.context.build_question(
                conversation,
                message,
            )

        except Exception as exc:

            self._debug_error(
                "CONTEXT BUILDER ERROR",
                exc,
            )

            enriched_question = original_question

        enriched_question = self._clean_text(enriched_question) or original_question

        self._debug_chat_request(
            conversation,
            original_question,
            enriched_question,
        )

        # =====================================================
        # 9. Hybrid Retrieval
        # =====================================================

        try:

            ranked_results = self.retriever.retrieve(
                question=enriched_question,
                language=language,
            )

        except Exception as exc:

            self._debug_error(
                "RETRIEVAL ERROR",
                exc,
            )

            return self._knowledge_failure(
                conversation=conversation,
                language=language,
                intent=intent_type,
                match_type="none",
                reason="Knowledge retrieval failed.",
            )

        # =====================================================
        # 10. No Retrieval Results
        # =====================================================

        if not ranked_results:

            print("\n" + "=" * 80)
            print("RETRIEVAL FAILED")
            print("=" * 80)

            print(
                "Question :",
                enriched_question,
            )

            print("Reason   : No retrieval results")

            print("LLM      : SKIPPED")

            print("=" * 80 + "\n")

            return self._knowledge_failure(
                conversation=conversation,
                language=language,
                intent=intent_type,
                match_type="none",
                reason="No retrieval results.",
            )

        # =====================================================
        # 11. Validate Best Candidate
        # =====================================================

        best = ranked_results[0]

        if not isinstance(
            best,
            dict,
        ):

            return self._knowledge_failure(
                conversation=conversation,
                language=language,
                intent=intent_type,
                match_type="none",
                reason="Invalid retrieval result.",
            )

        knowledge = best.get("knowledge")

        if knowledge is None:

            return self._knowledge_failure(
                conversation=conversation,
                language=language,
                intent=intent_type,
                match_type="none",
                reason=("Retrieval result contains " "no knowledge."),
            )

        # =====================================================
        # 12. Relevance Guard
        # =====================================================

        try:

            relevance_result = self.relevance.evaluate(
                best_result=best,
                question=enriched_question,
            )

        except TypeError:

            # Compatibility with older
            # RelevanceService signature.

            try:

                relevance_result = self.relevance.evaluate(best_result=best)

            except Exception as exc:

                self._debug_error(
                    "RELEVANCE ERROR",
                    exc,
                )

                return self._knowledge_failure(
                    conversation=conversation,
                    language=language,
                    intent=intent_type,
                    match_type="irrelevant",
                    reason=("Relevance validation failed."),
                )

        except Exception as exc:

            self._debug_error(
                "RELEVANCE ERROR",
                exc,
            )

            return self._knowledge_failure(
                conversation=conversation,
                language=language,
                intent=intent_type,
                match_type="irrelevant",
                reason=("Relevance validation failed."),
            )

        if not isinstance(
            relevance_result,
            dict,
        ):

            relevance_result = {
                "is_relevant": False,
                "reason": ("Invalid relevance result."),
            }

        self._debug_relevance(
            knowledge,
            enriched_question,
            relevance_result,
        )

        # =====================================================
        # 13. Block Irrelevant Retrieval
        # =====================================================

        if not relevance_result.get(
            "is_relevant",
            False,
        ):

            print("\n" + "=" * 80)
            print("RAG GENERATION BLOCKED")
            print("=" * 80)

            print(
                "Original Question :",
                original_question,
            )

            print(
                "Context Question  :",
                enriched_question,
            )

            print(
                "Knowledge Crop    :",
                getattr(
                    knowledge,
                    "crop",
                    "",
                ),
            )

            print(
                "Reason            :",
                relevance_result.get(
                    "reason",
                    "",
                ),
            )

            print("LLM               : SKIPPED")

            print("=" * 80 + "\n")

            return self._knowledge_failure(
                conversation=conversation,
                language=language,
                intent=intent_type,
                match_type="irrelevant",
                reason=relevance_result.get(
                    "reason",
                    "Insufficient relevance.",
                ),
            )

        # =====================================================
        # 14. Evidence Selection
        # =====================================================

        try:

            top_documents = self.evidence_selector.select(ranked_results)

        except Exception as exc:

            self._debug_error(
                "EVIDENCE SELECTION ERROR",
                exc,
            )

            top_documents = []

        if not top_documents:

            return self._knowledge_failure(
                conversation=conversation,
                language=language,
                intent=intent_type,
                match_type="irrelevant",
                reason=("No trustworthy supporting evidence."),
            )

        self._debug_evidence(top_documents)

        # =====================================================
        # 15. Grounded Generation
        # =====================================================

        try:

            generation_result = self.generator.generate(
                question=original_question,
                retrieved_documents=top_documents,
                conversation_context=enriched_question,
                target_language=language,
            )

        except Exception as exc:

            self._debug_error(
                "GENERATION ERROR",
                exc,
            )

            # LLM failure does not necessarily mean
            # knowledge failure.
            #
            # We may safely return the highest-ranked
            # trusted KB answer.

            trusted_answer = self._trusted_knowledge_answer(top_documents)

            if trusted_answer:
                import re
                if language in ("hi", "hinglish") and re.search(r'[a-zA-Z]{2,}', trusted_answer):
                    translated = self.generator._translate_to_target_language(trusted_answer, language)
                    if translated:
                        trusted_answer = translated

                generation_result = {
                    "answer": trusted_answer,
                    "answer_valid": False,
                    "guard_reason": ("LLM generation unavailable."),
                    "fallback_used": True,
                    "fallback_source": ("knowledge_base"),
                }

            else:

                return self._knowledge_failure(
                    conversation=conversation,
                    language=language,
                    intent=intent_type,
                    match_type="fallback",
                    reason=("Grounded generation failed."),
                )

        if not isinstance(
            generation_result,
            dict,
        ):

            return self._knowledge_failure(
                conversation=conversation,
                language=language,
                intent=intent_type,
                match_type="fallback",
                reason=("Invalid generation result."),
            )

        # =====================================================
        # 16. Generation Result
        # =====================================================

        answer = self._clean_text(
            generation_result.get(
                "answer",
                "",
            )
        )

        answer_valid = bool(
            generation_result.get(
                "answer_valid",
                False,
            )
        )

        fallback_used = bool(
            generation_result.get(
                "fallback_used",
                False,
            )
        )

        fallback_source = (
            self._clean_text(
                generation_result.get(
                    "fallback_source",
                    "",
                )
            )
            or None
        )

        if not answer:

            return self._knowledge_failure(
                conversation=conversation,
                language=language,
                intent=intent_type,
                match_type="fallback",
                reason=("Generation produced " "an empty answer."),
            )

        # =====================================================
        # 17. Generation Safety
        # =====================================================

        if not answer_valid and not fallback_used:

            return self._knowledge_failure(
                conversation=conversation,
                language=language,
                intent=intent_type,
                match_type="fallback",
                reason=generation_result.get(
                    "guard_reason",
                    ("Generated answer failed " "validation."),
                ),
            )

        trusted_kb_fallback = fallback_source == "knowledge_base"

        safe_fallback = fallback_source == "safe_fallback"

        # =====================================================
        # 18. Confidence
        # =====================================================

        try:

            confidence_result = self.confidence_service.evaluate(
                best_result=best,
                relevance_result=relevance_result,
                answer_valid=(answer_valid or trusted_kb_fallback),
                fallback_used=fallback_used,
                supporting_documents=(len(top_documents)),
            )

        except Exception as exc:

            self._debug_error(
                "CONFIDENCE SERVICE ERROR",
                exc,
            )

            confidence_result = {
                "percentage": 0,
                "label": "very_low",
                "agreement": {},
                "adjustments": [],
            }

        if not isinstance(
            confidence_result,
            dict,
        ):

            confidence_result = {
                "percentage": 0,
                "label": "very_low",
                "agreement": {},
                "adjustments": [],
            }

        confidence = confidence_result.get(
            "percentage",
            0,
        )

        confidence_label = (
            self._clean_text(
                confidence_result.get(
                    "label",
                    "",
                )
            )
            or "very_low"
        )

        # Generic safe fallback must never
        # have evidence-backed confidence.

        if safe_fallback:

            confidence = 0
            confidence_label = "very_low"

        # =====================================================
        # 19. Trusted Sources
        # =====================================================

        try:

            sources = self.source_builder.build_public(
                retrieved_documents=top_documents,
                limit=3,
            )

        except Exception as exc:

            self._debug_error(
                "SOURCE BUILDER ERROR",
                exc,
            )

            sources = []

        if not isinstance(
            sources,
            list,
        ):

            sources = []

        # Generic fallback must not expose
        # documents as supporting evidence.

        if safe_fallback:
            sources = []

        # =====================================================
        # 20. Save Assistant Response
        # =====================================================

        assistant_message = self._save_assistant(
            conversation,
            answer,
        )

        # =====================================================
        # 21. Debug Final Result
        # =====================================================

        self._debug_final(
            knowledge=knowledge,
            best=best,
            confidence=confidence,
            confidence_label=confidence_label,
            confidence_result=confidence_result,
            answer_valid=answer_valid,
            fallback_used=fallback_used,
            fallback_source=fallback_source,
            sources=sources,
            answer=answer,
        )

        # =====================================================
        # 22. Determine Public Success
        # =====================================================

        successful_answer = answer_valid or trusted_kb_fallback

        if safe_fallback:
            successful_answer = False

        if trusted_kb_fallback:

            match_type = "fallback"

        elif answer_valid:

            match_type = "hybrid"

        else:

            match_type = "fallback"

        # =====================================================
        # 23. Format Response
        # =====================================================

        response = self.response_formatter.format(
            success=successful_answer,
            answer=answer,
            confidence=confidence,
            sources=sources,
            conversation_id=conversation.id,
            language=language,
            match_type=match_type,
            fallback_used=fallback_used,
            fallback_source=fallback_source,
        )

        response["confidence_label"] = confidence_label

        response["intent"] = intent_type

        response["message_id"] = assistant_message.id if assistant_message else None

        # =====================================================
        # 23.1 TTS Audio Synthesis for Speaker Playback
        # =====================================================
        if answer:
            try:
                from apps.speech.services.text_to_speech_service import TextToSpeechService
                tts = TextToSpeechService()
                target_lang = response.get("language") or language or "hi"
                tts_result = tts.synthesize(text=answer, language=target_lang)
                if tts_result.get("audio_url"):
                    response["audio_url"] = tts_result.get("audio_url")
                    response["voice"] = tts_result.get("voice")
            except Exception as tts_exc:
                logger.warning("ChatService TTS synthesis skipped: %s", tts_exc)

        # =====================================================
        # 24. Final Validation
        # =====================================================

        return self._finalize(
            response,
            intent=intent_type,
        )

    # =========================================================
    # Trusted Knowledge Fallback
    # =========================================================

    @staticmethod
    def _trusted_knowledge_answer(
        documents,
    ):

        if not documents:
            return None

        for item in documents:

            if not isinstance(
                item,
                dict,
            ):
                continue

            knowledge = item.get("knowledge")

            if knowledge is None:
                continue

            answer = getattr(
                knowledge,
                "answer",
                None,
            )

            if not answer:
                continue

            answer = " ".join(str(answer).strip().split())

            if answer:
                return answer

        return None

    # =========================================================
    # Knowledge Failure
    # =========================================================

    def _knowledge_failure(
        self,
        conversation,
        language,
        intent,
        match_type,
        reason=None,
    ):

        language = self._normalize_language(language)

        answer = self._fallback_answer(language)

        assistant_message = self._save_assistant(
            conversation,
            answer,
        )

        response = self.response_formatter.format_no_answer(
            conversation_id=getattr(
                conversation,
                "id",
                None,
            ),
            language=language,
            match_type=match_type,
            reason=reason,
        )

        response["intent"] = intent

        response["message_id"] = assistant_message.id if assistant_message else None

        return self._finalize(
            response,
            intent=intent,
        )

    # =========================================================
    # Final Response Validation
    # =========================================================

    def _finalize(
        self,
        response,
        intent=None,
    ):

        if not isinstance(
            response,
            dict,
        ):

            response = self.response_formatter.format_error(
                error_code="invalid_response",
            )

        if intent and not response.get("intent"):

            response["intent"] = intent

        try:

            validation_result = self.response_validator.validate(response)

            if isinstance(
                validation_result,
                dict,
            ):

                print("\n" + "=" * 80)

                print("RESPONSE VALIDATION")

                print("=" * 80)

                print(
                    "Valid    :",
                    validation_result.get(
                        "is_valid",
                        False,
                    ),
                )

                print(
                    "Errors   :",
                    validation_result.get(
                        "errors",
                        [],
                    ),
                )

                print(
                    "Warnings :",
                    validation_result.get(
                        "warnings",
                        [],
                    ),
                )

                print("=" * 80 + "\n")

                validated_response = validation_result.get("response")

                if isinstance(
                    validated_response,
                    dict,
                ):

                    return validated_response

        except Exception as exc:

            self._debug_error(
                "RESPONSE VALIDATION ERROR",
                exc,
            )

        # -----------------------------------------------------
        # Compatibility fallback
        # -----------------------------------------------------

        try:

            return self.response_validator.sanitize(response)

        except Exception:

            return response

    # =========================================================
    # Save Assistant
    # =========================================================

    def _save_assistant(
        self,
        conversation,
        answer,
    ):
        """
        Save assistant response and return the
        created Message object.
        """

        if conversation is None:
            return None

        answer = self._clean_text(answer)

        if not answer:
            return None

        try:

            return self.memory.save_assistant_message(
                conversation,
                answer,
            )

        except Exception as exc:

            self._debug_error(
                "ASSISTANT MESSAGE SAVE ERROR",
                exc,
            )

            return None

    # =========================================================
    # Farmer-Facing Fallback
    # =========================================================

    def _fallback_answer(
        self,
        language=None,
    ):

        return self.response_formatter.get_fallback_message(language)

    # =========================================================
    # Greeting
    # =========================================================

    @staticmethod
    def _greeting(
        language,
    ):

        messages = {
            "hi": (
                "नमस्ते! मैं आपका कृषि सहायक हूँ। "
                "मैं आपकी खेती से जुड़ी जानकारी में "
                "मदद कर सकता हूँ।"
            ),
            "en": ("Hello! I am your agriculture assistant. " "How can I help you?"),
            "hinglish": (
                "Namaste! Main aapka agriculture "
                "assistant hoon. Aap farming se juda "
                "sawal pooch sakte hain."
            ),
            "gu": (
                "નમસ્તે! હું તમારો કૃષિ સહાયક છું. "
                "હું ખેતી સંબંધિત માહિતીમાં તમારી "
                "મદદ કરી શકું છું."
            ),
            "mr": (
                "नमस्कार! मी तुमचा कृषी सहाय्यक आहे. "
                "शेतीशी संबंधित माहितीसाठी मी तुम्हाला "
                "मदत करू शकतो."
            ),
            "pa": (
                "ਸਤ ਸ੍ਰੀ ਅਕਾਲ! ਮੈਂ ਤੁਹਾਡਾ ਖੇਤੀਬਾੜੀ "
                "ਸਹਾਇਕ ਹਾਂ। ਤੁਸੀਂ ਖੇਤੀ ਨਾਲ ਸੰਬੰਧਿਤ "
                "ਸਵਾਲ ਪੁੱਛ ਸਕਦੇ ਹੋ।"
            ),
            "ta": (
                "வணக்கம்! நான் உங்கள் வேளாண் உதவியாளர். "
                "விவசாயம் தொடர்பான கேள்விகளில் நான் "
                "உதவ முடியும்."
            ),
            "te": (
                "నమస్కారం! నేను మీ వ్యవసాయ సహాయకుడిని. "
                "వ్యవసాయానికి సంబంధించిన ప్రశ్నల్లో "
                "నేను సహాయం చేయగలను."
            ),
        }

        return messages.get(
            language,
            messages["hi"],
        )

    # =========================================================
    # Context Acknowledgement
    # =========================================================

    @staticmethod
    def _context_acknowledgement(
        language,
    ):

        messages = {
            "hi": (
                "ठीक है, मैंने यह जानकारी ध्यान में "
                "रख ली है। अब आप इससे जुड़ा सवाल "
                "पूछ सकते हैं।"
            ),
            "en": (
                "Okay, I have noted this information. "
                "You can now ask a question about it."
            ),
            "hinglish": (
                "Theek hai, maine ye information "
                "dhyan mein rakh li hai. Ab aap isse "
                "juda sawal pooch sakte hain."
            ),
            "gu": (
                "ઠીક છે, મેં આ માહિતી ધ્યાનમાં રાખી છે. "
                "હવે તમે તેના વિશે પ્રશ્ન પૂછી શકો છો."
            ),
            "mr": (
                "ठीक आहे, मी ही माहिती लक्षात ठेवली आहे. "
                "आता तुम्ही याबद्दल प्रश्न विचारू शकता."
            ),
            "pa": (
                "ਠੀਕ ਹੈ, ਮੈਂ ਇਹ ਜਾਣਕਾਰੀ ਧਿਆਨ ਵਿੱਚ "
                "ਰੱਖ ਲਈ ਹੈ। ਹੁਣ ਤੁਸੀਂ ਇਸ ਬਾਰੇ "
                "ਸਵਾਲ ਪੁੱਛ ਸਕਦੇ ਹੋ।"
            ),
            "ta": (
                "சரி, இந்த தகவலை நான் கருத்தில் "
                "கொண்டுள்ளேன். இப்போது இதைப் பற்றி "
                "கேள்வி கேட்கலாம்."
            ),
            "te": (
                "సరే, ఈ సమాచారాన్ని నేను గుర్తుంచుకున్నాను. "
                "ఇప్పుడు దీనికి సంబంధించిన ప్రశ్నను "
                "అడగవచ్చు."
            ),
        }

        return messages.get(
            language,
            messages["hi"],
        )

    # =========================================================
    # Language Resolution
    # =========================================================

    def _resolve_language(
        self,
        requested=None,
        detected=None,
    ):

        requested = self._clean_text(requested).lower()

        detected = self._clean_text(detected).lower()

        selected = (
            detected
            if detected in ("en", "hinglish", "gu", "mr", "pa", "ta", "te")
            else (requested or detected or "hi")
        )

        return self._normalize_language(selected)

    def _normalize_language(
        self,
        language,
    ):

        return self.response_formatter._normalize_language(language)

    # =========================================================
    # Debug
    # =========================================================

    @staticmethod
    def _debug_error(
        title,
        error,
    ):

        print("\n" + "=" * 80)

        print(title)

        print("=" * 80)

        print(
            "Error:",
            str(error),
        )

        print("=" * 80 + "\n")

    @staticmethod
    def _debug_language(
        message,
        detected,
        final,
    ):

        print("\n" + "=" * 80)

        print("LANGUAGE DETECTION")

        print("=" * 80)

        print(
            "Message           :",
            message,
        )

        print(
            "Detected Language :",
            detected,
        )

        print(
            "Final Language    :",
            final,
        )

        print("=" * 80)

    @staticmethod
    def _debug_intent(
        conversation,
        message,
        intent,
    ):

        print("\n" + "=" * 80)

        print("INTENT DETECTION")

        print("=" * 80)

        print(
            "Conversation ID :",
            getattr(
                conversation,
                "id",
                None,
            ),
        )

        print(
            "Message         :",
            message,
        )

        print(
            "Intent          :",
            intent,
        )

        print("=" * 80)

    @staticmethod
    def _debug_chat_request(
        conversation,
        original,
        enriched,
    ):

        print("\n" + "=" * 80)

        print("CHAT REQUEST")

        print("=" * 80)

        print(
            "Conversation ID  :",
            getattr(
                conversation,
                "id",
                None,
            ),
        )

        print(
            "Original Question:",
            original,
        )

        print(
            "Context Question :",
            enriched,
        )

        print("=" * 80)

    @staticmethod
    def _debug_relevance(
        knowledge,
        question,
        result,
    ):

        print("\n" + "=" * 80)

        print("RELEVANCE GUARD")

        print("=" * 80)

        print(
            "Best Knowledge  :",
            getattr(
                knowledge,
                "question",
                "",
            ),
        )

        print(
            "Knowledge Crop  :",
            getattr(
                knowledge,
                "crop",
                "",
            ),
        )

        print(
            "Question        :",
            question,
        )

        print(
            "Relevant        :",
            result.get(
                "is_relevant",
                False,
            ),
        )

        print(
            "Reason          :",
            result.get(
                "reason",
                "",
            ),
        )

        print(
            "Evidence Count  :",
            result.get(
                "evidence_count",
                0,
            ),
        )

        print(
            "Evidence        :",
            result.get(
                "evidence",
                [],
            ),
        )

        print(
            "Raw Scores      :",
            result.get(
                "scores",
                {},
            ),
        )

        print(
            "Crop Validation :",
            result.get(
                "crop_validation",
                {},
            ),
        )

        print("=" * 80 + "\n")

    def _debug_evidence(
        self,
        documents,
    ):

        print("\n" + "=" * 80)

        print("EVIDENCE SELECTION")

        print("=" * 80)

        for index, item in enumerate(
            documents,
            start=1,
        ):

            if not isinstance(
                item,
                dict,
            ):
                continue

            knowledge = item.get("knowledge")

            print(
                f"{index}.",
                getattr(
                    knowledge,
                    "question",
                    "",
                ),
            )

            print(
                "   Crop     :",
                getattr(
                    knowledge,
                    "crop",
                    "",
                ),
            )

            print(
                "   Hybrid   :",
                round(
                    self._safe_float(
                        item.get(
                            "score",
                            0,
                        )
                    ),
                    4,
                ),
            )

            print(
                "   Question :",
                round(
                    self._safe_float(
                        item.get(
                            "question_raw_score",
                            item.get(
                                "question_score",
                                0,
                            ),
                        )
                    ),
                    4,
                ),
            )

            print(
                "   Semantic :",
                round(
                    self._safe_float(
                        item.get(
                            "semantic_raw_score",
                            0,
                        )
                    ),
                    4,
                ),
            )

        print("=" * 80 + "\n")

    def _debug_final(
        self,
        knowledge,
        best,
        confidence,
        confidence_label,
        confidence_result,
        answer_valid,
        fallback_used,
        fallback_source,
        sources,
        answer,
    ):

        print("\n" + "=" * 80)

        print("FINAL RAG RESULT")

        print("=" * 80)

        print(
            "Best Knowledge :",
            getattr(
                knowledge,
                "question",
                "",
            ),
        )

        print(
            "Knowledge Crop :",
            getattr(
                knowledge,
                "crop",
                "",
            ),
        )

        print(
            "Hybrid Score   :",
            round(
                self._safe_float(
                    best.get(
                        "score",
                        0,
                    )
                ),
                4,
            ),
        )

        print(
            "Confidence     :",
            confidence,
        )

        print(
            "Confidence Type:",
            confidence_label,
        )

        print(
            "Agreement      :",
            confidence_result.get(
                "agreement",
                {},
            ),
        )

        print(
            "Adjustments    :",
            confidence_result.get(
                "adjustments",
                [],
            ),
        )

        print(
            "Answer Valid   :",
            answer_valid,
        )

        print(
            "Fallback Used  :",
            fallback_used,
        )

        print(
            "Fallback Source:",
            fallback_source,
        )

        print(
            "Sources        :",
            len(sources),
        )

        print("\nGenerated Answer:")

        print(answer)

        print("=" * 80 + "\n")

    # =========================================================
    # Generic Helpers
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
    def _safe_float(
        value,
        default=0.0,
    ):

        try:

            return float(value)

        except (
            TypeError,
            ValueError,
        ):

            return float(default)
