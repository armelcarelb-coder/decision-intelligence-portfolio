from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import duckdb
import pandas as pd


@dataclass(frozen=True)
class AuditConfig:
    """Configuration for the real performance dataset audit."""

    performance_path: Path
    database_path: Path
    minimum_minutes: int = 900
    expected_seasons: int = 14
    national_team_competition: str = (
        "national_team_competition"
    )


class RealPerformanceAudit:
    """Audit the real player performance dataset."""

    def __init__(self, config: AuditConfig) -> None:
        self.config = config

    def load_performance_dataset(self) -> pd.DataFrame:
        """Load the generated performance dataset."""

        path = self.config.performance_path

        if not path.exists():
            raise FileNotFoundError(
                f"Performance dataset not found: {path}"
            )

        return pd.read_csv(
            path,
            parse_dates=[
                "season_start",
                "season_end",
                "first_match_date",
                "last_match_date",
            ],
        )

    def load_transfers(self) -> pd.DataFrame:
        """Load transfer records from DuckDB."""

        path = self.config.database_path

        if not path.exists():
            raise FileNotFoundError(
                f"DuckDB database not found: {path}"
            )

        connection = duckdb.connect(
            str(path),
            read_only=True,
        )

        try:
            return connection.execute(
                """
                SELECT
                    player_id,
                    player_name,
                    transfer_date,
                    transfer_season
                FROM transfers
                """
            ).fetchdf()
        finally:
            connection.close()

    @staticmethod
    def audit_global(
        df: pd.DataFrame,
    ) -> dict[str, object]:
        """Audit global dataset dimensions."""

        return {
            "rows": len(df),
            "players": df["player_id"].nunique(),
            "seasons": df["season"].nunique(),
            "competitions": df["competition_id"].nunique(),
        }

    def audit_season_bounds(
        self,
        df: pd.DataFrame,
    ) -> pd.DataFrame:
        """Audit season boundaries."""

        seasons = (
            df.groupby("season", dropna=False)
            .agg(
                season_start=("season_start", "min"),
                season_end=("season_end", "max"),
                first_match=("first_match_date", "min"),
                last_match=("last_match_date", "max"),
                players=("player_id", "nunique"),
                rows=("player_id", "size"),
            )
            .reset_index()
            .sort_values("season")
        )

        seasons["duration_days"] = (
            seasons["season_end"] - seasons["season_start"]
        ).dt.days

        return seasons

    @staticmethod
    def audit_players(
        df: pd.DataFrame,
    ) -> dict[str, object]:
        """Audit player identifiers."""

        null_ids = int(
            df["player_id"].isna().sum()
        )

        names_per_player = (
            df.groupby("player_id")["player"]
            .nunique()
        )

        return {
            "unique_players": df["player_id"].nunique(),
            "null_player_ids": null_ids,
            "players_with_multiple_names": int(
                names_per_player.gt(1).sum()
            ),
        }

    def audit_minutes(
        self,
        df: pd.DataFrame,
    ) -> dict[str, object]:
        """Audit player minutes."""

        minutes = pd.to_numeric(
            df["minutes"],
            errors="coerce",
        )

        return {
            "total": float(minutes.sum()),
            "minimum": float(minutes.min()),
            "maximum": float(minutes.max()),
            "mean": float(minutes.mean()),
            "median": float(minutes.median()),
            "null": int(minutes.isna().sum()),
            "negative": int((minutes < 0).sum()),
            "zero": int((minutes == 0).sum()),
            "above_threshold": int(
                (
                    minutes
                    >= self.config.minimum_minutes
                ).sum()
            ),
        }

    @staticmethod
    def audit_duplicates(
        df: pd.DataFrame,
    ) -> dict[str, object]:
        """Audit duplicate player-season-competition records."""

        key = [
            "player_id",
            "season",
            "competition_id",
        ]

        duplicate_mask = df.duplicated(
            subset=key,
            keep=False,
        )

        return {
            "duplicate_rows": int(
                duplicate_mask.sum()
            ),
            "duplicate_groups": int(
                df.loc[duplicate_mask]
                .groupby(key)
                .ngroups
            ),
        }

    def audit_competitions(
        self,
        df: pd.DataFrame,
    ) -> dict[str, object]:
        """Audit competition classification."""

        unknown_rows = int(
            df["competition_level"]
            .fillna("")
            .eq("UNKNOWN")
            .sum()
        )

        national_team_rows = int(
            df["competition_type"]
            .fillna("")
            .eq(
                self.config.national_team_competition
            )
            .sum()
        )

        return {
            "levels": (
                df["competition_level"]
                .fillna("NULL")
                .value_counts()
                .to_dict()
            ),
            "unknown_rows": unknown_rows,
            "national_team_rows": (
                national_team_rows
            ),
        }

    def audit_dates(
        self,
        df: pd.DataFrame,
    ) -> dict[str, int]:
        """Audit date consistency."""

        invalid_season_dates = (
            df["season_start"].isna()
            | df["season_end"].isna()
            | (
                df["season_start"]
                > df["season_end"]
            )
        )

        invalid_match_dates = (
            df["first_match_date"].notna()
            & df["last_match_date"].notna()
            & (
                df["first_match_date"]
                > df["last_match_date"]
            )
        )

        matches_outside_season = (
            (
                df["first_match_date"].notna()
                & df["season_start"].notna()
                & (
                    df["first_match_date"]
                    < df["season_start"]
                )
            )
            |
            (
                df["last_match_date"].notna()
                & df["season_end"].notna()
                & (
                    df["last_match_date"]
                    > df["season_end"]
                )
            )
        )

        return {
            "invalid_season_dates": int(
                invalid_season_dates.sum()
            ),
            "invalid_match_dates": int(
                invalid_match_dates.sum()
            ),
            "matches_outside_season": int(
                matches_outside_season.sum()
            ),
        }

    @staticmethod
    def audit_outside_season_details(
        df: pd.DataFrame,
    ) -> dict[str, object]:
        """Analyse records outside season boundaries."""

        outside_start = (
            df["first_match_date"].notna()
            & df["season_start"].notna()
            & (
                df["first_match_date"]
                < df["season_start"]
            )
        )

        outside_end = (
            df["last_match_date"].notna()
            & df["season_end"].notna()
            & (
                df["last_match_date"]
                > df["season_end"]
            )
        )

        outside = df[
            outside_start | outside_end
        ].copy()

        if outside.empty:
            return {
                "rows": 0,
                "by_competition": {},
                "by_season": {},
                "by_competition_type": {},
                "examples": [],
            }

        competition_breakdown = (
            outside.groupby(
                [
                    "competition_id",
                    "competition_name",
                    "competition_level",
                ]
            )
            .size()
            .sort_values(ascending=False)
        )

        season_breakdown = (
            outside.groupby("season")
            .size()
            .sort_index()
        )

        competition_type_breakdown = (
            outside["competition_type"]
            .fillna("NULL")
            .value_counts()
        )

        example_columns = [
            "player_id",
            "player",
            "season",
            "competition_id",
            "competition_name",
            "competition_level",
            "season_start",
            "season_end",
            "first_match_date",
            "last_match_date",
        ]

        examples = (
            outside[
                example_columns
            ]
            .sort_values(
                [
                    "season",
                    "competition_id",
                    "player_id",
                ]
            )
            .head(30)
        )

        return {
            "rows": len(outside),
            "by_competition": (
                competition_breakdown
                .reset_index(name="rows")
                .to_dict("records")
            ),
            "by_season": (
                season_breakdown
                .to_dict()
            ),
            "by_competition_type": (
                competition_type_breakdown
                .to_dict()
            ),
            "examples": (
                examples.to_dict("records")
            ),
        }

    @staticmethod
    def audit_xg_xa(
        df: pd.DataFrame,
    ) -> dict[str, object]:
        """Verify that xG/xA are not fabricated."""

        return {
            "xg_null": int(
                df["xg"].isna().sum()
            ),
            "xa_null": int(
                df["xa"].isna().sum()
            ),
            "xg_all_null": bool(
                df["xg"].isna().all()
            ),
            "xa_all_null": bool(
                df["xa"].isna().all()
            ),
        }

    def audit_transfer_coverage(
        self,
        df: pd.DataFrame,
        transfers: pd.DataFrame,
    ) -> dict[str, object]:
        """Audit performance coverage against transfers."""

        performance_players = set(
            df["player_id"]
            .dropna()
            .astype(int)
            .unique()
        )

        transfer_players = set(
            transfers["player_id"]
            .dropna()
            .astype(int)
            .unique()
        )

        common_players = (
            performance_players
            & transfer_players
        )

        performance_only = (
            performance_players
            - transfer_players
        )

        transfer_only = (
            transfer_players
            - performance_players
        )

        eligible_players = set(
            df.groupby("player_id")["minutes"]
            .sum()
            .loc[
                lambda values: (
                    values
                    >= self.config.minimum_minutes
                )
            ]
            .index
            .astype(int)
        )

        eligible_transferred = (
            eligible_players
            & transfer_players
        )

        coverage = (
            len(common_players)
            / len(transfer_players)
            if transfer_players
            else 0.0
        )

        return {
            "performance_players": len(
                performance_players
            ),
            "transfer_players": len(
                transfer_players
            ),
            "common_players": len(
                common_players
            ),
            "performance_only": len(
                performance_only
            ),
            "transfer_only": len(
                transfer_only
            ),
            "coverage_ratio": coverage,
            "eligible_players": len(
                eligible_players
            ),
            "eligible_transferred": len(
                eligible_transferred
            ),
        }

    def audit_season_coverage(
        self,
        df: pd.DataFrame,
    ) -> pd.DataFrame:
        """Audit dataset coverage by season."""

        coverage = (
            df.groupby("season")
            .agg(
                rows=("player_id", "size"),
                players=("player_id", "nunique"),
                competitions=(
                    "competition_id",
                    "nunique",
                ),
                total_minutes=("minutes", "sum"),
                total_appearances=(
                    "appearances",
                    "sum",
                ),
            )
            .reset_index()
            .sort_values("season")
        )

        players_900 = (
            df.assign(
                eligible=(
                    df["minutes"]
                    >= self.config.minimum_minutes
                )
            )
            .groupby("season")["eligible"]
            .sum()
        )

        coverage["players_900min"] = (
            coverage["season"]
            .map(players_900)
            .fillna(0)
            .astype(int)
        )

        return coverage

    def run(self) -> dict[str, object]:
        """Run the complete audit."""

        df = self.load_performance_dataset()
        transfers = self.load_transfers()

        seasons = self.audit_season_bounds(df)

        return {
            "global": self.audit_global(df),
            "players": self.audit_players(df),
            "minutes": self.audit_minutes(df),
            "competitions": (
                self.audit_competitions(df)
            ),
            "duplicates": (
                self.audit_duplicates(df)
            ),
            "dates": self.audit_dates(df),
            "outside_season": (
                self.audit_outside_season_details(
                    df
                )
            ),
            "xg_xa": self.audit_xg_xa(df),
            "transfer_coverage": (
                self.audit_transfer_coverage(
                    df,
                    transfers,
                )
            ),
            "season_bounds": seasons,
            "season_coverage": (
                self.audit_season_coverage(df)
            ),
        }


