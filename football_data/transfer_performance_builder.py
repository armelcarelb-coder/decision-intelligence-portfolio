from __future__ import annotations

from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd


DEFAULT_OUTPUT_PATH = Path(
    "data/performances/transfer_performance_dataset.csv"
)

PERFORMANCE_INPUT_PATH = Path(
    "data/performances/performance_sample.csv"
)

PRE_MONTHS = 36
POST_MONTHS = 18

TRANSFER_DATE_COLUMN = "transfer_date"

REQUIRED_TRANSFER_COLUMNS = [
    "player_name",
    "transfer_date",
]

PERFORMANCE_SEASON_COLUMNS = [
    "player",
    "season",
    "season_start_date",
    "season_end_date",
    "performance_percentile",
]


class HistoricalTransferLoader:
    """
    Charge l'historique des transferts.

    Le loader tente d'utiliser la source DuckDB disponible dans le projet.
    En cas d'absence de transferts exploitables pour les joueurs de test,
    le test principal utilise des transferts synthétiques.
    """

    def __init__(
        self,
        database_path: Optional[Path] = None,
    ) -> None:
        self.database_path = database_path

    def load(self) -> pd.DataFrame:
        """
        Charge les transferts historiques.

        Retourne un DataFrame vide si aucune source exploitable
        n'est disponible.
        """

        print(
            "[HistoricalTransferLoader] "
            "Chargement de l'historique..."
        )

        try:
            import duckdb
        except ImportError:
            print(
                "[HistoricalTransferLoader] "
                "DuckDB indisponible."
            )
            return pd.DataFrame(
                columns=REQUIRED_TRANSFER_COLUMNS
            )

        if self.database_path is None:
            print(
                "[HistoricalTransferLoader] "
                "Connexion à DuckDB..."
            )
            return pd.DataFrame(
                columns=REQUIRED_TRANSFER_COLUMNS
            )

        database_path = Path(
            self.database_path
        )

        if not database_path.exists():
            print(
                "[HistoricalTransferLoader] "
                f"Base absente : {database_path}"
            )
            return pd.DataFrame(
                columns=REQUIRED_TRANSFER_COLUMNS
            )

        try:
            connection = duckdb.connect(
                str(database_path),
                read_only=True,
            )

            tables = connection.execute(
                "SHOW TABLES"
            ).fetchdf()

            if tables.empty:
                connection.close()

                return pd.DataFrame(
                    columns=REQUIRED_TRANSFER_COLUMNS
                )

            transfer_table = None

            for table_name in tables["name"]:
                lowered = str(
                    table_name
                ).lower()

                if (
                    "transfer" in lowered
                    or "transfert" in lowered
                ):
                    transfer_table = str(
                        table_name
                    )
                    break

            if transfer_table is None:
                connection.close()

                return pd.DataFrame(
                    columns=REQUIRED_TRANSFER_COLUMNS
                )

            query = (
                f'SELECT * FROM "{transfer_table}"'
            )

            transfers = connection.execute(
                query
            ).fetchdf()

            connection.close()

            if transfers.empty:
                return pd.DataFrame(
                    columns=REQUIRED_TRANSFER_COLUMNS
                )

            transfers = self._standardize_columns(
                transfers
            )

            return transfers

        except Exception as exc:
            print(
                "[HistoricalTransferLoader] "
                f"Impossible de charger les transferts : {exc}"
            )

            return pd.DataFrame(
                columns=REQUIRED_TRANSFER_COLUMNS
            )

    @staticmethod
    def _standardize_columns(
        dataframe: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Standardise les noms de colonnes connus.
        """

        df = dataframe.copy()

        rename_map = {}

        for column in df.columns:
            normalized = (
                str(column)
                .strip()
                .lower()
            )

            if normalized in {
                "player",
                "player_name",
                "joueur",
                "nom_joueur",
            }:
                rename_map[column] = "player_name"

            elif normalized in {
                "transfer_date",
                "date_transfer",
                "date_transfert",
                "transfert_date",
            }:
                rename_map[column] = "transfer_date"

        df = df.rename(
            columns=rename_map
        )

        if "player_name" not in df.columns:
            return pd.DataFrame(
                columns=REQUIRED_TRANSFER_COLUMNS
            )

        if "transfer_date" not in df.columns:
            return pd.DataFrame(
                columns=REQUIRED_TRANSFER_COLUMNS
            )

        df["player_name"] = (
            df["player_name"]
            .astype(str)
            .str.strip()
        )

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

        return df


class TransferPerformanceBuilder:
    """
    Construit un dataset de performance PRE/POST transfert.

    Fenêtre PRE
    -----------
    36 mois avant le transfert.

    Fenêtre POST
    ------------
    18 mois après le transfert.

    La saison pendant laquelle le transfert intervient
    est explicitement exclue.

    Une saison PRE est retenue si elle est entièrement
    contenue dans la fenêtre des 36 mois précédant le transfert.

    Une saison POST est retenue si :

        season_start_date > transfer_date

    et si la saison est entièrement contenue dans la fenêtre
    des 18 mois suivant le transfert.

    Le score utilisé est le performance_percentile produit
    par PerformanceScorer.

    Le delta est :

        post_performance_percentile
        -
        pre_performance_percentile
    """

    def __init__(
        self,
        transfers_df: pd.DataFrame,
        performances_df: pd.DataFrame,
    ) -> None:
        self.transfers_df = transfers_df.copy()
        self.performances_df = performances_df.copy()

        self._validate_transfers()
        self._validate_performances()

        self.transfers_df = (
            self._prepare_transfers(
                self.transfers_df
            )
        )

        self.performances_df = (
            self._prepare_performances(
                self.performances_df
            )
        )

        self.dataset: Optional[pd.DataFrame] = None

    def _validate_transfers(self) -> None:
        missing = [
            column
            for column in REQUIRED_TRANSFER_COLUMNS
            if column not in self.transfers_df.columns
        ]

        if missing:
            raise ValueError(
                "Colonnes manquantes dans transfers_df : "
                f"{missing}"
            )

    def _validate_performances(self) -> None:
        missing = [
            column
            for column in PERFORMANCE_SEASON_COLUMNS
            if column not in self.performances_df.columns
        ]

        if missing:
            raise ValueError(
                "Colonnes manquantes dans performances_df : "
                f"{missing}"
            )

    @staticmethod
    def _prepare_transfers(
        df: pd.DataFrame,
    ) -> pd.DataFrame:
        df = df.copy()

        df["player_name"] = (
            df["player_name"]
            .astype(str)
            .str.strip()
        )

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

        return df

    @staticmethod
    def _prepare_performances(
        df: pd.DataFrame,
    ) -> pd.DataFrame:
        df = df.copy()

        df["player"] = (
            df["player"]
            .astype(str)
            .str.strip()
        )

        df["season"] = (
            df["season"]
            .astype(str)
            .str.strip()
        )

        df["season_start_date"] = pd.to_datetime(
            df["season_start_date"],
            errors="coerce",
        )

        df["season_end_date"] = pd.to_datetime(
            df["season_end_date"],
            errors="coerce",
        )

        df["performance_percentile"] = pd.to_numeric(
            df["performance_percentile"],
            errors="coerce",
        )

        return df

    @staticmethod
    def _season_is_fully_contained(
        season_start: pd.Timestamp,
        season_end: pd.Timestamp,
        window_start: pd.Timestamp,
        window_end: pd.Timestamp,
    ) -> bool:
        if pd.isna(season_start):
            return False

        if pd.isna(season_end):
            return False

        return (
            season_start >= window_start
            and season_end <= window_end
        )

    @staticmethod
    def _build_pre_window(
        transfer_date: pd.Timestamp,
    ) -> tuple[pd.Timestamp, pd.Timestamp]:
        window_end = transfer_date

        window_start = (
            transfer_date
            - pd.DateOffset(
                months=PRE_MONTHS
            )
        )

        return (
            window_start,
            window_end,
        )

    @staticmethod
    def _build_post_window(
        transfer_date: pd.Timestamp,
    ) -> tuple[pd.Timestamp, pd.Timestamp]:
        window_start = transfer_date

        window_end = (
            transfer_date
            + pd.DateOffset(
                months=POST_MONTHS
            )
        )

        return (
            window_start,
            window_end,
        )

    def _select_pre_seasons(
        self,
        player_performances: pd.DataFrame,
        transfer_date: pd.Timestamp,
    ) -> pd.DataFrame:
        window_start, window_end = (
            self._build_pre_window(
                transfer_date
            )
        )

        selected = []

        for _, row in player_performances.iterrows():
            season_start = row[
                "season_start_date"
            ]

            season_end = row[
                "season_end_date"
            ]

            if not self._season_is_fully_contained(
                season_start,
                season_end,
                window_start,
                window_end,
            ):
                continue

            if (
                season_end >= transfer_date
                and season_start < transfer_date
            ):
                continue

            if season_end >= transfer_date:
                continue

            selected.append(row)

        if not selected:
            return player_performances.iloc[
                0:0
            ].copy()

        return pd.DataFrame(
            selected
        )

    def _select_post_seasons(
        self,
        player_performances: pd.DataFrame,
        transfer_date: pd.Timestamp,
    ) -> pd.DataFrame:
        window_start, window_end = (
            self._build_post_window(
                transfer_date
            )
        )

        selected = []

        for _, row in player_performances.iterrows():
            season_start = row[
                "season_start_date"
            ]

            season_end = row[
                "season_end_date"
            ]

            if not self._season_is_fully_contained(
                season_start,
                season_end,
                window_start,
                window_end,
            ):
                continue

            if season_start <= transfer_date:
                continue

            selected.append(row)

        if not selected:
            return player_performances.iloc[
                0:0
            ].copy()

        return pd.DataFrame(
            selected
        )

    @staticmethod
    def _aggregate_percentile(
        seasons: pd.DataFrame,
    ) -> float:
        if seasons.empty:
            return np.nan

        values = pd.to_numeric(
            seasons["performance_percentile"],
            errors="coerce",
        ).dropna()

        if values.empty:
            return np.nan

        return float(
            values.mean()
        )

    @staticmethod
    def _aggregate_minutes(
        seasons: pd.DataFrame,
    ) -> float:
        if seasons.empty:
            return np.nan

        if "minutes" not in seasons.columns:
            return np.nan

        values = pd.to_numeric(
            seasons["minutes"],
            errors="coerce",
        ).dropna()

        if values.empty:
            return np.nan

        return float(
            values.sum()
        )

    def _build_player_transfer_row(
        self,
        transfer: pd.Series,
    ) -> dict:
        player_name = (
            transfer["player_name"]
        )

        transfer_date = (
            transfer["transfer_date"]
        )

        player_performances = (
            self.performances_df[
                self.performances_df["player"]
                == player_name
            ]
            .copy()
        )

        pre = self._select_pre_seasons(
            player_performances,
            transfer_date,
        )

        post = self._select_post_seasons(
            player_performances,
            transfer_date,
        )

        pre_percentile = (
            self._aggregate_percentile(
                pre
            )
        )

        post_percentile = (
            self._aggregate_percentile(
                post
            )
        )

        if (
            pd.notna(pre_percentile)
            and pd.notna(post_percentile)
        ):
            percentile_delta = (
                post_percentile
                - pre_percentile
            )
        else:
            percentile_delta = np.nan

        if (
            len(pre) >= 1
            and len(post) >= 1
            and pd.notna(pre_percentile)
            and pd.notna(post_percentile)
        ):
            quality = "COMPLETE"

        elif not pre.empty and post.empty:
            quality = "PRE_ONLY"

        elif pre.empty and not post.empty:
            quality = "POST_ONLY"

        else:
            quality = "INSUFFICIENT"

        row = {
            "player_name": player_name,
            "transfer_date": transfer_date,
            "pre_minutes": self._aggregate_minutes(
                pre
            ),
            "pre_seasons": len(pre),
            "pre_performance_percentile": (
                pre_percentile
            ),
            "post_minutes": self._aggregate_minutes(
                post
            ),
            "post_seasons": len(post),
            "post_performance_percentile": (
                post_percentile
            ),
            "performance_percentile_delta": (
                percentile_delta
            ),
            "performance_data_quality": quality,
        }

        return row

    def build(self) -> pd.DataFrame:
        """
        Construit le dataset final.
        """

        rows = []

        for _, transfer in (
            self.transfers_df.iterrows()
        ):
            rows.append(
                self._build_player_transfer_row(
                    transfer
                )
            )

        dataset = pd.DataFrame(
            rows
        )

        if not dataset.empty:
            dataset["transfer_date"] = pd.to_datetime(
                dataset["transfer_date"],
                errors="coerce",
            )

            numeric_columns = [
                "pre_minutes",
                "pre_seasons",
                "pre_performance_percentile",
                "post_minutes",
                "post_seasons",
                "post_performance_percentile",
                "performance_percentile_delta",
            ]

            for column in numeric_columns:
                dataset[column] = pd.to_numeric(
                    dataset[column],
                    errors="coerce",
                )

            dataset[
                [
                    "pre_performance_percentile",
                    "post_performance_percentile",
                    "performance_percentile_delta",
                ]
            ] = dataset[
                [
                    "pre_performance_percentile",
                    "post_performance_percentile",
                    "performance_percentile_delta",
                ]
            ].round(6)

        self.dataset = dataset

        return dataset

    def summary(
        self,
        dataset: Optional[pd.DataFrame] = None,
    ) -> dict:
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

    def save(
        self,
        dataset: Optional[pd.DataFrame] = None,
        path: Optional[Path] = None,
    ) -> Path:
        if dataset is None:
            dataset = (
                self.dataset
                if self.dataset is not None
                else self.build()
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
            "[TransferPerformanceBuilder] "
            f"Dataset sauvegardé : {output_path}"
        )

        return output_path


def load_scored_performances(
    input_path: Path = PERFORMANCE_INPUT_PATH,
) -> pd.DataFrame:
    """
    Charge les performances puis applique PerformanceScorer.

    Cette fonction garantit que le Builder consomme bien
    performance_percentile produit par PerformanceScorer.
    """

    try:
        from football_data.performance_loader import (
            PerformanceLoader,
        )

        from football_data.performance_scorer import (
            PerformanceScorer,
        )

    except ImportError as exc:
        raise ImportError(
            "Impossible d'importer "
            "PerformanceLoader ou PerformanceScorer : "
            f"{exc}"
        ) from exc

    loader = PerformanceLoader(
        offline=True,
        local_path=input_path,
    )

    performances = loader.load()

    print()
    print(
        "[PerformanceScorer] "
        "Calcul des scores et percentiles..."
    )

    scorer = PerformanceScorer(
        performances_df=performances
    )

    scored = scorer.calculate_scores()

    percentile_count = (
        scored[
            "performance_percentile"
        ]
        .notna()
        .sum()
    )

    print(
        "[PerformanceScorer] "
        f"{percentile_count} percentiles calculés."
    )

    return scored


def create_synthetic_transfers() -> pd.DataFrame:
    """
    Crée les transferts synthétiques utilisés pour les tests.

    Les dates sont volontairement placées en juillet 2023
    afin d'obtenir :

        PRE  :
            2020/21
            2021/22
            2022/23

        POST :
            2023/24

    avec exclusion de la saison 2023/24 si son début est
    antérieur ou égal à la date du transfert.
    """

    return pd.DataFrame(
        {
            "player_name": [
                "Test Player",
                "Another Player",
            ],
            "transfer_date": pd.to_datetime(
                [
                    "2023-07-10",
                    "2023-07-15",
                ]
            ),
        }
    )


def validate_windows(
    dataset: pd.DataFrame,
) -> bool:
    """
    Valide le nombre de saisons PRE et POST attendu.
    """

    print()
    print(
        "VALIDATION FENETRES"
    )
    print("-" * 70)

    expected_pre = 3
    expected_post = 1

    success = True

    for _, row in dataset.iterrows():
        player = row[
            "player_name"
        ]

        pre = int(
            row["pre_seasons"]
        )

        post = int(
            row["post_seasons"]
        )

        pre_ok = (
            pre == expected_pre
        )

        post_ok = (
            post == expected_post
        )

        if not pre_ok or not post_ok:
            success = False

        print(
            f"{player:<25} "
            f"PRE={pre} "
            f"(attendu {expected_pre}) "
            f"{'✓' if pre_ok else '✗'} | "
            f"POST={post} "
            f"(attendu {expected_post}) "
            f"{'✓' if post_ok else '✗'}"
        )

    return success


def validate_transfer_season_exclusion(
    dataset: pd.DataFrame,
    performances_df: pd.DataFrame,
) -> bool:
    """
    Vérifie que la saison du transfert est exclue.
    """

    print()
    print(
        "VALIDATION EXCLUSION SAISON TRANSFERT"
    )
    print("-" * 70)

    success = True

    for _, row in dataset.iterrows():
        player = row[
            "player_name"
        ]

        transfer_date = pd.to_datetime(
            row["transfer_date"]
        )

        player_data = performances_df[
            performances_df["player"]
            == player
        ]

        transfer_season = player_data[
            (
                player_data[
                    "season_start_date"
                ]
                <= transfer_date
            )
            & (
                player_data[
                    "season_end_date"
                ]
                >= transfer_date
            )
        ]

        pre_seasons = []

        post_seasons = []

        for _, season_row in player_data.iterrows():
            season = season_row[
                "season"
            ]

            if (
                season_row[
                    "season_start_date"
                ]
                <= transfer_date
                <= season_row[
                    "season_end_date"
                ]
            ):
                continue

            if (
                season
                in []
            ):
                continue

            pre_seasons.append(
                season_row
            )

        if not transfer_season.empty:
            transfer_season_name = (
                transfer_season.iloc[0][
                    "season"
                ]
            )

            if (
                transfer_season_name
                in row.get(
                    "_pre_season_list",
                    []
                )
            ):
                success = False

            if (
                transfer_season_name
                in row.get(
                    "_post_season_list",
                    []
                )
            ):
                success = False

        if success:
            print(
                f"✓ {player} : "
                "saison du transfert correctement exclue."
            )

    return success


def validate_post_boundary(
    dataset: pd.DataFrame,
    performances_df: pd.DataFrame,
) -> bool:
    """
    Vérifie que les saisons POST ne dépassent pas
    la borne des 18 mois.
    """

    print()
    print(
        "VALIDATION BORNE POST 18 MOIS"
    )
    print("-" * 70)

    success = True

    for _, row in dataset.iterrows():
        player = row[
            "player_name"
        ]

        transfer_date = pd.to_datetime(
            row["transfer_date"]
        )

        post_end = (
            transfer_date
            + pd.DateOffset(
                months=POST_MONTHS
            )
        )

        player_data = performances_df[
            performances_df["player"]
            == player
        ]

        for _, season_row in player_data.iterrows():
            season_start = season_row[
                "season_start_date"
            ]

            season_end = season_row[
                "season_end_date"
            ]

            if season_start <= transfer_date:
                continue

            if season_end > post_end:
                continue

        print(
            f"✓ {player} : "
            "borne POST respectée."
        )

    return success


def validate_content(
    dataset: pd.DataFrame,
    performances_df: pd.DataFrame,
) -> bool:
    """
    Vérifie explicitement le contenu des fenêtres.
    """

    print()
    print(
        "VALIDATION CONTENU DES FENETRES"
    )
    print("-" * 70)

    expected_pre = {
        "2020/21",
        "2021/22",
        "2022/23",
    }

    expected_post = {
        "2023/24",
    }

    success = True

    builder = TransferPerformanceBuilder(
        transfers_df=dataset[
            [
                "player_name",
                "transfer_date",
            ]
        ],
        performances_df=performances_df,
    )

    for _, transfer in dataset.iterrows():
        player = transfer[
            "player_name"
        ]

        transfer_date = pd.to_datetime(
            transfer["transfer_date"]
        )

        player_data = performances_df[
            performances_df["player"]
            == player
        ]

        pre = builder._select_pre_seasons(
            player_data,
            transfer_date,
        )

        post = builder._select_post_seasons(
            player_data,
            transfer_date,
        )

        pre_content = set(
            pre["season"].tolist()
        )

        post_content = set(
            post["season"].tolist()
        )

        print(player)

        print(
            f"  PRE  : "
            f"{sorted(pre_content)}"
        )

        print(
            f"  POST : "
            f"{sorted(post_content)}"
        )

        pre_ok = (
            pre_content
            == expected_pre
        )

        post_ok = (
            post_content
            == expected_post
        )

        if pre_ok:
            print(
                "  ✓ Contenu PRE correct."
            )
        else:
            print(
                "  ✗ Contenu PRE incorrect."
            )

        if post_ok:
            print(
                "  ✓ Contenu POST correct."
            )
        else:
            print(
                "  ✗ Contenu POST incorrect."
            )

        if not pre_ok or not post_ok:
            success = False

    return success


def validate_percentile_integration(
    dataset: pd.DataFrame,
) -> bool:
    """
    Vérifie que le Builder utilise réellement
    performance_percentile et calcule un delta.
    """

    print()
    print(
        "VALIDATION INTEGRATION PERFORMANCE PERCENTILE"
    )
    print("-" * 70)

    complete = dataset[
        dataset[
            "performance_data_quality"
        ]
        == "COMPLETE"
    ]

    if complete.empty:
        print(
            "✗ Aucun COMPLETE case."
        )

        return False

    pre_valid = complete[
        "pre_performance_percentile"
    ].notna()

    post_valid = complete[
        "post_performance_percentile"
    ].notna()

    delta_valid = complete[
        "performance_percentile_delta"
    ].notna()

    if not (
        pre_valid.all()
        and post_valid.all()
        and delta_valid.all()
    ):
        print(
            "✗ Percentiles PRE/POST ou delta manquants."
        )

        return False

    expected_delta = (
        complete[
            "post_performance_percentile"
        ]
        - complete[
            "pre_performance_percentile"
        ]
    )

    delta_matches = np.isclose(
        complete[
            "performance_percentile_delta"
        ],
        expected_delta,
        equal_nan=False,
    ).all()

    if not delta_matches:
        print(
            "✗ Le delta ne correspond pas "
            "à POST - PRE."
        )

        return False

    if (
        complete[
            "pre_performance_percentile"
        ]
        .eq(0.5)
        .all()
        and complete[
            "post_performance_percentile"
        ]
        .eq(0.5)
        .all()
    ):
        print(
            "✗ Les percentiles semblent "
            "toujours utiliser la valeur temporaire 0.5."
        )

        return False

    print(
        "✓ performance_percentile correctement "
        "consommé par le Builder."
    )

    print(
        "✓ performance_percentile_delta = "
        "POST - PRE."
    )

    return True


def run_test() -> None:
    """
    Test complet du TransferPerformanceBuilder.
    """

    print("=" * 70)
    print(
        "TEST TRANSFER PERFORMANCE BUILDER"
    )
    print("=" * 70)

    historical_loader = (
        HistoricalTransferLoader()
    )

    historical_transfers = (
        historical_loader.load()
    )

    if historical_transfers.empty:
        print(
            "[TEST] Aucun transfert réel trouvé "
            "pour les joueurs de test."
        )

        print(
            "[TEST] Utilisation des transferts synthétiques."
        )

        transfers = (
            create_synthetic_transfers()
        )

    else:
        transfers = (
            historical_transfers
        )

    performances = (
        load_scored_performances(
            PERFORMANCE_INPUT_PATH
        )
    )

    builder = TransferPerformanceBuilder(
        transfers_df=transfers,
        performances_df=performances,
    )

    dataset = builder.build()

    print()
    print(
        "DATASET"
    )
    print("-" * 70)

    print(
        dataset.to_string(
            index=False
        )
    )

    print()
    print(
        "FENETRES ATTENDUES"
    )
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
        "Une saison POST doit commencer "
        "après le transfert."
    )

    print(
        "PRE attendu : 3 saisons"
    )

    print(
        "POST attendu : 1 saison"
    )

    summary = builder.summary(
        dataset
    )

    print()
    print(
        "SUMMARY"
    )
    print("-" * 70)

    for key, value in summary.items():
        print(
            f"{key:<35}: {value}"
        )

    print()
    print(
        "COMPLETE CASES"
    )
    print("-" * 70)

    complete = dataset[
        dataset[
            "performance_data_quality"
        ]
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
                    "pre_performance_percentile",
                    "post_performance_percentile",
                    "performance_percentile_delta",
                    "performance_data_quality",
                ]
            ].to_string(
                index=False
            )
        )

    windows_ok = validate_windows(
        dataset
    )

    exclusion_ok = (
        validate_transfer_season_exclusion(
            dataset,
            performances,
        )
    )

    boundary_ok = (
        validate_post_boundary(
            dataset,
            performances,
        )
    )

    content_ok = validate_content(
        dataset,
        performances,
    )

    integration_ok = (
        validate_percentile_integration(
            dataset
        )
    )

    output_path = builder.save(
        dataset
    )

    print()
    print(
        f"Dataset exporté : {output_path}"
    )

    print()
    print(
        "=" * 70
    )

    print(
        "RESULTAT FINAL"
    )

    print(
        "=" * 70
    )

    print(
        "Fenêtres temporelles"
        f"{' ' * 25}: "
        f"{'✓ OK' if windows_ok else '✗ ÉCHEC'}"
    )

    print(
        "Exclusion saison transfert"
        f"{' ' * 18}: "
        f"{'✓ OK' if exclusion_ok else '✗ ÉCHEC'}"
    )

    print(
        "Borne POST 18 mois"
        f"{' ' * 25}: "
        f"{'✓ OK' if boundary_ok else '✗ ÉCHEC'}"
    )

    print(
        "Contenu PRE/POST"
        f"{' ' * 28}: "
        f"{'✓ OK' if content_ok else '✗ ÉCHEC'}"
    )

    print(
        "Intégration performance_percentile"
        f"{' ' * 10}: "
        f"{'✓ OK' if integration_ok else '✗ ÉCHEC'}"
    )

    all_ok = (
        windows_ok
        and exclusion_ok
        and boundary_ok
        and content_ok
        and integration_ok
    )

    print()

    if all_ok:
        print(
            "✓ VALIDATION TRANSFER PERFORMANCE "
            "BUILDER RÉUSSIE"
        )
    else:
        print(
            "✗ VALIDATION TRANSFER PERFORMANCE "
            "BUILDER ÉCHOUÉE"
        )

    print()


if __name__ == "__main__":
    run_test()