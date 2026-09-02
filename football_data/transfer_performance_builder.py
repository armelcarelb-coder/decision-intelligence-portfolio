from __future__ import annotations

from pathlib import Path
from typing import Optional

import pandas as pd


# ============================================================================
# CONFIGURATION
# ============================================================================

PERFORMANCE_INPUT_PATH = Path("data/performances/performance_sample.csv")
PERFORMANCE_SCORED_PATH = Path("data/performances/performance_scored.csv")

MIN_MINUTES = 900

PRE_MONTHS = 36
POST_MONTHS = 18

DEFAULT_DATABASE_PATHS = [
    Path("dbt/duck.db"),
    Path("data/transfermarkt-datasets.duckdb"),
    Path("transfermarkt-datasets.duckdb"),
]


# ============================================================================
# HISTORICAL TRANSFER LOADER
# ============================================================================

class HistoricalTransferLoader:
    """
    Charge l'historique des transferts depuis DuckDB.

    Architecture :
        HistoricalTransferLoader
                ↓
        TransferPerformanceBuilder
    """

    def __init__(self, database_path: Optional[Path] = None):
        self.database_path = database_path

    def _resolve_database_path(self) -> Path:
        if self.database_path is not None:
            path = Path(self.database_path)

            if not path.exists():
                raise FileNotFoundError(
                    f"Base DuckDB introuvable : {path}"
                )

            return path

        for candidate in DEFAULT_DATABASE_PATHS:
            if candidate.exists():
                return candidate

        raise FileNotFoundError(
            "Aucune base DuckDB trouvée. Chemins testés : "
            + ", ".join(str(path) for path in DEFAULT_DATABASE_PATHS)
        )

    def load(self) -> pd.DataFrame:
        print("[HistoricalTransferLoader] Chargement de l'historique...")

        try:
            import duckdb
        except ImportError as exc:
            raise ImportError(
                "duckdb est requis pour charger l'historique des transferts."
            ) from exc

        database_path = self._resolve_database_path()

        print(
            f"[HistoricalTransferLoader] Connexion à DuckDB : "
            f"{database_path}"
        )

        connection = duckdb.connect(str(database_path), read_only=True)

        try:
            tables = connection.execute("SHOW TABLES").fetchdf()

            available_tables = set(
                tables.iloc[:, 0].astype(str).str.lower()
            )

            if "transfers" not in available_tables:
                raise RuntimeError(
                    "La table 'transfers' est absente de la base DuckDB."
                )

            transfers = connection.execute(
                """
                SELECT *
                FROM transfers
                """
            ).fetchdf()

        finally:
            connection.close()

        if transfers.empty:
            raise RuntimeError(
                "La table transfers est vide."
            )

        print(
            f"[HistoricalTransferLoader] "
            f"{len(transfers):,} transferts chargés."
        )

        return transfers


# ============================================================================
# PERFORMANCE LOADER
# ============================================================================

class PerformanceLoader:
    """
    Charge les performances historiques.

    Le loader privilégie le fichier local afin de permettre :
      - les tests offline ;
      - les tests reproductibles ;
      - le fallback vers une fixture contrôlée.
    """

    def __init__(
        self,
        offline: bool = True,
        local_path: Path = PERFORMANCE_INPUT_PATH,
    ):
        self.offline = offline
        self.local_path = Path(local_path)

    def load(self) -> pd.DataFrame:
        print("[PerformanceLoader] Chargement des performances historiques...")

        if not self.local_path.exists():
            raise FileNotFoundError(
                f"Fichier de performances introuvable : "
                f"{self.local_path}"
            )

        print(
            f"[PerformanceLoader] Chargement local : "
            f"{self.local_path}"
        )

        performances = pd.read_csv(self.local_path)

        if performances.empty:
            raise RuntimeError(
                "Le fichier de performances est vide."
            )

        print(
            f"[PerformanceLoader] "
            f"{len(performances):,} lignes chargées."
        )

        return performances


# ============================================================================
# PERFORMANCE SCORER
# ============================================================================

