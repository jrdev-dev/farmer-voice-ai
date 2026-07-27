from django.urls import path

from apps.knowledge_base.views import (
    KnowledgeListAPIView,
    KnowledgeSourceListAPIView,
    KnowledgeUploadAPIView,
)

app_name = "knowledge_base"

urlpatterns = [
    path(
        "",
        KnowledgeListAPIView.as_view(),
        name="knowledge-list",
    ),
    path(
        "sources/",
        KnowledgeSourceListAPIView.as_view(),
        name="knowledge-source-list",
    ),
    path(
        "upload/",
        KnowledgeUploadAPIView.as_view(),
        name="knowledge-upload",
    ),
]