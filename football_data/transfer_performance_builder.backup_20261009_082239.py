from __future__ import annotations

from pathlib import Path
from typing import Optional

import pandas as pd


# ============================================================================
# CONFIGURATION
# ============================================================================

PERFORMANCE_INPUT_PATH = Path(
    "data/performances/performance_sample.csv"
)

PERFORMANCE_SCORED_PATH = Path(
    "data/performances/performance_scored.csv"
)

TRANSFER_PERFORMANCE_OUTPUT_PATH = Path(
    "data/performances/transfer_performance_dataset.csv"
)

TRANSFER_RAW_OUTPUT_PATH = Path(
    "data/transfers/transfers_real.csv"
)

PERFORMANCE_SCORED_REAL_OUTPUT_PATH = Path(
    "data/performances/performance_scored_real.csv"
)

DEFAULT_DATABASE_PATHS = [
    Path("dbt/duck.db"),
    Path("data/transfermarkt-datasets.duckdb"),
    Path("transfermarkt-datasets.duckdb"),
]

MIN_MINUTES = 900

PRE_MONTHS = 36
POST_MONTHS = 18


# ============================================================================
# DATABASE RESOLUTION
# ============================================================================

def resolve_database_path(
    database_path: Optional[Path] = None,
) -> Path:

    if database_path is not None:

        database_path = Path(database_path)

        if not database_path.exists():
            raise FileNotFoundError(
                f"Base DuckDB introuvable : {database_path}"
            )

        return database_path

    for candidate in DEFAULT_DATABASE_PATHS:

        if candidate.exists():
            return candidate

    raise FileNotFoundError(
        "Aucune base DuckDB trouvée.\n"
        "Chemins testés :\n"
        + "\n".join(
            f"  - {path}"
            for path in DEFAULT_DATABASE_PATHS
        )
    )


# ============================================================================
# REAL TRANSFER LOADER
# ============================================================================

class RealTransferLoader:
    """
    Charge les transferts réels depuis la base Transfermarkt.

    Source principale :
        transfers

    Colonnes utilisées :
        player_id
        player_name
        transfer_date
        transfer_season
        from_club_id
        to_club_id
        from_club_name
        to_club_name
        transfer_fee
        market_value_in_eur
    """

    REQUIRED_COLUMNS = [
        "player_id",
        "player_name",
        "transfer_date",
        "transfer_season",
        "from_club_id",
        "to_club_id",
        "from_club_name",
        "to_club_name",
        "transfer_fee",
        "market_value_in_eur",
    ]

    def __init__(
        self,
        database_path: Optional[Path] = None,
    ):
        self.database_path = database_path

    def load(self) -> pd.DataFrame:

        print(
            "[RealTransferLoader] "
            "Chargement des transferts réels..."
        )

        try:
            import duckdb
        except ImportError as exc:
            raise ImportError(
                "Le package duckdb est requis."
            ) from exc

        database_path = resolve_database_path(
            self.database_path
        )

        print(
            f"[RealTransferLoader] "
            f"Base utilisée : {database_path}"
        )

        connection = duckdb.connect(
            str(database_path),
            read_only=True,
        )

        try:

            transfers = connection.execute(
                """
                SELECT
                    player_id,
                    player_name,
                    transfer_date,
                    transfer_season,
                    from_club_id,
                    to_club_id,
                    from_club_name,
                    to_club_name,
                    transfer_fee,
                    market_value_in_eur
                FROM transfers
                WHERE transfer_date IS NOT NULL
                ORDER BY transfer_date ASC, player_id ASC
                """
            ).fetchdf()

        finally:
            connection.close()

        if transfers.empty:

            raise RuntimeError(
                "Aucun transfert réel trouvé."
            )

        transfers["transfer_date"] = pd.to_datetime(
            transfers["transfer_date"],
            errors="coerce",
        )

        transfers = transfers[
            transfers["transfer_date"].notna()
        ].copy()

        transfers["player_id"] = pd.to_numeric(
            transfers["player_id"],
            errors="coerce",
        ).astype("Int64")

        transfers["player_name"] = (
            transfers["player_name"]
            .astype(str)
            .str.strip()
        )

        transfers["player_key"] = (
            transfers["player_name"]
            .str.casefold()
        )

        transfers = transfers.drop_duplicates(
            subset=[
                "player_id",
                "transfer_date",
                "from_club_id",
                "to_club_id",
            ]
        )

        print(
            f"[RealTransferLoader] "
            f"{len(transfers):,} transferts chargés."
        )

        print(
            f"[RealTransferLoader] "
            f"{transfers['player_id'].nunique():,} joueurs uniques."
        )

        return transfers


