"""
Smart Column Mapper

This module maps different dataset column names to the
internal Farmer Voice AI schema.

Example:

Crop Name      -> crop
Crop           -> crop
Crop_Name      -> crop

Question       -> question
Query          -> question

Answer         -> answer
Response       -> answer
"""

from typing import Dict, List, Optional


class ColumnMapper:
    """
    Smart column mapper for different dataset formats.
    """

    COLUMN_ALIASES: Dict[str, List[str]] = {

        "crop": [
            "crop",
            "crop name",
            "crop_name",
            "cropname",
        ],

        "question": [
            "question",
            "query",
            "user question",
            "faq",
        ],

        "answer": [
            "answer",
            "response",
            "solution",
        ],

        "stage": [
            "stage",
            "growth stage",
        ],

        "domain": [
            "domain",
            "category",
        ],

        "prepared_by": [
            "prepare by",
            "prepared by",
            "author",
        ],

        "language": [
            "language",
            "lang",
        ],
    }

    @staticmethod
    def normalize_column(column: str) -> str:
        """
        Normalize column name.

        Example:
        Crop_Name -> crop name
        USER QUESTION -> user question
        """

        return (
            column.strip()
            .lower()
            .replace("_", " ")
            .replace("-", " ")
        )

    @classmethod
    def map_columns(cls, dataframe_columns) -> Dict[str, str]:
        """
        Returns:

        {
            "crop": "Crop Name",
            "question": "Question",
            "answer": "Answer"
        }
        """

        mapped_columns = {}

        for original_column in dataframe_columns:

            normalized = cls.normalize_column(original_column)

            for db_field, aliases in cls.COLUMN_ALIASES.items():

                if normalized in aliases:
                    mapped_columns[db_field] = original_column

        return mapped_columns

    @staticmethod
    def get_required_fields():
        """
        Required database fields.
        """

        return [
            "question",
            "answer",
        ]

    @classmethod
    def missing_required_fields(cls, mapped_columns) -> List[str]:

        missing = []

        for field in cls.get_required_fields():

            if field not in mapped_columns:
                missing.append(field)

        return missing

    @classmethod
    def has_required_fields(cls, mapped_columns) -> bool:

        return len(cls.missing_required_fields(mapped_columns)) == 0

    @classmethod
    def get_column(
        cls,
        mapped_columns,
        field_name,
    ) -> Optional[str]:

        return mapped_columns.get(field_name)