class PerformanceScorer:
    """
    Calcule le score de performance et le percentile.

    Poids :
        goals_per90   : 30 %
        assists_per90 : 20 %
        xg_per90      : 30 %
        xa_per90      : 20 %

    Le percentile est calculé par :

        position
        + competition_level
        + season

    Les joueurs ayant moins de MIN_MINUTES minutes sont exclus du calcul
    du percentile.
    """

    WEIGHTS = {
        "goals_per90": 0.30,
        "assists_per90": 0.20,
        "xg_per90": 0.30,
        "xa_per90": 0.20,
    }

    REQUIRED_COLUMNS = [
        "player",
        "season",
        "season_start_date",
        "season_end_date",
        "competition",
        "competition_level",
        "team",
        "position",
        "minutes",
        "appearances",
        "starts",
        "goals",
        "assists",
        "xg",
        "xa",
        "goals_per90",
        "assists_per90",
        "xg_per90",
        "xa_per90",
    ]

    def __init__(self, performances_df: pd.DataFrame):
        self.performances_df = performances_df.copy()

    def _validate_columns(self) -> None:
        missing = [
            column
            for column in self.REQUIRED_COLUMNS
            if column not in self.performances_df.columns
        ]

        if missing:
            raise ValueError(
                "Colonnes manquantes dans les performances : "
                + ", ".join(missing)
            )

    def _prepare_data(self) -> pd.DataFrame:
        df = self.performances_df.copy()

        df["season_start_date"] = pd.to_datetime(
            df["season_start_date"],
            errors="coerce",
        )

        df["season_end_date"] = pd.to_datetime(
            df["season_end_date"],
            errors="coerce",
        )

        numeric_columns = [
            "minutes",
            "appearances",
            "starts",
            "goals",
            "assists",
            "xg",
            "xa",
            "goals_per90",
            "assists_per90",
            "xg_per90",
            "xa_per90",
        ]

        for column in numeric_columns:
            df[column] = pd.to_numeric(
                df[column],
                errors="coerce",
            )

        df["position"] = df["position"].astype(str).str.strip()
        df["competition_level"] = (
            df["competition_level"]
            .astype(str)
            .str.strip()
        )
        df["season"] = df["season"].astype(str).str.strip()

        return df

    def _calculate_raw_score(self, df: pd.DataFrame) -> pd.Series:
        weighted_sum = pd.Series(
            0.0,
            index=df.index,
        )

        available_weight = pd.Series(
            0.0,
            index=df.index,
        )

        for metric, weight in self.WEIGHTS.items():
            values = pd.to_numeric(
                df[metric],
                errors="coerce",
            )

            valid = values.notna()

            weighted_sum.loc[valid] += (
                values.loc[valid] * weight
            )

            available_weight.loc[valid] += weight

        score = weighted_sum / available_weight.replace(
            0,
            pd.NA,
        )

        return score

    def calculate_scores(self) -> pd.DataFrame:
        print(
            "[PerformanceScorer] Calcul des scores et percentiles..."
        )

        self._validate_columns()

        df = self._prepare_data()

        df["performance_score"] = self._calculate_raw_score(df)

        eligible = (
            df["minutes"].fillna(0) >= MIN_MINUTES
            & df["performance_score"].notna()
        )

        df["performance_percentile"] = pd.NA

        grouping_columns = [
            "position",
            "competition_level",
            "season",
        ]

        df.loc[eligible, "performance_percentile"] = (
            df.loc[eligible]
            .groupby(grouping_columns)["performance_score"]
            .rank(
                method="average",
                pct=True,
            )
        )

        df["performance_percentile"] = pd.to_numeric(
            df["performance_percentile"],
            errors="coerce",
        )

        df["performance_score_status"] = "INSUFFICIENT_MINUTES"

        df.loc[
            df["minutes"].fillna(0) >= MIN_MINUTES,
            "performance_score_status",
        ] = "VALID"

        df.loc[
            df["performance_score"].isna(),
            "performance_score_status",
        ] = "MISSING_METRICS"

        print(
            f"[PerformanceScorer] "
            f"{df['performance_percentile'].notna().sum():,} "
            f"percentile(s) calculé(s)."
        )

        return df

    def save(
        self,
        output_path: Path = PERFORMANCE_SCORED_PATH,
    ) -> None:
        output_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        scored = self.calculate_scores()

        scored.to_csv(
            output_path,
            index=False,
        )

        print(
            f"[PerformanceScorer] Résultat sauvegardé : "
            f"{output_path}"
        )


# ============================================================================
# TRANSFER PERFORMANCE BUILDER
# ============================================================================

