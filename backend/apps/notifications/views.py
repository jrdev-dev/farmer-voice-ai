from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from drf_spectacular.utils import (
    extend_schema,
    OpenApiResponse,
)

from apps.notifications.serializers.notification_serializer import (
    NotificationSerializer,
)
from apps.notifications.services.notification_service import (
    NotificationService,
)


class NotificationListAPIView(APIView):
    """
    Return notifications for the authenticated user.
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(
        responses={
            200: NotificationSerializer(many=True),
            401: OpenApiResponse(description="Authentication required."),
        },
        summary="Get user notifications",
        description=(
            "Returns notifications belonging to the "
            "authenticated Farmer Voice AI user."
        ),
        tags=["Notifications"],
    )
    def get(self, request):

        # Optional:
        # /api/notifications/?unread=true

        unread_value = request.query_params.get("unread", "").strip().lower()

        unread_only = unread_value in {
            "true",
            "1",
            "yes",
        }

        notifications = NotificationService.get_notifications(
            user=request.user,
            unread_only=unread_only,
        )

        serializer = NotificationSerializer(
            notifications,
            many=True,
        )

        return Response(
            {
                "success": True,
                "count": len(serializer.data),
                "data": serializer.data,
            },
            status=status.HTTP_200_OK,
        )


class UnreadNotificationCountAPIView(APIView):
    """
    Return unread notification count.
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(
        responses={
            200: OpenApiResponse(description=("Unread notification count returned.")),
            401: OpenApiResponse(description="Authentication required."),
        },
        summary="Get unread notification count",
        tags=["Notifications"],
    )
    def get(self, request):

        count = NotificationService.unread_count(request.user)

        return Response(
            {
                "success": True,
                "unread_count": count,
            },
            status=status.HTTP_200_OK,
        )


class MarkNotificationReadAPIView(APIView):
    """
    Mark one notification as read.
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=None,
        responses={
            200: NotificationSerializer,
            404: OpenApiResponse(description="Notification not found."),
            401: OpenApiResponse(description="Authentication required."),
        },
        summary="Mark notification as read",
        tags=["Notifications"],
    )
    def patch(
        self,
        request,
        notification_id,
    ):

        notification = NotificationService.mark_as_read(
            user=request.user,
            notification_id=notification_id,
        )

        if notification is None:

            return Response(
                {
                    "success": False,
                    "message": ("Notification not found."),
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = NotificationSerializer(notification)

        return Response(
            {
                "success": True,
                "message": ("Notification marked as read."),
                "data": serializer.data,
            },
            status=status.HTTP_200_OK,
        )


class MarkAllNotificationsReadAPIView(APIView):
    """
    Mark all notifications belonging to the
    authenticated user as read.
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=None,
        responses={
            200: OpenApiResponse(description=("All notifications marked as read.")),
            401: OpenApiResponse(description="Authentication required."),
        },
        summary="Mark all notifications as read",
        tags=["Notifications"],
    )
    def patch(self, request):

        updated_count = NotificationService.mark_all_as_read(request.user)

        return Response(
            {
                "success": True,
                "message": ("All notifications marked as read."),
                "updated_count": updated_count,
                "unread_count": 0,
            },
            status=status.HTTP_200_OK,
        )