# ============================================================================
# PERFORMANCE LOADER
# ============================================================================

class RealPerformanceLoader:

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

    def __init__(
        self,
        input_path: Path = PERFORMANCE_INPUT_PATH,
    ):
        self.input_path = Path(input_path)

    def load(self) -> pd.DataFrame:

        print(
            "[RealPerformanceLoader] "
            "Chargement des performances..."
        )

        if not self.input_path.exists():

            raise FileNotFoundError(
                f"Fichier introuvable : {self.input_path}"
            )

        df = pd.read_csv(
            self.input_path
        )

        if df.empty:

            raise RuntimeError(
                "Le fichier de performances est vide."
            )

        missing = [
            column
            for column in self.REQUIRED_COLUMNS
            if column not in df.columns
        ]

        if missing:

            raise ValueError(
                "Colonnes manquantes dans les performances : "
                + ", ".join(missing)
            )

        print(
            f"[RealPerformanceLoader] "
            f"{len(df):,} lignes chargées."
        )

        return df


# ============================================================================
# PERFORMANCE SCORER
# ============================================================================

class PerformanceScorer:

    WEIGHTS = {
        "goals_per90": 0.30,
        "assists_per90": 0.20,
        "xg_per90": 0.30,
        "xa_per90": 0.20,
    }

    def __init__(
        self,
        performances_df: pd.DataFrame,
    ):
        self.performances_df = performances_df.copy()

    def calculate_scores(self) -> pd.DataFrame:

        print(
            "[PerformanceScorer] "
            "Calcul des scores et percentiles..."
        )

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
                values.loc[valid]
                * weight
            )

            available_weight.loc[valid] += weight

        df["performance_score"] = (
            weighted_sum
            / available_weight.replace(
                0,
                pd.NA,
            )
        )

        eligible = (
            df["minutes"].fillna(0)
            >= MIN_MINUTES
        ) & (
            df["performance_score"].notna()
        )

        df["performance_percentile"] = pd.NA

        grouping_columns = [
            "position",
            "competition_level",
            "season",
        ]

        df.loc[
            eligible,
            "performance_percentile",
        ] = (
            df.loc[eligible]
            .groupby(grouping_columns)[
                "performance_score"
            ]
            .rank(
                method="average",
                pct=True,
            )
        )

        df["performance_percentile"] = pd.to_numeric(
            df["performance_percentile"],
            errors="coerce",
        )

        df["performance_score_status"] = (
            "INSUFFICIENT_MINUTES"
        )

        df.loc[
            df["minutes"].fillna(0)
            >= MIN_MINUTES,
            "performance_score_status",
        ] = "VALID"

        df.loc[
            df["performance_score"].isna(),
            "performance_score_status",
        ] = "MISSING_METRICS"

        print(
            "[PerformanceScorer] "
            f"{df['performance_percentile'].notna().sum():,} "
            "percentile(s) calculé(s)."
        )

        return df


# ============================================================================
# TRANSFER PERFORMANCE BUILDER
# ============================================================================