def print_section(title: str) -> None:
    """Print a formatted audit section."""

    print()
    print("=" * 80)
    print(title)
    print("=" * 80)


def print_dict(
    data: dict[str, object],
    indent: int = 2,
) -> None:
    """Print dictionary values."""

    prefix = " " * indent

    for key, value in data.items():
        if isinstance(value, float):
            print(f"{prefix}{key}: {value:.4f}")
        else:
            print(f"{prefix}{key}: {value}")

def audit_season_calendar_anomalies(self) -> dict:
    """
    Analyse les saisons dont les bornes calendaires semblent anormales.

    L'objectif est d'identifier :
        - les compétitions responsables des dates extrêmes ;
        - les types de compétition concernés ;
        - les joueurs concernés ;
        - les dates minimales/maximales observées ;
        - les éventuelles incohérences entre season et match_date.

    Aucun enregistrement n'est supprimé ou modifié.
    """

    df = self.df.copy()

    required_columns = {
        "player_id",
        "player",
        "season",
        "competition_id",
        "competition_name",
        "competition_type",
        "competition_sub_type",
        "competition_level",
        "first_match_date",
        "last_match_date",
    }

    missing = required_columns - set(df.columns)

    if missing:
        raise ValueError(
            "Colonnes nécessaires à l'audit du calendrier absentes : "
            + ", ".join(sorted(missing))
        )

    df["first_match_date"] = pd.to_datetime(
        df["first_match_date"],
        errors="coerce",
    )

    df["last_match_date"] = pd.to_datetime(
        df["last_match_date"],
        errors="coerce",
    )

    df["season"] = df["season"].astype(str)

    # --------------------------------------------------------------
    # Bornes globales par saison
    # --------------------------------------------------------------

    season_bounds = (
        df.groupby("season", as_index=False)
        .agg(
            season_start=("first_match_date", "min"),
            season_end=("last_match_date", "max"),
            rows=("player_id", "size"),
            players=("player_id", "nunique"),
            competitions=("competition_id", "nunique"),
        )
        .sort_values("season")
    )

    # --------------------------------------------------------------
    # Détection des saisons suspectes
    #
    # Une saison est considérée suspecte si :
    #   - elle couvre plus de 450 jours ;
    #   - ou son début est très tôt (< 1er juin) ;
    #   - ou sa fin est très tardive (> 31 juillet de l'année suivante).
    #
    # Ce sont des indicateurs d'audit, pas des règles de suppression.
    # --------------------------------------------------------------

    season_bounds["duration_days"] = (
        season_bounds["season_end"]
        - season_bounds["season_start"]
    ).dt.days

    season_bounds["season_year"] = pd.to_numeric(
        season_bounds["season"],
        errors="coerce",
    )

    season_bounds["expected_year_start"] = pd.to_datetime(
        season_bounds["season_year"].astype("Int64").astype(str)
        + "-06-01",
        errors="coerce",
    )

    season_bounds["expected_year_end"] = pd.to_datetime(
        (season_bounds["season_year"] + 1)
        .astype("Int64")
        .astype(str)
        + "-07-31",
        errors="coerce",
    )

    suspicious = season_bounds[
        (
            season_bounds["duration_days"] > 450
        )
        |
        (
            season_bounds["season_start"]
            < season_bounds["expected_year_start"]
        )
        |
        (
            season_bounds["season_end"]
            > season_bounds["expected_year_end"]
        )
    ].copy()

    # --------------------------------------------------------------
    # Détail des compétitions responsables des bornes
    # --------------------------------------------------------------

    details = []

    for _, row in suspicious.iterrows():
        season = row["season"]

        season_df = df[
            df["season"] == season
        ].copy()

        if season_df.empty:
            continue

        competition_details = (
            season_df.groupby(
                [
                    "competition_id",
                    "competition_name",
                    "competition_type",
                    "competition_sub_type",
                    "competition_level",
                ],
                dropna=False,
            )
            .agg(
                first_date=(
                    "first_match_date",
                    "min",
                ),
                last_date=(
                    "last_match_date",
                    "max",
                ),
                rows=(
                    "player_id",
                    "size",
                ),
                players=(
                    "player_id",
                    "nunique",
                ),
            )
            .reset_index()
        )

        competition_details["season"] = season

        competition_details["duration_days"] = (
            competition_details["last_date"]
            - competition_details["first_date"]
        ).dt.days

        competition_details["is_start_extreme"] = (
            competition_details["first_date"]
            == row["season_start"]
        )

        competition_details["is_end_extreme"] = (
            competition_details["last_date"]
            == row["season_end"]
        )

        details.append(
            competition_details
        )

    if details:
        competition_details_df = pd.concat(
            details,
            ignore_index=True,
        )
    else:
        competition_details_df = pd.DataFrame()

    # --------------------------------------------------------------
    # Enregistrements responsables des dates extrêmes
    # --------------------------------------------------------------

    extreme_records = []

    for _, row in suspicious.iterrows():
        season = row["season"]

        season_df = df[
            df["season"] == season
        ].copy()

        if season_df.empty:
            continue

        start_records = season_df[
            season_df["first_match_date"]
            == row["season_start"]
        ].copy()

        end_records = season_df[
            season_df["last_match_date"]
            == row["season_end"]
        ].copy()

        start_records["extreme_type"] = "SEASON_START"
        end_records["extreme_type"] = "SEASON_END"

        extreme_records.append(start_records)
        extreme_records.append(end_records)

    if extreme_records:
        extreme_records_df = pd.concat(
            extreme_records,
            ignore_index=True,
        )
    else:
        extreme_records_df = pd.DataFrame()

    return {
        "season_bounds": season_bounds,
        "suspicious_seasons": suspicious,
        "competition_details": competition_details_df,
        "extreme_records": extreme_records_df,
    }

