from typing import List, Optional
import pandas as pd


class CandidateLoader:

    def __init__(self, dataframe: Optional[pd.DataFrame] = None):
        self.dataframe = dataframe

    # =====================================================
    # PUBLIC API
    # =====================================================

    def load_targets(
        self,
        positions: Optional[List[str]] = None,
        max_market_value: Optional[float] = None,
        max_age: Optional[int] = None,
        contract_max: Optional[int] = None
    ) -> List[dict]:

        if self.dataframe is None:

            return []

        df = self.dataframe.copy()

        if positions:

            df = df[df["position"].isin(positions)]

        if max_market_value is not None:

            df = df[df["market_value"] <= max_market_value]

        if max_age is not None:

            df = df[df["age"] <= max_age]

        if contract_max is not None:

            df = df[
                df["contract_years_left"] <= contract_max
            ]

        return df.to_dict("records")

    # =====================================================
    # LOAD FROM CSV
    # =====================================================

    @classmethod
    def from_csv(cls, csv_path):

        df = pd.read_csv(csv_path)

        return cls(df)

    # =====================================================
    # LOAD FROM DATAFRAME
    # =====================================================

    @classmethod
    def from_dataframe(cls, dataframe):

        return cls(dataframe)

    # =====================================================
    # ADD PLAYER
    # =====================================================

    def add_player(self, player):

        if self.dataframe is None:

            self.dataframe = pd.DataFrame([player])

        else:

            self.dataframe = pd.concat(

                [

                    self.dataframe,

                    pd.DataFrame([player])

                ],

                ignore_index=True
            )

    # =====================================================
    # SAVE
    # =====================================================

    def save(self, filename):

        if self.dataframe is not None:

            self.dataframe.to_csv(

                filename,

                index=False
            )

    # =====================================================
    # STATS
    # =====================================================

    def summary(self):

        if self.dataframe is None:

            return {}

        return {

            "players": len(self.dataframe),

            "positions":

                self.dataframe["position"]

                .value_counts()

                .to_dict()

        }
    
if __name__ == "__main__":

    from football_data.loader import FootballDataLoader

    loader = FootballDataLoader()

    df = loader.build_global_scouting_dataset()

    candidate_loader = CandidateLoader.from_dataframe(df)

    print(candidate_loader.summary())

    targets = candidate_loader.load_targets(
        positions=["ST"],
        max_age=26
    )

    print(f"{len(targets)} joueurs trouvés")

    for player in targets[:5]:
        print(player["player"])