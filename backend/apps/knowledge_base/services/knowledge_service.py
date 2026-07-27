from typing import Optional

from django.db.models import Q, QuerySet

from apps.knowledge_base.models import (
    Knowledge,
    KnowledgeSource,
)


class KnowledgeService:
    """
    Central service for Knowledge and KnowledgeSource queries.

    Responsibilities
    ----------------
    1. Retrieve active agricultural knowledge.
    2. Retrieve knowledge sources.
    3. Provide safe source/knowledge lookups.
    4. Support dynamic crop/category/domain/stage/language filtering.
    5. Provide crop discovery directly from the database.
    6. Provide lightweight knowledge statistics.

    IMPORTANT
    ---------
    No crop names are hardcoded.

    Crop support is completely data-driven. If new crop
    knowledge is imported into the database, this service
    automatically exposes it.
    """

    # =========================================================
    # Base QuerySets
    # =========================================================

    @staticmethod
    def active_knowledge() -> QuerySet:
        """
        Base queryset containing only active knowledge.
        """

        return Knowledge.objects.filter(is_active=True)

    @staticmethod
    def all_sources() -> QuerySet:
        """
        Base KnowledgeSource queryset.
        """

        return KnowledgeSource.objects.all()

    # =========================================================
    # Knowledge Retrieval
    # =========================================================

    @classmethod
    def get_all_knowledge(
        cls,
    ) -> QuerySet:
        """
        Return all active knowledge records.
        """

        return (
            cls.active_knowledge()
            .select_related("knowledge_source")
            .order_by("-created_at")
        )

    @classmethod
    def get_knowledge_by_id(
        cls,
        knowledge_id,
    ) -> Optional[Knowledge]:
        """
        Safely retrieve one active Knowledge record.

        Returns None when not found.
        """

        if not knowledge_id:
            return None

        try:

            return (
                cls.active_knowledge()
                .select_related("knowledge_source")
                .get(id=knowledge_id)
            )

        except (
            Knowledge.DoesNotExist,
            ValueError,
            TypeError,
        ):

            return None

    # =========================================================
    # Sources
    # =========================================================

    @classmethod
    def get_all_sources(
        cls,
    ) -> QuerySet:
        """
        Return all knowledge sources.
        """

        return cls.all_sources().order_by("-created_at")

    @classmethod
    def get_source_by_id(
        cls,
        source_id,
    ) -> Optional[KnowledgeSource]:
        """
        Safely retrieve a KnowledgeSource.

        Returns None instead of raising DoesNotExist.
        """

        if not source_id:
            return None

        try:

            return KnowledgeSource.objects.get(id=source_id)

        except (
            KnowledgeSource.DoesNotExist,
            ValueError,
            TypeError,
        ):

            return None

    # =========================================================
    # Knowledge by Source
    # =========================================================

    @classmethod
    def get_knowledge_by_source(
        cls,
        source,
    ) -> QuerySet:
        """
        Return active knowledge belonging to a source.

        `source` may be either:
        - KnowledgeSource object
        - source ID
        """

        queryset = cls.active_knowledge().select_related("knowledge_source")

        if source is None:

            return queryset.none()

        if isinstance(
            source,
            KnowledgeSource,
        ):

            queryset = queryset.filter(knowledge_source=source)

        else:

            queryset = queryset.filter(knowledge_source_id=source)

        return queryset.order_by("-created_at")

    # =========================================================
    # Dynamic Filtering
    # =========================================================

    @classmethod
    def filter_knowledge(
        cls,
        crop: Optional[str] = None,
        category: Optional[str] = None,
        subcategory: Optional[str] = None,
        domain: Optional[str] = None,
        stage: Optional[str] = None,
        language: Optional[str] = None,
        source_id=None,
    ) -> QuerySet:
        """
        Dynamically filter active agricultural knowledge.

        All filters are optional.

        Example
        -------
        filter_knowledge(
            crop="Soybean",
            category="Fertilizer",
            language="hi",
        )

        No crop/category/domain values are hardcoded.
        """

        queryset = cls.active_knowledge().select_related("knowledge_source")

        if crop:

            queryset = queryset.filter(crop__iexact=str(crop).strip())

        if category:

            queryset = queryset.filter(category__iexact=str(category).strip())

        if subcategory:

            queryset = queryset.filter(subcategory__iexact=str(subcategory).strip())

        if domain:

            queryset = queryset.filter(domain__iexact=str(domain).strip())

        if stage:

            queryset = queryset.filter(stage__iexact=str(stage).strip())

        if language:

            queryset = queryset.filter(language__iexact=str(language).strip())

        if source_id:

            queryset = queryset.filter(knowledge_source_id=source_id)

        return queryset.order_by(
            "-priority",
            "-created_at",
        )

    # =========================================================
    # Crop Knowledge
    # =========================================================

    @classmethod
    def get_knowledge_by_crop(
        cls,
        crop: str,
        language: Optional[str] = None,
    ) -> QuerySet:
        """
        Return all active knowledge for a crop.
        """

        if not crop:

            return cls.active_knowledge().none()

        return cls.filter_knowledge(
            crop=crop,
            language=language,
        )

    # =========================================================
    # Universal Crop Discovery
    # =========================================================

    @classmethod
    def get_available_crops(
        cls,
    ):
        """
        Return every crop currently represented in the
        active knowledge base.

        This is the database-driven crop registry.

        Adding knowledge for a new crop automatically makes
        that crop available here.
        """

        crops = (
            cls.active_knowledge()
            .exclude(crop__isnull=True)
            .exclude(crop__exact="")
            .values_list(
                "crop",
                flat=True,
            )
            .distinct()
        )

        cleaned = {str(crop).strip() for crop in crops if crop and str(crop).strip()}

        return sorted(
            cleaned,
            key=str.casefold,
        )

    # =========================================================
    # Categories
    # =========================================================

    @classmethod
    def get_available_categories(
        cls,
        crop: Optional[str] = None,
    ):
        """
        Return categories dynamically from active knowledge.
        """

        queryset = cls.active_knowledge()

        if crop:

            queryset = queryset.filter(crop__iexact=str(crop).strip())

        values = (
            queryset.exclude(category__isnull=True)
            .exclude(category__exact="")
            .values_list(
                "category",
                flat=True,
            )
            .distinct()
        )

        cleaned = {
            str(value).strip() for value in values if value and str(value).strip()
        }

        return sorted(
            cleaned,
            key=str.casefold,
        )

    # =========================================================
    # Domains
    # =========================================================

    @classmethod
    def get_available_domains(
        cls,
        crop: Optional[str] = None,
    ):
        """
        Return agricultural domains dynamically.
        """

        queryset = cls.active_knowledge()

        if crop:

            queryset = queryset.filter(crop__iexact=str(crop).strip())

        values = (
            queryset.exclude(domain__isnull=True)
            .exclude(domain__exact="")
            .values_list(
                "domain",
                flat=True,
            )
            .distinct()
        )

        cleaned = {
            str(value).strip() for value in values if value and str(value).strip()
        }

        return sorted(
            cleaned,
            key=str.casefold,
        )

    # =========================================================
    # Stages
    # =========================================================

    @classmethod
    def get_available_stages(
        cls,
        crop: Optional[str] = None,
    ):
        """
        Return crop stages dynamically.
        """

        queryset = cls.active_knowledge()

        if crop:

            queryset = queryset.filter(crop__iexact=str(crop).strip())

        values = (
            queryset.exclude(stage__isnull=True)
            .exclude(stage__exact="")
            .values_list(
                "stage",
                flat=True,
            )
            .distinct()
        )

        cleaned = {
            str(value).strip() for value in values if value and str(value).strip()
        }

        return sorted(
            cleaned,
            key=str.casefold,
        )

    # =========================================================
    # Languages
    # =========================================================

    @classmethod
    def get_available_languages(
        cls,
    ):
        """
        Return languages represented in active knowledge.
        """

        values = (
            cls.active_knowledge()
            .exclude(language__isnull=True)
            .exclude(language__exact="")
            .values_list(
                "language",
                flat=True,
            )
            .distinct()
        )

        cleaned = {
            str(value).strip() for value in values if value and str(value).strip()
        }

        return sorted(
            cleaned,
            key=str.casefold,
        )

    # =========================================================
    # Generic Text Search
    # =========================================================

    @classmethod
    def simple_search(
        cls,
        text: str,
        limit: int = 20,
    ) -> QuerySet:
        """
        Lightweight database search.

        This is NOT the main RAG retriever.

        It is useful for:
        - Admin UI
        - Knowledge browsing
        - Debugging
        - Dataset inspection
        """

        if not text:

            return cls.active_knowledge().none()

        text = str(text).strip()

        if not text:

            return cls.active_knowledge().none()

        try:

            limit = int(limit)

        except (
            TypeError,
            ValueError,
        ):

            limit = 20

        limit = max(
            1,
            min(
                limit,
                100,
            ),
        )

        queryset = (
            cls.active_knowledge()
            .select_related("knowledge_source")
            .filter(
                Q(crop__icontains=text)
                | Q(category__icontains=text)
                | Q(subcategory__icontains=text)
                | Q(domain__icontains=text)
                | Q(stage__icontains=text)
                | Q(question__icontains=text)
                | Q(answer__icontains=text)
                | Q(keywords__icontains=text)
                | Q(search_text__icontains=text)
            )
            .order_by(
                "-priority",
                "-created_at",
            )
        )

        return queryset[:limit]

    # =========================================================
    # Statistics
    # =========================================================

    @classmethod
    def get_statistics(
        cls,
    ):
        """
        Return lightweight knowledge-base statistics.
        """

        active = cls.active_knowledge()

        return {
            "total_knowledge": (Knowledge.objects.count()),
            "active_knowledge": (active.count()),
            "inactive_knowledge": (Knowledge.objects.filter(is_active=False).count()),
            "sources": (KnowledgeSource.objects.count()),
            "crops": len(cls.get_available_crops()),
            "categories": len(cls.get_available_categories()),
            "domains": len(cls.get_available_domains()),
            "languages": len(cls.get_available_languages()),
        }
