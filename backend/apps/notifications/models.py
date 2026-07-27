from django.conf import settings
from django.db import models


class Notification(models.Model):
    """
    In-app notification for Farmer Voice AI users.
    """

    class Type(models.TextChoices):
        GENERAL = "GENERAL", "General"
        ADVISORY = "ADVISORY", "Advisory"
        ALERT = "ALERT", "Alert"
        SYSTEM = "SYSTEM", "System"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )

    notification_type = models.CharField(
        max_length=20,
        choices=Type.choices,
        default=Type.GENERAL,
    )

    title = models.CharField(
        max_length=255,
    )

    message = models.TextField()

    is_read = models.BooleanField(
        default=False,
    )

    metadata = models.JSONField(
        default=dict,
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    read_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    class Meta:
        db_table = "notifications"
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["user", "is_read"],
            ),
            models.Index(
                fields=["created_at"],
            ),
        ]

    def __str__(self):
        return f"{self.user.email} - {self.title}"
