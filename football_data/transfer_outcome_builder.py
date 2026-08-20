"""
football_data/transfer_outcome_builder.py

Construction de la variable cible historique pour le modèle
de simulation probabiliste des transferts.

Architecture :

    HistoricalTransferLoader
             +
    performances post-transfert
             ↓
    TransferOutcomeBuilder
             ↓
    labelled transfer dataset

Le module distingue :

    1. période d'adaptation
       T → T + 6 mois

    2. période d'évaluation
       T + 6 → T + 18 mois

Le transfert n'est intégré au dataset labellisé que si sa date
est antérieure ou égale à la cutoff_date.

IMPORTANT :
Ce module mesure le SUCCÈS SPORTIF du transfert.
Les variables économiques et la décision de recrutement
restent hors de ce module.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import numpy as np
import pandas as pd


# ============================================================================
# CONFIGURATION
# ============================================================================

@dataclass
class TransferOutcomeConfig:
    """
    Configuration du calcul du Transfer Outcome.
    """

    # ------------------------------------------------------------------
    # CUTOFF
    # ------------------------------------------------------------------

    cutoff_date: str = "2023-12-31"

    # ------------------------------------------------------------------
    # WINDOWS
    # ------------------------------------------------------------------

    adaptation_months: int = 6

    evaluation_months: int = 12

    # ------------------------------------------------------------------
    # WEIGHTS
    # ------------------------------------------------------------------

    playing_time_weight: float = 0.25

    performance_weight: float = 0.25

    availability_weight: float = 0.25

    starter_weight: float = 0.25

    # ------------------------------------------------------------------
    # SUCCESS THRESHOLDS
    # ------------------------------------------------------------------

    success_threshold: float = 0.70

    partial_success_threshold: float = 0.40

    # ------------------------------------------------------------------
    # POSITION NORMALIZATION
    # ------------------------------------------------------------------

    normalize_by_position: bool = True

    normalize_by_league_level: bool = True

    # ------------------------------------------------------------------
    # DATA QUALITY
    # ------------------------------------------------------------------

    minimum_metric_coverage: float = 0.50


# ============================================================================
# BUILDER
# ============================================================================

class TransferOutcomeBuilder:
    """
    Construit les outcomes historiques des transferts.

    Input principal :

        transfers_df
            historique des transferts

        performances_df
            performances du joueur après transfert

    Output :

        DataFrame contenant les variables nécessaires au futur
        modèle probabiliste.
    """

    REQUIRED_TRANSFER_COLUMNS = {
        "player_id",
        "player_name",
        "transfer_date",
    }

    REQUIRED_PERFORMANCE_COLUMNS = {
        "player_id",
        "date",
    }

    PERFORMANCE_COLUMNS = [
        "minutes_played",
        "minutes_available",
        "appearances",
        "starts",
        "matches_available",
    ]

    def __init__(
        self,
        config: Optional[TransferOutcomeConfig] = None,
    ):
        self.config = config or TransferOutcomeConfig()

        self.cutoff_date = pd.Timestamp(
            self.config.cutoff_date
        )

        self._validate_weights()

    # ======================================================================
    # PUBLIC API
    # ======================================================================

    def build(
        self,
        transfers_df: pd.DataFrame,
        performances_df: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Construit le dataset labellisé.

        Parameters
        ----------
        transfers_df:
            Historique des transferts.

        performances_df:
            Performances post-transfert.

        Returns
        -------
        pd.DataFrame
            Dataset avec les scores et labels.
        """

        self._validate_transfer_columns(
            transfers_df
        )

        self._validate_performance_columns(
            performances_df
        )

        transfers = self._prepare_transfers(
            transfers_df
        )

        performances = self._prepare_performances(
            performances_df
        )

        if transfers.empty:
            return pd.DataFrame()

        if performances.empty:
            return self._build_without_performances(
                transfers
            )

        records = []

        for _, transfer in transfers.iterrows():

            outcome = self._build_transfer_outcome(
                transfer,
                performances
            )

            records.append(outcome)

        result = pd.DataFrame(records)

        return self._finalize_dataset(
            result
        )

    # ======================================================================
    # VALIDATION
    # ======================================================================

    def _validate_weights(self):
        """
        Vérifie que les pondérations représentent 100 %.
        """

        weights = [
            self.config.playing_time_weight,
            self.config.performance_weight,
            self.config.availability_weight,
            self.config.starter_weight,
        ]

        total = sum(weights)

        if not np.isclose(
            total,
            1.0,
            atol=1e-6,
        ):
            raise ValueError(
                f"Les poids doivent totaliser 1.0. "
                f"Valeur actuelle : {total}"
            )

    def _validate_transfer_columns(
        self,
        df: pd.DataFrame,
    ):
        missing = (
            self.REQUIRED_TRANSFER_COLUMNS
            - set(df.columns)
        )

        if missing:
            raise ValueError(
                "Colonnes transfert manquantes : "
                f"{sorted(missing)}"
            )

    def _validate_performance_columns(
        self,
        df: pd.DataFrame,
    ):
        missing = (
            self.REQUIRED_PERFORMANCE_COLUMNS
            - set(df.columns)
        )

        if missing:
            raise ValueError(
                "Colonnes performances manquantes : "
                f"{sorted(missing)}"
            )

    # ======================================================================
    # PREPARATION TRANSFERS
    # ======================================================================

    def _prepare_transfers(
        self,
        df: pd.DataFrame,
    ) -> pd.DataFrame:

        transfers = df.copy()

        transfers["transfer_date"] = pd.to_datetime(
            transfers["transfer_date"],
            errors="coerce",
        )

        transfers = transfers.dropna(
            subset=["transfer_date"]
        )

        # --------------------------------------------------------------
        # CUTOFF
        # --------------------------------------------------------------

        transfers = transfers[
            transfers["transfer_date"]
            <= self.cutoff_date
        ]

        if transfers.empty:
            return transfers

        # --------------------------------------------------------------
        # WINDOW DATES
        # --------------------------------------------------------------

        transfers["adaptation_end_date"] = (
            transfers["transfer_date"]
            + pd.DateOffset(
                months=self.config.adaptation_months
            )
        )

        transfers["evaluation_start_date"] = (
            transfers["adaptation_end_date"]
        )

        transfers["evaluation_end_date"] = (
            transfers["evaluation_start_date"]
            + pd.DateOffset(
                months=self.config.evaluation_months
            )
        )

        # --------------------------------------------------------------
        # TRANSFER TYPE
        # --------------------------------------------------------------

        if "is_free_transfer" in transfers.columns:

            transfers["transfer_type"] = np.where(
                transfers["is_free_transfer"],
                "free",
                "permanent",
            )

        if "transfer_type" not in transfers.columns:

            transfers["transfer_type"] = (
                "permanent"
            )

        return transfers

    # ======================================================================
    # PREPARATION PERFORMANCES
    # ======================================================================

    def _prepare_performances(
        self,
        df: pd.DataFrame,
    ) -> pd.DataFrame:

        performances = df.copy()

        performances["date"] = pd.to_datetime(
            performances["date"],
            errors="coerce",
        )

        performances = performances.dropna(
            subset=[
                "player_id",
                "date",
            ]
        )

        # --------------------------------------------------------------
        # NUMERIC CONVERSION
        # --------------------------------------------------------------

        for column in self.PERFORMANCE_COLUMNS:

            if column in performances.columns:

                performances[column] = pd.to_numeric(
                    performances[column],
                    errors="coerce",
                )

        return performances

    # ======================================================================
    # BUILD SINGLE OUTCOME
    # ======================================================================

    def _build_transfer_outcome(
        self,
        transfer: pd.Series,
        performances: pd.DataFrame,
    ) -> dict:
        """
        Construit le label d'un transfert.
        """

        player_id = transfer["player_id"]

        transfer_date = pd.Timestamp(
            transfer["transfer_date"]
        )

        evaluation_start = pd.Timestamp(
            transfer["evaluation_start_date"]
        )

        evaluation_end = pd.Timestamp(
            transfer["evaluation_end_date"]
        )

        # --------------------------------------------------------------
        # PLAYER PERFORMANCE WINDOW
        # --------------------------------------------------------------

        player_data = performances[
            performances["player_id"]
            == player_id
        ].copy()

        evaluation_data = player_data[
            (
                player_data["date"]
                >= evaluation_start
            )
            &
            (
                player_data["date"]
                <= evaluation_end
            )
        ].copy()

        # --------------------------------------------------------------
        # BASIC RESULT
        # --------------------------------------------------------------

        result = {
            "player_id": player_id,

            "player_name":
                transfer.get(
                    "player_name",
                    None,
                ),

            "transfer_date":
                transfer_date,

            "transfer_season":
                transfer.get(
                    "transfer_season",
                    None,
                ),

            "transfer_type":
                transfer.get(
                    "transfer_type",
                    None,
                ),

            "from_club_name":
                transfer.get(
                    "from_club_name",
                    None,
                ),

            "to_club_name":
                transfer.get(
                    "to_club_name",
                    None,
                ),

            "adaptation_end_date":
                evaluation_start,

            "evaluation_start_date":
                evaluation_start,

            "evaluation_end_date":
                evaluation_end,
        }

        # --------------------------------------------------------------
        # NO PERFORMANCE DATA
        # --------------------------------------------------------------

        if evaluation_data.empty:

            return self._empty_outcome(
                result
            )

        # --------------------------------------------------------------
        # SCORES
        # --------------------------------------------------------------

        playing_time_score = (
            self._calculate_playing_time(
                evaluation_data
            )
        )

        performance_score = (
            self._calculate_performance(
                evaluation_data
            )
        )

        availability_score = (
            self._calculate_availability(
                evaluation_data
            )
        )

        starter_score = (
            self._calculate_starter_status(
                evaluation_data
            )
        )

        # --------------------------------------------------------------
        # GLOBAL SCORE
        # --------------------------------------------------------------

        scores = {
            "playing_time_score":
                playing_time_score,

            "performance_score":
                performance_score,

            "availability_score":
                availability_score,

            "starter_score":
                starter_score,
        }

        success_score = (
            self._calculate_success_score(
                scores
            )
        )

        # --------------------------------------------------------------
        # OUTCOME
        # --------------------------------------------------------------

        outcome = self._classify_outcome(
            success_score
        )

        # --------------------------------------------------------------
        # RETENTION INFORMATION
        # --------------------------------------------------------------

        retention = (
            self._extract_retention_variables(
                transfer,
                evaluation_data,
            )
        )

        result.update(scores)

        result.update({
            "success_score":
                success_score,

            "success":
                int(
                    success_score
                    >= self.config.success_threshold
                ),

            "transfer_outcome":
                outcome,
        })

        result.update(retention)

        return result

    # ======================================================================
    # PLAYING TIME
    # ======================================================================

    def _calculate_playing_time(
        self,
        df: pd.DataFrame,
    ) -> float:

        if "minutes_played" not in df.columns:
            return np.nan

        minutes_played = (
            df["minutes_played"]
            .fillna(0)
            .sum()
        )

        if "minutes_available" in df.columns:

            minutes_available = (
                df["minutes_available"]
                .fillna(0)
                .sum()
            )

        else:

            minutes_available = 0

        if minutes_available <= 0:

            return np.nan

        score = (
            minutes_played
            / minutes_available
        )

        return self._clip(score)

    # ======================================================================
    # PERFORMANCE
    # ======================================================================

    def _calculate_performance(
        self,
        df: pd.DataFrame,
    ) -> float:
        """
        Calcule un score de performance normalisé.

        Priorité :

        1. performance_percentile
        2. performance_score
        3. percentile calculé localement

        La normalisation position / niveau de championnat
        doit idéalement avoir été préparée en amont.
        """

        if "performance_percentile" in df.columns:

            values = pd.to_numeric(
                df["performance_percentile"],
                errors="coerce",
            )

            value = values.mean()

            if pd.notna(value):
                return self._clip(value)

        if "performance_score" in df.columns:

            values = pd.to_numeric(
                df["performance_score"],
                errors="coerce",
            )

            value = values.mean()

            if pd.notna(value):
                return self._clip(value)

        # --------------------------------------------------------------
        # FALLBACK
        # --------------------------------------------------------------

        return self._calculate_fallback_performance(
            df
        )

    def _calculate_fallback_performance(
        self,
        df: pd.DataFrame,
    ) -> float:
        """
        Fallback volontairement conservateur.

        Si aucune variable de performance normalisée
        n'est disponible, on ne fabrique pas artificiellement
        un score.

        On utilise éventuellement un score déjà fourni
        dans le dataset.
        """

        performance_columns = [
            "performance_percentile",
            "performance_score",
        ]

        available = [
            column
            for column in performance_columns
            if column in df.columns
        ]

        if not available:
            return np.nan

        return np.nan

    # ======================================================================
    # AVAILABILITY
    # ======================================================================

    def _calculate_availability(
        self,
        df: pd.DataFrame,
    ) -> float:

        if "matches_available" in df.columns:

            available = (
                df["matches_available"]
                .fillna(0)
                .sum()
            )

            if "matches_total" in df.columns:

                total = (
                    df["matches_total"]
                    .fillna(0)
                    .sum()
                )

            else:

                total = (
                    df["matches_available"]
                    .fillna(0)
                    .sum()
                )

            if total > 0:

                return self._clip(
                    available / total
                )

        # --------------------------------------------------------------
        # FALLBACK : MINUTES
        # --------------------------------------------------------------

        if (
            "minutes_played" in df.columns
            and "minutes_available" in df.columns
        ):

            minutes_played = (
                df["minutes_played"]
                .fillna(0)
                .sum()
            )

            minutes_available = (
                df["minutes_available"]
                .fillna(0)
                .sum()
            )

            if minutes_available > 0:

                return self._clip(
                    minutes_played
                    / minutes_available
                )

        return np.nan

    # ======================================================================
    # STARTER STATUS
    # ======================================================================

    def _calculate_starter_status(
        self,
        df: pd.DataFrame,
    ) -> float:

        if (
            "starts" not in df.columns
            or "appearances" not in df.columns
        ):
            return np.nan

        starts = (
            df["starts"]
            .fillna(0)
            .sum()
        )

        appearances = (
            df["appearances"]
            .fillna(0)
            .sum()
        )

        if appearances <= 0:

            return np.nan

        return self._clip(
            starts / appearances
        )

    # ======================================================================
    # SUCCESS SCORE
    # ======================================================================

    def _calculate_success_score(
        self,
        scores: dict,
    ) -> float:
        """
        Calcule le score final.

        Si certaines dimensions sont manquantes,
        les poids disponibles sont renormalisés.

        Cela évite de considérer automatiquement
        un joueur comme mauvais simplement parce
        qu'une source de données est incomplète.
        """

        weights = {
            "playing_time_score":
                self.config.playing_time_weight,

            "performance_score":
                self.config.performance_weight,

            "availability_score":
                self.config.availability_weight,

            "starter_score":
                self.config.starter_weight,
        }

        weighted_sum = 0.0
        weight_sum = 0.0

        for metric, value in scores.items():

            if pd.isna(value):
                continue

            weight = weights[metric]

            weighted_sum += (
                float(value)
                * weight
            )

            weight_sum += weight

        if weight_sum <= 0:
            return np.nan

        score = (
            weighted_sum
            / weight_sum
        )

        return round(
            self._clip(score),
            4,
        )

    # ======================================================================
    # CLASSIFICATION
    # ======================================================================

    def _classify_outcome(
        self,
        score: float,
    ) -> Optional[str]:

        if pd.isna(score):
            return None

        if (
            score
            >= self.config.success_threshold
        ):
            return "SUCCESS"

        if (
            score
            >= self.config.partial_success_threshold
        ):
            return "PARTIAL_SUCCESS"

        return "FAILURE"

    # ======================================================================
    # RETENTION
    # ======================================================================

    def _extract_retention_variables(
        self,
        transfer: pd.Series,
        performance_df: pd.DataFrame,
    ) -> dict:
        """
        Variables contextuelles liées à la conservation du joueur.

        Elles ne participent PAS au success_score.
        """

        result = {
            "retained_after_loan": None,
            "option_exercised": None,
            "contract_extended": None,
        }

        for column in result:

            if column in transfer.index:

                result[column] = transfer[column]

        return result

    # ======================================================================
    # EMPTY OUTCOME
    # ======================================================================

    def _empty_outcome(
        self,
        result: dict,
    ) -> dict:

        result.update({

            "playing_time_score":
                np.nan,

            "performance_score":
                np.nan,

            "availability_score":
                np.nan,

            "starter_score":
                np.nan,

            "success_score":
                np.nan,

            "success":
                None,

            "transfer_outcome":
                None,

            "retained_after_loan":
                None,

            "option_exercised":
                None,

            "contract_extended":
                None,

        })

        return result

    # ======================================================================
    # NO PERFORMANCE DATA
    # ======================================================================

    def _build_without_performances(
        self,
        transfers: pd.DataFrame,
    ) -> pd.DataFrame:

        records = []

        for _, transfer in transfers.iterrows():

            result = {

                "player_id":
                    transfer["player_id"],

                "player_name":
                    transfer.get(
                        "player_name",
                        None,
                    ),

                "transfer_date":
                    transfer["transfer_date"],

                "transfer_season":
                    transfer.get(
                        "transfer_season",
                        None,
                    ),

                "transfer_type":
                    transfer.get(
                        "transfer_type",
                        None,
                    ),

                "from_club_name":
                    transfer.get(
                        "from_club_name",
                        None,
                    ),

                "to_club_name":
                    transfer.get(
                        "to_club_name",
                        None,
                    ),

                "adaptation_end_date":
                    transfer[
                        "adaptation_end_date"
                    ],

                "evaluation_start_date":
                    transfer[
                        "evaluation_start_date"
                    ],

                "evaluation_end_date":
                    transfer[
                        "evaluation_end_date"
                    ],

                "playing_time_score":
                    np.nan,

                "performance_score":
                    np.nan,

                "availability_score":
                    np.nan,

                "starter_score":
                    np.nan,

                "success_score":
                    np.nan,

                "success":
                    None,

                "transfer_outcome":
                    None,

                "retained_after_loan":
                    None,

                "option_exercised":
                    None,

                "contract_extended":
                    None,
            }

            records.append(result)

        return pd.DataFrame(records)

    # ======================================================================
    # FINALIZATION
    # ======================================================================

    def _finalize_dataset(
        self,
        df: pd.DataFrame,
    ) -> pd.DataFrame:

        if df.empty:
            return df

        df = df.copy()

        df["transfer_date"] = pd.to_datetime(
            df["transfer_date"],
            errors="coerce",
        )

        df["evaluation_start_date"] = (
            pd.to_datetime(
                df["evaluation_start_date"],
                errors="coerce",
            )
        )

        df["evaluation_end_date"] = (
            pd.to_datetime(
                df["evaluation_end_date"],
                errors="coerce",
            )
        )

        # --------------------------------------------------------------
        # SORT
        # --------------------------------------------------------------

        df = df.sort_values(
            [
                "transfer_date",
                "player_id",
            ]
        )

        # --------------------------------------------------------------
        # RESET INDEX
        # --------------------------------------------------------------

        df = df.reset_index(
            drop=True
        )

        return df

    # ======================================================================
    # UTILITY
    # ======================================================================

    @staticmethod
    def _clip(
        value: float,
    ) -> float:

        return float(
            np.clip(
                value,
                0.0,
                1.0,
            )
        )

    # ======================================================================
    # REPORT
    # ======================================================================

    def summary(
        self,
        df: pd.DataFrame,
    ) -> dict:

        if df.empty:

            return {
                "rows": 0
            }

        summary = {
            "rows":
                len(df),

            "unique_players":
                df["player_id"]
                .nunique(),

            "cutoff_date":
                str(
                    self.cutoff_date.date()
                ),

            "successes":
                int(
                    (
                        df["transfer_outcome"]
                        == "SUCCESS"
                    ).sum()
                ),

            "partial_successes":
                int(
                    (
                        df["transfer_outcome"]
                        == "PARTIAL_SUCCESS"
                    ).sum()
                ),

            "failures":
                int(
                    (
                        df["transfer_outcome"]
                        == "FAILURE"
                    ).sum()
                ),

            "unlabelled":
                int(
                    df["transfer_outcome"]
                    .isna()
                    .sum()
                ),
        }

        if "transfer_type" in df.columns:

            summary["transfer_types"] = (
                df["transfer_type"]
                .value_counts(dropna=False)
                .to_dict()
            )

        return summary