class TransferPerformanceBuilder:
    """
    Construit les indicateurs PRE / POST autour d'un transfert.

    PRE :
        36 mois avant la date du transfert.

    POST :
        18 mois après la date du transfert.

    Règles :
        - la saison du transfert est exclue ;
        - une saison PRE doit être entièrement contenue dans la fenêtre PRE ;
        - une saison POST doit être entièrement contenue dans la fenêtre POST ;
        - une saison POST doit commencer après la date du transfert ;
        - le percentile provient obligatoirement de PerformanceScorer ;
        - agrégation pondérée par les minutes.
    """

    def __init__(
        self,
        performances_scored: pd.DataFrame,
        transfers: pd.DataFrame,
    ):
        self.performances = performances_scored.copy()
        self.transfers = transfers.copy()

        self._prepare_performances()
        self._prepare_transfers()

    # ------------------------------------------------------------------------
    # PREPARATION
    # ------------------------------------------------------------------------

    def _prepare_performances(self) -> None:
        required_columns = [
            "player",
            "season",
            "season_start_date",
            "season_end_date",
            "competition_level",
            "position",
            "minutes",
            "performance_percentile",
        ]

        missing = [
            column
            for column in required_columns
            if column not in self.performances.columns
        ]

        if missing:
            raise ValueError(
                "Colonnes manquantes dans performances_scored : "
                + ", ".join(missing)
            )

        self.performances["player_key"] = (
            self.performances["player"]
            .astype(str)
            .str.strip()
            .str.casefold()
        )

        self.performances["season_start_date"] = pd.to_datetime(
            self.performances["season_start_date"],
            errors="coerce",
        )

        self.performances["season_end_date"] = pd.to_datetime(
            self.performances["season_end_date"],
            errors="coerce",
        )

        self.performances["minutes"] = pd.to_numeric(
            self.performances["minutes"],
            errors="coerce",
        )

        self.performances["performance_percentile"] = pd.to_numeric(
            self.performances["performance_percentile"],
            errors="coerce",
        )

        self.performances["season"] = (
            self.performances["season"]
            .astype(str)
            .str.strip()
        )

        self.performances["competition_level"] = (
            self.performances["competition_level"]
            .astype(str)
            .str.strip()
        )

        self.performances["position"] = (
            self.performances["position"]
            .astype(str)
            .str.strip()
        )

    def _prepare_transfers(self) -> None:
        required_columns = [
            "player_name",
            "transfer_date",
        ]

        missing = [
            column
            for column in required_columns
            if column not in self.transfers.columns
        ]

        if missing:
            raise ValueError(
                "Colonnes manquantes dans transfers : "
                + ", ".join(missing)
            )

        self.transfers["player_key"] = (
            self.transfers["player_name"]
            .astype(str)
            .str.strip()
            .str.casefold()
        )

        self.transfers["transfer_date"] = pd.to_datetime(
            self.transfers["transfer_date"],
            errors="coerce",
        )

        self.transfers = self.transfers[
            self.transfers["transfer_date"].notna()
        ].copy()

    # ------------------------------------------------------------------------
    # DATE WINDOWS
    # ------------------------------------------------------------------------

    @staticmethod
    def _get_pre_window(
        transfer_date: pd.Timestamp,
    ) -> tuple[pd.Timestamp, pd.Timestamp]:

        pre_start = transfer_date - pd.DateOffset(
            months=PRE_MONTHS
        )

        pre_end = transfer_date

        return pre_start, pre_end

    @staticmethod
    def _get_post_window(
        transfer_date: pd.Timestamp,
    ) -> tuple[pd.Timestamp, pd.Timestamp]:

        post_start = transfer_date

        post_end = transfer_date + pd.DateOffset(
            months=POST_MONTHS
        )

        return post_start, post_end

    # ------------------------------------------------------------------------
    # TRANSFER SEASON EXCLUSION
    # ------------------------------------------------------------------------

    @staticmethod
    def _is_transfer_season(
        season_start: pd.Timestamp,
        season_end: pd.Timestamp,
        transfer_date: pd.Timestamp,
    ) -> bool:

        if pd.isna(season_start) or pd.isna(season_end):
            return False

        return (
            season_start <= transfer_date <= season_end
        )

    # ------------------------------------------------------------------------
    # SEASON SELECTION
    # ------------------------------------------------------------------------

    def _select_pre_seasons(
        self,
        player_df: pd.DataFrame,
        transfer_date: pd.Timestamp,
    ) -> pd.DataFrame:

        pre_start, pre_end = self._get_pre_window(
            transfer_date
        )

        mask = (
            (player_df["season_start_date"] >= pre_start)
            & (player_df["season_end_date"] <= pre_end)
            & (player_df["season_end_date"] < transfer_date)
        )

        selected = player_df.loc[mask].copy()

        if selected.empty:
            return selected

        selected = selected[
            ~selected.apply(
                lambda row: self._is_transfer_season(
                    row["season_start_date"],
                    row["season_end_date"],
                    transfer_date,
                ),
                axis=1,
            )
        ]

        return selected.sort_values(
            ["season_start_date", "season_end_date"]
        )

    def _select_post_seasons(
        self,
        player_df: pd.DataFrame,
        transfer_date: pd.Timestamp,
    ) -> pd.DataFrame:

        post_start, post_end = self._get_post_window(
            transfer_date
        )

        mask = (
            (player_df["season_start_date"] > transfer_date)
            & (player_df["season_end_date"] <= post_end)
            & (player_df["season_start_date"] >= post_start)
        )

        selected = player_df.loc[mask].copy()

        if selected.empty:
            return selected

        selected = selected[
            ~selected.apply(
                lambda row: self._is_transfer_season(
                    row["season_start_date"],
                    row["season_end_date"],
                    transfer_date,
                ),
                axis=1,
            )
        ]

        return selected.sort_values(
            ["season_start_date", "season_end_date"]
        )

    # ------------------------------------------------------------------------
    # AGGREGATION
    # ------------------------------------------------------------------------

    @staticmethod
    def _aggregate_percentile(
        seasons_df: pd.DataFrame,
    ) -> float:

        if seasons_df.empty:
            return float("nan")

        valid = seasons_df[
            seasons_df["performance_percentile"].notna()
        ].copy()

        if valid.empty:
            return float("nan")

        valid["minutes"] = pd.to_numeric(
            valid["minutes"],
            errors="coerce",
        )

        valid_minutes = valid[
            valid["minutes"].notna()
            & (valid["minutes"] > 0)
        ]

        if not valid_minutes.empty:
            weighted_sum = (
                valid_minutes["performance_percentile"]
                * valid_minutes["minutes"]
            ).sum()

            total_minutes = valid_minutes["minutes"].sum()

            if total_minutes > 0:
                return float(
                    weighted_sum / total_minutes
                )

        return float(
            valid["performance_percentile"].mean()
        )

    @staticmethod
    def _sum_minutes(
        seasons_df: pd.DataFrame,
    ) -> float:

        if seasons_df.empty:
            return 0.0

        minutes = pd.to_numeric(
            seasons_df["minutes"],
            errors="coerce",
        )

        return float(
            minutes.fillna(0).clip(lower=0).sum()
        )

    @staticmethod
    def _count_valid_percentile_seasons(
        seasons_df: pd.DataFrame,
    ) -> int:

        if seasons_df.empty:
            return 0

        return int(
            seasons_df["performance_percentile"]
            .notna()
            .sum()
        )

    @staticmethod
    def _season_list(
        seasons_df: pd.DataFrame,
    ) -> str:

        if seasons_df.empty:
            return ""

        seasons = (
            seasons_df["season"]
            .dropna()
            .astype(str)
            .drop_duplicates()
            .tolist()
        )

        return "|".join(seasons)

    # ------------------------------------------------------------------------
    # STATUS
    # ------------------------------------------------------------------------

    @staticmethod
    def _build_status(
        pre_percentile: float,
        post_percentile: float,
    ) -> str:

        pre_valid = pd.notna(pre_percentile)
        post_valid = pd.notna(post_percentile)

        if pre_valid and post_valid:
            return "COMPLETE"

        if pre_valid:
            return "PRE_ONLY"

        if post_valid:
            return "POST_ONLY"

        return "INSUFFICIENT"

    # ------------------------------------------------------------------------
    # BUILD ONE TRANSFER
    # ------------------------------------------------------------------------

    def _build_one_transfer(
        self,
        transfer_row: pd.Series,
    ) -> dict:

        player_key = transfer_row["player_key"]
        transfer_date = transfer_row["transfer_date"]

        player_df = self.performances[
            self.performances["player_key"] == player_key
        ].copy()

        pre_df = self._select_pre_seasons(
            player_df,
            transfer_date,
        )

        post_df = self._select_post_seasons(
            player_df,
            transfer_date,
        )

        pre_percentile = self._aggregate_percentile(
            pre_df
        )

        post_percentile = self._aggregate_percentile(
            post_df
        )

        performance_delta = float("nan")

        if (
            pd.notna(pre_percentile)
            and pd.notna(post_percentile)
        ):
            performance_delta = (
                post_percentile
                - pre_percentile
            )

        result = {
            "player_name": transfer_row["player_name"],
            "transfer_date": transfer_date,

            "pre_percentile": pre_percentile,
            "post_percentile": post_percentile,
            "performance_percentile_delta": performance_delta,

            "pre_minutes": self._sum_minutes(
                pre_df
            ),
            "post_minutes": self._sum_minutes(
                post_df
            ),

            "pre_seasons": self._count_valid_percentile_seasons(
                pre_df
            ),
            "post_seasons": self._count_valid_percentile_seasons(
                post_df
            ),

            "pre_seasons_list": self._season_list(
                pre_df
            ),
            "post_seasons_list": self._season_list(
                post_df
            ),

            "performance_status": self._build_status(
                pre_percentile,
                post_percentile,
            ),
        }

        for column in [
            "from_club_name",
            "to_club_name",
            "transfer_season",
            "transfer_fee",
            "market_value_in_eur",
        ]:
            if column in transfer_row.index:
                result[column] = transfer_row[column]

        return result

    # ------------------------------------------------------------------------
    # BUILD ALL TRANSFERS
    # ------------------------------------------------------------------------

    def build(
        self,
        transfers: Optional[pd.DataFrame] = None,
    ) -> pd.DataFrame:

        source = (
            self.transfers
            if transfers is None
            else transfers.copy()
        )

        if source.empty:
            return pd.DataFrame()

        rows = []

        for _, transfer_row in source.iterrows():
            rows.append(
                self._build_one_transfer(
                    transfer_row
                )
            )

        result = pd.DataFrame(rows)

        if not result.empty:
            result = result.sort_values(
                ["transfer_date", "player_name"]
            ).reset_index(drop=True)

        return result