class TransferPerformanceBuilder:

    def __init__(
        self,
        performances_scored: pd.DataFrame,
        transfers: pd.DataFrame,
    ):

        self.performances = (
            performances_scored.copy()
        )

        self.transfers = transfers.copy()

        self._prepare_performances()
        self._prepare_transfers()

    def _prepare_performances(self):

        required = [
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
            for column in required
            if column not in self.performances.columns
        ]

        if missing:

            raise ValueError(
                "Colonnes manquantes dans performances_scored : "
                + ", ".join(missing)
            )

        self.performances[
            "player_key"
        ] = (
            self.performances["player"]
            .astype(str)
            .str.strip()
            .str.casefold()
        )

        self.performances[
            "season_start_date"
        ] = pd.to_datetime(
            self.performances["season_start_date"],
            errors="coerce",
        )

        self.performances[
            "season_end_date"
        ] = pd.to_datetime(
            self.performances["season_end_date"],
            errors="coerce",
        )

        self.performances[
            "performance_percentile"
        ] = pd.to_numeric(
            self.performances[
                "performance_percentile"
            ],
            errors="coerce",
        )

        self.performances["minutes"] = pd.to_numeric(
            self.performances["minutes"],
            errors="coerce",
        )

        self.performances["season"] = (
            self.performances["season"]
            .astype(str)
            .str.strip()
        )

    def _prepare_transfers(self):

        required = [
            "player_id",
            "player_name",
            "transfer_date",
        ]

        missing = [
            column
            for column in required
            if column not in self.transfers.columns
        ]

        if missing:

            raise ValueError(
                "Colonnes manquantes dans transfers : "
                + ", ".join(missing)
            )

        self.transfers[
            "player_key"
        ] = (
            self.transfers["player_name"]
            .astype(str)
            .str.strip()
            .str.casefold()
        )

        self.transfers[
            "transfer_date"
        ] = pd.to_datetime(
            self.transfers["transfer_date"],
            errors="coerce",
        )

    @staticmethod
    def _aggregate_percentile(
        seasons_df: pd.DataFrame,
    ) -> float:

        if seasons_df.empty:

            return float("nan")

        valid = seasons_df[
            seasons_df[
                "performance_percentile"
            ].notna()
        ].copy()

        if valid.empty:

            return float("nan")

        valid["minutes"] = pd.to_numeric(
            valid["minutes"],
            errors="coerce",
        )

        weighted = valid[
            valid["minutes"].notna()
            & (valid["minutes"] > 0)
        ]

        if not weighted.empty:

            total_minutes = (
                weighted["minutes"].sum()
            )

            if total_minutes > 0:

                return float(
                    (
                        weighted[
                            "performance_percentile"
                        ]
                        * weighted["minutes"]
                    ).sum()
                    / total_minutes
                )

        return float(
            valid[
                "performance_percentile"
            ].mean()
        )

    @staticmethod
    def _sum_minutes(
        seasons_df: pd.DataFrame,
    ) -> float:

        if seasons_df.empty:

            return 0.0

        return float(
            pd.to_numeric(
                seasons_df["minutes"],
                errors="coerce",
            )
            .fillna(0)
            .clip(lower=0)
            .sum()
        )

    @staticmethod
    def _season_list(
        seasons_df: pd.DataFrame,
    ) -> str:

        if seasons_df.empty:

            return ""

        return "|".join(
            seasons_df["season"]
            .drop_duplicates()
            .astype(str)
            .tolist()
        )

    @staticmethod
    def _count_valid_seasons(
        seasons_df: pd.DataFrame,
    ) -> int:

        if seasons_df.empty:

            return 0

        return int(
            seasons_df[
                "performance_percentile"
            ].notna().sum()
        )

    @staticmethod
    def _status(
        pre: float,
        post: float,
    ) -> str:

        if pd.notna(pre) and pd.notna(post):
            return "COMPLETE"

        if pd.notna(pre):
            return "PRE_ONLY"

        if pd.notna(post):
            return "POST_ONLY"

        return "INSUFFICIENT"

    def _select_pre(
        self,
        player_df: pd.DataFrame,
        transfer_date: pd.Timestamp,
    ) -> pd.DataFrame:

        pre_start = (
            transfer_date
            - pd.DateOffset(
                months=PRE_MONTHS
            )
        )

        mask = (
            (
                player_df[
                    "season_start_date"
                ]
                >= pre_start
            )
            & (
                player_df[
                    "season_end_date"
                ]
                <= transfer_date
            )
            & (
                player_df[
                    "season_end_date"
                ]
                < transfer_date
            )
        )

        selected = player_df.loc[
            mask
        ].copy()

        if selected.empty:
            return selected

        selected = selected[
            ~(
                (
                    selected[
                        "season_start_date"
                    ]
                    <= transfer_date
                )
                & (
                    selected[
                        "season_end_date"
                    ]
                    >= transfer_date
                )
            )
        ]

        return selected.sort_values(
            "season_start_date"
        )

    def _select_post(
        self,
        player_df: pd.DataFrame,
        transfer_date: pd.Timestamp,
    ) -> pd.DataFrame:

        post_end = (
            transfer_date
            + pd.DateOffset(
                months=POST_MONTHS
            )
        )

        mask = (
            (
                player_df[
                    "season_start_date"
                ]
                > transfer_date
            )
            & (
                player_df[
                    "season_end_date"
                ]
                <= post_end
            )
            & (
                player_df[
                    "season_start_date"
                ]
                >= transfer_date
            )
        )

        selected = player_df.loc[
            mask
        ].copy()

        if selected.empty:
            return selected

        selected = selected[
            ~(
                (
                    selected[
                        "season_start_date"
                    ]
                    <= transfer_date
                )
                & (
                    selected[
                        "season_end_date"
                    ]
                    >= transfer_date
                )
            )
        ]

        return selected.sort_values(
            "season_start_date"
        )

    def _build_one(
        self,
        transfer: pd.Series,
    ) -> dict:

        player_key = transfer[
            "player_key"
        ]

        transfer_date = transfer[
            "transfer_date"
        ]

        player_df = self.performances[
            self.performances[
                "player_key"
            ]
            == player_key
        ].copy()

        pre_df = self._select_pre(
            player_df,
            transfer_date,
        )

        post_df = self._select_post(
            player_df,
            transfer_date,
        )

        pre_percentile = (
            self._aggregate_percentile(
                pre_df
            )
        )

        post_percentile = (
            self._aggregate_percentile(
                post_df
            )
        )

        delta = float("nan")

        if (
            pd.notna(pre_percentile)
            and pd.notna(post_percentile)
        ):

            delta = (
                post_percentile
                - pre_percentile
            )

        result = {
            "player_id": transfer[
                "player_id"
            ],

            "player_name": transfer[
                "player_name"
            ],

            "transfer_date": transfer[
                "transfer_date"
            ],

            "transfer_season": transfer.get(
                "transfer_season"
            ),

            "from_club_id": transfer.get(
                "from_club_id"
            ),

            "from_club_name": transfer.get(
                "from_club_name"
            ),

            "to_club_id": transfer.get(
                "to_club_id"
            ),

            "to_club_name": transfer.get(
                "to_club_name"
            ),

            "transfer_fee": transfer.get(
                "transfer_fee"
            ),

            "market_value_in_eur": transfer.get(
                "market_value_in_eur"
            ),

            "pre_percentile": pre_percentile,

            "post_percentile": post_percentile,

            "performance_percentile_delta": delta,

            "pre_minutes": self._sum_minutes(
                pre_df
            ),

            "post_minutes": self._sum_minutes(
                post_df
            ),

            "pre_seasons": self._count_valid_seasons(
                pre_df
            ),

            "post_seasons": self._count_valid_seasons(
                post_df
            ),

            "pre_seasons_list": self._season_list(
                pre_df
            ),

            "post_seasons_list": self._season_list(
                post_df
            ),

            "performance_status": self._status(
                pre_percentile,
                post_percentile,
            ),
        }

        return result

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

        print()
        print(
            "[TransferPerformanceBuilder] "
            f"Construction de {len(source):,} transferts..."
        )

        rows = []

        for index, transfer in source.iterrows():

            if (
                index > 0
                and index % 10_000 == 0
            ):

                print(
                    "[TransferPerformanceBuilder] "
                    f"{index:,}/{len(source):,}"
                )

            rows.append(
                self._build_one(
                    transfer
                )
            )

        result = pd.DataFrame(
            rows
        )

        if not result.empty:

            result = result.sort_values(
                [
                    "transfer_date",
                    "player_id",
                ]
            ).reset_index(
                drop=True
            )

        print(
            "[TransferPerformanceBuilder] "
            f"{len(result):,} lignes produites."
        )

        return result


