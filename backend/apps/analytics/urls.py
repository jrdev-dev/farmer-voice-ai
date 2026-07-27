from django.urls import path

from .views import (
    FarmerAnalyticsAPIView,
    RecentAnalyticsEventsAPIView,
    AdminAnalyticsAPIView,
)

urlpatterns = [
    path(
        "",
        FarmerAnalyticsAPIView.as_view(),
        name="farmer-analytics",
    ),
    path(
        "events/",
        RecentAnalyticsEventsAPIView.as_view(),
        name="analytics-events",
    ),
    path(
        "admin/",
        AdminAnalyticsAPIView.as_view(),
        name="admin-analytics",
    ),
]
