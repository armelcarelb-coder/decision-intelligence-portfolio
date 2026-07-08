from football_data.fbref_loader import FBrefLoader
from football_data.transfermarkt_loader import TransfermarktLoader
from football_data.statsbomb_loader import StatsBombLoader


class FootballDataLoader:

    def __init__(self, leagues, seasons):

        self.fbref = FBrefLoader(
            leagues,
            seasons
        )

        self.transfermarkt = TransfermarktLoader(
            leagues,
            seasons
        )

        self.statsbomb = StatsBombLoader()