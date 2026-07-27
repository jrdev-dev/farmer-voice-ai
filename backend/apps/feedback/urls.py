from django.urls import path

from .views import FeedbackAPIView

urlpatterns = [
    path(
        "",
        FeedbackAPIView.as_view(),
        name="feedback",
    ),
]
