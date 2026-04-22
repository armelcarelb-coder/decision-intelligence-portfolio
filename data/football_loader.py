from statsbombpy import sb
import pandas as pd

class FootballDataLoader :
    def __init__(self):
        """Initialise la connexion aux données ouvertes de StatsBomb."""
        self.free_competitions = None

    def get_competitions(self):
        """Affiche les competitions disponibles gratuitement."""
        self.free_competitions = sb.competitions()
        return self.free_competitions
    
    def get_matches(self,competition_id , season_id):
        """Récupère la liste des matchs pour une saison donnée."""
        return sb.matches(competition_id=competition_id, season_id=season_id)
    
    def get_events(self, match_id):
        return sb.events(match_id=match_id)

    def get_players_in_match(self, match_id):
        events = self.get_events(match_id)
        return events['player'].dropna().unique()
    
    def get_player_xg_goals(self, match_id, player_name):
        events = sb.events(match_id=match_id)

        player_events = events[events['player'] == player_name]

        shots = player_events[player_events['type'] == 'Shot']

        xg = shots['shot_statsbomb_xg'].fillna(0).values
        goals = shots['shot_outcome'].apply(lambda x: 1 if x == 'Goal' else 0).values

        return xg, goals
    
    def get_players_in_match(self, match_id):
       events = sb.events(match_id=match_id)
       return events['player'].dropna().unique()
    
    def get_player_stats(self, match_id, player_name):
       events = sb.events(match_id=match_id)

       player_events = events[events['player'] == player_name]

       shots = player_events[player_events['type'] == 'Shot']

       if len(shots) == 0:
           return {
              "xg_total": 0,
              "goals": 0,
              "shots": 0
            }

       xg_total = shots['shot_statsbomb_xg'].fillna(0).sum()
       goals = (shots['shot_outcome'] == 'Goal').sum()
       shots_count = len(shots)

       return {
          "xg_total": xg_total,
          "goals": goals,
          "shots": shots_count
        }
    
    
# --- TEST RAPIDE ---

if __name__ == "__main__":
    loader = FootballDataLoader()

    print("Récupération des matchs de La Liga...")

    matches = loader.get_matches(11, 42)
    print(f"Trouvé {len(matches)} matchs.")
    print(matches[['match_id', 'home_team', 'away_team']].head())

    # 👉 on prend un match exemple
    match_id = matches.iloc[0]['match_id']

    players = loader.get_players_in_match(match_id)

    print(f"\nNombre de joueurs trouvés : {len(players)}")
    print(players[:10])  # preview

    player_name = players[9]  # test rapide

    stats = loader.get_player_stats(match_id, player_name)

    print(f"\nStats pour {player_name} :")
    print(stats)