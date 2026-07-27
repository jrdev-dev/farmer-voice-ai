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

from .serializers.ocr_serializer import OCRRequestSerializer
from .services.ocr_service import OCRService

logger = logging.getLogger(__name__)


class OCRAPIView(APIView):
    """
    Authenticated OCR API for Farmer Voice AI.

    Flow
    ----
    Image Upload
        -> Request Validation
        -> Temporary File
        -> OCR Service
        -> Extracted Text
        -> Confidence
        -> Analytics
        -> API Response

    Important
    ---------
    OCR output is extracted user-provided text.

    It is NOT automatically treated as trusted
    agricultural Knowledge Base evidence.
    """

    permission_classes = [
        IsAuthenticated,
    ]

    parser_classes = [
        MultiPartParser,
        FormParser,
    ]

    @extend_schema(
        request=OCRRequestSerializer,
        responses={
            200: OpenApiResponse(description="OCR processing completed successfully."),
            400: OpenApiResponse(description="Invalid image or request."),
            401: OpenApiResponse(
                description=("Authentication credentials " "were not provided.")
            ),
            422: OpenApiResponse(
                description=(
                    "Image was processed but no readable " "text could be extracted."
                )
            ),
            500: OpenApiResponse(description="Unexpected OCR processing error."),
        },
        summary="Extract text from agricultural image",
        description=(
            "Upload an image and extract multilingual text "
            "using the Farmer Voice AI OCR service."
        ),
        tags=[
            "OCR",
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

        serializer = OCRRequestSerializer(
            data=request.data,
        )

        serializer.is_valid(
            raise_exception=True,
        )

        image = serializer.validated_data["image"]

        language = serializer.validated_data.get("language")

        if language is not None:
            language = str(language).strip()

        # =====================================================
        # 2. Determine Temporary File Extension
        # =====================================================

        original_name = getattr(
            image,
            "name",
            "",
        )

        suffix = os.path.splitext(original_name)[1].lower()

        temp_path = None

        try:

            # =================================================
            # 3. Save Uploaded Image Temporarily
            # =================================================

            with tempfile.NamedTemporaryFile(
                mode="wb",
                delete=False,
                suffix=suffix,
            ) as temp_file:

                for chunk in image.chunks():

                    if chunk:
                        temp_file.write(chunk)

                temp_path = temp_file.name

            # =================================================
            # 4. Defensive File Check
            # =================================================

            if (
                not temp_path
                or not os.path.exists(temp_path)
                or os.path.getsize(temp_path) <= 0
            ):

                AnalyticsService.record_event(
                    user=request.user,
                    event_type=(AnalyticsEvent.EventType.OCR),
                    language=language or "",
                    success=False,
                    metadata={
                        "reason": "empty_image",
                        "filename": original_name,
                    },
                )

                return Response(
                    {
                        "success": False,
                        "message": ("Uploaded image file is empty."),
                        "text": "",
                        "confidence": 0.0,
                        "lines": [],
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # =================================================
            # 5. Run OCR
            # =================================================

            ocr_service = OCRService()

            result = ocr_service.extract_text(
                image_path=temp_path,
                language=language,
            )

            # =================================================
            # 6. Validate Service Result
            # =================================================

            if not isinstance(
                result,
                dict,
            ):

                logger.error("OCRService returned a " "non-dictionary response.")

                AnalyticsService.record_event(
                    user=request.user,
                    event_type=(AnalyticsEvent.EventType.OCR),
                    language=language or "",
                    success=False,
                    metadata={
                        "reason": ("invalid_service_response"),
                        "filename": original_name,
                    },
                )

                return self._server_error()

            # =================================================
            # 7. Prepare OCR Analytics Data
            # =================================================

            detected_language = result.get("language") or language or ""

            extracted_text = str(
                result.get(
                    "text",
                    "",
                )
                or ""
            ).strip()

            lines = result.get(
                "lines",
                [],
            )

            if not isinstance(
                lines,
                list,
            ):
                lines = []

            confidence = result.get(
                "confidence",
                0.0,
            )

            # =================================================
            # 8. No Readable Text
            # =================================================

            if not result.get(
                "success",
                False,
            ):

                AnalyticsService.record_event(
                    user=request.user,
                    event_type=(AnalyticsEvent.EventType.OCR),
                    language=detected_language,
                    success=False,
                    metadata={
                        "reason": "no_readable_text",
                        "confidence": confidence,
                        "line_count": len(lines),
                        "text_available": bool(extracted_text),
                        "filename": original_name,
                    },
                )

                return Response(
                    {
                        "success": False,
                        "message": (
                            "No readable text could be " "extracted from the image."
                        ),
                        "text": extracted_text,
                        "language": result.get("language"),
                        "confidence": confidence,
                        "lines": lines,
                    },
                    status=(status.HTTP_422_UNPROCESSABLE_ENTITY),
                )

            # =================================================
            # 9. Successful OCR Analytics
            # =================================================

            AnalyticsService.record_event(
                user=request.user,
                event_type=(AnalyticsEvent.EventType.OCR),
                language=detected_language,
                success=True,
                metadata={
                    "confidence": confidence,
                    "line_count": len(lines),
                    "text_available": bool(extracted_text),
                    "character_count": len(extracted_text),
                    "filename": original_name,
                },
            )

            # =================================================
            # 10. Successful OCR Response
            # =================================================

            return Response(
                {
                    "success": True,
                    "message": ("Text extracted successfully."),
                    "text": extracted_text,
                    "language": result.get("language"),
                    "confidence": confidence,
                    "lines": lines,
                },
                status=status.HTTP_200_OK,
            )

        except Exception:

            logger.exception("Unexpected OCR processing failure.")

            AnalyticsService.record_event(
                user=request.user,
                event_type=(AnalyticsEvent.EventType.OCR),
                language=language or "",
                success=False,
                metadata={
                    "reason": ("ocr_processing_error"),
                    "filename": original_name,
                },
            )

            return self._server_error()

        finally:

            # =================================================
            # 11. Always Delete Temporary Image
            # =================================================

            if temp_path and os.path.exists(temp_path):

                try:

                    os.remove(temp_path)

                except OSError:

                    logger.warning(
                        ("Could not delete temporary " "OCR image: %s"),
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
                "message": ("Unable to process the image " "at this time."),
                "text": "",
                "confidence": 0.0,
                "lines": [],
            },
            status=(status.HTTP_500_INTERNAL_SERVER_ERROR),
        )
