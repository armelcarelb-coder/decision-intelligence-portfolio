from abc import ABC, abstractmethod
import pandas as pd


class BaseLoader(ABC):
    """
    Interface commune de tous les loaders de données.

    Chaque source de données (FBref, StatsBomb, Transfermarkt,
    Understat...) devra implémenter ces méthodes afin que
    FootballDataLoader puisse les utiliser sans connaître
    leur implémentation interne.
    """

    def __init__(self, leagues=None, seasons=None):

        self.leagues = leagues or []
        self.seasons = seasons or []

    # =====================================================
    # MAIN PUBLIC API
    # =====================================================

    @abstractmethod
    def load(self) -> pd.DataFrame:
        """
        Retourne le DataFrame principal de la source.
        """
        pass

    # =====================================================
    # OPTIONAL METHODS
    # =====================================================

    def health_check(self) -> bool:
        """
        Vérifie que la source est accessible.

        Peut être redéfinie par chaque loader.
        """

        return True

    def available_columns(self):

        df = self.load()

        if df.empty:
            return []

        return list(df.columns)

    def summary(self):

        df = self.load()

        return {

            "rows": len(df),

            "columns": len(df.columns),

            "column_names": list(df.columns)
        }