import soccerdata as sd


class TransfermarktLoader:

    def __init__(self, leagues, seasons):

        self.scraper = sd.Transfermarkt(
            leagues=leagues,
            seasons=seasons
        )

    def squads(self):

        return self.scraper.read_squads().reset_index()

    def transfers(self):

        return self.scraper.read_transfers().reset_index()