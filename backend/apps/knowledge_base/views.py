from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response

from drf_spectacular.openapi import OpenApiRequest
from drf_spectacular.utils import extend_schema

from apps.knowledge_base.models import (
    Knowledge,
    KnowledgeSource,
)

from apps.knowledge_base.serializers.knowledge_serializer import (
    KnowledgeSerializer,
    KnowledgeSourceSerializer,
)

from apps.knowledge_base.serializers.upload_serializer import (
    KnowledgeUploadSerializer,
)

from apps.knowledge_base.services.importer import (
    KnowledgeImporter,
)


class KnowledgeListAPIView(generics.ListAPIView):
    """
    List all active knowledge records.
    """

    queryset = Knowledge.objects.filter(
        is_active=True
    ).order_by("-created_at")

    serializer_class = KnowledgeSerializer


class KnowledgeSourceListAPIView(generics.ListAPIView):
    """
    List all uploaded knowledge sources.
    """

    queryset = KnowledgeSource.objects.all().order_by(
        "-created_at"
    )

    serializer_class = KnowledgeSourceSerializer


@extend_schema(
    tags=["Knowledge"],
    request=OpenApiRequest(
        request=KnowledgeUploadSerializer,
        encoding={
            "file": {
                "contentType": "multipart/form-data",
            }
        },
    ),
    responses={201: KnowledgeSourceSerializer},
)
class KnowledgeUploadAPIView(APIView):
    """
    Upload Knowledge Source
    """

    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):

        serializer = KnowledgeUploadSerializer(
            data=request.data
        )

        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data

        # ---------------------------------------------------------
        # Reuse existing source if already uploaded
        # ---------------------------------------------------------

        source, created = KnowledgeSource.objects.get_or_create(
            title=data["title"],
            source_type=data["source_type"],
            defaults={
                "description": data.get("description", ""),
                "file": data["file"],
                "source_name": data["file"].name,
                "language": data["language"],
                "status": KnowledgeSource.Status.PENDING,
            },
        )

        # ---------------------------------------------------------
        # Existing source -> replace old data
        # ---------------------------------------------------------

        if not created:

            Knowledge.objects.filter(
                knowledge_source=source
            ).delete()

            source.description = data.get("description", "")
            source.file = data["file"]
            source.source_name = data["file"].name
            source.language = data["language"]
            source.status = KnowledgeSource.Status.PENDING
            source.error_message = ""
            source.total_records = 0
            source.processed_records = 0
            source.failed_records = 0
            source.processed_at = None

            source.save()

        # ---------------------------------------------------------
        # Import Knowledge
        # ---------------------------------------------------------

        importer = KnowledgeImporter(source)

        success, errors = importer.process()

        if not success:

            return Response(
                {
                    "success": False,
                    "message": "Knowledge import failed.",
                    "errors": errors,
                    "source_id": source.id,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {
                "success": True,
                "message": "Knowledge imported successfully.",
                "source_id": source.id,
                "status": source.status,
                "total_records": source.total_records,
                "processed_records": source.processed_records,
                "failed_records": source.failed_records,
            },
            status=status.HTTP_201_CREATED,
        )