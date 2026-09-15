from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import duckdb
import pandas as pd

@dataclass(frozen=True)
class AuditConfig:
    database_path: Path = Path(
    "data/historical/transfermarkt-datasets.duckdb"
    )


    output_bounds_path: Path = Path(
        "data/audits/raw_season_calendar_bounds.csv"
    )

    output_review_path: Path = Path(
        "data/audits/raw_season_calendar_review.csv"
    )

    national_team_competition_type: str = "national_team_competition"

    # Une saison officielle de football peut commencer très tôt
    # avec les qualifications européennes.
    # Cette limite sert uniquement à détecter des affectations
    # manifestement anormales du champ games.season.
    plausible_start_month: int = 5

   # Seuil utilisé uniquement comme indicateur d'audit temporel.
    #
    # IMPORTANT :
    # Une durée supérieure à ce seuil ne transforme PAS automatiquement
    # une saison en REVIEW.
    #
    # Certaines saisons peuvent être exceptionnellement longues en raison
    # de perturbations historiques du calendrier : pandémie, interruption
    # puis reprise des compétitions, décalage des compétitions européennes
    # ou contexte géopolitique.
    #
    # Le seuil sert uniquement à identifier les saisons qui méritent une
    # lecture contextuelle dans la section d'audit temporel.
    suspicious_duration_days: int = 450

    # Une compétition sans métadonnées peut néanmoins être un
    # match officiel entre deux clubs.
    require_two_clubs_for_structural_keep: bool = True