# ============================================================================
# DATASET QUALITY REPORT
# ============================================================================

def generate_quality_report(
    result: pd.DataFrame,
) -> None:

    print()
    print("=" * 70)
    print("QUALITY REPORT — TRANSFER PERFORMANCE DATASET")
    print("=" * 70)

    if result.empty:

        print(
            "Dataset vide."
        )

        return

    total = len(result)

    complete = (
        result[
            "performance_status"
        ]
        == "COMPLETE"
    ).sum()

    pre_only = (
        result[
            "performance_status"
        ]
        == "PRE_ONLY"
    ).sum()

    post_only = (
        result[
            "performance_status"
        ]
        == "POST_ONLY"
    ).sum()

    insufficient = (
        result[
            "performance_status"
        ]
        == "INSUFFICIENT"
    ).sum()

    print(
        f"Transferts totaux       : {total:,}"
    )

    print(
        f"COMPLETE                : {complete:,}"
    )

    print(
        f"PRE_ONLY                : {pre_only:,}"
    )

    print(
        f"POST_ONLY               : {post_only:,}"
    )

    print(
        f"INSUFFICIENT            : {insufficient:,}"
    )

    print()

    print(
        "Couverture COMPLETE     : "
        f"{complete / total:.2%}"
    )

    print(
        "Percentile PRE présent  : "
        f"{result['pre_percentile'].notna().mean():.2%}"
    )

    print(
        "Percentile POST présent : "
        f"{result['post_percentile'].notna().mean():.2%}"
    )

    print(
        "Delta présent            : "
        f"{result['performance_percentile_delta'].notna().mean():.2%}"
    )

    print()

    print(
        "Joueurs uniques          : "
        f"{result['player_id'].nunique():,}"
    )

    print(
        "Transferts avec PRE >= 1 : "
        f"{(result['pre_seasons'] >= 1).sum():,}"
    )

    print(
        "Transferts avec POST >= 1: "
        f"{(result['post_seasons'] >= 1).sum():,}"
    )

    print()

    print(
        "Répartition des statuts :"
    )

    print(
        result[
            "performance_status"
        ]
        .value_counts(dropna=False)
        .to_string()
    )


