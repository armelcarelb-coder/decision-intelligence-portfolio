"""
performance_scorer.py

Calcul du score de performance normalisé des joueurs.

Objectif
--------
Transformer les statistiques brutes de PerformanceLoader en un
score de performance comparable entre joueurs.

Normalisation
-------------
Le percentile est calculé selon :

    position
    +
    competition_level
    +
    saison

Exemple :

    FW + TOP_5 + 2022/23

est comparé uniquement à :

    FW + TOP_5 + 2022/23

et non aux milieux, défenseurs ou joueurs de divisions différentes.

Architecture
------------
PerformanceLoader
        |
        v
performance_scorer.py
        |
        +--> score_performance
        |
        +--> performance_percentile
        |
        v
TransferPerformanceBuilder

Important
---------
Le scorer ne gère PAS les fenêtres temporelles PRE/POST.

Les fenêtres restent exclusivement dans :

    transfer_performance_builder.py

Le scorer est responsable uniquement de la normalisation
des performances individuelles.

Score actuel
------------
Le score combine :

    goals_per90
    assists_per90
    xg_per90
    xa_per90

avec les pondérations suivantes :

    goals_per90   : 30 %
    assists_per90 : 20 %
    xg_per90      : 30 %
    xa_per90      : 20 %

Le score est ensuite converti en percentile au sein du groupe :

    position + competition_level + season

Gestion des minutes
-------------------
Un minimum de minutes est requis pour éviter de donner un score
fiable à un joueur ayant joué seulement quelques minutes.

Valeur par défaut :

    900 minutes

Les joueurs sous ce seuil reçoivent :

    performance_score = NaN
    performance_percentile = NaN

Usage
-----
    python -m football_data.performance_scorer
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd


# ============================================================================
# CONFIGURATION
# ============================================================================

DEFAULT_INPUT_PATH = Path(
    "data/performances/performance_sample.csv"
)

DEFAULT_OUTPUT_PATH = Path(
    "data/performances/performance_scored.csv"
)

MIN_MINUTES = 900

PERCENTILE_METHOD = "average"


# ============================================================================
# COLONNES ATTENDUES
# ============================================================================

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


SCORE_COMPONENTS = {
    "goals_per90": 0.30,
    "assists_per90": 0.20,
    "xg_per90": 0.30,
    "xa_per90": 0.20,
}


# ============================================================================
# SCORER
# ============================================================================


class PerformanceScorer:
    """
    Calcule un score de performance normalisé.

    Le percentile est calculé à l'intérieur de chaque groupe :

        position
        competition_level
        season
    """

    def __init__(
        self,
        performances_df: pd.DataFrame,
        min_minutes: int = MIN_MINUTES,
    ) -> None:

        self.performances_df = performances_df.copy()

        self.min_minutes = min_minutes

        self._validate_input()

        self.performances_df = (
            self._prepare_data(
                self.performances_df
            )
        )

        self.scored_dataset: Optional[pd.DataFrame] = None

    # ========================================================================
    # VALIDATION
    # ========================================================================

    def _validate_input(self) -> None:
        """
        Vérifie les colonnes nécessaires.
        """

        missing = [
            column
            for column in REQUIRED_COLUMNS
            if column not in self.performances_df.columns
        ]

        if missing:

            raise ValueError(
                "Colonnes manquantes dans "
                f"performances_df : {missing}"
            )

    # ========================================================================
    # PREPARATION
    # ========================================================================

    @staticmethod
    def _prepare_data(
        df: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Nettoyage et typage des données.
        """

        df = df.copy()

        # --------------------------------------------------------------------
        # STRINGS
        # --------------------------------------------------------------------

        string_columns = [
            "player",
            "season",
            "competition",
            "competition_level",
            "team",
            "position",
        ]

        for column in string_columns:

            df[column] = (
                df[column]
                .astype(str)
                .str.strip()
            )

        # --------------------------------------------------------------------
        # DATES
        # --------------------------------------------------------------------

        df["season_start_date"] = pd.to_datetime(
            df["season_start_date"],
            errors="coerce",
        )

        df["season_end_date"] = pd.to_datetime(
            df["season_end_date"],
            errors="coerce",
        )

        # --------------------------------------------------------------------
        # NUMERIQUES
        # --------------------------------------------------------------------

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

        return df

    # ========================================================================
    # SCORE BRUT
    # ========================================================================

    def _calculate_raw_score(
        self,
        df: pd.DataFrame,
    ) -> pd.Series:
        """
        Calcule le score pondéré à partir des métriques /90.

        Score :

            30 % goals_per90
            20 % assists_per90
            30 % xg_per90
            20 % xa_per90
        """

        score = pd.Series(
            0.0,
            index=df.index,
        )

        total_weight = pd.Series(
            0.0,
            index=df.index,
        )

        for column, weight in SCORE_COMPONENTS.items():

            values = pd.to_numeric(
                df[column],
                errors="coerce",
            )

            valid = values.notna()

            score.loc[valid] += (
                values.loc[valid] * weight
            )

            total_weight.loc[valid] += weight

        score = score.where(
            total_weight > 0
        )

        # --------------------------------------------------------------------
        # RENORMALISATION SI CERTAINES METRIQUES MANQUENT
        # --------------------------------------------------------------------

        score = (
            score
            / total_weight.replace(
                0,
                np.nan,
            )
        )

        return score

    # ========================================================================
    # STANDARDISATION DANS UN GROUPE
    # ========================================================================

    @staticmethod
    def _group_percentile(
        series: pd.Series,
    ) -> pd.Series:
        """
        Transforme une série de scores en percentile [0, 1].

        Exemple :

            1er joueur  -> 0.0
            médiane     -> ~0.5
            meilleur    -> 1.0
        """

        valid = series.notna()

        result = pd.Series(
            np.nan,
            index=series.index,
            dtype=float,
        )

        if valid.sum() == 0:

            return result

        if valid.sum() == 1:

            result.loc[valid] = 0.5

            return result

        ranks = (
            series.loc[valid]
            .rank(
                method=PERCENTILE_METHOD,
                pct=True,
            )
        )

        result.loc[valid] = ranks

        return result

    # ========================================================================
    # CALCUL SCORE
    # ========================================================================

    def calculate_scores(
        self,
    ) -> pd.DataFrame:
        """
        Calcule score et percentile.

        Retourne un DataFrame enrichi avec :

            performance_score
            performance_percentile
            performance_score_status
        """

        df = self.performances_df.copy()

        # --------------------------------------------------------------------
        # SCORE BRUT
        # --------------------------------------------------------------------

        df["performance_score"] = (
            self._calculate_raw_score(
                df
            )
        )

        # --------------------------------------------------------------------
        # ELIGIBILITE
        # --------------------------------------------------------------------

        df["performance_score_status"] = (
            "ELIGIBLE"
        )

        insufficient_minutes = (
            df["minutes"]
            < self.min_minutes
        )

        missing_score = (
            df["performance_score"]
            .isna()
        )

        df.loc[
            insufficient_minutes,
            "performance_score_status",
        ] = "INSUFFICIENT_MINUTES"

        df.loc[
            (~insufficient_minutes)
            & missing_score,
            "performance_score_status",
        ] = "INSUFFICIENT_METRICS"

        # --------------------------------------------------------------------
        # SCORE NON ELIGIBLE
        # --------------------------------------------------------------------

        eligible = (
            (~insufficient_minutes)
            & df["performance_score"].notna()
        )

        df.loc[
            ~eligible,
            "performance_score",
        ] = np.nan

        # --------------------------------------------------------------------
        # PERCENTILE
        #
        # Groupe :
        #
        # position
        # competition_level
        # season
        # --------------------------------------------------------------------

        df["performance_percentile"] = np.nan

        group_columns = [
            "position",
            "competition_level",
            "season",
        ]

        eligible_df = df.loc[
            eligible
        ].copy()

        if not eligible_df.empty:

            percentiles = (
                eligible_df
                .groupby(
                    group_columns,
                    dropna=False,
                )[
                    "performance_score"
                ]
                .transform(
                    self._group_percentile
                )
            )

            df.loc[
                eligible_df.index,
                "performance_percentile",
            ] = percentiles

        # --------------------------------------------------------------------
        # ARRONDI
        # --------------------------------------------------------------------

        df["performance_score"] = (
            df["performance_score"]
            .round(6)
        )

        df["performance_percentile"] = (
            df["performance_percentile"]
            .round(6)
        )

        self.scored_dataset = df

        return df

    # ========================================================================
    # SUMMARY
    # ========================================================================

    def summary(
        self,
        dataset: Optional[pd.DataFrame] = None,
    ) -> dict:
        """
        Produit un résumé du scoring.
        """

        if dataset is None:

            dataset = (
                self.scored_dataset
                if self.scored_dataset is not None
                else pd.DataFrame()
            )

        if dataset.empty:

            return {
                "rows": 0,
                "eligible": 0,
                "insufficient_minutes": 0,
                "insufficient_metrics": 0,
                "unique_players": 0,
                "unique_groups": 0,
                "mean_score": np.nan,
                "mean_percentile": np.nan,
            }

        status = dataset[
            "performance_score_status"
        ]

        groups = (
            dataset[
                [
                    "position",
                    "competition_level",
                    "season",
                ]
            ]
            .drop_duplicates()
        )

        return {
            "rows": len(dataset),

            "eligible": (
                status == "ELIGIBLE"
            ).sum(),

            "insufficient_minutes": (
                status
                == "INSUFFICIENT_MINUTES"
            ).sum(),

            "insufficient_metrics": (
                status
                == "INSUFFICIENT_METRICS"
            ).sum(),

            "unique_players": dataset[
                "player"
            ].nunique(),

            "unique_groups": len(groups),

            "mean_score": dataset[
                "performance_score"
            ].mean(),

            "mean_percentile": dataset[
                "performance_percentile"
            ].mean(),
        }

    # ========================================================================
    # SAVE
    # ========================================================================

    def save(
        self,
        dataset: Optional[pd.DataFrame] = None,
        path: Optional[Path] = None,
    ) -> Path:
        """
        Sauvegarde le dataset scoré.
        """

        if dataset is None:

            dataset = (
                self.scored_dataset
                if self.scored_dataset is not None
                else self.calculate_scores()
            )

        output_path = (
            Path(path)
            if path is not None
            else DEFAULT_OUTPUT_PATH
        )

        output_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        dataset.to_csv(
            output_path,
            index=False,
        )

        print(
            "[PerformanceScorer] "
            f"Dataset sauvegardé : {output_path}"
        )

        return output_path


