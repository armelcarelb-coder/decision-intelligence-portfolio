from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import unicodedata

from .match_mapping import (
    build_match_mapping,
    build_player_mapping,
)
from .understat_xg_xa import (
    UnderstatXgXaSource,
)


@dataclass(frozen=True)
class XgXaEnricherConfig:

    db_path: str = (
        "data/historical/transfermarkt-datasets.duckdb"
    )

    season_bounds_path: str = (
        "data/audits/season_calendar_bounds_final.csv"
    )

    performance_input_path: str = (
        "data/performances/"
        "player_competition_season_performance.csv"
    )

    game_player_output_path: str = (
        "data/enrichment/xg_xa_game_player.csv"
    )

    aggregated_output_path: str = (
        "data/enrichment/"
        "player_competition_season_performance_xgxa.csv"
    )

    audit_dir: str = (
        "data/audits"
    )

    understat_cache_dir: str = (
        "data/enrichment/understat_cache"
    )

    request_pause_seconds: float = 0.25

    understat_batch_size: int = 50


class XgXaEnricher:
    @staticmethod
    def _normalize_country_name(
        value: object,
    ) -> str:

        if value is None:
            return ""

        if pd.isna(value):
            return ""

        text = str(value).strip().lower()

        text = unicodedata.normalize(
            "NFKD",
            text,
        )

        text = "".join(
            char
            for char in text
            if not unicodedata.combining(char)
        )

        return (
            text
            .replace("&", "and")
            .strip()
        )


    @classmethod
    def _country_to_understat_league(
        cls,
        value: object,
    ) -> str | None:

        normalized = cls._normalize_country_name(
            value
        )

        mapping = {
            "england": "ENG-Premier League",
            "england, uk": "ENG-Premier League",
            "spain": "ESP-La Liga",
            "italy": "ITA-Serie A",
            "germany": "GER-Bundesliga",
            "france": "FRA-Ligue 1",
        }

        return mapping.get(
            normalized
        )
    
    SUPPORTED_COUNTRIES = {
        "england",
        "spain",
        "italy",
        "germany",
        "france",
    }

    def __init__(
        self,
        config: XgXaEnricherConfig | None = None,
    ) -> None:

        self.config = (
            config
            or XgXaEnricherConfig()
        )

        self.db_path = Path(
            self.config.db_path
        )

        self.performance_input_path = Path(
            self.config.performance_input_path
        )

        self.game_player_output_path = Path(
            self.config.game_player_output_path
        )

        self.aggregated_output_path = Path(
            self.config.aggregated_output_path
        )

        self.audit_dir = Path(
            self.config.audit_dir
        )

        self.audit_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.source = (
            UnderstatXgXaSource(
                cache_dir=(
                    self.config.understat_cache_dir
                ),
                request_pause_seconds=(
                    self.config.request_pause_seconds
                ),
                batch_size=(
                    self.config.understat_batch_size
                ),
            )
        )

    # ======================================================================
    # PUBLIC
    # ======================================================================

    def run(
        self,
        seasons: list[int] | None = None,
        countries: list[str] | None = None,
    ) -> dict:

        self._validate_paths()

        bounds = self._load_season_bounds()

        tm_player_games = (
            self._load_transfermarkt_targets(
                bounds=bounds,
                seasons=seasons,
                countries=countries,
            )
        )

        if tm_player_games.empty:

            raise RuntimeError(
                "Aucun match joueur Transfermarkt "
                "dans le périmètre demandé."
            )

        tm_matches = (
            tm_player_games[
                [
                    "game_id",
                    "match_date",
                    "season",
                    "competition_id",
                    "competition_name",
                    "country_name",
                    "home_team",
                    "away_team",
                    "home_goals",
                    "away_goals",
                    "understat_league",
                ]
            ]
            .drop_duplicates()
            .copy()
        )

        # ------------------------------------------------------------------
        # UNDERSTAT SCHEDULE
        # ------------------------------------------------------------------

        understat_schedules = []

        groups = (
            tm_matches[
                [
                    "understat_league",
                    "season",
                ]
            ]
            .drop_duplicates()
        )

        for _, group in groups.iterrows():

            schedule = (
                self.source.load_schedule(
                    league=group[
                        "understat_league"
                    ],
                    season=int(
                        group["season"]
                    ),
                )
            )

            if schedule.empty:
                continue

            schedule["understat_league"] = (
                group[
                    "understat_league"
                ]
            )

            understat_schedules.append(
                schedule
            )

        if understat_schedules:

            understat_schedule = pd.concat(
                understat_schedules,
                ignore_index=True,
            )

        else:

            understat_schedule = (
                pd.DataFrame()
            )

        # ------------------------------------------------------------------
        # MATCH MAPPING
        # ------------------------------------------------------------------

        match_mappings = []

        for (
            league,
            season,
        ), tm_group in tm_matches.groupby(
            [
                "understat_league",
                "season",
            ],
            dropna=False,
        ):

            # --------------------------------------------------------------
            # SOURCE UNDERSTAT NON DISPONIBLE POUR CE GROUPE
            # --------------------------------------------------------------

            if pd.isna(league):

                fallback_rows = []

                for _, tm_row in tm_group.iterrows():

                    fallback_rows.append(
                        {
                            "tm_game_id": tm_row[
                                "game_id"
                            ],
                            "understat_game_id": pd.NA,
                            "tm_match_date": tm_row[
                                "match_date"
                            ],
                            "understat_match_date": pd.NaT,
                            "tm_home_team": tm_row[
                                "home_team"
                            ],
                            "tm_away_team": tm_row[
                                "away_team"
                            ],
                            "understat_home_team": pd.NA,
                            "understat_away_team": pd.NA,
                            "candidate_count": 0,
                            "candidate_ids": "",
                            "mapping_status": (
                                "MATCH_UNMATCHED"
                            ),
                            "mapping_method": (
                                "COUNTRY_NOT_MAPPED"
                            ),
                            "mapping_reason": (
                                "NO_UNDERSTAT_LEAGUE_MAPPING"
                            ),
                            "understat_league": pd.NA,
                            "season": season,
                        }
                    )

                if fallback_rows:

                    match_mappings.append(
                        pd.DataFrame(
                            fallback_rows
                        )
                    )

                continue

            # --------------------------------------------------------------
            # SOURCE UNDERSTAT
            # --------------------------------------------------------------

            us_group = understat_schedule[
                (
                    understat_schedule[
                        "understat_league"
                    ]
                    == league
                )
                &
                (
                    understat_schedule[
                        "season"
                    ]
                    == season
                )
            ].copy()

            if us_group.empty:

                fallback_rows = []

                for _, tm_row in tm_group.iterrows():

                    fallback_rows.append(
                        {
                            "tm_game_id": tm_row[
                                "game_id"
                            ],
                            "understat_game_id": pd.NA,
                            "tm_match_date": tm_row[
                                "match_date"
                            ],
                            "understat_match_date": pd.NaT,
                            "tm_home_team": tm_row[
                                "home_team"
                            ],
                            "tm_away_team": tm_row[
                                "away_team"
                            ],
                            "understat_home_team": pd.NA,
                            "understat_away_team": pd.NA,
                            "candidate_count": 0,
                            "candidate_ids": "",
                            "mapping_status": (
                                "MATCH_UNMATCHED"
                            ),
                            "mapping_method": (
                                "UNDERSTAT_SCHEDULE_UNAVAILABLE"
                            ),
                            "mapping_reason": (
                                "SOURCE_SCHEDULE_UNAVAILABLE"
                            ),
                            "understat_league": league,
                            "season": season,
                        }
                    )

                match_mappings.append(
                    pd.DataFrame(
                        fallback_rows
                    )
                )

                continue

            mapped = build_match_mapping(
                transfermarkt_matches=tm_group,
                understat_schedule=us_group,
            )

            mapped[
                "understat_league"
            ] = league

            mapped[
                "season"
            ] = int(season)

            match_mappings.append(
                mapped
            )

            us_group = understat_schedule[
                (
                    understat_schedule[
                        "understat_league"
                    ]
                    == league
                )
                &
                (
                    understat_schedule[
                        "season"
                    ]
                    == season
                )
            ].copy()

            if us_group.empty:

                for _, tm_row in tm_group.iterrows():

                    match_mappings.append(
                        pd.DataFrame(
                            [
                                {
                                    "tm_game_id": tm_row[
                                        "game_id"
                                    ],
                                    "understat_game_id": pd.NA,
                                    "tm_match_date": tm_row[
                                        "match_date"
                                    ],
                                    "understat_match_date": pd.NaT,
                                    "tm_home_team": tm_row[
                                        "home_team"
                                    ],
                                    "tm_away_team": tm_row[
                                        "away_team"
                                    ],
                                    "understat_home_team": pd.NA,
                                    "understat_away_team": pd.NA,
                                    "candidate_count": 0,
                                    "candidate_ids": "",
                                    "mapping_status": (
                                        "MATCH_UNMATCHED"
                                    ),
                                    "mapping_method": (
                                        "UNDERSTAT_SCHEDULE_UNAVAILABLE"
                                    ),
                                    "mapping_reason": (
                                        "SOURCE_SCHEDULE_UNAVAILABLE"
                                    ),
                                }
                            ]
                        )
                    )

                continue

            mapped = build_match_mapping(
                transfermarkt_matches=tm_group,
                understat_schedule=us_group,
            )

            mapped[
                "understat_league"
            ] = league

            mapped["season"] = season

            match_mappings.append(
                mapped
            )

        if match_mappings:

            match_mapping = pd.concat(
                match_mappings,
                ignore_index=True,
            )

            if match_mappings:

                match_mapping = pd.concat(
                    match_mappings,
                    ignore_index=True,
                )

            else:

                match_mapping = pd.DataFrame(
                    columns=[
                        "tm_game_id",
                        "understat_game_id",
                        "tm_match_date",
                        "understat_match_date",
                        "tm_home_team",
                        "tm_away_team",
                        "understat_home_team",
                        "understat_away_team",
                        "candidate_count",
                        "candidate_ids",
                        "mapping_status",
                        "mapping_method",
                        "mapping_reason",
                        "understat_league",
                        "season",
                    ]
                )

        else:

            match_mapping = pd.DataFrame()

        # ------------------------------------------------------------------
        # UNDERSTAT PLAYER MATCH DATA
        # ------------------------------------------------------------------

        player_source_frames = []

        confirmed = match_mapping[
            match_mapping[
                "mapping_status"
            ]
            == "MATCH_CONFIRMED"
        ].copy()

        for (
            league,
            season,
        ), group in confirmed.groupby(
            [
                "understat_league",
                "season",
            ],
            dropna=False,
        ):

            match_ids = (
                group[
                    "understat_game_id"
                ]
                .dropna()
                .astype(int)
                .unique()
                .tolist()
            )

            if not match_ids:
                continue

            player_stats = (
                self.source.load_player_match_stats(
                    league=league,
                    season=int(season),
                    match_ids=match_ids,
                )
            )

            if not player_stats.empty:

                player_stats[
                    "understat_league"
                ] = league

                player_stats[
                    "season"
                ] = int(season)

                player_source_frames.append(
                    player_stats
                )

        if player_source_frames:

            understat_player_stats = (
                pd.concat(
                    player_source_frames,
                    ignore_index=True,
                )
            )

        else:

            understat_player_stats = (
                pd.DataFrame()
            )

        # ------------------------------------------------------------------
        # PLAYER MAPPING
        # ------------------------------------------------------------------

        game_player = build_player_mapping(
            transfermarkt_player_games=(
                tm_player_games
            ),
            understat_player_stats=(
                understat_player_stats
            ),
            match_mapping=(
                match_mapping
            ),
        )

        if game_player.empty:
            raise RuntimeError(
                "L'enrichissement game × player "
                "est vide."
            )

        # ------------------------------------------------------------------
        # FINAL GAME PLAYER STATUS
        # ------------------------------------------------------------------

        game_player[
            "source_available"
        ] = (
            game_player[
                "player_mapping_status"
            ]
            == "PLAYER_CONFIRMED"
        )

        game_player[
            "source_metric_status"
        ] = np.select(
            [
                (
                    game_player[
                        "source_available"
                    ]
                    &
                    game_player["xg"].notna()
                    &
                    game_player["xa"].notna()
                ),
                (
                    game_player[
                        "source_available"
                    ]
                    &
                    (
                        game_player["xg"].isna()
                        |
                        game_player["xa"].isna()
                    )
                ),
                (
                    game_player[
                        "player_mapping_status"
                    ]
                    == "PLAYER_REVIEW_TEAM_MISMATCH"
                ),
            ],
            [
                "SOURCE_CONFIRMED",
                "SOURCE_PARTIAL_METRICS",
                "PLAYER_MAPPING_REVIEW",
            ],
            default="SOURCE_UNAVAILABLE",
        )

        game_player[
            "validation_status"
        ] = np.select(
            [
                (
                    game_player[
                        "source_metric_status"
                    ]
                    == "SOURCE_CONFIRMED"
                ),
                (
                    game_player[
                        "player_mapping_status"
                    ]
                    .astype(str)
                    .str.startswith(
                        "PLAYER_REVIEW"
                    )
                ),
            ],
            [
                "VALID",
                "REVIEW",
            ],
            default="UNMATCHED",
        )

        game_player[
            "enrichment_version"
        ] = "xg_xa_v1_understat"

        # ------------------------------------------------------------------
        # SAVE GAME PLAYER
        # ------------------------------------------------------------------

        self.game_player_output_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        game_player.to_csv(
            self.game_player_output_path,
            index=False,
            encoding="utf-8",
        )

        # ------------------------------------------------------------------
        # AUDIT MATCH / PLAYER
        # ------------------------------------------------------------------

        match_review_path = (
            self.audit_dir
            / "xg_xa_match_mapping_review.csv"
        )

        player_review_path = (
            self.audit_dir
            / "xg_xa_player_mapping_review.csv"
        )

        match_mapping.to_csv(
            match_review_path,
            index=False,
            encoding="utf-8",
        )

        game_player[
            [
                "game_id",
                "player_id",
                "player",
                "team",
                "understat_game_id",
                "understat_player_id",
                "player_mapping_status",
                "player_mapping_method",
                "xg",
                "xa",
                "validation_status",
            ]
        ].to_csv(
            player_review_path,
            index=False,
            encoding="utf-8",
        )

        # ------------------------------------------------------------------
        # AGGREGATION
        # ------------------------------------------------------------------

        aggregated = (
            self._aggregate_to_player_competition_season(
                game_player
            )
        )

        # ------------------------------------------------------------------
        # MERGE PERFORMANCE DATASET
        # ------------------------------------------------------------------

        enriched_performance = (
            self._merge_with_performance_dataset(
                aggregated
            )
        )

        enriched_performance.to_csv(
            self.aggregated_output_path,
            index=False,
            encoding="utf-8",
        )

        summary = (
            self._build_summary(
                game_player,
                aggregated,
                enriched_performance,
            )
        )

        summary_path = (
            self.audit_dir
            / "xg_xa_enrichment_summary.csv"
        )

        summary.to_csv(
            summary_path,
            index=False,
            encoding="utf-8",
        )

        report_path = (
            self.audit_dir
            / "xg_xa_enrichment_report.txt"
        )

        self._write_report(
            game_player=game_player,
            aggregated=aggregated,
            enriched_performance=(
                enriched_performance
            ),
            report_path=report_path,
        )

        print()
        print(
            "============================================================"
        )
        print(
            "XG/XA ENRICHMENT V1 — TERMINÉ"
        )
        print(
            "============================================================"
        )
        print(
            f"Game/player : "
            f"{self.game_player_output_path}"
        )
        print(
            f"Performance : "
            f"{self.aggregated_output_path}"
        )
        print(
            f"Audit       : "
            f"{self.audit_dir}"
        )

        return {
            "game_player": game_player,
            "aggregated": aggregated,
            "performance": enriched_performance,
            "summary": summary,
        }

    # ======================================================================
    # DATABASE
    # ======================================================================

    def _validate_paths(self) -> None:

        if not self.db_path.exists():
            raise FileNotFoundError(
                f"DuckDB introuvable : {self.db_path}"
            )

        if not self.performance_input_path.exists():
            raise FileNotFoundError(
                "Dataset de performances introuvable : "
                f"{self.performance_input_path}"
            )

    def _connect(
        self,
    ) -> duckdb.DuckDBPyConnection:

        return duckdb.connect(
            str(self.db_path),
            read_only=True,
        )

    # ======================================================================
    # SEASON BOUNDS
    # ======================================================================

    def _load_season_bounds(
        self,
    ) -> pd.DataFrame:

        path = Path(
            self.config.season_bounds_path
        )

        if not path.exists():
            raise FileNotFoundError(
                f"Bornes absentes : {path}"
            )

        df = pd.read_csv(
            path
        )

        required = {
            "season",
            "season_start",
            "season_end",
        }

        missing = (
            required
            - set(df.columns)
        )

        if missing:
            raise ValueError(
                "Colonnes manquantes bornes : "
                + ", ".join(
                    sorted(missing)
                )
            )

        df["season"] = pd.to_numeric(
            df["season"],
            errors="coerce",
        )

        df["season_start"] = pd.to_datetime(
            df["season_start"],
            errors="coerce",
        )

        df["season_end"] = pd.to_datetime(
            df["season_end"],
            errors="coerce",
        )

        if df[
            [
                "season",
                "season_start",
                "season_end",
            ]
        ].isna().any().any():

            raise ValueError(
                "Bornes saisonnières invalides."
            )

        return df

    # ======================================================================
    # TRANSFERMARKT TARGET
    # ======================================================================

    def _load_transfermarkt_targets(
        self,
        bounds: pd.DataFrame,
        seasons: list[int] | None,
        countries: list[str] | None,
    ) -> pd.DataFrame:

        requested_seasons = (
            seasons
            if seasons
            else bounds["season"]
            .astype(int)
            .tolist()
        )

        requested_seasons = sorted(
            set(
                int(value)
                for value in requested_seasons
            )
        )

        requested_countries = (
            countries
            if countries
            else sorted(
                self.SUPPORTED_COUNTRIES
            )
        )

        requested_countries = [
            str(country)
            .strip()
            .lower()
            for country in requested_countries
        ]

        country_sql = ", ".join(
            "'"
            + country.replace("'", "''")
            + "'"
            for country in requested_countries
        )

        season_sql = ", ".join(
            str(season)
            for season in requested_seasons
        )

        query = f"""
        WITH target_matches AS (

            SELECT DISTINCT

                CAST(g.game_id AS BIGINT)
                    AS game_id,

                CAST(g.season AS INTEGER)
                    AS season,

                CAST(g.date AS DATE)
                    AS match_date,

                g.competition_id,

                c.name
                    AS competition_name,

                LOWER(
                    TRIM(
                        c.country_name
                    )
                )
                    AS country_name,

                hc.name
                    AS home_team,

                ac.name
                    AS away_team,

                g.home_club_id,

                g.away_club_id,

                g.home_club_goals
                    AS home_goals,

                g.away_club_goals
                    AS away_goals

            FROM games AS g

            INNER JOIN season_calendar_bounds AS sb

                ON CAST(g.season AS INTEGER)
                    = sb.season

                AND CAST(g.date AS DATE)
                    >= CAST(sb.season_start AS DATE)

                AND CAST(g.date AS DATE)
                    <= CAST(sb.season_end AS DATE)

            INNER JOIN competitions AS c

                ON g.competition_id
                    = c.competition_id

            LEFT JOIN clubs AS hc

                ON g.home_club_id
                    = hc.club_id

            LEFT JOIN clubs AS ac

                ON g.away_club_id
                    = ac.club_id

            WHERE

                CAST(g.season AS INTEGER)
                    IN ({season_sql})

                AND LOWER(
                    TRIM(
                        c.country_name
                    )
                ) IN ({country_sql})

                AND c.type
                    = 'domestic_league'

                AND c.sub_type
                    = 'first_tier'

        )

        SELECT

            tm.game_id,

            tm.season,

            tm.match_date,

            tm.competition_id,

            tm.competition_name,

            tm.country_name,

            tm.home_team,

            tm.away_team,

            tm.home_goals,

            tm.away_goals,

            a.player_id,

            COALESCE(
                p.name,
                a.player_name
            ) AS player,

            p.position,

            a.player_club_id,

            pc.name AS team,

            a.minutes_played,
            a.goals,
            a.assists

        FROM target_matches AS tm

        INNER JOIN appearances AS a

            ON CAST(a.game_id AS BIGINT)
                = tm.game_id

        LEFT JOIN players AS p

            ON a.player_id
                = p.player_id

        LEFT JOIN clubs AS pc

            ON a.player_club_id
                = pc.club_id

        WHERE

            a.player_id IS NOT NULL

        ORDER BY

            tm.season,
            tm.match_date,
            tm.game_id,
            a.player_id
        """

        with self._connect() as con:

            con.register(
                "season_calendar_bounds",
                bounds,
            )

            df = (
                con.execute(
                    query
                )
                .fetchdf()
            )

            con.unregister(
                "season_calendar_bounds"
            )

        if df.empty:
            return df

        df[
            "understat_league"
        ] = df[
            "country_name"
        ].map(
            self._country_to_understat_league
        )

        df[
            "minutes_played"
        ] = pd.to_numeric(
            df[
                "minutes_played"
            ],
            errors="coerce",
        )

        df["match_date"] = pd.to_datetime(
            df["match_date"],
            errors="coerce",
        )

        # Contrôle de grain Transfermarkt.
        duplicated = df.duplicated(
            subset=[
                "game_id",
                "player_id",
            ],
            keep=False,
        )

        if duplicated.any():

            sample = (
                df.loc[
                    duplicated,
                    [
                        "game_id",
                        "player_id",
                    ],
                ]
                .drop_duplicates()
                .head(20)
            )

            raise ValueError(
                "Duplications game_id × player_id "
                "dans la source Transfermarkt.\n"
                f"{sample.to_string(index=False)}"
            )

        return df

    # ======================================================================
    # AGGREGATION
    # ======================================================================

    def _aggregate_to_player_competition_season(
        self,
        game_player: pd.DataFrame,
    ) -> pd.DataFrame:

        df = game_player.copy()

        df["source_confirmed"] = (
            df["source_metric_status"]
            == "SOURCE_CONFIRMED"
        )

        grouped = []

        grouping = [
            "player_id",
            "season",
            "competition_id",
            "competition_name",
        ]

        for key, group in df.groupby(
            grouping,
            dropna=False,
        ):

            player_id, season, competition_id, competition_name = key

            total_games = len(group)

            confirmed_games = int(
                group[
                    "source_confirmed"
                ].sum()
            )

            coverage_rate = (
                confirmed_games
                / total_games
                if total_games
                else np.nan
            )

            source_complete = (
                confirmed_games
                == total_games
                and
                group[
                    "xg"
                ].notna().all()
                and
                group[
                    "xa"
                ].notna().all()
            )

            tm_minutes = pd.to_numeric(
                group[
                    "minutes_played"
                ],
                errors="coerce",
            ).sum(
                min_count=1
            )

            if source_complete:

                xg = pd.to_numeric(
                    group["xg"],
                    errors="coerce",
                ).sum(
                    min_count=1
                )

                xa = pd.to_numeric(
                    group["xa"],
                    errors="coerce",
                ).sum(
                    min_count=1
                )

                status = (
                    "COMPLETE_SOURCE_COVERAGE"
                )

            else:

                xg = np.nan
                xa = np.nan

                status = (
                    "PARTIAL_SOURCE_COVERAGE"
                )

            grouped.append(
                {
                    "player_id": player_id,
                    "season": season,
                    "competition_id": competition_id,
                    "competition_name": competition_name,
                    "game_player_rows": total_games,
                    "source_confirmed_rows": confirmed_games,
                    "xg_xa_coverage_rate": coverage_rate,
                    "source_minutes": tm_minutes,
                    "xg": xg,
                    "xa": xa,
                    "xg_xa_enrichment_status": status,
                    "xg_xa_source": "Understat",
                    "xg_xa_source_library": "soccerdata",
                    "xg_xa_source_version": (
                        self.source.source_version
                    ),
                }
            )

        return pd.DataFrame(
            grouped
        )

    # ======================================================================
    # MERGE PERFORMANCE DATASET
    # ======================================================================

    def _merge_with_performance_dataset(
        self,
        aggregated: pd.DataFrame,
    ) -> pd.DataFrame:

        performance = pd.read_csv(
            self.performance_input_path
        )

        required = {
            "player_id",
            "season",
            "competition_id",
            "minutes",
        }

        missing = (
            required
            - set(performance.columns)
        )

        if missing:
            raise ValueError(
                "Colonnes manquantes performance dataset : "
                + ", ".join(sorted(missing))
            )

        performance["player_id"] = pd.to_numeric(
            performance["player_id"],
            errors="coerce",
        )

        performance["season"] = pd.to_numeric(
            performance["season"],
            errors="coerce",
        )

        performance["minutes"] = pd.to_numeric(
            performance["minutes"],
            errors="coerce",
        )

        aggregated["player_id"] = pd.to_numeric(
            aggregated["player_id"],
            errors="coerce",
        )

        aggregated["season"] = pd.to_numeric(
            aggregated["season"],
            errors="coerce",
        )

        result = performance.merge(
            aggregated,
            on=[
                "player_id",
                "season",
                "competition_id",
            ],
            how="left",
            suffixes=(
                "",
                "_xgxa",
            ),
        )

        # ------------------------------------------------------------------
        # OUT OF SCOPE
        # ------------------------------------------------------------------

        result[
            "xg_xa_enrichment_status"
        ] = result[
            "xg_xa_enrichment_status"
        ].fillna(
            "OUT_OF_SCOPE"
        )

        result[
            "xg_xa_source"
        ] = result[
            "xg_xa_source"
        ].fillna(
            pd.NA
        )

        result[
            "xg_xa_source_library"
        ] = result[
            "xg_xa_source_library"
        ].fillna(
            pd.NA
        )

        result[
            "xg_xa_source_version"
        ] = result[
            "xg_xa_source_version"
        ].fillna(
            pd.NA
        )

        # ------------------------------------------------------------------
        # MINUTES CONSISTENCY
        # ------------------------------------------------------------------

        result[
            "minutes_consistent_with_game_level"
        ] = np.isclose(
            result["minutes"].fillna(0),
            result[
                "source_minutes"
            ].fillna(0),
            atol=0.001,
        )

        # ------------------------------------------------------------------
        # CALCUL xG/xA PER90
        # ------------------------------------------------------------------

        complete = (
            result[
                "xg_xa_enrichment_status"
            ]
            == "COMPLETE_SOURCE_COVERAGE"
        )

        valid_minutes = (
            result["minutes"]
            > 0
        )

        valid_for_rates = (
            complete
            & valid_minutes
            & result[
                "minutes_consistent_with_game_level"
            ]
            & result["xg"].notna()
            & result["xa"].notna()
        )

        result["xg"] = (
            result["xg"]
            .where(
                valid_for_rates
            )
        )

        result["xa"] = (
            result["xa"]
            .where(
                valid_for_rates
            )
        )

        result["xg_per90"] = (
            result["xg"]
            .div(
                result["minutes"]
            )
            .mul(90)
            .where(
                valid_for_rates
            )
        )

        result["xa_per90"] = (
            result["xa"]
            .div(
                result["minutes"]
            )
            .mul(90)
            .where(
                valid_for_rates
            )
        )

        result["xg_xa_enrichment_status"] = np.select(
            [
                result[
                    "xg_xa_enrichment_status"
                ].eq(
                    "COMPLETE_SOURCE_COVERAGE"
                )
                &
                ~result[
                    "minutes_consistent_with_game_level"
                ],
                result[
                    "xg_xa_enrichment_status"
                ].eq(
                    "COMPLETE_SOURCE_COVERAGE"
                ),
                result[
                    "xg_xa_enrichment_status"
                ].eq(
                    "PARTIAL_SOURCE_COVERAGE"
                ),
            ],
            [
                "MINUTES_MISMATCH_REVIEW",
                "COMPLETE",
                "PARTIAL",
            ],
            default="OUT_OF_SCOPE",
        )

        return result

    # ======================================================================
    # SUMMARY
    # ======================================================================

    def _build_summary(
        self,
        game_player: pd.DataFrame,
        aggregated: pd.DataFrame,
        performance: pd.DataFrame,
    ) -> pd.DataFrame:

        rows = []

        rows.append(
            {
                "metric": "game_player_rows",
                "value": len(game_player),
            }
        )

        rows.append(
            {
                "metric": "unique_game_player",
                "value": game_player[
                    [
                        "game_id",
                        "player_id",
                    ]
                ]
                .drop_duplicates()
                .shape[0],
            }
        )

        rows.append(
            {
                "metric": "match_confirmed",
                "value": int(
                    (
                        game_player[
                            "mapping_status"
                        ]
                        == "MATCH_CONFIRMED"
                    ).sum()
                ),
            }
        )

        rows.append(
            {
                "metric": "match_review",
                "value": int(
                    (
                        game_player[
                            "mapping_status"
                        ]
                        == "MATCH_REVIEW"
                    ).sum()
                ),
            }
        )

        rows.append(
            {
                "metric": "match_unmatched",
                "value": int(
                    (
                        game_player[
                            "mapping_status"
                        ]
                        == "MATCH_UNMATCHED"
                    ).sum()
                ),
            }
        )

        rows.append(
            {
                "metric": "player_confirmed",
                "value": int(
                    (
                        game_player[
                            "player_mapping_status"
                        ]
                        == "PLAYER_CONFIRMED"
                    ).sum()
                ),
            }
        )

        rows.append(
            {
                "metric": "xg_non_null",
                "value": int(
                    game_player["xg"]
                    .notna()
                    .sum()
                ),
            }
        )

        rows.append(
            {
                "metric": "xa_non_null",
                "value": int(
                    game_player["xa"]
                    .notna()
                    .sum()
                ),
            }
        )

        rows.append(
            {
                "metric": "complete_aggregated_groups",
                "value": int(
                    (
                        aggregated[
                            "xg_xa_enrichment_status"
                        ]
                        == "COMPLETE_SOURCE_COVERAGE"
                    ).sum()
                ),
            }
        )

        rows.append(
            {
                "metric": "performance_complete_rows",
                "value": int(
                    (
                        performance[
                            "xg_xa_enrichment_status"
                        ]
                        == "COMPLETE"
                    ).sum()
                ),
            }
        )

        rows.append(
            {
                "metric": "performance_xg_non_null",
                "value": int(
                    performance["xg"]
                    .notna()
                    .sum()
                ),
            }
        )

        rows.append(
            {
                "metric": "performance_xa_non_null",
                "value": int(
                    performance["xa"]
                    .notna()
                    .sum()
                ),
            }
        )

        return pd.DataFrame(
            rows
        )

    # ======================================================================
    # REPORT
    # ======================================================================

    def _write_report(
        self,
        game_player: pd.DataFrame,
        aggregated: pd.DataFrame,
        enriched_performance: pd.DataFrame,
        report_path: Path,
    ) -> None:

        match_counts = (
            game_player[
                "mapping_status"
            ]
            .value_counts(
                dropna=False
            )
            .to_string()
        )

        player_counts = (
            game_player[
                "player_mapping_status"
            ]
            .value_counts(
                dropna=False
            )
            .to_string()
        )

        enrichment_counts = (
            enriched_performance[
                "xg_xa_enrichment_status"
            ]
            .value_counts(
                dropna=False
            )
            .to_string()
        )

        report = f"""
XG/XA ENRICHMENT V1 — REPORT

SOURCE
------
Name       : Understat
Library    : soccerdata
Version    : {self.source.source_version}

METHODOLOGY
-----------
Grain source           : game_id × player_id
XG reconstruction      : NO
XA reconstruction      : NO
Missing source data    : NULL
Partial aggregation    : NOT USED FOR SCORING
Only confirmed maps    : YES

GAME/PLAYER DATA
----------------
Rows                     : {len(game_player):,}
Unique game/player       : {game_player[['game_id', 'player_id']].drop_duplicates().shape[0]:,}
xG non-null              : {game_player['xg'].notna().sum():,}
xA non-null              : {game_player['xa'].notna().sum():,}

MATCH MAPPING
-------------
{match_counts}

PLAYER MAPPING
--------------
{player_counts}

AGGREGATION
-----------
Groups                   : {len(aggregated):,}
Complete source groups   : {(aggregated['xg_xa_enrichment_status'] == 'COMPLETE_SOURCE_COVERAGE').sum():,}
Partial source groups    : {(aggregated['xg_xa_enrichment_status'] == 'PARTIAL_SOURCE_COVERAGE').sum():,}

PERFORMANCE DATASET
-------------------
Rows                     : {len(enriched_performance):,}
COMPLETE                 : {(enriched_performance['xg_xa_enrichment_status'] == 'COMPLETE').sum():,}
PARTIAL                 : {(enriched_performance['xg_xa_enrichment_status'] == 'PARTIAL').sum():,}
OUT_OF_SCOPE            : {(enriched_performance['xg_xa_enrichment_status'] == 'OUT_OF_SCOPE').sum():,}
MINUTES_MISMATCH_REVIEW : {(enriched_performance['xg_xa_enrichment_status'] == 'MINUTES_MISMATCH_REVIEW').sum():,}

PERFORMANCE xG/xA
-----------------
xG non-null             : {enriched_performance['xg'].notna().sum():,}
xA non-null             : {enriched_performance['xa'].notna().sum():,}
xG/90 non-null          : {enriched_performance['xg_per90'].notna().sum():,}
xA/90 non-null          : {enriched_performance['xa_per90'].notna().sum():,}

IMPORTANT
---------
Les groupes incomplets ne reçoivent pas de xG/xA agrégé.
Aucun NULL n'est transformé en zéro.
Aucune métrique n'est reconstruite à partir des buts/passes.
Le PerformanceScorer n'est pas modifié par cette étape.
"""

        report_path.write_text(
            report.strip()
            + "\n",
            encoding="utf-8",
        )


