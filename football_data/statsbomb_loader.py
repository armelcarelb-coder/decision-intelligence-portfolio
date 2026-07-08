from statsbombpy import sb
import pandas as pd


class StatsBombLoader:

    def get_matches(self, competition_id, season_id):

        return sb.matches(
            competition_id=competition_id,
            season_id=season_id
        )

    def get_barca_matches(self, matches):

        return matches[
            (matches["home_team"] == "Barcelona") |
            (matches["away_team"] == "Barcelona")
        ]

    def get_player_events(self, player_name, match_ids):

        all_events = []

        for match_id in match_ids:

            try:

                events = sb.events(match_id=match_id)

                player_events = events[
                    events["player"] == player_name
                ]

                if len(player_events):

                    all_events.append(player_events)

            except Exception:

                pass

        if not all_events:

            return pd.DataFrame()

        return pd.concat(all_events)