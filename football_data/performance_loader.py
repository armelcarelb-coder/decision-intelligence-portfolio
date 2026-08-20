# football_data/performance_loader.py

from __future__ import annotations

from typing import Optional, List
import pandas as pd


class PerformanceLoader:
    """
    Chargeur centralisé des performances historiques des joueurs.

    Responsabilité :
        - récupérer les performances historiques ;
        - uniformiser les colonnes ;
        - conserver les informations nécessaires à l'analyse
          pré/post-transfert.

    Ne contient PAS :
        - logique de transfert ;
        - calcul du succès d'un transfert ;
        - calcul de success_probability ;
        - décision de recrutement.
    """

    REQUIRED_COLUMNS = [
        "player",
        "season",
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

    def __init__(
        self,
        football_loader=None,
        leagues: Optional[List[str]] = None,
        seasons: Optional[List[str]] = None,
    ):
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

        self.dataframe: Optional[pd.DataFrame] = None

    # ==========================================================
    # PUBLIC API
    # ==========================================================

    def load(self) -> pd.DataFrame:
        """
        Charge les performances historiques.

        Retourne un DataFrame normalisé.
        """

        if self.football_loader is None:
            raise ValueError(
                "football_loader est requis pour charger "
                "les données de performance."
            )

        print(
            "[PerformanceLoader] "
            "Chargement des performances historiques..."
        )

        df = self._load_fbref()

        df = self._normalize(df)

        self.dataframe = df

        print(
            "[PerformanceLoader] "
            f"{len(df)} lignes chargées."
        )

        return df

    # ==========================================================
    # FBREF
    # ==========================================================

    def _load_fbref(self) -> pd.DataFrame:
        """
        Charge les statistiques joueurs depuis FBref.

        Le loader spécialisé FBref reste responsable de
        l'interaction avec soccerdata.
        """

        fbref = self.football_loader.fbref_loader

        try:
            df = fbref.read_player_season_stats(
                stat_type="standard"
            )

        except AttributeError:

            # Compatibilité avec différentes implémentations
            # de FBrefLoader.

            if hasattr(fbref, "load_player_stats"):

                df = fbref.load_player_stats()

            else:

                raise AttributeError(
                    "FBrefLoader ne possède aucune méthode "
                    "compatible pour charger les statistiques "
                    "joueurs."
                )

        if df is None:

            return pd.DataFrame()

        if not isinstance(df, pd.DataFrame):

            raise TypeError(
                "FBrefLoader doit retourner un pandas.DataFrame."
            )

        return df.reset_index()

    # ==========================================================
    # NORMALISATION
    # ==========================================================

    def _normalize(
        self,
        df: pd.DataFrame
    ) -> pd.DataFrame:

        if df.empty:

            return pd.DataFrame(
                columns=self.REQUIRED_COLUMNS
            )

        df = df.copy()

        # ------------------------------------------------------
        # NORMALISATION DES NOMS
        # ------------------------------------------------------

        rename_map = {

            "Player": "player",
            "player_name": "player",

            "Squad": "team",
            "club": "team",

            "Pos": "position",

            "Min": "minutes",
            "Playing Time Min": "minutes",

            "MP": "appearances",
            "Playing Time MP": "appearances",

            "Starts": "starts",

            "Gls": "goals",
            "Goals": "goals",

            "Ast": "assists",
            "Assists": "assists",

            "xG": "xg",

            "xAG": "xa",
            "xA": "xa",
        }

        df = df.rename(columns=rename_map)

        # ------------------------------------------------------
        # SAISON
        # ------------------------------------------------------

        if "season" not in df.columns:

            if "Season" in df.columns:

                df = df.rename(
                    columns={"Season": "season"}
                )

            else:

                df["season"] = None

        # ------------------------------------------------------
        # COLONNES MANQUANTES
        # ------------------------------------------------------

        for column in self.REQUIRED_COLUMNS:

            if column not in df.columns:

                df[column] = None

        # ------------------------------------------------------
        # NUMERIC
        # ------------------------------------------------------

        numeric_columns = [
            "minutes",
            "appearances",
            "starts",
            "goals",
            "assists",
            "xg",
            "xa",
        ]

        for column in numeric_columns:

            df[column] = pd.to_numeric(
                df[column],
                errors="coerce"
            )

        # ------------------------------------------------------
        # IDENTIFICATION
        # ------------------------------------------------------

        df["player"] = (
            df["player"]
            .astype("string")
            .str.strip()
        )

        df["team"] = (
            df["team"]
            .astype("string")
            .str.strip()
        )

        df["position"] = (
            df["position"]
            .astype("string")
            .str.strip()
        )

        df["season"] = (
            df["season"]
            .astype("string")
            .str.strip()
        )

        # ------------------------------------------------------
        # PER 90
        # ------------------------------------------------------

        minutes = df["minutes"]

        df["goals_per90"] = (
            df["goals"] / minutes * 90
        ).where(minutes > 0)

        df["assists_per90"] = (
            df["assists"] / minutes * 90
        ).where(minutes > 0)

        df["xg_per90"] = (
            df["xg"] / minutes * 90
        ).where(minutes > 0)

        df["xa_per90"] = (
            df["xa"] / minutes * 90
        ).where(minutes > 0)

        # ------------------------------------------------------
        # PLAYING TIME
        # ------------------------------------------------------

        # Ici nous conservons le temps de jeu brut.
        #
        # Le calcul définitif de playing_time_score sera
        # effectué dans TransferOutcomeBuilder, car lui seul
        # connaît le contexte du transfert.

        # ------------------------------------------------------
        # DEDUPLICATION
        # ------------------------------------------------------

        df = df.drop_duplicates(
            subset=[
                "player",
                "season",
                "team"
            ]
        )

        # ------------------------------------------------------
        # SORTIE
        # ------------------------------------------------------

        output_columns = [
            "player",
            "season",
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

        return df[
            [
                column
                for column in output_columns
                if column in df.columns
            ]
        ].reset_index(drop=True)

    # ==========================================================
    # FILTER
    # ==========================================================

    def filter_players(
        self,
        player_names: Optional[List[str]] = None,
    ) -> pd.DataFrame:

        if self.dataframe is None:

            raise RuntimeError(
                "Aucune donnée chargée. "
                "Appelez load() avant filter_players()."
            )

        df = self.dataframe.copy()

        if player_names:

            df = df[
                df["player"].isin(player_names)
            ]

        return df

    # ==========================================================
    # FILTER SEASONS
    # ==========================================================

    def filter_seasons(
        self,
        seasons: List[str]
    ) -> pd.DataFrame:

        if self.dataframe is None:

            raise RuntimeError(
                "Aucune donnée chargée."
            )

        return self.dataframe[
            self.dataframe["season"].isin(seasons)
        ].copy()

    # ==========================================================
    # SUMMARY
    # ==========================================================

    def summary(self) -> dict:

        if self.dataframe is None:

            return {}

        df = self.dataframe

        return {
            "rows": len(df),

            "unique_players":
                df["player"].nunique(),

            "unique_seasons":
                df["season"].nunique(),

            "unique_teams":
                df["team"].nunique(),

            "missing_minutes":
                int(df["minutes"].isna().sum()),

            "missing_position":
                int(df["position"].isna().sum()),
        }


# ==============================================================
# TEST
# ==============================================================

if __name__ == "__main__":

    from football_data.loader import FootballDataLoader

    print()
    print("=" * 70)
    print("TEST PERFORMANCE LOADER")
    print("=" * 70)

    football_loader = FootballDataLoader(
        leagues=[
            "ESP-La Liga"
        ],
        seasons=[
            "2223",
            "2324"
        ]
    )

    loader = PerformanceLoader(
        football_loader=football_loader
    )

    try:

        df = loader.load()

        print()
        print("DATASET")
        print("-" * 70)

        print(
            f"Shape : {df.shape}"
        )

        print()
        print("SUMMARY")
        print("-" * 70)

        for key, value in loader.summary().items():

            print(
                f"{key:<25}: {value}"
            )

        print()
        print("COLONNES")
        print("-" * 70)

        print(
            list(df.columns)
        )

        print()
        print("APERÇU")
        print("-" * 70)

        if not df.empty:

            print(
                df.head(10).to_string(
                    index=False
                )
            )

        print()
        print("=" * 70)
        print("✓ PERFORMANCE LOADER TEST TERMINÉ")
        print("=" * 70)

    except Exception as e:

        print()
        print("=" * 70)
        print("✗ PERFORMANCE LOADER TEST FAILED")
        print("=" * 70)

        print(
            f"\nErreur : {e}"
        )

        raise