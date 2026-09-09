from dataclasses import dataclass
from pathlib import Path

import duckdb
import pandas as pd


@dataclass(frozen=True)
class AuditConfig:
    performance_path: Path
    database_path: Path

    minimum_minutes: int = 900
    expected_seasons: int = 14

    national_team_competition: str = "national_team_competition"

    suspicious_duration_days: int = 450

    expected_season_start_month: int = 6
    expected_season_start_day: int = 1

    expected_season_end_month: int = 7
    expected_season_end_day: int = 31


class RealPerformanceAudit:
    def __init__(self, config: AuditConfig):
        self.config = config

    # ============================================================
    # LOAD DATA
    # ============================================================

    def load_performance_dataset(self) -> pd.DataFrame:
        path = self.config.performance_path

        if not path.exists():
            raise FileNotFoundError(
                f"Performance dataset not found: {path}"
            )

        df = pd.read_csv(path)

        required_columns = {
            "player_id",
            "player",
            "season",
            "season_start",
            "season_end",
            "competition_id",
            "competition_name",
            "competition_level",
            "first_match_date",
            "last_match_date",
            "appearances",
            "minutes",
            "goals",
            "assists",
            "xg",
            "xa",
        }

        missing = required_columns - set(df.columns)

        if missing:
            raise ValueError(
                f"Missing columns in performance dataset: {sorted(missing)}"
            )

        for column in [
            "season_start",
            "season_end",
            "first_match_date",
            "last_match_date",
        ]:
            df[column] = pd.to_datetime(
                df[column],
                errors="coerce",
            )

        return df

    def load_transfers(self) -> pd.DataFrame:
        if not self.config.database_path.exists():
            raise FileNotFoundError(
                f"Transfermarkt database not found: "
                f"{self.config.database_path}"
            )

        query = """
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
        """

        with duckdb.connect(
            str(self.config.database_path),
            read_only=True,
        ) as con:
            transfers = con.execute(query).df()

        transfers["transfer_date"] = pd.to_datetime(
            transfers["transfer_date"],
            errors="coerce",
        )

        return transfers

    # ============================================================
    # GLOBAL AUDIT
    # ============================================================

    def audit_global(self, df: pd.DataFrame) -> dict:
        return {
            "rows": len(df),
            "unique_players": df["player_id"].nunique(),
            "seasons": df["season"].nunique(),
            "competitions": df["competition_id"].nunique(),
        }

    # ============================================================
    # SEASON BOUNDS
    # ============================================================

    def audit_season_bounds(self, df: pd.DataFrame) -> pd.DataFrame:
        result = (
            df.groupby("season")
            .agg(
                season_start=("season_start", "min"),
                season_end=("season_end", "max"),
                first_match=("first_match_date", "min"),
                last_match=("last_match_date", "max"),
                rows=("player_id", "size"),
                players=("player_id", "nunique"),
            )
            .reset_index()
            .sort_values("season")
        )

        result["duration_days"] = (
            result["season_end"] - result["season_start"]
        ).dt.days

        return result

    # ============================================================
    # PLAYERS
    # ============================================================

    def audit_players(self, df: pd.DataFrame) -> dict:
        name_counts = (
            df.groupby("player_id")["player"]
            .nunique()
        )

        players_with_multiple_names = (
            name_counts[name_counts > 1]
        )

        return {
            "unique_players": df["player_id"].nunique(),
            "null_player_ids": int(df["player_id"].isna().sum()),
            "players_with_multiple_names": len(
                players_with_multiple_names
            ),
        }

    # ============================================================
    # MINUTES
    # ============================================================

    def audit_minutes(self, df: pd.DataFrame) -> dict:
        minutes = pd.to_numeric(
            df["minutes"],
            errors="coerce",
        )

        return {
            "total_minutes": float(minutes.sum()),
            "min_minutes": float(minutes.min()),
            "max_minutes": float(minutes.max()),
            "mean_minutes": float(minutes.mean()),
            "median_minutes": float(minutes.median()),
            "null_minutes": int(minutes.isna().sum()),
            "negative_minutes": int((minutes < 0).sum()),
            "zero_minutes": int((minutes == 0).sum()),
            "above_threshold": int(
                (minutes >= self.config.minimum_minutes).sum()
            ),
        }

    # ============================================================
    # DUPLICATES
    # ============================================================

    def audit_duplicates(self, df: pd.DataFrame) -> dict:
        key_columns = [
            "player_id",
            "season",
            "competition_id",
        ]

        duplicate_mask = df.duplicated(
            subset=key_columns,
            keep=False,
        )

        duplicate_rows = df.loc[duplicate_mask]

        duplicate_groups = (
            duplicate_rows.groupby(key_columns)
            .size()
            if not duplicate_rows.empty
            else pd.Series(dtype="int64")
        )

        return {
            "duplicate_rows": len(duplicate_rows),
            "duplicate_groups": int(
                (duplicate_groups > 1).sum()
            ),
        }

    # ============================================================
    # COMPETITIONS
    # ============================================================

    def audit_competitions(self, df: pd.DataFrame) -> dict:
        level_counts = (
            df["competition_level"]
            .value_counts(dropna=False)
            .to_dict()
        )

        national_team_rows = int(
            (
                df["competition_type"]
                == self.config.national_team_competition
            ).sum()
        )

        unknown_rows = int(
            (
                df["competition_level"]
                == "UNKNOWN"
            ).sum()
        )

        return {
            "competition_levels": level_counts,
            "unknown_rows": unknown_rows,
            "national_team_rows": national_team_rows,
        }

    # ============================================================
    # DATES
    # ============================================================

    def audit_dates(self, df: pd.DataFrame) -> dict:
        invalid_season_dates = int(
            (
                df["season_start"].isna()
                | df["season_end"].isna()
            ).sum()
        )

        invalid_match_dates = int(
            (
                df["first_match_date"].isna()
                | df["last_match_date"].isna()
            ).sum()
        )

        matches_outside_season = int(
            (
                (df["first_match_date"] < df["season_start"])
                | (df["last_match_date"] > df["season_end"])
            ).sum()
        )

        return {
            "invalid_season_dates": invalid_season_dates,
            "invalid_match_dates": invalid_match_dates,
            "matches_outside_season": matches_outside_season,
        }

    # ============================================================
    # OUTSIDE SEASON DETAILS
    # ============================================================

    def audit_outside_season_details(
        self,
        df: pd.DataFrame,
    ) -> pd.DataFrame:

        mask = (
            (df["first_match_date"] < df["season_start"])
            | (df["last_match_date"] > df["season_end"])
        )

        columns = [
            "player_id",
            "player",
            "season",
            "competition_id",
            "competition_name",
            "competition_level",
            "first_match_date",
            "last_match_date",
            "season_start",
            "season_end",
        ]

        return (
            df.loc[mask, columns]
            .sort_values(
                [
                    "season",
                    "first_match_date",
                ]
            )
            .reset_index(drop=True)
        )

    # ============================================================
    # XG / XA
    # ============================================================

    def audit_xg_xa(self, df: pd.DataFrame) -> dict:
        return {
            "xg_rows": int(df["xg"].notna().sum()),
            "xg_null_rows": int(df["xg"].isna().sum()),
            "xa_rows": int(df["xa"].notna().sum()),
            "xa_null_rows": int(df["xa"].isna().sum()),
        }

    # ============================================================
    # TRANSFER COVERAGE
    # ============================================================

    def audit_transfer_coverage(
        self,
        df: pd.DataFrame,
        transfers: pd.DataFrame,
    ) -> dict:

        performance_players = set(
            df["player_id"]
            .dropna()
            .astype(int)
        )

        transfer_players = set(
            transfers["player_id"]
            .dropna()
            .astype(int)
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
            df.loc[
                df["minutes"] >= self.config.minimum_minutes,
                "player_id",
            ]
            .dropna()
            .astype(int)
        )

        eligible_transferred = (
            eligible_players
            & transfer_players
        )

        coverage_ratio = (
            len(common_players)
            / len(performance_players)
            if performance_players
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
            "coverage_ratio": coverage_ratio,
            "eligible_players": len(
                eligible_players
            ),
            "eligible_transferred": len(
                eligible_transferred
            ),
        }

    # ============================================================
    # SEASON COVERAGE
    # ============================================================

    def audit_season_coverage(
        self,
        df: pd.DataFrame,
    ) -> pd.DataFrame:

        result = (
            df.groupby("season")
            .agg(
                rows=("player_id", "size"),
                players=("player_id", "nunique"),
                competitions=("competition_id", "nunique"),
                total_minutes=("minutes", "sum"),
                appearances=("appearances", "sum"),
            )
            .reset_index()
            .sort_values("season")
        )

        eligible = (
            df[df["minutes"] >= self.config.minimum_minutes]
            .groupby("season")["player_id"]
            .nunique()
            .rename("players_900min")
        )

        result = result.merge(
            eligible,
            on="season",
            how="left",
        )

        result["players_900min"] = (
            result["players_900min"]
            .fillna(0)
            .astype(int)
        )

        return result

    # ============================================================
    # TARGETED SEASON CALENDAR AUDIT
    # ============================================================

    def audit_season_calendar_anomalies(
        self,
        df: pd.DataFrame,
    ) -> dict:

        season_bounds = (
            df.groupby("season")
            .agg(
                actual_start=("first_match_date", "min"),
                actual_end=("last_match_date", "max"),
            )
            .reset_index()
            .sort_values("season")
        )

        season_bounds["duration_days"] = (
            season_bounds["actual_end"]
            - season_bounds["actual_start"]
        ).dt.days

        # --------------------------------------------------------
        # Expected calendar envelope
        #
        # This is ONLY an audit heuristic.
        # It does NOT modify the dataset.
        # --------------------------------------------------------

        season_bounds["expected_start"] = pd.to_datetime(
            season_bounds["season"].astype(str)
            + f"-{self.config.expected_season_start_month:02d}"
            + f"-{self.config.expected_season_start_day:02d}"
        )

        season_bounds["expected_end"] = pd.to_datetime(
            (
                season_bounds["season"] + 1
            ).astype(str)
            + f"-{self.config.expected_season_end_month:02d}"
            + f"-{self.config.expected_season_end_day:02d}"
        )

        season_bounds["start_before_expected"] = (
            season_bounds["actual_start"]
            < season_bounds["expected_start"]
        )

        season_bounds["end_after_expected"] = (
            season_bounds["actual_end"]
            > season_bounds["expected_end"]
        )

        season_bounds["duration_suspicious"] = (
            season_bounds["duration_days"]
            > self.config.suspicious_duration_days
        )

        suspicious_seasons = season_bounds[
            (
                season_bounds["start_before_expected"]
                | season_bounds["end_after_expected"]
                | season_bounds["duration_suspicious"]
            )
        ].copy()

        # --------------------------------------------------------
        # Competition-level analysis
        # --------------------------------------------------------

        competition_bounds = (
            df.groupby(
                [
                    "season",
                    "competition_id",
                    "competition_name",
                    "competition_level",
                ]
            )
            .agg(
                first_match=("first_match_date", "min"),
                last_match=("last_match_date", "max"),
                rows=("player_id", "size"),
                players=("player_id", "nunique"),
            )
            .reset_index()
        )

        competition_bounds["duration_days"] = (
            competition_bounds["last_match"]
            - competition_bounds["first_match"]
        ).dt.days

        # --------------------------------------------------------
        # Extreme records
        # --------------------------------------------------------

        earliest_records = (
            df[
                [
                    "season",
                    "player_id",
                    "player",
                    "competition_id",
                    "competition_name",
                    "competition_level",
                    "first_match_date",
                    "last_match_date",
                ]
            ]
            .sort_values("first_match_date")
            .head(20)
            .reset_index(drop=True)
        )

        latest_records = (
            df[
                [
                    "season",
                    "player_id",
                    "player",
                    "competition_id",
                    "competition_name",
                    "competition_level",
                    "first_match_date",
                    "last_match_date",
                ]
            ]
            .sort_values(
                "last_match_date",
                ascending=False,
            )
            .head(20)
            .reset_index(drop=True)
        )

        # --------------------------------------------------------
        # Records outside expected envelope
        # --------------------------------------------------------

        merged = df.merge(
            season_bounds[
                [
                    "season",
                    "expected_start",
                    "expected_end",
                ]
            ],
            on="season",
            how="left",
        )

        expected_envelope_violations = merged[
            (
                merged["first_match_date"]
                < merged["expected_start"]
            )
            | (
                merged["last_match_date"]
                > merged["expected_end"]
            )
        ].copy()

        expected_envelope_violations = (
            expected_envelope_violations[
                [
                    "season",
                    "player_id",
                    "player",
                    "competition_id",
                    "competition_name",
                    "competition_level",
                    "first_match_date",
                    "last_match_date",
                    "expected_start",
                    "expected_end",
                ]
            ]
            .sort_values(
                [
                    "season",
                    "first_match_date",
                ]
            )
            .reset_index(drop=True)
        )

        return {
            "season_bounds": season_bounds,
            "suspicious_seasons": suspicious_seasons,
            "competition_bounds": competition_bounds,
            "earliest_records": earliest_records,
            "latest_records": latest_records,
            "expected_envelope_violations": (
                expected_envelope_violations
            ),
        }

    # ============================================================
    # RUN COMPLETE AUDIT
    # ============================================================

    def run(self) -> dict:
        df = self.load_performance_dataset()
        transfers = self.load_transfers()

        report = {
            "global": self.audit_global(df),
            "season_bounds": self.audit_season_bounds(df),
            "players": self.audit_players(df),
            "minutes": self.audit_minutes(df),
            "duplicates": self.audit_duplicates(df),
            "competitions": self.audit_competitions(df),
            "dates": self.audit_dates(df),
            "outside_season_details": (
                self.audit_outside_season_details(df)
            ),
            "xg_xa": self.audit_xg_xa(df),
            "transfer_coverage": (
                self.audit_transfer_coverage(
                    df,
                    transfers,
                )
            ),
            "season_coverage": (
                self.audit_season_coverage(df)
            ),
            "season_calendar_anomalies": (
                self.audit_season_calendar_anomalies(df)
            ),
        }

        return report

    # ============================================================
    # PRINT TARGETED CALENDAR AUDIT
    # ============================================================

    def print_season_calendar_anomalies(
        self,
        report: dict,
    ) -> None:

        calendar = report[
            "season_calendar_anomalies"
        ]

        print()
        print("=" * 80)
        print("TARGETED SEASON CALENDAR AUDIT")
        print("=" * 80)

        print()
        print("--- SEASON BOUNDS ---")

        print(
            calendar[
                "season_bounds"
            ].to_string(index=False)
        )

        print()
        print("--- SUSPICIOUS SEASONS ---")

        suspicious = calendar[
            "suspicious_seasons"
        ]

        if suspicious.empty:
            print("No suspicious seasons detected.")
        else:
            print(
                suspicious.to_string(
                    index=False
                )
            )

        print()
        print("--- COMPETITION BOUNDS FOR SUSPICIOUS SEASONS ---")

        suspicious_season_ids = set(
            suspicious["season"].tolist()
        )

        competition_bounds = calendar[
            "competition_bounds"
        ]

        suspicious_competitions = (
            competition_bounds[
                competition_bounds["season"].isin(
                    suspicious_season_ids
                )
            ]
            .sort_values(
                [
                    "season",
                    "first_match",
                ]
            )
        )

        if suspicious_competitions.empty:
            print(
                "No competition-level anomalies "
                "available for suspicious seasons."
            )
        else:
            print(
                suspicious_competitions.to_string(
                    index=False
                )
            )

        print()
        print("--- EARLIEST RECORDS ---")

        print(
            calendar[
                "earliest_records"
            ].to_string(index=False)
        )

        print()
        print("--- LATEST RECORDS ---")

        print(
            calendar[
                "latest_records"
            ].to_string(index=False)
        )

        print()
        print(
            "--- EXPECTED CALENDAR ENVELOPE VIOLATIONS ---"
        )

        violations = calendar[
            "expected_envelope_violations"
        ]

        print(
            f"Rows outside expected envelope: "
            f"{len(violations)}"
        )

        if not violations.empty:
            print(
                violations.head(100).to_string(
                    index=False
                )
            )

            if len(violations) > 100:
                print()
                print(
                    f"... {len(violations) - 100} "
                    "additional rows not displayed."
                )


