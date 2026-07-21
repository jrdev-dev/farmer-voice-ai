from apps.knowledge_base.models import (
    Knowledge,
    KnowledgeSource,
)


class KnowledgeService:

    @staticmethod
    def get_all_knowledge():
        return Knowledge.objects.filter(
            is_active=True
        ).order_by("-created_at")

    @staticmethod
    def get_all_sources():
        return KnowledgeSource.objects.order_by(
            "-created_at"
        )