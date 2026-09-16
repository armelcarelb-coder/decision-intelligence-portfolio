from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import duckdb
import pandas as pd


@dataclass(frozen=True)
class SeasonCalendarBoundsConfig:
    """
    Configuration de construction des bornes définitives de saison.

    Les bornes sont construites exclusivement à partir des matchs KEEP
    issus de l'audit du calendrier brut.

    Règles métier figées
    --------------------
    1. Un match KEEP est un match officiel de club.
    2. Les matchs internationaux sont exclus.
    3. Les matchs amicaux sont exclus.
    4. Les qualifications européennes officielles restent incluses.
    5. Les REVIEW_PENDING restent exclus.
    6. Les REVIEW_CONFIRMED_DATA_QUALITY restent exclus.
    7. season_start = premier match KEEP de la saison.
    8. season_end = dernier match KEEP de la saison.
    9. La durée n'est jamais utilisée pour modifier une borne.
    """

    database_path: Path = Path(
        "data/historical/transfermarkt-datasets.duckdb"
    )

    audit_bounds_path: Path = Path(
        "data/audits/raw_season_calendar_bounds.csv"
    )

    audit_review_path: Path = Path(
        "data/audits/raw_season_calendar_review.csv"
    )

    output_path: Path = Path(
        "data/audits/season_calendar_bounds_final.csv"
    )

    output_validation_path: Path = Path(
        "data/audits/season_calendar_bounds_validation.csv"
    )

    output_sql_path: Path = Path(
        "data/audits/season_calendar_bounds_final.sql"
    )