# ============================================================================
# DATASET FILTER
# ============================================================================

def filter_real_dataset(
    result: pd.DataFrame,
) -> pd.DataFrame:

    """
    Prépare une version exploitable pour les analyses ML.

    On conserve ici toutes les lignes produites par le Builder.

    Le filtre métier COMPLET n'est PAS appliqué à cette étape :
    les observations PRE_ONLY / POST_ONLY restent disponibles pour
    l'analyse de couverture et la construction ultérieure des labels.
    """

    if result.empty:

        return result

    result = result.copy()

    result["transfer_date"] = pd.to_datetime(
        result["transfer_date"],
        errors="coerce",
    )

    result["transfer_year"] = (
        result["transfer_date"]
        .dt.year
    )

    result["transfer_month"] = (
        result["transfer_date"]
        .dt.month
    )

    return result


# ============================================================================
# SAVE DATASET
# ============================================================================

def save_dataset(
    result: pd.DataFrame,
) -> None:

    TRANSFER_PERFORMANCE_OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    result.to_csv(
        TRANSFER_PERFORMANCE_OUTPUT_PATH,
        index=False,
    )

    print()
    print(
        "[OUTPUT] Dataset final sauvegardé : "
        f"{TRANSFER_PERFORMANCE_OUTPUT_PATH}"
    )

    print(
        f"[OUTPUT] {len(result):,} lignes."
    )


# ============================================================================
# MAIN
# ============================================================================

