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


Score
-----
Le score combine :

    goals_per90
    assists_per90
    xg_per90
    xa_per90

avec les pondérations :

    goals_per90   : 30 %
    assists_per90 : 20 %
    xg_per90      : 30 %
    xa_per90      : 20 %

Si certaines métriques sont absentes, les poids disponibles
sont renormalisés.

Exemple :

    goals_per90 = disponible
    assists_per90 = disponible
    xg_per90 = NaN
    xa_per90 = NaN

Alors :

    score =
        (goals_per90 * 0.30
        + assists_per90 * 0.20)
        / 0.50


Percentile
----------
Le percentile est calculé à l'intérieur du groupe :

    position + competition_level + season

Les joueurs non éligibles ne participent PAS au calcul du percentile.


Gestion des minutes
-------------------
Minimum requis :

    900 minutes

Sous ce seuil :

    performance_score = NaN
    performance_percentile = NaN
    status = INSUFFICIENT_MINUTES


Gestion des métriques
---------------------
Si aucune métrique permettant de calculer le score n'est disponible :

    performance_score = NaN
    performance_percentile = NaN
    status = INSUFFICIENT_METRICS


Gestion du groupe
-----------------
Pour calculer un percentile, les informations suivantes sont nécessaires :

    position
    competition_level
    season

Si l'une de ces valeurs est absente :

    performance_percentile = NaN
    status = INSUFFICIENT_GROUP


Cas d'un seul joueur
--------------------
Lorsqu'un groupe contient un seul joueur éligible :

    percentile = 0.5


Cas des ex-aequo
----------------
Les ex-aequo utilisent :

    rank(method="average", pct=True)

Ce qui garantit le même percentile pour les joueurs
ayant exactement le même score.


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


GROUP_COLUMNS = [
    "position",
    "competition_level",
    "season",
]


