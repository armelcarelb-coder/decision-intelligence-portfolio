from football_data.base_loader import BaseLoader

import soccerdata as sd


class TransfermarktLoader(BaseLoader):

    def __init__(self, leagues=None, seasons=None):

        super().__init__(leagues, seasons)

        self.scraper = sd.Transfermarkt(

            leagues=self.leagues,

            seasons=self.seasons
        )

    def load(self):

        return self.scraper.read_squads().reset_index()
    
if __name__ == "__main__":

    loader = TransfermarktLoader()

    df = loader.load()

    print(df.head())

    print(df.columns)

    print(len(df))