# ============================================================================
# CONTROLLED TEST FIXTURE
# ============================================================================

def create_controlled_test_fixture() -> pd.DataFrame:
    """
    Crée une fixture déterministe destinée à tester l'intégration complète :

        Fixture brute
              ↓
        PerformanceScorer
              ↓
        performance_percentile
              ↓
        TransferPerformanceBuilder

    Fixture :
        2020/21
        2021/22
        2022/23
        2023/24
        2024/25

    Transfert :
        2023-07-10

    Avec les règles PRE/POST :
        PRE  = 2020/21 + 2021/22 + 2022/23
        POST = 2023/24

    2024/25 est volontairement hors de la fenêtre POST de 18 mois.

    Important :
        Les percentiles ne sont PAS fabriqués dans le Builder.
        Ils sont calculés par PerformanceScorer.
    """

    seasons = [
        {
            "season": "2020/21",
            "start": "2020-08-01",
            "end": "2021-05-31",
        },
        {
            "season": "2021/22",
            "start": "2021-08-01",
            "end": "2022-05-31",
        },
        {
            "season": "2022/23",
            "start": "2022-08-01",
            "end": "2023-05-31",
        },
        {
            "season": "2023/24",
            "start": "2023-08-01",
            "end": "2024-05-31",
        },
        {
            "season": "2024/25",
            "start": "2024-08-01",
            "end": "2025-05-31",
        },
    ]

    players = [
        {
            "player": "Controlled Player A",
            "position": "FW",
            "competition_level": "Top",
            "team": "Controlled FC",
            "base_goals": 0.50,
            "base_assists": 0.20,
            "base_xg": 0.60,
            "base_xa": 0.25,
        },
        {
            "player": "Controlled Player B",
            "position": "FW",
            "competition_level": "Top",
            "team": "Controlled FC",
            "base_goals": 0.70,
            "base_assists": 0.30,
            "base_xg": 0.80,
            "base_xa": 0.35,
        },
    ]

    rows = []

    for player in players:
        for season_index, season in enumerate(seasons):

            factor = 1.0 + (season_index * 0.05)

            goals_per90 = (
                player["base_goals"] * factor
            )

            assists_per90 = (
                player["base_assists"] * factor
            )

            xg_per90 = (
                player["base_xg"] * factor
            )

            xa_per90 = (
                player["base_xa"] * factor
            )

            minutes = 1800 + (
                season_index * 100
            )

            appearances = 25 + season_index
            starts = 20 + season_index

            goals = round(
                goals_per90 * minutes / 90
            )

            assists = round(
                assists_per90 * minutes / 90
            )

            xg = round(
                xg_per90 * minutes / 90,
                2,
            )

            xa = round(
                xa_per90 * minutes / 90,
                2,
            )

            rows.append(
                {
                    "player": player["player"],
                    "season": season["season"],
                    "season_start_date": season["start"],
                    "season_end_date": season["end"],
                    "competition": "Controlled League",
                    "competition_level": player[
                        "competition_level"
                    ],
                    "team": player["team"],
                    "position": player["position"],
                    "minutes": minutes,
                    "appearances": appearances,
                    "starts": starts,
                    "goals": goals,
                    "assists": assists,
                    "xg": xg,
                    "xa": xa,
                    "goals_per90": goals_per90,
                    "assists_per90": assists_per90,
                    "xg_per90": xg_per90,
                    "xa_per90": xa_per90,
                }
            )

    return pd.DataFrame(rows)


