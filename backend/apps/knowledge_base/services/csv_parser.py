from pathlib import Path

import pandas as pd


class CSVParser:
    """
    Service for reading CSV files.
    """

    def __init__(self, file_path):
        self.file_path = Path(file_path)

    def validate_file(self):

        if not self.file_path.exists():
            raise FileNotFoundError(
                f"File not found: {self.file_path}"
            )

        if self.file_path.suffix.lower() != ".csv":
            raise ValueError(
                "Only CSV files are allowed."
            )

    def read(self):

        self.validate_file()

        dataframe = pd.read_csv(
            self.file_path
        )

        return dataframe

    def total_records(self):

        return len(self.read())

    def columns(self):

        return list(self.read().columns)