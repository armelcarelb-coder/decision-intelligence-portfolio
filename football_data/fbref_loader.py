import soccerdata as sd


class FBrefLoader:

    def __init__(self, leagues, seasons):

        self.scraper = sd.FBref(
            leagues=leagues,
            seasons=seasons
        )

    def standard(self):

        return self.scraper.read_player_season_stats(
            stat_type="standard"
        ).reset_index()

    def shooting(self):

        return self.scraper.read_player_season_stats(
            stat_type="shooting"
        ).reset_index()

    def passing(self):

        return self.scraper.read_player_season_stats(
            stat_type="passing"
        ).reset_index()

    def defensive(self):

        return self.scraper.read_player_season_stats(
            stat_type="defense"
        ).reset_index()

    def possession(self):

        return self.scraper.read_player_season_stats(
            stat_type="possession"
        ).reset_index()