def create_controlled_test_transfers() -> pd.DataFrame:
    """
    Crée deux transferts synthétiques correspondant aux joueurs de la fixture.
    """

    return pd.DataFrame(
        [
            {
                "player_name": "Controlled Player A",
                "transfer_date": "2023-07-10",
                "transfer_season": "2023/24",
                "from_club_name": "Old FC",
                "to_club_name": "New FC",
                "transfer_fee": 10_000_000,
                "market_value_in_eur": 12_000_000,
            },
            {
                "player_name": "Controlled Player B",
                "transfer_date": "2023-07-10",
                "transfer_season": "2023/24",
                "from_club_name": "Old FC",
                "to_club_name": "New FC",
                "transfer_fee": 15_000_000,
                "market_value_in_eur": 18_000_000,
            },
        ]
    )


# ============================================================================
# REAL DATA VALIDATION
# ============================================================================

def try_build_real_test_fixture(
    performances: pd.DataFrame,
) -> Optional[pd.DataFrame]:
    """
    Cherche automatiquement un joueur réel disposant d'une couverture
    temporelle suffisante pour effectuer un test PRE/POST.

    Le transfert synthétique est placé après la troisième saison PRE.

    Retourne None si la couverture réelle n'est pas suffisante.
    """

    if performances.empty:
        return None

    if "performance_percentile" not in performances.columns:
        return None

    df = performances.copy()

    df["player_key"] = (
        df["player"]
        .astype(str)
        .str.strip()
        .str.casefold()
    )

    df["season_start_date"] = pd.to_datetime(
        df["season_start_date"],
        errors="coerce",
    )

    df["season_end_date"] = pd.to_datetime(
        df["season_end_date"],
        errors="coerce",
    )

    df["performance_percentile"] = pd.to_numeric(
        df["performance_percentile"],
        errors="coerce",
    )

    df["minutes"] = pd.to_numeric(
        df["minutes"],
        errors="coerce",
    )

    eligible = df[
        df["performance_percentile"].notna()
        & df["season_start_date"].notna()
        & df["season_end_date"].notna()
        & (df["minutes"].fillna(0) >= MIN_MINUTES)
    ].copy()

    if eligible.empty:
        return None

    for player_key, player_df in eligible.groupby(
        "player_key"
    ):

        player_df = (
            player_df
            .sort_values("season_start_date")
            .drop_duplicates(
                subset=["season"],
                keep="first",
            )
        )

        if len(player_df) < 4:
            continue

        for index in range(
            len(player_df) - 2
        ):

            pre_candidates = player_df.iloc[
                index:index + 3
            ]

            if len(pre_candidates) != 3:
                continue

            transfer_date = (
                pre_candidates.iloc[-1][
                    "season_end_date"
                ]
                + pd.Timedelta(days=30)
            )

            pre_start = (
                transfer_date
                - pd.DateOffset(months=PRE_MONTHS)
            )

            if (
                pre_candidates.iloc[0][
                    "season_start_date"
                ] < pre_start
            ):
                continue

            post_candidates = player_df[
                (
                    player_df["season_start_date"]
                    > transfer_date
                )
                & (
                    player_df["season_end_date"]
                    <= transfer_date
                    + pd.DateOffset(months=POST_MONTHS)
                )
            ]

            if post_candidates.empty:
                continue

            selected_post = post_candidates.iloc[0]

            if (
                selected_post["season_start_date"]
                <= transfer_date
            ):
                continue

            if (
                selected_post["season_end_date"]
                > transfer_date
                + pd.DateOffset(months=POST_MONTHS)
            ):
                continue

            player_name = (
                pre_candidates.iloc[0]["player"]
            )

            return pd.DataFrame(
                [
                    {
                        "player_name": player_name,
                        "transfer_date": transfer_date,
                        "transfer_season": "SYNTHETIC",
                        "from_club_name": "Synthetic From",
                        "to_club_name": "Synthetic To",
                        "transfer_fee": None,
                        "market_value_in_eur": None,
                    }
                ]
            )

    return None


