import os
import pandas as pd
from django.core.management.base import BaseCommand
from django.db import transaction
from apps.knowledge_base.models import Knowledge, KnowledgeSource
from apps.knowledge_base.services.normalizer import QuestionNormalizer
from apps.knowledge_base.services.vector_store import VectorStore


class Command(BaseCommand):
    help = "Import multi-sheet agricultural Q&A dataset from an Excel (.xlsx / .xls) or CSV file into the database and rebuild FAISS index."

    def add_arguments(self, parser):
        parser.add_argument("file_path", type=str, help="Path to the Excel or CSV file")
        parser.add_argument("--clear", action="store_true", help="Clear existing knowledge database before importing")

    @transaction.atomic
    def handle(self, *args, **options):
        file_path = options["file_path"]
        clear_existing = options.get("clear", False)

        if not os.path.exists(file_path):
            self.stdout.write(self.style.ERROR(f"File not found: {file_path}"))
            return

        self.stdout.write(f"Reading file: {file_path}")

        sheets_dict = {}
        try:
            if file_path.endswith(".csv"):
                sheets_dict["Sheet1"] = pd.read_csv(file_path)
            else:
                excel_file = pd.ExcelFile(file_path)
                for sheet_name in excel_file.sheet_names:
                    df_sheet = pd.read_excel(excel_file, sheet_name=sheet_name)
                    if len(df_sheet) > 0:
                        sheets_dict[sheet_name] = df_sheet
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error reading file: {e}"))
            return

        if clear_existing:
            self.stdout.write(self.style.WARNING("Clearing existing Knowledge records..."))
            Knowledge.objects.all().delete()

        source, _ = KnowledgeSource.objects.get_or_create(
            title=f"Imported Dataset ({os.path.basename(file_path)})",
            defaults={
                "source_type": KnowledgeSource.SourceType.EXCEL,
                "source_name": os.path.basename(file_path),
                "version": "1.0",
                "status": KnowledgeSource.Status.COMPLETED,
            },
        )

        normalizer = QuestionNormalizer()
        total_created = 0

        for sheet_name, df in sheets_dict.items():
            self.stdout.write(f"Processing sheet '{sheet_name}' with {len(df)} rows...")
            column_map = {}
            for col in df.columns:
                clean_col = str(col).strip().lower()
                if "crop" in clean_col:
                    column_map[col] = "crop"
                elif "question" in clean_col or "सवाल" in clean_col or "प्रश्न" in clean_col:
                    column_map[col] = "question"
                elif "answer" in clean_col or "जवाब" in clean_col or "उत्तर" in clean_col:
                    column_map[col] = "answer"
                elif "stage" in clean_col:
                    column_map[col] = "stage"
                elif "category" in clean_col:
                    column_map[col] = "category"
                elif "keywords" in clean_col:
                    column_map[col] = "keywords"

            df = df.rename(columns=column_map)

            if "question" not in df.columns or "answer" not in df.columns:
                self.stdout.write(self.style.WARNING(f"Skipping sheet '{sheet_name}' - Missing required Question/Answer columns."))
                continue

            for idx, row in df.iterrows():
                question = str(row.get("question", "")).strip()
                answer = str(row.get("answer", "")).strip()

                if not question or not answer or question == "nan" or answer == "nan":
                    continue

                crop = str(row.get("crop", sheet_name)).strip()
                if crop == "nan" or not crop:
                    crop = sheet_name

                stage = str(row.get("stage", "General")).strip()
                if stage == "nan": stage = "General"

                category = str(row.get("category", "General")).strip()
                if category == "nan": category = "General"

                keywords = str(row.get("keywords", "")).strip()
                if keywords == "nan": keywords = ""

                norm_q = normalizer.normalize(question)
                search_text = normalizer.build_search_text(
                    question=question,
                    answer=answer,
                    crop=crop,
                    stage=stage,
                    domain="Agronomy",
                )

                Knowledge.objects.create(
                    knowledge_source=source,
                    crop=crop,
                    category=Knowledge.Category.GENERAL,
                    stage=stage,
                    question=question,
                    normalized_question=norm_q,
                    answer=answer,
                    keywords=keywords,
                    search_text=search_text,
                    language="hi",
                )
                total_created += 1

        self.stdout.write(self.style.SUCCESS(f"Successfully imported {total_created} knowledge records into database across all sheets."))

        # Rebuild FAISS Vector Index
        self.stdout.write("Rebuilding FAISS Vector Embeddings index...")
        vs = VectorStore()
        vs.build_index()
        vs.save()
        self.stdout.write(self.style.SUCCESS("FAISS Index rebuild & save complete!"))
