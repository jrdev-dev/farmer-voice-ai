from django.urls import path

from .views import VoiceChatView

urlpatterns = [
    path(
        "chat/",
        VoiceChatView.as_view(),
        name="voice-chat",
    ),
]
