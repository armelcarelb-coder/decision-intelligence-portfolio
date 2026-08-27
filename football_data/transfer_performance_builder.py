"""
transfer_performance_builder.py

Construction du dataset performance pré/post-transfert.

Objectif
--------
Jointure entre :

    HistoricalTransferLoader
        +
    PerformanceLoader

afin de construire le dataset d'analyse des performances
autour d'un transfert.

Fenêtres méthodologiques
------------------------
PRE:
    36 mois avant la date du transfert.

POST:
    18 mois après la date du transfert.

Règle importante:
    La saison durant laquelle le transfert intervient est exclue.

    Une saison est considérée comme POST uniquement si :

        season_start_date > transfer_date

    et :

        season_start_date < transfer_date + 18 mois

Cette convention permet d'éviter de considérer une saison commencée
avant le transfert comme une véritable saison post-transfert.

Normalisation
-------------
Le calcul définitif de performance_percentile sera réalisé dans
une étape dédiée.

Il devra être calculé selon :

    position
    +
    niveau de championnat
    +
    saison / contexte temporel

Pour le moment, une valeur neutre de 0.5 est utilisée uniquement
pour tester la mécanique de jointure et des fenêtres temporelles.

Usage
-----
    python -m football_data.transfer_performance_builder
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

DEFAULT_OUTPUT_PATH = Path(
    "data/performances/transfer_performance_dataset.csv"
)

DEFAULT_PERFORMANCE_LOCAL_PATH = Path(
    "data/performances/performance_sample.csv"
)

PRE_WINDOW_MONTHS = 36
POST_WINDOW_MONTHS = 18


# ============================================================================
# COLONNES ATTENDUES
# ============================================================================

TRANSFER_REQUIRED_COLUMNS = [
    "player_id",
    "player_name",
    "transfer_date",
    "transfer_season",
]

PERFORMANCE_REQUIRED_COLUMNS = [
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


# ============================================================================
# CONFIGURATION BUILDER
# ============================================================================

@dataclass
class TransferPerformanceConfig:
    """
    Configuration méthodologique du builder.
    """

    pre_window_months: int = PRE_WINDOW_MONTHS
    post_window_months: int = POST_WINDOW_MONTHS

    min_pre_seasons: int = 1
    min_post_seasons: int = 1

    output_path: Path = DEFAULT_OUTPUT_PATH


# ============================================================================
# BUILDER
# ============================================================================

class TransferPerformanceBuilder:
    """
    Construit le dataset performance pré/post-transfert.
    """

    def __init__(
        self,
        transfers_df: pd.DataFrame,
        performances_df: pd.DataFrame,
        config: Optional[TransferPerformanceConfig] = None,
    ) -> None:

        self.config = (
            config
            if config is not None
            else TransferPerformanceConfig()
        )

        self.transfers_df = transfers_df.copy()
        self.performances_df = performances_df.copy()

        self._validate_inputs()

        self.transfers_df = self._prepare_transfers(
            self.transfers_df
        )

        self.performances_df = self._prepare_performances(
            self.performances_df
        )

        self.dataset: Optional[pd.DataFrame] = None

    # ========================================================================
    # VALIDATION DES INPUTS
    # ========================================================================

    def _validate_inputs(self) -> None:
        """
        Vérifie la présence des colonnes nécessaires.
        """

        missing_transfer = [
            column
            for column in TRANSFER_REQUIRED_COLUMNS
            if column not in self.transfers_df.columns
        ]

        if missing_transfer:
            raise ValueError(
                "Colonnes manquantes dans transfers_df : "
                f"{missing_transfer}"
            )

        missing_performance = [
            column
            for column in PERFORMANCE_REQUIRED_COLUMNS
            if column not in self.performances_df.columns
        ]

        if missing_performance:
            raise ValueError(
                "Colonnes manquantes dans performances_df : "
                f"{missing_performance}"
            )

    # ========================================================================
    # PREPARATION TRANSFERTS
    # ========================================================================

    @staticmethod
    def _prepare_transfers(
        df: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Nettoyage minimal du dataset des transferts.
        """

        df = df.copy()

        df["transfer_date"] = pd.to_datetime(
            df["transfer_date"],
            errors="coerce",
        )

        df = df.dropna(
            subset=[
                "player_name",
                "transfer_date",
            ]
        )

        df["player_name"] = (
            df["player_name"]
            .astype(str)
            .str.strip()
        )

        return df

    # ========================================================================
    # PREPARATION PERFORMANCES
    # ========================================================================

    @staticmethod
    def _prepare_performances(
        df: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Nettoyage et typage du dataset de performances.
        """

        df = df.copy()

        df["season_start_date"] = pd.to_datetime(
            df["season_start_date"],
            errors="coerce",
        )

        df["season_end_date"] = pd.to_datetime(
            df["season_end_date"],
            errors="coerce",
        )

        df["player"] = (
            df["player"]
            .astype(str)
            .str.strip()
        )

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

            if column in df.columns:

                df[column] = pd.to_numeric(
                    df[column],
                    errors="coerce",
                )

        return df

    # ========================================================================
    # FENETRES TEMPORELLES
    # ========================================================================

    def _calculate_windows(
        self,
        transfer_date: pd.Timestamp,
    ) -> tuple[
        pd.Timestamp,
        pd.Timestamp,
        pd.Timestamp,
        pd.Timestamp,
    ]:
        """
        Calcule les bornes PRE et POST.
        """

        pre_start = (
            transfer_date
            - pd.DateOffset(
                months=self.config.pre_window_months
            )
        )

        pre_end = transfer_date

        post_start = transfer_date

        post_end = (
            transfer_date
            + pd.DateOffset(
                months=self.config.post_window_months
            )
        )

        return (
            pre_start,
            pre_end,
            post_start,
            post_end,
        )

    # ========================================================================
    # SELECTION PRE
    # ========================================================================

    def _select_pre_performances(
        self,
        player_performances: pd.DataFrame,
        transfer_date: pd.Timestamp,
    ) -> pd.DataFrame:
        """
        Sélectionne les saisons PRE.

        Une saison PRE doit :

            1. être terminée avant ou à la date du transfert
            2. avoir une date de fin strictement après la borne
               de 36 mois.

        Cela garantit qu'une saison contenant le transfert
        n'est pas utilisée comme saison PRE.
        """

        pre_start, pre_end, _, _ = (
            self._calculate_windows(
                transfer_date
            )
        )

        data = player_performances.copy()

        mask = (
            (data["season_end_date"] <= pre_end)
            &
            (data["season_end_date"] > pre_start)
        )

        result = data.loc[mask].copy()

        return result.sort_values(
            "season_start_date"
        )

    # ========================================================================
    # SELECTION POST
    # ========================================================================

    def _select_post_performances(
        self,
        player_performances: pd.DataFrame,
        transfer_date: pd.Timestamp,
    ) -> pd.DataFrame:
        """
        Sélectionne les saisons POST.

        Règle méthodologique :

            season_start_date > transfer_date

        Une saison commencée avant ou le jour du transfert
        est donc exclue.

        La saison doit également commencer avant la fin
        de la fenêtre de 18 mois.
        """

        _, _, post_start, post_end = (
            self._calculate_windows(
                transfer_date
            )
        )

        data = player_performances.copy()

        mask = (
            (data["season_start_date"] > post_start)
            &
            (data["season_start_date"] < post_end)
        )

        result = data.loc[mask].copy()

        return result.sort_values(
            "season_start_date"
        )

    # ========================================================================
    # AGREGER LES PERFORMANCES
    # ========================================================================

    @staticmethod
    def _aggregate_performances(
        df: pd.DataFrame,
    ) -> dict:
        """
        Agrège les performances d'une fenêtre.
        """

        if df.empty:

            return {
                "minutes": np.nan,
                "seasons": 0,
                "performance_percentile": np.nan,
            }

        minutes = df["minutes"].sum(
            min_count=1
        )

        seasons = df["season"].nunique()

        # --------------------------------------------------------------------
        # VALEUR TEMPORAIRE
        #
        # Le vrai percentile sera calculé dans l'étape suivante.
        # --------------------------------------------------------------------

        performance_percentile = 0.5

        return {
            "minutes": minutes,
            "seasons": seasons,
            "performance_percentile": (
                performance_percentile
            ),
        }

    # ========================================================================
    # CONSTRUCTION D'UNE LIGNE DE TRANSFERT
    # ========================================================================

    def _build_transfer_row(
        self,
        transfer: pd.Series,
    ) -> dict:
        """
        Construit une observation pour un transfert.
        """

        player_name = transfer["player_name"]

        transfer_date = transfer["transfer_date"]

        # --------------------------------------------------------------------
        # IDENTIFICATION JOUEUR
        # --------------------------------------------------------------------

        player_mask = (
            self.performances_df["player"]
            .str.casefold()
            == str(player_name).casefold()
        )

        player_performances = (
            self.performances_df.loc[
                player_mask
            ].copy()
        )

        # --------------------------------------------------------------------
        # PRE
        # --------------------------------------------------------------------

        pre_data = self._select_pre_performances(
            player_performances,
            transfer_date,
        )

        # --------------------------------------------------------------------
        # POST
        # --------------------------------------------------------------------

        post_data = self._select_post_performances(
            player_performances,
            transfer_date,
        )

        # --------------------------------------------------------------------
        # AGREGATION
        # --------------------------------------------------------------------

        pre = self._aggregate_performances(
            pre_data
        )

        post = self._aggregate_performances(
            post_data
        )

        # --------------------------------------------------------------------
        # QUALITE DES DONNEES
        # --------------------------------------------------------------------

        has_pre = (
            pre["seasons"]
            >= self.config.min_pre_seasons
        )

        has_post = (
            post["seasons"]
            >= self.config.min_post_seasons
        )

        if has_pre and has_post:

            quality = "COMPLETE"

        elif has_pre:

            quality = "PRE_ONLY"

        elif has_post:

            quality = "POST_ONLY"

        else:

            quality = "INSUFFICIENT"

        # --------------------------------------------------------------------
        # DELTA
        # --------------------------------------------------------------------

        if (
            pd.notna(
                pre["performance_percentile"]
            )
            and pd.notna(
                post["performance_percentile"]
            )
        ):

            delta = (
                post["performance_percentile"]
                - pre["performance_percentile"]
            )

        else:

            delta = np.nan

        # --------------------------------------------------------------------
        # RESULTAT
        # --------------------------------------------------------------------

        return {
            "player_id": transfer.get(
                "player_id",
                np.nan,
            ),

            "player_name": player_name,

            "transfer_date": transfer_date,

            "transfer_season": transfer.get(
                "transfer_season",
                np.nan,
            ),

            "pre_minutes": pre["minutes"],

            "pre_seasons": pre["seasons"],

            "pre_performance_percentile": (
                pre["performance_percentile"]
            ),

            "post_minutes": post["minutes"],

            "post_seasons": post["seasons"],

            "post_performance_percentile": (
                post["performance_percentile"]
            ),

            "performance_percentile_delta": delta,

            "performance_data_quality": quality,
        }

    # ========================================================================
    # BUILD
    # ========================================================================

    def build(self) -> pd.DataFrame:
        """
        Construit le dataset final.
        """

        rows = []

        for _, transfer in self.transfers_df.iterrows():

            row = self._build_transfer_row(
                transfer
            )

            rows.append(row)

        result = pd.DataFrame(
            rows
        )

        if not result.empty:

            result = result.sort_values(
                [
                    "transfer_date",
                    "player_name",
                ]
            ).reset_index(
                drop=True
            )

        self.dataset = result

        return result

    # ========================================================================
    # SUMMARY
    # ========================================================================

    def summary(
        self,
        dataset: Optional[pd.DataFrame] = None,
    ) -> dict:
        """
        Produit un résumé du dataset.
        """

        if dataset is None:

            dataset = (
                self.dataset
                if self.dataset is not None
                else pd.DataFrame()
            )

        if dataset.empty:

            return {
                "rows": 0,
                "unique_players": 0,
                "complete_cases": 0,
                "pre_only": 0,
                "post_only": 0,
                "insufficient": 0,
                "mean_pre_percentile": np.nan,
                "mean_post_percentile": np.nan,
                "mean_percentile_delta": np.nan,
            }

        quality = dataset[
            "performance_data_quality"
        ]

        return {
            "rows": len(dataset),

            "unique_players": dataset[
                "player_name"
            ].nunique(),

            "complete_cases": (
                quality == "COMPLETE"
            ).sum(),

            "pre_only": (
                quality == "PRE_ONLY"
            ).sum(),

            "post_only": (
                quality == "POST_ONLY"
            ).sum(),

            "insufficient": (
                quality == "INSUFFICIENT"
            ).sum(),

            "mean_pre_percentile": dataset[
                "pre_performance_percentile"
            ].mean(),

            "mean_post_percentile": dataset[
                "post_performance_percentile"
            ].mean(),

            "mean_percentile_delta": dataset[
                "performance_percentile_delta"
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
        Sauvegarde le dataset au format CSV.
        """

        if dataset is None:

            dataset = (
                self.dataset
                if self.dataset is not None
                else self.build()
            )

        output_path = (
            Path(path)
            if path is not None
            else self.config.output_path
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
            "[TransferPerformanceBuilder] "
            f"Dataset sauvegardé : {output_path}"
        )

        return output_path


# ============================================================================
# VALIDATION DES FENETRES
# ============================================================================

def validate_windows(
    builder: TransferPerformanceBuilder,
    dataset: pd.DataFrame,
    expected_pre_seasons: int = 3,
    expected_post_seasons: int = 1,
) -> bool:
    """
    Vérifie le nombre de saisons PRE et POST.
    """

    print()
    print("VALIDATION FENETRES")
    print("-" * 70)

    success = True

    for _, row in dataset.iterrows():

        pre_ok = (
            row["pre_seasons"]
            == expected_pre_seasons
        )

        post_ok = (
            row["post_seasons"]
            == expected_post_seasons
        )

        print(
            f"{str(row['player_name']):<25}"
            f" PRE={row['pre_seasons']} "
            f"(attendu {expected_pre_seasons}) "
            f"{'✓' if pre_ok else '✗'}"
            f" | "
            f"POST={row['post_seasons']} "
            f"(attendu {expected_post_seasons}) "
            f"{'✓' if post_ok else '✗'}"
        )

        if not pre_ok or not post_ok:

            success = False

    return success


# ============================================================================
# VALIDATION EXCLUSION SAISON TRANSFERT
# ============================================================================

def validate_transfer_season_exclusion(
    builder: TransferPerformanceBuilder,
) -> bool:
    """
    Vérifie qu'aucune saison commencée avant ou à la date
    du transfert n'est considérée comme POST.
    """

    print()
    print(
        "VALIDATION EXCLUSION SAISON TRANSFERT"
    )
    print("-" * 70)

    success = True

    for _, transfer in builder.transfers_df.iterrows():

        player_name = transfer["player_name"]

        transfer_date = transfer["transfer_date"]

        player_mask = (
            builder.performances_df["player"]
            .str.casefold()
            == str(player_name).casefold()
        )

        player_performances = (
            builder.performances_df.loc[
                player_mask
            ].copy()
        )

        post_data = (
            builder._select_post_performances(
                player_performances,
                transfer_date,
            )
        )

        invalid = post_data[
            post_data["season_start_date"]
            <= transfer_date
        ]

        if not invalid.empty:

            print(
                f"✗ {player_name} : "
                "une saison de transfert apparaît dans POST."
            )

            success = False

        else:

            print(
                f"✓ {player_name} : "
                "saison du transfert correctement exclue."
            )

    return success


# ============================================================================
# VALIDATION SPECIFIQUE DES BORNES
# ============================================================================

def validate_post_boundary(
    builder: TransferPerformanceBuilder,
) -> bool:
    """
    Vérifie explicitement que les saisons POST respectent
    la borne de 18 mois.
    """

    print()
    print(
        "VALIDATION BORNE POST 18 MOIS"
    )
    print("-" * 70)

    success = True

    for _, transfer in builder.transfers_df.iterrows():

        player_name = transfer["player_name"]

        transfer_date = transfer["transfer_date"]

        _, _, _, post_end = (
            builder._calculate_windows(
                transfer_date
            )
        )

        player_mask = (
            builder.performances_df["player"]
            .str.casefold()
            == str(player_name).casefold()
        )

        player_performances = (
            builder.performances_df.loc[
                player_mask
            ].copy()
        )

        post_data = (
            builder._select_post_performances(
                player_performances,
                transfer_date,
            )
        )

        invalid = post_data[
            post_data["season_start_date"]
            >= post_end
        ]

        if not invalid.empty:

            print(
                f"✗ {player_name} : "
                "une saison dépasse la borne POST."
            )

            success = False

        else:

            print(
                f"✓ {player_name} : "
                "borne POST respectée."
            )

    return success


# ============================================================================
# TEST PRINCIPAL
# ============================================================================

def run_test() -> None:

    print("=" * 70)
    print("TEST TRANSFER PERFORMANCE BUILDER")
    print("=" * 70)

    # ========================================================================
    # IMPORTS
    # ========================================================================

    try:

        from football_data.historical_transfer_loader import (
            HistoricalTransferLoader,
        )

        from football_data.performance_loader import (
            PerformanceLoader,
        )

    except ImportError as exc:

        print(
            "Erreur import modules :",
            exc,
        )

        return

    # ========================================================================
    # HISTORIQUE TRANSFERTS
    # ========================================================================

    historical_loader = HistoricalTransferLoader(
        offline=True
    )

    transfers = historical_loader.load()

    # ========================================================================
    # PERFORMANCES
    # ========================================================================

    performance_loader = PerformanceLoader(
        offline=True,
        local_path=DEFAULT_PERFORMANCE_LOCAL_PATH,
    )

    performances = performance_loader.load()

    # ========================================================================
    # FILTRAGE DU DATASET DE TEST
    # ========================================================================

    test_players = [
        "Test Player",
        "Another Player",
    ]

    transfers_test = transfers[
        transfers["player_name"].isin(
            test_players
        )
    ].copy()

    transfers_test = transfers_test[
        transfers_test["transfer_date"].between(
            "2023-07-01",
            "2023-07-31",
        )
    ].copy()

    # ========================================================================
    # VERIFICATION DU TEST
    # ========================================================================

    if transfers_test.empty:

        raise ValueError(
            "Aucun transfert de test trouvé pour "
            "Test Player / Another Player "
            "sur juillet 2023."
        )

    # ========================================================================
    # BUILDER
    # ========================================================================

    builder = TransferPerformanceBuilder(
        transfers_df=transfers_test,
        performances_df=performances,
    )

    dataset = builder.build()

    # ========================================================================
    # DATASET
    # ========================================================================

    print()
    print("DATASET")
    print("-" * 70)

    columns_to_display = [
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

    display_columns = [
        column
        for column in columns_to_display
        if column in dataset.columns
    ]

    print(
        dataset[
            display_columns
        ].to_string(
            index=False
        )
    )

    # ========================================================================
    # FENETRES ATTENDUES
    # ========================================================================

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

    print(
        "PRE attendu : 3 saisons"
    )

    print(
        "POST attendu : 1 saison"
    )

    # ========================================================================
    # SUMMARY
    # ========================================================================

    summary = builder.summary(
        dataset
    )

    print()
    print("SUMMARY")
    print("-" * 70)

    for key, value in summary.items():

        print(
            f"{key:<30}: {value}"
        )

    # ========================================================================
    # COMPLETE CASES
    # ========================================================================

    print()
    print("COMPLETE CASES")
    print("-" * 70)

    complete = dataset[
        dataset["performance_data_quality"]
        == "COMPLETE"
    ]

    if complete.empty:

        print(
            "Aucun COMPLETE case."
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
            ].to_string(
                index=False
            )
        )

    # ========================================================================
    # VALIDATION FENETRES
    # ========================================================================

    windows_ok = validate_windows(
        builder,
        dataset,
        expected_pre_seasons=3,
        expected_post_seasons=1,
    )

    # ========================================================================
    # VALIDATION EXCLUSION
    # ========================================================================

    exclusion_ok = (
        validate_transfer_season_exclusion(
            builder
        )
    )

    # ========================================================================
    # VALIDATION BORNE POST
    # ========================================================================

    boundary_ok = (
        validate_post_boundary(
            builder
        )
    )

    # ========================================================================
    # SAVE
    # ========================================================================

    output_path = builder.save(
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
        windows_ok
        and exclusion_ok
        and boundary_ok
    ):

        print(
            "✓ VALIDATION DES FENETRES RÉUSSIE"
        )

    else:

        print(
            "✗ VALIDATION DES FENETRES ÉCHOUÉE"
        )

    print()


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":

    run_test()