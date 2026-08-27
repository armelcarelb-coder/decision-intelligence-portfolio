"""
football_data/transfer_performance_builder.py

Construction du dataset historique de performance des transferts.

Architecture
------------

HistoricalTransferLoader
        +
PerformanceLoader
        |
        v
TransferPerformanceBuilder
        |
        +--> fenêtre PRE  : 36 mois avant transfert
        |
        +--> fenêtre POST : 18 mois après transfert
        |
        +--> contexte position + niveau de championnat
        |
        v
Dataset transfert / performances
        |
        v
Future PerformanceNormalizer
        |
        v
Future TransferOutcomeBuilder


Méthodologie
------------

PRE
---
36 mois avant la date du transfert.

POST
----
18 mois après la date du transfert.

Important
---------
Les performances sont agrégées par saison.

Nous utilisons les vraies dates :

    season_start_date
    season_end_date

fournies par PerformanceLoader.

Une saison PRE est retenue si elle est entièrement
située avant le transfert et qu'elle intersecte
la fenêtre des 36 mois.

Une saison POST est retenue si elle commence après
le transfert et qu'elle intersecte la fenêtre des
18 mois.

La saison contenant le transfert est volontairement
exclue afin d'éviter le mélange entre performance
pré-transfert et post-transfert.

Le percentile de performance est calculé ici au niveau
saison + position + niveau de championnat.

Cependant, cette étape reste préparatoire :

    performance_percentile

sera ensuite amélioré avec le futur PerformanceNormalizer
lorsque nous disposerons d'un véritable dataset FBref
suffisamment large.

Le builder ne dépend donc pas d'une valeur artificielle
de percentile lorsque le groupe de comparaison est trop
petit.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd


# ============================================================================
# CONFIGURATION
# ============================================================================

@dataclass
class TransferPerformanceConfig:
    """
    Configuration méthodologique du builder.
    """

    # ------------------------------------------------------------------
    # Fenêtres temporelles
    # ------------------------------------------------------------------

    pre_months: int = 36
    post_months: int = 18

    # ------------------------------------------------------------------
    # Minimums de données
    # ------------------------------------------------------------------

    min_pre_minutes: int = 900
    min_post_minutes: int = 450

    min_pre_seasons: int = 1
    min_post_seasons: int = 1

    # ------------------------------------------------------------------
    # Métriques de performance
    # ------------------------------------------------------------------

    performance_metrics: tuple[str, ...] = (
        "goals_per90",
        "assists_per90",
        "xg_per90",
        "xa_per90",
    )

    # ------------------------------------------------------------------
    # Poids du score de performance
    # ------------------------------------------------------------------

    metric_weights: Optional[dict[str, float]] = None

    # ------------------------------------------------------------------
    # Valeurs inconnues
    # ------------------------------------------------------------------

    unknown_competition_level: str = "UNKNOWN"
    unknown_position: str = "UNKNOWN"

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    output_path: str = (
        "data/performances/transfer_performance_dataset.csv"
    )

    def __post_init__(self) -> None:

        if self.metric_weights is None:
            self.metric_weights = {
                "goals_per90": 0.30,
                "assists_per90": 0.20,
                "xg_per90": 0.30,
                "xa_per90": 0.20,
            }

        # Vérification des poids

        total_weight = sum(
            self.metric_weights.get(metric, 0.0)
            for metric in self.performance_metrics
        )

        if total_weight <= 0:
            raise ValueError(
                "La somme des poids des métriques doit être > 0."
            )


# ============================================================================
# BUILDER
# ============================================================================

class TransferPerformanceBuilder:
    """
    Construit le dataset de performances PRE / POST transfert.
    """

    def __init__(
        self,
        transfers: Optional[pd.DataFrame] = None,
        performances: Optional[pd.DataFrame] = None,
        config: Optional[TransferPerformanceConfig] = None,
    ):
        self.transfers = transfers
        self.performances = performances

        self.config = (
            config
            if config is not None
            else TransferPerformanceConfig()
        )

        self.dataset: Optional[pd.DataFrame] = None

    # ======================================================================
    # PUBLIC API
    # ======================================================================

    def build(
        self,
        transfers: Optional[pd.DataFrame] = None,
        performances: Optional[pd.DataFrame] = None,
    ) -> pd.DataFrame:
        """
        Construit le dataset transfert + performances PRE/POST.
        """

        if transfers is not None:
            self.transfers = transfers

        if performances is not None:
            self.performances = performances

        if self.transfers is None:
            raise ValueError(
                "Les données de transferts sont obligatoires."
            )

        if self.performances is None:
            raise ValueError(
                "Les données de performances sont obligatoires."
            )

        transfers_df = self._prepare_transfers(
            self.transfers.copy()
        )

        performances_df = self._prepare_performances(
            self.performances.copy()
        )

        if transfers_df.empty:
            raise ValueError(
                "Aucun transfert exploitable après préparation."
            )

        if performances_df.empty:
            raise ValueError(
                "Aucune performance exploitable après préparation."
            )

        # --------------------------------------------------------------
        # Percentiles contemporains
        # --------------------------------------------------------------

        performances_df = (
            self._calculate_performance_percentiles(
                performances_df
            )
        )

        # --------------------------------------------------------------
        # Construction du dataset
        # --------------------------------------------------------------

        rows = []

        for _, transfer in transfers_df.iterrows():

            player_id = transfer["player_id"]

            player_perf = performances_df[
                performances_df["player_id"].astype(str)
                == str(player_id)
            ].copy()

            # ----------------------------------------------------------
            # Fallback par nom
            # ----------------------------------------------------------
            #
            # Utile lorsque PerformanceLoader ne possède pas encore
            # l'identifiant Transfermarkt du joueur.
            #

            if player_perf.empty and "player_name" in transfer.index:

                transfer_name = str(
                    transfer["player_name"]
                ).strip().lower()

                player_perf = performances_df[
                    performances_df["player"]
                    .astype(str)
                    .str.strip()
                    .str.lower()
                    == transfer_name
                ].copy()

            if player_perf.empty:
                continue

            pre = self._build_pre_transfer_profile(
                transfer,
                player_perf,
            )

            post = self._build_post_transfer_profile(
                transfer,
                player_perf,
            )

            row = self._merge_transfer_profiles(
                transfer,
                pre,
                post,
            )

            rows.append(row)

        if not rows:

            self.dataset = pd.DataFrame()

            return self.dataset

        self.dataset = pd.DataFrame(rows)

        return self.dataset

    # ======================================================================
    # PREPARE TRANSFERS
    # ======================================================================

    def _prepare_transfers(
        self,
        df: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Prépare les données de transferts.
        """

        required = [
            "player_id",
            "player_name",
            "transfer_date",
        ]

        missing = [
            col
            for col in required
            if col not in df.columns
        ]

        if missing:
            raise ValueError(
                "Colonnes manquantes dans les transferts : "
                + ", ".join(missing)
            )

        df["transfer_date"] = pd.to_datetime(
            df["transfer_date"],
            errors="coerce",
        )

        df = df.dropna(
            subset=[
                "player_id",
                "transfer_date",
            ]
        )

        # --------------------------------------------------------------
        # Destination
        # --------------------------------------------------------------

        if "to_club_name" in df.columns:

            df = df[
                df["to_club_name"]
                .fillna("")
                .astype(str)
                .str.strip()
                != ""
            ]

        # --------------------------------------------------------------
        # Suppression doublons
        # --------------------------------------------------------------

        duplicate_columns = [
            col
            for col in [
                "player_id",
                "transfer_date",
                "from_club_name",
                "to_club_name",
            ]
            if col in df.columns
        ]

        if duplicate_columns:

            df = df.drop_duplicates(
                subset=duplicate_columns,
                keep="first",
            )

        return df.reset_index(drop=True)

    # ======================================================================
    # PREPARE PERFORMANCES
    # ======================================================================

    def _prepare_performances(
        self,
        df: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Prépare le dataset PerformanceLoader.

        Nouveau schéma attendu :

            player
            season
            season_start_date
            season_end_date
            competition
            competition_level
            team
            position
            minutes
            appearances
            starts
            goals
            assists
            xg
            xa
            goals_per90
            assists_per90
            xg_per90
            xa_per90
        """

        required = [
            "player",
            "season",
            "season_start_date",
            "season_end_date",
            "competition",
            "competition_level",
            "team",
            "position",
            "minutes",
            "starts",
            "goals_per90",
            "assists_per90",
            "xg_per90",
            "xa_per90",
        ]

        missing = [
            col
            for col in required
            if col not in df.columns
        ]

        if missing:
            raise ValueError(
                "Colonnes manquantes dans les performances : "
                + ", ".join(missing)
            )

        # --------------------------------------------------------------
        # Identifiant joueur
        # --------------------------------------------------------------

        if "player_id" not in df.columns:

            df["player_id"] = (
                df["player"]
                .astype(str)
                .str.strip()
                .str.lower()
            )

        # --------------------------------------------------------------
        # Dates de saison
        # --------------------------------------------------------------

        df["season_start_date"] = pd.to_datetime(
            df["season_start_date"],
            errors="coerce",
        )

        df["season_end_date"] = pd.to_datetime(
            df["season_end_date"],
            errors="coerce",
        )

        # --------------------------------------------------------------
        # Saison
        # --------------------------------------------------------------

        df["season"] = (
            df["season"]
            .astype(str)
            .str.strip()
        )

        # --------------------------------------------------------------
        # Compétition
        # --------------------------------------------------------------

        df["competition"] = (
            df["competition"]
            .fillna("UNKNOWN")
            .astype(str)
            .str.strip()
        )

        # --------------------------------------------------------------
        # Niveau de championnat
        # --------------------------------------------------------------

        df["competition_level"] = (
            df["competition_level"]
            .fillna(
                self.config.unknown_competition_level
            )
            .astype(str)
            .str.upper()
            .str.strip()
        )

        # --------------------------------------------------------------
        # Position
        # --------------------------------------------------------------

        df["position"] = (
            df["position"]
            .fillna(
                self.config.unknown_position
            )
            .astype(str)
            .str.upper()
            .str.strip()
        )

        # --------------------------------------------------------------
        # Numériques
        # --------------------------------------------------------------

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

        for col in numeric_columns:

            if col in df.columns:

                df[col] = pd.to_numeric(
                    df[col],
                    errors="coerce",
                )

        # --------------------------------------------------------------
        # Sécurité
        # --------------------------------------------------------------

        for col in [
            "minutes",
            "appearances",
            "starts",
        ]:

            df[col] = (
                df[col]
                .fillna(0)
                .clip(lower=0)
            )

        # --------------------------------------------------------------
        # Dates obligatoires
        # --------------------------------------------------------------

        df = df.dropna(
            subset=[
                "season_start_date",
                "season_end_date",
            ]
        )

        # --------------------------------------------------------------
        # Cohérence des dates
        # --------------------------------------------------------------

        df = df[
            df["season_end_date"]
            >= df["season_start_date"]
        ]

        # --------------------------------------------------------------
        # Performances jouables
        # --------------------------------------------------------------

        df = df[
            df["minutes"] > 0
        ]

        return df.reset_index(drop=True)

    # ======================================================================
    # PERCENTILES
    # ======================================================================

    def _calculate_performance_percentiles(
        self,
        df: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Calcule les percentiles contemporains.

        Groupe :

            season
            position
            competition_level

        Remarque importante
        -------------------
        Cette étape est actuellement une première normalisation.

        Avec le vrai dataset FBref, nous disposerons d'un nombre
        beaucoup plus important de joueurs par groupe.

        Lorsqu'un groupe contient un seul joueur, le percentile
        est fixé à 0.50 car aucune comparaison statistique
        n'est possible.
        """

        df = df.copy()

        group_columns = [
            "season",
            "position",
            "competition_level",
        ]

        percentile_columns = []

        # --------------------------------------------------------------
        # Percentile par métrique
        # --------------------------------------------------------------

        for metric in self.config.performance_metrics:

            if metric not in df.columns:
                continue

            percentile_col = (
                f"{metric}_percentile"
            )

            percentile_columns.append(
                percentile_col
            )

            def percentile_rank(group):

                values = pd.to_numeric(
                    group,
                    errors="coerce",
                )

                valid_count = values.notna().sum()

                if valid_count <= 1:

                    return pd.Series(
                        0.50,
                        index=group.index,
                    )

                return values.rank(
                    pct=True,
                    method="average",
                )

            df[percentile_col] = (
                df.groupby(
                    group_columns,
                    dropna=False,
                )[metric]
                .transform(percentile_rank)
            )

        # --------------------------------------------------------------
        # Score pondéré
        # --------------------------------------------------------------

        weighted_sum = pd.Series(
            0.0,
            index=df.index,
        )

        total_weight = pd.Series(
            0.0,
            index=df.index,
        )

        for metric in self.config.performance_metrics:

            percentile_col = (
                f"{metric}_percentile"
            )

            if percentile_col not in df.columns:
                continue

            weight = self.config.metric_weights.get(
                metric,
                0.0,
            )

            valid = (
                df[percentile_col].notna()
            )

            weighted_sum += (
                df[percentile_col]
                .fillna(0.0)
                * weight
            )

            total_weight += (
                valid.astype(float)
                * weight
            )

        df["performance_percentile"] = np.where(
            total_weight > 0,
            weighted_sum / total_weight,
            np.nan,
        )

        df["performance_percentile"] = (
            df["performance_percentile"]
            .clip(0, 1)
        )

        return df

    # ======================================================================
    # PRE TRANSFER
    # ======================================================================

    def _build_pre_transfer_profile(
        self,
        transfer: pd.Series,
        performances: pd.DataFrame,
    ) -> dict:
        """
        Construit le profil PRE.

        Fenêtre :

            transfer_date - 36 mois
            jusqu'à
            transfer_date

        Une saison doit :

            1. être entièrement terminée avant le transfert ;
            2. intersecter la fenêtre PRE.

        La saison contenant le transfert est donc exclue.
        """

        transfer_date = pd.Timestamp(
            transfer["transfer_date"]
        )

        pre_start = (
            transfer_date
            - pd.DateOffset(
                months=self.config.pre_months
            )
        )

        selected = performances[
            (
                performances["season_end_date"]
                < transfer_date
            )
            &
            (
                performances["season_end_date"]
                >= pre_start
            )
        ].copy()

        if selected.empty:

            return self._empty_profile(
                prefix="pre"
            )

        return self._aggregate_profile(
            selected,
            prefix="pre",
        )

    # ======================================================================
    # POST TRANSFER
    # ======================================================================

    def _build_post_transfer_profile(
        self,
        transfer: pd.Series,
        performances: pd.DataFrame,
    ) -> dict:
        """
        Construit le profil POST.

        Fenêtre :

            transfer_date
            jusqu'à
            transfer_date + 18 mois

        Une saison doit commencer après le transfert
        et commencer avant la fin de la fenêtre.

        La saison du transfert est donc exclue.
        """

        transfer_date = pd.Timestamp(
            transfer["transfer_date"]
        )

        post_end = (
            transfer_date
            + pd.DateOffset(
                months=self.config.post_months
            )
        )

        selected = performances[
            (
                performances["season_start_date"]
                > transfer_date
            )
            &
            (
                performances["season_start_date"]
                <= post_end
            )
        ].copy()

        if selected.empty:

            return self._empty_profile(
                prefix="post"
            )

        return self._aggregate_profile(
            selected,
            prefix="post",
        )

    # ======================================================================
    # AGGREGATION
    # ======================================================================

    def _aggregate_profile(
        self,
        df: pd.DataFrame,
        prefix: str,
    ) -> dict:
        """
        Agrège les performances sur plusieurs saisons.

        Les métriques de performance sont pondérées
        par le nombre de minutes.
        """

        result = {}

        # --------------------------------------------------------------
        # Volumes
        # --------------------------------------------------------------

        total_minutes = (
            df["minutes"]
            .fillna(0)
            .sum()
        )

        total_starts = (
            df["starts"]
            .fillna(0)
            .sum()
        )

        total_appearances = (
            df["appearances"]
            .fillna(0)
            .sum()
        )

        # --------------------------------------------------------------
        # Métriques pondérées par minutes
        # --------------------------------------------------------------

        metrics = [
            "goals_per90",
            "assists_per90",
            "xg_per90",
            "xa_per90",
            "performance_percentile",
        ]

        for metric in metrics:

            if metric not in df.columns:
                continue

            values = pd.to_numeric(
                df[metric],
                errors="coerce",
            )

            weights = (
                df["minutes"]
                .fillna(0)
            )

            valid = (
                values.notna()
                & weights.gt(0)
            )

            if valid.any():

                weighted_value = np.average(
                    values[valid],
                    weights=weights[valid],
                )

            else:

                weighted_value = np.nan

            result[
                f"{prefix}_{metric}"
            ] = weighted_value

        # --------------------------------------------------------------
        # Volumes
        # --------------------------------------------------------------

        result[
            f"{prefix}_minutes"
        ] = total_minutes

        result[
            f"{prefix}_appearances"
        ] = total_appearances

        result[
            f"{prefix}_starts"
        ] = total_starts

        # --------------------------------------------------------------
        # Starter rate
        # --------------------------------------------------------------

        if total_appearances > 0:

            result[
                f"{prefix}_starter_rate"
            ] = (
                total_starts
                / total_appearances
            )

        else:

            result[
                f"{prefix}_starter_rate"
            ] = np.nan

        # --------------------------------------------------------------
        # Nombre de saisons
        # --------------------------------------------------------------

        result[
            f"{prefix}_seasons"
        ] = (
            df["season"]
            .nunique()
        )

        # --------------------------------------------------------------
        # Compétitions utilisées
        # --------------------------------------------------------------

        if "competition" in df.columns:

            competitions = (
                df["competition"]
                .dropna()
                .astype(str)
                .unique()
                .tolist()
            )

            result[
                f"{prefix}_competitions"
            ] = "|".join(
                sorted(competitions)
            )

        else:

            result[
                f"{prefix}_competitions"
            ] = ""

        # --------------------------------------------------------------
        # Niveaux de championnat
        # --------------------------------------------------------------

        if "competition_level" in df.columns:

            levels = (
                df["competition_level"]
                .dropna()
                .astype(str)
                .unique()
                .tolist()
            )

            result[
                f"{prefix}_competition_levels"
            ] = "|".join(
                sorted(levels)
            )

        else:

            result[
                f"{prefix}_competition_levels"
            ] = ""

        # --------------------------------------------------------------
        # Positions
        # --------------------------------------------------------------

        if "position" in df.columns:

            positions = (
                df["position"]
                .dropna()
                .astype(str)
                .unique()
                .tolist()
            )

            result[
                f"{prefix}_positions"
            ] = "|".join(
                sorted(positions)
            )

        else:

            result[
                f"{prefix}_positions"
            ] = ""

        # --------------------------------------------------------------
        # Qualité des données
        # --------------------------------------------------------------

        minimum_minutes = (
            self.config.min_pre_minutes
            if prefix == "pre"
            else self.config.min_post_minutes
        )

        minimum_seasons = (
            self.config.min_pre_seasons
            if prefix == "pre"
            else self.config.min_post_seasons
        )

        result[
            f"{prefix}_data_sufficient"
        ] = bool(
            total_minutes >= minimum_minutes
            and
            df["season"].nunique()
            >= minimum_seasons
        )

        # --------------------------------------------------------------
        # Stabilité de la performance
        # --------------------------------------------------------------

        if "performance_percentile" in df.columns:

            values = pd.to_numeric(
                df["performance_percentile"],
                errors="coerce",
            )

            result[
                f"{prefix}_performance_min"
            ] = values.min()

            result[
                f"{prefix}_performance_max"
            ] = values.max()

            result[
                f"{prefix}_performance_std"
            ] = values.std()

        return result

    # ======================================================================
    # EMPTY PROFILE
    # ======================================================================

    @staticmethod
    def _empty_profile(
        prefix: str,
    ) -> dict:
        """
        Profil vide lorsque aucune donnée n'est disponible.
        """

        return {

            f"{prefix}_minutes":
                np.nan,

            f"{prefix}_appearances":
                np.nan,

            f"{prefix}_starts":
                np.nan,

            f"{prefix}_starter_rate":
                np.nan,

            f"{prefix}_goals_per90":
                np.nan,

            f"{prefix}_assists_per90":
                np.nan,

            f"{prefix}_xg_per90":
                np.nan,

            f"{prefix}_xa_per90":
                np.nan,

            f"{prefix}_performance_percentile":
                np.nan,

            f"{prefix}_seasons":
                0,

            f"{prefix}_competitions":
                "",

            f"{prefix}_competition_levels":
                "",

            f"{prefix}_positions":
                "",

            f"{prefix}_data_sufficient":
                False,

            f"{prefix}_performance_min":
                np.nan,

            f"{prefix}_performance_max":
                np.nan,

            f"{prefix}_performance_std":
                np.nan,
        }

    # ======================================================================
    # MERGE
    # ======================================================================

    def _merge_transfer_profiles(
        self,
        transfer: pd.Series,
        pre: dict,
        post: dict,
    ) -> dict:
        """
        Fusionne transfert + profils PRE/POST.
        """

        result = {}

        # --------------------------------------------------------------
        # Informations transfert
        # --------------------------------------------------------------

        transfer_columns = [
            "player_id",
            "player_name",
            "transfer_date",
            "transfer_season",
            "from_club_id",
            "from_club_name",
            "to_club_id",
            "to_club_name",
            "transfer_fee",
            "market_value_in_eur",
            "position",
            "sub_position",
            "age_at_transfer",
            "is_free_transfer",
            "transfer_fee_known",
        ]

        for col in transfer_columns:

            if col in transfer.index:

                result[col] = transfer[col]

        # --------------------------------------------------------------
        # Profiles
        # --------------------------------------------------------------

        result.update(pre)
        result.update(post)

        # --------------------------------------------------------------
        # Delta performance
        # --------------------------------------------------------------

        pre_perf = pre.get(
            "pre_performance_percentile",
            np.nan,
        )

        post_perf = post.get(
            "post_performance_percentile",
            np.nan,
        )

        if (
            pd.notna(pre_perf)
            and
            pd.notna(post_perf)
        ):

            result[
                "performance_percentile_delta"
            ] = (
                post_perf
                - pre_perf
            )

        else:

            result[
                "performance_percentile_delta"
            ] = np.nan

        # --------------------------------------------------------------
        # Delta minutes
        # --------------------------------------------------------------

        pre_minutes = pre.get(
            "pre_minutes",
            np.nan,
        )

        post_minutes = post.get(
            "post_minutes",
            np.nan,
        )

        if (
            pd.notna(pre_minutes)
            and
            pd.notna(post_minutes)
        ):

            result[
                "minutes_delta"
            ] = (
                post_minutes
                - pre_minutes
            )

        else:

            result[
                "minutes_delta"
            ] = np.nan

        # --------------------------------------------------------------
        # Qualité
        # --------------------------------------------------------------

        result[
            "performance_data_quality"
        ] = self._data_quality(
            pre,
            post,
        )

        return result

    # ======================================================================
    # DATA QUALITY
    # ======================================================================

    @staticmethod
    def _data_quality(
        pre: dict,
        post: dict,
    ) -> str:
        """
        Classe la complétude du dossier performance.
        """

        pre_ok = pre.get(
            "pre_data_sufficient",
            False,
        )

        post_ok = post.get(
            "post_data_sufficient",
            False,
        )

        if pre_ok and post_ok:
            return "COMPLETE"

        if pre_ok:
            return "PRE_ONLY"

        if post_ok:
            return "POST_ONLY"

        return "INSUFFICIENT"

    # ======================================================================
    # FILTERS
    # ======================================================================

    def filter_complete_cases(
        self,
    ) -> pd.DataFrame:
        """
        Retourne uniquement les observations
        ayant suffisamment de données PRE et POST.
        """

        if self.dataset is None:

            raise ValueError(
                "Construis d'abord le dataset avec build()."
            )

        return self.dataset[
            self.dataset[
                "performance_data_quality"
            ]
            == "COMPLETE"
        ].copy()

    # ======================================================================
    # SAVE
    # ======================================================================

    def save(
        self,
        path: Optional[str] = None,
    ) -> Path:
        """
        Sauvegarde le dataset au format CSV.
        """

        if self.dataset is None:

            raise ValueError(
                "Aucun dataset à sauvegarder."
            )

        output = Path(
            path
            if path is not None
            else self.config.output_path
        )

        output.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.dataset.to_csv(
            output,
            index=False,
        )

        print(
            "[TransferPerformanceBuilder] "
            f"Dataset sauvegardé : {output}"
        )

        return output

    # ======================================================================
    # SUMMARY
    # ======================================================================

    def summary(self) -> dict:
        """
        Retourne un résumé du dataset construit.
        """

        if self.dataset is None:

            return {
                "rows": 0
            }

        df = self.dataset

        return {

            "rows":
                len(df),

            "unique_players":
                (
                    df["player_id"].nunique()
                    if "player_id" in df.columns
                    else 0
                ),

            "complete_cases":
                int(
                    (
                        df["performance_data_quality"]
                        == "COMPLETE"
                    ).sum()
                ),

            "pre_only":
                int(
                    (
                        df["performance_data_quality"]
                        == "PRE_ONLY"
                    ).sum()
                ),

            "post_only":
                int(
                    (
                        df["performance_data_quality"]
                        == "POST_ONLY"
                    ).sum()
                ),

            "insufficient":
                int(
                    (
                        df["performance_data_quality"]
                        == "INSUFFICIENT"
                    ).sum()
                ),

            "mean_pre_percentile":
                df[
                    "pre_performance_percentile"
                ].mean(),

            "mean_post_percentile":
                df[
                    "post_performance_percentile"
                ].mean(),

            "mean_percentile_delta":
                df[
                    "performance_percentile_delta"
                ].mean(),
        }


# ============================================================================
# TEST DATA
# ============================================================================

def _build_test_transfers() -> pd.DataFrame:
    """
    Jeu de données de test.

    Les transferts sont volontairement placés
    au milieu de la saison 2023/24 afin de vérifier
    que cette saison est exclue du PRE et du POST.
    """

    return pd.DataFrame({

        "player_id": [
            "P001",
            "P002",
        ],

        "player_name": [
            "Test Player",
            "Another Player",
        ],

        "transfer_date": [
            "2023-07-10",
            "2023-07-15",
        ],

        "transfer_season": [
            "23/24",
            "23/24",
        ],

        "from_club_id": [
            "C001",
            "C002",
        ],

        "from_club_name": [
            "Old FC",
            "Other FC",
        ],

        "to_club_id": [
            "C003",
            "C004",
        ],

        "to_club_name": [
            "New FC",
            "New Other FC",
        ],

        "transfer_fee": [
            20_000_000,
            0,
        ],

        "market_value_in_eur": [
            25_000_000,
            8_000_000,
        ],

        "position": [
            "FW",
            "MF",
        ],

        "age_at_transfer": [
            24,
            27,
        ],

        "is_free_transfer": [
            False,
            True,
        ],

        "transfer_fee_known": [
            True,
            True,
        ],
    })


def _build_test_performances() -> pd.DataFrame:
    """
    Dataset de test aligné sur les 19 colonnes
    du nouveau performance_sample.csv.

    Chaque joueur dispose de :

        2020/21
        2021/22
        2022/23
        2023/24
        2024/25

    Pour un transfert en juillet 2023 :

        PRE 36 mois :
            2020/21
            2021/22
            2022/23

        POST 18 mois :
            2024/25

    La saison 2023/24 est volontairement exclue
    car elle contient la date du transfert.
    """

    rows = [

        # ==============================================================
        # TEST PLAYER
        # ==============================================================

        {
            "player_id": "P001",
            "player": "Test Player",
            "season": "2020/21",
            "season_start_date": "2020-08-01",
            "season_end_date": "2021-05-23",
            "competition": "Ligue 1",
            "competition_level": "TOP_5",
            "team": "Old FC",
            "position": "FW",
            "minutes": 1800,
            "appearances": 24,
            "starts": 18,
            "goals": 10,
            "assists": 5,
            "xg": 9.2,
            "xa": 4.1,
            "goals_per90": 0.50,
            "assists_per90": 0.25,
            "xg_per90": 0.46,
            "xa_per90": 0.205,
        },

        {
            "player_id": "P001",
            "player": "Test Player",
            "season": "2021/22",
            "season_start_date": "2021-08-01",
            "season_end_date": "2022-05-23",
            "competition": "Ligue 1",
            "competition_level": "TOP_5",
            "team": "Old FC",
            "position": "FW",
            "minutes": 2400,
            "appearances": 30,
            "starts": 27,
            "goals": 15,
            "assists": 7,
            "xg": 13.5,
            "xa": 6.2,
            "goals_per90": 0.5625,
            "assists_per90": 0.2625,
            "xg_per90": 0.50625,
            "xa_per90": 0.2325,
        },

        {
            "player_id": "P001",
            "player": "Test Player",
            "season": "2022/23",
            "season_start_date": "2022-08-01",
            "season_end_date": "2023-06-03",
            "competition": "Ligue 1",
            "competition_level": "TOP_5",
            "team": "Old FC",
            "position": "FW",
            "minutes": 2700,
            "appearances": 32,
            "starts": 30,
            "goals": 20,
            "assists": 8,
            "xg": 18.5,
            "xa": 7.2,
            "goals_per90": 0.6667,
            "assists_per90": 0.2667,
            "xg_per90": 0.6167,
            "xa_per90": 0.2400,
        },

        # Saison du transfert -> doit être exclue du PRE et POST

        {
            "player_id": "P001",
            "player": "Test Player",
            "season": "2023/24",
            "season_start_date": "2023-08-01",
            "season_end_date": "2024-05-19",
            "competition": "Ligue 1",
            "competition_level": "TOP_5",
            "team": "New FC",
            "position": "FW",
            "minutes": 2500,
            "appearances": 30,
            "starts": 28,
            "goals": 17,
            "assists": 9,
            "xg": 16.8,
            "xa": 8.1,
            "goals_per90": 0.6120,
            "assists_per90": 0.3240,
            "xg_per90": 0.6048,
            "xa_per90": 0.2916,
        },

        {
            "player_id": "P001",
            "player": "Test Player",
            "season": "2024/25",
            "season_start_date": "2024-08-01",
            "season_end_date": "2025-05-25",
            "competition": "Ligue 1",
            "competition_level": "TOP_5",
            "team": "New FC",
            "position": "FW",
            "minutes": 2600,
            "appearances": 31,
            "starts": 29,
            "goals": 19,
            "assists": 10,
            "xg": 18.2,
            "xa": 9.0,
            "goals_per90": 0.6577,
            "assists_per90": 0.3462,
            "xg_per90": 0.6300,
            "xa_per90": 0.3115,
        },

        # ==============================================================
        # ANOTHER PLAYER
        # ==============================================================

        {
            "player_id": "P002",
            "player": "Another Player",
            "season": "2020/21",
            "season_start_date": "2020-08-01",
            "season_end_date": "2021-05-23",
            "competition": "Ligue 2",
            "competition_level": "SECOND_TIER",
            "team": "Other FC",
            "position": "MF",
            "minutes": 2100,
            "appearances": 28,
            "starts": 24,
            "goals": 7,
            "assists": 10,
            "xg": 6.5,
            "xa": 8.9,
            "goals_per90": 0.3000,
            "assists_per90": 0.4286,
            "xg_per90": 0.2786,
            "xa_per90": 0.3814,
        },

        {
            "player_id": "P002",
            "player": "Another Player",
            "season": "2021/22",
            "season_start_date": "2021-08-01",
            "season_end_date": "2022-05-14",
            "competition": "Ligue 2",
            "competition_level": "SECOND_TIER",
            "team": "Other FC",
            "position": "MF",
            "minutes": 2400,
            "appearances": 30,
            "starts": 27,
            "goals": 8,
            "assists": 12,
            "xg": 7.4,
            "xa": 10.2,
            "goals_per90": 0.3000,
            "assists_per90": 0.4500,
            "xg_per90": 0.2775,
            "xa_per90": 0.3825,
        },

        {
            "player_id": "P002",
            "player": "Another Player",
            "season": "2022/23",
            "season_start_date": "2022-08-01",
            "season_end_date": "2023-06-02",
            "competition": "Ligue 2",
            "competition_level": "SECOND_TIER",
            "team": "Other FC",
            "position": "MF",
            "minutes": 2300,
            "appearances": 29,
            "starts": 25,
            "goals": 9,
            "assists": 11,
            "xg": 8.1,
            "xa": 9.8,
            "goals_per90": 0.3522,
            "assists_per90": 0.4304,
            "xg_per90": 0.3170,
            "xa_per90": 0.3835,
        },

        # Saison du transfert

        {
            "player_id": "P002",
            "player": "Another Player",
            "season": "2023/24",
            "season_start_date": "2023-08-01",
            "season_end_date": "2024-05-17",
            "competition": "Ligue 2",
            "competition_level": "SECOND_TIER",
            "team": "New Other FC",
            "position": "MF",
            "minutes": 2200,
            "appearances": 28,
            "starts": 24,
            "goals": 8,
            "assists": 13,
            "xg": 7.6,
            "xa": 10.5,
            "goals_per90": 0.3273,
            "assists_per90": 0.5318,
            "xg_per90": 0.3109,
            "xa_per90": 0.4295,
        },

        {
            "player_id": "P002",
            "player": "Another Player",
            "season": "2024/25",
            "season_start_date": "2024-08-01",
            "season_end_date": "2025-05-17",
            "competition": "Ligue 2",
            "competition_level": "SECOND_TIER",
            "team": "New Other FC",
            "position": "MF",
            "minutes": 2500,
            "appearances": 30,
            "starts": 27,
            "goals": 10,
            "assists": 14,
            "xg": 9.2,
            "xa": 11.4,
            "goals_per90": 0.3600,
            "assists_per90": 0.5040,
            "xg_per90": 0.3312,
            "xa_per90": 0.4104,
        },
    ]

    return pd.DataFrame(rows)


# ============================================================================
# MAIN TEST
# ============================================================================

if __name__ == "__main__":

    print()
    print("=" * 70)
    print("TEST TRANSFER PERFORMANCE BUILDER")
    print("=" * 70)

    # ------------------------------------------------------------------
    # Données de test
    # ------------------------------------------------------------------

    transfers = _build_test_transfers()

    performances = _build_test_performances()

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    config = TransferPerformanceConfig(

        pre_months=36,

        post_months=18,

        min_pre_minutes=900,

        min_post_minutes=450,

        min_pre_seasons=1,

        min_post_seasons=1,
    )

    # ------------------------------------------------------------------
    # Builder
    # ------------------------------------------------------------------

    builder = TransferPerformanceBuilder(

        transfers=transfers,

        performances=performances,

        config=config,
    )

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    dataset = builder.build()

    # ------------------------------------------------------------------
    # Dataset
    # ------------------------------------------------------------------

    print()
    print("DATASET")
    print("-" * 70)

    display_columns = [

        "player_name",

        "transfer_date",

        "pre_minutes",

        "pre_seasons",

        "pre_performance_percentile",

        "post_minutes",

        "post_seasons",

        "post_performance_percentile",

        "performance_percentile_delta",

        "performance_data_quality",
    ]

    available_columns = [
        col
        for col in display_columns
        if col in dataset.columns
    ]

    if dataset.empty:

        print("Dataset vide.")

    else:

        print(
            dataset[
                available_columns
            ].to_string(
                index=False
            )
        )

    # ------------------------------------------------------------------
    # Fenêtres utilisées
    # ------------------------------------------------------------------

    print()
    print("FENÊTRES ATTENDUES")
    print("-" * 70)

    print(
        "PRE  : 36 mois avant le transfert"
    )

    print(
        "POST : 18 mois après le transfert"
    )

    print(
        "Saison du transfert : EXCLUE"
    )

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------

    print()
    print("SUMMARY")
    print("-" * 70)

    for key, value in builder.summary().items():

        print(
            f"{key:30}: {value}"
        )

    # ------------------------------------------------------------------
    # Complete cases
    # ------------------------------------------------------------------

    print()
    print("COMPLETE CASES")
    print("-" * 70)

    complete = (
        builder
        .filter_complete_cases()
    )

    if complete.empty:

        print(
            "Aucun cas complet."
        )

    else:

        print(
            complete[
                [
                    "player_name",
                    "pre_seasons",
                    "post_seasons",
                    "pre_minutes",
                    "post_minutes",
                    "performance_data_quality",
                ]
            ]
            .to_string(
                index=False
            )
        )

    # ------------------------------------------------------------------
    # Vérification des colonnes temporelles
    # ------------------------------------------------------------------

    print()
    print("VALIDATION FENETRES")
    print("-" * 70)

    expected_pre_seasons = {
        "Test Player": 3,
        "Another Player": 3,
    }

    expected_post_seasons = {
        "Test Player": 1,
        "Another Player": 1,
    }

    validation_ok = True

    for _, row in dataset.iterrows():

        player = row["player_name"]

        pre_expected = (
            expected_pre_seasons
            .get(player)
        )

        post_expected = (
            expected_post_seasons
            .get(player)
        )

        pre_actual = int(
            row["pre_seasons"]
        )

        post_actual = int(
            row["post_seasons"]
        )

        pre_ok = (
            pre_actual
            == pre_expected
        )

        post_ok = (
            post_actual
            == post_expected
        )

        print(
            f"{player:25} "
            f"PRE={pre_actual} "
            f"(attendu {pre_expected}) "
            f"{'✓' if pre_ok else '✗'} | "
            f"POST={post_actual} "
            f"(attendu {post_expected}) "
            f"{'✓' if post_ok else '✗'}"
        )

        if not pre_ok or not post_ok:

            validation_ok = False

    # ------------------------------------------------------------------
    # Save
    # ------------------------------------------------------------------

    output_path = builder.save()

    print()
    print(
        f"Dataset exporté : {output_path}"
    )

    # ------------------------------------------------------------------
    # Final
    # ------------------------------------------------------------------

    print()

    if validation_ok:

        print(
            "✓ VALIDATION FENETRES 36/18 MOIS OK"
        )

        print(
            "✓ TEST TRANSFER PERFORMANCE BUILDER TERMINÉ"
        )

    else:

        print(
            "✗ VALIDATION DES FENETRES ÉCHOUÉE"
        )

        raise SystemExit(1)