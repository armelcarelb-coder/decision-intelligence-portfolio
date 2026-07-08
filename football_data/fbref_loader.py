import soccerdata as sd


class FBrefLoader:

    def __init__(self, leagues, seasons):

        self.scraper = sd.FBref(
            leagues=leagues,
            seasons=seasons
        )

    def player_standard_stats(self):

        return self.scraper.read_player_season_stats(
            stat_type="standard"
        ).reset_index()

    def player_shooting_stats(self):

        return self.scraper.read_player_season_stats(
            stat_type="shooting"
        ).reset_index()

    def player_passing_stats(self):

        return self.scraper.read_player_season_stats(
            stat_type="passing"
        ).reset_index()