# ============================================================================
# VALIDATIONS
# ============================================================================

def validate_scorer_output(
    scored: pd.DataFrame,
) -> None:

    print()
    print("VALIDATION INPUT PERFORMANCE SCORER")
    print("-" * 70)

    if "performance_percentile" not in scored.columns:
        raise AssertionError(
            "performance_percentile absent de la sortie du scorer."
        )

    print(
        "✓ performance_percentile présent."
    )

    count = scored[
        "performance_percentile"
    ].notna().sum()

    if count == 0:
        raise AssertionError(
            "Aucun percentile produit par PerformanceScorer."
        )

    print(
        f"✓ {count} percentile(s) disponible(s)."
    )

    invalid = scored[
        scored["performance_percentile"].notna()
        & (
            (scored["performance_percentile"] < 0)
            | (scored["performance_percentile"] > 1)
        )
    ]

    if not invalid.empty:
        raise AssertionError(
            "Des percentiles sont hors de l'intervalle [0, 1]."
        )

    print(
        "✓ Valeurs comprises dans [0, 1]."
    )


def validate_controlled_result(
    scored_fixture: pd.DataFrame,
    transfers: pd.DataFrame,
    result: pd.DataFrame,
) -> None:

    print()
    print("VALIDATION FIXTURE CONTRÔLÉE")
    print("-" * 70)

    expected_players = {
        "controlled player a",
        "controlled player b",
    }

    actual_players = set(
        result["player_name"]
        .astype(str)
        .str.strip()
        .str.casefold()
    )

    if actual_players != expected_players:
        raise AssertionError(
            f"Joueurs inattendus : {actual_players}"
        )

    print(
        "✓ Les deux joueurs de la fixture sont présents."
    )

    for _, row in result.iterrows():

        player = str(
            row["player_name"]
        ).strip().casefold()

        if row["pre_seasons"] != 3:
            raise AssertionError(
                f"{player}: PRE attendu = 3, "
                f"obtenu = {row['pre_seasons']}"
            )

        if row["post_seasons"] != 1:
            raise AssertionError(
                f"{player}: POST attendu = 1, "
                f"obtenu = {row['post_seasons']}"
            )

        expected_pre = (
            "2020/21|2021/22|2022/23"
        )

        expected_post = "2023/24"

        if row["pre_seasons_list"] != expected_pre:
            raise AssertionError(
                f"{player}: PRE seasons incorrectes : "
                f"{row['pre_seasons_list']}"
            )

        if row["post_seasons_list"] != expected_post:
            raise AssertionError(
                f"{player}: POST seasons incorrectes : "
                f"{row['post_seasons_list']}"
            )

        if "2024/25" in str(
            row["post_seasons_list"]
        ):
            raise AssertionError(
                f"{player}: 2024/25 ne doit pas être "
                f"dans la fenêtre POST."
            )

        if pd.isna(
            row["pre_percentile"]
        ):
            raise AssertionError(
                f"{player}: percentile PRE absent."
            )

        if pd.isna(
            row["post_percentile"]
        ):
            raise AssertionError(
                f"{player}: percentile POST absent."
            )

        expected_delta = (
            row["post_percentile"]
            - row["pre_percentile"]
        )

        if not abs(
            row["performance_percentile_delta"]
            - expected_delta
        ) < 1e-12:
            raise AssertionError(
                f"{player}: delta incorrect."
            )

        if row["performance_status"] != "COMPLETE":
            raise AssertionError(
                f"{player}: statut inattendu : "
                f"{row['performance_status']}"
            )

    print(
        "✓ PRE = 3 saisons."
    )

    print(
        "✓ POST = 1 saison."
    )

    print(
        "✓ 2020/21, 2021/22 et 2022/23 sélectionnées en PRE."
    )

    print(
        "✓ 2023/24 sélectionnée en POST."
    )

    print(
        "✓ 2024/25 correctement exclue de la fenêtre POST."
    )

    print(
        "✓ performance_percentile_delta = POST - PRE."
    )

    print(
        "✓ Les percentiles proviennent du PerformanceScorer."
    )

    print(
        "✓ Agrégation et statut COMPLETE validés."
    )


