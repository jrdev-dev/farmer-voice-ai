from django.db.models import Count, Q

from apps.analytics.models import AnalyticsEvent
from apps.chatbot.models import Conversation, Message
from apps.feedback.models import Feedback


class AnalyticsService:
    """
    Handles Farmer Voice AI analytics.

    Responsibilities:
    - Record application usage events
    - Calculate farmer-specific statistics
    - Calculate admin/global statistics
    - Calculate feedback performance
    - Calculate language and event usage
    """

    # =========================================================
    # Record Event
    # =========================================================

    @staticmethod
    def record_event(
        user,
        event_type,
        language="",
        success=True,
        metadata=None,
    ):
        """
        Store an analytics event.

        Analytics failure should never break the main
        Farmer Voice AI workflow.
        """

        if user is None:
            return None

        if metadata is None:
            metadata = {}

        try:
            return AnalyticsEvent.objects.create(
                user=user,
                event_type=event_type,
                language=(language or "").strip(),
                success=bool(success),
                metadata=metadata,
            )

        except Exception as exc:
            print("\n" + "=" * 80)
            print("ANALYTICS EVENT ERROR")
            print("=" * 80)
            print("Error :", str(exc))
            print("=" * 80 + "\n")

            return None

    # =========================================================
    # Farmer Dashboard
    # =========================================================

    @staticmethod
    def farmer_summary(user):
        """
        Return analytics belonging only to the
        currently authenticated farmer.
        """

        conversations = Conversation.objects.filter(user=user)

        messages = Message.objects.filter(conversation__user=user)

        feedback = Feedback.objects.filter(user=user)

        events = AnalyticsEvent.objects.filter(user=user)

        total_feedback = feedback.count()

        helpful_feedback = feedback.filter(rating="HELPFUL").count()

        not_helpful_feedback = feedback.filter(rating="NOT_HELPFUL").count()

        helpful_rate = 0

        if total_feedback:
            helpful_rate = round(
                (helpful_feedback / total_feedback) * 100,
                2,
            )

        return {
            "total_conversations": conversations.count(),
            "total_messages": messages.count(),
            "user_messages": messages.filter(role=Message.Role.USER).count(),
            "assistant_messages": messages.filter(role=Message.Role.ASSISTANT).count(),
            "total_feedback": total_feedback,
            "helpful_feedback": helpful_feedback,
            "not_helpful_feedback": not_helpful_feedback,
            "helpful_rate": helpful_rate,
            "total_events": events.count(),
            "successful_events": events.filter(success=True).count(),
            "failed_events": events.filter(success=False).count(),
            "event_usage": list(
                events.values("event_type")
                .annotate(count=Count("id"))
                .order_by("-count")
            ),
            "language_usage": list(
                events.exclude(language="")
                .values("language")
                .annotate(count=Count("id"))
                .order_by("-count")
            ),
        }

    # =========================================================
    # Admin / Global Dashboard
    # =========================================================

    @staticmethod
    def global_summary():
        """
        Return system-wide analytics.

        This should only be exposed through an
        admin-protected API.
        """

        conversations = Conversation.objects.all()

        messages = Message.objects.all()

        feedback = Feedback.objects.all()

        events = AnalyticsEvent.objects.all()

        total_feedback = feedback.count()

        helpful_feedback = feedback.filter(rating="HELPFUL").count()

        not_helpful_feedback = feedback.filter(rating="NOT_HELPFUL").count()

        helpful_rate = 0

        if total_feedback:
            helpful_rate = round(
                (helpful_feedback / total_feedback) * 100,
                2,
            )

        return {
            "total_conversations": conversations.count(),
            "total_messages": messages.count(),
            "user_messages": messages.filter(role=Message.Role.USER).count(),
            "assistant_messages": messages.filter(role=Message.Role.ASSISTANT).count(),
            "total_feedback": total_feedback,
            "helpful_feedback": helpful_feedback,
            "not_helpful_feedback": not_helpful_feedback,
            "helpful_rate": helpful_rate,
            "total_events": events.count(),
            "successful_events": events.filter(success=True).count(),
            "failed_events": events.filter(success=False).count(),
            "event_usage": list(
                events.values("event_type")
                .annotate(count=Count("id"))
                .order_by("-count")
            ),
            "language_usage": list(
                events.exclude(language="")
                .values("language")
                .annotate(count=Count("id"))
                .order_by("-count")
            ),
        }

    # =========================================================
    # Recent Events
    # =========================================================

    @staticmethod
    def recent_events(
        user=None,
        limit=20,
    ):
        """
        Return recent analytics events.

        If user is provided, only that user's
        events are returned.
        """

        queryset = AnalyticsEvent.objects.select_related("user")

        if user is not None:
            queryset = queryset.filter(user=user)

        return queryset.order_by("-created_at")[:limit]
