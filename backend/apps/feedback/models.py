from django.conf import settings
from django.db import models

from apps.chatbot.models import Message


class Feedback(models.Model):
    """
    Stores farmer feedback for an AI assistant response.

    One user can submit only one feedback record
    for a particular assistant message.

    Feedback can later be used for:
    - Answer quality analysis
    - Retrieval quality monitoring
    - Analytics
    - Expert review
    """

    class Rating(models.TextChoices):
        HELPFUL = "HELPFUL", "Helpful"
        NOT_HELPFUL = "NOT_HELPFUL", "Not Helpful"

    # =========================================================
    # Relationships
    # =========================================================

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="feedbacks",
    )

    message = models.ForeignKey(
        Message,
        on_delete=models.CASCADE,
        related_name="feedbacks",
    )

    # =========================================================
    # Feedback
    # =========================================================

    rating = models.CharField(
        max_length=20,
        choices=Rating.choices,
    )

    comment = models.TextField(
        blank=True,
    )

    # =========================================================
    # Timestamps
    # =========================================================

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    # =========================================================
    # Meta
    # =========================================================

    class Meta:
        db_table = "feedback"

        ordering = [
            "-created_at",
        ]

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "user",
                    "message",
                ],
                name="unique_user_message_feedback",
            )
        ]

        indexes = [
            models.Index(
                fields=[
                    "rating",
                    "created_at",
                ]
            ),
            models.Index(
                fields=[
                    "user",
                    "created_at",
                ]
            ),
        ]

    # =========================================================
    # String Representation
    # =========================================================

    def __str__(self):
        return f"{self.user.email} - " f"Message {self.message_id} - " f"{self.rating}"