def validate_minute_weighting(
    scored_fixture: pd.DataFrame,
    result: pd.DataFrame,
) -> None:

    print()
    print("VALIDATION PONDÉRATION PAR LES MINUTES")
    print("-" * 70)

    for _, result_row in result.iterrows():

        player_key = (
            str(result_row["player_name"])
            .strip()
            .casefold()
        )

        player_df = scored_fixture[
            scored_fixture["player"]
            .astype(str)
            .str.strip()
            .str.casefold()
            == player_key
        ].copy()

        pre_df = player_df[
            player_df["season"].isin(
                [
                    "2020/21",
                    "2021/22",
                    "2022/23",
                ]
            )
        ].copy()

        post_df = player_df[
            player_df["season"].eq(
                "2023/24"
            )
        ].copy()

        pre_minutes = pd.to_numeric(
            pre_df["minutes"],
            errors="coerce",
        )

        pre_percentiles = pd.to_numeric(
            pre_df["performance_percentile"],
            errors="coerce",
        )

        expected_pre = (
            (
                pre_percentiles * pre_minutes
            ).sum()
            / pre_minutes.sum()
        )

        post_minutes = pd.to_numeric(
            post_df["minutes"],
            errors="coerce",
        )

        post_percentiles = pd.to_numeric(
            post_df["performance_percentile"],
            errors="coerce",
        )

        expected_post = (
            (
                post_percentiles * post_minutes
            ).sum()
            / post_minutes.sum()
        )

        if not abs(
            result_row["pre_percentile"]
            - expected_pre
        ) < 1e-12:
            raise AssertionError(
                f"{player_key}: pondération PRE incorrecte."
            )

        if not abs(
            result_row["post_percentile"]
            - expected_post
        ) < 1e-12:
            raise AssertionError(
                f"{player_key}: pondération POST incorrecte."
            )

    print(
        "✓ Moyenne PRE pondérée par les minutes."
    )

    print(
        "✓ Moyenne POST pondérée par les minutes."
    )


def validate_transfer_season_exclusion(
    scored_fixture: pd.DataFrame,
) -> None:

    print()
    print("VALIDATION EXCLUSION DE LA SAISON DU TRANSFERT")
    print("-" * 70)

    transfers = create_controlled_test_transfers()

    builder = TransferPerformanceBuilder(
        performances_scored=scored_fixture,
        transfers=transfers,
    )

    result = builder.build()

    for _, row in result.iterrows():

        transfer_date = pd.Timestamp(
            row["transfer_date"]
        )

        selected_seasons = []

        if row["pre_seasons_list"]:
            selected_seasons.extend(
                row["pre_seasons_list"].split("|")
            )

        if row["post_seasons_list"]:
            selected_seasons.extend(
                row["post_seasons_list"].split("|")
            )

        player_key = (
            str(row["player_name"])
            .strip()
            .casefold()
        )

        player_df = scored_fixture[
            scored_fixture["player"]
            .astype(str)
            .str.strip()
            .str.casefold()
            == player_key
        ]

        transfer_season_rows = player_df[
            (
                player_df["season_start_date"]
                <= transfer_date
            )
            & (
                player_df["season_end_date"]
                >= transfer_date
            )
        ]

        transfer_seasons = set(
            transfer_season_rows["season"]
            .astype(str)
        )

        overlap = (
            set(selected_seasons)
            & transfer_seasons
        )

        if overlap:
            raise AssertionError(
                f"Saison du transfert détectée dans "
                f"les saisons sélectionnées : {overlap}"
            )

    print(
        "✓ Aucune saison contenant la date du transfert "
        "n'est utilisée."
    )


def validate_post_boundary(
    result: pd.DataFrame,
    scored_fixture: pd.DataFrame,
) -> None:

    print()
    print("VALIDATION BORNE POST = +18 MOIS")
    print("-" * 70)

    for _, row in result.iterrows():

        transfer_date = pd.Timestamp(
            row["transfer_date"]
        )

        post_end = (
            transfer_date
            + pd.DateOffset(months=POST_MONTHS)
        )

        post_seasons = (
            []
            if not row["post_seasons_list"]
            else row["post_seasons_list"].split("|")
        )

        player_key = (
            str(row["player_name"])
            .strip()
            .casefold()
        )

        player_df = scored_fixture[
            scored_fixture["player"]
            .astype(str)
            .str.strip()
            .str.casefold()
            == player_key
        ]

        selected = player_df[
            player_df["season"].isin(post_seasons)
        ]

        if not selected.empty:
            invalid = selected[
                selected["season_end_date"] > post_end
            ]

            if not invalid.empty:
                raise AssertionError(
                    f"{row['player_name']}: une saison POST "
                    f"dépasse la borne de +18 mois."
                )

    print(
        f"✓ Toutes les saisons POST sont entièrement "
        f"contenues dans la fenêtre de +{POST_MONTHS} mois."
    )


# ============================================================================
# MAIN TEST
# ============================================================================

