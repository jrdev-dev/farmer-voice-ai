from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from drf_spectacular.utils import (
    extend_schema,
    OpenApiResponse,
)

from apps.analytics.serializers.analytics_serializer import (
    AnalyticsEventSerializer,
    AnalyticsSummarySerializer,
)
from apps.analytics.services.analytics_service import AnalyticsService


class FarmerAnalyticsAPIView(APIView):
    """
    Analytics dashboard for the currently
    authenticated farmer.
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(
        responses={
            200: AnalyticsSummarySerializer,
            401: OpenApiResponse(description="Authentication required."),
        },
        summary="Get farmer analytics",
        description=(
            "Returns conversation, message, feedback, "
            "event and language usage statistics for "
            "the authenticated farmer."
        ),
        tags=["Analytics"],
    )
    def get(self, request):

        data = AnalyticsService.farmer_summary(request.user)

        serializer = AnalyticsSummarySerializer(data)

        return Response(
            {
                "success": True,
                "data": serializer.data,
            }
        )


class RecentAnalyticsEventsAPIView(APIView):
    """
    Recent analytics events belonging to
    the authenticated farmer.
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(
        responses={
            200: AnalyticsEventSerializer(many=True),
            401: OpenApiResponse(description="Authentication required."),
        },
        summary="Get recent farmer analytics events",
        tags=["Analytics"],
    )
    def get(self, request):

        events = AnalyticsService.recent_events(
            user=request.user,
            limit=20,
        )

        serializer = AnalyticsEventSerializer(
            events,
            many=True,
        )

        return Response(
            {
                "success": True,
                "data": serializer.data,
            }
        )


class AdminAnalyticsAPIView(APIView):
    """
    System-wide Farmer Voice AI analytics.

    Only ADMIN users can access this endpoint.
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(
        responses={
            200: AnalyticsSummarySerializer,
            401: OpenApiResponse(description="Authentication required."),
            403: OpenApiResponse(description="Admin access required."),
        },
        summary="Get global system analytics",
        tags=["Analytics"],
    )
    def get(self, request):

        # -----------------------------------------------------
        # Role Protection
        # -----------------------------------------------------

        if request.user.role != "ADMIN":

            return Response(
                {
                    "success": False,
                    "message": "Admin access required.",
                },
                status=403,
            )

        data = AnalyticsService.global_summary()

        serializer = AnalyticsSummarySerializer(data)

        return Response(
            {
                "success": True,
                "data": serializer.data,
            }
        )
