from config.strategy_config import STRATEGIES
from strategy.strategy_manager import StrategyManager
from agent.memory import AgentMemory
from agent.comparator import PlayerComparator
from llm.llm_reasoner import LLMReasoner

class ScoutAgent:

    def __init__(self, loader):
        from engine.multi_player_engine import MultiPlayerEngine

        self.engine = MultiPlayerEngine(loader)

        # ✅ mémoire agent
        self.memory = AgentMemory()

        self.strategy_manager = StrategyManager()

        self.comparator = PlayerComparator()

        self.reasoner = LLMReasoner()

    # 🧠 1. Compréhension simple (rule-based NLP)

    
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

        results = self.engine.analyze_players(players, match_ids)
        total_players = len(results)

        if len(results) == 0:
           return "❌ Aucun joueur analysable."
        
        if "compare" in request.lower():

            last_player = self.memory.get_last_recommendation()

            if last_player is None:
                 return "❌ Aucun joueur précédent à comparer."

            ranked = self.memory.last_results

            current_best = ranked[0]

            comparison = self.comparator.compare_players(
                last_player,
                current_best
            )

            return "\n".join(comparison)

        strategies = self.strategy_manager.detect_strategies(request)
        print(f"🧠 Stratégies détectées: {strategies}")

        filtered = self.strategy_manager.apply_strategies(
            results,
            strategies
        )
        filtered_count = len(filtered)

        if filtered_count == 0:
           fallback_mode = True
           filtered = results
        else:
           fallback_mode = False

        ranked = self.engine.rank_players(filtered)
        best = ranked[0]
        
        llm_explanation = self.reasoner.explain_recommendation(best)

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

    {llm_explanation}
    """
        self.memory.save_interaction(request, response)

        return response   # ✅ FIX CRITIQUE
        