# ============================================================================
# DEMO / TEST
# ============================================================================

def _build_test_transfers() -> pd.DataFrame:

    return pd.DataFrame({

        "player_id": [
            1,
            2,
            3,
        ],

        "player_name": [
            "Player Success",
            "Player Partial",
            "Player Failure",
        ],

        "transfer_date": [
            "2023-07-01",
            "2023-07-01",
            "2023-07-01",
        ],

        "transfer_season": [
            "23/24",
            "23/24",
            "23/24",
        ],

        "from_club_name": [
            "Club A",
            "Club B",
            "Club C",
        ],

        "to_club_name": [
            "Club X",
            "Club X",
            "Club X",
        ],

        "is_free_transfer": [
            False,
            True,
            False,
        ],

        "transfer_type": [
            "permanent",
            "free",
            "loan",
        ],
    })


def _build_test_performances() -> pd.DataFrame:
    """
    Dataset synthétique uniquement destiné au test
    du builder.

    Dans la plateforme réelle, ces données viendront
    des loaders de performances.
    """

    return pd.DataFrame({

        "player_id": [
            1,
            2,
            3,
        ],

        "date": [
            "2024-02-01",
            "2024-02-01",
            "2024-02-01",
        ],

        "minutes_played": [
            2700,
            1500,
            500,
        ],

        "minutes_available": [
            3000,
            3000,
            3000,
        ],

        "appearances": [
            30,
            24,
            15,
        ],

        "starts": [
            27,
            12,
            3,
        ],

        "matches_available": [
            30,
            30,
            30,
        ],

        "matches_total": [
            30,
            30,
            30,
        ],

        "performance_percentile": [
            0.90,
            0.55,
            0.20,
        ],
    })


# ============================================================================
# MAIN TEST
# ============================================================================

if __name__ == "__main__":

    print()
    print("=" * 70)
    print("TEST TRANSFER OUTCOME BUILDER")
    print("=" * 70)

    transfers = _build_test_transfers()

    performances = _build_test_performances()

    config = TransferOutcomeConfig(
        cutoff_date="2023-12-31",
        adaptation_months=6,
        evaluation_months=12,
    )

    builder = TransferOutcomeBuilder(
        config=config
    )

    result = builder.build(
        transfers_df=transfers,
        performances_df=performances,
    )

    print()
    print("RESULT")
    print("-" * 70)

    columns = [
        "player_name",
        "transfer_type",
        "playing_time_score",
        "performance_score",
        "availability_score",
        "starter_score",
        "success_score",
        "transfer_outcome",
    ]

    print(
        result[columns].to_string(
            index=False
        )
    )

    print()
    print("SUMMARY")
    print("-" * 70)

    summary = builder.summary(
        result
    )

    for key, value in summary.items():

        print(
            f"{key:25}: {value}"
        )

    print()
    print("=" * 70)
    print("TEST TERMINE")
    print("=" * 70)