import pandas as pd

from football_data.fbref_loader import FBrefLoader
from football_data.transfermarkt_loader import TransfermarktLoader
from football_data.statsbomb_loader import StatsBombLoader
from football_data.understat_loader import UnderstatLoader
from football_data.candidate_loader import CandidateLoader


class FootballDataLoader:

    def __init__(self, leagues=None, seasons=None):

        self.leagues = leagues or ["ESP-La Liga"]
        self.seasons = seasons or ["2425"]

        self.fbref_loader = FBrefLoader(
            self.leagues,
            self.seasons
        )

        self.transfermarkt_loader = TransfermarktLoader(
            self.leagues,
            self.seasons
        )

        self.understat_loader = UnderstatLoader(
            self.leagues,
            self.seasons
        )

        self.statsbomb_loader = StatsBombLoader()

    # =====================================================
    # GLOBAL SCOUTING DATASET
    # =====================================================

    def build_global_scouting_dataset(self):

        print("Loading FBref...")

        fbref_df = self.fbref_loader.load()

        print("Loading Transfermarkt...")

        market_df = self.transfermarkt_loader.load()

        print("Loading Understat...")

        understat_df = self.understat_loader.load()

        dataset = fbref_df.copy()

        if not market_df.empty:

            dataset = dataset.merge(

                market_df,

                on="player",

                how="left"
            )

        if not understat_df.empty:

            dataset = dataset.merge(

                understat_df,

                on="player",

                how="left"
            )

        dataset = dataset.drop_duplicates(
            subset=["player"]
        )

        return dataset

        # =====================================================
    # CANDIDATE LOADER
    # =====================================================

    def load_global_candidates(self):

        dataset = self.build_global_scouting_dataset()

        return CandidateLoader.from_dataframe(
            dataset
        )

if __name__ == "__main__":

    loader = FootballDataLoader()

    df = loader.load()

    print(df.head())

    print(df.columns)

    print(len(df))