def main():

    print("=" * 70)
    print(
        "CONSTRUCTION DATASET RÉEL "
        "TRANSFERTS + PERFORMANCE PRE/POST"
    )
    print("=" * 70)

    # ------------------------------------------------------------------------
    # 1. Chargement des performances
    # ------------------------------------------------------------------------

    performance_loader = RealPerformanceLoader(
        PERFORMANCE_INPUT_PATH
    )

    performances = (
        performance_loader.load()
    )

    # ------------------------------------------------------------------------
    # 2. Calcul des scores / percentiles
    # ------------------------------------------------------------------------

    scorer = PerformanceScorer(
        performances_df=performances
    )

    performances_scored = (
        scorer.calculate_scores()
    )

    PERFORMANCE_SCORED_REAL_OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    performances_scored.to_csv(
        PERFORMANCE_SCORED_REAL_OUTPUT_PATH,
        index=False,
    )

    print(
        "[OUTPUT] Performances scorées sauvegardées : "
        f"{PERFORMANCE_SCORED_REAL_OUTPUT_PATH}"
    )

    # ------------------------------------------------------------------------
    # 3. Chargement des transferts réels
    # ------------------------------------------------------------------------

    transfer_loader = RealTransferLoader()

    transfers = (
        transfer_loader.load()
    )

    TRANSFER_RAW_OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    transfers.drop(
        columns=[
            "player_key"
        ],
        errors="ignore",
    ).to_csv(
        TRANSFER_RAW_OUTPUT_PATH,
        index=False,
    )

    print(
        "[OUTPUT] Transferts réels sauvegardés : "
        f"{TRANSFER_RAW_OUTPUT_PATH}"
    )

    # ------------------------------------------------------------------------
    # 4. Contrôle de l'intersection joueurs
    # ------------------------------------------------------------------------

    performance_players = set(
        performances_scored[
            "player"
        ]
        .astype(str)
        .str.strip()
        .str.casefold()
    )

    transfer_players = set(
        transfers[
            "player_name"
        ]
        .astype(str)
        .str.strip()
        .str.casefold()
    )

    common_players = (
        performance_players
        & transfer_players
    )

    print()
    print(
        "[MATCHING]"
    )

    print(
        f"Joueurs performances : "
        f"{len(performance_players):,}"
    )

    print(
        f"Joueurs transferts   : "
        f"{len(transfer_players):,}"
    )

    print(
        f"Joueurs communs      : "
        f"{len(common_players):,}"
    )

    # ------------------------------------------------------------------------
    # 5. Construction PRE / POST
    # ------------------------------------------------------------------------

    builder = TransferPerformanceBuilder(
        performances_scored=performances_scored,
        transfers=transfers,
    )

    result = builder.build()

    if result.empty:

        raise RuntimeError(
            "Le dataset final est vide."
        )

    # ------------------------------------------------------------------------
    # 6. Enrichissement minimal
    # ------------------------------------------------------------------------

    result = filter_real_dataset(
        result
    )

    # ------------------------------------------------------------------------
    # 7. Quality report
    # ------------------------------------------------------------------------

    generate_quality_report(
        result
    )

    # ------------------------------------------------------------------------
    # 8. Sauvegarde
    # ------------------------------------------------------------------------

    save_dataset(
        result
    )

    # ------------------------------------------------------------------------
    # 9. Aperçu
    # ------------------------------------------------------------------------

    print()
    print("=" * 70)
    print("APERÇU DATASET FINAL")
    print("=" * 70)

    preview_columns = [
        "player_id",
        "player_name",
        "transfer_date",
        "from_club_name",
        "to_club_name",
        "transfer_fee",
        "market_value_in_eur",
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

    available_columns = [
        column
        for column in preview_columns
        if column in result.columns
    ]

    print(
        result[
            available_columns
        ]
        .head(20)
        .to_string(index=False)
    )

    print()
    print("=" * 70)
    print("✓ CONSTRUCTION DATASET RÉELLE TERMINÉE")
    print("=" * 70)


if __name__ == "__main__":
    main()