def parse_args():

    parser = argparse.ArgumentParser(
        description=(
            "Enrichissement xG/xA V1 "
            "Transfermarkt -> Understat"
        )
    )

    parser.add_argument(
        "--db-path",
        default=(
            "data/historical/"
            "transfermarkt-datasets.duckdb"
        ),
    )

    parser.add_argument(
        "--season-bounds-path",
        default=(
            "data/audits/"
            "season_calendar_bounds_final.csv"
        ),
    )

    parser.add_argument(
        "--seasons",
        nargs="*",
        type=int,
        default=None,
        help=(
            "Ex: --seasons 2024 2025. "
            "Par défaut toutes les saisons."
        ),
    )

    parser.add_argument(
        "--countries",
        nargs="*",
        default=None,
        help=(
            "Ex: --countries england france"
        ),
    )

    parser.add_argument(
        "--request-pause-seconds",
        type=float,
        default=0.25,
    )

    parser.add_argument(
        "--batch-size",
        type=int,
        default=50,
    )

    return parser.parse_args()


def main():

    args = parse_args()

    config = XgXaEnricherConfig(
        db_path=args.db_path,
        season_bounds_path=(
            args.season_bounds_path
        ),
        request_pause_seconds=(
            args.request_pause_seconds
        ),
        understat_batch_size=(
            args.batch_size
        ),
    )

    enricher = XgXaEnricher(
        config=config
    )

    enricher.run(
        seasons=args.seasons,
        countries=args.countries,
    )


if __name__ == "__main__":
    main()