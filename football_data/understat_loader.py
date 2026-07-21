from football_data.base_loader import BaseLoader

import pandas as pd


class UnderstatLoader(BaseLoader):

    def __init__(self, leagues=None, seasons=None):

        super().__init__(leagues, seasons)

    def load(self):

        return pd.DataFrame()
    
if __name__ == "__main__":

    loader = UnderstatLoader()

    df = loader.load()

    print(df.head())

    print(df.columns)

    print(len(df))