from django.utils import timezone

from apps.notifications.models import Notification


class NotificationService:
    """
    Business logic for Farmer Voice AI notifications.
    """

    # =========================================================
    # Create Notification
    # =========================================================

    @staticmethod
    def create_notification(
        user,
        title,
        message,
        notification_type=Notification.Type.GENERAL,
        metadata=None,
    ):
        """
        Create a notification for a user.
        """

        if metadata is None:
            metadata = {}

        return Notification.objects.create(
            user=user,
            title=title,
            message=message,
            notification_type=notification_type,
            metadata=metadata,
        )

    # =========================================================
    # Get User Notifications
    # =========================================================

    @staticmethod
    def get_notifications(
        user,
        unread_only=False,
    ):
        """
        Return notifications belonging only to
        the authenticated user.
        """

        queryset = Notification.objects.filter(user=user)

        if unread_only:
            queryset = queryset.filter(is_read=False)

        return queryset.order_by("-created_at")

    # =========================================================
    # Unread Count
    # =========================================================

    @staticmethod
    def unread_count(user):
        """
        Return number of unread notifications.
        """

        return Notification.objects.filter(
            user=user,
            is_read=False,
        ).count()

    # =========================================================
    # Mark One Notification As Read
    # =========================================================

    @staticmethod
    def mark_as_read(
        user,
        notification_id,
    ):
        """
        Mark one notification as read.

        User filtering prevents one farmer from
        modifying another farmer's notification.
        """

        notification = Notification.objects.filter(
            id=notification_id,
            user=user,
        ).first()

        if notification is None:
            return None

        if not notification.is_read:
            notification.is_read = True
            notification.read_at = timezone.now()

            notification.save(
                update_fields=[
                    "is_read",
                    "read_at",
                ]
            )

        return notification

    # =========================================================
    # Mark All Notifications As Read
    # =========================================================

    @staticmethod
    def mark_all_as_read(user):
        """
        Mark all unread notifications for the
        authenticated user as read.
        """

        return Notification.objects.filter(
            user=user,
            is_read=False,
        ).update(
            is_read=True,
            read_at=timezone.now(),
        )
