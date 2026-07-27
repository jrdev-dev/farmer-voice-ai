from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from drf_spectacular.utils import (
    extend_schema,
    OpenApiResponse,
)

from apps.analytics.models import AnalyticsEvent
from apps.analytics.services.analytics_service import AnalyticsService

from apps.feedback.serializers.feedback_serializer import (
    FeedbackSerializer,
)


class FeedbackAPIView(APIView):
    """
    Farmer feedback API.

    Allows an authenticated farmer to submit feedback
    for an assistant-generated chat message.

    If feedback already exists for the same user and
    assistant message, it is updated instead of creating
    a duplicate record.

    Every successful feedback submission is also recorded
    as an analytics event.
    """

    permission_classes = [
        IsAuthenticated,
    ]

    # =========================================================
    # Submit Feedback
    # =========================================================

    @extend_schema(
        request=FeedbackSerializer,
        responses={
            200: FeedbackSerializer,
            400: OpenApiResponse(description="Invalid feedback request."),
            401: OpenApiResponse(description="Authentication required."),
        },
        summary="Submit feedback for an AI response",
        description=(
            "Submit HELPFUL or NOT_HELPFUL feedback for "
            "an assistant-generated chat message."
        ),
        tags=[
            "Feedback",
        ],
    )
    def post(
        self,
        request,
        *args,
        **kwargs,
    ):

        # =====================================================
        # 1. Validate Feedback
        # =====================================================

        serializer = FeedbackSerializer(
            data=request.data,
            context={
                "request": request,
            },
        )

        serializer.is_valid(
            raise_exception=True,
        )

        # =====================================================
        # 2. Create / Update Feedback
        # =====================================================

        feedback = serializer.save()

        # =====================================================
        # 3. Record Feedback Analytics
        # =====================================================
        #
        # AnalyticsService handles its own exceptions.
        # Analytics failure must never break feedback saving.
        # =====================================================

        AnalyticsService.record_event(
            user=request.user,
            event_type=(AnalyticsEvent.EventType.FEEDBACK),
            language="",
            success=True,
            metadata={
                "feedback_id": feedback.id,
                "message_id": feedback.message_id,
                "rating": feedback.rating,
                "has_comment": bool(feedback.comment and feedback.comment.strip()),
            },
        )

        # =====================================================
        # 4. Serialize Response
        # =====================================================

        response_serializer = FeedbackSerializer(
            feedback,
            context={
                "request": request,
            },
        )

        # =====================================================
        # 5. Return Response
        # =====================================================

        return Response(
            {
                "success": True,
                "message": ("Feedback saved successfully."),
                "data": response_serializer.data,
            },
            status=status.HTTP_200_OK,
        )
