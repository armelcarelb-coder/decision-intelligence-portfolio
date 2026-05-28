import numpy as np

from models.football_model import (
    FootballAnalystProbabilistic
)

from engine.decision_engine import (
    PlayerDecisionEngine
)

from features.feature_engineering import (
    FeatureEngineer
)


class ScoutSystem:

    def __init__(self, loader):

        self.loader = loader

        self.feature_engineer = FeatureEngineer()

    def analyze_player(self, player_name, match_ids):

        xg_all = []
        goals_all = []

        # =========================
        # NOUVELLES STATS
        # =========================
        total_minutes = 0

        assists = 0
        key_passes = 0
        progressive_passes = 0

        pressures = 0
        tackles = 0
        interceptions = 0

        dribbles = 0

        # =========================
        # MATCH LOOP
        # =========================
        for match_id in match_ids:

            # xG + goals
            xg, goals = self.loader.get_player_xg_goals(
                match_id,
                player_name
            )

            xg_all.extend(xg)
            goals_all.extend(goals)

            # =========================
            # EVENTS DATA
            # =========================
            events = self.loader.get_player_events(
                match_id,
                player_name
            )

            if events is None or len(events) == 0:
                continue

            # Minutes
            total_minutes += 90

            # Assists
            assists += len(events[
                events["pass_goal_assist"] == True
            ])

            # Key passes
            key_passes += len(events[
                events["pass_shot_assist"] == True
            ])

            # Progressive passes
            progressive_passes += len(events[
                events["type"] == "Pass"
            ])

            # Pressures
            pressures += len(events[
                events["type"] == "Pressure"
            ])

            # Tackles
            tackles += len(events[
                events["type"] == "Duel"
            ])

            # Interceptions
            interceptions += len(events[
                events["type"] == "Interception"
            ])

            # Dribbles
            dribbles += len(events[
                events["type"] == "Dribble"
            ])

        # =========================
        # SECURITE
        # =========================
        if len(xg_all) == 0:

            print(f"Aucune donnée pour {player_name}")

            return None

        xg = np.array(xg_all)

        goals = np.array(goals_all)

        # =========================
        # FEATURE ENGINEERING
        # =========================
        features = self.feature_engineer.compute_features(
            xg,
            goals
        )

        player_profile = (
            self.feature_engineer.build_player_profile(
                player_name,
                features
            )
        )

        # =========================
        # MODEL
        # =========================
        model = FootballAnalystProbabilistic(
            player_name
        )

        model.build_model(xg, goals)

        model.train()

        # =========================
        # DECISION ENGINE
        # =========================
        engine = PlayerDecisionEngine(model)

        result = engine.make_decision(

            transfer_cost=10,

            salary_cost=5,

            xg_total=features["xg_total"]
        )

        # =========================
        # FINAL OUTPUT
        # =========================
        return {

            "player": player_name,

            "probability":
                result["probability_performance"],

            "profit":
                result["expected_profit"],

            "decision":
                result["decision"],

            # =====================
            # CORE FOOTBALL FEATURES
            # =====================
            "style":
                player_profile["style"],

            "efficiency":
                player_profile["efficiency"],

            "xg_total":
                features["xg_total"],

            "goals":
                int(features["goals_total"]),

            "shots":
                int(features["shots"]),

            "conversion_rate":
                features["conversion_rate"],

            "avg_xg_per_shot":
                features["avg_xg_per_shot"],

            # =====================
            # ADVANCED FEATURES
            # =====================
            "minutes":
                total_minutes,

            "assists":
                assists,

            "key_passes":
                key_passes,

            "progressive_passes":
                progressive_passes,

            "pressures":
                pressures,

            "tackles":
                tackles,

            "interceptions":
                interceptions,

            "dribbles":
                dribbles
        }

    def rank_players(self, results):

        return sorted(
            results,
            key=lambda x: x["profit"],
            reverse=True
        )

    def recommend(self, ranked_players):

        if len(ranked_players) == 0:

            return "Aucun joueur analysé"

        best = ranked_players[0]

        if best["profit"] <= 0:

            return (
                f"❌ Aucun joueur rentable. "
                f"Meilleur candidat: "
                f"{best['player']} "
                f"({best['profit']:.2f})"
            )

        return (
            f"✅ Recruter {best['player']} "
            f"(Profit attendu: "
            f"{best['profit']:.2f})"
        )