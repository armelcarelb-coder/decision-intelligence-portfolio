import numpy as np
from models.football_model import FootballAnalystProbabilistic
from engine.decision_engine import PlayerDecisionEngine
from features.feature_engineering import FeatureEngineer

class ScoutSystem:

    def __init__(self, loader):
        self.loader = loader
        self.feature_engineer = FeatureEngineer()

    def analyze_player(self, player_name, match_ids):
        xg_all = []
        goals_all = []

        for match_id in match_ids:
            xg, goals = self.loader.get_player_xg_goals(match_id, player_name)

            xg_all.extend(xg)
            goals_all.extend(goals)

    # ✅ sécurité
        if len(xg_all) == 0:
            print(f"Aucune donnée pour {player_name}")
            return None

        xg = np.array(xg_all)
        goals = np.array(goals_all)

    # ✅ FEATURE ENGINEERING ICI (AU BON ENDROIT)
        features = self.feature_engineer.compute_features(xg, goals)
        player_profile = self.feature_engineer.build_player_profile(player_name, features)

    # ✅ MODEL
        model = FootballAnalystProbabilistic(player_name)
        model.build_model(xg, goals)
        model.train()

    # ✅ DECISION
        engine = PlayerDecisionEngine(model)

        result = engine.make_decision(
            transfer_cost=10,
            salary_cost=5,
            xg_total=features["xg_total"]
        )

    # ✅ OUTPUT ENRICHI
        return {
            "player": player_name,
            "probability": result["probability_performance"],
            "profit": result["expected_profit"],
            "decision": result["decision"],

            # Features enrichies
            "style": player_profile["style"],
            "efficiency": player_profile["efficiency"],
            "xg_total": features["xg_total"],
            "goals_total": features["goals_total"],
            "shots": features["shots"],
            "conversion_rate": features["conversion_rate"],
            "avg_xg_per_shot": features["avg_xg_per_shot"]
        }

    def rank_players(self, results):
        return sorted(results, key=lambda x: x["profit"], reverse=True)

    def recommend(self, ranked_players):
        if len(ranked_players) == 0:
           return "Aucun joueur analysé"

        best = ranked_players[0]

        if best["profit"] <= 0:
           return f"❌ Aucun joueur rentable. Meilleur candidat: {best['player']} ({best['profit']:.2f})"

        return f"✅ Recruter {best['player']} (Profit attendu: {best['profit']:.2f})"