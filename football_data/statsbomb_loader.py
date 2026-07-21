from football_data.base_loader import BaseLoader

import pandas as pd


class StatsBombLoader(BaseLoader):

    def __init__(self):

        super().__init__()

    def load(self):

        return pd.DataFrame()
    
if __name__ == "__main__":

    loader = StatsBombLoader()

    df = loader.load()

    print(df.head())

    print(df.columns)

    print(len(df))