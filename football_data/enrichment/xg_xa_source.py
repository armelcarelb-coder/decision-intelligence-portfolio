from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterable

import pandas as pd


class XgXaSource(ABC):
    """
    Interface générique d'une source externe xG/xA.

    La source doit fournir les données au niveau :

        game_id × player_id

    aucune agrégation saisonnière ne doit être faite ici.
    """

    source_name: str = "UNKNOWN"
    source_library: str = "UNKNOWN"
    source_version: str = "UNKNOWN"

    @abstractmethod
    def load_schedule(
        self,
        league: str,
        season: int,
    ) -> pd.DataFrame:
        """
        Retourne le calendrier source au niveau match.
        """
        raise NotImplementedError

    @abstractmethod
    def load_player_match_stats(
        self,
        league: str,
        season: int,
        match_ids: Iterable[int],
    ) -> pd.DataFrame:
        """
        Retourne les statistiques joueurs au niveau match.
        """
        raise NotImplementedError

    def metadata(self) -> dict:
        return {
            "source_name": self.source_name,
            "source_library": self.source_library,
            "source_version": self.source_version,
        }