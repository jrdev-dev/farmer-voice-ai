from rest_framework import serializers

from apps.analytics.models import AnalyticsEvent


class AnalyticsEventSerializer(serializers.ModelSerializer):
    """
    Serializer for analytics event history.
    """

    class Meta:
        model = AnalyticsEvent
        fields = (
            "id",
            "event_type",
            "language",
            "success",
            "metadata",
            "created_at",
        )

        read_only_fields = fields


class EventUsageSerializer(serializers.Serializer):
    """
    Event-wise usage statistics.
    """

    event_type = serializers.CharField()
    count = serializers.IntegerField()


class LanguageUsageSerializer(serializers.Serializer):
    """
    Language-wise usage statistics.
    """

    language = serializers.CharField()
    count = serializers.IntegerField()


class AnalyticsSummarySerializer(serializers.Serializer):
    """
    Dashboard analytics response.
    """

    total_conversations = serializers.IntegerField()

    total_messages = serializers.IntegerField()

    user_messages = serializers.IntegerField()

    assistant_messages = serializers.IntegerField()

    total_feedback = serializers.IntegerField()

    helpful_feedback = serializers.IntegerField()

    not_helpful_feedback = serializers.IntegerField()

    helpful_rate = serializers.FloatField()

    total_events = serializers.IntegerField()

    successful_events = serializers.IntegerField()

    failed_events = serializers.IntegerField()

    event_usage = EventUsageSerializer(
        many=True,
    )

    language_usage = LanguageUsageSerializer(
        many=True,
    )
