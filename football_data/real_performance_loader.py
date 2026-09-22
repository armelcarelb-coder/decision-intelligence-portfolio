from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import duckdb
import pandas as pd


@dataclass(frozen=True)
class RealPerformanceLoaderConfig:
    """
    Configuration du chargement des performances réelles
    depuis la base Transfermarkt DuckDB.
    """

    # Base DuckDB Transfermarkt
    db_path: str = (
        "data/historical/transfermarkt-datasets.duckdb"
    )

    # Bornes de saison FIGÉES
    season_bounds_path: str = (
        "data/audits/season_calendar_bounds_final.csv"
    )

    # Dataset de sortie
    output_path: str = (
        "data/performances/player_competition_season_performance.csv"
    )

    # 0 = aucune restriction au niveau du Loader
    min_minutes: int = 0

    # Les compétitions de sélections nationales sont exclues.
    exclude_national_team: bool = True


class RealPerformanceLoader:
    """
    Charge et agrège les performances historiques réelles depuis
    la base Transfermarkt DuckDB

    Architecture :

    appearances
          │
          ├── games
          │
          ├── competitions
          │
          ├── players
          │
          └── season_calendar_bounds_final.csv
                │
                ▼
          bornes de saison FIGÉES
                │
                ▼
          filtrage calendrier
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

    IMPORTANT
    ---------
    Le calendrier de saison n'est plus calculé à partir des
    performances.

    La source de vérité est :

        season_calendar_bounds_final.csv

    Pour chaque match, la date doit respecter :

        season_start <= match_date <= season_end

    Les matchs hors de cette enveloppe sont exclus.

    Cela permet notamment d'exclure explicitement le match
    game_id=3606208, affecté à la saison RAW 2025 mais daté
    du 2021-09-22.
    """

    UNKNOWN_COMPETITION_LEVEL = "UNKNOWN"

    REQUIRED_BOUNDS_COLUMNS = {
        "season",
        "season_start",
        "season_end",
    }

    EXPECTED_SEASON_COUNT = 14

    def __init__(
        self,
        config: Optional[RealPerformanceLoaderConfig] = None,
    ) -> None:
        self.config = config or RealPerformanceLoaderConfig()

        self.db_path = Path(
            self.config.db_path
        )

        self.season_bounds_path = Path(
            self.config.season_bounds_path
        )

        self.output_path = Path(
            self.config.output_path
        )

        self._validate_configuration()

    # ------------------------------------------------------------------
    # PUBLIC API
    # ------------------------------------------------------------------

    def load(self) -> pd.DataFrame:
        """
        Exécute le pipeline complet et retourne le dataset agrégé.
        """

        print(
            "[RealPerformanceLoader] "
            "Chargement des performances réelles..."
        )

        self._validate_database()

        season_bounds = (
            self._load_and_validate_season_bounds()
        )

        query = self._build_query()

        with self._connect() as con:

            con.register(
                "season_calendar_bounds",
                season_bounds,
            )

            df = con.execute(
                query
            ).fetchdf()

            con.unregister(
                "season_calendar_bounds"
            )

        if df.empty:
            print(
                "[RealPerformanceLoader] "
                "Aucun enregistrement de performance trouvé."
            )
            return df

        df = self._post_process(
            df
        )

        self._validate_calendar_integration(
            df,
            season_bounds,
        )

        print(
            "[RealPerformanceLoader] "
            f"{len(df):,} lignes agrégées."
        )

        return df

    def save(
        self,
        df: pd.DataFrame,
    ) -> None:
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

    def _connect(
        self,
    ) -> duckdb.DuckDBPyConnection:
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
                for row in con.execute(
                    "SHOW TABLES"
                ).fetchall()
            }

        missing = (
            required_tables - tables
        )

        if missing:
            raise RuntimeError(
                "Tables manquantes dans la base DuckDB : "
                + ", ".join(
                    sorted(missing)
                )
            )

    # ------------------------------------------------------------------
    # SEASON CALENDAR
    # ------------------------------------------------------------------

    def _load_and_validate_season_bounds(
        self,
    ) -> pd.DataFrame:
        """
        Charge les bornes définitives de saison.

        Cette méthode ne calcule aucune borne.

        Elle vérifie uniquement que l'artefact figé est présent,
        correctement structuré et cohérent.
        """

        if not self.season_bounds_path.exists():
            raise FileNotFoundError(
                "Fichier des bornes définitives introuvable : "
                f"{self.season_bounds_path}"
            )

        bounds = pd.read_csv(
            self.season_bounds_path
        )

        missing = (
            self.REQUIRED_BOUNDS_COLUMNS
            - set(bounds.columns)
        )

        if missing:
            raise ValueError(
                "Colonnes manquantes dans les bornes définitives : "
                + ", ".join(
                    sorted(missing)
                )
            )

        bounds = bounds[
            [
                "season",
                "season_start",
                "season_end",
            ]
        ].copy()

        # --------------------------------------------------------------
        # Types
        # --------------------------------------------------------------

        bounds["season"] = pd.to_numeric(
            bounds["season"],
            errors="coerce",
        )

        bounds["season_start"] = pd.to_datetime(
            bounds["season_start"],
            errors="coerce",
        )

        bounds["season_end"] = pd.to_datetime(
            bounds["season_end"],
            errors="coerce",
        )

        # --------------------------------------------------------------
        # NULL
        # --------------------------------------------------------------

        if bounds[
            [
                "season",
                "season_start",
                "season_end",
            ]
        ].isna().any().any():

            raise ValueError(
                "Les bornes définitives contiennent des valeurs NULL."
            )

        # --------------------------------------------------------------
        # Saison entière
        # --------------------------------------------------------------

        bounds["season"] = (
            bounds["season"]
            .astype(int)
        )

        # --------------------------------------------------------------
        # Unicité
        # --------------------------------------------------------------

        duplicated = (
            bounds["season"]
            .duplicated()
        )

        if duplicated.any():

            duplicated_seasons = (
                bounds.loc[
                    duplicated,
                    "season",
                ]
                .astype(str)
                .tolist()
            )

            raise ValueError(
                "Saisons dupliquées dans les bornes définitives : "
                + ", ".join(
                    duplicated_seasons
                )
            )

        # --------------------------------------------------------------
        # Ordre des bornes
        # --------------------------------------------------------------

        invalid_bounds = (
            bounds["season_start"]
            > bounds["season_end"]
        )

        if invalid_bounds.any():

            invalid_seasons = (
                bounds.loc[
                    invalid_bounds,
                    "season",
                ]
                .astype(str)
                .tolist()
            )

            raise ValueError(
                "Bornes invalides dans "
                "season_calendar_bounds_final.csv "
                "pour les saisons : "
                + ", ".join(
                    invalid_seasons
                )
            )

        # --------------------------------------------------------------
        # Nombre de saisons
        # --------------------------------------------------------------

        if len(bounds) != self.EXPECTED_SEASON_COUNT:

            raise ValueError(
                "Nombre inattendu de saisons dans les bornes définitives : "
                f"{len(bounds)} "
                f"(attendu : {self.EXPECTED_SEASON_COUNT})"
            )

        # --------------------------------------------------------------
        # Contrôle spécifique 2025
        # --------------------------------------------------------------

        season_2025 = bounds[
            bounds["season"] == 2025
        ]

        if season_2025.empty:
            raise ValueError(
                "La saison 2025 est absente "
                "des bornes définitives."
            )

        expected_2025_start = pd.Timestamp(
            "2025-06-15"
        )

        actual_2025_start = season_2025.iloc[0][
            "season_start"
        ]

        if actual_2025_start != expected_2025_start:

            raise ValueError(
                "Borne de début de saison 2025 inattendue : "
                f"{actual_2025_start} "
                f"(attendu : {expected_2025_start})"
            )

        # --------------------------------------------------------------
        # Contrôle spécifique 3606208
        # --------------------------------------------------------------

        season_2025_end = season_2025.iloc[0][
            "season_end"
        ]

        review_game_date = pd.Timestamp(
            "2021-09-22"
        )

        if (
            actual_2025_start
            <= review_game_date
            <= season_2025_end
        ):

            raise ValueError(
                "Le calendrier définitif de 2025 "
                "inclurait le game_id=3606208 "
                "(2021-09-22). "
                "Les bornes définitives sont incohérentes."
            )

        print(
            "[RealPerformanceLoader] "
            "Bornes définitives chargées."
        )

        print(
            f"  Fichier : {self.season_bounds_path}"
        )

        print(
            f"  Saisons : {len(bounds)}"
        )

        print(
            "  Saison 2025 : "
            f"{actual_2025_start.date()} -> "
            f"{season_2025_end.date()}"
        )

        print(
            "  game_id=3606208 : "
            "exclu par les bornes calendaires."
        )

        return bounds

    # ------------------------------------------------------------------
    # SQL
    # ------------------------------------------------------------------

    def _build_query(self) -> str:
        """
        Construit la requête DuckDB.

        La table season_calendar_bounds est enregistrée temporairement
        dans DuckDB depuis season_calendar_bounds_final.csv.

        La granularité finale est :

            player_id
            + season
            + competition_id
            + competition_level
        """

        national_team_filter = ""

        if self.config.exclude_national_team:

            national_team_filter = """
                AND COALESCE(
                    g.competition_type,
                    ''
                ) != 'national_team_competition'

                AND LOWER(
                    COALESCE(
                        c.competition_code,
                        ''
                    )
                ) NOT IN (
                    'world-cup',
                    'uefa-euro',
                    'euro',
                    'africa-cup-of-nations',
                    'afcon',
                    'afc-asian-cup',
                    'asian-cup',
                    'copa-america',
                    'concacaf-gold-cup',
                    'concacaf-nations-league',
                    'uefa-nations-league',
                    'fifa-confederations-cup',
                    'olympic-football',
                    'olympics'
                )

                AND LOWER(
                    COALESCE(
                        c.name,
                        ''
                    )
                ) NOT IN (
                    'world cup',
                    'uefa euro',
                    'euro',
                    'africa cup of nations',
                    'afcon',
                    'afc asian cup',
                    'asian cup',
                    'copa america',
                    'concacaf gold cup',
                    'concacaf nations league',
                    'uefa nations league',
                    'fifa confederations cup',
                    'olympic football',
                    'olympics'
                )
            """

        min_minutes_filter = ""

        if self.config.min_minutes > 0:

            min_minutes_filter = f"""
                HAVING SUM(
                    COALESCE(
                        a.minutes_played,
                        0
                    )
                ) >= {int(self.config.min_minutes)}
            """

        query = f"""
        WITH base AS (

            SELECT

                a.player_id,

                p.name AS player,

                p.position,

                p.sub_position,

                CAST(
                    g.season AS INTEGER
                ) AS season,

                g.date AS match_date,

                a.game_id,

                a.minutes_played,

                a.goals,

                a.assists,

                a.competition_id,

                c.competition_code,

                c.name AS competition_name,

                c.sub_type AS competition_sub_type,

                c.type AS competition_type,

                c.country_name,

                c.confederation,

                /*
                * Bornes de saison FIGÉES.
                *
                * Elles proviennent exclusivement de :
                *
                * season_calendar_bounds_final.csv
                */

                sb.season_start,

                sb.season_end,

                CASE

                    /*
                    * Champions League
                    */

                    WHEN c.sub_type =
                        'uefa_champions_league'

                        THEN 'CHAMPIONS_LEAGUE'

                    /*
                    * Europa League
                    */

                    WHEN c.sub_type =
                        'uefa_europa_league'

                        THEN 'EUROPA_LEAGUE'

                    /*
                    * Conference League
                    */

                    WHEN c.sub_type =
                        'uefa_conference_league'

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

                    WHEN c.type =
                        'domestic_league'

                        AND c.sub_type =
                            'first_tier'

                        THEN 'TOP_LEAGUE'

                    /*
                    * Domestic cups
                    */

                    WHEN c.type =
                        'domestic_cup'

                        THEN 'DOMESTIC_CUP'

                    /*
                    * Domestic super cups
                    */

                    WHEN c.sub_type =
                        'domestic_super_cup'

                        THEN 'DOMESTIC_SUPER_CUP'

                    /*
                    * Playoffs
                    */

                    WHEN c.sub_type =
                        'play_off'

                        THEN 'PLAY_OFF'

                    /*
                    * Unknown metadata
                    */

                    ELSE '{self.UNKNOWN_COMPETITION_LEVEL}'

                END AS competition_level

            FROM appearances AS a

            INNER JOIN games AS g

                ON CAST(
                    a.game_id AS VARCHAR
                )
                =
                CAST(
                    g.game_id AS VARCHAR
                )

            /*
            * Les bornes définitives sont une référence obligatoire.
            */

            INNER JOIN season_calendar_bounds AS sb

                ON CAST(
                    g.season AS INTEGER
                )
                =
                sb.season

                AND g.date >= sb.season_start

                AND g.date <= sb.season_end

            LEFT JOIN competitions AS c

                ON a.competition_id =
                c.competition_id

            LEFT JOIN players AS p

                ON a.player_id =
                p.player_id

            WHERE

                a.player_id IS NOT NULL

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

                /*
                * Les bornes sont identiques pour toutes les lignes
                * d'une même saison.
                */

                MAX(season_start)
                    AS season_start,

                MAX(season_end)
                    AS season_end,

                competition_id,

                MAX(competition_name)
                    AS competition_name,

                MAX(competition_sub_type)
                    AS competition_sub_type,

                MAX(competition_type)
                    AS competition_type,

                MAX(country_name)
                    AS country_name,

                MAX(confederation)
                    AS confederation,

                MAX(competition_level)
                    AS competition_level,

                MIN(match_date)
                    AS first_match_date,

                MAX(match_date)
                    AS last_match_date,

                COUNT(
                    DISTINCT game_id
                ) AS appearances,

                SUM(
                    COALESCE(
                        minutes_played,
                        0
                    )
                ) AS minutes,

                SUM(
                    COALESCE(
                        goals,
                        0
                    )
                ) AS goals,

                SUM(
                    COALESCE(
                        assists,
                        0
                    )
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

            season_start,

            season_end,

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
            * 90 minutes is the denominator utilisé
            * throughout the performance pipeline.
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
            * xG / xA intentionally NULL.
            */

            CAST(
                NULL AS DOUBLE
            ) AS xg,

            CAST(
                NULL AS DOUBLE
            ) AS xa,

            CAST(
                NULL AS DOUBLE
            ) AS xg_per90,

            CAST(
                NULL AS DOUBLE
            ) AS xa_per90

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

    def _post_process(
        self,
        df: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Nettoyage léger côté pandas.

        Aucun calcul de bornes de saison n'est effectué ici.
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

        if "season" in result.columns:

            result["season"] = pd.to_numeric(
                result["season"],
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
            "season_start",
            "season_end",
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
            .fillna(
                self.UNKNOWN_COMPETITION_LEVEL
            )
            .astype(str)
        )

        result["competition_level"] = (
            result["competition_level"]
            .replace(
                {
                    "":
                        self.UNKNOWN_COMPETITION_LEVEL,
                    "None":
                        self.UNKNOWN_COMPETITION_LEVEL,
                    "nan":
                        self.UNKNOWN_COMPETITION_LEVEL,
                }
            )
        )

        # --------------------------------------------------------------
        # Contrôle calendrier
        # --------------------------------------------------------------

        invalid_calendar = (
            result["first_match_date"]
            < result["season_start"]
        ) | (
            result["last_match_date"]
            > result["season_end"]
        )

        if invalid_calendar.any():

            invalid_rows = int(
                invalid_calendar.sum()
            )

            raise ValueError(
                "Des performances contiennent des dates "
                "en dehors des bornes définitives : "
                f"{invalid_rows} ligne(s)."
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

        result = result[
            existing_columns
        ]

        return result

    # ------------------------------------------------------------------
    # CALENDAR INTEGRATION VALIDATION
    # ------------------------------------------------------------------

    def _validate_calendar_integration(
        self,
        df: pd.DataFrame,
        season_bounds: pd.DataFrame,
    ) -> None:
        """
        Vérifie que le dataset final respecte exactement les bornes
        définitives.
        """

        # --------------------------------------------------------------
        # Toutes les saisons doivent exister dans l'artefact
        # --------------------------------------------------------------

        known_seasons = set(
            season_bounds["season"]
            .astype(int)
            .tolist()
        )

        output_seasons = set(
            df["season"]
            .dropna()
            .astype(int)
            .tolist()
        )

        unknown_seasons = (
            output_seasons - known_seasons
        )

        if unknown_seasons:

            raise ValueError(
                "Des saisons absentes des bornes définitives "
                "sont présentes dans le résultat : "
                + ", ".join(
                    map(
                        str,
                        sorted(
                            unknown_seasons
                        ),
                    )
                )
            )

        # --------------------------------------------------------------
        # Bornes identiques au référentiel
        # --------------------------------------------------------------

        expected = season_bounds.copy()

        expected["season"] = (
            expected["season"]
            .astype(int)
        )

        expected["season_start"] = pd.to_datetime(
            expected["season_start"]
        )

        expected["season_end"] = pd.to_datetime(
            expected["season_end"]
        )

        actual = (
            df[
                [
                    "season",
                    "season_start",
                    "season_end",
                ]
            ]
            .drop_duplicates()
            .copy()
        )

        actual["season"] = (
            actual["season"]
            .astype(int)
        )

        actual["season_start"] = pd.to_datetime(
            actual["season_start"]
        )

        actual["season_end"] = pd.to_datetime(
            actual["season_end"]
        )

        comparison = actual.merge(
            expected,
            on="season",
            how="left",
            suffixes=(
                "_actual",
                "_expected",
            ),
            validate="many_to_one",
        )

        mismatched = comparison[
            (
                comparison["season_start_actual"]
                !=
                comparison["season_start_expected"]
            )
            |
            (
                comparison["season_end_actual"]
                !=
                comparison["season_end_expected"]
            )
        ]

        if not mismatched.empty:

            raise ValueError(
                "Les bornes présentes dans les performances "
                "ne correspondent pas aux bornes définitives :\n"
                + mismatched.to_string(
                    index=False
                )
            )

        # --------------------------------------------------------------
        # Contrôle spécifique 3606208
        # --------------------------------------------------------------

        with self._connect() as con:

            review_check = con.execute(
                """
                SELECT
                    g.game_id,
                    g.season,
                    g.date
                FROM games AS g
                WHERE g.game_id = 3606208
                """
            ).fetchdf()

        if not review_check.empty:

            appears_in_output = False

            if "season" in df.columns:

                appears_in_output = bool(
                    (
                        (
                            df["season"]
                            .astype("Int64")
                            == 2025
                        )
                        &
                        (
                            pd.to_datetime(
                                df["first_match_date"]
                            )
                            <= pd.Timestamp(
                                "2021-09-22"
                            )
                        )
                        &
                        (
                            pd.to_datetime(
                                df["last_match_date"]
                            )
                            >= pd.Timestamp(
                                "2021-09-22"
                            )
                        )
                    ).any()
                )

            if appears_in_output:

                raise ValueError(
                    "Le match 3606208 semble avoir été "
                    "réintroduit dans les performances."
                )

        print(
            "[RealPerformanceLoader] "
            "Intégration des bornes calendaires : OK."
        )

        print(
            f"  Saisons référentielles : "
            f"{len(season_bounds)}"
        )

        print(
            f"  Saisons dans output    : "
            f"{len(output_seasons)}"
        )

        print(
            "  Bornes identiques      : OUI"
        )

        print(
            "  game_id=3606208        : EXCLU"
        )

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

        # --------------------------------------------------------------
        # IDs joueurs valides
        # --------------------------------------------------------------

        invalid_player_ids = int(
            df["player_id"].isna().sum()
        )

        # --------------------------------------------------------------
        # Minutes négatives
        # --------------------------------------------------------------

        negative_minutes = int(
            (
                df["minutes"] < 0
            ).sum()
        )

        # --------------------------------------------------------------
        # Goals négatifs
        # --------------------------------------------------------------

        negative_goals = int(
            (
                df["goals"] < 0
            ).sum()
        )

        # --------------------------------------------------------------
        # Assists négatives
        # --------------------------------------------------------------

        negative_assists = int(
            (
                df["assists"] < 0
            ).sum()
        )

        # --------------------------------------------------------------
        # Per90 incohérents
        # --------------------------------------------------------------

        invalid_goals_per90 = int(
            (
                (
                    df["goals_per90"] < 0
                )
                |
                (
                    df["goals_per90"].isna()
                    &
                    (
                        df["minutes"] > 0
                    )
                )
            ).sum()
        )

        invalid_season_bounds = int(
            (
                df["season_start"].isna()
                |
                df["season_end"].isna()
                |
                (
                    df["season_start"]
                    >
                    df["season_end"]
                )
            ).sum()
        )

        # --------------------------------------------------------------
        # Match dates hors bornes
        # --------------------------------------------------------------

        invalid_match_dates = int(
            (
                (
                    df["first_match_date"]
                    <
                    df["season_start"]
                )
                |
                (
                    df["last_match_date"]
                    >
                    df["season_end"]
                )
            ).sum()
        )

        # --------------------------------------------------------------
        # xG/xA doivent être NULL à ce stade
        # --------------------------------------------------------------

        non_null_xg = int(
            df["xg"].notna().sum()
        )

        non_null_xa = int(
            df["xa"].notna().sum()
        )

        checks = {

            "rows":
                len(df),

            "unique_players":
                df["player_id"].nunique(),

            "invalid_player_ids":
                invalid_player_ids,

            "negative_minutes":
                negative_minutes,

            "negative_goals":
                negative_goals,

            "negative_assists":
                negative_assists,

            "invalid_goals_per90":
                invalid_goals_per90,

            "invalid_season_bounds":
                invalid_season_bounds,

            "invalid_match_dates":
                invalid_match_dates,

            "non_null_xg_before_enrichment":
                non_null_xg,

            "non_null_xa_before_enrichment":
                non_null_xa,

            "competition_levels":
                sorted(
                    df[
                        "competition_level"
                    ]
                    .dropna()
                    .unique()
                    .tolist()
                ),
        }

        errors = []

        if invalid_player_ids > 0:

            errors.append(
                f"{invalid_player_ids} "
                "player_id invalides"
            )

        if negative_minutes > 0:

            errors.append(
                f"{negative_minutes} lignes "
                "avec minutes négatives"
            )

        if negative_goals > 0:

            errors.append(
                f"{negative_goals} lignes "
                "avec goals négatifs"
            )

        if negative_assists > 0:

            errors.append(
                f"{negative_assists} lignes "
                "avec assists négatives"
            )

        if invalid_season_bounds > 0:

            errors.append(
                f"{invalid_season_bounds} lignes "
                "avec bornes de saison invalides"
            )

        if invalid_match_dates > 0:

            errors.append(
                f"{invalid_match_dates} lignes "
                "avec dates hors bornes définitives"
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
            "[RealPerformanceLoader] "
            "Validation OK."
        )

        print(
            f"  Lignes               : "
            f"{checks['rows']:,}"
        )

        print(
            f"  Joueurs uniques      : "
            f"{checks['unique_players']:,}"
        )

        print(
            f"  Bornes invalides     : "
            f"{checks['invalid_season_bounds']}"
        )

        print(
            f"  Dates hors bornes    : "
            f"{checks['invalid_match_dates']}"
        )

        print(
            "  Competition levels   : "
            + ", ".join(
                checks["competition_levels"]
            )
        )

        print(
            "  xG/xA                : NULL "
            "(en attente enrichment)"
        )

        return checks

# ------------------------------------------------------------------
# CONFIGURATION
# ------------------------------------------------------------------

    def _validate_configuration(
        self,
    ) -> None:
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
        db_path=(
            "data/historical/"
            "transfermarkt-datasets.duckdb"
        ),

        season_bounds_path=(
            "data/audits/"
            "season_calendar_bounds_final.csv"
        ),

        output_path=(
            "data/performances/"
            "player_competition_season_performance.csv"
        ),

        min_minutes=0,

        exclude_national_team=True,
    )

    loader = RealPerformanceLoader(
        config
    )

    df = loader.run()

    if df.empty:
        print(
            "[RealPerformanceLoader] "
            "Aucune donnée générée."
        )
        return

    loader.validate_output(
        df
    )

    print()
    print(
        "=" * 72
    )
    print(
        "REAL PERFORMANCE LOADER — SUMMARY"
    )
    print(
        "=" * 72
    )

    print(
        f"Rows              : "
        f"{len(df):,}"
    )

    print(
        f"Players           : "
        f"{df['player_id'].nunique():,}"
    )

    print(
        f"Seasons           : "
        f"{df['season'].nunique():,}"
    )

    print(
        f"Competitions      : "
        f"{df['competition_id'].nunique():,}"
    )

    print()

    print(
        "Competition levels:"
    )

    print(
        df[
            "competition_level"
        ]
        .value_counts()
        .to_string()
    )

    print()

    print(
        "Season bounds:"
    )

    print(
        df[
            [
                "season",
                "season_start",
                "season_end",
            ]
        ]
        .drop_duplicates()
        .sort_values(
            "season"
        )
        .to_string(
            index=False
        )
    )

    print()

    print(
        "Sample:"
    )

    print(
        df.head(10)
        .to_string(
            index=False
        )
    )


if __name__ == "__main__":
    main()