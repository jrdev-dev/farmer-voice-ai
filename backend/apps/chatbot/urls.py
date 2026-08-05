from django.urls import path

from .views import (
    ChatAPIView,
    ConversationListAPIView,
    ConversationDetailAPIView,
)

urlpatterns = [
    path(
        "",
        ChatAPIView.as_view(),
        name="chat",
    ),
    path(
        "conversations/",
        ConversationListAPIView.as_view(),
        name="conversation_list",
    ),
    path(
        "conversations/new/",
        ConversationListAPIView.as_view(),
        name="conversation_new",
    ),
    path(
        "conversations/<uuid:conversation_id>/",
        ConversationDetailAPIView.as_view(),
        name="conversation_detail",
    ),
]