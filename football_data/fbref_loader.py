from football_data.base_loader import BaseLoader

import soccerdata as sd
import pandas as pd


class FBrefLoader(BaseLoader):

    def __init__(self, leagues=None, seasons=None):

        super().__init__(leagues, seasons)

        self.scraper = sd.FBref(

            leagues=self.leagues,

            seasons=self.seasons
        )

    def load(self):

        df = self.scraper.read_player_season_stats(
            stat_type="standard"
        )

        return df.reset_index()
    
if __name__ == "__main__":

    loader = FBrefLoader()

    df = loader.load()

    print(df.head())

    print(df.columns)

    print(len(df))