from django.db import transaction
from django.utils import timezone

from apps.knowledge_base.models import (
    Knowledge,
    KnowledgeSource,
)

from .csv_parser import CSVParser
from .excel_parser import ExcelParser
from .validator import KnowledgeValidator


class KnowledgeImporter:
    """
    Import validated knowledge into database.
    """

    def __init__(self, source: KnowledgeSource):
        self.source = source
        self.validator = KnowledgeValidator()

    def get_parser(self):

        if self.source.source_type == KnowledgeSource.SourceType.EXCEL:
            return ExcelParser(self.source.file.path)

        if self.source.source_type == KnowledgeSource.SourceType.CSV:
            return CSVParser(self.source.file.path)

        raise ValueError(
            f"Unsupported source type: {self.source.source_type}"
        )

    @transaction.atomic
    def process(self):

        self.source.status = KnowledgeSource.Status.PROCESSING
        self.source.save(update_fields=["status"])

        try:

            parser = self.get_parser()

            dataframe = parser.read()

            self.source.total_records = len(dataframe)
            self.source.save(update_fields=["total_records"])

            result = self.validator.validate(dataframe)

            if not result["success"]:

                self.source.status = KnowledgeSource.Status.FAILED
                self.source.failed_records = len(result["errors"])
                self.source.error_message = "\n".join(result["errors"])
                self.source.processed_at = timezone.now()

                self.source.save()

                return False, result["errors"]
            # ---------------------------------------------------------
            # Remove old knowledge of this source
            # ---------------------------------------------------------

            Knowledge.objects.filter(
                knowledge_source=self.source
            ).delete()

            knowledge_objects = []

            for record in result["records"]:

                knowledge_objects.append(

                    Knowledge(

                        knowledge_source=self.source,

                        question=record["question"],

                        normalized_question=record["normalized_question"],

                        answer=record["answer"],

                        crop=record["crop"],

                        stage=record["stage"],

                        domain=record["domain"],

                        prepared_by=record["prepared_by"],

                        language=record["language"],

                        search_text=record["search_text"],
                    )

                )

            Knowledge.objects.bulk_create(
                knowledge_objects,
                batch_size=1000,
            )

            self.source.status = KnowledgeSource.Status.COMPLETED
            self.source.processed_records = len(knowledge_objects)
            self.source.failed_records = 0
            self.source.processed_at = timezone.now()

            self.source.save()

            return True, None

        except Exception as e:

            self.source.status = KnowledgeSource.Status.FAILED
            self.source.error_message = str(e)
            self.source.processed_at = timezone.now()

            self.source.save()

            raise