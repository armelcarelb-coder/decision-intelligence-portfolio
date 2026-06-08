class BayesianTransferSimulator:

    def __init__(self):

        pass

    def simulate_transfer(self, player):

        probability = 0.50

        reasons = []

        # -----------------------------
        # SAFE VARIABLES
        # -----------------------------
        fit_level = player.get(
            "fit_level",
            "LOW"
        )

        market_level = player.get(
            "market_level",
            "RISKY"
        )

        age = player.get(
            "age",
            0
        )

        injury_risk = player.get(
            "injury_risk",
            "medium"
        )

        salary = player.get(
            "salary",
            0
        )

        # -----------------------------
        # TACTICAL FIT
        # -----------------------------
        if fit_level == "ELITE":
            probability += 0.25
            reasons.append(
                "compatibilité tactique exceptionnelle"
            )

        elif fit_level == "HIGH":
            probability += 0.15
            reasons.append(
                "bonne compatibilité tactique"
            )

        elif fit_level == "MEDIUM":
            probability += 0.05
            reasons.append(
                "compatibilité tactique correcte"
            )

        # -----------------------------
        # MARKET OPPORTUNITY
        # -----------------------------
        if market_level == "EXCELLENT":
            probability += 0.20
            reasons.append(
                "opportunité marché excellente"
            )

        elif market_level == "GOOD":
            probability += 0.10
            reasons.append(
                "coût marché raisonnable"
            )

        elif market_level == "RISKY":
            probability -= 0.10
            reasons.append(
                "risque financier élevé"
            )

        # -----------------------------
        # AGE FACTOR
        # -----------------------------
        if 23 <= age <= 28:
            probability += 0.10
            reasons.append(
                "âge optimal de performance"
            )

        elif 29 <= age <= 30:
            probability += 0.05
            reasons.append(
                "joueur expérimenté"
            )

        elif age >= 31:
            probability -= 0.15
            reasons.append(
                "risque de déclin physique"
            )

        # -----------------------------
        # INJURY RISK
        # -----------------------------
        if injury_risk == "low":
            probability += 0.10
            reasons.append(
                "profil physique fiable"
            )

        elif injury_risk == "medium":
            probability += 0

        elif injury_risk == "high":
            probability -= 0.20
            reasons.append(
                "risque blessure important"
            )

        # -----------------------------
        # SALARY RISK
        # -----------------------------
        if salary >= 18:
            probability -= 0.10
            reasons.append(
                "masse salariale élevée"
            )

        # -----------------------------
        # LIMITES
        # -----------------------------
        probability = max(
            0.01,
            min(probability, 0.99)
        )

        # -----------------------------
        # DECISION
        # -----------------------------
        if probability >= 0.80:
            decision = "SIGN"

        elif probability >= 0.60:
            decision = "MONITOR"

        else:
            decision = "AVOID"

        # -----------------------------
        # RISK PROFILE
        # -----------------------------
        if probability >= 0.75:
            risk = "LOW"

        elif probability >= 0.55:
            risk = "MEDIUM"

        else:
            risk = "HIGH"

        return {

            "success_probability":
                round(probability, 2),

            "transfer_decision":
                decision,

            "risk_level":
                risk,

            "simulation_reasons":
                reasons
        }