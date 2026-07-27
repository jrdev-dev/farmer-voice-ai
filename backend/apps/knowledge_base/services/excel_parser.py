from pathlib import Path

import pandas as pd


class ExcelParser:
    """
    Service for reading and validating Excel files.
    """

    SUPPORTED_EXTENSIONS = [".xlsx", ".xls"]

    def __init__(self, file_path):
        self.file_path = Path(file_path)

    def validate_file(self):
        """
        Validate file existence and extension.
        """

        if not self.file_path.exists():
            raise FileNotFoundError(
                f"File not found: {self.file_path}"
            )

        if self.file_path.suffix.lower() not in self.SUPPORTED_EXTENSIONS:
            raise ValueError(
                f"Unsupported file type: {self.file_path.suffix}"
            )

    def read(self):
        """
        Read Excel file and return pandas DataFrame.
        """

        self.validate_file()

        dataframe = pd.read_excel(
            self.file_path,
            engine="openpyxl",
        )

        return dataframe

    def total_records(self):
        """
        Return total rows in Excel.
        """

        dataframe = self.read()

        return len(dataframe)

    def columns(self):
        """
        Return column names.
        """

        dataframe = self.read()

        return list(dataframe.columns)