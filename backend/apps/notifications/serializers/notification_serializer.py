from rest_framework import serializers

from apps.notifications.models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    """
    Public notification representation.
    """

    class Meta:
        model = Notification

        fields = (
            "id",
            "notification_type",
            "title",
            "message",
            "is_read",
            "metadata",
            "created_at",
            "read_at",
        )

        read_only_fields = fields
