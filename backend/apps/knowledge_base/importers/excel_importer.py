import pandas as pd


class ExcelImporter:

    @staticmethod
    def read_excel(file):
        dataframe = pd.read_excel(file)

        return dataframe.to_dict(orient="records")