from django.conf import settings
from django.db import models


class AnalyticsEvent(models.Model):
    """
    Stores important usage events for Farmer Voice AI.

    Examples:
    - TEXT_CHAT
    - VOICE_CHAT
    - OCR
    - FEEDBACK
    """

    class EventType(models.TextChoices):
        TEXT_CHAT = "TEXT_CHAT", "Text Chat"
        VOICE_CHAT = "VOICE_CHAT", "Voice Chat"
        OCR = "OCR", "OCR"
        FEEDBACK = "FEEDBACK", "Feedback"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="analytics_events",
    )

    event_type = models.CharField(
        max_length=30,
        choices=EventType.choices,
    )

    language = models.CharField(
        max_length=20,
        blank=True,
    )

    success = models.BooleanField(
        default=True,
    )

    metadata = models.JSONField(
        default=dict,
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        db_table = "analytics_events"
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["user", "event_type"],
            ),
            models.Index(
                fields=["created_at"],
            ),
        ]

    def __str__(self):
        return f"{self.user.email} - " f"{self.event_type} - " f"{self.created_at}"
