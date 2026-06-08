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
        # SAFE VARIABLES
        # =====================================

        age = player.get("age", 0)

        salary = player.get(
            "salary",
            999
        )

        contract_years_left = player.get(
            "contract_years_left",
            99
        )

        fit_level = player.get(
            "fit_level",
            "LOW"
        )

        success_probability = player.get(
            "success_probability",
            0
        )

        market_value = player.get(
            "market_value",
            999
        )

        injury_risk = player.get(
            "injury_risk",
            "medium"
        )

        style = player.get(
            "style",
            "balanced_player"
        )

        xg_total = player.get(
            "xg_total",
            0
        )

        # =====================================
        # ECONOMIC MODE
        # =====================================
        if scenario == "economic":

            if age <= 24:
                score += 3
                reasons.append(
                    "fort potentiel de revente"
                )

            if salary <= 10:
                score += 3
                reasons.append(
                    "salaire faible"
                )

            if contract_years_left <= 2:
                score += 2
                reasons.append(
                    "transfert potentiellement abordable"
                )

        # =====================================
        # WIN NOW MODE
        # =====================================
        elif scenario == "win_now":

            if fit_level == "ELITE":
                score += 4
                reasons.append(
                    "impact tactique immédiat"
                )

            elif fit_level == "HIGH":
                score += 2
                reasons.append(
                    "bonne compatibilité tactique"
                )

            if success_probability >= 0.80:
                score += 4
                reasons.append(
                    "très forte probabilité de réussite"
                )

            elif success_probability >= 0.65:
                score += 2
                reasons.append(
                    "bonne probabilité de réussite"
                )

            if 26 <= age <= 30:
                score += 2
                reasons.append(
                    "joueur dans son prime"
                )

            elif 23 <= age <= 25:
                score += 1
                reasons.append(
                    "âge proche du prime"
                )

        # =====================================
        # YOUNG TALENT MODE
        # =====================================
        elif scenario == "young_talent":

            if age <= 22:
                score += 5
                reasons.append(
                    "très jeune talent"
                )

            elif age <= 25:
                score += 3
                reasons.append(
                    "jeune profil à développer"
                )

            if market_value < 60:
                score += 2
                reasons.append(
                    "coût encore raisonnable"
                )

        # =====================================
        # INJURY CRISIS MODE
        # =====================================
        elif scenario == "injury_crisis":

            if injury_risk == "low":
                score += 5
                reasons.append(
                    "très fiable physiquement"
                )

            if fit_level in [
                "HIGH",
                "ELITE"
            ]:
                score += 3
                reasons.append(
                    "adaptation rapide"
                )

        # =====================================
        # STAR DEPARTURE MODE
        # =====================================
        elif scenario == "star_departure":

            if style == "offensive_player":
                score += 4
                reasons.append(
                    "capacité à remplacer production offensive"
                )

            if xg_total >= 8:
                score += 3
                reasons.append(
                    "fort impact offensif"
                )

            if success_probability >= 0.75:
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