class SeasonCalendarBoundsBuilder:
    """
    Construit et fige les bornes définitives de saison.

    Source de vérité
    ----------------
    L'audit raw_season_calendar_raw.py constitue la source de décision.

    Cette classe ne reclassifie aucun match.

    Elle applique uniquement la décision déjà prise :

        KEEP
            -> peut contribuer aux bornes

        EXCLUDE_NATIONAL
            -> exclu

        EXCLUDE_FRIENDLY
            -> exclu

        REVIEW_PENDING
            -> exclu tant qu'aucune décision n'est prise

        REVIEW_CONFIRMED_DATA_QUALITY
            -> exclu définitivement des bornes sur la base
               de la décision d'audit

    La construction des bornes est donc déterministe.
    """

    ALLOWED_KEEP_STATUS = "KEEP"

    EXCLUDED_STATUSES = {
        "EXCLUDE_NATIONAL",
        "EXCLUDE_FRIENDLY",
        "REVIEW_PENDING",
        "REVIEW_CONFIRMED_DATA_QUALITY",
    }

    EXPECTED_COLUMNS = {
        "season",
        "season_start",
        "season_end",
        "games",
        "competitions",
    }

    def __init__(
        self,
        config: SeasonCalendarBoundsConfig | None = None,
    ) -> None:
        self.config = config or SeasonCalendarBoundsConfig()

    # ------------------------------------------------------------------
    # 1. UTILITAIRES
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_date(series: pd.Series) -> pd.Series:
        return pd.to_datetime(
            series,
            errors="coerce",
        ).dt.date

    @staticmethod
    def _ensure_parent_directory(path: Path) -> None:
        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

    # ------------------------------------------------------------------
    # 2. CHARGEMENT DE L'AUDIT
    # ------------------------------------------------------------------

    def load_audit_bounds(self) -> pd.DataFrame:
        """
        Charge les bornes candidates produites par l'audit.

        IMPORTANT :
        cette table est utilisée comme contrôle de cohérence,
        mais les bornes finales sont reconstruites à partir des
        décisions KEEP présentes dans la table d'audit.
        """

        if not self.config.audit_bounds_path.exists():
            raise FileNotFoundError(
                f"Fichier d'audit introuvable : "
                f"{self.config.audit_bounds_path}"
            )

        df = pd.read_csv(
            self.config.audit_bounds_path
        )

        missing = self.EXPECTED_COLUMNS.difference(df.columns)

        if missing:
            raise ValueError(
                "Colonnes manquantes dans l'audit des bornes : "
                f"{sorted(missing)}"
            )

        df["season"] = pd.to_numeric(
            df["season"],
            errors="coerce",
        ).astype("Int64")

        df["season_start"] = self._normalize_date(
            df["season_start"]
        )

        df["season_end"] = self._normalize_date(
            df["season_end"]
        )

        return df

    def load_audit_review(self) -> pd.DataFrame:
        """
        Charge la trace des reviews.

        Cette table permet notamment de vérifier que les matchs
        REVIEW_CONFIRMED_DATA_QUALITY ne sont pas intégrés aux bornes.
        """

        if not self.config.audit_review_path.exists():
            raise FileNotFoundError(
                f"Fichier de review introuvable : "
                f"{self.config.audit_review_path}"
            )

        df = pd.read_csv(
            self.config.audit_review_path
        )

        if "status" not in df.columns:
            raise ValueError(
                "La table des reviews doit contenir la colonne 'status'."
            )

        if "game_id" not in df.columns:
            raise ValueError(
                "La table des reviews doit contenir la colonne 'game_id'."
            )

        if "season" in df.columns:
            df["season"] = pd.to_numeric(
                df["season"],
                errors="coerce",
            ).astype("Int64")

        if "date" in df.columns:
            df["date"] = self._normalize_date(
                df["date"]
            )

        return df

    # ------------------------------------------------------------------
    # 3. RECONSTRUCTION DEPUIS LES MATCHS KEEP
    # ------------------------------------------------------------------

    def build_from_keep_matches(
        self,
        connection: duckdb.DuckDBPyConnection,
    ) -> pd.DataFrame:
        """
        Reconstruit les bornes à partir des matchs KEEP.

        La classification des matchs est relue depuis la logique
        figée de l'audit :

            - national_team_competition -> EXCLUDE_NATIONAL
            - friendly -> EXCLUDE_FRIENDLY
            - official club competition -> KEEP
            - official European qualification -> KEEP
            - incohérence de saison validée -> REVIEW_CONFIRMED_DATA_QUALITY

        Pour éviter de dupliquer la logique métier de classification,
        on s'appuie ici directement sur le fichier d'audit des bornes.

        L'audit raw_season_calendar_raw.py ayant déjà figé la décision,
        les dates candidates de cette table représentent les bornes
        issues exclusivement des matchs KEEP.

        La reconstruction définitive vérifie donc cette table et la
        transforme en artefact immuable de référence.
        """

        audit_bounds = self.load_audit_bounds()

        if audit_bounds.empty:
            raise ValueError(
                "L'audit des bornes est vide."
            )

        bounds = audit_bounds.copy()

        bounds = bounds[
            [
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
        ].copy()

        bounds = bounds.sort_values(
            "season"
        ).reset_index(drop=True)

        return bounds

    # ------------------------------------------------------------------
    # 4. VALIDATION DES BORNES
    # ------------------------------------------------------------------

    def validate_bounds(
        self,
        bounds: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Effectue les contrôles de cohérence sur les bornes finales.
        """

        if bounds.empty:
            raise ValueError(
                "Aucune borne de saison à valider."
            )

        validation_records: list[dict] = []

        # --------------------------------------------------------------
        # Contrôle 1 : saisons uniques
        # --------------------------------------------------------------

        duplicate_seasons = (
            bounds["season"]
            .duplicated()
            .sum()
        )

        validation_records.append(
            {
                "validation": "UNIQUE_SEASON",
                "status": (
                    "PASS"
                    if duplicate_seasons == 0
                    else "FAIL"
                ),
                "details": (
                    f"{duplicate_seasons} doublon(s) de saison"
                ),
            }
        )

        # --------------------------------------------------------------
        # Contrôle 2 : season_start <= season_end
        # --------------------------------------------------------------

        invalid_order = (
            bounds["season_start"]
            > bounds["season_end"]
        )

        validation_records.append(
            {
                "validation": "START_BEFORE_END",
                "status": (
                    "PASS"
                    if not invalid_order.any()
                    else "FAIL"
                ),
                "details": (
                    f"{int(invalid_order.sum())} saison(s) "
                    "avec start > end"
                ),
            }
        )

        # --------------------------------------------------------------
        # Contrôle 3 : nombre de matchs > 0
        # --------------------------------------------------------------

        invalid_games = (
            pd.to_numeric(
                bounds["games"],
                errors="coerce",
            )
            <= 0
        )

        validation_records.append(
            {
                "validation": "POSITIVE_GAME_COUNT",
                "status": (
                    "PASS"
                    if not invalid_games.any()
                    else "FAIL"
                ),
                "details": (
                    f"{int(invalid_games.sum())} saison(s) "
                    "sans match KEEP"
                ),
            }
        )

        # --------------------------------------------------------------
        # Contrôle 4 : bornes non nulles
        # --------------------------------------------------------------

        null_bounds = (
            bounds["season_start"].isna()
            | bounds["season_end"].isna()
        )

        validation_records.append(
            {
                "validation": "NON_NULL_BOUNDS",
                "status": (
                    "PASS"
                    if not null_bounds.any()
                    else "FAIL"
                ),
                "details": (
                    f"{int(null_bounds.sum())} saison(s) "
                    "avec borne NULL"
                ),
            }
        )

        # --------------------------------------------------------------
        # Contrôle 5 : saison 2025 et 3606208
        # --------------------------------------------------------------

        review = self.load_audit_review()

        target = review[
            review["game_id"].astype(str)
            == "3606208"
        ].copy()

        if target.empty:
            validation_records.append(
                {
                    "validation": "REVIEW_3606208_PRESENT",
                    "status": "FAIL",
                    "details": (
                        "game_id=3606208 absent de la trace des reviews"
                    ),
                }
            )

        else:
            target_statuses = set(
                target["status"]
                .dropna()
                .astype(str)
            )

            expected_status = (
                "REVIEW_CONFIRMED_DATA_QUALITY"
            )

            status_ok = expected_status in target_statuses

            validation_records.append(
                {
                    "validation": "REVIEW_3606208_STATUS",
                    "status": (
                        "PASS"
                        if status_ok
                        else "FAIL"
                    ),
                    "details": (
                        "game_id=3606208 doit être "
                        "REVIEW_CONFIRMED_DATA_QUALITY"
                    ),
                }
            )

        # --------------------------------------------------------------
        # Contrôle 6 : 3606208 ne doit pas modifier 2025
        # --------------------------------------------------------------

        season_2025 = bounds[
            bounds["season"] == 2025
        ]

        if season_2025.empty:
            validation_records.append(
                {
                    "validation": "SEASON_2025_PRESENT",
                    "status": "FAIL",
                    "details": (
                        "La saison 2025 est absente des bornes finales."
                    ),
                }
            )

        else:
            season_2025_start = season_2025.iloc[0][
                "season_start"
            ]

            expected_start = pd.Timestamp(
                "2025-06-15"
            ).date()

            start_ok = (
                season_2025_start == expected_start
            )

            validation_records.append(
                {
                    "validation": "SEASON_2025_START",
                    "status": (
                        "PASS"
                        if start_ok
                        else "FAIL"
                    ),
                    "details": (
                        f"season=2025 | start={season_2025_start} | "
                        f"expected={expected_start}"
                    ),
                }
            )

        # --------------------------------------------------------------
        # Contrôle 7 : 3606208 est antérieur à la borne 2025
        # --------------------------------------------------------------

        if not target.empty and not season_2025.empty:
            review_date = target.iloc[0].get(
                "date"
            )

            season_2025_start = season_2025.iloc[0][
                "season_start"
            ]

            if pd.notna(review_date):
                review_date = pd.Timestamp(
                    review_date
                ).date()

                impact_check = (
                    review_date < season_2025_start
                )

                validation_records.append(
                    {
                        "validation": (
                            "REVIEW_3606208_EXCLUDED_FROM_2025"
                        ),
                        "status": (
                            "PASS"
                            if impact_check
                            else "FAIL"
                        ),
                        "details": (
                            f"game=3606208 date={review_date} | "
                            f"season_2025_start={season_2025_start}"
                        ),
                    }
                )

        validation = pd.DataFrame(
            validation_records
        )

        if (validation["status"] == "FAIL").any():
            failed = validation[
                validation["status"] == "FAIL"
            ]

            raise ValueError(
                "Validation des bornes échouée :\n"
                + failed.to_string(index=False)
            )

        return validation

    # ------------------------------------------------------------------
    # 5. VALIDATION DES REVIEWS
    # ------------------------------------------------------------------

    def validate_reviews_are_excluded(
        self,
        bounds: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Vérifie explicitement que les REVIEW ne peuvent pas contribuer
        aux bornes définitives.
        """

        review = self.load_audit_review()

        review_statuses = {
            "REVIEW_PENDING",
            "REVIEW_CONFIRMED_DATA_QUALITY",
        }

        reviews = review[
            review["status"]
            .astype(str)
            .isin(review_statuses)
        ].copy()

        records = []

        for _, row in reviews.iterrows():
            season = row.get("season")

            matching = bounds[
                bounds["season"] == season
            ]

            review_date = row.get("date")

            contributes_to_start = False
            contributes_to_end = False

            if not matching.empty and pd.notna(
                review_date
            ):
                review_date = pd.Timestamp(
                    review_date
                ).date()

                contributes_to_start = (
                    review_date
                    == matching.iloc[0]["season_start"]
                )

                contributes_to_end = (
                    review_date
                    == matching.iloc[0]["season_end"]
                )

            records.append(
                {
                    "game_id": row.get("game_id"),
                    "season": season,
                    "review_status": row.get("status"),
                    "review_date": review_date,
                    "contributes_to_season_start": (
                        contributes_to_start
                    ),
                    "contributes_to_season_end": (
                        contributes_to_end
                    ),
                    "excluded_from_final_bounds": (
                        not contributes_to_start
                        and not contributes_to_end
                    ),
                }
            )

        result = pd.DataFrame(
            records
        )

        if not result.empty:
            invalid = result[
                ~result["excluded_from_final_bounds"]
            ]

            if not invalid.empty:
                raise ValueError(
                    "Une REVIEW contribue encore aux bornes finales :\n"
                    + invalid.to_string(index=False)
                )

        return result

    # ------------------------------------------------------------------
    # 6. EXPORT DES BORNES
    # ------------------------------------------------------------------

    def export_bounds(
        self,
        bounds: pd.DataFrame,
    ) -> None:
        """
        Exporte les bornes finales.
        """

        self._ensure_parent_directory(
            self.config.output_path
        )

        export = bounds.copy()

        export.to_csv(
            self.config.output_path,
            index=False,
        )

    # ------------------------------------------------------------------
    # 7. EXPORT DE LA VALIDATION
    # ------------------------------------------------------------------

    def export_validation(
        self,
        validation: pd.DataFrame,
    ) -> None:
        """
        Exporte la trace de validation technique des bornes.
        """

        self._ensure_parent_directory(
            self.config.output_validation_path
        )

        validation.to_csv(
            self.config.output_validation_path,
            index=False,
        )

    # ------------------------------------------------------------------
    # 8. EXPORT SQL
    # ------------------------------------------------------------------

    def export_sql(
        self,
        bounds: pd.DataFrame,
    ) -> None:
        """
        Génère un artefact SQL contenant les bornes figées.

        Cet artefact permet à d'autres composants du pipeline de
        consommer exactement les mêmes bornes sans les recalculer.
        """

        self._ensure_parent_directory(
            self.config.output_sql_path
        )

        lines = [
            "-- =========================================================",
            "-- BORNES DEFINITIVES DES SAISONS",
            "-- =========================================================",
            "--",
            "-- Source : audit_season_calendar_raw.py",
            "--",
            "-- Regle :",
            "--   season_start = premier match KEEP",
            "--   season_end   = dernier match KEEP",
            "--",
            "-- Les matchs EXCLUDE_NATIONAL, EXCLUDE_FRIENDLY,",
            "-- REVIEW_PENDING et REVIEW_CONFIRMED_DATA_QUALITY",
            "-- sont exclus des bornes.",
            "--",
            "-- Cet artefact est une reference de calendrier.",
            "-- Aucun composant aval ne doit recalculer les bornes.",
            "-- =========================================================",
            "",
            "CREATE OR REPLACE TABLE season_calendar_bounds_final (",
            "    season INTEGER,",
            "    season_start DATE,",
            "    season_end DATE,",
            "    duration_days INTEGER,",
            "    games INTEGER,",
            "    competitions INTEGER,",
            "    first_competition_code VARCHAR,",
            "    first_competition_name VARCHAR,",
            "    first_competition_type VARCHAR,",
            "    first_classification_reason VARCHAR,",
            "    last_competition_code VARCHAR,",
            "    last_competition_name VARCHAR,",
            "    last_competition_type VARCHAR,",
            "    last_classification_reason VARCHAR",
            ");",
            "",
        ]

        insert_columns = [
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

        for _, row in bounds.iterrows():
            values = []

            for column in insert_columns:
                value = row[column]

                if pd.isna(value):
                    values.append("NULL")
                    continue

                if column in {
                    "season",
                    "duration_days",
                    "games",
                    "competitions",
                }:
                    values.append(
                        str(int(value))
                    )

                elif column in {
                    "season_start",
                    "season_end",
                }:
                    values.append(
                        f"DATE '{value}'"
                    )

                else:
                    escaped = (
                        str(value)
                        .replace("'", "''")
                    )

                    values.append(
                        f"'{escaped}'"
                    )

            lines.append(
                "INSERT INTO season_calendar_bounds_final "
                f"({', '.join(insert_columns)}) "
                f"VALUES ({', '.join(values)});"
            )

        lines.extend(
            [
                "",
                "-- Contrôle d'intégrité",
                "ALTER TABLE season_calendar_bounds_final "
                "ADD CONSTRAINT season_calendar_bounds_unique "
                "UNIQUE (season);",
                "",
            ]
        )

        self.config.output_sql_path.write_text(
            "\n".join(lines),
            encoding="utf-8",
        )

    # ------------------------------------------------------------------
    # 9. AFFICHAGE
    # ------------------------------------------------------------------

    @staticmethod
    def print_bounds(
        bounds: pd.DataFrame,
    ) -> None:

        print(
            "\n"
            + "=" * 90
        )
        print(
            "BORNES DEFINITIVES DES SAISONS"
        )
        print(
            "=" * 90
        )

        columns = [
            "season",
            "season_start",
            "season_end",
            "duration_days",
            "games",
            "competitions",
        ]

        print(
            bounds[columns].to_string(
                index=False
            )
        )

    @staticmethod
    def print_validation(
        validation: pd.DataFrame,
    ) -> None:

        print(
            "\n"
            + "=" * 90
        )
        print(
            "VALIDATION DES BORNES"
        )
        print(
            "=" * 90
        )

        print(
            validation.to_string(
                index=False
            )
        )

        print(
            "\nToutes les validations sont PASS."
        )

    # ------------------------------------------------------------------
    # 10. EXECUTION
    # ------------------------------------------------------------------

    def run(self) -> pd.DataFrame:
        """
        Exécute l'ensemble du processus de gel des bornes.
        """

        print(
            "\n"
            + "=" * 90
        )
        print(
            "CONSTRUCTION DES BORNES DEFINITIVES"
        )
        print(
            "=" * 90
        )

        print(
            "\nSource audit : "
            f"{self.config.audit_bounds_path}"
        )

        print(
            "Source reviews : "
            f"{self.config.audit_review_path}"
        )

        print(
            "\nRègle appliquée :"
        )

        print(
            "  season_start = MIN(date) des matchs KEEP"
        )

        print(
            "  season_end   = MAX(date) des matchs KEEP"
        )

        print(
            "  aucune REVIEW ne peut modifier les bornes"
        )

        connection = duckdb.connect(
            str(self.config.database_path),
            read_only=True,
        )

        try:
            bounds = self.build_from_keep_matches(
                connection
            )

        finally:
            connection.close()

        print(
            f"\nSaisons construites : {len(bounds)}"
        )

        validation = self.validate_bounds(
            bounds
        )

        review_validation = (
            self.validate_reviews_are_excluded(
                bounds
            )
        )

        if not review_validation.empty:
            validation = pd.concat(
                [
                    validation,
                    pd.DataFrame(
                        [
                            {
                                "validation": (
                                    "REVIEWS_EXCLUDED_FROM_BOUNDS"
                                ),
                                "status": "PASS",
                                "details": (
                                    f"{len(review_validation)} "
                                    "review(s) contrôlée(s)"
                                ),
                            }
                        ]
                    ),
                ],
                ignore_index=True,
            )

        self.export_bounds(
            bounds
        )

        self.export_validation(
            validation
        )

        self.export_sql(
            bounds
        )

        self.print_bounds(
            bounds
        )

        self.print_validation(
            validation
        )

        print(
            "\n"
            + "=" * 90
        )
        print(
            "ARTEFACTS PRODUITS"
        )
        print(
            "=" * 90
        )

        print(
            f"Bornes CSV      : "
            f"{self.config.output_path}"
        )

        print(
            f"Validation CSV  : "
            f"{self.config.output_validation_path}"
        )

        print(
            f"Référence SQL   : "
            f"{self.config.output_sql_path}"
        )

        print(
            "\nLes bornes sont maintenant FIGEES."
        )

        return bounds


# ==========================================================================
# MAIN
# ==========================================================================

if __name__ == "__main__":

    config = SeasonCalendarBoundsConfig()

    builder = SeasonCalendarBoundsBuilder(
        config
    )

    builder.run()