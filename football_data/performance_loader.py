from __future__ import annotations

from pathlib import Path
from typing import Optional, List

import pandas as pd


class PerformanceLoader:
    """
    Chargeur centralisé des performances historiques des joueurs.

    Responsabilités
    ---------------
    - Charger les performances depuis une source distante ou locale.
    - Normaliser les noms de colonnes.
    - Nettoyer les types de données.
    - Normaliser les informations temporelles des saisons.
    - Conserver les informations de compétition et de niveau.
    - Calculer les métriques simples par 90 minutes.
    - Fournir des méthodes de filtrage et de résumé.

    Ce module NE fait PAS :
    - l'analyse des transferts ;
    - la définition du succès d'un transfert ;
    - le calcul des percentiles ;
    - le calcul de la probabilité de réussite ;
    - la décision de recrutement.

    Architecture :

        FBref / CSV / Parquet
                ↓
        PerformanceLoader
                ↓
        DataFrame normalisé
                ↓
        PerformanceNormalizer
                ↓
        TransferPerformanceBuilder
    """

    # ==========================================================
    # SCHEMA
    # ==========================================================

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
    ]

    NUMERIC_COLUMNS = [
        "minutes",
        "appearances",
        "starts",
        "goals",
        "assists",
        "xg",
        "xa",
    ]

    DATE_COLUMNS = [
        "season_start_date",
        "season_end_date",
    ]

    OUTPUT_COLUMNS = [
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

    # ==========================================================
    # INITIALIZATION
    # ==========================================================

    def __init__(
        self,
        football_loader=None,
        leagues: Optional[List[str]] = None,
        seasons: Optional[List[str]] = None,
        offline: bool = False,
        local_path: Optional[str] = None,
    ):
        """
        Parameters
        ----------
        football_loader:
            Instance de FootballDataLoader utilisée en mode online.

        leagues:
            Ligues à charger en mode online.

        seasons:
            Saisons à charger en mode online.

        offline:
            Si True, aucune connexion FBref n'est effectuée.
            Les données sont chargées depuis local_path.

        local_path:
            Chemin vers un fichier CSV ou Parquet local.
        """

        self.football_loader = football_loader

        self.leagues = (
            leagues
            if leagues is not None
            else ["ESP-La Liga"]
        )

        self.seasons = (
            seasons
            if seasons is not None
            else ["2324"]
        )

        self.offline = offline
        self.local_path = local_path

        self.dataframe: Optional[pd.DataFrame] = None

    # ==========================================================
    # PUBLIC API
    # ==========================================================

    def load(self) -> pd.DataFrame:
        """
        Charge et normalise les performances.

        Mode offline
        ------------
        Charge local_path.

        Mode online
        -----------
        Utilise le FBrefLoader fourni par FootballDataLoader.

        Returns
        -------
        pd.DataFrame
            Dataset de performances normalisé.
        """

        print(
            "[PerformanceLoader] "
            "Chargement des performances historiques..."
        )

        # ------------------------------------------------------
        # OFFLINE
        # ------------------------------------------------------

        if self.offline:

            df = self._load_local()

        # ------------------------------------------------------
        # ONLINE
        # ------------------------------------------------------

        else:

            if self.football_loader is None:

                raise ValueError(
                    "football_loader est requis "
                    "en mode online."
                )

            df = self._load_fbref()

        # ------------------------------------------------------
        # NORMALISATION
        # ------------------------------------------------------

        df = self._normalize(df)

        self.dataframe = df

        print(
            "[PerformanceLoader] "
            f"{len(df)} lignes chargées."
        )

        return df

    # ==========================================================
    # LOCAL LOADING
    # ==========================================================

    def _load_local(self) -> pd.DataFrame:
        """
        Charge les données depuis un fichier local.

        Formats supportés :
        - CSV
        - Parquet
        """

        if self.local_path is None:

            raise ValueError(
                "local_path est requis "
                "en mode offline."
            )

        path = Path(self.local_path)

        if not path.exists():

            raise FileNotFoundError(
                f"Fichier de performances introuvable : "
                f"{path}"
            )

        print(
            "[PerformanceLoader] "
            f"Chargement local : {path}"
        )

        suffix = path.suffix.lower()

        # ------------------------------------------------------
        # CSV
        # ------------------------------------------------------

        if suffix == ".csv":

            return pd.read_csv(path)

        # ------------------------------------------------------
        # PARQUET
        # ------------------------------------------------------

        if suffix in [".parquet", ".pq"]:

            try:

                return pd.read_parquet(path)

            except ImportError as exc:

                raise ImportError(
                    "Le chargement Parquet nécessite "
                    "pyarrow ou fastparquet."
                ) from exc

        # ------------------------------------------------------
        # FORMAT INCONNU
        # ------------------------------------------------------

        raise ValueError(
            "Format de fichier non supporté : "
            f"{suffix}. "
            "Utilisez CSV ou Parquet."
        )

    # ==========================================================
    # FBREF
    # ==========================================================

    def _load_fbref(self) -> pd.DataFrame:
        """
        Charge les statistiques joueurs via FBrefLoader.

        La responsabilité de communiquer avec FBref reste
        dans football_data.fbref_loader.
        """

        fbref = self.football_loader.fbref_loader

        # ------------------------------------------------------
        # API 1
        # ------------------------------------------------------

        if hasattr(
            fbref,
            "read_player_season_stats"
        ):

            df = fbref.read_player_season_stats(
                stat_type="standard"
            )

        # ------------------------------------------------------
        # API 2
        # ------------------------------------------------------

        elif hasattr(
            fbref,
            "load_player_stats"
        ):

            df = fbref.load_player_stats()

        # ------------------------------------------------------
        # AUCUNE API COMPATIBLE
        # ------------------------------------------------------

        else:

            raise AttributeError(
                "FBrefLoader ne possède aucune méthode "
                "compatible pour charger les statistiques "
                "joueurs."
            )

        if df is None:

            return pd.DataFrame()

        if not isinstance(
            df,
            pd.DataFrame
        ):

            raise TypeError(
                "FBrefLoader doit retourner "
                "un pandas.DataFrame."
            )

        return df.reset_index()

    # ==========================================================
    # NORMALIZATION
    # ==========================================================

    def _normalize(
        self,
        df: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Normalise le DataFrame provenant de la source.

        Cette méthode :
        - harmonise les noms ;
        - construit les dates de saison si nécessaire ;
        - conserve compétition et niveau ;
        - nettoie les types ;
        - calcule les métriques /90 ;
        - déduplique les observations.

        Elle ne calcule PAS de percentile.
        """

        # ------------------------------------------------------
        # DATAFRAME VIDE
        # ------------------------------------------------------

        if df is None or df.empty:

            return pd.DataFrame(
                columns=self.OUTPUT_COLUMNS
            )

        df = df.copy()

        # ------------------------------------------------------
        # NORMALISATION DES NOMS
        # ------------------------------------------------------

        rename_map = {

            # Player
            "Player": "player",
            "player_name": "player",
            "Player Name": "player",

            # Season
            "Season": "season",
            "season_name": "season",
            "year": "season",

            # Season dates
            "Season Start Date": "season_start_date",
            "season_start": "season_start_date",
            "start_date": "season_start_date",

            "Season End Date": "season_end_date",
            "season_end": "season_end_date",
            "end_date": "season_end_date",

            # Competition
            "Competition": "competition",
            "League": "competition",
            "league": "competition",

            # Competition level
            "Competition Level": "competition_level",
            "League Level": "competition_level",
            "league_level": "competition_level",
            "level": "competition_level",

            # Team
            "Squad": "team",
            "club": "team",
            "Club": "team",

            # Position
            "Pos": "position",
            "Position": "position",

            # Minutes
            "Min": "minutes",
            "Playing Time Min": "minutes",
            "Minutes": "minutes",

            # Matches
            "MP": "appearances",
            "Playing Time MP": "appearances",
            "Matches": "appearances",

            # Starts
            "Starts": "starts",

            # Goals
            "Gls": "goals",
            "Goals": "goals",

            # Assists
            "Ast": "assists",
            "Assists": "assists",

            # Expected goals
            "xG": "xg",

            # Expected assists
            "xAG": "xa",
            "xA": "xa",
        }

        df = df.rename(
            columns=rename_map
        )

        # ------------------------------------------------------
        # SAISON
        # ------------------------------------------------------

        if "season" not in df.columns:

            df["season"] = pd.NA

        # ------------------------------------------------------
        # COMPETITION
        # ------------------------------------------------------

        if "competition" not in df.columns:

            df["competition"] = pd.NA

        # ------------------------------------------------------
        # COMPETITION LEVEL
        # ------------------------------------------------------

        if "competition_level" not in df.columns:

            df["competition_level"] = pd.NA

        # ------------------------------------------------------
        # DATES DE SAISON
        # ------------------------------------------------------

        if (
            "season_start_date" not in df.columns
            or "season_end_date" not in df.columns
        ):

            generated_dates = df["season"].apply(
                self._season_to_dates
            )

            if "season_start_date" not in df.columns:

                df["season_start_date"] = (
                    generated_dates.apply(
                        lambda x: x[0]
                    )
                )

            if "season_end_date" not in df.columns:

                df["season_end_date"] = (
                    generated_dates.apply(
                        lambda x: x[1]
                    )
                )

        # ------------------------------------------------------
        # COLONNES MANQUANTES
        # ------------------------------------------------------

        for column in self.REQUIRED_COLUMNS:

            if column not in df.columns:

                df[column] = pd.NA

        # ------------------------------------------------------
        # TYPES NUMÉRIQUES
        # ------------------------------------------------------

        for column in self.NUMERIC_COLUMNS:

            df[column] = pd.to_numeric(
                df[column],
                errors="coerce"
            )

        # ------------------------------------------------------
        # TYPES DATES
        # ------------------------------------------------------

        for column in self.DATE_COLUMNS:

            df[column] = pd.to_datetime(
                df[column],
                errors="coerce"
            )

        # ------------------------------------------------------
        # IDENTIFICATION / TEXTE
        # ------------------------------------------------------

        text_columns = [
            "player",
            "season",
            "competition",
            "competition_level",
            "team",
            "position",
        ]

        for column in text_columns:

            df[column] = (
                df[column]
                .astype("string")
                .str.strip()
            )

        # ------------------------------------------------------
        # NORMALISATION POSITION
        # ------------------------------------------------------

        df["position"] = (
            df["position"]
            .str.upper()
            .str.strip()
        )

        # ------------------------------------------------------
        # PER 90
        # ------------------------------------------------------

        minutes = df["minutes"]

        # Goals / 90
        df["goals_per90"] = (
            df["goals"]
            .div(minutes)
            .mul(90)
            .where(minutes > 0)
        )

        # Assists / 90
        df["assists_per90"] = (
            df["assists"]
            .div(minutes)
            .mul(90)
            .where(minutes > 0)
        )

        # xG / 90
        df["xg_per90"] = (
            df["xg"]
            .div(minutes)
            .mul(90)
            .where(minutes > 0)
        )

        # xA / 90
        df["xa_per90"] = (
            df["xa"]
            .div(minutes)
            .mul(90)
            .where(minutes > 0)
        )

        # ------------------------------------------------------
        # NETTOYAGE VALEURS INFINIES
        # ------------------------------------------------------

        df = df.replace(
            [float("inf"), float("-inf")],
            pd.NA
        )

        # ------------------------------------------------------
        # DÉDUPLICATION
        # ------------------------------------------------------

        df = df.drop_duplicates(
            subset=[
                "player",
                "season",
                "team",
                "competition",
            ],
            keep="first",
        )

        # ------------------------------------------------------
        # COLONNES DE SORTIE
        # ------------------------------------------------------

        for column in self.OUTPUT_COLUMNS:

            if column not in df.columns:

                df[column] = pd.NA

        df = df[
            self.OUTPUT_COLUMNS
        ]

        return df.reset_index(
            drop=True
        )

    # ==========================================================
    # SEASON DATE HELPER
    # ==========================================================

    @staticmethod
    def _season_to_dates(season):
        """
        Transforme une saison football en dates.

        Exemples
        --------
        2020/21
            -> 2020-07-01 / 2021-06-30

        2023/24
            -> 2023-07-01 / 2024-06-30

        2023-24
            -> 2023-07-01 / 2024-06-30

        2324
            -> 2023-07-01 / 2024-06-30

        2223
            -> 2022-07-01 / 2023-06-30
        """

        if pd.isna(season):

            return pd.NaT, pd.NaT

        value = str(season).strip()

        # ------------------------------------------------------
        # FORMAT 2020/21
        # ------------------------------------------------------

        if "/" in value:

            parts = value.split("/")

            if len(parts) == 2:

                try:

                    start_year = int(parts[0])

                    end_part = parts[1]

                    if len(end_part) == 2:

                        end_year = (
                            start_year // 100 * 100
                            + int(end_part)
                        )

                    else:

                        end_year = int(end_part)

                    return (
                        pd.Timestamp(
                            year=start_year,
                            month=7,
                            day=1
                        ),
                        pd.Timestamp(
                            year=end_year,
                            month=6,
                            day=30
                        ),
                    )

                except ValueError:

                    pass

        # ------------------------------------------------------
        # FORMAT 2020-21
        # ------------------------------------------------------

        if "-" in value:

            parts = value.split("-")

            if len(parts) == 2:

                try:

                    start_year = int(parts[0])

                    end_part = parts[1]

                    if len(end_part) == 2:

                        end_year = (
                            start_year // 100 * 100
                            + int(end_part)
                        )

                    else:

                        end_year = int(end_part)

                    return (
                        pd.Timestamp(
                            year=start_year,
                            month=7,
                            day=1
                        ),
                        pd.Timestamp(
                            year=end_year,
                            month=6,
                            day=30
                        ),
                    )

                except ValueError:

                    pass

        # ------------------------------------------------------
        # FORMAT 2324 / 2223
        # ------------------------------------------------------

        if (
            len(value) == 4
            and value.isdigit()
        ):

            try:

                first_two = int(value[:2])
                last_two = int(value[2:])

                start_year = 2000 + first_two
                end_year = 2000 + last_two

                return (
                    pd.Timestamp(
                        year=start_year,
                        month=7,
                        day=1
                    ),
                    pd.Timestamp(
                        year=end_year,
                        month=6,
                        day=30
                    ),
                )

            except ValueError:

                pass

        return pd.NaT, pd.NaT

    # ==========================================================
    # FILTER PLAYERS
    # ==========================================================

    def filter_players(
        self,
        player_names: Optional[List[str]] = None,
    ) -> pd.DataFrame:
        """
        Filtre le dataset sur une liste de joueurs.
        """

        self._check_loaded()

        df = self.dataframe.copy()

        if player_names:

            names = {
                str(name).strip().lower()
                for name in player_names
            }

            df = df[
                df["player"]
                .str.lower()
                .isin(names)
            ]

        return df.reset_index(
            drop=True
        )

    # ==========================================================
    # FILTER SEASONS
    # ==========================================================

    def filter_seasons(
        self,
        seasons: List[str]
    ) -> pd.DataFrame:
        """
        Filtre le dataset sur certaines saisons.
        """

        self._check_loaded()

        return self.dataframe[
            self.dataframe["season"]
            .isin(seasons)
        ].copy().reset_index(
            drop=True
        )

    # ==========================================================
    # FILTER POSITION
    # ==========================================================

    def filter_positions(
        self,
        positions: List[str]
    ) -> pd.DataFrame:
        """
        Filtre le dataset sur certaines positions.
        """

        self._check_loaded()

        normalized_positions = [
            str(position).upper().strip()
            for position in positions
        ]

        return self.dataframe[
            self.dataframe["position"]
            .isin(normalized_positions)
        ].copy().reset_index(
            drop=True
        )

    # ==========================================================
    # FILTER COMPETITION
    # ==========================================================

    def filter_competitions(
        self,
        competitions: List[str]
    ) -> pd.DataFrame:
        """
        Filtre le dataset sur certaines compétitions.
        """

        self._check_loaded()

        normalized = {
            str(value).strip().lower()
            for value in competitions
        }

        return self.dataframe[
            self.dataframe["competition"]
            .str.lower()
            .isin(normalized)
        ].copy().reset_index(
            drop=True
        )

    # ==========================================================
    # FILTER COMPETITION LEVEL
    # ==========================================================

    def filter_competition_levels(
        self,
        levels: List[str]
    ) -> pd.DataFrame:
        """
        Filtre le dataset sur le niveau de championnat.
        """

        self._check_loaded()

        normalized = {
            str(value).strip().lower()
            for value in levels
        }

        return self.dataframe[
            self.dataframe["competition_level"]
            .str.lower()
            .isin(normalized)
        ].copy().reset_index(
            drop=True
        )

    # ==========================================================
    # GET PLAYER HISTORY
    # ==========================================================

    def get_player_history(
        self,
        player_name: str
    ) -> pd.DataFrame:
        """
        Retourne l'historique de performance d'un joueur.
        """

        self._check_loaded()

        return self.dataframe[
            self.dataframe["player"]
            .str.lower()
            == player_name.strip().lower()
        ].copy().sort_values(
            by=[
                "season_start_date",
                "season",
            ],
            na_position="last",
        ).reset_index(
            drop=True
        )

    # ==========================================================
    # SUMMARY
    # ==========================================================

    def summary(self) -> dict:
        """
        Retourne un résumé du dataset chargé.
        """

        self._check_loaded()

        df = self.dataframe

        return {

            "rows":
                len(df),

            "unique_players":
                df["player"].nunique(),

            "unique_seasons":
                df["season"].nunique(),

            "unique_teams":
                df["team"].nunique(),

            "unique_positions":
                df["position"].nunique(),

            "unique_competitions":
                df["competition"].nunique(),

            "competition_levels":
                df["competition_level"]
                .dropna()
                .unique()
                .tolist(),

            "missing_minutes":
                int(
                    df["minutes"]
                    .isna()
                    .sum()
                ),

            "missing_position":
                int(
                    df["position"]
                    .isna()
                    .sum()
                ),

            "missing_xg":
                int(
                    df["xg"]
                    .isna()
                    .sum()
                ),

            "missing_xa":
                int(
                    df["xa"]
                    .isna()
                    .sum()
                ),

            "missing_season_start_date":
                int(
                    df["season_start_date"]
                    .isna()
                    .sum()
                ),

            "missing_season_end_date":
                int(
                    df["season_end_date"]
                    .isna()
                    .sum()
                ),

            "missing_competition":
                int(
                    df["competition"]
                    .isna()
                    .sum()
                ),

            "missing_competition_level":
                int(
                    df["competition_level"]
                    .isna()
                    .sum()
                ),
        }

    # ==========================================================
    # VALIDATION
    # ==========================================================

    def validate(self) -> dict:
        """
        Vérifie rapidement la qualité du dataset chargé.
        """

        self._check_loaded()

        df = self.dataframe

        return {

            "is_empty":
                df.empty,

            "has_player":
                df["player"].notna().any(),

            "has_season":
                df["season"].notna().any(),

            "has_season_dates":
                (
                    df["season_start_date"]
                    .notna()
                    .any()
                    and
                    df["season_end_date"]
                    .notna()
                    .any()
                ),

            "has_competition":
                df["competition"].notna().any(),

            "has_competition_level":
                df["competition_level"].notna().any(),

            "has_position":
                df["position"].notna().any(),

            "has_minutes":
                df["minutes"].notna().any(),

            "has_per90":
                (
                    df[
                        [
                            "goals_per90",
                            "assists_per90",
                            "xg_per90",
                            "xa_per90",
                        ]
                    ]
                    .notna()
                    .any()
                    .any()
                ),
        }

    # ==========================================================
    # INTERNAL VALIDATION
    # ==========================================================

    def _check_loaded(self) -> None:

        if self.dataframe is None:

            raise RuntimeError(
                "Aucune donnée chargée. "
                "Appelez load() avant cette opération."
            )


# ==================================================================
# TEST DU MODULE
# ==================================================================

if __name__ == "__main__":

    print()
    print("=" * 70)
    print("TEST PERFORMANCE LOADER")
    print("=" * 70)

    # --------------------------------------------------------------
    # MODE OFFLINE
    # --------------------------------------------------------------

    LOCAL_PATH = (
        "data/performances/performance_sample.csv"
    )

    loader = PerformanceLoader(
        offline=True,
        local_path=LOCAL_PATH,
    )

    try:

        # ==========================================================
        # LOAD
        # ==========================================================

        df = loader.load()

        # ==========================================================
        # DATASET
        # ==========================================================

        print()
        print("DATASET")
        print("-" * 70)

        print(
            f"Shape : {df.shape}"
        )

        # ==========================================================
        # SUMMARY
        # ==========================================================

        print()
        print("SUMMARY")
        print("-" * 70)

        summary = loader.summary()

        for key, value in summary.items():

            print(
                f"{key:<30}: {value}"
            )

        # ==========================================================
        # VALIDATION
        # ==========================================================

        print()
        print("VALIDATION")
        print("-" * 70)

        validation = loader.validate()

        for key, value in validation.items():

            status = "✓" if value else "✗"

            print(
                f"{status} {key:<30}: {value}"
            )

        # ==========================================================
        # COLUMNS
        # ==========================================================

        print()
        print("COLONNES")
        print("-" * 70)

        print(
            list(df.columns)
        )

        # ==========================================================
        # PREVIEW
        # ==========================================================

        print()
        print("APERÇU")
        print("-" * 70)

        if not df.empty:

            print(
                df.head(10).to_string(
                    index=False
                )
            )

        # ==========================================================
        # PLAYER HISTORY TEST
        # ==========================================================

        if not df.empty:

            first_player = (
                df["player"]
                .dropna()
                .iloc[0]
            )

            print()
            print(
                f"HISTORIQUE : {first_player}"
            )

            print("-" * 70)

            history = loader.get_player_history(
                first_player
            )

            print(
                history.to_string(
                    index=False
                )
            )

        # ==========================================================
        # FILTER SEASON TEST
        # ==========================================================

        seasons = (
            df["season"]
            .dropna()
            .unique()
            .tolist()
        )

        if seasons:

            test_season = seasons[0]

            filtered = (
                loader.filter_seasons(
                    [test_season]
                )
            )

            print()
            print(
                f"TEST FILTRE SAISON : {test_season}"
            )

            print(
                f"Lignes : {len(filtered)}"
            )

        # ==========================================================
        # FILTER POSITION TEST
        # ==========================================================

        positions = (
            df["position"]
            .dropna()
            .unique()
            .tolist()
        )

        if positions:

            test_position = positions[0]

            filtered = (
                loader.filter_positions(
                    [test_position]
                )
            )

            print()
            print(
                f"TEST FILTRE POSITION : "
                f"{test_position}"
            )

            print(
                f"Lignes : {len(filtered)}"
            )

        # ==========================================================
        # FILTER COMPETITION TEST
        # ==========================================================

        competitions = (
            df["competition"]
            .dropna()
            .unique()
            .tolist()
        )

        if competitions:

            test_competition = competitions[0]

            filtered = (
                loader.filter_competitions(
                    [test_competition]
                )
            )

            print()
            print(
                f"TEST FILTRE COMPETITION : "
                f"{test_competition}"
            )

            print(
                f"Lignes : {len(filtered)}"
            )

        # ==========================================================
        # FINAL TEST
        # ==========================================================

        print()
        print("=" * 70)
        print(
            "✓ PERFORMANCE LOADER TEST TERMINÉ"
        )
        print("=" * 70)

    except Exception as exc:

        print()
        print("=" * 70)
        print(
            "✗ PERFORMANCE LOADER TEST FAILED"
        )
        print("=" * 70)

        print()
        print(
            f"Erreur : {exc}"
        )

        raise