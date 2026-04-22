import numpy as np
from models.football_model import FootballAnalystProbabilistic
from engine.decision_engine import PlayerDecisionEngine
from data.football_loader import FootballDataLoader

# 1.Données
loader = FootballDataLoader()

matches = loader.get_matches(11, 42)

# DEBUG joueurs
players = loader.get_players_in_match(matches.iloc[0]['match_id'])
print("Joueurs disponibles :", players)

# Choix manuel (après inspection)
player_name = "Ivan Rakitić"  # à ajuster

xg_all = []
goals_all = []

for match_id in matches.head(5)['match_id']:
    xg, goals = loader.get_player_xg_goals(match_id, player_name)

    xg_all.extend(xg)
    goals_all.extend(goals)

xg = np.array(xg_all)
goals = np.array(goals_all)

# sécurité
if len(xg) == 0:
    print("Pas de données pour ce joueur.")
    exit()

# 2. modèle
model = FootballAnalystProbabilistic(player_name)
model.build_model(xg, goals)
model.train()

# 3. engine
engine = PlayerDecisionEngine(model)

result = engine.make_decision(
    transfer_cost=10,
    salary_cost=5,
    xg_total=xg.sum()
)

print("\n=== DECISION REPORT ===")
print(f"Probabilité performance : {result['probability_performance']:.2%}")
print(f"Profit attendu : {result['expected_profit']:.2f}")
print(f"Décision : {result['decision']}")