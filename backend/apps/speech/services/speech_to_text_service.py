import logging
import re
import time
from pathlib import Path
from typing import Dict, Optional

from faster_whisper import WhisperModel

from .speech_text_normalizer import SpeechTextNormalizer

try:
    from apps.knowledge_base.services.vocabulary_service import VocabularyService
except Exception:
    VocabularyService = None


logger = logging.getLogger(__name__)


class SpeechToTextService:
    """
    Fast multilingual Speech-To-Text service for Farmer Voice AI.

    Design goals
    ------------
    - Cache Faster-Whisper model.
    - Respect explicitly selected frontend language.
    - Use dynamic agriculture vocabulary from VocabularyService.
    - Avoid crop-specific / fertilizer-specific hardcoding.
    - Optimize short interactive farmer queries.
    - Reject obvious Whisper hallucinations.
    - Preserve existing API response contract.
    - Expose detailed timing information for debugging.

    Supported application languages
    --------------------------------
    Hindi, English, Hinglish, Gujarati, Marathi,
    Punjabi, Tamil and Telugu.
    """

    # =========================================================
    # Shared Process-Level Cache
    # =========================================================

    _models = {}

    _dynamic_prompt_cache = None
    _dynamic_prompt_cache_time = 0.0

    # Dynamic vocabulary does not need DB access on every audio.
    DYNAMIC_PROMPT_CACHE_TTL = 300

    # Prevent huge Whisper prompts.
    MAX_DYNAMIC_PROMPT_TERMS = 80
    MAX_DYNAMIC_PROMPT_CHARS = 1200

    # =========================================================
    # Languages
    # =========================================================

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
        "hi-in": "hi",
        "en-in": "en",
        "en-us": "en",
        "gu-in": "gu",
        "mr-in": "mr",
        "pa-in": "pa",
        "ta-in": "ta",
        "te-in": "te",
    }

    # =========================================================
    # Whisper Language Mapping
    # =========================================================

    WHISPER_LANGUAGE_MAP = {
        "hi": "hi",
        "en": "en",
        "gu": "gu",
        "mr": "mr",
        "pa": "pa",
        "ta": "ta",
        "te": "te",
        # Mixed Hindi-English.
        "hinglish": None,
    }

    # =========================================================
    # Generic Language Prompts
    # =========================================================
    #
    # These prompts contain instructions only.
    #
    # Crop / pest / disease / fertilizer terminology comes
    # dynamically from VocabularyService.
    # =========================================================

    INITIAL_PROMPTS = {
        "hi": (
            "यह भारतीय किसान की कृषि बातचीत है: सोयाबीन, गेहूं, धान, मक्का, कपास, आलू, सरसों, खाद, यूरिया, डीएपी, पोटाश, सिंचाई, पानी, रोग, कीट, इल्ली, दवा, छिड़काव, उपज। "
            "बोले गए कृषि शब्दों और फसलों के नाम (जैसे सोयाबीन, खाद, कौन सी दवा) को बिल्कुल सही हिंदी में ट्रांसक्राइब करें।"
        ),
        "en": (
            "This is an agricultural conversation with an Indian farmer. "
            "Transcribe the spoken words accurately. Preserve local, "
            "agricultural and technical terminology."
        ),
        "gu": (
            "આ ભારતીય ખેડૂત સાથે કૃષિ સંબંધિત વાતચીત છે. "
            "બોલાયેલા શબ્દોને સાચી રીતે લખો અને કૃષિ તથા સ્થાનિક "
            "શબ્દોને ધ્યાનથી ઓળખો."
        ),
        "mr": (
            "ही भारतीय शेतकऱ्याशी कृषी संबंधित बातचीत आहे. "
            "बोललेले शब्द अचूक लिहा आणि कृषी, स्थानिक व तांत्रिक "
            "शब्द काळजीपूर्वक ओळखा."
        ),
        "pa": (
            "ਇਹ ਭਾਰਤੀ ਕਿਸਾਨ ਨਾਲ ਖੇਤੀਬਾੜੀ ਸੰਬੰਧੀ ਗੱਲਬਾਤ ਹੈ। "
            "ਬੋਲੇ ਗਏ ਸ਼ਬਦਾਂ ਨੂੰ ਸਹੀ ਲਿਖੋ ਅਤੇ ਖੇਤੀਬਾੜੀ ਤੇ ਸਥਾਨਕ "
            "ਸ਼ਬਦਾਂ ਨੂੰ ਧਿਆਨ ਨਾਲ ਪਛਾਣੋ।"
        ),
        "ta": (
            "இது இந்திய விவசாயியுடன் வேளாண்மை தொடர்பான உரையாடல். "
            "பேசப்பட்ட சொற்களை துல்லியமாக எழுதவும். உள்ளூர் மற்றும் "
            "வேளாண்மை தொழில்நுட்ப சொற்களை கவனமாக அடையாளம் காணவும்."
        ),
        "te": (
            "ఇది భారతీయ రైతుతో వ్యవసాయ సంబంధిత సంభాషణ. "
            "మాట్లాడిన పదాలను ఖచ్చితంగా వ్రాయండి. స్థానిక, వ్యవసాయ "
            "మరియు సాంకేతిక పదాలను జాగ్రత్తగా గుర్తించండి."
        ),
    }

    GENERIC_PROMPT = (
        "यह भारतीय किसान की कृषि बातचीत है। "
        "बोले गए शब्दों को हिंदी, हिंग्लिश या मूल भाषा में ही ट्रांसक्राइब करें। "
        "Do not translate Hindi speech into English. Transcribe exact spoken words."
    )

    # =========================================================
    # Constructor
    # =========================================================

    def __init__(
        self,
        model_size="small",
        device="cpu",
        compute_type="int8",
    ):

        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type

        model_key = (
            model_size,
            device,
            compute_type,
        )

        model_load_start = time.perf_counter()

        if model_key not in self._models:

            logger.info(
                "Loading Faster Whisper model: " "model=%s device=%s compute_type=%s",
                model_size,
                device,
                compute_type,
            )

            self._models[model_key] = WhisperModel(
                model_size,
                device=device,
                compute_type=compute_type,
            )

            logger.info(
                "Faster Whisper model loaded in %.3f sec",
                time.perf_counter() - model_load_start,
            )

        self.model = self._models[model_key]

        self.text_normalizer = SpeechTextNormalizer()

        try:
            self.vocabulary_service = (
                VocabularyService() if VocabularyService is not None else None
            )
        except Exception as exc:

            logger.warning(
                "VocabularyService initialization failed: %s",
                exc,
            )

            self.vocabulary_service = None

    # =========================================================
    # Main Transcription
    # =========================================================

    def transcribe(
        self,
        audio_path: str,
        language: str = None,
    ):
        """
        Convert farmer speech into normalized text.

        Existing response keys are preserved.

        Additional timing metadata is included for debugging.
        """

        total_start = time.perf_counter()

        timings: Dict[str, float] = {}

        # =====================================================
        # 1. Audio Validation
        # =====================================================

        stage_start = time.perf_counter()

        audio_file = self._validate_audio(audio_path)

        timings["audio_validation"] = time.perf_counter() - stage_start

        # =====================================================
        # 2. Requested Language
        # =====================================================

        stage_start = time.perf_counter()

        app_language = self._normalize_language(language)

        whisper_language = None

        if app_language:
            whisper_language = self.WHISPER_LANGUAGE_MAP.get(app_language)

        if not whisper_language:
            # Default to Hindi for Indian agricultural speech to prevent Whisper translating Hindi to English
            whisper_language = "hi"

        timings["language_setup"] = time.perf_counter() - stage_start

        # =====================================================
        # 3. Dynamic Whisper Prompt
        # =====================================================

        stage_start = time.perf_counter()

        initial_prompt = self._get_initial_prompt(app_language)

        timings["prompt_build"] = time.perf_counter() - stage_start

        logger.info(
            "STT request: selected=%s whisper_language=%s "
            "audio_bytes=%s prompt_chars=%s",
            app_language,
            whisper_language,
            audio_file.stat().st_size,
            len(initial_prompt or ""),
        )

        # =====================================================
        # 4. Faster Whisper
        # =====================================================

        inference_start = time.perf_counter()

        segments, info = self.model.transcribe(
            str(audio_file),
            # If user selected Hindi, Gujarati etc.,
            # language detection is not required.
            language=whisper_language,
            task="transcribe",
            # -------------------------------------------------
            # Interactive CPU decoding
            # -------------------------------------------------
            beam_size=1,
            best_of=1,
            temperature=0.0,
            # -------------------------------------------------
            # VAD
            # -------------------------------------------------
            #
            # Short farmer questions should not wait through
            # large silent sections.
            # -------------------------------------------------
            vad_filter=True,
            vad_parameters={
                "min_silence_duration_ms": 250,
                "speech_pad_ms": 150,
            },
            # Each short farmer query should be decoded
            # independently.
            condition_on_previous_text=False,
            initial_prompt=initial_prompt,
        )

        # IMPORTANT:
        #
        # faster-whisper returns a lazy segment generator.
        # Actual inference occurs while iterating segments.
        #
        # Therefore inference timing MUST include iteration.

        text_parts = []

        segment_count = 0

        for segment in segments:

            segment_count += 1

            segment_text = self._clean_text(
                getattr(
                    segment,
                    "text",
                    "",
                )
            )

            if segment_text:

                text_parts.append(segment_text)

        raw_text = self._clean_text(" ".join(text_parts))

        timings["whisper_inference"] = time.perf_counter() - inference_start

        # =====================================================
        # 5. Whisper Language Metadata
        # =====================================================

        stage_start = time.perf_counter()

        detected_language = getattr(
            info,
            "language",
            None,
        )

        detected_language = self._normalize_language(detected_language)

        if app_language == "hinglish":

            final_language = "hinglish"

        elif app_language:

            # Frontend language selection wins.
            final_language = app_language

        else:

            final_language = detected_language or "hi"

        language_probability = self._safe_probability(
            getattr(
                info,
                "language_probability",
                0.0,
            )
        )

        timings["language_result"] = time.perf_counter() - stage_start

        # =====================================================
        # 6. Raw Transcript Validation
        # =====================================================

        stage_start = time.perf_counter()

        transcript_validation = self._validate_transcript(
            raw_text,
            final_language,
        )

        timings["raw_validation"] = time.perf_counter() - stage_start

        if not transcript_validation["valid"]:

            timings["total"] = time.perf_counter() - total_start

            self._log_timing(
                timings=timings,
                raw_text=raw_text,
                normalized_text="",
                language=final_language,
                segment_count=segment_count,
            )

            return self._failure_result(
                raw_text=raw_text,
                language=final_language,
                detected_language=detected_language,
                language_probability=language_probability,
                reason=transcript_validation["reason"],
                timings=timings,
            )

        # =====================================================
        # 7. Speech Text Normalization
        # =====================================================

        normalization_start = time.perf_counter()

        try:

            normalization_result = self.text_normalizer.normalize(raw_text)

        except Exception as exc:

            logger.exception(
                "Speech text normalization failed: %s",
                exc,
            )

            normalization_result = {}

        if not isinstance(
            normalization_result,
            dict,
        ):
            normalization_result = {}

        corrected_text = self._clean_text(
            normalization_result.get(
                "corrected_text",
                raw_text,
            )
        )

        normalized_text = self._clean_text(
            normalization_result.get(
                "normalized_text",
                corrected_text,
            )
        )

        # -----------------------------------------------------
        # Do NOT restore known garbage.
        # -----------------------------------------------------

        normalizer_says_garbage = bool(
            normalization_result.get(
                "is_garbage",
                False,
            )
        )

        if normalizer_says_garbage:

            corrected_text = ""
            normalized_text = ""

        else:

            # Protect valid Whisper transcript if normalizer
            # unexpectedly fails.
            if not corrected_text:
                corrected_text = raw_text

            if not normalized_text:
                normalized_text = corrected_text

        timings["normalization"] = time.perf_counter() - normalization_start

        # =====================================================
        # 8. Corrected Validation
        # =====================================================

        stage_start = time.perf_counter()

        corrected_validation = self._validate_transcript(
            corrected_text,
            final_language,
        )

        timings["corrected_validation"] = time.perf_counter() - stage_start

        if not corrected_validation["valid"]:

            timings["total"] = time.perf_counter() - total_start

            self._log_timing(
                timings=timings,
                raw_text=raw_text,
                normalized_text=normalized_text,
                language=final_language,
                segment_count=segment_count,
            )

            return self._failure_result(
                raw_text=raw_text,
                language=final_language,
                detected_language=detected_language,
                language_probability=language_probability,
                reason=corrected_validation["reason"],
                timings=timings,
            )

        # =====================================================
        # 9. Success
        # =====================================================

        timings["total"] = time.perf_counter() - total_start

        self._log_timing(
            timings=timings,
            raw_text=raw_text,
            normalized_text=normalized_text,
            language=final_language,
            segment_count=segment_count,
        )

        return {
            "success": True,
            "text": corrected_text,
            "raw_text": raw_text,
            "normalized_text": normalized_text,
            "language": final_language,
            "detected_language": detected_language,
            "language_probability": round(
                language_probability,
                4,
            ),
            "reason": None,
            "timings": self._rounded_timings(timings),
        }

    # =========================================================
    # Audio Validation
    # =========================================================

    @staticmethod
    def _validate_audio(
        audio_path,
    ) -> Path:

        if not audio_path:

            raise ValueError("Audio path is required.")

        audio_file = Path(audio_path)

        if not audio_file.exists():

            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        if not audio_file.is_file():

            raise ValueError("Audio path must point to a file.")

        if audio_file.stat().st_size <= 0:

            raise ValueError("Audio file is empty.")

        return audio_file

    # =========================================================
    # Dynamic Vocabulary Prompt
    # =========================================================

    def _get_dynamic_vocabulary_prompt(
        self,
    ) -> str:
        """
        Build Whisper context vocabulary dynamically.

        No crop names are hardcoded here.

        Vocabulary can come from:
        - DB knowledge
        - crop aliases
        - agriculture term configuration
        - categories
        - stages
        - domains
        - configured aliases
        """

        if self.vocabulary_service is None:
            return ""

        now = time.monotonic()

        cache_age = now - self.__class__._dynamic_prompt_cache_time

        if (
            self.__class__._dynamic_prompt_cache is not None
            and cache_age < self.DYNAMIC_PROMPT_CACHE_TTL
        ):

            return self.__class__._dynamic_prompt_cache

        try:

            vocabulary = self.vocabulary_service.get_search_vocabulary()

        except Exception as exc:

            logger.warning(
                "Could not load dynamic STT vocabulary: %s",
                exc,
            )

            return ""

        if not vocabulary:

            prompt = ""

        else:

            terms = []

            seen = set()

            for value in vocabulary:

                value = self._clean_text(value)

                if not value:
                    continue

                key = value.casefold()

                if key in seen:
                    continue

                seen.add(key)

                terms.append(value)

            # Stable output helps caching/debugging.
            terms.sort(key=str.casefold)

            terms = terms[: self.MAX_DYNAMIC_PROMPT_TERMS]

            prompt = ", ".join(terms)

            if len(prompt) > self.MAX_DYNAMIC_PROMPT_CHARS:

                prompt = prompt[: self.MAX_DYNAMIC_PROMPT_CHARS]

                # Don't end in the middle of a term if possible.
                last_separator = prompt.rfind(",")

                if last_separator > 0:

                    prompt = prompt[:last_separator]

        self.__class__._dynamic_prompt_cache = prompt

        self.__class__._dynamic_prompt_cache_time = now

        return prompt

    # =========================================================
    # Initial Prompt
    # =========================================================

    def _get_initial_prompt(
        self,
        language,
    ) -> str:

        if language == "hinglish":

            base_prompt = self.GENERIC_PROMPT

        elif language:

            base_prompt = self.INITIAL_PROMPTS.get(
                language,
                self.GENERIC_PROMPT,
            )

        else:

            base_prompt = self.GENERIC_PROMPT

        dynamic_vocabulary = self._get_dynamic_vocabulary_prompt()

        if not dynamic_vocabulary:

            return base_prompt

        return f"{base_prompt} " f"Relevant vocabulary: " f"{dynamic_vocabulary}."

    # =========================================================
    # Transcript Validation
    # =========================================================

    def _validate_transcript(
        self,
        text,
        language,
    ):

        text = self._clean_text(text)

        if not text:

            return {
                "valid": False,
                "reason": "empty_transcript",
            }

        if not any(character.isalnum() for character in text):

            return {
                "valid": False,
                "reason": ("punctuation_only_transcript"),
            }

        # -----------------------------------------------------
        # Hindi
        # -----------------------------------------------------

        if language == "hi":

            arabic_count = len(
                re.findall(
                    r"[\u0600-\u06FF]",
                    text,
                )
            )

            devanagari_count = len(
                re.findall(
                    r"[\u0900-\u097F]",
                    text,
                )
            )

            latin_count = len(
                re.findall(
                    r"[A-Za-z]",
                    text,
                )
            )

            meaningful_count = arabic_count + devanagari_count + latin_count

            if (
                meaningful_count > 0
                and arabic_count >= 3
                and arabic_count > (devanagari_count + latin_count)
            ):

                return {
                    "valid": False,
                    "reason": ("hindi_script_mismatch"),
                }

        # -----------------------------------------------------
        # Regional Scripts
        # -----------------------------------------------------

        script_ranges = {
            "gu": r"[\u0A80-\u0AFF]",
            "pa": r"[\u0A00-\u0A7F]",
            "ta": r"[\u0B80-\u0BFF]",
            "te": r"[\u0C00-\u0C7F]",
        }

        if language in script_ranges:

            expected_count = len(
                re.findall(
                    script_ranges[language],
                    text,
                )
            )

            latin_count = len(
                re.findall(
                    r"[A-Za-z]",
                    text,
                )
            )

            all_indic_or_arabic = len(
                re.findall(
                    (
                        r"[\u0600-\u06FF"
                        r"\u0900-\u097F"
                        r"\u0A00-\u0A7F"
                        r"\u0A80-\u0AFF"
                        r"\u0B80-\u0BFF"
                        r"\u0C00-\u0C7F]"
                    ),
                    text,
                )
            )

            if (
                expected_count == 0
                and all_indic_or_arabic >= 4
                and latin_count < all_indic_or_arabic
            ):

                return {
                    "valid": False,
                    "reason": ("language_script_mismatch"),
                }

        return {
            "valid": True,
            "reason": None,
        }

    # =========================================================
    # Language Normalization
    # =========================================================

    def _normalize_language(
        self,
        language,
    ) -> Optional[str]:

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

        prefix = value.split(
            "-",
            1,
        )[0]

        if prefix in self.SUPPORTED_LANGUAGES:

            return prefix

        return None

    # =========================================================
    # Failure Result
    # =========================================================

    def _failure_result(
        self,
        raw_text,
        language,
        detected_language,
        language_probability,
        reason,
        timings,
    ):

        logger.warning(
            "Speech transcript rejected: " "language=%s reason=%s raw=%r",
            language,
            reason,
            raw_text,
        )

        return {
            "success": False,
            "text": "",
            "raw_text": raw_text,
            "normalized_text": "",
            "language": language,
            "detected_language": (detected_language),
            "language_probability": round(
                language_probability,
                4,
            ),
            "reason": reason,
            "timings": self._rounded_timings(timings),
        }

    # =========================================================
    # Timing Logger
    # =========================================================

    def _log_timing(
        self,
        timings,
        raw_text,
        normalized_text,
        language,
        segment_count,
    ):

        print()
        print("=" * 80)
        print("SPEECH TO TEXT TIMING")
        print("=" * 80)

        print(f"Model              : {self.model_size}")

        print(f"Device             : {self.device}")

        print(f"Compute Type       : {self.compute_type}")

        print(f"Language           : {language}")

        print(f"Segments           : {segment_count}")

        print("-" * 80)

        for key, value in timings.items():

            print(f"{key:<20}: " f"{value:.3f} sec")

        print("-" * 80)

        print(f"Raw Transcript     : {raw_text}")

        print(f"Normalized         : {normalized_text}")

        print("=" * 80)
        print()

    # =========================================================
    # Helpers
    # =========================================================

    @staticmethod
    def _clean_text(
        value,
    ) -> str:

        if value is None:
            return ""

        value = str(value).replace(
            "\x00",
            " ",
        )

        return " ".join(value.strip().split())

    @staticmethod
    def _safe_probability(
        value,
    ) -> float:

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
    def _rounded_timings(
        timings,
    ):

        return {
            key: round(
                float(value),
                4,
            )
            for key, value in timings.items()
        }