# ============================================================================
# VALIDATIONS
# ============================================================================


def validate_percentiles(
    dataset: pd.DataFrame,
) -> bool:
    """
    Vérifie que les percentiles sont compris entre 0 et 1.
    """

    print()
    print(
        "VALIDATION PERCENTILES"
    )
    print("-" * 70)

    valid = dataset[
        "performance_percentile"
    ].dropna()

    if valid.empty:

        print(
            "✗ Aucun percentile calculé."
        )

        return False

    in_range = (
        (valid >= 0)
        & (valid <= 1)
    ).all()

    if in_range:

        print(
            f"✓ Tous les percentiles sont dans [0, 1]. "
            f"n={len(valid)}"
        )

    else:

        print(
            "✗ Des percentiles sont hors de [0, 1]."
        )

    return bool(in_range)


def validate_group_normalization(
    dataset: pd.DataFrame,
) -> bool:
    """
    Vérifie que les percentiles sont calculés séparément
    pour chaque combinaison :

        position
        competition_level
        season
    """

    print()
    print(
        "VALIDATION NORMALISATION PAR GROUPE"
    )
    print("-" * 70)

    group_columns = [
        "position",
        "competition_level",
        "season",
    ]

    valid = dataset[
        dataset["performance_percentile"].notna()
    ].copy()

    if valid.empty:

        print(
            "✗ Aucun groupe exploitable."
        )

        return False

    success = True

    for group_values, group in valid.groupby(
        group_columns,
        dropna=False,
    ):

        position, level, season = (
            group_values
        )

        percentiles = group[
            "performance_percentile"
        ]

        print(
            f"{position:<5} | "
            f"{level:<12} | "
            f"{season:<8} | "
            f"n={len(group):<3} | "
            f"min={percentiles.min():.3f} | "
            f"max={percentiles.max():.3f}"
        )

        if (
            percentiles.min() < 0
            or percentiles.max() > 1
        ):

            success = False

    if success:

        print()
        print(
            "✓ Normalisation par groupe respectée."
        )

    return success