def print_season_calendar_anomalies(
    self,
    report: dict,
) -> None:
    """
    Affiche l'analyse détaillée des anomalies de calendrier.
    """

    print_section(
        "SEASON CALENDAR — TARGETED ANOMALY ANALYSIS"
    )

    suspicious = report[
        "suspicious_seasons"
    ]

    if suspicious.empty:
        print("Aucune saison suspecte détectée.")
        return

    print(
        f"Saisons suspectes : "
        f"{len(suspicious)}"
    )

    print()

    print(
        suspicious[
            [
                "season",
                "season_start",
                "season_end",
                "duration_days",
                "rows",
                "players",
                "competitions",
            ]
        ]
        .to_string(index=False)
    )

    competition_details = report[
        "competition_details"
    ]

    if competition_details.empty:
        return

    print()
    print("-" * 80)
    print("COMPETITIONS RESPONSIBLE FOR EXTREME DATES")
    print("-" * 80)

    display_columns = [
        "season",
        "competition_id",
        "competition_name",
        "competition_type",
        "competition_sub_type",
        "competition_level",
        "first_date",
        "last_date",
        "duration_days",
        "rows",
        "players",
        "is_start_extreme",
        "is_end_extreme",
    ]

    print(
        competition_details[
            display_columns
        ]
        .sort_values(
            [
                "season",
                "first_date",
                "last_date",
            ]
        )
        .to_string(index=False)
    )

    extreme_records = report[
        "extreme_records"
    ]

    if extreme_records.empty:
        return

    print()
    print("-" * 80)
    print("EXTREME RECORDS")
    print("-" * 80)

    extreme_columns = [
        "season",
        "extreme_type",
        "player_id",
        "player",
        "competition_id",
        "competition_name",
        "competition_type",
        "competition_sub_type",
        "competition_level",
        "first_match_date",
        "last_match_date",
    ]

    print(
        extreme_records[
            extreme_columns
        ]
        .sort_values(
            [
                "season",
                "extreme_type",
                "first_match_date",
            ]
        )
        .to_string(index=False)
    )

