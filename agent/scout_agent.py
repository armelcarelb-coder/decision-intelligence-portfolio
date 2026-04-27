from config.strategy_config import STRATEGIES

class ScoutAgent:

    def __init__(self, loader):
        from engine.multi_player_engine import MultiPlayerEngine
        self.engine = MultiPlayerEngine(loader)

    # 🧠 1. Compréhension simple (rule-based NLP)
    def interpret_request(self, request):
        request = request.lower()

        active_strategies = []

        for key in STRATEGIES.keys():
            if key in request:
                active_strategies.append(key)

        return active_strategies

    # 🎯 2. Application des filtres
    def apply_strategies(self, players, strategies):
        if not strategies:
            return players

        filtered = players

        for strat in strategies:
            filtered = list(filter(STRATEGIES[strat], filtered))

        return filtered

    # 🧠 3. RUN AGENT
    def run(self, request, players, match_ids):

        print("\n🤖 AGENT SCOUT ACTIVÉ")
        print(f"🎯 Mission: {request}")

        # 1. Analyse brute
        results = self.engine.analyze_players(players[:5], match_ids)

        if len(results) == 0:
            return "❌ Aucun joueur analysable."

        # 2. Compréhension
        strategies = self.interpret_request(request)
        print(f"🧠 Stratégies détectées: {strategies}")

        # 3. Filtrage
        filtered = self.apply_strategies(results, strategies)

        if len(filtered) == 0:
            print("⚠️ Aucun joueur ne correspond aux critères.")
            print("🔄 Relaxation des contraintes...")

            filtered = results  # fallback

            fallback_mode = True
        else:
            fallback_mode = False

        # 4. Ranking
        ranked = self.engine.rank_players(filtered)

        best = ranked[0]

        # 5. Recommandation
        decision = self.engine.recommend(ranked)

        # 6. Réponse intelligente
        response = f"""
📊 SCOUT REPORT

🎯 Critères: {', '.join(strategies) if strategies else 'Aucun filtre'}

🏆 Meilleur joueur: {best['player']}

💰 Profit attendu: {best['profit']:.2f}
📈 Probabilité: {best['probability']:.2%}

🎯 Profil:
- Style: {best['style']}
- Efficiency: {best['efficiency']}

📢 Décision:
{decision}

note = "⚠️ Critères non satisfaits, meilleure alternative proposée\n" if fallback_mode else ""
"""

        return response