from typing import List, Optional
import pandas as pd


class CandidateLoader:
    """
    CandidateLoader

    Gère un dataset de joueurs déjà construit.

    Responsabilités :
    - filtrer les candidats
    - sauvegarder
    - charger
    - statistiques
    """

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
        contract_max: Optional[int] = None,
    ) -> List[dict]:

        if self.dataframe is None or self.dataframe.empty:
            return []

        df = self.dataframe.copy()

        # -----------------------------
        # Position
        # -----------------------------

        if positions and "position" in df.columns:

            df = df[df["position"].isin(positions)]

        # -----------------------------
        # Valeur marchande
        # -----------------------------

        if (
            max_market_value is not None
            and "market_value" in df.columns
        ):

            df = df[df["market_value"] <= max_market_value]

        # -----------------------------
        # Age
        # -----------------------------

        if max_age is not None and "age" in df.columns:

            df = df[df["age"] <= max_age]

        # -----------------------------
        # Contrat
        # -----------------------------

        if (
            contract_max is not None
            and "contract_years_left" in df.columns
        ):

            df = df[
                df["contract_years_left"] <= contract_max
            ]

        return df.to_dict("records")

    # =====================================================
    # LOAD CSV
    # =====================================================

    @classmethod
    def from_csv(cls, csv_path):

        dataframe = pd.read_csv(csv_path)

        return cls(dataframe)

    # =====================================================
    # LOAD DATAFRAME
    # =====================================================

    @classmethod
    def from_dataframe(cls, dataframe):

        return cls(dataframe)

    # =====================================================
    # ADD PLAYER
    # =====================================================

    def add_player(self, player: dict):

        player_df = pd.DataFrame([player])

        if self.dataframe is None:

            self.dataframe = player_df

        else:

            self.dataframe = pd.concat(
                [self.dataframe, player_df],
                ignore_index=True
            )

    # =====================================================
    # REMOVE PLAYER
    # =====================================================

    def remove_player(self, player_name: str):

        if self.dataframe is None:
            return

        if "player" not in self.dataframe.columns:
            return

        self.dataframe = self.dataframe[
            self.dataframe["player"] != player_name
        ]

    # =====================================================
    # SAVE
    # =====================================================

    def save(self, filename):

        if self.dataframe is None:
            return

        self.dataframe.to_csv(
            filename,
            index=False
        )

    # =====================================================
    # SUMMARY
    # =====================================================

    def summary(self):

        if self.dataframe is None:

            return {}

        summary = {

            "players": len(self.dataframe),

            "columns": list(self.dataframe.columns)

        }

        if "position" in self.dataframe.columns:

            summary["positions"] = (

                self.dataframe["position"]

                .value_counts()

                .to_dict()

            )

        return summary

    # =====================================================
    # GET DATAFRAME
    # =====================================================

    def get_dataframe(self):

        return self.dataframe