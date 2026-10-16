from config.strategy_config import STRATEGIES
from strategy.strategy_manager import StrategyManager
from agent.memory import AgentMemory
from agent.comparator import PlayerComparator
from llm.llm_reasoner import LLMReasoner
from tactical.tactical_fit_engine import TacticalFitEngine
from normalization.normalization import Normalizer
from profiling.player_profiler import PlayerProfiler
from engine.role_aware_talent_engine import (
    PlayerSeasonRecord,
    RoleAwareBayesianTalentEngine,
)

class ScoutAgent:

    def __init__(self, loader, talent_engine=None):
        from engine.multi_player_engine import MultiPlayerEngine

        self.engine = MultiPlayerEngine(loader)

        self.memory = AgentMemory()
        self.strategy_manager = StrategyManager()
        self.comparator = PlayerComparator()
        self.reasoner = LLMReasoner()
        self.tactical_engine = TacticalFitEngine()
        self.profiler = PlayerProfiler()

        # Role-aware Bayesian ability engine.
        # If not provided, it can be trained later from available player data.
        self.talent_engine = talent_engine

    # 🧠 1. Compréhension simple (rule-based NLP)

    def _build_talent_records(self, players):
        records = []

        for player in players:
            metrics = {
                "goals": player.get("goals", 0),
                "xg": player.get("xg", 0),
                "assists": player.get("assists", 0),
                "xag": player.get("xag", 0),
                "successful_dribbles": player.get(
                    "successful_dribbles", 0
                ),
                "attempted_dribbles": player.get(
                    "attempted_dribbles", 0
                ),
                "progressive_actions_per90": player.get(
                    "progressive_actions_per90", 0
                ),
                "crosses_per90": player.get("crosses_per90", 0),
                "pressures_per90": player.get("pressures_per90", 0),
                "tackles": player.get("tackles", 0),
                "interceptions": player.get("interceptions", 0),
                "passes_completed": player.get("passes_completed", 0),
                "passes_attempted": player.get("passes_attempted", 0),
            }

            records.append(
                PlayerSeasonRecord(
                    player=player.get("player"),
                    position=player.get("position_group", "UNKNOWN"),
                    minutes=player.get("minutes", 0),
                    metrics=metrics,
                )
            )

        return records

    def _ensure_talent_engine(self, players):
        if self.talent_engine is not None:
            return self.talent_engine

        records = self._build_talent_records(players)

        engine = RoleAwareBayesianTalentEngine(
            abilities=[
                "finishing",
                "chance_creation",
                "ball_progression",
                "defensive_impact",
                "pressing_impact",
            ]
        )

        engine.build_model(records)
        engine.train()

        self.talent_engine = engine

        return engine
    
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

        results = self.engine.analyze_players(players[:50], match_ids)

        if results:
            talent_engine = self._ensure_talent_engine(results)

            for player in results:
                try:
                    player = talent_engine.process(player)
                except ValueError as error:
                    player["ability_profile"] = {}
                    player["ability_error"] = str(error)
        profile = self.profiler.classify_player(best)
        ability_summary = self._format_ability_profile(
            best.get("ability_profile", {})
        )

        if results is None:
            results = []

        if len(results) == 0:
            return "❌ Aucun joueur analysable."

        total_players = len(results)

        # Role-aware Bayesian enrichment.
        if results:
            talent_engine = self._ensure_talent_engine(results)

            for player in results:
                try:
                    player = talent_engine.process(player)
                except ValueError as error:
                    player["ability_profile"] = {}
                    player["ability_error"] = str(error)

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

        normalizer = Normalizer()
        player = normalizer.normalize_player(best)

        profile = self.profiler.classify_player(best)

        best = {
            **best,
            **profile
        }

        tactical_fit = self.tactical_engine.evaluate_player(best)

        llm_explanation = self.reasoner.explain_recommendation(best)

        self.memory.save_results(ranked)
        self.memory.save_recommendation(ranked[0])
        self.memory.save_strategies(strategies)

        decision = self.engine.recommend(ranked)

        reasons = self.build_reasoning(best, strategies)
        reasons.extend(
            self._build_ability_reasoning(best, strategies)
        )

        ability_summary = self._format_ability_profile(
            best.get("ability_profile", {})
        )

        note = ""

        if fallback_mode:
            note = (
                "⚠️ Aucun joueur ne correspond strictement aux critères "
                "→ meilleure alternative proposée\n"
            )

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

    🧠 Role-Aware Ability Profile:
    {ability_summary}
    

    🧠 Role-Aware Ability Profile:
    {ability_summary}

    🧠 Raisonnement:
        - {chr(10).join(reasons)}

    📢 Décision:
        {decision}

    {llm_explanation}

    📊 Tactical Fit:
    - Fit score : {tactical_fit['fit_score']}/15
    - Fit level : {tactical_fit['fit_level']}

    🧠 Archetype Analysis:
    - Primary : {best['primary_archetype']}
    - Secondary : {best['secondary_archetypes']}

    🧠 Compatibilité tactique:
    - {chr(10).join(tactical_fit['fit_reasons'])}
    """

        self.memory.save_interaction(request, response)

        return response

    def _format_ability_profile(self, ability_profile):
        if not ability_profile:
            return (
                "Aucune estimation d’abilité disponible "
                "pour ce joueur."
            )

        labels = {
            "finishing": "Finition",
            "chance_creation": "Création",
            "ball_progression": "Progression",
            "defensive_impact": "Impact défensif",
            "pressing_impact": "Pressing",
        }

        lines = []

        for ability, values in ability_profile.items():
            label = labels.get(
                ability,
                ability.replace("_", " ").title()
            )

            lines.append(
                f"- {label}: "
                f"{values['posterior_mean']:.2f} "
                f"(HDI 94%: "
                f"{values['hdi_low']:.2f}–"
                f"{values['hdi_high']:.2f})"
            )

        return "\n".join(lines)

    def _build_ability_reasoning(self, player, strategies):
        reasons = []
        profile = player.get("ability_profile", {})
        reasons = self.build_reasoning(best, strategies)
        reasons.extend(
            self._build_ability_reasoning(best, strategies)
        )
  
        if not profile:
            return reasons

        if "offensif" in strategies:
            finishing = profile.get("finishing", {}).get(
                "probability_above_1"
            )

            creation = profile.get("chance_creation", {}).get(
                "probability_above_1"
            )

            if finishing is not None and finishing > 0.5:
                reasons.append(
                    "finition estimée au-dessus du niveau de référence"
                )

            if creation is not None and creation > 0.5:
                reasons.append(
                    "capacité de création estimée "
                    "au-dessus du niveau de référence"
                )

        if "low_risk" in strategies:
            defensive = profile.get("defensive_impact", {}).get(
                "probability_above_1"
            )

            if defensive is not None and defensive > 0.5:
                reasons.append(
                    "impact défensif estimé "
                    "au-dessus du niveau de référence"
                )

        return reasons

    def _build_talent_records(self, players):
        records = []

        for player in players:
            minutes = player.get("minutes", 0)

            if minutes <= 0:
                continue

            metrics = {
                "goals": player.get("goals", 0),
                "xg_total": player.get("xg_total", 0),
                "assists": player.get("assists", 0),
                "key_passes": player.get("key_passes", 0),
                "progressive_passes": player.get(
                    "progressive_passes", 0
                ),
                "tackles": player.get("tackles", 0),
                "interceptions": player.get(
                    "interceptions", 0
                ),
                "pressures": player.get("pressures", 0),
            }

            records.append(
                PlayerSeasonRecord(
                    player=player.get("player", "Unknown"),
                    position=player.get(
                        "position_group",
                        "UNKNOWN"
                    ),
                    minutes=minutes,
                    metrics=metrics,
                )
            )

        return records

  
