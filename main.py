from data.football_loader import FootballDataLoader
from engine.multi_player_engine import MultiPlayerEngine
from agent.scout_agent import ScoutAgent

loader = FootballDataLoader()

matches = loader.get_matches(11, 42)
match_ids = matches.head(5)['match_id']


# joueurs à analyser (extraits du match)
players = loader.get_players_in_match(match_ids.iloc[0])

agent = ScoutAgent(loader)

response = agent.run(
    request="Trouve moi le meilleur joueur rentable",
    players=players,
    match_ids=match_ids
)

print(response)

# ⚠️ on limite pour éviter explosion calcul
players = players[:5]

engine = MultiPlayerEngine(loader)

results = engine.analyze_players(players, match_ids)

ranked = engine.rank_players(results)

print("\n" + "━" * 30)
print("🏆 RANKING JOUEURS")
print("━" * 30)

for i, r in enumerate(ranked, 1):
    print(f"\n#{i} {r['player']}")
    print(f"   💰 Profit attendu : {r['profit']:.2f}")
    print(f"   📊 Probabilité performance : {r['probability']:.2%}")
    print(f"   🎯 Style : {r['style']}")
    print(f"   ⚡ Efficiency : {r['efficiency']}")

print("\n" + "━" * 30)
print("🧠 PLAYER PROFILES")
print("━" * 30)

for r in ranked:
    print(f"\n👤 {r['player']}")
    print(f"   xG total        : {float(r['xg_total']):.2f}")
    print(f"   Goals           : {int(r['goals_total'])}")
    print(f"   Shots           : {r['shots']}")
    print(f"   Conversion rate : {float(r['conversion_rate']):.2f}")
    print(f"   xG / shot       : {float(r['avg_xg_per_shot']):.2f}")

print("\n" + "━" * 30)
print("📢 RECOMMANDATION")
print("━" * 30)

print(engine.recommend(ranked))

best = ranked[0]

print("\n🧠 ANALYSE EXPERT")
print("━" * 30)

print(
    f"{best['player']} présente le meilleur compromis.\n"
    f"- Probabilité élevée ({best['probability']:.2%})\n"
    f"- Risque maîtrisé (profit: {best['profit']:.2f})\n"
    f"- Profil: {best['style']} / {best['efficiency']}"
)

while True:
    user_request = input("\n💬 Que veux-tu analyser ? (exit pour quitter) : ")

    if user_request.lower() == "exit":
        print("👋 Fin du scouting.")
        break

    response = agent.run(
        request=user_request,
        players=players,
        match_ids=match_ids
    )

    print(response)