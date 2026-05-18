import pandas as pd
from data.football_loader import FootballDataLoader
from agent.scout_agent import ScoutAgent
from analysis.squad_analyser import SquadAnalyzer
from statsbombpy import sb
from recruitment.needs_engine import RecruitmentNeedsEngine

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

players = loader.get_all_players(match_ids)

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
    
while True:
    request = input("\n💬 Que veux-tu analyser ? (exit pour quitter) : ")

    if request.lower() == "exit":
        break

    response = agent.run(request, players, match_ids)
    print(response)

print(agent.memory.get_history())