def main() -> None:

    print("=" * 70)
    print("TEST TRANSFER PERFORMANCE BUILDER")
    print("=" * 70)

    # ------------------------------------------------------------------------
    # 1. Chargement des performances réelles
    # ------------------------------------------------------------------------

    try:
        performance_loader = PerformanceLoader(
            offline=True,
            local_path=PERFORMANCE_INPUT_PATH,
        )

        real_performances = performance_loader.load()

    except Exception as exc:

        print(
            f"[TEST] Impossible de charger les performances réelles : "
            f"{exc}"
        )

        real_performances = pd.DataFrame()

    # ------------------------------------------------------------------------
    # 2. Passage obligatoire par PerformanceScorer
    # ------------------------------------------------------------------------

    use_controlled_fixture = False

    if not real_performances.empty:

        try:

            real_scorer = PerformanceScorer(
                performances_df=real_performances
            )

            scored_real = (
                real_scorer.calculate_scores()
            )

            validate_scorer_output(
                scored_real
            )

        except Exception as exc:

            print(
                "[TEST] Échec du scoring des données réelles : "
                f"{exc}"
            )

            scored_real = pd.DataFrame()

    else:
        scored_real = pd.DataFrame()

    # ------------------------------------------------------------------------
    # 3. Recherche d'une fixture réelle exploitable
    # ------------------------------------------------------------------------

    real_test_transfers = None

    if not scored_real.empty:

        real_test_transfers = (
            try_build_real_test_fixture(
                scored_real
            )
        )

    if real_test_transfers is not None:

        print()
        print(
            "[TEST] Données réelles suffisamment couvertes."
        )

        builder = TransferPerformanceBuilder(
            performances_scored=scored_real,
            transfers=real_test_transfers,
        )

        result = builder.build()

        if result.empty:
            raise RuntimeError(
                "Le Builder n'a produit aucun résultat "
                "avec les données réelles."
            )

        print()
        print("RÉSULTAT TEST RÉEL")
        print("-" * 70)

        print(
            result.to_string(index=False)
        )

        validate_post_boundary(
            result,
            scored_real,
        )

        print()
        print("=" * 70)
        print("✓ TEST RÉEL TERMINÉ AVEC SUCCÈS")
        print("=" * 70)

        return

    # ------------------------------------------------------------------------
    # 4. Fallback fixture contrôlée
    # ------------------------------------------------------------------------

    use_controlled_fixture = True

    if use_controlled_fixture:

        print()
        print(
            "[TEST] Couverture réelle insuffisante."
        )

        print(
            "[TEST] Génération d'une fixture contrôlée."
        )

        raw_fixture = (
            create_controlled_test_fixture()
        )

        controlled_transfers = (
            create_controlled_test_transfers()
        )

        print(
            f"[TEST] Fixture brute : "
            f"{len(raw_fixture)} lignes."
        )

        # ------------------------------------------------------------
        # IMPORTANT :
        # On repasse la fixture par PerformanceScorer.
        # Aucun percentile n'est injecté manuellement.
        # ------------------------------------------------------------

        fixture_scorer = PerformanceScorer(
            performances_df=raw_fixture
        )

        scored_fixture = (
            fixture_scorer.calculate_scores()
        )

        validate_scorer_output(
            scored_fixture
        )

        # ------------------------------------------------------------
        # Builder
        # ------------------------------------------------------------

        builder = TransferPerformanceBuilder(
            performances_scored=scored_fixture,
            transfers=controlled_transfers,
        )

        result = builder.build()

        if result.empty:
            raise RuntimeError(
                "Le Builder n'a produit aucun résultat "
                "avec la fixture contrôlée."
            )

        print()
        print("RÉSULTAT FIXTURE CONTRÔLÉE")
        print("-" * 70)

        display_columns = [
            "player_name",
            "transfer_date",
            "pre_percentile",
            "post_percentile",
            "performance_percentile_delta",
            "pre_minutes",
            "post_minutes",
            "pre_seasons",
            "post_seasons",
            "pre_seasons_list",
            "post_seasons_list",
            "performance_status",
        ]

        available_display_columns = [
            column
            for column in display_columns
            if column in result.columns
        ]

        print(
            result[
                available_display_columns
            ].to_string(index=False)
        )

        # ------------------------------------------------------------
        # Validations
        # ------------------------------------------------------------

        validate_controlled_result(
            scored_fixture=scored_fixture,
            transfers=controlled_transfers,
            result=result,
        )

        validate_minute_weighting(
            scored_fixture=scored_fixture,
            result=result,
        )

        validate_transfer_season_exclusion(
            scored_fixture=scored_fixture,
        )

        validate_post_boundary(
            result=result,
            scored_fixture=scored_fixture,
        )

        # ------------------------------------------------------------
        # Sauvegarde facultative de la fixture scorée
        # ------------------------------------------------------------

        fixture_output = Path(
            "data/performances/performance_controlled_scored.csv"
        )

        fixture_output.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        scored_fixture.to_csv(
            fixture_output,
            index=False,
        )

        print()
        print(
            f"✓ Fixture scorée sauvegardée : "
            f"{fixture_output}"
        )

        print()
        print("=" * 70)
        print("✓ TEST FIXTURE CONTRÔLÉE TERMINÉ AVEC SUCCÈS")
        print("=" * 70)


if __name__ == "__main__":
    main()