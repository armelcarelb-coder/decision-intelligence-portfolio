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
    
    def get_player_events(self,match_id, player_name):
        """Extrait tous les évènements (tirs,passes) d'un joueur précis sur un match."""
        events = sb.events(match_id=match_id)
        player_data = events[events['player'] == player_name]
        return player_data
    
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
    
# --- TEST RAPIDE ---

if __name__ == "__main__":
    loader = FootballDataLoader()

    # Exemple : Laliga 2015/2016 (ID 11, Saison 42)
    print("Récupération des matchs de La Liga...")

    matches = loader.get_matches(11,42)
    print(f"Trouvé{len(matches)} matchs.")
    print(matches[['match_id', 'home_team', 'away_team']].head())

    loader.get_players_in_match()
    print("players")
