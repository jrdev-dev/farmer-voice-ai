import asyncio
import logging
import threading
import uuid
from pathlib import Path

import edge_tts
from django.conf import settings

logger = logging.getLogger(__name__)


class TextToSpeechService:
    """
    Converts Farmer Voice AI text responses into speech.

    Supported application languages:
    - Hindi
    - English
    - Hinglish
    - Marathi
    - Gujarati
    - Punjabi
    - Tamil
    - Telugu

    Audio files are generated inside MEDIA_ROOT and the
    relative MEDIA_URL is returned to the API layer.
    """

    # =========================================================
    # Voices
    # =========================================================

    VOICES = {
        "hi": "hi-IN-SwaraNeural",
        "en": "en-IN-NeerjaNeural",
        "hinglish": "hi-IN-SwaraNeural",
        "mr": "mr-IN-AarohiNeural",
        "gu": "gu-IN-DhwaniNeural",
        "pa": "pa-IN-VaaniNeural",
        "ta": "ta-IN-PallaviNeural",
        "te": "te-IN-ShrutiNeural",
    }

    LANGUAGE_ALIASES = {
        "hindi": "hi",
        "english": "en",
        "hinglish": "hinglish",
        "marathi": "mr",
        "gujarati": "gu",
        "punjabi": "pa",
        "tamil": "ta",
        "telugu": "te",
        "hi-in": "hi",
        "en-in": "en",
        "gu-in": "gu",
        "mr-in": "mr",
        "pa-in": "pa",
        "ta-in": "ta",
        "te-in": "te",
    }

    DEFAULT_LANGUAGE = "hi"

    DEFAULT_VOICE = VOICES[DEFAULT_LANGUAGE]

    # =========================================================
    # Constructor
    # =========================================================

    def __init__(self):

        self.output_directory = Path(settings.MEDIA_ROOT) / "speech" / "responses"

        self.output_directory.mkdir(
            parents=True,
            exist_ok=True,
        )

    # =========================================================
    # Language
    # =========================================================

    def normalize_language(
        self,
        language,
    ):
        """
        Normalize application/locale language values.
        """

        if language is None:
            return self.DEFAULT_LANGUAGE

        value = str(language).strip().lower()

        if not value:
            return self.DEFAULT_LANGUAGE

        value = value.replace(
            "_",
            "-",
        )

        value = self.LANGUAGE_ALIASES.get(
            value,
            value,
        )

        if value in self.VOICES:
            return value

        prefix = value.split(
            "-",
            1,
        )[0]

        if prefix in self.VOICES:
            return prefix

        logger.warning(
            "Unsupported TTS language '%s'. " "Using default language '%s'.",
            language,
            self.DEFAULT_LANGUAGE,
        )

        return self.DEFAULT_LANGUAGE

    # =========================================================
    # Voice Selection
    # =========================================================

    def get_voice(
        self,
        language,
    ):
        """
        Select TTS voice according to language.
        """

        normalized_language = self.normalize_language(language)

        return self.VOICES.get(
            normalized_language,
            self.DEFAULT_VOICE,
        )

    # =========================================================
    # Async Generation
    # =========================================================

    async def _generate(
        self,
        text,
        voice,
        output_path,
    ):
        """
        Generate speech asynchronously using Edge TTS.
        """

        communicate = edge_tts.Communicate(
            text=text,
            voice=voice,
        )

        await communicate.save(str(output_path))

    # =========================================================
    # Coroutine Runner
    # =========================================================

    def _run_async(
        self,
        coroutine_factory,
    ):
        """
        Safely run Edge TTS from synchronous Django code.

        If no event loop is currently running, asyncio.run()
        is sufficient.

        If synthesize() is called from a thread already running
        an event loop, execute the coroutine in a separate thread
        with its own loop.
        """

        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(coroutine_factory())

        result = {
            "value": None,
            "error": None,
        }

        def runner():

            try:

                result["value"] = asyncio.run(coroutine_factory())

            except Exception as exc:

                result["error"] = exc

        thread = threading.Thread(
            target=runner,
            daemon=True,
        )

        thread.start()
        thread.join()

        if result["error"] is not None:
            raise result["error"]

        return result["value"]

    # =========================================================
    # Synthesize
    # =========================================================

    def synthesize(
        self,
        text,
        language="hi",
    ):
        """
        Convert text into an MP3 audio file.

        Returns
        -------
        {
            "success": bool,
            "audio_path": str | None,
            "audio_url": str | None,
            "voice": str | None,
            "language": str
        }
        """

        # -----------------------------------------------------
        # Validate Text
        # -----------------------------------------------------

        if text is None:

            return self._empty_result(language)

        text = str(text).strip()

        if not text:

            return self._empty_result(language)

        # -----------------------------------------------------
        # Resolve Language + Voice
        # -----------------------------------------------------

        normalized_language = self.normalize_language(language)

        voice = self.get_voice(normalized_language)

        # -----------------------------------------------------
        # Generate Unique File
        # -----------------------------------------------------

        filename = f"{uuid.uuid4().hex}.mp3"

        output_path = self.output_directory / filename

        # -----------------------------------------------------
        # Generate Audio
        # -----------------------------------------------------

        try:

            self._run_async(
                lambda: self._generate(
                    text=text,
                    voice=voice,
                    output_path=output_path,
                )
            )

            # Edge TTS should have created a real audio file.
            if not output_path.exists() or output_path.stat().st_size <= 0:

                raise RuntimeError("TTS generated an empty audio file.")

        except Exception:

            # Remove partial/corrupted output.
            try:

                if output_path.exists():
                    output_path.unlink()

            except OSError:

                logger.exception("Could not remove failed TTS output.")

            logger.exception(
                "Text-to-speech generation failed. " "language=%s voice=%s",
                normalized_language,
                voice,
            )

            raise

        # -----------------------------------------------------
        # Build Media URL
        # -----------------------------------------------------

        media_url = str(settings.MEDIA_URL)

        if not media_url.endswith("/"):
            media_url += "/"

        relative_url = f"{media_url}" f"speech/responses/{filename}"

        logger.info(
            ("Text-to-speech completed. " "language=%s voice=%s characters=%s"),
            normalized_language,
            voice,
            len(text),
        )

        return {
            "success": True,
            "audio_path": str(output_path),
            "audio_url": relative_url,
            "voice": voice,
            "language": normalized_language,
        }

    # =========================================================
    # Empty Result
    # =========================================================

    def _empty_result(
        self,
        language,
    ):

        normalized_language = self.normalize_language(language)

        return {
            "success": False,
            "audio_path": None,
            "audio_url": None,
            "voice": None,
            "language": normalized_language,
        }
