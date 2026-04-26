from data.football_loader import FootballDataLoader
from engine.multi_player_engine import MultiPlayerEngine

loader = FootballDataLoader()

matches = loader.get_matches(11, 42)
match_ids = matches.head(5)['match_id']

# joueurs à analyser (extraits du match)
players = loader.get_players_in_match(match_ids.iloc[0])

# ⚠️ on limite pour éviter explosion calcul
players = players[:5]

engine = MultiPlayerEngine(loader)

results = engine.analyze_players(players, match_ids)

ranked = engine.rank_players(results)

print("\n=== RANKING JOUEURS ===")
for r in ranked:
    print(
    f"{r['player']} | Profit: {r['profit']:.2f} | Prob: {r['probability']:.2%} | "
    f"Style: {r['style']} | Efficiency: {r['efficiency']} | "
    f"xG: {r['xg_total']:.2f} | Goals: {r['goals'] if 'goals' in r else 'N/A'} | Shots: {r['shots']}"
)

print("\n=== PLAYER PROFILES ===")
for r in ranked:
    profile = {
        "name": r["player"],
        "style": r["style"],
        "efficiency": r["efficiency"],
        "xg_total": round(r["xg_total"], 2),
        "goals_total": r["goals_total"],
        "shots": r["shots"],
        "conversion_rate": round(r["conversion_rate"], 2),
        "avg_xg_per_shot": round(r["avg_xg_per_shot"], 2)
    }
    print(profile)

print("\n=== RECOMMANDATION ===")
print(engine.recommend(ranked))