def main() -> None:
    """Run the real performance dataset audit."""

    config = AuditConfig(
        performance_path=Path(
            "data/performances/"
            "player_competition_season_performance.csv"
        ),
        database_path=Path(
            "data/historical/transfermarkt-datasets.duckdb"
        ),
    )
    
    season_calendar_report = (
        audit_season_calendar_anomalies()
    )

    print_season_calendar_anomalies(
        season_calendar_report
    )
    
    report = audit.run()
    report["season_calendar_anomalies"] = (
        season_calendar_report
    )

    print()
    print("=" * 80)
    print("REAL PERFORMANCE LOADER — AUDIT")
    print("=" * 80)

    print_section("GLOBAL")
    print_dict(report["global"])

    print_section("PLAYERS")
    print_dict(report["players"])

    print_section("MINUTES")
    print_dict(report["minutes"])

    print_section("DUPLICATES")
    print_dict(report["duplicates"])

    print_section("DATES")
    print_dict(report["dates"])

    print_section(
        "OUTSIDE SEASON — DETAILED ANALYSIS"
    )

    outside = report["outside_season"]

    print(
        f"Rows concerned: "
        f"{outside['rows']:,}"
    )

    print("\nBy competition:")
    for item in outside["by_competition"]:
        print(
            f"  {item['competition_id']} | "
            f"{item['competition_name']} | "
            f"{item['competition_level']} | "
            f"{item['rows']:,}"
        )

    print("\nBy season:")
    for season, rows in (
        outside["by_season"].items()
    ):
        print(
            f"  {season}: {rows:,}"
        )

    print("\nBy competition type:")
    for competition_type, rows in (
        outside["by_competition_type"].items()
    ):
        print(
            f"  {competition_type}: "
            f"{rows:,}"
        )

    print("\nExamples:")
    for example in outside["examples"]:
        print(
            f"  player={example['player_id']} "
            f"| {example['player']} "
            f"| season={example['season']} "
            f"| competition="
            f"{example['competition_id']} "
            f"| first="
            f"{example['first_match_date']} "
            f"| last="
            f"{example['last_match_date']} "
            f"| season_start="
            f"{example['season_start']} "
            f"| season_end="
            f"{example['season_end']}"
        )

    print_section("COMPETITIONS")
    print_dict(report["competitions"])

    print_section("xG / xA")
    print_dict(report["xg_xa"])

    print_section("TRANSFER COVERAGE")
    print_dict(
        report["transfer_coverage"]
    )

    print_section("SEASON COVERAGE")
    print(
        report["season_coverage"]
        .to_string(index=False)
    )


if __name__ == "__main__":
    main()