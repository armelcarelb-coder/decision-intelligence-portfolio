from __future__ import annotations

from pathlib import Path
from typing import Optional, List

import duckdb
import pandas as pd
import urllib.request
import shutil


class HistoricalTransferLoader:
    """
    Charge et normalise l'historique des transferts
    provenant du dataset dcaribou/transfermarkt-datasets.

    Architecture :

        Transfermarkt Dataset
                |
                v
        DuckDB local
                |
                v
        transfers
                +
        players
                |
                v
        normalisation
                |
                v
        DataFrame historique
                |
                v
        Parquet analytique

    Important :
        Ce loader ne construit PAS encore la variable
        "transfer_success".

        Cette responsabilité appartiendra à une étape
        ultérieure : TransferOutcomeBuilder.
    """

    # ==========================================================
    # SOURCE OFFICIELLE
    # ==========================================================

    DEFAULT_SOURCE_URL = (
        "https://pub-e682421888d945d684bcae8890b0ec20.r2.dev/"
        "data/transfermarkt-datasets.duckdb"
    )

    # ==========================================================
    # CHEMINS LOCAUX
    # ==========================================================

    DEFAULT_DATABASE_PATH = (
        "data/historical/"
        "transfermarkt-datasets.duckdb"
    )

    DEFAULT_PARQUET_PATH = (
        "data/historical/"
        "historical_transfers.parquet"
    )

    # ==========================================================
    # INITIALISATION
    # ==========================================================

    def __init__(
        self,
        database_path: Optional[str] = None,
        parquet_path: Optional[str] = None,
        source_url: Optional[str] = None,
        seasons: Optional[List[str]] = None,
        offline: bool = False,
    ):
        """
        Parameters
        ----------
        database_path :
            Chemin vers la base DuckDB locale.

        parquet_path :
            Chemin vers le dataset historique normalisé.

        source_url :
            URL de téléchargement du dataset DuckDB.

        seasons :
            Liste optionnelle des saisons à conserver.

        offline :
            Si True, aucun téléchargement réseau ne sera tenté.
        """

        self.database_path = Path(
            database_path
            if database_path
            else self.DEFAULT_DATABASE_PATH
        )

        self.parquet_path = Path(
            parquet_path
            if parquet_path
            else self.DEFAULT_PARQUET_PATH
        )

        self.source_url = (
            source_url
            if source_url
            else self.DEFAULT_SOURCE_URL
        )

        self.seasons = seasons

        self.offline = offline

        self.dataframe: Optional[pd.DataFrame] = None

    # ==========================================================
    # PUBLIC API
    # ==========================================================

    def load(
        self,
        prefer_parquet: bool = False
    ) -> pd.DataFrame:
        """
        Charge les données historiques.

        Ordre :

        prefer_parquet=True
            ↓
        Parquet
            ↓
        DuckDB

        Sinon :

        DuckDB
            ↓
        normalisation
            ↓
        Parquet
        """

        print(
            "[HistoricalTransferLoader] "
            "Chargement de l'historique..."
        )

        # ------------------------------------------------------
        # 1. PARQUET
        # ------------------------------------------------------

        if (
            prefer_parquet
            and self.parquet_path.exists()
        ):

            print(
                "[HistoricalTransferLoader] "
                "Lecture du Parquet local..."
            )

            df = pd.read_parquet(
                self.parquet_path
            )

            self.dataframe = df

            return df

        # ------------------------------------------------------
        # 2. DUCKDB
        # ------------------------------------------------------

        if not self.database_path.exists():

            if self.offline:

                raise FileNotFoundError(
                    "Dataset historique absent.\n\n"
                    f"Base attendue : "
                    f"{self.database_path}\n\n"
                    "Le loader est en mode offline=True, "
                    "aucun téléchargement ne sera effectué."
                )

            self.acquire()

        # ------------------------------------------------------
        # 3. QUERY
        # ------------------------------------------------------

        df = self._query_database()

        # ------------------------------------------------------
        # 4. NORMALISATION
        # ------------------------------------------------------

        df = self._normalize(df)

        # ------------------------------------------------------
        # 5. FILTRE SAISON
        # ------------------------------------------------------

        if self.seasons:

            df = self._filter_seasons(df)

        self.dataframe = df

        return df

    # ==========================================================
    # ACQUISITION
    # ==========================================================

    def acquire(
        self,
        force: bool = False
    ):
        """
        Télécharge la base DuckDB officielle.

        Cette méthode est volontairement séparée de load().
        """

        if (
            self.database_path.exists()
            and not force
        ):

            print(
                "[HistoricalTransferLoader] "
                "Base DuckDB déjà présente."
            )

            return self.database_path

        print(
            "[HistoricalTransferLoader] "
            "Acquisition du dataset Transfermarkt..."
        )

        self.database_path.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        temporary_path = (
            self.database_path.with_suffix(
                ".download"
            )
        )

        # ------------------------------------------------------
        # USER AGENT
        # ------------------------------------------------------

        request = urllib.request.Request(
            self.source_url,
            headers={
                "User-Agent":
                    "football-ai-decision-intelligence/1.0",
                "Accept":
                    "application/octet-stream,*/*",
            }
        )

        try:

            with urllib.request.urlopen(
                request,
                timeout=120
            ) as response:

                with open(
                    temporary_path,
                    "wb"
                ) as output:

                    shutil.copyfileobj(
                        response,
                        output
                    )

            # --------------------------------------------------
            # VALIDATION DU FICHIER
            # --------------------------------------------------

            if not temporary_path.exists():

                raise RuntimeError(
                    "Le téléchargement n'a produit "
                    "aucun fichier."
                )

            file_size = (
                temporary_path.stat().st_size
            )

            if file_size < 1024:

                raise RuntimeError(
                    "Le fichier téléchargé semble invalide "
                    f"({file_size} octets)."
                )

            temporary_path.replace(
                self.database_path
            )

        except Exception as exc:

            if temporary_path.exists():
                temporary_path.unlink()

            raise RuntimeError(
                "\nImpossible d'acquérir le dataset "
                "Transfermarkt.\n\n"
                f"URL : {self.source_url}\n\n"
                "Si le serveur retourne HTTP 403, "
                "télécharge manuellement le fichier DuckDB "
                "depuis le dépôt officiel puis place-le ici :\n\n"
                f"{self.database_path}\n"
            ) from exc

        print(
            "[HistoricalTransferLoader] "
            "Dataset téléchargé avec succès."
        )

        print(
            f"[HistoricalTransferLoader] "
            f"Fichier : {self.database_path}"
        )

        return self.database_path

    # ==========================================================
    # DATABASE QUERY
    # ==========================================================

    def _query_database(self) -> pd.DataFrame:

        print(
            "[HistoricalTransferLoader] "
            "Connexion à DuckDB..."
        )

        connection = duckdb.connect(
            str(self.database_path),
            read_only=True
        )

        try:

            # --------------------------------------------------
            # Vérification des tables
            # --------------------------------------------------

            tables = connection.execute(
                "SHOW TABLES"
            ).fetchdf()

            available_tables = set(
                tables["name"].tolist()
            )

            required_tables = {
                "transfers",
                "players",
            }

            missing = (
                required_tables
                - available_tables
            )

            if missing:

                raise RuntimeError(
                    "Tables manquantes dans le dataset DuckDB : "
                    f"{sorted(missing)}"
                )

            # --------------------------------------------------
            # QUERY
            # --------------------------------------------------

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

                    p.name AS player_profile_name,

                    p.position,

                    p.sub_position,

                    p.foot,

                    p.date_of_birth,

                    p.country_of_citizenship,

                    p.country_of_birth,

                    p.height_in_cm,

                    p.current_club_id,

                    p.current_club_name,

                    p.contract_expiration_date,

                    p.highest_market_value_in_eur

                FROM transfers AS t

                LEFT JOIN players AS p

                    ON t.player_id = p.player_id

                ORDER BY
                    t.transfer_date,
                    t.player_id
            """

            df = connection.execute(
                query
            ).fetchdf()

            return df

        finally:

            connection.close()

    # ==========================================================
    # NORMALISATION
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

        df["contract_expiration_date"] = pd.to_datetime(
            df["contract_expiration_date"],
            errors="coerce"
        )

        # ------------------------------------------------------
        # NUMERIC
        # ------------------------------------------------------

        numeric_columns = [
            "player_id",
            "from_club_id",
            "to_club_id",
            "transfer_fee",
            "market_value_in_eur",
            "highest_market_value_in_eur",
            "height_in_cm",
        ]

        for column in numeric_columns:

            if column in df.columns:

                df[column] = pd.to_numeric(
                    df[column],
                    errors="coerce"
                )

        # ------------------------------------------------------
        # AGE AT TRANSFER
        # ------------------------------------------------------

        df["age_at_transfer"] = (
            (
                df["transfer_date"]
                - df["date_of_birth"]
            ).dt.days
            / 365.25
        )

        df["age_at_transfer"] = (
            df["age_at_transfer"]
            .round(2)
        )

        # ------------------------------------------------------
        # FREE TRANSFER
        # ------------------------------------------------------

        # IMPORTANT :
        #
        # 0    = free transfer
        # NULL = unknown fee
        #
        # On ne transforme donc PAS NULL en 0.

        df["is_free_transfer"] = (
            df["transfer_fee"] == 0
        )

        df["transfer_fee_known"] = (
            df["transfer_fee"].notna()
        )

        # ------------------------------------------------------
        # TRANSFER FEE / MARKET VALUE
        # ------------------------------------------------------

        df["fee_to_market_value_ratio"] = (
            df["transfer_fee"]
            / df["market_value_in_eur"]
        )

        df[
            "fee_to_market_value_ratio"
        ] = (
            df[
                "fee_to_market_value_ratio"
            ]
            .replace(
                [
                    float("inf"),
                    -float("inf")
                ],
                pd.NA
            )
        )

        # ------------------------------------------------------
        # MARKET PREMIUM
        # ------------------------------------------------------

        df["transfer_premium_eur"] = (
            df["transfer_fee"]
            - df["market_value_in_eur"]
        )

        # ------------------------------------------------------
        # MARKET PREMIUM %
        # ------------------------------------------------------

        df["transfer_premium_pct"] = (
            (
                df["transfer_fee"]
                - df["market_value_in_eur"]
            )
            / df["market_value_in_eur"]
        )

        # ------------------------------------------------------
        # CONTRACT AGE
        # ------------------------------------------------------

        df["contract_years_after_transfer"] = (
            (
                df["contract_expiration_date"]
                - df["transfer_date"]
            ).dt.days
            / 365.25
        )

        df[
            "contract_years_after_transfer"
        ] = (
            df[
                "contract_years_after_transfer"
            ].round(2)
        )

        # ------------------------------------------------------
        # PLAYER NAME QUALITY
        # ------------------------------------------------------

        df["player_name_normalized"] = (
            df["player_name"]
            .astype("string")
            .str.strip()
            .str.lower()
        )

        # ------------------------------------------------------
        # CLUB NAME NORMALIZATION
        # ------------------------------------------------------

        for column in [
            "from_club_name",
            "to_club_name",
        ]:

            df[
                f"{column}_normalized"
            ] = (
                df[column]
                .astype("string")
                .str.strip()
                .str.lower()
            )

        # ------------------------------------------------------
        # DUPLICATES
        # ------------------------------------------------------

        duplicate_columns = [
            "player_id",
            "transfer_date",
            "from_club_id",
            "to_club_id",
        ]

        df = df.drop_duplicates(
            subset=duplicate_columns
        )

        # ------------------------------------------------------
        # INVALID RECORDS
        # ------------------------------------------------------

        df = df[
            df["player_id"].notna()
        ]

        df = df[
            df["transfer_date"].notna()
        ]

        # ------------------------------------------------------
        # SORT
        # ------------------------------------------------------

        df = df.sort_values(
            [
                "player_id",
                "transfer_date",
            ]
        )

        return df.reset_index(
            drop=True
        )

    # ==========================================================
    # SEASON FILTER
    # ==========================================================

    def _filter_seasons(
        self,
        df: pd.DataFrame
    ) -> pd.DataFrame:

        if not self.seasons:

            return df

        seasons = {
            str(season)
            for season in self.seasons
        }

        return df[
            df["transfer_season"]
            .astype(str)
            .isin(seasons)
        ].reset_index(
            drop=True
        )

    # ==========================================================
    # SAVE PARQUET
    # ==========================================================

    def save(
        self,
        path: Optional[str] = None
    ):

        if self.dataframe is None:

            raise ValueError(
                "Aucune donnée chargée. "
                "Appelez load() avant save()."
            )

        output_path = Path(
            path
            if path
            else self.parquet_path
        )

        output_path.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        self.dataframe.to_parquet(
            output_path,
            index=False
        )

        print(
            "[HistoricalTransferLoader] "
            f"Dataset normalisé sauvegardé : "
            f"{output_path}"
        )

        return output_path

    # ==========================================================
    # SUMMARY
    # ==========================================================

    def summary(self):

        if self.dataframe is None:

            return {}

        df = self.dataframe

        return {

            "rows": len(df),

            "unique_players": (
                df["player_id"]
                .nunique()
            ),

            "unique_from_clubs": (
                df["from_club_id"]
                .nunique()
            ),

            "unique_to_clubs": (
                df["to_club_id"]
                .nunique()
            ),

            "free_transfers": int(
                df["is_free_transfer"]
                .sum()
            ),

            "known_fees": int(
                df["transfer_fee_known"]
                .sum()
            ),

            "unknown_fees": int(
                df["transfer_fee_known"]
                .eq(False)
                .sum()
            ),

            "date_min": (
                df["transfer_date"]
                .min()
            ),

            "date_max": (
                df["transfer_date"]
                .max()
            ),

            "missing_player_profile": int(
                df["player_profile_name"]
                .isna()
                .sum()
            ),

            "missing_position": int(
                df["position"]
                .isna()
                .sum()
            ),

            "missing_market_value": int(
                df["market_value_in_eur"]
                .isna()
                .sum()
            ),

            "missing_age": int(
                df["age_at_transfer"]
                .isna()
                .sum()
            ),
        }

    # ==========================================================
    # DATA QUALITY
    # ==========================================================

    def quality_report(self):

        if self.dataframe is None:

            raise ValueError(
                "Aucune donnée chargée."
            )

        df = self.dataframe

        report = []

        for column in df.columns:

            report.append(
                {
                    "column": column,
                    "dtype": str(
                        df[column].dtype
                    ),
                    "rows": len(df),
                    "missing": int(
                        df[column]
                        .isna()
                        .sum()
                    ),
                    "missing_pct": round(
                        df[column]
                        .isna()
                        .mean()
                        * 100,
                        2
                    ),
                    "unique": int(
                        df[column]
                        .nunique(
                            dropna=True
                        )
                    ),
                }
            )

        return pd.DataFrame(
            report
        )


# ==============================================================
# TEST DU MODULE
# ==============================================================

if __name__ == "__main__":

    print()
    print("=" * 70)
    print("TEST HISTORICAL TRANSFER LOADER")
    print("=" * 70)

    # ----------------------------------------------------------
    # MODE NORMAL
    # ----------------------------------------------------------

    loader = HistoricalTransferLoader(
        offline=False
    )

    try:

        df = loader.load()

        print()
        print("DATASET CHARGÉ")
        print("-" * 70)

        print(
            f"Shape : {df.shape}"
        )

        print()
        print("SUMMARY")
        print("-" * 70)

        for key, value in (
            loader.summary()
            .items()
        ):

            print(
                f"{key:30} : {value}"
            )

        print()
        print("COLONNES")
        print("-" * 70)

        print(
            df.columns.tolist()
        )

        print()
        print("APERÇU")
        print("-" * 70)

        columns = [
            "player_id",
            "player_name",
            "transfer_date",
            "transfer_season",
            "from_club_name",
            "to_club_name",
            "transfer_fee",
            "market_value_in_eur",
            "age_at_transfer",
            "position",
            "is_free_transfer",
        ]

        available = [
            column
            for column in columns
            if column in df.columns
        ]

        print(
            df[available]
            .head(10)
            .to_string(
                index=False
            )
        )

        # ------------------------------------------------------
        # QUALITY
        # ------------------------------------------------------

        print()
        print("DATA QUALITY")
        print("-" * 70)

        quality = (
            loader
            .quality_report()
        )

        print(
            quality[
                [
                    "column",
                    "missing",
                    "missing_pct",
                    "unique",
                ]
            ]
            .to_string(
                index=False
            )
        )

        # ------------------------------------------------------
        # SAVE
        # ------------------------------------------------------

        loader.save()

        print()
        print(
            "✓ HistoricalTransferLoader "
            "TEST PASSED"
        )

    except Exception as exc:

        print()
        print(
            "✗ HistoricalTransferLoader "
            "TEST FAILED"
        )

        print(
            f"\nErreur : {exc}"
        )

        raise