from typing import Dict, List

import pandas as pd

from .column_mapper import ColumnMapper
from .normalizer import QuestionNormalizer


class KnowledgeValidator:
    """
    Validate uploaded knowledge datasets and
    prepare cleaned records for importing.
    """

    def __init__(self):

        self.mapper = ColumnMapper()
        self.normalizer = QuestionNormalizer()

    def validate(self, dataframe: pd.DataFrame):

        mapped_columns = self.mapper.map_columns(
            dataframe.columns
        )

        missing = self.mapper.missing_required_fields(
            mapped_columns
        )

        if missing:

            return {
                "success": False,
                "errors": [
                    f"Missing required fields: {', '.join(missing)}"
                ],
                "records": [],
            }

        records = []
        errors = []

        duplicate_questions = set()

        for index, row in dataframe.iterrows():

            record = self.prepare_record(
                row,
                mapped_columns,
                index,
                errors,
            )

            if not record:
                continue

            question = record["normalized_question"]

            if question in duplicate_questions:

                errors.append(
                    f"Row {index + 2}: Duplicate question."
                )

                continue

            duplicate_questions.add(question)

            records.append(record)

        return {
            "success": len(errors) == 0,
            "errors": errors,
            "records": records,
        }

    def prepare_record(
        self,
        row,
        mapped_columns,
        row_index,
        errors,
    ):

        question = self.get_value(
            row,
            mapped_columns,
            "question",
        )

        answer = self.get_value(
            row,
            mapped_columns,
            "answer",
        )

        if not question:

            errors.append(
                f"Row {row_index + 2}: Question is required."
            )

            return None

        if not answer:

            errors.append(
                f"Row {row_index + 2}: Answer is required."
            )

            return None

        crop = self.get_value(
            row,
            mapped_columns,
            "crop",
        )

        stage = self.get_value(
            row,
            mapped_columns,
            "stage",
        )

        domain = self.get_value(
            row,
            mapped_columns,
            "domain",
        )

        prepared_by = self.get_value(
            row,
            mapped_columns,
            "prepared_by",
        )

        language = (
            self.get_value(
                row,
                mapped_columns,
                "language",
            )
            or "en"
        )

        normalized_question = (
            self.normalizer.normalize(question)
        )

        search_text = (
            self.normalizer.build_search_text(
                question=question,
                answer=answer,
                crop=crop,
                stage=stage,
                domain=domain,
            )
        )

        return {

            "question": question,

            "normalized_question": normalized_question,

            "answer": answer,

            "crop": crop,

            "stage": stage,

            "domain": domain,

            "prepared_by": prepared_by,

            "language": language.lower(),

            "search_text": search_text,
        }

    @staticmethod
    def get_value(
        row,
        mapped_columns,
        field_name,
    ):

        column = mapped_columns.get(field_name)

        if not column:

            return ""

        value = row[column]

        if pd.isna(value):

            return ""

        return str(value).strip()