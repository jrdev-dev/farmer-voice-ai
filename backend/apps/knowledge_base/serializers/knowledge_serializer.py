from rest_framework import serializers

from apps.knowledge_base.models import (
    Knowledge,
    KnowledgeSource,
)


class KnowledgeSourceSerializer(serializers.ModelSerializer):
    class Meta:
        model = KnowledgeSource
        fields = "__all__"
        read_only_fields = (
            "id",
            "created_at",
            "updated_at",
        )


class KnowledgeSerializer(serializers.ModelSerializer):

    class Meta:
        model = Knowledge
        fields = "__all__"
        read_only_fields = (
            "id",
            "created_at",
            "updated_at",
        )