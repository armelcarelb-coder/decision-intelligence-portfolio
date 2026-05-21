class MultiScenarioEngine:

    def __init__(self):

        self.scenarios = [

            "economic",

            "win_now",

            "young_talent",

            "injury_crisis",

            "star_departure"
        ]

    def evaluate(self, player, scenario):

        score = 0

        reasons = []

        # =====================================
        # ECONOMIC MODE
        # =====================================
        if scenario == "economic":

            if player["age"] <= 24:
                score += 3
                reasons.append(
                    "fort potentiel de revente"
                )

            if player["salary"] <= 10:
                score += 3
                reasons.append(
                    "salaire faible"
                )

            if player["contract_years_left"] <= 2:
                score += 2
                reasons.append(
                    "transfert potentiellement abordable"
                )

        # =====================================
        # WIN NOW MODE
        # =====================================
        elif scenario == "win_now":

            if player["fit_level"] == "ELITE":
                score += 4
                reasons.append(
                    "impact tactique immédiat"
                )

            if player["success_probability"] >= 0.80:
                score += 4
                reasons.append(
                    "très forte probabilité de réussite"
                )

            if 26 <= player["age"] <= 30:
                score += 2
                reasons.append(
                    "joueur dans son prime"
                )

        # =====================================
        # YOUNG TALENT MODE
        # =====================================
        elif scenario == "young_talent":

            if player["age"] <= 22:
                score += 5
                reasons.append(
                    "très jeune talent"
                )

            elif player["age"] <= 25:
                score += 3
                reasons.append(
                    "jeune profil à développer"
                )

            if player["market_value"] < 60:
                score += 2
                reasons.append(
                    "coût encore raisonnable"
                )

        # =====================================
        # INJURY CRISIS MODE
        # =====================================
        elif scenario == "injury_crisis":

            if player["injury_risk"] == "low":
                score += 5
                reasons.append(
                    "très fiable physiquement"
                )

            if player["fit_level"] in ["HIGH", "ELITE"]:
                score += 3
                reasons.append(
                    "adaptation rapide"
                )

        # =====================================
        # STAR DEPARTURE MODE
        # =====================================
        elif scenario == "star_departure":

            if player["style"] == "offensive_player":
                score += 4
                reasons.append(
                    "capacité à remplacer production offensive"
                )

            if player["xg_total"] >= 8:
                score += 3
                reasons.append(
                    "fort impact offensif"
                )

            if player["success_probability"] >= 0.75:
                score += 2
                reasons.append(
                    "transition sécurisée"
                )

        # =====================================
        # LEVEL
        # =====================================
        if score >= 8:
            level = "PRIORITY"

        elif score >= 5:
            level = "INTERESTING"

        else:
            level = "LOW_PRIORITY"

        return {

            "scenario_score": score,

            "scenario_level": level,

            "scenario_reasons": reasons
        }