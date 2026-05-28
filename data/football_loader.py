from statsbombpy import sb
import pandas as pd


class FootballDataLoader:

    def __init__(self):

        pass

    # =========================================
    # MATCHES
    # =========================================
    def get_matches(self, competition_id, season_id):

        return sb.matches(
            competition_id=competition_id,
            season_id=season_id
        )

    # =========================================
    # BARÇA MATCHES
    # =========================================
    def get_barca_matches(self, matches):

        return matches[
            (matches["home_team"] == "Barcelona")
            |
            (matches["away_team"] == "Barcelona")
        ]

    # =========================================
    # BARÇA PLAYERS ONLY
    # =========================================
    def get_barca_players_only(self, match_ids):

        players = set()

        for match_id in match_ids:

            try:

                events = sb.events(match_id=match_id)

                # équipe Barça seulement
                barca_events = events[
                    events["team"] == "Barcelona"
                ]

                if "player" in barca_events.columns:

                    unique_players = (
                        barca_events["player"]
                        .dropna()
                        .unique()
                    )

                    players.update(unique_players)

            except Exception as e:

                print(
                    f"Erreur match {match_id}: {e}"
                )

        return list(players)

    # =========================================
    # PLAYER EVENTS
    # =========================================
    def get_player_events(self, player_name, match_ids):

        all_events = []

        for match_id in match_ids:

            try:

                events = sb.events(match_id=match_id)

                player_events = events[
                    events["player"] == player_name
                ]

                if len(player_events) > 0:

                    all_events.append(player_events)

            except Exception as e:

                print(
                    f"Erreur récupération events {player_name}: {e}"
                )

        if len(all_events) == 0:

            return pd.DataFrame()

        return pd.concat(all_events)

    # =========================================
    # LEGACY xG/goals METHOD
    # =========================================
    def get_player_xg_goals(self, match_id, player_name):

        try:

            events = sb.events(match_id=match_id)

            player_shots = events[
                (events["player"] == player_name)
                &
                (events["type"] == "Shot")
            ]

            xg = (
                player_shots["shot_statsbomb_xg"]
                .fillna(0)
                .tolist()
            )

            goals = []

            for _, shot in player_shots.iterrows():

                if shot.get("shot_outcome") == "Goal":
                    goals.append(1)
                else:
                    goals.append(0)

            return xg, goals

        except Exception:

            return [], []