# ================================================================
# MAIN
# ================================================================

def main() -> None:

    config = AuditConfig(
        performance_path=Path(
            "data/performances/"
            "player_competition_season_performance.csv"
        ),
        database_path=Path(
            "data/historical/"
            "transfermarkt-datasets.duckdb"
        ),
        minimum_minutes=900,
        expected_seasons=14,
        national_team_competition=(
            "national_team_competition"
        ),
        suspicious_duration_days=450,
        expected_season_start_month=6,
        expected_season_start_day=1,
        expected_season_end_month=7,
        expected_season_end_day=31,
    )

    audit = RealPerformanceAudit(config)

    report = audit.run()

    print()
    print("=" * 80)
    print("REAL PERFORMANCE DATASET AUDIT")
    print("=" * 80)

    # ------------------------------------------------------------
    # GLOBAL
    # ------------------------------------------------------------

    print()
    print("--- GLOBAL ---")

    for key, value in report["global"].items():
        print(f"{key}: {value}")

    # ------------------------------------------------------------
    # PLAYERS
    # ------------------------------------------------------------

    print()
    print("--- PLAYERS ---")

    for key, value in report["players"].items():
        print(f"{key}: {value}")

    # ------------------------------------------------------------
    # MINUTES
    # ------------------------------------------------------------

    print()
    print("--- MINUTES ---")

    for key, value in report["minutes"].items():
        print(f"{key}: {value}")

    # ------------------------------------------------------------
    # DUPLICATES
    # ------------------------------------------------------------

    print()
    print("--- DUPLICATES ---")

    for key, value in report["duplicates"].items():
        print(f"{key}: {value}")

    # ------------------------------------------------------------
    # DATES
    # ------------------------------------------------------------

    print()
    print("--- DATES ---")

    for key, value in report["dates"].items():
        print(f"{key}: {value}")

    # ------------------------------------------------------------
    # COMPETITIONS
    # ------------------------------------------------------------

    print()
    print("--- COMPETITIONS ---")

    for key, value in report["competitions"].items():
        print(f"{key}: {value}")

    # ------------------------------------------------------------
    # XG / XA
    # ------------------------------------------------------------

    print()
    print("--- XG / XA ---")

    for key, value in report["xg_xa"].items():
        print(f"{key}: {value}")

    # ------------------------------------------------------------
    # TRANSFER COVERAGE
    # ------------------------------------------------------------

    print()
    print("--- TRANSFER COVERAGE ---")

    for key, value in report[
        "transfer_coverage"
    ].items():
        print(f"{key}: {value}")

    # ------------------------------------------------------------
    # SEASON COVERAGE
    # ------------------------------------------------------------

    print()
    print("--- SEASON COVERAGE ---")

    print(
        report[
            "season_coverage"
        ].to_string(index=False)
    )

    # ------------------------------------------------------------
    # SEASON CALENDAR ANALYSIS
    # ------------------------------------------------------------

    audit.print_season_calendar_anomalies(
        report
    )


if __name__ == "__main__":
    main()