from django.core.management.base import BaseCommand
from django.db import transaction

from apps.knowledge_base.models import Knowledge
from apps.knowledge_base.services.normalizer import QuestionNormalizer
from apps.knowledge_base.services.vector_store import VectorStore


class Command(BaseCommand):
    """
    Re-normalize existing Knowledge records and
    rebuild the FAISS semantic search index.
    """

    help = "Rebuild normalized_question, search_text " "and FAISS knowledge index."

    @transaction.atomic
    def handle(self, *args, **options):

        normalizer = QuestionNormalizer()

        knowledge_items = list(Knowledge.objects.all().order_by("id"))

        if not knowledge_items:
            self.stdout.write(self.style.WARNING("No knowledge records found."))
            return

        self.stdout.write(f"Processing {len(knowledge_items)} knowledge records...")

        # ==================================================
        # 1. Re-normalize Database Records
        # ==================================================

        for item in knowledge_items:

            item.normalized_question = normalizer.normalize(item.question)

            item.search_text = normalizer.build_search_text(
                question=item.question,
                answer=item.answer,
                crop=item.crop,
                stage=item.stage,
                domain=item.domain,
            )

        Knowledge.objects.bulk_update(
            knowledge_items,
            [
                "normalized_question",
                "search_text",
            ],
            batch_size=500,
        )

        self.stdout.write(
            self.style.SUCCESS(f"Updated {len(knowledge_items)} knowledge records.")
        )

        # ==================================================
        # 2. Rebuild FAISS Index
        # ==================================================

        self.stdout.write("Rebuilding FAISS index...")

        vector_store = VectorStore()

        vector_store.build_index()

        vector_store.save()

        self.stdout.write(
            self.style.SUCCESS(
                f"FAISS index rebuilt with " f"{vector_store.index.ntotal} vectors."
            )
        )

        self.stdout.write(
            self.style.SUCCESS("Knowledge index rebuild completed successfully.")
        )