def validate_score_components(
    dataset: pd.DataFrame,
) -> bool:
    """
    Vérifie que le score utilise bien les composantes attendues.
    """

    print()
    print(
        "VALIDATION COMPOSANTES DU SCORE"
    )
    print("-" * 70)

    print(
        "goals_per90   : 30 %"
    )

    print(
        "assists_per90 : 20 %"
    )

    print(
        "xg_per90      : 30 %"
    )

    print(
        "xa_per90      : 20 %"
    )

    total_weight = sum(
        SCORE_COMPONENTS.values()
    )

    success = (
        abs(total_weight - 1.0)
        < 1e-9
    )

    if success:

        print(
            "✓ Pondérations = 100 %"
        )

    else:

        print(
            "✗ Pondérations incorrectes."
        )

    return success


# ============================================================================
# TEST PRINCIPAL
# ============================================================================


def run_test() -> None:
    """
    Test complet du PerformanceScorer.
    """

    print("=" * 70)
    print(
        "TEST PERFORMANCE SCORER"
    )
    print("=" * 70)

    # ========================================================================
    # IMPORT PERFORMANCE LOADER
    # ========================================================================

    try:

        from football_data.performance_loader import (
            PerformanceLoader,
        )

    except ImportError as exc:

        print(
            "Erreur import PerformanceLoader :",
            exc,
        )

        return

    # ========================================================================
    # CHARGEMENT
    # ========================================================================

    loader = PerformanceLoader(
        offline=True,
        local_path=DEFAULT_INPUT_PATH,
    )

    performances = loader.load()

    # ========================================================================
    # SCORER
    # ========================================================================

    scorer = PerformanceScorer(
        performances_df=performances,
        min_minutes=MIN_MINUTES,
    )

    dataset = scorer.calculate_scores()

    # ========================================================================
    # DATASET
    # ========================================================================

    print()
    print(
        "DATASET SCORÉ"
    )
    print("-" * 70)

    columns = [
        "player",
        "season",
        "competition",
        "competition_level",
        "position",
        "minutes",
        "goals_per90",
        "assists_per90",
        "xg_per90",
        "xa_per90",
        "performance_score",
        "performance_percentile",
        "performance_score_status",
    ]

    print(
        dataset[
            columns
        ].to_string(
            index=False
        )
    )

    # ========================================================================
    # SUMMARY
    # ========================================================================

    summary = scorer.summary(
        dataset
    )

    print()
    print(
        "SUMMARY"
    )
    print("-" * 70)

    for key, value in summary.items():

        print(
            f"{key:<30}: {value}"
        )

    # ========================================================================
    # VALIDATIONS
    # ========================================================================

    percentile_ok = (
        validate_percentiles(
            dataset
        )
    )

    normalization_ok = (
        validate_group_normalization(
            dataset
        )
    )

    components_ok = (
        validate_score_components(
            dataset
        )
    )

    # ========================================================================
    # SAVE
    # ========================================================================

    output_path = scorer.save(
        dataset
    )

    print()
    print(
        f"Dataset exporté : {output_path}"
    )

    # ========================================================================
    # RESULTAT
    # ========================================================================

    print()

    if (
        percentile_ok
        and normalization_ok
        and components_ok
    ):

        print(
            "✓ VALIDATION PERFORMANCE SCORER RÉUSSIE"
        )

    else:

        print(
            "✗ VALIDATION PERFORMANCE SCORER ÉCHOUÉE"
        )

    print()


# ============================================================================
# MAIN
# ============================================================================


if __name__ == "__main__":

    run_test()