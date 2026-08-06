"""
Django settings for Farmer Voice AI.

Development configuration.
Deployment-specific production settings will be handled separately.
"""

import os
from pathlib import Path
from datetime import timedelta
from dotenv import load_dotenv
import dj_database_url

# =============================================================================
# BASE DIRECTORY & ENVIRONMENT
# =============================================================================

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


# =============================================================================
# API KEYS
# =============================================================================

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

# =============================================================================
# SECURITY
# =============================================================================

SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY",
    "django-insecure-development-only-farmer-voice-ai",
)

DEBUG = os.environ.get(
    "DJANGO_DEBUG",
    "True",
).lower() in {
    "true",
    "1",
    "yes",
}

ALLOWED_HOSTS = [
    "127.0.0.1",
    "localhost",
    "192.168.31.120",
    ".onrender.com",
    "*",
]

CSRF_TRUSTED_ORIGINS = [
    "https://*.loca.lt",
    "https://*.lhr.life",
]

# Tell Django it's behind a proxy that terminates SSL (like localtunnel/ngrok)
# This fixes the "Mixed Content" HTTP vs HTTPS issues when returning absolute URLs.
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')


# =============================================================================
# INSTALLED APPLICATIONS
# =============================================================================

INSTALLED_APPS = [
    # -------------------------------------------------------------------------
    # Django
    # -------------------------------------------------------------------------
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # -------------------------------------------------------------------------
    # Third Party
    # -------------------------------------------------------------------------
    "rest_framework",
    "rest_framework_simplejwt.token_blacklist",
    "drf_spectacular",
    # -------------------------------------------------------------------------
    # Local Applications
    # -------------------------------------------------------------------------
    "apps.accounts",
    "apps.knowledge_base",
    "apps.chatbot",
    "apps.speech",
    "apps.ocr",
    "apps.feedback",
    "apps.notifications",
    "apps.analytics",
    "apps.common",
]


# =============================================================================
# MIDDLEWARE
# =============================================================================

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]


# =============================================================================
# URL CONFIGURATION
# =============================================================================

ROOT_URLCONF = "config.urls"


# =============================================================================
# TEMPLATES
# =============================================================================

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        # ---------------------------------------------------------------------
        # Project-level templates
        #
        # templates/chatbot_ui/login.html
        # templates/chatbot_ui/chat.html
        # ---------------------------------------------------------------------
        "DIRS": [
            BASE_DIR / "templates",
        ],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]


# =============================================================================
# WSGI
# =============================================================================

WSGI_APPLICATION = "config.wsgi.application"


# =============================================================================
# DATABASE
# =============================================================================

DATABASES = {
    "default": dj_database_url.config(
        default=f"sqlite:///{BASE_DIR}/db.sqlite3",
        conn_max_age=600,
        conn_health_checks=True,
    )
}


# =============================================================================
# PASSWORD VALIDATION
# =============================================================================

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "UserAttributeSimilarityValidator"
        ),
    },
    {
        "NAME": ("django.contrib.auth.password_validation." "MinimumLengthValidator"),
    },
    {
        "NAME": ("django.contrib.auth.password_validation." "CommonPasswordValidator"),
    },
    {
        "NAME": ("django.contrib.auth.password_validation." "NumericPasswordValidator"),
    },
]


# =============================================================================
# INTERNATIONALIZATION
# =============================================================================

LANGUAGE_CODE = "en-us"

# Farmer Voice AI currently targets Indian farmers.
TIME_ZONE = "Asia/Kolkata"

USE_I18N = True

USE_TZ = True


# =============================================================================
# STATIC FILES
# =============================================================================

STATIC_URL = "/static/"

# -------------------------------------------------------------------------
# Project-level static files
#
# static/chatbot_ui/css/style.css
# static/chatbot_ui/js/login.js
# static/chatbot_ui/js/chat.js
# -------------------------------------------------------------------------

STATICFILES_DIRS = [
    BASE_DIR / "static",
]

# Used later by:
#
# python manage.py collectstatic
#
# Production web server can serve files from this directory.
STATIC_ROOT = BASE_DIR / "staticfiles"


# =============================================================================
# MEDIA FILES
# =============================================================================

MEDIA_URL = "/media/"

MEDIA_ROOT = BASE_DIR / "media"


# =============================================================================
# DEFAULT PRIMARY KEY
# =============================================================================

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# =============================================================================
# CUSTOM USER MODEL
# =============================================================================

AUTH_USER_MODEL = "accounts.User"


# =============================================================================
# DJANGO REST FRAMEWORK
# =============================================================================

REST_FRAMEWORK = {
    # -------------------------------------------------------------------------
    # Authentication
    # -------------------------------------------------------------------------
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    # -------------------------------------------------------------------------
    # Secure by default
    #
    # APIs require authentication unless a view explicitly uses AllowAny.
    # -------------------------------------------------------------------------
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    # -------------------------------------------------------------------------
    # OpenAPI
    # -------------------------------------------------------------------------
    "DEFAULT_SCHEMA_CLASS": ("drf_spectacular.openapi.AutoSchema"),
}


# =============================================================================
# JWT
# =============================================================================

SIMPLE_JWT = {
    # -------------------------------------------------------------------------
    # Access token used for authenticated API requests.
    # -------------------------------------------------------------------------
    "ACCESS_TOKEN_LIFETIME": timedelta(
        minutes=30,
    ),
    # -------------------------------------------------------------------------
    # Refresh token used to obtain another access token.
    # -------------------------------------------------------------------------
    "REFRESH_TOKEN_LIFETIME": timedelta(
        days=7,
    ),
    # -------------------------------------------------------------------------
    # Issue a new refresh token whenever refreshed.
    # -------------------------------------------------------------------------
    "ROTATE_REFRESH_TOKENS": True,
    # -------------------------------------------------------------------------
    # Old refresh token becomes unusable after rotation.
    # -------------------------------------------------------------------------
    "BLACKLIST_AFTER_ROTATION": True,
    # -------------------------------------------------------------------------
    # Authorization header:
    #
    # Authorization: Bearer <access-token>
    # -------------------------------------------------------------------------
    "AUTH_HEADER_TYPES": ("Bearer",),
}


# =============================================================================
# DRF SPECTACULAR / SWAGGER
# =============================================================================

SPECTACULAR_SETTINGS = {
    "TITLE": "Farmer Voice AI API",
    "DESCRIPTION": ("Multilingual AI agricultural assistant backend APIs."),
    "VERSION": "1.0.0",
    "COMPONENT_SPLIT_REQUEST": True,
    "SERVE_INCLUDE_SCHEMA": False,
}


# =============================================================================
# FILE UPLOAD LIMITS
# =============================================================================

# -------------------------------------------------------------------------
# Maximum request size handled in memory.
#
# Used for:
# - Voice/audio uploads
# - OCR image uploads
# - Knowledge Base imports
#
# NOTE:
# VoiceChatSerializer currently permits audio up to 25 MB.
# Therefore Django's request limit should not be smaller than that.
# -------------------------------------------------------------------------

DATA_UPLOAD_MAX_MEMORY_SIZE = 30 * 1024 * 1024

FILE_UPLOAD_MAX_MEMORY_SIZE = 30 * 1024 * 1024
