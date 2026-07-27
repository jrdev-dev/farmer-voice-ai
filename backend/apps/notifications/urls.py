from django.urls import path

from .views import (
    NotificationListAPIView,
    UnreadNotificationCountAPIView,
    MarkNotificationReadAPIView,
    MarkAllNotificationsReadAPIView,
)

urlpatterns = [
    path(
        "",
        NotificationListAPIView.as_view(),
        name="notification-list",
    ),
    path(
        "unread-count/",
        UnreadNotificationCountAPIView.as_view(),
        name="notification-unread-count",
    ),
    path(
        "<int:notification_id>/read/",
        MarkNotificationReadAPIView.as_view(),
        name="notification-read",
    ),
    path(
        "read-all/",
        MarkAllNotificationsReadAPIView.as_view(),
        name="notification-read-all",
    ),
]
