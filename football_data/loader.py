from football_data.fbref_loader import FBrefLoader
from football_data.transfermarkt_loader import TransfermarktLoader
from football_data.statsbomb_loader import StatsBombLoader


class FootballDataLoader:

    def __init__(
        self,
        leagues=None,
        seasons=None
    ):

        self.leagues = leagues or ["ESP-La Liga"]
        self.seasons = seasons or ["2425"]

        self.fbref = FBrefLoader(
            leagues=self.leagues,
            seasons=self.seasons
        )

        self.transfermarkt = TransfermarktLoader(
            leagues=self.leagues,
            seasons=self.seasons
        )

        self.statsbomb = StatsBombLoader()