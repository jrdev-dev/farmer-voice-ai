from rest_framework import serializers

from apps.chatbot.models import Message
from apps.feedback.models import Feedback


class FeedbackSerializer(serializers.ModelSerializer):
    """
    Create or update farmer feedback for an
    assistant-generated chat message.

    Security validation ensures:
    - Message belongs to logged-in user.
    - Feedback can only target ASSISTANT messages.
    """

    message_id = serializers.IntegerField(
        write_only=True,
    )

    message = serializers.IntegerField(
        source="message_id",
        read_only=True,
    )

    class Meta:
        model = Feedback

        fields = (
            "id",
            "message",
            "message_id",
            "rating",
            "comment",
            "created_at",
            "updated_at",
        )

        read_only_fields = (
            "id",
            "created_at",
            "updated_at",
        )

    # =========================================================
    # Message Validation
    # =========================================================

    def validate_message_id(
        self,
        value,
    ):
        """
        Ensure feedback is being submitted for:
        1. An existing message
        2. An assistant response
        3. A conversation owned by the current user
        """

        request = self.context.get("request")

        if request is None or not request.user.is_authenticated:
            raise serializers.ValidationError("Authenticated user is required.")

        try:

            message = Message.objects.select_related(
                "conversation",
            ).get(
                id=value,
            )

        except Message.DoesNotExist:

            raise serializers.ValidationError("Message not found.")

        # -----------------------------------------------------
        # Only Assistant Messages Can Receive Feedback
        # -----------------------------------------------------

        if message.role != Message.Role.ASSISTANT:

            raise serializers.ValidationError(
                "Feedback can only be submitted " "for assistant messages."
            )

        # -----------------------------------------------------
        # Ownership Check
        # -----------------------------------------------------

        if message.conversation.user_id != request.user.id:

            raise serializers.ValidationError(
                "You cannot submit feedback " "for this message."
            )

        # Save resolved object so create/update does not
        # need another database lookup.
        self._validated_message = message

        return value

    # =========================================================
    # Comment Validation
    # =========================================================

    def validate_comment(
        self,
        value,
    ):

        if value is None:
            return ""

        value = str(value).strip()

        # Prevent unnecessarily huge feedback payloads.
        if len(value) > 2000:

            raise serializers.ValidationError(
                "Feedback comment must not exceed " "2000 characters."
            )

        return value

    # =========================================================
    # Create / Update Feedback
    # =========================================================

    def create(
        self,
        validated_data,
    ):
        """
        Create feedback or update the user's existing
        feedback for the same assistant message.

        This allows:

        HELPFUL -> NOT_HELPFUL

        without creating duplicate records.
        """

        request = self.context["request"]

        # message_id is an API-only input field.
        validated_data.pop(
            "message_id",
            None,
        )

        message = getattr(
            self,
            "_validated_message",
            None,
        )

        if message is None:

            raise serializers.ValidationError(
                {"message_id": ("A valid assistant message " "is required.")}
            )

        rating = validated_data["rating"]

        comment = validated_data.get(
            "comment",
            "",
        )

        feedback, _ = Feedback.objects.update_or_create(
            user=request.user,
            message=message,
            defaults={
                "rating": rating,
                "comment": comment,
            },
        )

        return feedback
