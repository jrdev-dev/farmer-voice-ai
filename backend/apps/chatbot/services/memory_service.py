from django.db import transaction
from django.utils import timezone

from apps.chatbot.models import Conversation, Message


class MemoryService:
    """
    Conversation memory service for Farmer Voice AI.

    Responsibilities
    ----------------
    1. Get or create the user's active conversation.
    2. Persist user and assistant messages.
    3. Retrieve recent conversation history.
    4. Provide chronological context for follow-up questions.
    5. Keep conversation timestamps updated.
    6. Support conversation reset / lifecycle management.

    IMPORTANT
    ---------
    Conversation memory is contextual information only.

    Previous assistant answers must NEVER automatically become
    trusted agricultural evidence.

    Agricultural facts must still come from the Knowledge Base
    and pass retrieval/relevance validation.
    """

    DEFAULT_HISTORY_LIMIT = 10
    MAX_HISTORY_LIMIT = 50

    # =========================================================
    # Conversation
    # =========================================================

    def get_or_create_conversation(
        self,
        user,
    ):
        """
        Return the user's latest active conversation.

        If no active conversation exists, create one.
        """

        if user is None:
            raise ValueError("User is required to create a conversation.")

        conversation = (
            Conversation.objects.filter(
                user=user,
                is_active=True,
            )
            .order_by(
                "-updated_at",
                "-created_at",
            )
            .first()
        )

        if conversation:
            return conversation

        return Conversation.objects.create(
            user=user,
            is_active=True,
        )

    # =========================================================
    # Save User Message
    # =========================================================

    def save_user_message(
        self,
        conversation,
        message,
    ):
        """
        Save a farmer/user message.
        """

        return self._save_message(
            conversation=conversation,
            role=Message.Role.USER,
            message=message,
        )

    # =========================================================
    # Save Assistant Message
    # =========================================================

    def save_assistant_message(
        self,
        conversation,
        message,
    ):
        """
        Save assistant response and return the
        created Message object.
        """

        return Message.objects.create(
            conversation=conversation,
            role=Message.Role.ASSISTANT,
            content=message,
        )

    # =========================================================
    # Internal Message Save
    # =========================================================

    @transaction.atomic
    def _save_message(
        self,
        conversation,
        role,
        message,
    ):
        """
        Central message persistence method.
        """

        if conversation is None:
            raise ValueError("Conversation is required.")

        message = self._clean_text(message)

        if not message:
            raise ValueError("Message cannot be empty.")

        if role not in (
            Message.Role.USER,
            Message.Role.ASSISTANT,
        ):
            raise ValueError(f"Unsupported message role: {role}")

        saved_message = Message.objects.create(
            conversation=conversation,
            role=role,
            content=message,
        )

        # -----------------------------------------------------
        # Update conversation activity
        # -----------------------------------------------------
        #
        # If updated_at uses auto_now=True Django will normally
        # update it when save() executes.
        # This explicit save ensures the conversation moves to
        # the top after new activity.
        # -----------------------------------------------------

        try:

            conversation.updated_at = timezone.now()

            conversation.save(
                update_fields=[
                    "updated_at",
                ]
            )

        except Exception:
            # Some Conversation model versions may not expose
            # an editable updated_at field.
            #
            # Message persistence should not fail because of
            # timestamp maintenance.
            pass

        return saved_message

    # =========================================================
    # Recent Messages
    # =========================================================

    def recent_messages(
        self,
        conversation,
        limit=10,
    ):
        """
        Return recent messages.

        Compatibility behavior:
        newest message first.

        Existing services depending on the old MemoryService
        can continue using this method.
        """

        if conversation is None:
            return Message.objects.none()

        limit = self._normalize_limit(limit)

        return conversation.messages.all().order_by(
            "-created_at",
            "-id",
        )[:limit]

    # =========================================================
    # Chronological History
    # =========================================================

    def chronological_messages(
        self,
        conversation,
        limit=10,
    ):
        """
        Return recent messages in natural conversation order:

        oldest -> newest

        Useful when constructing LLM/context history.
        """

        if conversation is None:
            return []

        limit = self._normalize_limit(limit)

        messages = list(
            conversation.messages.all().order_by(
                "-created_at",
                "-id",
            )[:limit]
        )

        messages.reverse()

        return messages

    # =========================================================
    # User Messages
    # =========================================================

    def recent_user_messages(
        self,
        conversation,
        limit=10,
    ):
        """
        Return recent farmer messages only.

        Useful for:
        - crop reference resolution
        - contextual follow-up handling
        - avoiding assistant-generated text being interpreted
          as farmer context
        """

        if conversation is None:
            return Message.objects.none()

        limit = self._normalize_limit(limit)

        return conversation.messages.filter(
            role=Message.Role.USER,
        ).order_by(
            "-created_at",
            "-id",
        )[:limit]

    # =========================================================
    # Last User Message
    # =========================================================

    def last_user_message(
        self,
        conversation,
    ):
        """
        Return latest user message or None.
        """

        if conversation is None:
            return None

        return (
            conversation.messages.filter(
                role=Message.Role.USER,
            )
            .order_by(
                "-created_at",
                "-id",
            )
            .first()
        )

    # =========================================================
    # Last Assistant Message
    # =========================================================

    def last_assistant_message(
        self,
        conversation,
    ):
        """
        Return latest assistant message or None.
        """

        if conversation is None:
            return None

        return (
            conversation.messages.filter(
                role=Message.Role.ASSISTANT,
            )
            .order_by(
                "-created_at",
                "-id",
            )
            .first()
        )

    # =========================================================
    # Context Text
    # =========================================================

    def build_context_text(
        self,
        conversation,
        limit=8,
        include_assistant=True,
    ):
        """
        Build lightweight chronological conversation text.

        Example:

        Farmer: मेरे खेत में सोयाबीन है।
        Assistant: ठीक है...
        Farmer: इसमें कौन सी खाद डालूं?

        IMPORTANT:
        This text is contextual memory only.
        It must never be treated as trusted KB evidence.
        """

        messages = self.chronological_messages(
            conversation,
            limit=limit,
        )

        context_lines = []

        for message in messages:

            role = getattr(
                message,
                "role",
                None,
            )

            content = self._clean_text(
                getattr(
                    message,
                    "content",
                    "",
                )
            )

            if not content:
                continue

            if role == Message.Role.USER:

                context_lines.append(f"Farmer: {content}")

            elif role == Message.Role.ASSISTANT and include_assistant:

                context_lines.append(f"Assistant: {content}")

        return "\n".join(context_lines)

    # =========================================================
    # Conversation Statistics
    # =========================================================

    def message_count(
        self,
        conversation,
    ):
        """
        Return number of messages in a conversation.
        """

        if conversation is None:
            return 0

        return conversation.messages.count()

    # =========================================================
    # Start New Conversation
    # =========================================================

    @transaction.atomic
    def start_new_conversation(
        self,
        user,
    ):
        """
        Close existing active conversations and create a fresh
        conversation.

        Useful later for:
        - New Chat button
        - Ionic mobile app
        - Web UI
        """

        if user is None:
            raise ValueError("User is required.")

        Conversation.objects.filter(
            user=user,
            is_active=True,
        ).update(is_active=False)

        return Conversation.objects.create(
            user=user,
            is_active=True,
        )

    # =========================================================
    # Close Conversation
    # =========================================================

    def close_conversation(
        self,
        conversation,
    ):
        """
        Mark a conversation inactive.
        """

        if conversation is None:
            return False

        conversation.is_active = False

        update_fields = [
            "is_active",
        ]

        try:

            conversation.updated_at = timezone.now()

            update_fields.append("updated_at")

        except Exception:
            pass

        conversation.save(update_fields=update_fields)

        return True

    # =========================================================
    # Clear Conversation Messages
    # =========================================================

    @transaction.atomic
    def clear_messages(
        self,
        conversation,
    ):
        """
        Delete messages from a conversation.

        Intended for explicit reset/admin functionality only.
        """

        if conversation is None:
            return 0

        deleted_count, _ = conversation.messages.all().delete()

        return deleted_count

    # =========================================================
    # Helpers
    # =========================================================

    def _normalize_limit(
        self,
        limit,
    ):
        """
        Keep history queries bounded.
        """

        try:
            limit = int(limit)

        except (
            TypeError,
            ValueError,
        ):
            limit = self.DEFAULT_HISTORY_LIMIT

        if limit <= 0:
            limit = self.DEFAULT_HISTORY_LIMIT

        return min(
            limit,
            self.MAX_HISTORY_LIMIT,
        )

    @staticmethod
    def _clean_text(
        value,
    ):
        """
        Normalize message text before persistence.
        """

        if value is None:
            return ""

        value = str(value).replace(
            "\x00",
            " ",
        )

        return " ".join(value.strip().split())
