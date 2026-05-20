import pandas as pd
from data.football_loader import FootballDataLoader
from agent.scout_agent import ScoutAgent
from analysis.squad_analyser import SquadAnalyzer
from statsbombpy import sb
from recruitment.needs_engine import RecruitmentNeedsEngine
from tactical.tactical_fit_engine import TacticalFitEngine
from market.market_intelligence import MarketIntelligence


competitions = sb.competitions()

print(competitions[
    competitions["competition_name"] == "La Liga"
][[
    "season_name",
    "competition_id",
    "season_id"
]])

loader = FootballDataLoader()

matches_1 = loader.get_matches(11, 42)
matches_2 = loader.get_matches(11, 90)

matches = pd.concat([
    matches_1,
    matches_2
])

matches = loader.get_barca_matches(matches)

match_ids = matches["match_id"]

players = loader.get_barca_players(match_ids)

match_ids = matches['match_id']

players = loader.get_barca_players_only(match_ids)

agent = ScoutAgent(loader)
analyzer = SquadAnalyzer()

needs_engine = RecruitmentNeedsEngine()



# 1. Lancer agent UNE FOIS pour générer les données
agent.run("analyse initiale", players, match_ids)

# 2. Récupérer les résultats du scouting
results = agent.memory.last_results

# 3. Analyse l'effectif
team_report = analyzer.analyze_team(results)

# 4. Détecter les faiblesses
weaknesses = analyzer.detect_weaknesses(team_report)

# 5. Générer besoins recrutement
needs = needs_engine.generate_needs(weaknesses)

fit_engine = TacticalFitEngine()

market_engine = MarketIntelligence()

recruitment_targets = [

    {
        "player": "Rafael Leao",
        "position": "LW",
        "style": "offensive_player",
        "efficiency": "elite_finisher",
        "probability": 0.81,

        "shots": 42,
        "xg_total": 8.4,

        "age": 25,
        "market_value": 90,
        "contract_years_left": 3,
        "salary": 14,
        "injury_risk": "medium"
    },

    {
        "player": "Joshua Kimmich",
        "position": "CM",
        "style": "balanced_player",
        "efficiency": "elite_controller",
        "probability": 0.88,

        "shots": 12,
        "xg_total": 2.1,

        "age": 29,
        "market_value": 50,
        "contract_years_left": 1,
        "salary": 16,
        "injury_risk": "low"
    },

    {
        "player": "Alexander Isak",
        "position": "ST",
        "style": "offensive_player",
        "efficiency": "clinical_finisher",
        "probability": 0.79,

        "shots": 51,
        "xg_total": 10.7,

        "age": 24,
        "market_value": 75,
        "contract_years_left": 4,
        "salary": 12,
        "injury_risk": "medium"
    }
]

fit_results = []

for target in recruitment_targets:

    fit = fit_engine.evaluate_player(target)
    market = market_engine.evaluate_market(target)
    fit_results.append({
        **target,
        **fit,
        **market
    })

print("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
print("📊 ANALYSE EFFECTIF BARÇA")
print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

print(f"\n👥 Joueurs analysés: {len(results)}")
print(f"🎮 Matchs analysés: {len(match_ids)}")

print(team_report)

print("\n⚠️ FAIBLESSES DÉTECTÉES")
for w in weaknesses:
    print(f"- {w}")

print("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
print("🎯 BESOINS RECRUTEMENT")
print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

for n in needs:

    print(f"""
📌 Priorité : {n['priority']}
🎯 Poste : {n['position']}
👤 Profil recherché : {n['profile']}
🧠 Raison : {n['reason']}
""")
    
print("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
print("🧠 TACTICAL FIT ENGINE")
print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

for player in fit_results:

    print(f"""
👤 {player['player']}
⚽ Position : {player['position']}

📊 Fit Score : {player['fit_score']}
🔥 Fit Level : {player['fit_level']}

🧠 Tactical Traits:
- Style : {player['style']}
- Efficiency : {player['efficiency']}

print("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
print("💰 MARKET INTELLIGENCE")
print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

📈 Market Score : {player['market_score']}
🏷️ Market Level : {player['market_level']}
""")
    
while True:
    request = input("\n💬 Que veux-tu analyser ? (exit pour quitter) : ")

    if request.lower() == "exit":
        break

    response = agent.run(request, players, match_ids)
    print(response)

print(agent.memory.get_history())