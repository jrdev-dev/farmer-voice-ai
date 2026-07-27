import logging
import os
import tempfile

from rest_framework import status
from rest_framework.parsers import (
    FormParser,
    MultiPartParser,
)
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from drf_spectacular.utils import (
    extend_schema,
    OpenApiResponse,
)

from apps.analytics.models import AnalyticsEvent
from apps.analytics.services.analytics_service import AnalyticsService

from .serializers.speech_serializer import VoiceChatSerializer
from .services.voice_chat_service import VoiceChatService

logger = logging.getLogger(__name__)


class VoiceChatView(APIView):
    """
    Authenticated Farmer Voice Chat API.

    Pipeline
    --------
    Audio Upload
        -> Temporary Audio File
        -> Speech To Text
        -> Transcript Processing
        -> Language Detection
        -> ChatService
        -> RAG
        -> Text To Speech
        -> Analytics
        -> Voice Response

    The uploaded input audio is temporary and is deleted
    after processing.
    """

    permission_classes = [
        IsAuthenticated,
    ]

    parser_classes = [
        MultiPartParser,
        FormParser,
    ]

    @extend_schema(
        request=VoiceChatSerializer,
        responses={
            200: OpenApiResponse(description="Voice request processed successfully."),
            400: OpenApiResponse(description="Invalid audio request."),
            401: OpenApiResponse(
                description=("Authentication credentials " "were not provided.")
            ),
            500: OpenApiResponse(description="Unexpected speech processing error."),
        },
        summary="Voice chat with Farmer Voice AI",
        description=(
            "Upload farmer audio and receive transcript, "
            "detected language, grounded agricultural answer, "
            "confidence, sources and generated speech output."
        ),
        tags=[
            "Speech",
        ],
    )
    def post(
        self,
        request,
        *args,
        **kwargs,
    ):

        # =====================================================
        # 1. Validate Request
        # =====================================================

        serializer = VoiceChatSerializer(
            data=request.data,
        )

        serializer.is_valid(
            raise_exception=True,
        )

        audio = serializer.validated_data["audio"]

        # Language is optional.
        # None allows automatic language detection.

        language = serializer.validated_data.get("language")

        if language is not None:

            language = str(language).strip()

            if not language:
                language = None

        # =====================================================
        # 2. Determine Temporary File Extension
        # =====================================================

        original_name = getattr(
            audio,
            "name",
            "",
        )

        suffix = os.path.splitext(original_name)[1].lower()

        if not suffix:
            suffix = ".wav"

        temp_path = None

        try:

            # =================================================
            # 3. Save Input Audio Temporarily
            # =================================================

            with tempfile.NamedTemporaryFile(
                mode="wb",
                delete=False,
                suffix=suffix,
            ) as temp_file:

                for chunk in audio.chunks():

                    if chunk:
                        temp_file.write(chunk)

                temp_path = temp_file.name

            # =================================================
            # 4. Defensive Empty File Check
            # =================================================

            if (
                not temp_path
                or not os.path.exists(temp_path)
                or os.path.getsize(temp_path) <= 0
            ):

                # ---------------------------------------------
                # Record failed voice event
                # ---------------------------------------------

                AnalyticsService.record_event(
                    user=request.user,
                    event_type=(AnalyticsEvent.EventType.VOICE_CHAT),
                    language=language or "",
                    success=False,
                    metadata={
                        "reason": "empty_audio",
                        "filename": original_name,
                    },
                )

                return Response(
                    {
                        "success": False,
                        "message": ("Uploaded audio file is empty."),
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # =================================================
            # 5. Run Complete Voice Pipeline
            # =================================================

            voice_service = VoiceChatService()

            result = voice_service.chat(
                user=request.user,
                audio_path=temp_path,
                language=language,
            )

            # =================================================
            # 6. Validate Service Result
            # =================================================

            if not isinstance(
                result,
                dict,
            ):

                logger.error("VoiceChatService returned " "a non-dictionary response.")

                AnalyticsService.record_event(
                    user=request.user,
                    event_type=(AnalyticsEvent.EventType.VOICE_CHAT),
                    language=language or "",
                    success=False,
                    metadata={
                        "reason": ("invalid_service_response"),
                    },
                )

                return self._server_error()

            # =================================================
            # 7. Build Absolute TTS Audio URL
            # =================================================

            audio_url = result.get("audio_url")

            if audio_url:

                audio_url = str(audio_url).strip()

                result["audio_url"] = request.build_absolute_uri(audio_url)

            # =================================================
            # 8. Record Voice Analytics
            # =================================================

            detected_language = result.get(
                "language",
                language or "",
            )

            AnalyticsService.record_event(
                user=request.user,
                event_type=(AnalyticsEvent.EventType.VOICE_CHAT),
                language=detected_language or "",
                success=result.get(
                    "success",
                    False,
                ),
                metadata={
                    "language_probability": result.get(
                        "language_probability",
                        0,
                    ),
                    "confidence": result.get(
                        "confidence",
                        0,
                    ),
                    "match_type": result.get(
                        "match_type",
                        "",
                    ),
                    "source_count": len(
                        result.get(
                            "sources",
                            [],
                        )
                        or []
                    ),
                    "tts_generated": bool(result.get("audio_url")),
                    "voice": result.get("voice"),
                    "transcript_available": bool(result.get("transcript")),
                },
            )

            # =================================================
            # 9. Return Voice Result
            # =================================================

            return Response(
                result,
                status=status.HTTP_200_OK,
            )

        except Exception:

            logger.exception("Unexpected VoiceChatService failure.")

            # Analytics must not interfere with
            # exception handling.

            AnalyticsService.record_event(
                user=request.user,
                event_type=(AnalyticsEvent.EventType.VOICE_CHAT),
                language=language or "",
                success=False,
                metadata={
                    "reason": ("voice_processing_error"),
                },
            )

            return self._server_error()

        finally:

            # =================================================
            # 10. Always Delete Temporary Input Audio
            # =================================================

            if temp_path and os.path.exists(temp_path):

                try:

                    os.remove(temp_path)

                except OSError:

                    logger.warning(
                        ("Could not delete temporary " "voice input file: %s"),
                        temp_path,
                    )

    # =========================================================
    # Controlled Server Error
    # =========================================================

    @staticmethod
    def _server_error():

        return Response(
            {
                "success": False,
                "message": ("Unable to process the voice request " "at this time."),
            },
            status=(status.HTTP_500_INTERNAL_SERVER_ERROR),
        )
