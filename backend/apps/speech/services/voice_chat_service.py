import logging

from apps.chatbot.services.chat_service import ChatService
from apps.chatbot.services.language_service import LanguageService

from .speech_to_text_service import SpeechToTextService
from .text_to_speech_service import TextToSpeechService

logger = logging.getLogger(__name__)


class VoiceChatService:
    """
    Orchestrates the complete Farmer Voice AI voice pipeline.

    Flow
    ----
    Audio
        -> Speech To Text
        -> Transcript
        -> Language Resolution
        -> ChatService
        -> Knowledge Retrieval / RAG
        -> Grounded Answer
        -> Text To Speech
        -> Final Voice Response

    Important:
    Speech transcription is input processing only.
    Agricultural answers still come through ChatService and
    its trusted knowledge/retrieval pipeline.
    """

    SUPPORTED_LANGUAGES = {
        "hi",
        "en",
        "hinglish",
        "gu",
        "mr",
        "pa",
        "ta",
        "te",
    }

    LANGUAGE_ALIASES = {
        "hindi": "hi",
        "english": "en",
        "gujarati": "gu",
        "marathi": "mr",
        "punjabi": "pa",
        "tamil": "ta",
        "telugu": "te",
        "hinglish": "hinglish",
        # Common STT / locale variants
        "hi-in": "hi",
        "en-in": "en",
        "en-us": "en",
        "gu-in": "gu",
        "mr-in": "mr",
        "pa-in": "pa",
        "ta-in": "ta",
        "te-in": "te",
    }

    SPEECH_NOT_UNDERSTOOD = {
        "hi": ("ऑडियो से स्पष्ट आवाज़ समझ नहीं आई। " "कृपया दोबारा बोलें।"),
        "hinglish": (
            "Audio se awaaz clearly samajh nahi aayi. " "Kripya dobara boliye."
        ),
        "en": ("I could not understand the audio clearly. " "Please speak again."),
        "gu": ("ઓડિયોમાં અવાજ સ્પષ્ટ રીતે સમજાયો નથી. " "કૃપા કરીને ફરી બોલો."),
        "mr": ("ऑडिओमधील आवाज स्पष्टपणे समजला नाही. " "कृपया पुन्हा बोला."),
        "pa": ("ਆਡੀਓ ਵਿੱਚ ਆਵਾਜ਼ ਸਪਸ਼ਟ ਤੌਰ ਤੇ ਸਮਝ ਨਹੀਂ ਆਈ। " "ਕਿਰਪਾ ਕਰਕੇ ਦੁਬਾਰਾ ਬੋਲੋ।"),
        "ta": (
            "ஆடியோவில் குரல் தெளிவாக புரியவில்லை. " "தயவுசெய்து மீண்டும் பேசுங்கள்."
        ),
        "te": ("ఆడియోలో మాట స్పష్టంగా అర్థం కాలేదు. " "దయచేసి మళ్లీ మాట్లాడండి."),
    }

    def __init__(self):

        self.stt = SpeechToTextService()

        self.chat_service = ChatService()

        self.tts = TextToSpeechService()

        self.language_service = LanguageService()

    # =========================================================
    # Main Voice Chat
    # =========================================================

    def chat(
        self,
        user,
        audio_path: str,
        language: str = None,
    ):

        requested_language = self._normalize_language(language)

        # =====================================================
        # 1. Speech To Text
        # =====================================================

        try:

            speech_result = self.stt.transcribe(
                audio_path=audio_path,
                language=requested_language,
            )

        except Exception:

            logger.exception("Speech-to-text processing failed.")

            return self._build_speech_error(
                language=requested_language,
                match_type="speech_processing_error",
            )

        if not isinstance(
            speech_result,
            dict,
        ):

            logger.error("SpeechToTextService returned " "a non-dictionary response.")

            return self._build_speech_error(
                language=requested_language,
                match_type="speech_processing_error",
            )

        # =====================================================
        # 2. Extract Transcript
        # =====================================================

        transcript = self._clean_text(speech_result.get("text", ""))

        raw_transcript = self._clean_text(
            speech_result.get(
                "raw_text",
                transcript,
            )
        )

        normalized_text = self._clean_text(
            speech_result.get(
                "normalized_text",
                transcript,
            )
        )

        # =====================================================
        # 3. Resolve Language
        # =====================================================

        stt_language = self._normalize_language(speech_result.get("language"))

        # Priority:
        #
        # 1. Explicit language selected by user
        # 2. STT detected language
        # 3. Chat LanguageService detection from transcript

        resolved_language = requested_language or stt_language

        if not resolved_language and transcript:

            resolved_language = self.language_service.detect(transcript)

            resolved_language = self._normalize_language(resolved_language)

        if not resolved_language:
            resolved_language = "hi"

        # =====================================================
        # 4. Empty / Unclear Transcript
        # =====================================================

        if not transcript:

            return self._build_speech_error(
                language=resolved_language,
                match_type="speech_not_understood",
                speech_result=speech_result,
            )

        # =====================================================
        # 5. Send Transcript Through Chat Pipeline
        # =====================================================

        try:

            chat_result = self.chat_service.chat(
                user=user,
                message=transcript,
                language=resolved_language,
            )

        except Exception:

            logger.exception("Chat pipeline failed during voice chat.")

            return {
                "success": False,
                "transcript": transcript,
                "raw_transcript": raw_transcript,
                "normalized_text": normalized_text,
                "language": resolved_language,
                "language_probability": self._probability(
                    speech_result.get(
                        "language_probability",
                        0,
                    )
                ),
                "answer": "",
                "confidence": 0.0,
                "match_type": "chat_processing_error",
                "sources": [],
                "audio_url": None,
                "voice": None,
            }

        if not isinstance(
            chat_result,
            dict,
        ):

            logger.error(
                "ChatService returned a non-dictionary " "response during voice chat."
            )

            chat_result = {}

        answer = self._clean_text(chat_result.get("answer", ""))

        # ChatService may return a more accurate final
        # application language.
        final_language = self._normalize_language(chat_result.get("language"))

        if not final_language:
            final_language = resolved_language

        # =====================================================
        # 6. Text To Speech
        # =====================================================

        tts_result = {
            "success": False,
            "audio_url": None,
            "voice": None,
        }

        if answer:

            try:

                generated_tts = self.tts.synthesize(
                    text=answer,
                    language=final_language,
                )

                if isinstance(
                    generated_tts,
                    dict,
                ):
                    tts_result = generated_tts

            except Exception:

                # TTS is optional output enhancement.
                # A TTS failure must never destroy a valid
                # grounded text answer.

                logger.exception("Text-to-speech generation failed.")

        # =====================================================
        # 7. Final Response
        # =====================================================

        result = {
            "success": bool(
                chat_result.get(
                    "success",
                    False,
                )
            ),
            "transcript": transcript,
            "raw_transcript": raw_transcript,
            "normalized_text": normalized_text,
            "language": final_language,
            "language_probability": self._probability(
                speech_result.get(
                    "language_probability",
                    0,
                )
            ),
            "answer": answer,
            "confidence": self._confidence(
                chat_result.get(
                    "confidence",
                    0,
                )
            ),
            "match_type": chat_result.get(
                "match_type",
                "none",
            ),
            "sources": self._safe_sources(
                chat_result.get(
                    "sources",
                    [],
                )
            ),
            "audio_url": tts_result.get("audio_url"),
            "voice": tts_result.get("voice"),
        }

        logger.info(
            (
                "Voice chat completed. "
                "language=%s match_type=%s confidence=%s "
                "tts_success=%s"
            ),
            result["language"],
            result["match_type"],
            result["confidence"],
            bool(
                tts_result.get(
                    "success",
                    False,
                )
            ),
        )

        return result

    # =========================================================
    # Speech Error Response
    # =========================================================

    def _build_speech_error(
        self,
        language=None,
        match_type="speech_not_understood",
        speech_result=None,
    ):

        language = self._normalize_language(language) or "hi"

        speech_result = (
            speech_result
            if isinstance(
                speech_result,
                dict,
            )
            else {}
        )

        return {
            "success": False,
            "answer": self.SPEECH_NOT_UNDERSTOOD.get(
                language,
                self.SPEECH_NOT_UNDERSTOOD["hi"],
            ),
            "transcript": "",
            "raw_transcript": self._clean_text(speech_result.get("raw_text", "")),
            "normalized_text": "",
            "language": language,
            "language_probability": self._probability(
                speech_result.get(
                    "language_probability",
                    0,
                )
            ),
            "confidence": 0.0,
            "match_type": match_type,
            "sources": [],
            "audio_url": None,
            "voice": None,
        }

    # =========================================================
    # Helpers
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

        value = self.LANGUAGE_ALIASES.get(
            value,
            value,
        )

        if value in self.SUPPORTED_LANGUAGES:
            return value

        # Some STT engines may return locale-like values
        # such as hi-IN or gu-IN.

        prefix = value.split(
            "-",
            1,
        )[0]

        if prefix in self.SUPPORTED_LANGUAGES:
            return prefix

        return None

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
    def _confidence(
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
                100.0,
                value,
            ),
        )

    @staticmethod
    def _probability(
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

    @staticmethod
    def _safe_sources(
        sources,
    ):

        if not isinstance(
            sources,
            list,
        ):
            return []

        return [
            source
            for source in sources
            if isinstance(
                source,
                dict,
            )
        ]
