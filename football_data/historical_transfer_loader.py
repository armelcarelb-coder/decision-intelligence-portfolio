from __future__ import annotations

from pathlib import Path
from typing import Optional, List

import duckdb
import pandas as pd
import urllib.request


class HistoricalTransferLoader:
    """
    Loader de l'historique des transferts Transfermarkt.

    Source :
        dcaribou/transfermarkt-datasets

    Architecture :

        Dataset Transfermarkt
                ↓
        DuckDB local
                ↓
        transfers
                +
        players
                ↓
        normalisation
                ↓
        DataFrame historique
    """

    DEFAULT_URL = (
        "https://pub-e682421888d945d684bcae8890b0ec20.r2.dev/"
        "data/transfermarkt-datasets.duckdb"
    )

    DEFAULT_LOCAL_PATH = (
        "data/historical/"
        "transfermarkt-datasets.duckdb"
    )

    def __init__(
        self,
        local_path: Optional[str] = None,
        source_url: Optional[str] = None,
        seasons: Optional[List[str]] = None,
    ):

        self.local_path = Path(
            local_path
            if local_path
            else self.DEFAULT_LOCAL_PATH
        )

        self.source_url = (
            source_url
            if source_url
            else self.DEFAULT_URL
        )

        self.seasons = seasons

        self.dataframe: Optional[pd.DataFrame] = None

    # ==========================================================
    # PUBLIC API
    # ==========================================================

    def load(self) -> pd.DataFrame:

        print(
            "[HistoricalTransferLoader] "
            "Chargement de l'historique des transferts..."
        )

        self._ensure_local_database()

        df = self._query_database()

        df = self._normalize(df)

        if self.seasons:
            df = self._filter_seasons(df)

        self.dataframe = df

        print(
            "[HistoricalTransferLoader] "
            f"{len(df):,} transferts chargés."
        )

        return df

    # ==========================================================
    # DOWNLOAD DATABASE
    # ==========================================================

    def _ensure_local_database(self):

        if self.local_path.exists():

            print(
                "[HistoricalTransferLoader] "
                "Base DuckDB locale trouvée."
            )

            return

        print(
            "[HistoricalTransferLoader] "
            "Base DuckDB absente."
        )

        print(
            "[HistoricalTransferLoader] "
            "Téléchargement depuis Transfermarkt dataset..."
        )

        self.local_path.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        try:

            urllib.request.urlretrieve(
                self.source_url,
                self.local_path
            )

        except Exception as exc:

            if self.local_path.exists():
                self.local_path.unlink()

            raise RuntimeError(
                "Impossible de télécharger le dataset "
                "Transfermarkt."
            ) from exc

        print(
            "[HistoricalTransferLoader] "
            f"Base téléchargée : {self.local_path}"
        )

    # ==========================================================
    # QUERY DATABASE
    # ==========================================================

    def _query_database(self) -> pd.DataFrame:

        print(
            "[HistoricalTransferLoader] "
            "Interrogation de la base DuckDB..."
        )

        con = duckdb.connect(
            str(self.local_path),
            read_only=True
        )

        try:

            query = """
                SELECT

                    t.player_id,
                    t.player_name,
                    t.transfer_date,
                    t.transfer_season,

                    t.from_club_id,
                    t.from_club_name,

                    t.to_club_id,
                    t.to_club_name,

                    t.transfer_fee,
                    t.market_value_in_eur,

                    p.position,
                    p.sub_position,
                    p.date_of_birth,
                    p.country_of_citizenship

                FROM transfers AS t

                LEFT JOIN players AS p

                    ON t.player_id = p.player_id

                ORDER BY t.transfer_date
            """

            return con.execute(
                query
            ).fetchdf()

        finally:

            con.close()

    # ==========================================================
    # NORMALIZATION
    # ==========================================================

    def _normalize(
        self,
        df: pd.DataFrame
    ) -> pd.DataFrame:

        if df.empty:
            return df

        df = df.copy()

        # ------------------------------------------------------
        # DATES
        # ------------------------------------------------------

        df["transfer_date"] = pd.to_datetime(
            df["transfer_date"],
            errors="coerce"
        )

        df["date_of_birth"] = pd.to_datetime(
            df["date_of_birth"],
            errors="coerce"
        )

        # ------------------------------------------------------
        # NUMERIC TYPES
        # ------------------------------------------------------

        df["transfer_fee"] = pd.to_numeric(
            df["transfer_fee"],
            errors="coerce"
        )

        df["market_value_in_eur"] = pd.to_numeric(
            df["market_value_in_eur"],
            errors="coerce"
        )

        # ------------------------------------------------------
        # AGE AT TRANSFER
        # ------------------------------------------------------

        df["age_at_transfer"] = (
            (
                df["transfer_date"]
                - df["date_of_birth"]
            ).dt.days / 365.25
        ).round(2)

        # ------------------------------------------------------
        # FREE TRANSFER
        # ------------------------------------------------------

        df["is_free_transfer"] = (
            df["transfer_fee"]
            .fillna(0)
            == 0
        )

        # ------------------------------------------------------
        # FEE / MARKET VALUE
        # ------------------------------------------------------

        df["fee_to_market_value_ratio"] = (
            df["transfer_fee"]
            / df["market_value_in_eur"]
        )

        df["fee_to_market_value_ratio"] = (
            df["fee_to_market_value_ratio"]
            .replace(
                [float("inf"), -float("inf")],
                pd.NA
            )
        )

        # ------------------------------------------------------
        # REMOVE INVALID CLUB MOVES
        # ------------------------------------------------------

        df = df[
            df["from_club_id"]
            != df["to_club_id"]
        ]

        # ------------------------------------------------------
        # DUPLICATES
        # ------------------------------------------------------

        df = df.drop_duplicates(
            subset=[
                "player_id",
                "transfer_date",
                "from_club_id",
                "to_club_id"
            ]
        )

        return df.reset_index(drop=True)

    # ==========================================================
    # SEASON FILTER
    # ==========================================================

    def _filter_seasons(
        self,
        df: pd.DataFrame
    ) -> pd.DataFrame:

        if "transfer_season" not in df.columns:
            return df

        seasons = {
            str(season)
            for season in self.seasons
        }

        return df[
            df["transfer_season"]
            .astype(str)
            .isin(seasons)
        ].reset_index(drop=True)

    # ==========================================================
    # SAVE
    # ==========================================================

    def save(
        self,
        path: str = (
            "data/historical/"
            "historical_transfers.parquet"
        )
    ):

        if self.dataframe is None:

            raise ValueError(
                "Aucune donnée chargée."
            )

        output = Path(path)

        output.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        if output.suffix == ".parquet":

            self.dataframe.to_parquet(
                output,
                index=False
            )

        elif output.suffix == ".csv":

            self.dataframe.to_csv(
                output,
                index=False
            )

        else:

            raise ValueError(
                "Format non supporté."
            )

        print(
            "[HistoricalTransferLoader] "
            f"Sauvegardé : {output}"
        )

    # ==========================================================
    # SUMMARY
    # ==========================================================

    def summary(self):

        if self.dataframe is None:
            return {}

        df = self.dataframe

        return {

            "transfers": len(df),

            "players": (
                df["player_id"]
                .nunique()
            ),

            "clubs_from": (
                df["from_club_id"]
                .nunique()
            ),

            "clubs_to": (
                df["to_club_id"]
                .nunique()
            ),

            "free_transfers": int(
                df["is_free_transfer"]
                .sum()
            ),

            "date_min": (
                df["transfer_date"]
                .min()
            ),

            "date_max": (
                df["transfer_date"]
                .max()
            )
        }


# ==============================================================
# TEST
# ==============================================================

if __name__ == "__main__":

    loader = HistoricalTransferLoader()

    df = loader.load()

    print("\n")
    print("=" * 70)
    print("HISTORICAL TRANSFER DATASET")
    print("=" * 70)

    print("\nShape :")
    print(df.shape)

    print("\nRésumé :")
    print(loader.summary())

    print("\nColonnes :")
    print(df.columns.tolist())

    print("\nAperçu :")

    print(
        df[
            [
                "player_id",
                "player_name",
                "transfer_date",
                "from_club_name",
                "to_club_name",
                "transfer_fee",
                "market_value_in_eur",
                "age_at_transfer"
            ]
        ].head(10)
    )