NUMERIC_COLUMNS = [
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
# STATUTS
# ============================================================================

STATUS_ELIGIBLE = "ELIGIBLE"
STATUS_INSUFFICIENT_MINUTES = "INSUFFICIENT_MINUTES"
STATUS_INSUFFICIENT_METRICS = "INSUFFICIENT_METRICS"
STATUS_INSUFFICIENT_GROUP = "INSUFFICIENT_GROUP"


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

        if self.min_minutes < 0:
            raise ValueError(
                "min_minutes doit être >= 0."
            )

        self._validate_input()

        self.performances_df = (
            self._prepare_data(
                self.performances_df
            )
        )

        self.scored_dataset: Optional[pd.DataFrame] = None

    # ========================================================================
    # VALIDATION INPUT
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

        Les valeurs manquantes textuelles sont conservées comme
        NaN plutôt que converties en chaîne "nan".
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
                .astype("string")
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

        for column in NUMERIC_COLUMNS:

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

        Les métriques disponibles sont renormalisées.

        Exemple :

            goals_per90 + xg_per90 disponibles

        alors :

            score =
                (goals_per90 * 0.30
                + xg_per90 * 0.30)
                / 0.60
        """

        score = pd.Series(
            0.0,
            index=df.index,
            dtype=float,
        )

        total_weight = pd.Series(
            0.0,
            index=df.index,
            dtype=float,
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

        score = (
            score
            / total_weight.replace(
                0,
                np.nan,
            )
        )

        return score

    # ========================================================================
    # PERCENTILE
    # ========================================================================

    @staticmethod
    def _group_percentile(
        series: pd.Series,
    ) -> pd.Series:
        """
        Transforme une série de scores en percentile [0, 1].

        Règles :

        - groupe vide -> NaN
        - un seul joueur -> 0.5
        - plusieurs joueurs -> rank(pct=True)
        - ex-aequo -> percentile moyen
        """

        valid = series.notna()

        result = pd.Series(
            np.nan,
            index=series.index,
            dtype=float,
        )

        valid_count = int(valid.sum())

        if valid_count == 0:
            return result

        if valid_count == 1:

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
        # STATUT INITIAL
        # --------------------------------------------------------------------

        df["performance_score_status"] = (
            STATUS_ELIGIBLE
        )

        # --------------------------------------------------------------------
        # MINUTES
        # --------------------------------------------------------------------

        insufficient_minutes = (
            df["minutes"].isna()
            | (
                df["minutes"]
                < self.min_minutes
            )
        )

        # --------------------------------------------------------------------
        # SCORE MANQUANT
        # --------------------------------------------------------------------

        missing_score = (
            df["performance_score"]
            .isna()
        )

        # --------------------------------------------------------------------
        # GROUPE INCOMPLET
        # --------------------------------------------------------------------

        missing_group = (
            df[GROUP_COLUMNS]
            .isna()
            .any(axis=1)
        )

        # --------------------------------------------------------------------
        # STATUTS
        # --------------------------------------------------------------------

        df.loc[
            insufficient_minutes,
            "performance_score_status",
        ] = STATUS_INSUFFICIENT_MINUTES

        df.loc[
            (~insufficient_minutes)
            & missing_score,
            "performance_score_status",
        ] = STATUS_INSUFFICIENT_METRICS

        df.loc[
            (~insufficient_minutes)
            & (~missing_score)
            & missing_group,
            "performance_score_status",
        ] = STATUS_INSUFFICIENT_GROUP

        # --------------------------------------------------------------------
        # ELIGIBILITE SCORE
        #
        # Un joueur doit :
        #
        # - avoir suffisamment de minutes
        # - avoir au moins une métrique valide
        # --------------------------------------------------------------------

        eligible_score = (
            (~insufficient_minutes)
            & df["performance_score"].notna()
        )

        # --------------------------------------------------------------------
        # SCORE NON ELIGIBLE
        # --------------------------------------------------------------------

        df.loc[
            ~eligible_score,
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
        #
        # Les joueurs ayant un score invalide sont exclus.
        # --------------------------------------------------------------------

        df["performance_percentile"] = np.nan

        eligible_percentile = (
            eligible_score
            & (~missing_group)
        )

        eligible_df = df.loc[
            eligible_percentile
        ].copy()

        if not eligible_df.empty:

            percentiles = (
                eligible_df
                .groupby(
                    GROUP_COLUMNS,
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
                "insufficient_group": 0,
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
                GROUP_COLUMNS
            ]
            .drop_duplicates()
        )

        return {
            "rows": len(dataset),

            "eligible": (
                status == STATUS_ELIGIBLE
            ).sum(),

            "insufficient_minutes": (
                status
                == STATUS_INSUFFICIENT_MINUTES
            ).sum(),

            "insufficient_metrics": (
                status
                == STATUS_INSUFFICIENT_METRICS
            ).sum(),

            "insufficient_group": (
                status
                == STATUS_INSUFFICIENT_GROUP
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
# VALIDATION PERCENTILES
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


# ============================================================================
# VALIDATION NORMALISATION PAR GROUPE
# ============================================================================


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
        GROUP_COLUMNS,
        dropna=False,
    ):

        position, level, season = (
            group_values
        )

        percentiles = group[
            "performance_percentile"
        ]

        print(
            f"{str(position):<5} | "
            f"{str(level):<12} | "
            f"{str(season):<8} | "
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


# ============================================================================
# VALIDATION COMPOSANTES
# ============================================================================


def validate_score_components(
    dataset: pd.DataFrame,
) -> bool:
    """
    Vérifie les pondérations du score.
    """

    print()
    print(
        "VALIDATION COMPOSANTES DU SCORE"
    )
    print("-" * 70)

    for column, weight in SCORE_COMPONENTS.items():

        print(
            f"{column:<15}: "
            f"{weight * 100:.0f} %"
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
# TEST CAS LIMITE : MINUTES INSUFFISANTES
# ============================================================================


def validate_insufficient_minutes(
    scorer: PerformanceScorer,
) -> bool:
    """
    Vérifie qu'un joueur sous le seuil de minutes
    ne reçoit ni score ni percentile.
    """

    print()
    print(
        "TEST CAS LIMITE : MINUTES INSUFFISANTES"
    )
    print("-" * 70)

    df = pd.DataFrame(
        [
            {
                "player": "Low Minutes Player",
                "season": "2023/24",
                "season_start_date": "2023-08-01",
                "season_end_date": "2024-05-31",
                "competition": "Ligue 1",
                "competition_level": "TOP_5",
                "team": "Test FC",
                "position": "FW",
                "minutes": 899,
                "appearances": 15,
                "starts": 5,
                "goals": 3,
                "assists": 2,
                "xg": 2.5,
                "xa": 1.5,
                "goals_per90": 0.30,
                "assists_per90": 0.20,
                "xg_per90": 0.25,
                "xa_per90": 0.15,
            }
        ]
    )

    test_scorer = PerformanceScorer(
        df,
        min_minutes=scorer.min_minutes,
    )

    result = test_scorer.calculate_scores()

    row = result.iloc[0]

    success = (
        row["performance_score_status"]
        == STATUS_INSUFFICIENT_MINUTES
        and pd.isna(
            row["performance_score"]
        )
        and pd.isna(
            row["performance_percentile"]
        )
    )

    if success:

        print(
            "✓ Joueur sous le seuil correctement exclu."
        )

    else:

        print(
            "✗ Erreur sur le traitement des minutes."
        )

    return bool(success)


# ============================================================================
# TEST CAS LIMITE : METRIQUES MANQUANTES
# ============================================================================


def validate_missing_metrics(
    scorer: PerformanceScorer,
) -> bool:
    """
    Vérifie :

    1. toutes les métriques manquantes
    2. une seule métrique disponible
    3. renormalisation des poids
    """

    print()
    print(
        "TEST CAS LIMITE : METRIQUES MANQUANTES"
    )
    print("-" * 70)

    base = {
        "season": "2023/24",
        "season_start_date": "2023-08-01",
        "season_end_date": "2024-05-31",
        "competition": "Ligue 1",
        "competition_level": "TOP_5",
        "team": "Test FC",
        "position": "FW",
        "minutes": 1800,
        "appearances": 25,
        "starts": 20,
        "goals": 10,
        "assists": 5,
        "xg": 9,
        "xa": 4,
    }

    rows = []

    # ------------------------------------------------------------------------
    # Toutes les métriques manquantes
    # ------------------------------------------------------------------------

    row_all_missing = base.copy()

    row_all_missing.update(
        {
            "player": "All Metrics Missing",
            "goals_per90": np.nan,
            "assists_per90": np.nan,
            "xg_per90": np.nan,
            "xa_per90": np.nan,
        }
    )

    rows.append(row_all_missing)

    # ------------------------------------------------------------------------
    # Une seule métrique disponible
    # ------------------------------------------------------------------------

    row_one_metric = base.copy()

    row_one_metric.update(
        {
            "player": "One Metric Available",
            "goals_per90": 0.80,
            "assists_per90": np.nan,
            "xg_per90": np.nan,
            "xa_per90": np.nan,
        }
    )

    rows.append(row_one_metric)

    test_scorer = PerformanceScorer(
        pd.DataFrame(rows),
        min_minutes=scorer.min_minutes,
    )

    result = test_scorer.calculate_scores()

    missing_row = result[
        result["player"]
        == "All Metrics Missing"
    ].iloc[0]

    one_metric_row = result[
        result["player"]
        == "One Metric Available"
    ].iloc[0]

    # Avec une seule métrique :
    #
    # score = (0.80 * 0.30) / 0.30
    #
    # donc :
    #
    # score = 0.80

    expected_one_metric_score = 0.80

    success_missing = (
        missing_row[
            "performance_score_status"
        ]
        == STATUS_INSUFFICIENT_METRICS
        and pd.isna(
            missing_row[
                "performance_score"
            ]
        )
    )

    success_renormalization = (
        one_metric_row[
            "performance_score_status"
        ]
        == STATUS_ELIGIBLE
        and abs(
            one_metric_row[
                "performance_score"
            ]
            - expected_one_metric_score
        )
        < 1e-6
    )

    if success_missing:

        print(
            "✓ Toutes les métriques manquantes "
            "-> INSUFFICIENT_METRICS."
        )

    else:

        print(
            "✗ Erreur sur les métriques entièrement manquantes."
        )

    if success_renormalization:

        print(
            "✓ Renormalisation des poids correcte."
        )

    else:

        print(
            "✗ Erreur de renormalisation."
        )

    return bool(
        success_missing
        and success_renormalization
    )


# ============================================================================
# TEST CAS LIMITE : GROUPE UNIQUE
# ============================================================================


def validate_single_player_group() -> bool:
    """
    Vérifie qu'un groupe contenant un seul joueur
    reçoit le percentile 0.5.
    """

    print()
    print(
        "TEST CAS LIMITE : GROUPE AVEC UN SEUL JOUEUR"
    )
    print("-" * 70)

    row = {
        "player": "Single Player",
        "season": "2023/24",
        "season_start_date": "2023-08-01",
        "season_end_date": "2024-05-31",
        "competition": "Ligue 1",
        "competition_level": "TOP_5",
        "team": "Test FC",
        "position": "FW",
        "minutes": 1800,
        "appearances": 25,
        "starts": 20,
        "goals": 10,
        "assists": 5,
        "xg": 9,
        "xa": 4,
        "goals_per90": 0.80,
        "assists_per90": 0.30,
        "xg_per90": 0.70,
        "xa_per90": 0.30,
    }

    scorer = PerformanceScorer(
        pd.DataFrame([row])
    )

    result = scorer.calculate_scores()

    percentile = result.iloc[0][
        "performance_percentile"
    ]

    success = (
        abs(percentile - 0.5)
        < 1e-9
    )

    if success:

        print(
            "✓ Groupe singleton -> percentile 0.5."
        )

    else:

        print(
            f"✗ Percentile obtenu : {percentile}"
        )

    return bool(success)


# ============================================================================
# TEST CAS LIMITE : EX-AEQUO
# ============================================================================


def validate_ties() -> bool:
    """
    Vérifie que deux joueurs ayant exactement le même score
    obtiennent le même percentile.
    """

    print()
    print(
        "TEST CAS LIMITE : EX-AEQUO"
    )
    print("-" * 70)

    base = {
        "season": "2023/24",
        "season_start_date": "2023-08-01",
        "season_end_date": "2024-05-31",
        "competition": "Ligue 1",
        "competition_level": "TOP_5",
        "team": "Test FC",
        "position": "FW",
        "minutes": 1800,
        "appearances": 25,
        "starts": 20,
        "goals": 10,
        "assists": 5,
        "xg": 9,
        "xa": 4,
        "goals_per90": 0.60,
        "assists_per90": 0.30,
        "xg_per90": 0.60,
        "xa_per90": 0.30,
    }

    rows = []

    for player in [
        "Tie Player A",
        "Tie Player B",
        "Higher Player",
    ]:

        row = base.copy()

        row["player"] = player

        if player == "Higher Player":

            row["goals_per90"] = 1.00
            row["assists_per90"] = 0.50
            row["xg_per90"] = 0.90
            row["xa_per90"] = 0.50

        rows.append(row)

    scorer = PerformanceScorer(
        pd.DataFrame(rows)
    )

    result = scorer.calculate_scores()

    a = result[
        result["player"]
        == "Tie Player A"
    ].iloc[0]

    b = result[
        result["player"]
        == "Tie Player B"
    ].iloc[0]

    higher = result[
        result["player"]
        == "Higher Player"
    ].iloc[0]

    success = (
        abs(
            a["performance_score"]
            - b["performance_score"]
        )
        < 1e-9
        and abs(
            a["performance_percentile"]
            - b["performance_percentile"]
        )
        < 1e-9
        and higher[
            "performance_percentile"
        ]
        > a[
            "performance_percentile"
        ]
    )

    if success:

        print(
            "✓ Ex-aequo correctement gérés."
        )

    else:

        print(
            "✗ Erreur dans la gestion des ex-aequo."
        )

    return bool(success)


# ============================================================================
# TEST CAS LIMITE : JOUEUR NON ELIGIBLE EXCLU DU PERCENTILE
# ============================================================================


def validate_ineligible_excluded_from_percentile() -> bool:
    """
    Vérifie qu'un joueur sous le seuil de minutes
    n'influence pas le percentile des joueurs éligibles.
    """

    print()
    print(
        "TEST CAS LIMITE : EXCLUSION DES NON ELIGIBLES"
    )
    print("-" * 70)

    base = {
        "season": "2023/24",
        "season_start_date": "2023-08-01",
        "season_end_date": "2024-05-31",
        "competition": "Ligue 1",
        "competition_level": "TOP_5",
        "team": "Test FC",
        "position": "FW",
        "appearances": 20,
        "starts": 15,
        "goals": 5,
        "assists": 3,
        "xg": 5,
        "xa": 3,
        "goals_per90": 0.50,
        "assists_per90": 0.30,
        "xg_per90": 0.50,
        "xa_per90": 0.30,
    }

    rows = []

    # ------------------------------------------------------------------------
    # Joueur faible mais non éligible
    # ------------------------------------------------------------------------

    low = base.copy()

    low.update(
        {
            "player": "Low Minutes",
            "minutes": 100,
            "goals_per90": 0.01,
            "assists_per90": 0.01,
            "xg_per90": 0.01,
            "xa_per90": 0.01,
        }
    )

    rows.append(low)

    # ------------------------------------------------------------------------
    # Joueur éligible
    # ------------------------------------------------------------------------

    eligible = base.copy()

    eligible.update(
        {
            "player": "Eligible Player",
            "minutes": 1800,
        }
    )

    rows.append(eligible)

    scorer = PerformanceScorer(
        pd.DataFrame(rows)
    )

    result = scorer.calculate_scores()

    low_result = result[
        result["player"]
        == "Low Minutes"
    ].iloc[0]

    eligible_result = result[
        result["player"]
        == "Eligible Player"
    ].iloc[0]

    success = (
        low_result[
            "performance_score_status"
        ]
        == STATUS_INSUFFICIENT_MINUTES
        and pd.isna(
            low_result[
                "performance_percentile"
            ]
        )
        and abs(
            eligible_result[
                "performance_percentile"
            ]
            - 0.5
        )
        < 1e-9
    )

    if success:

        print(
            "✓ Les joueurs non éligibles sont exclus du percentile."
        )

    else:

        print(
            "✗ Un joueur non éligible influence le percentile."
        )

    return bool(success)


# ============================================================================
# TEST CAS LIMITE : GROUPE INCOMPLET
# ============================================================================


def validate_missing_group() -> bool:
    """
    Vérifie qu'un joueur dont le groupe est incomplet
    ne reçoit pas de percentile.
    """

    print()
    print(
        "TEST CAS LIMITE : GROUPE INCOMPLET"
    )
    print("-" * 70)

    row = {
        "player": "Missing Group Player",
        "season": "2023/24",
        "season_start_date": "2023-08-01",
        "season_end_date": "2024-05-31",
        "competition": "Ligue 1",
        "competition_level": "TOP_5",
        "team": "Test FC",
        "position": np.nan,
        "minutes": 1800,
        "appearances": 25,
        "starts": 20,
        "goals": 10,
        "assists": 5,
        "xg": 9,
        "xa": 4,
        "goals_per90": 0.80,
        "assists_per90": 0.30,
        "xg_per90": 0.70,
        "xa_per90": 0.30,
    }

    scorer = PerformanceScorer(
        pd.DataFrame([row])
    )

    result = scorer.calculate_scores()

    output = result.iloc[0]

    success = (
        output[
            "performance_score_status"
        ]
        == STATUS_INSUFFICIENT_GROUP
        and pd.notna(
            output[
                "performance_score"
            ]
        )
        and pd.isna(
            output[
                "performance_percentile"
            ]
        )
    )

    if success:

        print(
            "✓ Groupe incomplet correctement détecté."
        )

    else:

        print(
            "✗ Erreur dans la gestion du groupe incomplet."
        )

    return bool(success)


# ============================================================================
# TEST PRINCIPAL
# ============================================================================


def run_test() -> None:
    """
    Test complet du PerformanceScorer.

    Inclut :

        1. test nominal
        2. minutes insuffisantes
        3. métriques manquantes
        4. groupe singleton
        5. ex-aequo
        6. exclusion des non éligibles
        7. groupe incomplet
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
    # CHARGEMENT DATASET NOMINAL
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
    # VALIDATIONS NOMINALES
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
    # TESTS CAS LIMITES
    # ========================================================================

    edge_minutes_ok = (
        validate_insufficient_minutes(
            scorer
        )
    )

    edge_metrics_ok = (
        validate_missing_metrics(
            scorer
        )
    )

    edge_singleton_ok = (
        validate_single_player_group()
    )

    edge_ties_ok = (
        validate_ties()
    )

    edge_exclusion_ok = (
        validate_ineligible_excluded_from_percentile()
    )

    edge_group_ok = (
        validate_missing_group()
    )

    # ========================================================================
    # RESULTAT TESTS CAS LIMITES
    # ========================================================================

    print()
    print(
        "RÉSUMÉ DES TESTS CAS LIMITES"
    )
    print("-" * 70)

    edge_tests = {
        "minutes insuffisantes": edge_minutes_ok,
        "métriques manquantes": edge_metrics_ok,
        "groupe singleton": edge_singleton_ok,
        "ex-aequo": edge_ties_ok,
        "exclusion non éligibles": edge_exclusion_ok,
        "groupe incomplet": edge_group_ok,
    }

    for name, success in edge_tests.items():

        print(
            f"{name:<35}: "
            f"{'✓ PASS' if success else '✗ FAIL'}"
        )

    all_edge_tests_ok = all(
        edge_tests.values()
    )

    # ========================================================================
    # SAVE
    #
    # On sauvegarde uniquement le dataset nominal.
    # ========================================================================

    output_path = scorer.save(
        dataset
    )

    print()
    print(
        f"Dataset exporté : {output_path}"
    )

    # ========================================================================
    # RESULTAT FINAL
    # ========================================================================

    print()

    if (
        percentile_ok
        and normalization_ok
        and components_ok
        and all_edge_tests_ok
    ):

        print(
            "✓ VALIDATION PERFORMANCE SCORER RÉUSSIE"
        )

        print(
            "✓ Tous les cas limites sont validés."
        )

        print(
            "✓ Le scorer est prêt pour l'étape d'intégration."
        )

    else:

        print(
            "✗ VALIDATION PERFORMANCE SCORER ÉCHOUÉE"
        )

        print(
            "✗ Le scorer ne doit pas encore être intégré."
        )

    print()


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":

    run_test()