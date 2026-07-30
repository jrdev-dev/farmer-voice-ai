from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
)

from apps.chatbot.ui_views import (
    chat_page,
    login_page,
    register_page,
)

urlpatterns = [
    # =========================================================
    # FRONTEND UI
    # =========================================================
    path(
        "",
        login_page,
        name="login-page",
    ),
    path(
        "register/",
        register_page,
        name="register-page",
    ),
    path(
        "chat/",
        chat_page,
        name="chat-page",
    ),
    # =========================================================
    # DJANGO ADMIN
    # =========================================================
    path(
        "admin/",
        admin.site.urls,
    ),
    # =========================================================
    # ACCOUNTS
    # =========================================================
    path(
        "api/accounts/",
        include("apps.accounts.urls"),
    ),
    # =========================================================
    # CHAT
    # =========================================================
    path(
        "api/chat/",
        include("apps.chatbot.urls"),
    ),
    # =========================================================
    # KNOWLEDGE BASE
    # =========================================================
    path(
        "api/knowledge/",
        include("apps.knowledge_base.urls"),
    ),
    # =========================================================
    # SPEECH
    # =========================================================
    path(
        "api/speech/",
        include("apps.speech.urls"),
    ),
    # =========================================================
    # OCR
    # =========================================================
    path(
        "api/ocr/",
        include("apps.ocr.urls"),
    ),
    # =========================================================
    # FEEDBACK
    # =========================================================
    path(
        "api/feedback/",
        include("apps.feedback.urls"),
    ),
    # =========================================================
    # ANALYTICS
    # =========================================================
    path(
        "api/analytics/",
        include("apps.analytics.urls"),
    ),
    # =========================================================
    # NOTIFICATIONS
    # =========================================================
    path(
        "api/notifications/",
        include("apps.notifications.urls"),
    ),
    # =========================================================
    # OPENAPI SCHEMA
    # =========================================================
    path(
        "api/schema/",
        SpectacularAPIView.as_view(),
        name="schema",
    ),
    # =========================================================
    # SWAGGER
    # =========================================================
    path(
        "api/schema/swagger-ui/",
        SpectacularSwaggerView.as_view(
            url_name="schema",
        ),
        name="swagger-ui",
    ),
]


# =============================================================
# DEVELOPMENT MEDIA FILES
# =============================================================

if settings.DEBUG:

    urlpatterns += static(
        settings.MEDIA_URL,
        document_root=settings.MEDIA_ROOT,
    )
