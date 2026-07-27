from rest_framework import serializers

from apps.knowledge_base.models import (
    Knowledge,
    KnowledgeSource,
)


class KnowledgeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Knowledge
        fields = "__all__"


class KnowledgeSourceSerializer(serializers.ModelSerializer):
    class Meta:
        model = KnowledgeSource
        fields = "__all__"