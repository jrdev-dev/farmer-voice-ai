from django.contrib import admin
from .models import KnowledgeSource, Knowledge


@admin.register(KnowledgeSource)
class KnowledgeSourceAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "title",
        "source_type",
        "status",
        "language",
        "version",
        "created_at",
    )

    search_fields = (
        "title",
        "source_name",
    )

    list_filter = (
        "source_type",
        "status",
        "language",
    )


@admin.register(Knowledge)
class KnowledgeAdmin(admin.ModelAdmin):

    list_display = (
        "id",
        "crop",
        "category",
        "stage",
        "language",
        "priority",
        "is_active",
    )

    search_fields = (
        "crop",
        "question",
        "keywords",
    )

    list_filter = (
        "category",
        "language",
        "is_active",
    )