class RawSeasonCalendarAudit:
    """
    Audit du calendrier réel des saisons à partir de la table RAW games.

    Business rules
    --------------
    1. Les matchs internationaux / équipes nationales sont exclus.
    2. Les matchs amicaux / préparation sont exclus.
    3. Un match officiel de qualification européenne peut être
    le premier match de la saison, même si le championnat
    national n'a pas encore commencé.
    4. Les compétitions officielles entre clubs sont conservées.
    5. Les compétitions dont les métadonnées sont absentes ne sont
    pas automatiquement exclues : elles peuvent être KEEP si
    la structure du match confirme un match entre deux clubs.
    6. Les affectations manifestement incohérentes de games.season
    restent REVIEW.
    7. Les bornes candidates sont calculées uniquement à partir
    des matchs KEEP.
    8. Les REVIEW sont ensuite testés pour déterminer s'ils peuvent
    déplacer la borne de début ou de fin.
    """

    FRIENDLY_KEYWORDS = (
        "friendly",
        "friendlies",
        "friendly match",
        "club friendly",
        "international friendly",
        "amical",
        "match amical",
        "amicaux",
        "amicale",
        "pre-season",
        "preseason",
        "pre season",
        "preparation",
        "pré-saison",
        "preparation match",
        "test match",
        "training match",
        "practice match",
    )

    NATIONAL_COMPETITION_CODES = (
        "world-cup",
        "uefa-euro",
        "euro",
        "africa-cup-of-nations",
        "afcon",
        "afc-asian-cup",
        "asian-cup",
        "copa-america",
        "concacaf-gold-cup",
        "concacaf-nations-league",
        "uefa-nations-league",
        "fifa-confederations-cup",
        "olympic-football",
        "olympics",
    )

    def __init__(self, config: AuditConfig):
        self.config = config
        self.connection: Optional[duckdb.DuckDBPyConnection] = None
        self.raw_games: Optional[pd.DataFrame] = None
        self.classified_games: Optional[pd.DataFrame] = None

    # ------------------------------------------------------------------
    # Connection
    # ------------------------------------------------------------------

    def connect(self) -> None:
        if self.connection is not None:
            return

        self.connection = duckdb.connect(
            database=str(self.config.database_path),
            read_only=True,
        )

    def close(self) -> None:
        if self.connection is not None:
            self.connection.close()
            self.connection = None

    def _require_connection(self) -> duckdb.DuckDBPyConnection:
        if self.connection is None:
            raise RuntimeError("DuckDB connection is not open.")
        return self.connection

    # ------------------------------------------------------------------
    # Display helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _print_title(title: str) -> None:
        print()
        print("=" * 90)
        print(title)
        print("=" * 90)

    @staticmethod
    def _print_dataframe(
        dataframe: pd.DataFrame,
        max_rows: int = 50,
    ) -> None:
        if dataframe.empty:
            print("(aucune ligne)")
            return

        print(dataframe.head(max_rows).to_string(index=False))

        if len(dataframe) > max_rows:
            print()
            print(
                f"... {len(dataframe) - max_rows} lignes supplémentaires "
                f"non affichées."
            )

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def audit_schema(self) -> None:
        connection = self._require_connection()

        self._print_title("1. SCHEMA RAW GAMES")

        tables = connection.execute(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'main'
            ORDER BY table_name
            """
        ).fetchdf()

        print("Tables disponibles :")
        self._print_dataframe(tables)

        columns = connection.execute(
            """
            SELECT
                column_name,
                data_type
            FROM information_schema.columns
            WHERE table_schema = 'main'
            AND table_name = 'games'
            ORDER BY ordinal_position
            """
        ).fetchdf()

        print()
        print("Colonnes de games :")
        self._print_dataframe(columns)

    # ------------------------------------------------------------------
    # Competition types
    # ------------------------------------------------------------------

    def audit_competition_types(self) -> pd.DataFrame:
        connection = self._require_connection()

        self._print_title("2. COMPETITION TYPES")

        dataframe = connection.execute(
            """
            SELECT
                competition_type,
                COUNT(*) AS games
            FROM games
            GROUP BY competition_type
            ORDER BY games DESC
            """
        ).fetchdf()

        self._print_dataframe(dataframe)

        return dataframe

    # ------------------------------------------------------------------
    # Raw games
    # ------------------------------------------------------------------

    def load_raw_games(self) -> pd.DataFrame:
        connection = self._require_connection()

        query = """
            SELECT
                g.game_id,
                g.competition_id,
                g.season,
                g.round,
                g.date,
                g.home_club_id,
                g.away_club_id,
                g.home_club_goals,
                g.away_club_goals,
                g.competition_type,

                c.competition_code,
                c.name AS competition_name,
                c.sub_type AS competition_sub_type,
                c.type AS competition_metadata_type,
                c.country_name,
                c.confederation

            FROM games AS g

            LEFT JOIN competitions AS c
                ON g.competition_id = c.competition_id

            WHERE g.date IS NOT NULL

            ORDER BY
                g.season,
                g.date,
                g.game_id
        """

        dataframe = connection.execute(query).fetchdf()

        dataframe["date"] = pd.to_datetime(
            dataframe["date"],
            errors="coerce",
        )

        self.raw_games = dataframe

        return dataframe

    # ------------------------------------------------------------------
    # Text normalization
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_text(value) -> str:
        if value is None:
            return ""

        if pd.isna(value):
            return ""

        return (
            str(value)
            .strip()
            .lower()
            .replace("_", " ")
            .replace("-", " ")
        )

    def _competition_metadata_text(
        self,
        row: pd.Series,
    ) -> str:
        fields = [
            row.get("competition_code"),
            row.get("competition_name"),
            row.get("competition_sub_type"),
            row.get("competition_metadata_type"),
            row.get("round"),
        ]

        return " ".join(
            self._normalize_text(value)
            for value in fields
            if self._normalize_text(value)
        )

    def _is_friendly(self, row: pd.Series) -> bool:
        text = self._competition_metadata_text(row)

        return any(
            keyword in text
            for keyword in self.FRIENDLY_KEYWORDS
        )

    def _is_national_team(self, row: pd.Series) -> bool:
        """
        Détermine si le match appartient à une compétition
        de sélection nationale.

        Règles :
        - national_team_competition => sélection nationale
        - certains codes/noms explicitement nationaux => sélection nationale
        - international_cup seul ne signifie PAS sélection nationale :
        les compétitions européennes de clubs restent des compétitions de clubs.
        """

        competition_type = self._normalize_text(
            row.get("competition_type")
        )

        competition_code = self._normalize_text(
            row.get("competition_code")
        )

        competition_name = self._normalize_text(
            row.get("competition_name")
        )

        # 1. Type Transfermarkt explicite
        if competition_type == self._normalize_text(
            self.config.national_team_competition_type
        ):
            return True

        # 2. Codes/noms explicitement nationaux.
        # NATIONAL_COMPETITION_CODES est normalisé au moment
        # de la comparaison car _normalize_text() transforme
        # les "-" et "_" en espaces.
        national_competition_codes = {
            self._normalize_text(code)
            for code in self.NATIONAL_COMPETITION_CODES
        }

        if competition_code in national_competition_codes:
            return True

        if competition_name in national_competition_codes:
            return True

        return False
    # ------------------------------------------------------------------
    # Structural classification
    # ------------------------------------------------------------------

    def _has_two_clubs(self, row: pd.Series) -> bool:
        home_club_id = row.get("home_club_id")
        away_club_id = row.get("away_club_id")

        if pd.isna(home_club_id) or pd.isna(away_club_id):
            return False

        return True

    def _has_competition_metadata(self, row: pd.Series) -> bool:
        fields = [
            row.get("competition_id"),
            row.get("competition_code"),
            row.get("competition_name"),
            row.get("competition_metadata_type"),
        ]

        return any(
            not pd.isna(value) and str(value).strip() != ""
            for value in fields
        )

    def _looks_like_european_qualification(
        self,
        row: pd.Series,
    ) -> bool:
        text = self._competition_metadata_text(row)

        qualification_keywords = (
            "qualifying",
            "qualification",
            "qualifier",
            "qualification round",
            "qualifying round",
            "champions league qualifying",
            "europa league qualifying",
            "conference league qualifying",
            "uefa qualifying",
        )

        european_keywords = (
            "uefa",
            "champions league",
            "europa league",
            "conference league",
            "ucl",
            "uel",
            "uecl",
        )

        return (
            any(keyword in text for keyword in qualification_keywords)
            and any(keyword in text for keyword in european_keywords)
        )

    def _season_start_is_structurally_plausible(
        self,
        row: pd.Series,
    ) -> bool:
        """
        Ne considère pas qu'un match européen de qualification avant
        le championnat national est anormal.

        La vérification cherche uniquement les affectations clairement
        aberrantes, par exemple un match très ancien placé dans une
        saison récente.
        """

        season = row.get("season")
        date = row.get("date")

        if pd.isna(season) or pd.isna(date):
            return False

        try:
            season_int = int(season)
        except (TypeError, ValueError):
            return False

        date = pd.Timestamp(date)

        # Cas standard : saison située autour de l'année de début.
        #
        # Une qualification européenne peut commencer en juin/juillet.
        # On ne rejette donc PAS les qualifications européennes
        # simplement parce qu'elles précèdent le championnat.
        if date.year in {season_int, season_int + 1}:
            return True

        # Cas particulier : les compétitions exceptionnellement
        # décalées peuvent se prolonger dans l'année suivante.
        #
        # On conserve ici une tolérance jusqu'à environ 15 mois.
        if date.year == season_int + 2:
            return True

        return False

    def classify_row(self, row: pd.Series) -> tuple[str, str]:
        """
        Retourne :
            STATUS
            REASON
        """

        # --------------------------------------------------------------
        # 1. NATIONAL TEAM
        # --------------------------------------------------------------

        if self._is_national_team(row):
            return (
                "EXCLUDE_NATIONAL",
                "NATIONAL_TEAM_MATCH",
            )

        # --------------------------------------------------------------
        # 2. FRIENDLY
        # --------------------------------------------------------------

        if self._is_friendly(row):
            return (
                "EXCLUDE_FRIENDLY",
                "FRIENDLY_OR_PREPARATION_MATCH",
            )

        # --------------------------------------------------------------
        # 3. MISSING METADATA
        # --------------------------------------------------------------

        has_two_clubs = self._has_two_clubs(row)
        has_metadata = self._has_competition_metadata(row)

        if not has_metadata:

            if (
                self.config.require_two_clubs_for_structural_keep
                and not has_two_clubs
            ):
                return (
                    "REVIEW",
                    "UNKNOWN_COMPETITION_NO_TWO_CLUB_STRUCTURE",
                )

            # Deux clubs sont présents.
            #
            # On ne rejette pas automatiquement :
            # il peut s'agir d'une compétition officielle dont les
            # métadonnées ne sont pas disponibles dans Transfermarkt.
            #
            # On vérifie cependant que l'affectation à la saison n'est
            # pas manifestement aberrante.
            if not self._season_start_is_structurally_plausible(row):
                return (
                    "REVIEW",
                    "UNKNOWN_COMPETITION_SUSPICIOUS_SEASON_ASSIGNMENT",
                )

            return (
                "KEEP",
                "OFFICIAL_CLUB_STRUCTURAL",
            )

        # --------------------------------------------------------------
        # 4. KNOWN OFFICIAL CLUB MATCH
        # --------------------------------------------------------------

        if not has_two_clubs:
            return (
                "REVIEW",
                "OFFICIAL_COMPETITION_WITHOUT_TWO_CLUB_STRUCTURE",
            )

        if not self._season_start_is_structurally_plausible(row):
            return (
                "REVIEW",
                "SUSPICIOUS_SEASON_ASSIGNMENT",
            )

        # Les qualifications européennes sont explicitement KEEP.
        if self._looks_like_european_qualification(row):
            return (
                "KEEP",
                "OFFICIAL_EUROPEAN_QUALIFICATION",
            )

        return (
            "KEEP",
            "OFFICIAL_CLUB_COMPETITION",
        )

    # ------------------------------------------------------------------
    # Classification
    # ------------------------------------------------------------------

    def classify_games(
        self,
        dataframe: Optional[pd.DataFrame] = None,
    ) -> pd.DataFrame:

        if dataframe is None:
            if self.raw_games is None:
                dataframe = self.load_raw_games()
            else:
                dataframe = self.raw_games

        classified = dataframe.copy()

        classifications = classified.apply(
            self.classify_row,
            axis=1,
            result_type="expand",
        )

        classifications.columns = [
            "status",
            "classification_reason",
        ]

        classified = pd.concat(
            [
                classified,
                classifications,
            ],
            axis=1,
        )

        classified["season"] = pd.to_numeric(
            classified["season"],
            errors="coerce",
        )

        self.classified_games = classified

        return classified

    # ------------------------------------------------------------------
    # Classification audit
    # ------------------------------------------------------------------

    def audit_classification(
        self,
        dataframe: Optional[pd.DataFrame] = None,
    ) -> pd.DataFrame:

        if dataframe is None:
            dataframe = self.classified_games

        if dataframe is None:
            raise RuntimeError(
                "Games have not been loaded/classified."
            )

        self._print_title("3. CLASSIFICATION DES MATCHS")

        summary = (
            dataframe
            .groupby(
                ["status", "classification_reason"],
                dropna=False,
            )
            .agg(
                games=("game_id", "count"),
                seasons=("season", "nunique"),
                first_date=("date", "min"),
                last_date=("date", "max"),
            )
            .reset_index()
            .sort_values(
                ["status", "games"],
                ascending=[True, False],
            )
        )

        self._print_dataframe(summary, max_rows=100)

        return summary

    # ------------------------------------------------------------------
    # Review extraction
    # ------------------------------------------------------------------

    def extract_review_games(
        self,
        dataframe: Optional[pd.DataFrame] = None,
    ) -> pd.DataFrame:

        if dataframe is None:
            dataframe = self.classified_games

        if dataframe is None:
            raise RuntimeError(
                "Games have not been loaded/classified."
            )

        review = dataframe.loc[
            dataframe["status"] == "REVIEW"
        ].copy()

        review = review.sort_values(
            ["season", "date", "game_id"]
        )

        return review

    def print_review_summary(
        self,
        review: pd.DataFrame,
    ) -> None:

        self._print_title("4. REVIEW À VALIDER AVANT INTÉGRATION")

        if review.empty:
            print("Aucun match REVIEW.")
            return

        summary = (
            review
            .groupby(
                ["season", "classification_reason"],
                dropna=False,
            )
            .agg(
                games=("game_id", "count"),
                first_date=("date", "min"),
                last_date=("date", "max"),
                competitions=("competition_id", "nunique"),
            )
            .reset_index()
            .sort_values(
                ["season", "games"],
                ascending=[True, False],
            )
        )

        self._print_dataframe(summary, max_rows=200)

        print()
        print("Détail des REVIEW :")

        columns = [
            "game_id",
            "season",
            "date",
            "round",
            "competition_id",
            "competition_code",
            "competition_name",
            "competition_sub_type",
            "competition_metadata_type",
            "competition_type",
            "home_club_id",
            "away_club_id",
            "status",
            "classification_reason",
        ]

        available_columns = [
            column
            for column in columns
            if column in review.columns
        ]

        self._print_dataframe(
            review[available_columns],
            max_rows=200,
        )

    # ------------------------------------------------------------------
    # Candidate bounds
    # ------------------------------------------------------------------

    def calculate_candidate_bounds(
        self,
        dataframe: Optional[pd.DataFrame] = None,
    ) -> pd.DataFrame:

        if dataframe is None:
            dataframe = self.classified_games

        if dataframe is None:
            raise RuntimeError(
                "Games have not been loaded/classified."
            )

        keep = dataframe.loc[
            dataframe["status"] == "KEEP"
        ].copy()

        if keep.empty:
            return pd.DataFrame(
                columns=[
                    "season",
                    "season_start",
                    "season_end",
                    "duration_days",
                    "games",
                    "competitions",
                    "first_competition",
                    "last_competition",
                ]
            )

        bounds = (
            keep
            .groupby("season")
            .agg(
                season_start=("date", "min"),
                season_end=("date", "max"),
                games=("game_id", "count"),
                competitions=("competition_id", "nunique"),
            )
            .reset_index()
        )

        bounds["duration_days"] = (
            bounds["season_end"] - bounds["season_start"]
        ).dt.days

        first_rows = (
            keep
            .sort_values(
                ["season", "date", "game_id"]
            )
            .groupby("season", as_index=False)
            .first()
        )

        last_rows = (
            keep
            .sort_values(
                ["season", "date", "game_id"]
            )
            .groupby("season", as_index=False)
            .last()
        )

        first_competitions = first_rows[
            [
                "season",
                "competition_code",
                "competition_name",
                "competition_type",
                "classification_reason",
            ]
        ].rename(
            columns={
                "competition_code": "first_competition_code",
                "competition_name": "first_competition_name",
                "competition_type": "first_competition_type",
                "classification_reason": "first_classification_reason",
            }
        )

        last_competitions = last_rows[
            [
                "season",
                "competition_code",
                "competition_name",
                "competition_type",
                "classification_reason",
            ]
        ].rename(
            columns={
                "competition_code": "last_competition_code",
                "competition_name": "last_competition_name",
                "competition_type": "last_competition_type",
                "classification_reason": "last_classification_reason",
            }
        )

        bounds = bounds.merge(
            first_competitions,
            on="season",
            how="left",
        )

        bounds = bounds.merge(
            last_competitions,
            on="season",
            how="left",
        )

        return bounds.sort_values("season").reset_index(drop=True)

    def print_candidate_bounds(
        self,
        bounds: pd.DataFrame,
    ) -> None:

        self._print_title("5. BORNES CANDIDATES — MATCHS KEEP UNIQUEMENT")

        if bounds.empty:
            print("Aucune borne calculée.")
            return

        columns = [
            "season",
            "season_start",
            "season_end",
            "duration_days",
            "games",
            "competitions",
            "first_competition_code",
            "first_competition_name",
            "first_classification_reason",
            "last_competition_code",
            "last_competition_name",
            "last_classification_reason",
        ]

        available_columns = [
            column
            for column in columns
            if column in bounds.columns
        ]

        self._print_dataframe(
            bounds[available_columns],
            max_rows=100,
        )

    # ------------------------------------------------------------------
    # Review impact on bounds
    # ------------------------------------------------------------------

    def calculate_review_impact(
        self,
        classified: Optional[pd.DataFrame] = None,
        bounds: Optional[pd.DataFrame] = None,
    ) -> pd.DataFrame:

        if classified is None:
            classified = self.classified_games

        if classified is None:
            raise RuntimeError(
                "Games have not been loaded/classified."
            )

        if bounds is None:
            bounds = self.calculate_candidate_bounds(classified)

        review = self.extract_review_games(classified)

        if review.empty:
            return pd.DataFrame(
                columns=[
                    "season",
                    "review_status",
                    "review_reason",
                    "review_games",
                    "first_review_date",
                    "last_review_date",
                    "candidate_start",
                    "candidate_end",
                    "impact",
                ]
            )

        rows = []

        bounds_by_season = {
            row["season"]: row
            for _, row in bounds.iterrows()
        }

        for (
            season,
            reason,
        ), group in review.groupby(
            ["season", "classification_reason"],
            dropna=False,
        ):

            first_review_date = group["date"].min()
            last_review_date = group["date"].max()

            candidate = bounds_by_season.get(season)

            if candidate is None:
                impact = "NO_KEEP_FOR_SEASON"
                candidate_start = pd.NaT
                candidate_end = pd.NaT

            else:
                candidate_start = candidate["season_start"]
                candidate_end = candidate["season_end"]

                moves_start = (
                    pd.notna(first_review_date)
                    and first_review_date < candidate_start
                )

                moves_end = (
                    pd.notna(last_review_date)
                    and last_review_date > candidate_end
                )

                if moves_start and moves_end:
                    impact = "COULD_MOVE_START_AND_END"

                elif moves_start:
                    impact = "COULD_MOVE_START_EARLIER"

                elif moves_end:
                    impact = "COULD_MOVE_END_LATER"

                else:
                    impact = "INSIDE_CURRENT_BOUNDS"

            rows.append(
                {
                    "season": season,
                    "review_status": "REVIEW",
                    "review_reason": reason,
                    "review_games": len(group),
                    "first_review_date": first_review_date,
                    "last_review_date": last_review_date,
                    "candidate_start": candidate_start,
                    "candidate_end": candidate_end,
                    "impact": impact,
                }
            )

        return (
            pd.DataFrame(rows)
            .sort_values(
                ["season", "impact", "review_games"],
                ascending=[True, True, False],
            )
            .reset_index(drop=True)
        )

    def print_review_impact(
        self,
        impact: pd.DataFrame,
    ) -> None:

        self._print_title("6. IMPACT DES REVIEW SUR LES BORNES")

        if impact.empty:
            print("Aucun REVIEW.")
            return

        self._print_dataframe(
            impact,
            max_rows=200,
        )

    # ------------------------------------------------------------------
    # Exclusions
    # ------------------------------------------------------------------

    def audit_exclusions(
        self,
        classified: Optional[pd.DataFrame] = None,
    ) -> pd.DataFrame:

        if classified is None:
            classified = self.classified_games

        if classified is None:
            raise RuntimeError(
                "Games have not been loaded/classified."
            )

        self._print_title("7. MATCHS EXCLUS")

        exclusions = (
            classified
            .loc[
                classified["status"].isin(
                    [
                        "EXCLUDE_NATIONAL",
                        "EXCLUDE_FRIENDLY",
                    ]
                )
            ]
            .groupby(
                [
                    "status",
                    "classification_reason",
                    "competition_type",
                    "competition_code",
                    "competition_name",
                ],
                dropna=False,
            )
            .agg(
                games=("game_id", "count"),
                first_date=("date", "min"),
                last_date=("date", "max"),
            )
            .reset_index()
            .sort_values(
                "games",
                ascending=False,
            )
        )

        self._print_dataframe(
            exclusions,
            max_rows=200,
        )

        return exclusions

    # ------------------------------------------------------------------
    # Temporal outliers
    # ------------------------------------------------------------------

    def audit_temporal_outliers(
        self,
        bounds: Optional[pd.DataFrame] = None,
    ) -> pd.DataFrame:

        if bounds is None:
            bounds = self.calculate_candidate_bounds()

        self._print_title(
            "8. DURÉE DES SAISONS — INDICATEUR D'AUDIT"
        )

        if bounds.empty:
            print("Aucune saison.")
            return bounds

        outliers = bounds.loc[
            bounds["duration_days"]
            > self.config.suspicious_duration_days
        ].copy()

        if outliers.empty:
            print(
                "Aucune saison ne dépasse "
                f"{self.config.suspicious_duration_days} jours."
            )
        else:
            print(
                f"Saisons dépassant "
                f"{self.config.suspicious_duration_days} jours "
                f"(indicateur d'audit, sans changement automatique de statut) :"
            )
            self._print_dataframe(
                outliers,
                max_rows=100,
            )

        return outliers
    print()
    print(
        "IMPORTANT : une durée supérieure au seuil ne constitue "
        "pas à elle seule une anomalie."
    )
    print(
        "Elle ne modifie pas le statut KEEP/REVIEW d'une saison."
    )
    print(
        "L'interprétation doit tenir compte du contexte historique "
        "et de la cohérence de l'affectation des matchs à la saison."
    )
    # ------------------------------------------------------------------
    # Boundary games
    # ------------------------------------------------------------------

    def audit_boundary_games(
        self,
        classified: Optional[pd.DataFrame] = None,
        bounds: Optional[pd.DataFrame] = None,
    ) -> pd.DataFrame:

        if classified is None:
            classified = self.classified_games

        if classified is None:
            raise RuntimeError(
                "Games have not been loaded/classified."
            )

        if bounds is None:
            bounds = self.calculate_candidate_bounds(classified)

        self._print_title("9. MATCHS AUX BORNES")

        keep = classified.loc[
            classified["status"] == "KEEP"
        ].copy()

        if keep.empty:
            print("Aucun match KEEP.")
            return pd.DataFrame()

        rows = []

        for _, bound in bounds.iterrows():

            season = bound["season"]

            season_games = keep.loc[
                keep["season"] == season
            ].copy()

            if season_games.empty:
                continue

            first = (
                season_games
                .sort_values(
                    ["date", "game_id"]
                )
                .iloc[0]
            )

            last = (
                season_games
                .sort_values(
                    ["date", "game_id"]
                )
                .iloc[-1]
            )

            rows.append(
                {
                    "season": season,
                    "first_game_id": first["game_id"],
                    "first_date": first["date"],
                    "first_competition_code": first[
                        "competition_code"
                    ],
                    "first_competition_name": first[
                        "competition_name"
                    ],
                    "first_round": first["round"],
                    "first_reason": first[
                        "classification_reason"
                    ],
                    "last_game_id": last["game_id"],
                    "last_date": last["date"],
                    "last_competition_code": last[
                        "competition_code"
                    ],
                    "last_competition_name": last[
                        "competition_name"
                    ],
                    "last_round": last["round"],
                    "last_reason": last[
                        "classification_reason"
                    ],
                }
            )

        result = pd.DataFrame(rows)

        self._print_dataframe(
            result,
            max_rows=100,
        )

        return result

    # ------------------------------------------------------------------
    # Boundary competition audit
    # ------------------------------------------------------------------

    def audit_boundary_competitions(
        self,
        classified: Optional[pd.DataFrame] = None,
        bounds: Optional[pd.DataFrame] = None,
    ) -> pd.DataFrame:

        if classified is None:
            classified = self.classified_games

        if classified is None:
            raise RuntimeError(
                "Games have not been loaded/classified."
            )

        if bounds is None:
            bounds = self.calculate_candidate_bounds(classified)

        self._print_title("10. COMPÉTITIONS AUTOUR DES BORNES")

        keep = classified.loc[
            classified["status"] == "KEEP"
        ].copy()

        rows = []

        for _, bound in bounds.iterrows():

            season = bound["season"]
            start = bound["season_start"]
            end = bound["season_end"]

            season_games = keep.loc[
                keep["season"] == season
            ].copy()

            if season_games.empty:
                continue

            first_window = season_games.loc[
                season_games["date"]
                <= start + pd.Timedelta(days=14)
            ]

            last_window = season_games.loc[
                season_games["date"]
                >= end - pd.Timedelta(days=14)
            ]

            for side, window in [
                ("START", first_window),
                ("END", last_window),
            ]:

                if window.empty:
                    continue

                competition_summary = (
                    window
                    .groupby(
                        [
                            "competition_code",
                            "competition_name",
                            "classification_reason",
                        ],
                        dropna=False,
                    )
                    .agg(
                        games=("game_id", "count"),
                        first_date=("date", "min"),
                        last_date=("date", "max"),
                    )
                    .reset_index()
                )

                competition_summary.insert(
                    0,
                    "season",
                    season,
                )

                competition_summary.insert(
                    1,
                    "boundary",
                    side,
                )

                rows.append(
                    competition_summary
                )

        if not rows:
            print("Aucune donnée.")
            return pd.DataFrame()

        result = pd.concat(
            rows,
            ignore_index=True,
        )

        self._print_dataframe(
            result,
            max_rows=200,
        )

        return result

    # ------------------------------------------------------------------
    # Suspicious season assignment details
    # ------------------------------------------------------------------

    def audit_suspicious_seasons(
        self,
        classified: Optional[pd.DataFrame] = None,
    ) -> pd.DataFrame:

        if classified is None:
            classified = self.classified_games

        if classified is None:
            raise RuntimeError(
                "Games have not been loaded/classified."
            )

        self._print_title(
            "11. AFFECTATIONS DE SAISON SUSPECTES"
        )

        suspicious = classified.loc[
            classified["classification_reason"].isin(
                [
                    "SUSPICIOUS_SEASON_ASSIGNMENT",
                    "UNKNOWN_COMPETITION_SUSPICIOUS_SEASON_ASSIGNMENT",
                ]
            )
        ].copy()

        if suspicious.empty:
            print(
                "Aucune affectation de saison suspecte "
                "selon les règles actuelles."
            )
            return suspicious

        columns = [
            "game_id",
            "season",
            "date",
            "round",
            "competition_id",
            "competition_code",
            "competition_name",
            "competition_type",
            "home_club_id",
            "away_club_id",
            "status",
            "classification_reason",
        ]

        available_columns = [
            column
            for column in columns
            if column in suspicious.columns
        ]

        self._print_dataframe(
            suspicious[available_columns],
            max_rows=300,
        )

        return suspicious

    # ------------------------------------------------------------------
    # Games around suspicious boundaries
    # ------------------------------------------------------------------

    def audit_games_around_boundaries(
        self,
        classified: Optional[pd.DataFrame] = None,
        bounds: Optional[pd.DataFrame] = None,
        days: int = 30,
    ) -> pd.DataFrame:

        if classified is None:
            classified = self.classified_games

        if classified is None:
            raise RuntimeError(
                "Games have not been loaded/classified."
            )

        if bounds is None:
            bounds = self.calculate_candidate_bounds(classified)

        self._print_title(
            f"12. MATCHS AUTOUR DES BORNES ±{days} JOURS"
        )

        rows = []

        for _, bound in bounds.iterrows():

            season = bound["season"]
            start = bound["season_start"]
            end = bound["season_end"]

            nearby = classified.loc[
                (
                    classified["season"] == season
                )
                & (
                    (
                        (
                            classified["date"]
                            >= start - pd.Timedelta(days=days)
                        )
                        & (
                            classified["date"]
                            <= start + pd.Timedelta(days=days)
                        )
                    )
                    |
                    (
                        (
                            classified["date"]
                            >= end - pd.Timedelta(days=days)
                        )
                        & (
                            classified["date"]
                            <= end + pd.Timedelta(days=days)
                        )
                    )
                )
            ].copy()

            if nearby.empty:
                continue

            nearby.insert(
                0,
                "audited_season",
                season,
            )

            rows.append(nearby)

        if not rows:
            print("Aucun match trouvé.")
            return pd.DataFrame()

        result = pd.concat(
            rows,
            ignore_index=True,
        )

        columns = [
            "audited_season",
            "game_id",
            "season",
            "date",
            "round",
            "competition_id",
            "competition_code",
            "competition_name",
            "competition_type",
            "home_club_id",
            "away_club_id",
            "status",
            "classification_reason",
        ]

        available_columns = [
            column
            for column in columns
            if column in result.columns
        ]

        result = result[
            available_columns
        ].sort_values(
            [
                "audited_season",
                "date",
                "game_id",
            ]
        )

        self._print_dataframe(
            result,
            max_rows=300,
        )

        return result

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def export_season_bounds(
        self,
        bounds: pd.DataFrame,
    ) -> None:

        output_path = self.config.output_bounds_path

        output_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        export_columns = [
            "season",
            "season_start",
            "season_end",
            "duration_days",
            "games",
            "competitions",
            "first_competition_code",
            "first_competition_name",
            "first_classification_reason",
            "last_competition_code",
            "last_competition_name",
            "last_classification_reason",
        ]

        available_columns = [
            column
            for column in export_columns
            if column in bounds.columns
        ]

        bounds[
            available_columns
        ].to_csv(
            output_path,
            index=False,
        )

        print()
        print(
            f"Bornes candidates exportées vers : "
            f"{output_path}"
        )

    def export_review(
        self,
        review: pd.DataFrame,
        impact: Optional[pd.DataFrame] = None,
    ) -> None:

        output_path = self.config.output_review_path

        output_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        export = review.copy()

        if impact is not None and not impact.empty:

            impact_columns = [
                "season",
                "review_reason",
                "review_games",
                "first_review_date",
                "last_review_date",
                "candidate_start",
                "candidate_end",
                "impact",
            ]

            available_columns = [
                column
                for column in impact_columns
                if column in impact.columns
            ]

            export = export.merge(
                impact[
                    available_columns
                ],
                left_on=[
                    "season",
                    "classification_reason",
                ],
                right_on=[
                    "season",
                    "review_reason",
                ],
                how="left",
            )

            if "review_reason" in export.columns:
                export = export.drop(
                    columns=["review_reason"]
                )

        export.to_csv(
            output_path,
            index=False,
        )

        print(
            f"REVIEW exportés vers : "
            f"{output_path}"
        )

    # ------------------------------------------------------------------
    # Main audit
    # ------------------------------------------------------------------

    def run(self) -> dict:

        try:
            self.connect()

            # 1
            self.audit_schema()

            # 2
            self.audit_competition_types()

            # 3
            raw_games = self.load_raw_games()

            print()
            print(
                f"RAW games chargés : {len(raw_games):,}"
            )

            # 4
            classified = self.classify_games(raw_games)

            self.audit_classification(classified)

            # 5
            review = self.extract_review_games(
                classified
            )

            self.print_review_summary(review)

            # 6
            bounds = self.calculate_candidate_bounds(
                classified
            )

            self.print_candidate_bounds(bounds)

            # 7
            review_impact = self.calculate_review_impact(
                classified,
                bounds,
            )

            self.print_review_impact(
                review_impact
            )

            # 8
            self.audit_exclusions(
                classified
            )

            # 9
            self.audit_temporal_outliers(
                bounds
            )

            # 10
            boundary_games = self.audit_boundary_games(
                classified,
                bounds,
            )

            # 11
            boundary_competitions = (
                self.audit_boundary_competitions(
                    classified,
                    bounds,
                )
            )

            # 12
            suspicious = self.audit_suspicious_seasons(
                classified
            )

            # 13
            around_boundaries = (
                self.audit_games_around_boundaries(
                    classified,
                    bounds,
                    days=30,
                )
            )

            # Exports
            self.export_season_bounds(
                bounds
            )

            self.export_review(
                review,
                review_impact,
            )

            # Final summary
            self._print_title(
                "13. SYNTHÈSE FINALE"
            )

            print(
                f"RAW games              : {len(raw_games):,}"
            )

            print(
                f"KEEP                   : "
                f"{(classified['status'] == 'KEEP').sum():,}"
            )

            print(
                f"EXCLUDE_NATIONAL       : "
                f"{(
                    classified['status']
                    == 'EXCLUDE_NATIONAL'
                ).sum():,}"
            )

            print(
                f"EXCLUDE_FRIENDLY       : "
                f"{(
                    classified['status']
                    == 'EXCLUDE_FRIENDLY'
                ).sum():,}"
            )

            print(
                f"REVIEW                 : "
                f"{(
                    classified['status']
                    == 'REVIEW'
                ).sum():,}"
            )

            print(
                f"Saisons avec bornes    : "
                f"{bounds['season'].nunique():,}"
            )

            print()

            if not review_impact.empty:

                impact_counts = (
                    review_impact["impact"]
                    .value_counts()
                )

                print(
                    "Impact des REVIEW :"
                )

                for impact, count in (
                    impact_counts.items()
                ):
                    print(
                        f"  {impact:<35} "
                        f"{count:,}"
                    )

            print()
            print(
                "IMPORTANT : les bornes ci-dessus sont "
                "des bornes CANDIDATES."
            )
            print(
                "Les REVIEW susceptibles de déplacer "
                "une borne doivent être validés avant "
                "intégration dans PerformanceLoader."
            )

            return {
                "raw_games": raw_games,
                "classified_games": classified,
                "review": review,
                "bounds": bounds,
                "review_impact": review_impact,
                "boundary_games": boundary_games,
                "boundary_competitions": boundary_competitions,
                "suspicious": suspicious,
                "around_boundaries": around_boundaries,
            }

        finally:
            self.close()


def main() -> None:

    config = AuditConfig(
        database_path=Path(
            "data/historical/transfermarkt-datasets.duckdb"
        ),
        output_bounds_path=Path(
            "data/audits/raw_season_calendar_bounds.csv"
        ),
        output_review_path=Path(
            "data/audits/raw_season_calendar_review.csv"
        ),
        national_team_competition_type=(
            "national_team_competition"
        ),
    )
    audit = RawSeasonCalendarAudit(
        config
    )
    audit.run()


if __name__ == "__main__":
    main()
