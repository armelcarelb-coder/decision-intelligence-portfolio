from __future__ import annotations

from pathlib import Path

import duckdb

DATABASE_PATH = Path("data/historical/transfermarkt-datasets.duckdb")

# Valeur connue dans le dataset Transfermarkt utilisé par le projet.

NATIONAL_TEAM_COMPETITION = "national_team_competition"

# Mots-clés utilisés uniquement pour identifier les compétitions

# qui correspondent manifestement à des matchs amicaux/préparation.

FRIENDLY_KEYWORDS = (
"friendly",
"friendlies",
"amical",
"pre-season",
"preseason",
"pre season",
"preparation",
"préparation",
"test match",
"test-match",
)

class RawSeasonCalendarAudit:

# Audit de référence du calendrier des saisons club.

    def __init__(self, database_path: Path):
        self.database_path = database_path
        self.con: duckdb.DuckDBPyConnection | None = None

    # ------------------------------------------------------------------
    # CONNECTION
    # ------------------------------------------------------------------

    def connect(self) -> None:
        if not self.database_path.exists():
            raise FileNotFoundError(
                f"Base DuckDB introuvable : {self.database_path}"
            )

        self.con = duckdb.connect(
            database=str(self.database_path),
            read_only=True,
        )

    def close(self) -> None:
        if self.con is not None:
            self.con.close()
            self.con = None

    # ------------------------------------------------------------------
    # HELPERS
    # ------------------------------------------------------------------

    def _require_connection(self) -> duckdb.DuckDBPyConnection:
        if self.con is None:
            raise RuntimeError("La connexion DuckDB n'est pas ouverte.")
        return self.con

    @staticmethod
    def _print_title(title: str) -> None:
        print()
        print("=" * 100)
        print(title)
        print("=" * 100)

    @staticmethod
    def _print_dataframe(df, max_rows: int = 100) -> None:
        if df.empty:
            print("Aucune ligne.")
            return

        if len(df) > max_rows:
            print(
                f"Affichage limité à {max_rows} lignes "
                f"sur {len(df)} lignes."
            )
            print(df.head(max_rows).to_string(index=False))
        else:
            print(df.to_string(index=False))

    # ------------------------------------------------------------------
    # 1. SCHEMA
    # ------------------------------------------------------------------

    def audit_schema(self) -> None:
        con = self._require_connection()

        self._print_title("1. SCHEMA DES TABLES UTILISEES")

        for table_name in ("games", "competitions"):
            print(f"\n--- {table_name} ---")

            df = con.execute(
                f"""
                DESCRIBE {table_name}
                """
            ).df()

            self._print_dataframe(df, max_rows=100)

    # ------------------------------------------------------------------
    # 2. VALEURS DE COMPETITION_TYPE
    # ------------------------------------------------------------------

    def audit_competition_types(self) -> None:
        con = self._require_connection()

        self._print_title(
            "2. REPARTITION DES competition_type DANS games"
        )

        df = con.execute(
            """
            SELECT
                competition_type,
                COUNT(*) AS games_count,
                MIN(date) AS first_date,
                MAX(date) AS last_date,
                COUNT(DISTINCT season) AS seasons_count
            FROM games
            GROUP BY competition_type
            ORDER BY games_count DESC
            """
        ).df()

        self._print_dataframe(df)

    # ------------------------------------------------------------------
    # 3. CONSTRUCTION DU PERIMETRE OFFICIEL CLUB
    # ------------------------------------------------------------------

    def build_official_club_games(self):
        """
        Construit la relation logique des matchs officiels de clubs.

        Règles :

        1. date non NULL
        2. competition_type != national_team_competition
        3. competition_type = club lorsque cette information est disponible
        4. exclusion des compétitions dont les métadonnées indiquent
        manifestement un match amical / préparation.

        Le résultat n'est pas écrit dans la base.
        """

        con = self._require_connection()

        return con.execute(
            f"""
            WITH competition_metadata AS (
                SELECT
                    competition_id,
                    competition_code,
                    name,
                    sub_type,
                    type,
                    country_name,
                    confederation
                FROM competitions
            )

            SELECT
                g.game_id,
                g.season,
                CAST(g.date AS DATE) AS match_date,
                g.competition_id,
                g.competition_type,

                c.competition_code,
                c.name AS competition_name,
                c.sub_type AS competition_sub_type,
                c.type AS competition_type_metadata,
                c.country_name,
                c.confederation,

                CASE
                    WHEN g.competition_type = ?
                        THEN 'EXCLUDE_NATIONAL_TEAM'

                    WHEN LOWER(
                        COALESCE(c.name, '') || ' ' ||
                        COALESCE(c.competition_code, '') || ' ' ||
                        COALESCE(c.sub_type, '') || ' ' ||
                        COALESCE(c.type, '')
                    ) LIKE '%friendly%'
                        THEN 'EXCLUDE_FRIENDLY'

                    WHEN LOWER(
                        COALESCE(c.name, '') || ' ' ||
                        COALESCE(c.competition_code, '') || ' ' ||
                        COALESCE(c.sub_type, '') || ' ' ||
                        COALESCE(c.type, '')
                    ) LIKE '%amical%'
                        THEN 'EXCLUDE_FRIENDLY'

                    WHEN LOWER(
                        COALESCE(c.name, '') || ' ' ||
                        COALESCE(c.competition_code, '') || ' ' ||
                        COALESCE(c.sub_type, '') || ' ' ||
                        COALESCE(c.type, '')
                    ) LIKE '%pre-season%'
                        THEN 'EXCLUDE_FRIENDLY'

                    WHEN LOWER(
                        COALESCE(c.name, '') || ' ' ||
                        COALESCE(c.competition_code, '') || ' ' ||
                        COALESCE(c.sub_type, '') || ' ' ||
                        COALESCE(c.type, '')
                    ) LIKE '%preseason%'
                        THEN 'EXCLUDE_FRIENDLY'

                    WHEN LOWER(
                        COALESCE(c.name, '') || ' ' ||
                        COALESCE(c.competition_code, '') || ' ' ||
                        COALESCE(c.sub_type, '') || ' ' ||
                        COALESCE(c.type, '')
                    ) LIKE '%pre season%'
                        THEN 'EXCLUDE_FRIENDLY'

                    WHEN LOWER(
                        COALESCE(c.name, '') || ' ' ||
                        COALESCE(c.competition_code, '') || ' ' ||
                        COALESCE(c.sub_type, '') || ' ' ||
                        COALESCE(c.type, '')
                    ) LIKE '%preparation%'
                        THEN 'EXCLUDE_FRIENDLY'

                    WHEN LOWER(
                        COALESCE(c.name, '') || ' ' ||
                        COALESCE(c.competition_code, '') || ' ' ||
                        COALESCE(c.sub_type, '') || ' ' ||
                        COALESCE(c.type, '')
                    ) LIKE '%préparation%'
                        THEN 'EXCLUDE_FRIENDLY'

                    WHEN LOWER(
                        COALESCE(c.name, '') || ' ' ||
                        COALESCE(c.competition_code, '') || ' ' ||
                        COALESCE(c.sub_type, '') || ' ' ||
                        COALESCE(c.type, '')
                    ) LIKE '%test match%'
                        THEN 'EXCLUDE_FRIENDLY'

                    WHEN c.competition_id IS NULL
                        THEN 'REVIEW_MISSING_COMPETITION_METADATA'

                    ELSE 'KEEP'
                END AS audit_status

            FROM games g
            LEFT JOIN competition_metadata c
                ON g.competition_id = c.competition_id

            WHERE g.date IS NOT NULL
            """,
            [NATIONAL_TEAM_COMPETITION],
        ).df()

    # ------------------------------------------------------------------
    # 4. STATISTIQUES DU PERIMETRE
    # ------------------------------------------------------------------

    def audit_official_club_scope(self) -> None:
        con = self._require_connection()

        self._print_title(
            "3. CONTROLE DU PERIMETRE MATCHS OFFICIELS CLUB"
        )

        df = con.execute(
            f"""
            WITH base AS (
                SELECT
                    g.game_id,
                    g.season,
                    g.date,
                    g.competition_id,
                    g.competition_type,
                    c.competition_code,
                    c.name,
                    c.sub_type,
                    c.type,
                    CASE
                        WHEN g.competition_type = '{NATIONAL_TEAM_COMPETITION}'
                            THEN 'EXCLUDE_NATIONAL_TEAM'

                        WHEN LOWER(
                            COALESCE(c.name, '') || ' ' ||
                            COALESCE(c.competition_code, '') || ' ' ||
                            COALESCE(c.sub_type, '') || ' ' ||
                            COALESCE(c.type, '')
                        ) LIKE '%friendly%'
                            THEN 'EXCLUDE_FRIENDLY'

                        WHEN LOWER(
                            COALESCE(c.name, '') || ' ' ||
                            COALESCE(c.competition_code, '') || ' ' ||
                            COALESCE(c.sub_type, '') || ' ' ||
                            COALESCE(c.type, '')
                        ) LIKE '%amical%'
                            THEN 'EXCLUDE_FRIENDLY'

                        WHEN LOWER(
                            COALESCE(c.name, '') || ' ' ||
                            COALESCE(c.competition_code, '') || ' ' ||
                            COALESCE(c.sub_type, '') || ' ' ||
                            COALESCE(c.type, '')
                        ) LIKE '%pre-season%'
                            THEN 'EXCLUDE_FRIENDLY'

                        WHEN LOWER(
                            COALESCE(c.name, '') || ' ' ||
                            COALESCE(c.competition_code, '') || ' ' ||
                            COALESCE(c.sub_type, '') || ' ' ||
                            COALESCE(c.type, '')
                        ) LIKE '%preseason%'
                            THEN 'EXCLUDE_FRIENDLY'

                        WHEN LOWER(
                            COALESCE(c.name, '') || ' ' ||
                            COALESCE(c.competition_code, '') || ' ' ||
                            COALESCE(c.sub_type, '') || ' ' ||
                            COALESCE(c.type, '')
                        ) LIKE '%preparation%'
                            THEN 'EXCLUDE_FRIENDLY'

                        WHEN LOWER(
                            COALESCE(c.name, '') || ' ' ||
                            COALESCE(c.competition_code, '') || ' ' ||
                            COALESCE(c.sub_type, '') || ' ' ||
                            COALESCE(c.type, '')
                        ) LIKE '%préparation%'
                            THEN 'EXCLUDE_FRIENDLY'

                        WHEN c.competition_id IS NULL
                            THEN 'REVIEW_MISSING_COMPETITION_METADATA'

                        ELSE 'KEEP'
                    END AS audit_status

                FROM games g
                LEFT JOIN competitions c
                    ON g.competition_id = c.competition_id

                WHERE g.date IS NOT NULL
            )

            SELECT
                audit_status,
                COUNT(*) AS games_count,
                COUNT(DISTINCT game_id) AS distinct_games,
                COUNT(DISTINCT season) AS seasons_count,
                MIN(date) AS first_date,
                MAX(date) AS last_date
            FROM base
            GROUP BY audit_status
            ORDER BY games_count DESC
            """
        ).df()

        self._print_dataframe(df)

    # ------------------------------------------------------------------
    # 5. BORNES DE SAISON
    # ------------------------------------------------------------------

    def calculate_season_bounds(self):
        """
        Calcule les bornes métier :

            season_start = premier match officiel club
            season_end   = dernier match officiel club

        Les dates sont inclusives.

        IMPORTANT :
            les bornes sont calculées uniquement sur les matchs
            dont audit_status = KEEP.

        Les compétitions sans métadonnées ne sont PAS intégrées
        automatiquement aux bornes : elles sont remontées séparément
        pour revue.
        """

        con = self._require_connection()

        df = con.execute(
            f"""
            WITH official_club_games AS (
                SELECT
                    g.game_id,
                    g.season,
                    CAST(g.date AS DATE) AS match_date,
                    g.competition_id,
                    g.competition_type,

                    c.competition_code,
                    c.name AS competition_name,
                    c.sub_type,
                    c.type,

                    CASE
                        WHEN g.competition_type = '{NATIONAL_TEAM_COMPETITION}'
                            THEN 'EXCLUDE_NATIONAL_TEAM'

                        WHEN LOWER(
                            COALESCE(c.name, '') || ' ' ||
                            COALESCE(c.competition_code, '') || ' ' ||
                            COALESCE(c.sub_type, '') || ' ' ||
                            COALESCE(c.type, '')
                        ) LIKE '%friendly%'
                            THEN 'EXCLUDE_FRIENDLY'

                        WHEN LOWER(
                            COALESCE(c.name, '') || ' ' ||
                            COALESCE(c.competition_code, '') || ' ' ||
                            COALESCE(c.sub_type, '') || ' ' ||
                            COALESCE(c.type, '')
                        ) LIKE '%amical%'
                            THEN 'EXCLUDE_FRIENDLY'

                        WHEN LOWER(
                            COALESCE(c.name, '') || ' ' ||
                            COALESCE(c.competition_code, '') || ' ' ||
                            COALESCE(c.sub_type, '') || ' ' ||
                            COALESCE(c.type, '')
                        ) LIKE '%pre-season%'
                            THEN 'EXCLUDE_FRIENDLY'

                        WHEN LOWER(
                            COALESCE(c.name, '') || ' ' ||
                            COALESCE(c.competition_code, '') || ' ' ||
                            COALESCE(c.sub_type, '') || ' ' ||
                            COALESCE(c.type, '')
                        ) LIKE '%preseason%'
                            THEN 'EXCLUDE_FRIENDLY'

                        WHEN LOWER(
                            COALESCE(c.name, '') || ' ' ||
                            COALESCE(c.competition_code, '') || ' ' ||
                            COALESCE(c.sub_type, '') || ' ' ||
                            COALESCE(c.type, '')
                        ) LIKE '%preparation%'
                            THEN 'EXCLUDE_FRIENDLY'

                        WHEN LOWER(
                            COALESCE(c.name, '') || ' ' ||
                            COALESCE(c.competition_code, '') || ' ' ||
                            COALESCE(c.sub_type, '') || ' ' ||
                            COALESCE(c.type, '')
                        ) LIKE '%préparation%'
                            THEN 'EXCLUDE_FRIENDLY'

                        WHEN c.competition_id IS NULL
                            THEN 'REVIEW_MISSING_COMPETITION_METADATA'

                        ELSE 'KEEP'
                    END AS audit_status

                FROM games g
                LEFT JOIN competitions c
                    ON g.competition_id = c.competition_id

                WHERE g.date IS NOT NULL
            )

            SELECT
                season,

                MIN(match_date) AS season_start,
                MAX(match_date) AS season_end,

                DATE_DIFF(
                    'day',
                    MIN(match_date),
                    MAX(match_date)
                ) + 1 AS season_duration_days,

                COUNT(DISTINCT game_id) AS official_club_games,

                COUNT(DISTINCT competition_id)
                    AS official_club_competitions

            FROM official_club_games

            WHERE audit_status = 'KEEP'

            GROUP BY season
            ORDER BY season
            """
        ).df()

        return df

    def print_season_bounds(self) -> None:
        self._print_title(
            "4. BORNES OFFICIELLES DES SAISONS CLUB"
        )

        df = self.calculate_season_bounds()

        print(
            "\nDEFINITION :\n"
            "  season_start = premier match officiel de club\n"
            "  season_end   = dernier match officiel de club\n"
            "  bornes inclusives = [season_start, season_end]\n"
        )

        self._print_dataframe(df, max_rows=200)

    # ------------------------------------------------------------------
    # 6. MATCH QUI DETERMINE CHAQUE BORNE
    # ------------------------------------------------------------------

    def audit_boundary_matches(self) -> None:
        con = self._require_connection()

        self._print_title(
            "5. MATCHS DETERMINANT LES BORNES DE CHAQUE SAISON"
        )

        df = con.execute(
            f"""
            WITH official_club_games AS (
                SELECT
                    g.game_id,
                    g.season,
                    CAST(g.date AS DATE) AS match_date,
                    g.competition_id,
                    g.competition_type,
                    c.competition_code,
                    c.name AS competition_name,
                    c.sub_type,
                    c.type,

                    CASE
                        WHEN g.competition_type = '{NATIONAL_TEAM_COMPETITION}'
                            THEN 'EXCLUDE_NATIONAL_TEAM'

                        WHEN LOWER(
                            COALESCE(c.name, '') || ' ' ||
                            COALESCE(c.competition_code, '') || ' ' ||
                            COALESCE(c.sub_type, '') || ' ' ||
                            COALESCE(c.type, '')
                        ) LIKE '%friendly%'
                            THEN 'EXCLUDE_FRIENDLY'

                        WHEN LOWER(
                            COALESCE(c.name, '') || ' ' ||
                            COALESCE(c.competition_code, '') || ' ' ||
                            COALESCE(c.sub_type, '') || ' ' ||
                            COALESCE(c.type, '')
                        ) LIKE '%amical%'
                            THEN 'EXCLUDE_FRIENDLY'

                        WHEN LOWER(
                            COALESCE(c.name, '') || ' ' ||
                            COALESCE(c.competition_code, '') || ' ' ||
                            COALESCE(c.sub_type, '') || ' ' ||
                            COALESCE(c.type, '')
                        ) LIKE '%pre-season%'
                            THEN 'EXCLUDE_FRIENDLY'

                        WHEN LOWER(
                            COALESCE(c.name, '') || ' ' ||
                            COALESCE(c.competition_code, '') || ' ' ||
                            COALESCE(c.sub_type, '') || ' ' ||
                            COALESCE(c.type, '')
                        ) LIKE '%preseason%'
                            THEN 'EXCLUDE_FRIENDLY'

                        WHEN LOWER(
                            COALESCE(c.name, '') || ' ' ||
                            COALESCE(c.competition_code, '') || ' ' ||
                            COALESCE(c.sub_type, '') || ' ' ||
                            COALESCE(c.type, '')
                        ) LIKE '%preparation%'
                            THEN 'EXCLUDE_FRIENDLY'

                        WHEN LOWER(
                            COALESCE(c.name, '') || ' ' ||
                            COALESCE(c.competition_code, '') || ' ' ||
                            COALESCE(c.sub_type, '') || ' ' ||
                            COALESCE(c.type, '')
                        ) LIKE '%préparation%'
                            THEN 'EXCLUDE_FRIENDLY'

                        WHEN c.competition_id IS NULL
                            THEN 'REVIEW_MISSING_COMPETITION_METADATA'

                        ELSE 'KEEP'
                    END AS audit_status

                FROM games g
                LEFT JOIN competitions c
                    ON g.competition_id = c.competition_id

                WHERE g.date IS NOT NULL
            ),

            bounds AS (
                SELECT
                    season,
                    MIN(match_date) AS season_start,
                    MAX(match_date) AS season_end
                FROM official_club_games
                WHERE audit_status = 'KEEP'
                GROUP BY season
            )

            SELECT
                g.season,
                g.match_date,
                CASE
                    WHEN g.match_date = b.season_start
                        THEN 'SEASON_START'
                    WHEN g.match_date = b.season_end
                        THEN 'SEASON_END'
                END AS boundary_type,

                g.game_id,
                g.competition_id,
                g.competition_code,
                g.competition_name,
                g.competition_type,

                g.season AS raw_game_season

            FROM official_club_games g

            INNER JOIN bounds b
                ON g.season = b.season
                AND (
                    g.match_date = b.season_start
                    OR g.match_date = b.season_end
                )

            WHERE g.audit_status = 'KEEP'

            ORDER BY
                g.season,
                g.match_date,
                boundary_type
            """
        ).df()

        self._print_dataframe(df, max_rows=500)

    # ------------------------------------------------------------------
    # 7. COMPETITIONS QUI DETERMINENT LES BORNES
    # ------------------------------------------------------------------

    def audit_boundary_competitions(self) -> None:
        con = self._require_connection()

        self._print_title(
            "6. COMPETITIONS QUI DETERMINENT LES BORNES"
        )

        df = con.execute(
            f"""
            WITH official_club_games AS (
                SELECT
                    g.game_id,
                    g.season,
                    CAST(g.date AS DATE) AS match_date,
                    g.competition_id,
                    c.competition_code,
                    c.name AS competition_name,
                    g.competition_type,

                    CASE
                        WHEN g.competition_type = '{NATIONAL_TEAM_COMPETITION}'
                            THEN 'EXCLUDE_NATIONAL_TEAM'

                        WHEN LOWER(
                            COALESCE(c.name, '') || ' ' ||
                            COALESCE(c.competition_code, '') || ' ' ||
                            COALESCE(c.sub_type, '') || ' ' ||
                            COALESCE(c.type, '')
                        ) LIKE '%friendly%'
                            THEN 'EXCLUDE_FRIENDLY'

                        WHEN LOWER(
                            COALESCE(c.name, '') || ' ' ||
                            COALESCE(c.competition_code, '') || ' ' ||
                            COALESCE(c.sub_type, '') || ' ' ||
                            COALESCE(c.type, '')
                        ) LIKE '%amical%'
                            THEN 'EXCLUDE_FRIENDLY'

                        WHEN LOWER(
                            COALESCE(c.name, '') || ' ' ||
                            COALESCE(c.competition_code, '') || ' ' ||
                            COALESCE(c.sub_type, '') || ' ' ||
                            COALESCE(c.type, '')
                        ) LIKE '%pre-season%'
                            THEN 'EXCLUDE_FRIENDLY'

                        WHEN LOWER(
                            COALESCE(c.name, '') || ' ' ||
                            COALESCE(c.competition_code, '') || ' ' ||
                            COALESCE(c.sub_type, '') || ' ' ||
                            COALESCE(c.type, '')
                        ) LIKE '%preseason%'
                            THEN 'EXCLUDE_FRIENDLY'

                        WHEN LOWER(
                            COALESCE(c.name, '') || ' ' ||
                            COALESCE(c.competition_code, '') || ' ' ||
                            COALESCE(c.sub_type, '') || ' ' ||
                            COALESCE(c.type, '')
                        ) LIKE '%preparation%'
                            THEN 'EXCLUDE_FRIENDLY'

                        WHEN LOWER(
                            COALESCE(c.name, '') || ' ' ||
                            COALESCE(c.competition_code, '') || ' ' ||
                            COALESCE(c.sub_type, '') || ' ' ||
                            COALESCE(c.type, '')
                        ) LIKE '%préparation%'
                            THEN 'EXCLUDE_FRIENDLY'

                        WHEN c.competition_id IS NULL
                            THEN 'REVIEW_MISSING_COMPETITION_METADATA'

                        ELSE 'KEEP'
                    END AS audit_status

                FROM games g
                LEFT JOIN competitions c
                    ON g.competition_id = c.competition_id

                WHERE g.date IS NOT NULL
            ),

            bounds AS (
                SELECT
                    season,
                    MIN(match_date) AS season_start,
                    MAX(match_date) AS season_end
                FROM official_club_games
                WHERE audit_status = 'KEEP'
                GROUP BY season
            ),

            boundary_games AS (
                SELECT
                    g.*,
                    CASE
                        WHEN g.match_date = b.season_start
                            THEN 'SEASON_START'
                        WHEN g.match_date = b.season_end
                            THEN 'SEASON_END'
                    END AS boundary_type
                FROM official_club_games g
                INNER JOIN bounds b
                    ON g.season = b.season
                    AND (
                        g.match_date = b.season_start
                        OR g.match_date = b.season_end
                    )
                WHERE g.audit_status = 'KEEP'
            )

            SELECT
                season,
                boundary_type,
                competition_id,
                competition_code,
                competition_name,
                MIN(match_date) AS boundary_date,
                COUNT(*) AS games_on_boundary

            FROM boundary_games

            GROUP BY
                season,
                boundary_type,
                competition_id,
                competition_code,
                competition_name

            ORDER BY
                season,
                boundary_type,
                boundary_date
            """
        ).df()

        self._print_dataframe(df, max_rows=500)

    # ------------------------------------------------------------------
    # 8. COMPETITIONS SANS METADONNEES
    # ------------------------------------------------------------------

    def audit_missing_competition_metadata(self) -> None:
        con = self._require_connection()

        self._print_title(
            "7. COMPETITIONS PRESENTES DANS games MAIS ABSENTES DE competitions"
        )

        df = con.execute(
            """
            SELECT
                g.competition_id,
                g.competition_type,
                COUNT(*) AS games_count,
                COUNT(DISTINCT g.season) AS seasons_count,
                MIN(g.date) AS first_date,
                MAX(g.date) AS last_date,
                MIN(g.season) AS first_season,
                MAX(g.season) AS last_season
            FROM games g
            LEFT JOIN competitions c
                ON g.competition_id = c.competition_id
            WHERE c.competition_id IS NULL
            GROUP BY
                g.competition_id,
                g.competition_type
            ORDER BY games_count DESC
            """
        ).df()

        self._print_dataframe(df, max_rows=500)

    # ------------------------------------------------------------------
    # 9. NATIONAL TEAM EXCLUSION
    # ------------------------------------------------------------------

    def audit_national_team_games(self) -> None:
        con = self._require_connection()

        self._print_title(
            "8. MATCHS DE SELECTION NATIONALE EXCLUS DU PERIMETRE"
        )

        df = con.execute(
            f"""
            SELECT
                season,
                competition_id,
                competition_type,
                COUNT(*) AS games_count,
                MIN(date) AS first_date,
                MAX(date) AS last_date
            FROM games
            WHERE competition_type = '{NATIONAL_TEAM_COMPETITION}'
            GROUP BY
                season,
                competition_id,
                competition_type
            ORDER BY
                season,
                first_date
            """
        ).df()

        self._print_dataframe(df, max_rows=500)

    # ------------------------------------------------------------------
    # 10. COMPETITIONS AMICALES / PREPARATION DETECTEES
    # ------------------------------------------------------------------

    def audit_friendly_competitions(self) -> None:
        con = self._require_connection()

        self._print_title(
            "9. COMPETITIONS IDENTIFIEES COMME AMICALES / PREPARATION"
        )

        df = con.execute(
            """
            SELECT
                g.competition_id,
                g.competition_type,
                c.competition_code,
                c.name AS competition_name,
                c.sub_type,
                c.type,
                COUNT(*) AS games_count,
                COUNT(DISTINCT g.season) AS seasons_count,
                MIN(g.date) AS first_date,
                MAX(g.date) AS last_date
            FROM games g
            LEFT JOIN competitions c
                ON g.competition_id = c.competition_id

            WHERE
                LOWER(
                    COALESCE(c.name, '') || ' ' ||
                    COALESCE(c.competition_code, '') || ' ' ||
                    COALESCE(c.sub_type, '') || ' ' ||
                    COALESCE(c.type, '')
                ) LIKE '%friendly%'

                OR LOWER(
                    COALESCE(c.name, '') || ' ' ||
                    COALESCE(c.competition_code, '') || ' ' ||
                    COALESCE(c.sub_type, '') || ' ' ||
                    COALESCE(c.type, '')
                ) LIKE '%amical%'

                OR LOWER(
                    COALESCE(c.name, '') || ' ' ||
                    COALESCE(c.competition_code, '') || ' ' ||
                    COALESCE(c.sub_type, '') || ' ' ||
                    COALESCE(c.type, '')
                ) LIKE '%pre-season%'

                OR LOWER(
                    COALESCE(c.name, '') || ' ' ||
                    COALESCE(c.competition_code, '') || ' ' ||
                    COALESCE(c.sub_type, '') || ' ' ||
                    COALESCE(c.type, '')
                ) LIKE '%preseason%'

                OR LOWER(
                    COALESCE(c.name, '') || ' ' ||
                    COALESCE(c.competition_code, '') || ' ' ||
                    COALESCE(c.sub_type, '') || ' ' ||
                    COALESCE(c.type, '')
                ) LIKE '%preparation%'

                OR LOWER(
                    COALESCE(c.name, '') || ' ' ||
                    COALESCE(c.competition_code, '') || ' ' ||
                    COALESCE(c.sub_type, '') || ' ' ||
                    COALESCE(c.type, '')
                ) LIKE '%préparation%'

            GROUP BY
                g.competition_id,
                g.competition_type,
                c.competition_code,
                c.name,
                c.sub_type,
                c.type

            ORDER BY games_count DESC
            """
        ).df()

        self._print_dataframe(df, max_rows=500)

    # ------------------------------------------------------------------
    # 11. CONTROLE DES SAISONS SUSPECTES
    # ------------------------------------------------------------------

    def audit_suspicious_seasons(self) -> None:
        self._print_title(
            "10. CONTROLE DES SAISONS AUX BORNES POTENTIELLEMENT ANORMALES"
        )

        bounds = self.calculate_season_bounds()

        if bounds.empty:
            print("Aucune saison détectée.")
            return

        suspicious = bounds[
            (bounds["season_duration_days"] > 400)
            | (bounds["season_duration_days"] < 200)
        ].copy()

        if suspicious.empty:
            print(
                "Aucune saison ne dépasse les seuils d'alerte "
                "(< 200 jours ou > 400 jours)."
            )
            return

        print(
            "ATTENTION : ces saisons sont signalées pour REVUE.\n"
            "Une durée > 400 jours n'implique pas automatiquement que "
            "la borne est fausse : elle peut révéler une compétition "
            "officielle prolongée, un rattachement de saison inhabituel "
            "ou une anomalie du dataset."
        )

        self._print_dataframe(suspicious)

    # ------------------------------------------------------------------
    # 12. AUDIT DETAILLE DES LONGUES EXTENSIONS
    # ------------------------------------------------------------------

    def audit_season_long_tails(self) -> None:
        con = self._require_connection()

        self._print_title(
            "11. COMPETITIONS QUI PROLONGENT FORTEMENT UNE SAISON"
        )

        df = con.execute(
            f"""
            WITH official_club_games AS (
                SELECT
                    g.game_id,
                    g.season,
                    CAST(g.date AS DATE) AS match_date,
                    g.competition_id,
                    g.competition_type,
                    c.competition_code,
                    c.name AS competition_name,
                    c.sub_type,
                    c.type,

                    CASE
                        WHEN g.competition_type = '{NATIONAL_TEAM_COMPETITION}'
                            THEN 'EXCLUDE_NATIONAL_TEAM'

                        WHEN LOWER(
                            COALESCE(c.name, '') || ' ' ||
                            COALESCE(c.competition_code, '') || ' ' ||
                            COALESCE(c.sub_type, '') || ' ' ||
                            COALESCE(c.type, '')
                        ) LIKE '%friendly%'
                            THEN 'EXCLUDE_FRIENDLY'

                        WHEN LOWER(
                            COALESCE(c.name, '') || ' ' ||
                            COALESCE(c.competition_code, '') || ' ' ||
                            COALESCE(c.sub_type, '') || ' ' ||
                            COALESCE(c.type, '')
                        ) LIKE '%amical%'
                            THEN 'EXCLUDE_FRIENDLY'

                        WHEN LOWER(
                            COALESCE(c.name, '') || ' ' ||
                            COALESCE(c.competition_code, '') || ' ' ||
                            COALESCE(c.sub_type, '') || ' ' ||
                            COALESCE(c.type, '')
                        ) LIKE '%pre-season%'
                            THEN 'EXCLUDE_FRIENDLY'

                        WHEN LOWER(
                            COALESCE(c.name, '') || ' ' ||
                            COALESCE(c.competition_code, '') || ' ' ||
                            COALESCE(c.sub_type, '') || ' ' ||
                            COALESCE(c.type, '')
                        ) LIKE '%preseason%'
                            THEN 'EXCLUDE_FRIENDLY'

                        WHEN LOWER(
                            COALESCE(c.name, '') || ' ' ||
                            COALESCE(c.competition_code, '') || ' ' ||
                            COALESCE(c.sub_type, '') || ' ' ||
                            COALESCE(c.type, '')
                        ) LIKE '%preparation%'
                            THEN 'EXCLUDE_FRIENDLY'

                        WHEN LOWER(
                            COALESCE(c.name, '') || ' ' ||
                            COALESCE(c.competition_code, '') || ' ' ||
                            COALESCE(c.sub_type, '') || ' ' ||
                            COALESCE(c.type, '')
                        ) LIKE '%préparation%'
                            THEN 'EXCLUDE_FRIENDLY'

                        WHEN c.competition_id IS NULL
                            THEN 'REVIEW_MISSING_COMPETITION_METADATA'

                        ELSE 'KEEP'
                    END AS audit_status

                FROM games g
                LEFT JOIN competitions c
                    ON g.competition_id = c.competition_id

                WHERE g.date IS NOT NULL
            ),

            bounds AS (
                SELECT
                    season,
                    MIN(match_date) AS season_start,
                    MAX(match_date) AS season_end
                FROM official_club_games
                WHERE audit_status = 'KEEP'
                GROUP BY season
            ),

            competition_bounds AS (
                SELECT
                    season,
                    competition_id,
                    competition_code,
                    competition_name,
                    MIN(match_date) AS competition_start,
                    MAX(match_date) AS competition_end,
                    COUNT(DISTINCT game_id) AS games_count

                FROM official_club_games
                WHERE audit_status = 'KEEP'

                GROUP BY
                    season,
                    competition_id,
                    competition_code,
                    competition_name
            )

            SELECT
                cb.season,
                cb.competition_id,
                cb.competition_code,
                cb.competition_name,
                cb.competition_start,
                cb.competition_end,
                cb.games_count,

                b.season_start,
                b.season_end,

                DATE_DIFF(
                    'day',
                    b.season_start,
                    cb.competition_start
                ) AS days_after_season_start,

                DATE_DIFF(
                    'day',
                    cb.competition_end,
                    b.season_end
                ) AS days_before_season_end

            FROM competition_bounds cb

            INNER JOIN bounds b
                ON cb.season = b.season

            WHERE
                DATE_DIFF(
                    'day',
                    b.season_start,
                    cb.competition_start
                ) > 300

                OR DATE_DIFF(
                    'day',
                    cb.competition_end,
                    b.season_end
                ) > 300

            ORDER BY
                cb.season,
                cb.competition_start
            """
        ).df()

        self._print_dataframe(df, max_rows=1000)

    # ------------------------------------------------------------------
    # 13. CONTROLE DES MATCHS AUTOUR DES BORNES
    # ------------------------------------------------------------------

    def audit_games_around_boundaries(self) -> None:
        con = self._require_connection()

        self._print_title(
            "12. MATCHS AUTOUR DES BORNES DES SAISONS"
        )

        df = con.execute(
            f"""
            WITH official_club_games AS (
                SELECT
                    g.game_id,
                    g.season,
                    CAST(g.date AS DATE) AS match_date,
                    g.competition_id,
                    g.competition_type,
                    c.competition_code,
                    c.name AS competition_name,

                    CASE
                        WHEN g.competition_type = '{NATIONAL_TEAM_COMPETITION}'
                            THEN 'EXCLUDE_NATIONAL_TEAM'

                        WHEN LOWER(
                            COALESCE(c.name, '') || ' ' ||
                            COALESCE(c.competition_code, '') || ' ' ||
                            COALESCE(c.sub_type, '') || ' ' ||
                            COALESCE(c.type, '')
                        ) LIKE '%friendly%'
                            THEN 'EXCLUDE_FRIENDLY'

                        WHEN LOWER(
                            COALESCE(c.name, '') || ' ' ||
                            COALESCE(c.competition_code, '') || ' ' ||
                            COALESCE(c.sub_type, '') || ' ' ||
                            COALESCE(c.type, '')
                        ) LIKE '%amical%'
                            THEN 'EXCLUDE_FRIENDLY'

                        WHEN LOWER(
                            COALESCE(c.name, '') || ' ' ||
                            COALESCE(c.competition_code, '') || ' ' ||
                            COALESCE(c.sub_type, '') || ' ' ||
                            COALESCE(c.type, '')
                        ) LIKE '%pre-season%'
                            THEN 'EXCLUDE_FRIENDLY'

                        WHEN LOWER(
                            COALESCE(c.name, '') || ' ' ||
                            COALESCE(c.competition_code, '') || ' ' ||
                            COALESCE(c.sub_type, '') || ' ' ||
                            COALESCE(c.type, '')
                        ) LIKE '%preseason%'
                            THEN 'EXCLUDE_FRIENDLY'

                        WHEN LOWER(
                            COALESCE(c.name, '') || ' ' ||
                            COALESCE(c.competition_code, '') || ' ' ||
                            COALESCE(c.sub_type, '') || ' ' ||
                            COALESCE(c.type, '')
                        ) LIKE '%preparation%'
                            THEN 'EXCLUDE_FRIENDLY'

                        WHEN LOWER(
                            COALESCE(c.name, '') || ' ' ||
                            COALESCE(c.competition_code, '') || ' ' ||
                            COALESCE(c.sub_type, '') || ' ' ||
                            COALESCE(c.type, '')
                        ) LIKE '%préparation%'
                            THEN 'EXCLUDE_FRIENDLY'

                        WHEN c.competition_id IS NULL
                            THEN 'REVIEW_MISSING_COMPETITION_METADATA'

                        ELSE 'KEEP'
                    END AS audit_status

                FROM games g
                LEFT JOIN competitions c
                    ON g.competition_id = c.competition_id

                WHERE g.date IS NOT NULL
            ),

            bounds AS (
                SELECT
                    season,
                    MIN(match_date) AS season_start,
                    MAX(match_date) AS season_end
                FROM official_club_games
                WHERE audit_status = 'KEEP'
                GROUP BY season
            )

            SELECT
                g.season,
                g.match_date,
                g.game_id,
                g.competition_id,
                g.competition_code,
                g.competition_name,
                g.competition_type,
                g.audit_status,

                b.season_start,
                b.season_end,

                CASE
                    WHEN g.match_date < b.season_start
                        THEN 'BEFORE_SEASON_START'

                    WHEN g.match_date > b.season_end
                        THEN 'AFTER_SEASON_END'

                    WHEN g.match_date = b.season_start
                        THEN 'SEASON_START'

                    WHEN g.match_date = b.season_end
                        THEN 'SEASON_END'

                    ELSE 'INSIDE'
                END AS position_relative_to_bounds

            FROM official_club_games g

            INNER JOIN bounds b
                ON g.season = b.season

            WHERE
                g.match_date BETWEEN
                    b.season_start - INTERVAL 15 DAY
                    AND
                    b.season_end + INTERVAL 15 DAY

            ORDER BY
                g.season,
                g.match_date
            """
        ).df()

        self._print_dataframe(df, max_rows=2000)

    # ------------------------------------------------------------------
    # 14. EXPORT DES BORNES
    # ------------------------------------------------------------------

    def export_season_bounds(self, output_path: Path) -> None:
        """
        Exporte uniquement les bornes calculées.

        Ce fichier pourra ensuite devenir la source de vérité
        consommée par RealPerformanceLoader.

        Aucune modification de la base DuckDB.
        """

        bounds = self.calculate_season_bounds()

        output_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        bounds.to_csv(
            output_path,
            index=False,
        )

        print()
        print(f"Bornes exportées vers : {output_path}")

    # ------------------------------------------------------------------
    # RUN
    # ------------------------------------------------------------------

    def run(self) -> None:
        self.connect()

        try:
            self.audit_schema()
            self.audit_competition_types()
            self.audit_official_club_scope()
            self.print_season_bounds()
            self.audit_boundary_matches()
            self.audit_boundary_competitions()
            self.audit_missing_competition_metadata()
            self.audit_national_team_games()
            self.audit_friendly_competitions()
            self.audit_suspicious_seasons()
            self.audit_season_long_tails()
            self.audit_games_around_boundaries()

        finally:
            self.close()


def main() -> None:
    audit = RawSeasonCalendarAudit(
    database_path=DATABASE_PATH,
    )
    audit.run()


if __name__ == "__main__":
    main()
