from rest_framework import generics

from apps.knowledge_base.models import (
    Knowledge,
    KnowledgeSource,
)
from apps.knowledge_base.serializers.knowledge_serializer import (
    KnowledgeSerializer,
    KnowledgeSourceSerializer,
)


class KnowledgeListAPIView(generics.ListAPIView):
    queryset = Knowledge.objects.filter(
        is_active=True
    ).order_by("-created_at")

    serializer_class = KnowledgeSerializer


class KnowledgeSourceListAPIView(generics.ListAPIView):
    queryset = KnowledgeSource.objects.all().order_by(
        "-created_at"
    )

    serializer_class = KnowledgeSourceSerializer