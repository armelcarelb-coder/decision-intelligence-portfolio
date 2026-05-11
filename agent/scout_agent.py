from config.strategy_config import STRATEGIES
from agent.memory import AgentMemory

class ScoutAgent:

    def __init__(self, loader):
        from engine.multi_player_engine import MultiPlayerEngine

        self.engine = MultiPlayerEngine(loader)

        # ✅ mémoire agent
        self.memory = AgentMemory()

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

    
    def build_reasoning(self, best_player, strategies):
        reasons = []

        if "rentable" in strategies:
           reasons.append("profit attendu élevé")

        if "low_risk" in strategies:
            reasons.append("probabilité de performance élevée")

        if "offensif" in strategies:
            reasons.append("profil offensif (volume de jeu élevé)")

        if "efficace" in strategies:
            reasons.append("excellente efficacité devant le but")

    # fallback si rien détecté
        if not reasons:
            reasons.append("meilleur compromis global")

        return reasons

        # 🧠 3. RUN AGENT
    def run(self, request, players, match_ids):

        print("\n🤖 AGENT SCOUT ACTIVÉ")
        print(f"🎯 Mission: {request}")

        results = self.engine.analyze_players(players[:5], match_ids)
        total_players = len(results)

        if len(results) == 0:
           return "❌ Aucun joueur analysable."

        strategies = self.interpret_request(request)
        print(f"🧠 Stratégies détectées: {strategies}")

        filtered = self.apply_strategies(results, strategies)
        filtered_count = len(filtered)

        if filtered_count == 0:
           fallback_mode = True
           filtered = results
        else:
           fallback_mode = False

        ranked = self.engine.rank_players(filtered)
        best = ranked[0]
        self.memory.save_results(ranked)
        self.memory.save_recommendation(ranked[0])
        self.memory.save_strategies(strategies)

        decision = self.engine.recommend(ranked)

        reasons = self.build_reasoning(best, strategies)

        note = ""
        if fallback_mode:
           note = "⚠️ Aucun joueur ne correspond strictement aux critères → meilleure alternative proposée\n"

        response = f"""
    🤖 AGENT SCOUT — ANALYSE INTELLIGENTE

    📊 Analyse globale:
      - Joueurs analysés: {total_players}
      - Joueurs après filtrage: {filtered_count}

    🎯 Critères: {', '.join(strategies) if strategies else 'Aucun filtre'}

    {note}

    🏆 Meilleur joueur: {best['player']}

    💰 Profit attendu: {best['profit']:.2f}
    📈 Probabilité: {best['probability']:.2%}

    🎯 Profil:
      - Style: {best['style']}
      - Efficiency: {best['efficiency']}

    🧠 Raisonnement:
      - {chr(10).join(reasons)}

    📢 Décision:
     {decision}
    """
        self.memory.save_interaction(request, response)

        return response   # ✅ FIX CRITIQUE
        
