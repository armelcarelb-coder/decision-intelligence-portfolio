from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import duckdb
import pandas as pd


@dataclass(frozen=True)
class RealPerformanceLoaderConfig:
    """
    Configuration du chargement des performances réelles depuis Transfermarkt DuckDB.
    """

    db_path: str = "data/transfermarkt-datasets.duckdb"

    output_path: str = (
        "data/performances/player_competition_season_performance.csv"
    )

    min_minutes: int = 0

    # Les compétitions de sélections nationales sont exclues.
    exclude_national_team: bool = True


class RealPerformanceLoader:
    """
    Charge et agrège les performances historiques réelles depuis la base
    Transfermarkt DuckDB.

    Architecture :

        appearances
              │
              ├── games
              │
              ├── competitions
              │
              └── players
                    │
                    ▼
        filtrage compétitions club
                    │
                    ▼
        classification competition_level
                    │
                    ▼
        agrégation joueur / saison / compétition
                    │
                    ▼
        player_competition_season_performance.csv

    La majorité du traitement est réalisée directement dans DuckDB afin
    d'éviter une boucle Python sur ~1,9 million d'apparitions.
    """

    UNKNOWN_COMPETITION_LEVEL = "UNKNOWN"

    def __init__(
        self,
        config: Optional[RealPerformanceLoaderConfig] = None,
    ) -> None:
        self.config = config or RealPerformanceLoaderConfig()

        self.db_path = Path(self.config.db_path)
        self.output_path = Path(self.config.output_path)

        self._validate_configuration()

    # ------------------------------------------------------------------
    # PUBLIC API
    # ------------------------------------------------------------------

    def load(self) -> pd.DataFrame:
        """
        Exécute le pipeline complet et retourne le dataset agrégé.
        """

        print("[RealPerformanceLoader] Chargement des performances réelles...")

        self._validate_database()

        query = self._build_query()

        with self._connect() as con:
            df = con.execute(query).fetchdf()

        if df.empty:
            print(
                "[RealPerformanceLoader] Aucun enregistrement de performance trouvé."
            )
            return df

        df = self._post_process(df)

        print(
            "[RealPerformanceLoader] "
            f"{len(df):,} lignes agrégées."
        )

        return df

    def save(self, df: pd.DataFrame) -> None:
        """
        Sauvegarde le dataset agrégé au format CSV.
        """

        if df.empty:
            raise ValueError(
                "Impossible de sauvegarder un dataset de performances vide."
            )

        self.output_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        df.to_csv(
            self.output_path,
            index=False,
            encoding="utf-8",
        )

        print(
            "[RealPerformanceLoader] "
            f"Dataset sauvegardé : {self.output_path}"
        )

    def run(self) -> pd.DataFrame:
        """
        Exécute le chargement puis sauvegarde le résultat.
        """

        df = self.load()

        if not df.empty:
            self.save(df)

        return df

    # ------------------------------------------------------------------
    # DATABASE
    # ------------------------------------------------------------------

    def _connect(self) -> duckdb.DuckDBPyConnection:
        """
        Ouvre une connexion DuckDB en lecture seule.
        """

        return duckdb.connect(
            str(self.db_path),
            read_only=True,
        )

    def _validate_database(self) -> None:
        """
        Vérifie que la base et les tables nécessaires existent.
        """

        if not self.db_path.exists():
            raise FileNotFoundError(
                f"Base DuckDB introuvable : {self.db_path}"
            )

        required_tables = {
            "appearances",
            "games",
            "competitions",
            "players",
        }

        with self._connect() as con:
            tables = {
                row[0]
                for row in con.execute("SHOW TABLES").fetchall()
            }

        missing = required_tables - tables

        if missing:
            raise RuntimeError(
                "Tables manquantes dans la base DuckDB : "
                + ", ".join(sorted(missing))
            )

    # ------------------------------------------------------------------
    # SQL
    # ------------------------------------------------------------------

    def _build_query(self) -> str:
        """
        Construit la requête DuckDB.

        Toute l'agrégation lourde est réalisée côté DuckDB.

        La granularité finale est :

            player_id
            + season
            + competition_id
            + competition_level

        Les noms, positions et informations de compétition sont ensuite
        conservés pour permettre le calcul des percentiles dans
        PerformanceScorer.
        """

        national_team_filter = ""

        if self.config.exclude_national_team:
            national_team_filter = """
                AND COALESCE(g.competition_type, '') !=
                    'national_team_competition'
            """

        min_minutes_filter = ""

        if self.config.min_minutes > 0:
            min_minutes_filter = f"""
                HAVING SUM(COALESCE(a.minutes_played, 0))
                    >= {int(self.config.min_minutes)}
            """

        query = f"""
        WITH base AS (

            SELECT
                a.player_id,

                p.name AS player,

                p.position,
                p.sub_position,

                CAST(g.season AS VARCHAR) AS season,

                g.date AS match_date,

                a.game_id,

                a.minutes_played,
                a.goals,
                a.assists,

                a.competition_id,

                c.name AS competition_name,
                c.sub_type AS competition_sub_type,
                c.type AS competition_type,
                c.country_name,
                c.confederation,

                CASE

                    /*
                     * Champions League
                     */
                    WHEN c.sub_type = 'uefa_champions_league'
                        THEN 'CHAMPIONS_LEAGUE'

                    /*
                     * Europa League
                     */
                    WHEN c.sub_type = 'uefa_europa_league'
                        THEN 'EUROPA_LEAGUE'

                    /*
                     * Conference League
                     */
                    WHEN c.sub_type = 'uefa_conference_league'
                        THEN 'CONFERENCE_LEAGUE'

                    /*
                     * UEFA qualifications
                     */
                    WHEN c.sub_type IN (
                        'uefa_champions_league_qualifying',
                        'uefa_europa_league_qualifying',
                        'uefa_conference_league_qualifying'
                    )
                        THEN 'EUROPE_QUALIFIER'

                    /*
                     * Domestic first tier
                     */
                    WHEN c.type = 'domestic_league'
                         AND c.sub_type = 'first_tier'
                        THEN 'TOP_LEAGUE'

                    /*
                     * Domestic cups
                     */
                    WHEN c.type = 'domestic_cup'
                        THEN 'DOMESTIC_CUP'

                    /*
                     * Domestic super cups
                     */
                    WHEN c.sub_type = 'domestic_super_cup'
                        THEN 'DOMESTIC_SUPER_CUP'

                    /*
                     * Playoffs
                     */
                    WHEN c.sub_type = 'play_off'
                        THEN 'PLAY_OFF'

                    /*
                     * Unknown metadata
                     */
                    ELSE '{self.UNKNOWN_COMPETITION_LEVEL}'

                END AS competition_level

            FROM appearances AS a

            INNER JOIN games AS g
                ON CAST(a.game_id AS VARCHAR) =
                   CAST(g.game_id AS VARCHAR)

            LEFT JOIN competitions AS c
                ON a.competition_id = c.competition_id

            LEFT JOIN players AS p
                ON a.player_id = p.player_id

            WHERE a.player_id IS NOT NULL
              AND g.season IS NOT NULL
              AND g.date IS NOT NULL
              {national_team_filter}
        ),

        aggregated AS (

            SELECT

                player_id,

                MAX(player) AS player,

                MAX(position) AS position,
                MAX(sub_position) AS sub_position,

                season,

                competition_id,

                MAX(competition_name) AS competition_name,
                MAX(competition_sub_type) AS competition_sub_type,
                MAX(competition_type) AS competition_type,
                MAX(country_name) AS country_name,
                MAX(confederation) AS confederation,

                MAX(competition_level) AS competition_level,

                MIN(match_date) AS first_match_date,
                MAX(match_date) AS last_match_date,

                COUNT(DISTINCT game_id) AS appearances,

                SUM(
                    COALESCE(minutes_played, 0)
                ) AS minutes,

                SUM(
                    COALESCE(goals, 0)
                ) AS goals,

                SUM(
                    COALESCE(assists, 0)
                ) AS assists

            FROM base

            GROUP BY
                player_id,
                season,
                competition_id

            {min_minutes_filter}
        )

        SELECT

            player_id,
            player,

            position,
            sub_position,

            season,

            competition_id,
            competition_name,
            competition_sub_type,
            competition_type,
            country_name,
            confederation,
            competition_level,

            first_match_date,
            last_match_date,

            appearances,
            minutes,
            goals,
            assists,

            /*
             * Performance rates.
             *
             * 90 minutes is the denominator used throughout
             * the performance pipeline.
             */
            CASE
                WHEN minutes > 0
                    THEN goals * 90.0 / minutes
                ELSE NULL
            END AS goals_per90,

            CASE
                WHEN minutes > 0
                    THEN assists * 90.0 / minutes
                ELSE NULL
            END AS assists_per90,

            /*
             * xG / xA are deliberately NULL.
             *
             * Transfermarkt does not provide expected-goal or
             * expected-assist data.
             *
             * They will be populated by the future enrichment
             * stage before PerformanceScorer is executed.
             */
            CAST(NULL AS DOUBLE) AS xg,

            CAST(NULL AS DOUBLE) AS xa,

            CAST(NULL AS DOUBLE) AS xg_per90,

            CAST(NULL AS DOUBLE) AS xa_per90

        FROM aggregated

        ORDER BY
            player_id,
            season,
            competition_level,
            competition_id
        """

        return query

    # ------------------------------------------------------------------
    # POST PROCESSING
    # ------------------------------------------------------------------

    def _post_process(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Nettoyage léger côté pandas.

        Aucun calcul lourd n'est effectué ici.
        """

        result = df.copy()

        # --------------------------------------------------------------
        # Types
        # --------------------------------------------------------------

        if "player_id" in result.columns:
            result["player_id"] = pd.to_numeric(
                result["player_id"],
                errors="coerce",
            ).astype("Int64")

        for column in [
            "appearances",
            "minutes",
            "goals",
            "assists",
        ]:
            if column in result.columns:
                result[column] = pd.to_numeric(
                    result[column],
                    errors="coerce",
                )

        for column in [
            "goals_per90",
            "assists_per90",
            "xg",
            "xa",
            "xg_per90",
            "xa_per90",
        ]:
            if column in result.columns:
                result[column] = pd.to_numeric(
                    result[column],
                    errors="coerce",
                )

        # --------------------------------------------------------------
        # Dates
        # --------------------------------------------------------------

        for column in [
            "first_match_date",
            "last_match_date",
        ]:
            if column in result.columns:
                result[column] = pd.to_datetime(
                    result[column],
                    errors="coerce",
                )

        # --------------------------------------------------------------
        # Missing competition metadata
        # --------------------------------------------------------------

        result["competition_level"] = (
            result["competition_level"]
            .fillna(self.UNKNOWN_COMPETITION_LEVEL)
            .astype(str)
        )

        result["competition_level"] = result[
            "competition_level"
        ].replace(
            {
                "": self.UNKNOWN_COMPETITION_LEVEL,
                "None": self.UNKNOWN_COMPETITION_LEVEL,
                "nan": self.UNKNOWN_COMPETITION_LEVEL,
            }
        )

        # --------------------------------------------------------------
        # Explicit season bounds
        # --------------------------------------------------------------

        season_bounds = self._build_season_bounds(result)

        result = result.merge(
            season_bounds,
            on="season",
            how="left",
            validate="many_to_one",
        )

        # --------------------------------------------------------------
        # Column ordering
        # --------------------------------------------------------------

        ordered_columns = [
            "player_id",
            "player",
            "position",
            "sub_position",
            "season",
            "season_start",
            "season_end",
            "competition_id",
            "competition_name",
            "competition_sub_type",
            "competition_type",
            "country_name",
            "confederation",
            "competition_level",
            "first_match_date",
            "last_match_date",
            "appearances",
            "minutes",
            "goals",
            "assists",
            "goals_per90",
            "assists_per90",
            "xg",
            "xa",
            "xg_per90",
            "xa_per90",
        ]

        existing_columns = [
            column
            for column in ordered_columns
            if column in result.columns
        ]

        result = result[existing_columns]

        return result

    # ------------------------------------------------------------------
    # SEASON CALENDAR
    # ------------------------------------------------------------------

    def _build_season_bounds(
        self,
        df: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Construit les bornes de saison.

        Important :
        les dates de saison ne doivent pas être calculées à partir
        de toutes les compétitions du joueur.

        On privilégie les matchs de TOP_LEAGUE afin d'éviter que les
        compétitions internationales ou les qualifications UEFA
        étendent artificiellement la saison.

        Pour une saison ne disposant pas de TOP_LEAGUE dans le dataset,
        on utilise ensuite les dates observées comme fallback.

        Les bornes sont donc déterministes et conservées dans le
        dataset final.
        """

        work = df[
            [
                "season",
                "competition_level",
                "first_match_date",
                "last_match_date",
            ]
        ].copy()

        work["first_match_date"] = pd.to_datetime(
            work["first_match_date"],
            errors="coerce",
        )

        work["last_match_date"] = pd.to_datetime(
            work["last_match_date"],
            errors="coerce",
        )

        # --------------------------------------------------------------
        # Priorité 1 : TOP_LEAGUE
        # --------------------------------------------------------------

        top_league = work[
            work["competition_level"] == "TOP_LEAGUE"
        ].copy()

        top_bounds = (
            top_league
            .groupby("season", as_index=False)
            .agg(
                season_start=(
                    "first_match_date",
                    "min",
                ),
                season_end=(
                    "last_match_date",
                    "max",
                ),
            )
        )

        # --------------------------------------------------------------
        # Fallback : toutes les compétitions club
        # --------------------------------------------------------------

        fallback_bounds = (
            work
            .groupby("season", as_index=False)
            .agg(
                fallback_start=(
                    "first_match_date",
                    "min",
                ),
                fallback_end=(
                    "last_match_date",
                    "max",
                ),
            )
        )

        bounds = fallback_bounds.merge(
            top_bounds,
            on="season",
            how="left",
        )

        bounds["season_start"] = bounds[
            "season_start"
        ].fillna(
            bounds["fallback_start"]
        )

        bounds["season_end"] = bounds[
            "season_end"
        ].fillna(
            bounds["fallback_end"]
        )

        bounds = bounds[
            [
                "season",
                "season_start",
                "season_end",
            ]
        ]

        return bounds

    # ------------------------------------------------------------------
    # VALIDATION
    # ------------------------------------------------------------------

    def validate_output(
        self,
        df: pd.DataFrame,
    ) -> dict:
        """
        Effectue les contrôles principaux sur le dataset généré.
        """

        if df.empty:
            raise ValueError(
                "Le dataset de performances est vide."
            )

        required_columns = [
            "player_id",
            "player",
            "position",
            "season",
            "season_start",
            "season_end",
            "competition_level",
            "minutes",
            "goals",
            "assists",
            "goals_per90",
            "assists_per90",
            "xg",
            "xa",
            "xg_per90",
            "xa_per90",
        ]

        missing = [
            column
            for column in required_columns
            if column not in df.columns
        ]

        if missing:
            raise ValueError(
                "Colonnes obligatoires absentes : "
                + ", ".join(missing)
            )

        # IDs joueurs valides
        invalid_player_ids = int(
            df["player_id"].isna().sum()
        )

        # Minutes négatives
        negative_minutes = int(
            (df["minutes"] < 0).sum()
        )

        # Goals négatifs
        negative_goals = int(
            (df["goals"] < 0).sum()
        )

        # Assists négatives
        negative_assists = int(
            (df["assists"] < 0).sum()
        )

        # Per90 incohérents
        invalid_goals_per90 = int(
            (
                (df["goals_per90"] < 0)
                | (df["goals_per90"].isna() & (df["minutes"] > 0))
            ).sum()
        )

        invalid_season_bounds = int(
            (
                df["season_start"].isna()
                | df["season_end"].isna()
                | (
                    df["season_start"]
                    > df["season_end"]
                )
            ).sum()
        )

        # xG/xA doivent être NULL à ce stade
        non_null_xg = int(
            df["xg"].notna().sum()
        )

        non_null_xa = int(
            df["xa"].notna().sum()
        )

        checks = {
            "rows": len(df),
            "unique_players": df["player_id"].nunique(),
            "invalid_player_ids": invalid_player_ids,
            "negative_minutes": negative_minutes,
            "negative_goals": negative_goals,
            "negative_assists": negative_assists,
            "invalid_goals_per90": invalid_goals_per90,
            "invalid_season_bounds": invalid_season_bounds,
            "non_null_xg_before_enrichment": non_null_xg,
            "non_null_xa_before_enrichment": non_null_xa,
            "competition_levels": sorted(
                df["competition_level"]
                .dropna()
                .unique()
                .tolist()
            ),
        }

        errors = []

        if invalid_player_ids > 0:
            errors.append(
                f"{invalid_player_ids} player_id invalides"
            )

        if negative_minutes > 0:
            errors.append(
                f"{negative_minutes} lignes avec minutes négatives"
            )

        if negative_goals > 0:
            errors.append(
                f"{negative_goals} lignes avec goals négatifs"
            )

        if negative_assists > 0:
            errors.append(
                f"{negative_assists} lignes avec assists négatives"
            )

        if invalid_season_bounds > 0:
            errors.append(
                f"{invalid_season_bounds} lignes avec bornes de saison invalides"
            )

        if non_null_xg > 0:
            errors.append(
                "xg doit rester NULL avant enrichissement"
            )

        if non_null_xa > 0:
            errors.append(
                "xa doit rester NULL avant enrichissement"
            )

        if errors:
            raise ValueError(
                "Validation du dataset échouée : "
                + " | ".join(errors)
            )

        print(
            "[RealPerformanceLoader] Validation OK."
        )

        print(
            f"  Lignes               : {checks['rows']:,}"
        )

        print(
            f"  Joueurs uniques      : "
            f"{checks['unique_players']:,}"
        )

        print(
            "  Competition levels   : "
            + ", ".join(checks["competition_levels"])
        )

        print(
            "  xG/xA                : NULL "
            "(en attente enrichment)"
        )

        return checks

    # ------------------------------------------------------------------
    # CONFIGURATION
    # ------------------------------------------------------------------

    def _validate_configuration(self) -> None:
        """
        Valide la configuration initiale.
        """

        if self.config.min_minutes < 0:
            raise ValueError(
                "min_minutes doit être >= 0."
            )


# ----------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------

def main() -> None:
    """
    Point d'entrée CLI.
    """

    config = RealPerformanceLoaderConfig(
        db_path="data/transfermarkt-datasets.duckdb",
        output_path=(
            "data/performances/"
            "player_competition_season_performance.csv"
        ),
        min_minutes=0,
        exclude_national_team=True,
    )

    loader = RealPerformanceLoader(config)

    df = loader.run()

    if df.empty:
        print(
            "[RealPerformanceLoader] "
            "Aucune donnée générée."
        )
        return

    loader.validate_output(df)

    print()
    print("=" * 72)
    print("REAL PERFORMANCE LOADER — SUMMARY")
    print("=" * 72)

    print(
        f"Rows              : {len(df):,}"
    )

    print(
        f"Players           : {df['player_id'].nunique():,}"
    )

    print(
        f"Seasons           : {df['season'].nunique():,}"
    )

    print(
        f"Competitions      : "
        f"{df['competition_id'].nunique():,}"
    )

    print()
    print("Competition levels:")
    print(
        df["competition_level"]
        .value_counts()
        .to_string()
    )

    print()
    print("Sample:")
    print(
        df.head(10).to_string(index=False)
    )


if __name__ == "__main__":
    main()