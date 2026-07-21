from rest_framework import serializers


class KnowledgeUploadSerializer(serializers.Serializer):
    file = serializers.FileField()

    title = serializers.CharField(max_length=255)

    description = serializers.CharField(
        required=False,
        allow_blank=True,
    )

    source_type = serializers.ChoiceField(
        choices=[
            "excel",
            "csv",
        ]
    )

    language = serializers.CharField(
        default="en"
    )