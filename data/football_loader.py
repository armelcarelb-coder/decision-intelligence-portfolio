import pandas as pd
from datetime import datetime

from football_data.fbref_loader import FBrefLoader
from football_data.transfermarkt_loader import TransfermarktLoader
from football_data.statsbomb_loader import StatsBombLoader


class FootballDataLoader:

    def __init__(
        self,
        leagues=None,
        seasons=None
    ):

        self.leagues = leagues or ["ESP-La Liga"]

        self.seasons = seasons or ["2425"]

        self.fbref_loader = FBrefLoader(

            leagues=self.leagues,

            seasons=self.seasons

        )

        self.transfermarkt_loader = TransfermarktLoader(

            leagues=self.leagues,

            seasons=self.seasons

        )

        self.statsbomb_loader = StatsBombLoader()

    # =====================================================
    # GLOBAL DATASET
    # =====================================================

    def build_global_scouting_dataset(self):

        print("\nLoading FBref...")

        df_fbref = self.fbref_loader.load()

        print(f"{len(df_fbref)} players")

        print("\nLoading Transfermarkt...")

        df_market = self.transfermarkt_loader.load()

        print(f"{len(df_market)} players")

        # -------------------------------------

        df = pd.merge(

            df_fbref,

            df_market,

            on="player",

            how="left"

        )

        # -------------------------------------

        if "contract_expires" in df.columns:

            current_year = datetime.now().year

            df["contract_years_left"] = (

                pd.to_numeric(

                    df["contract_expires"],

                    errors="coerce"

                )

                - current_year

            )

        else:

            df["contract_years_left"] = None

        # -------------------------------------

        df = df.drop_duplicates(

            subset=["player"]

        )

        print()

        print("Dataset created")

        print()

        print("Players :", len(df))

        print()

        print(df.columns.tolist())

        return df