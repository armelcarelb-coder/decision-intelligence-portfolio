"""
transfer_performance_builder.py

Construction du dataset historique de performance des transferts.

Objectif
--------
Relier :

    HistoricalTransferLoader
            +
    PerformanceLoader

afin de construire un dataset :

    transfert
        ↓
    performances pré-transfert
        ↓
    performances post-transfert
        ↓
    comparaison position + niveau de championnat
        ↓
    dataset destiné au modèle probabiliste de transfert.

Fenêtres méthodologiques
------------------------
PRE  : 36 mois avant le transfert
POST : 18 mois après le transfert

Important
---------
Les données de performance étant actuellement agrégées par saison,
nous utilisons uniquement les saisons complètes.

La saison du transfert est volontairement exclue du calcul PRE
afin d'éviter une fuite d'information entre performances avant
et après le transfert.

Le même principe est appliqué au POST lorsque la saison contient
le transfert : on ne considère que les saisons complètes suivant
le transfert.

Le calcul du percentile est effectué par :

    saison
    position
    niveau de championnat

Si league_level n'est pas disponible, la valeur UNKNOWN est utilisée.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Iterable

import numpy as np
import pandas as pd


# ============================================================================
# CONFIGURATION
# ============================================================================

@dataclass
class TransferPerformanceConfig:

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

    # Nombre minimal de saisons utilisées
    min_pre_seasons: int = 1
    min_post_seasons: int = 1

    # ------------------------------------------------------------------
    # Colonnes performance
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

    metric_weights: dict[str, float] = None

    # ------------------------------------------------------------------
    # Valeur utilisée lorsqu'on ne connaît pas le niveau
    # ------------------------------------------------------------------

    unknown_league_level: str = "UNKNOWN"

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    output_path: str = (
        "data/performances/transfer_performance_dataset.csv"
    )

    def __post_init__(self):

        if self.metric_weights is None:
            self.metric_weights = {
                "goals_per90": 0.30,
                "assists_per90": 0.20,
                "xg_per90": 0.30,
                "xa_per90": 0.20,
            }


# ============================================================================
# BUILDER
# ============================================================================

class TransferPerformanceBuilder:

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
        Construit le dataset final.

        Parameters
        ----------
        transfers :
            Historique des transferts.

        performances :
            Historique des performances joueurs.

        Returns
        -------
        pd.DataFrame
            Dataset transfert + performances PRE/POST.
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

        performances_df = self._calculate_performance_percentiles(
            performances_df
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

            if player_perf.empty:
                continue

            pre = self._build_pre_transfer_profile(
                transfer,
                player_perf
            )

            post = self._build_post_transfer_profile(
                transfer,
                player_perf
            )

            row = self._merge_transfer_profiles(
                transfer,
                pre,
                post
            )

            rows.append(row)

        if not rows:

            self.dataset = pd.DataFrame()

            return self.dataset

        self.dataset = pd.DataFrame(rows)

        return self.dataset

    # ======================================================================
    # TRANSFERTS
    # ======================================================================

    def _prepare_transfers(
        self,
        df: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Nettoyage minimal des transferts.

        Le cutoff historique est volontairement conservé hors du builder :
        il appartient à HistoricalTransferLoader / TransferOutcomeBuilder.

        Ici nous vérifions simplement les informations nécessaires.
        """

        required = [
            "player_id",
            "player_name",
            "transfer_date",
        ]

        missing = [
            col for col in required
            if col not in df.columns
        ]

        if missing:

            raise ValueError(
                "Colonnes manquantes dans les transferts : "
                + ", ".join(missing)
            )

        df["transfer_date"] = pd.to_datetime(
            df["transfer_date"],
            errors="coerce"
        )

        df = df.dropna(
            subset=[
                "player_id",
                "transfer_date",
            ]
        )

        # --------------------------------------------------------------
        # Suppression des transferts sans club destination
        # --------------------------------------------------------------

        if "to_club_name" in df.columns:

            df = df[
                df["to_club_name"]
                .fillna("")
                .str.strip()
                != ""
            ]

        # --------------------------------------------------------------
        # Suppression des lignes identiques
        # --------------------------------------------------------------

        df = df.drop_duplicates(
            subset=[
                "player_id",
                "transfer_date",
                "from_club_name",
                "to_club_name",
            ],
            keep="first"
        )

        return df.reset_index(drop=True)

    # ======================================================================
    # PERFORMANCES
    # ======================================================================

    def _prepare_performances(
        self,
        df: pd.DataFrame,
    ) -> pd.DataFrame:

        required = [
            "player",
            "season",
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
            col for col in required
            if col not in df.columns
        ]

        if missing:

            raise ValueError(
                "Colonnes manquantes dans les performances : "
                + ", ".join(missing)
            )

        # --------------------------------------------------------------
        # player_id
        # --------------------------------------------------------------

        if "player_id" not in df.columns:

            # Le loader actuel utilise "player".
            #
            # Nous ne pouvons pas prétendre que player == Transfermarkt ID.
            # Le builder crée donc un identifiant texte temporaire.
            df["player_id"] = (
                df["player"]
                .astype(str)
                .str.strip()
            )

        # --------------------------------------------------------------
        # Niveau de championnat
        # --------------------------------------------------------------

        if "league_level" not in df.columns:

            df["league_level"] = (
                self.config.unknown_league_level
            )

        df["league_level"] = (
            df["league_level"]
            .fillna(
                self.config.unknown_league_level
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
            .fillna("UNKNOWN")
            .astype(str)
            .str.upper()
            .str.strip()
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
        # Variables numériques
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
                    errors="coerce"
                )

        # --------------------------------------------------------------
        # Sécurité
        # --------------------------------------------------------------

        df["minutes"] = (
            df["minutes"]
            .fillna(0)
            .clip(lower=0)
        )

        df["starts"] = (
            df["starts"]
            .fillna(0)
            .clip(lower=0)
        )

        df["appearances"] = (
            df["appearances"]
            .fillna(0)
            .clip(lower=0)
        )

        # --------------------------------------------------------------
        # Suppression des lignes inutilisables
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

        Groupe de comparaison :

            saison
            position
            league_level

        Le score final est une moyenne pondérée des percentiles
        de chaque métrique.
        """

        df = df.copy()

        group_columns = [
            "season",
            "position",
            "league_level",
        ]

        percentile_columns = []

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
                    errors="coerce"
                )

                if values.notna().sum() <= 1:

                    return pd.Series(
                        0.50,
                        index=group.index
                    )

                return values.rank(
                    pct=True,
                    method="average"
                )

            df[percentile_col] = (
                df.groupby(
                    group_columns,
                    dropna=False
                )[metric]
                .transform(percentile_rank)
            )

        # --------------------------------------------------------------
        # Score pondéré
        # --------------------------------------------------------------

        weighted_sum = pd.Series(
            0.0,
            index=df.index
        )

        total_weight = pd.Series(
            0.0,
            index=df.index
        )

        for metric in self.config.performance_metrics:

            percentile_col = (
                f"{metric}_percentile"
            )

            if percentile_col not in df.columns:
                continue

            weight = self.config.metric_weights.get(
                metric,
                0.0
            )

            weighted_sum += (
                df[percentile_col]
                .fillna(0.5)
                * weight
            )

            total_weight += (
                df[percentile_col].notna()
                * weight
            )

        df["performance_percentile"] = np.where(
            total_weight > 0,
            weighted_sum / total_weight,
            0.50
        )

        df["performance_percentile"] = (
            df["performance_percentile"]
            .clip(0, 1)
        )

        return df

    # ======================================================================
    # SAISON
    # ======================================================================

    @staticmethod
    def _season_dates(
        season: str,
    ) -> tuple[pd.Timestamp, pd.Timestamp]:
        """
        Convertit :

            2223 -> 2022-07-01 / 2023-06-30

        Accepte également :

            2022-23
            2022/23
        """

        value = str(season).strip()

        digits = "".join(
            char
            for char in value
            if char.isdigit()
        )

        if len(digits) == 4:

            start_year = int(
                "20" + digits[:2]
            )

            end_year = int(
                "20" + digits[2:]
            )

        elif len(digits) == 8:

            start_year = int(
                digits[:4]
            )

            end_year = int(
                digits[4:]
            )

        else:

            raise ValueError(
                f"Saison non reconnue : {season}"
            )

        return (
            pd.Timestamp(
                f"{start_year}-07-01"
            ),
            pd.Timestamp(
                f"{end_year}-06-30"
            ),
        )

    # ======================================================================
    # PRE TRANSFERT
    # ======================================================================

    def _build_pre_transfer_profile(
        self,
        transfer: pd.Series,
        performances: pd.DataFrame,
    ) -> dict:

        transfer_date = transfer[
            "transfer_date"
        ]

        pre_start = (
            transfer_date
            - pd.DateOffset(
                months=self.config.pre_months
            )
        )

        selected = []

        for _, row in performances.iterrows():

            try:

                season_start, season_end = (
                    self._season_dates(
                        row["season"]
                    )
                )

            except ValueError:

                continue

            # Saison entièrement antérieure
            if (
                season_end < transfer_date
                and season_end >= pre_start
            ):

                selected.append(row)

        if not selected:

            return self._empty_profile(
                prefix="pre"
            )

        selected_df = pd.DataFrame(
            selected
        )

        return self._aggregate_profile(
            selected_df,
            prefix="pre"
        )

    # ======================================================================
    # POST TRANSFERT
    # ======================================================================

    def _build_post_transfer_profile(
        self,
        transfer: pd.Series,
        performances: pd.DataFrame,
    ) -> dict:

        transfer_date = transfer[
            "transfer_date"
        ]

        post_end = (
            transfer_date
            + pd.DateOffset(
                months=self.config.post_months
            )
        )

        selected = []

        for _, row in performances.iterrows():

            try:

                season_start, season_end = (
                    self._season_dates(
                        row["season"]
                    )
                )

            except ValueError:

                continue

            # La saison doit commencer après le transfert
            # afin d'éviter de mélanger pré et post.
            if (
                season_start > transfer_date
                and season_start <= post_end
            ):

                selected.append(row)

        if not selected:

            return self._empty_profile(
                prefix="post"
            )

        selected_df = pd.DataFrame(
            selected
        )

        return self._aggregate_profile(
            selected_df,
            prefix="post"
        )

    # ======================================================================
    # AGREGATION
    # ======================================================================

    def _aggregate_profile(
        self,
        df: pd.DataFrame,
        prefix: str,
    ) -> dict:

        result = {}

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
        # Moyennes pondérées par minutes
        # --------------------------------------------------------------

        for metric in [
            "goals_per90",
            "assists_per90",
            "xg_per90",
            "xa_per90",
            "performance_percentile",
        ]:

            if metric not in df.columns:
                continue

            values = pd.to_numeric(
                df[metric],
                errors="coerce"
            )

            weights = df["minutes"].fillna(0)

            valid = (
                values.notna()
                & weights.gt(0)
            )

            if valid.any():

                weighted_value = np.average(
                    values[valid],
                    weights=weights[valid]
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
        ] = df["season"].nunique()

        # --------------------------------------------------------------
        # Niveau de données suffisant
        # --------------------------------------------------------------

        result[
            f"{prefix}_data_sufficient"
        ] = bool(
            total_minutes
            >= (
                self.config.min_pre_minutes
                if prefix == "pre"
                else self.config.min_post_minutes
            )
            and
            df["season"].nunique()
            >= (
                self.config.min_pre_seasons
                if prefix == "pre"
                else self.config.min_post_seasons
            )
        )

        # --------------------------------------------------------------
        # Evolution / stabilité
        # --------------------------------------------------------------

        if "performance_percentile" in df.columns:

            result[
                f"{prefix}_performance_min"
            ] = df[
                "performance_percentile"
            ].min()

            result[
                f"{prefix}_performance_max"
            ] = df[
                "performance_percentile"
            ].max()

            result[
                f"{prefix}_performance_std"
            ] = df[
                "performance_percentile"
            ].std()

        return result

    # ======================================================================
    # EMPTY PROFILE
    # ======================================================================

    @staticmethod
    def _empty_profile(
        prefix: str,
    ) -> dict:

        return {

            f"{prefix}_minutes": np.nan,

            f"{prefix}_appearances": np.nan,

            f"{prefix}_starts": np.nan,

            f"{prefix}_starter_rate": np.nan,

            f"{prefix}_goals_per90": np.nan,

            f"{prefix}_assists_per90": np.nan,

            f"{prefix}_xg_per90": np.nan,

            f"{prefix}_xa_per90": np.nan,

            f"{prefix}_performance_percentile": np.nan,

            f"{prefix}_seasons": 0,

            f"{prefix}_data_sufficient": False,

            f"{prefix}_performance_min": np.nan,

            f"{prefix}_performance_max": np.nan,

            f"{prefix}_performance_std": np.nan,
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
            np.nan
        )

        post_perf = post.get(
            "post_performance_percentile",
            np.nan
        )

        if (
            pd.notna(pre_perf)
            and pd.notna(post_perf)
        ):

            result[
                "performance_percentile_delta"
            ] = post_perf - pre_perf

        else:

            result[
                "performance_percentile_delta"
            ] = np.nan

        # --------------------------------------------------------------
        # Delta minutes
        # --------------------------------------------------------------

        pre_minutes = pre.get(
            "pre_minutes",
            np.nan
        )

        post_minutes = post.get(
            "post_minutes",
            np.nan
        )

        if (
            pd.notna(pre_minutes)
            and pd.notna(post_minutes)
        ):

            result[
                "minutes_delta"
            ] = post_minutes - pre_minutes

        else:

            result[
                "minutes_delta"
            ] = np.nan

        # --------------------------------------------------------------
        # Qualité du dataset
        # --------------------------------------------------------------

        result[
            "performance_data_quality"
        ] = self._data_quality(
            pre,
            post
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

        pre_ok = pre.get(
            "pre_data_sufficient",
            False
        )

        post_ok = post.get(
            "post_data_sufficient",
            False
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

        if self.dataset is None:

            raise ValueError(
                "Construis d'abord le dataset avec build()."
            )

        return self.dataset[
            self.dataset[
                "performance_data_quality"
            ] == "COMPLETE"
        ].copy()

    # ======================================================================
    # SAVE
    # ======================================================================

    def save(
        self,
        path: Optional[str] = None,
    ) -> Path:

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
            exist_ok=True
        )

        self.dataset.to_csv(
            output,
            index=False
        )

        print(
            f"[TransferPerformanceBuilder] "
            f"Dataset sauvegardé : {output}"
        )

        return output

    # ======================================================================
    # SUMMARY
    # ======================================================================

    def summary(self) -> dict:

        if self.dataset is None:

            return {
                "rows": 0
            }

        df = self.dataset

        return {

            "rows": len(df),

            "unique_players": (
                df["player_id"].nunique()
                if "player_id" in df.columns
                else 0
            ),

            "complete_cases": int(
                (
                    df["performance_data_quality"]
                    == "COMPLETE"
                ).sum()
            ),

            "pre_only": int(
                (
                    df["performance_data_quality"]
                    == "PRE_ONLY"
                ).sum()
            ),

            "post_only": int(
                (
                    df["performance_data_quality"]
                    == "POST_ONLY"
                ).sum()
            ),

            "insufficient": int(
                (
                    df["performance_data_quality"]
                    == "INSUFFICIENT"
                ).sum()
            ),

            "mean_pre_percentile": (
                df[
                    "pre_performance_percentile"
                ].mean()
            ),

            "mean_post_percentile": (
                df[
                    "post_performance_percentile"
                ].mean()
            ),

            "mean_percentile_delta": (
                df[
                    "performance_percentile_delta"
                ].mean()
            ),
        }


# ============================================================================
# TEST OFFLINE
# ============================================================================

def _build_test_transfers() -> pd.DataFrame:

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
            "2324",
            "2324",
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

    return pd.DataFrame({

        "player_id": [
            "P001",
            "P001",
            "P001",
            "P002",
            "P002",
            "P002",
        ],

        "player": [
            "Test Player",
            "Test Player",
            "Test Player",
            "Another Player",
            "Another Player",
            "Another Player",
        ],

        "season": [
            "2021-22",
            "2022-23",
            "2023-24",
            "2021-22",
            "2022-23",
            "2023-24",
        ],

        "team": [
            "Old FC",
            "Old FC",
            "New FC",
            "Other FC",
            "Other FC",
            "New Other FC",
        ],

        "league_level": [
            "TOP",
            "TOP",
            "TOP",
            "TOP",
            "TOP",
            "TOP",
        ],

        "position": [
            "FW",
            "FW",
            "FW",
            "MF",
            "MF",
            "MF",
        ],

        "minutes": [
            2500,
            2700,
            2300,
            2200,
            2400,
            1800,
        ],

        "appearances": [
            30,
            32,
            28,
            28,
            30,
            25,
        ],

        "starts": [
            28,
            30,
            25,
            25,
            27,
            20,
        ],

        "goals": [
            15,
            20,
            18,
            8,
            10,
            9,
        ],

        "assists": [
            6,
            8,
            7,
            10,
            12,
            11,
        ],

        "xg": [
            13,
            18,
            16,
            7,
            9,
            8,
        ],

        "xa": [
            5,
            7,
            6,
            9,
            11,
            10,
        ],

        "goals_per90": [
            0.54,
            0.67,
            0.70,
            0.33,
            0.38,
            0.45,
        ],

        "assists_per90": [
            0.22,
            0.27,
            0.27,
            0.41,
            0.45,
            0.55,
        ],

        "xg_per90": [
            0.47,
            0.60,
            0.63,
            0.29,
            0.34,
            0.40,
        ],

        "xa_per90": [
            0.18,
            0.23,
            0.23,
            0.38,
            0.41,
            0.50,
        ],
    })


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":

    print("=" * 70)
    print("TEST TRANSFER PERFORMANCE BUILDER")
    print("=" * 70)

    transfers = _build_test_transfers()

    performances = _build_test_performances()

    config = TransferPerformanceConfig(
        pre_months=36,
        post_months=18,
        min_pre_minutes=900,
        min_post_minutes=450,
    )

    builder = TransferPerformanceBuilder(
        transfers=transfers,
        performances=performances,
        config=config,
    )

    dataset = builder.build()

    print("\nDATASET")
    print("-" * 70)

    print(
        dataset[
            [
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
        ].to_string(index=False)
    )

    print("\nSUMMARY")
    print("-" * 70)

    for key, value in builder.summary().items():

        print(
            f"{key:30}: {value}"
        )

    print("\nCOMPLETE CASES")
    print("-" * 70)

    complete = (
        builder
        .filter_complete_cases()
    )

    print(
        complete[
            [
                "player_name",
                "performance_data_quality",
            ]
        ].to_string(index=False)
    )

    print("\n" + "=" * 70)
    print("✓ TEST TRANSFER PERFORMANCE BUILDER TERMINÉ")
    print("=" * 70)