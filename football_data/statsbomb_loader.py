from statsbombpy import sb
import pandas as pd


class StatsBombLoader:

    def get_matches(
        self,
        competition_id,
        season_id
    ):

        return sb.matches(
            competition_id=competition_id,
            season_id=season_id
        )

    def get_events(self, match_id):

        return sb.events(match_id=match_id)

    def get_lineups(self, match_id):

        return sb.lineups(match_id=match_id)

    def get_competitions(self):

        return sb.competitions()