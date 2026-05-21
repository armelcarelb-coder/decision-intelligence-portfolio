class BayesianTransferSimulator:

    def __init__(self):

        pass

    def simulate_transfer(self, player):

        probability = 0.50

        reasons = []

        # -----------------------------
        # TACTICAL FIT
        # -----------------------------
        if player["fit_level"] == "ELITE":
            probability += 0.25
            reasons.append(
                "compatibilité tactique exceptionnelle"
            )

        elif player["fit_level"] == "HIGH":
            probability += 0.15
            reasons.append(
                "bonne compatibilité tactique"
            )

        elif player["fit_level"] == "MEDIUM":
            probability += 0.05

        # -----------------------------
        # MARKET OPPORTUNITY
        # -----------------------------
        if player["market_level"] == "EXCELLENT":
            probability += 0.20
            reasons.append(
                "opportunité marché excellente"
            )

        elif player["market_level"] == "GOOD":
            probability += 0.10
            reasons.append(
                "coût marché raisonnable"
            )

        elif player["market_level"] == "RISKY":
            probability -= 0.10
            reasons.append(
                "risque financier élevé"
            )

        # -----------------------------
        # AGE FACTOR
        # -----------------------------
        if 23 <= player["age"] <= 28:
            probability += 0.10
            reasons.append(
                "âge optimal de performance"
            )

        elif player["age"] >= 31:
            probability -= 0.15
            reasons.append(
                "risque de déclin physique"
            )

        # -----------------------------
        # INJURY RISK
        # -----------------------------
        if player["injury_risk"] == "low":
            probability += 0.10

        elif player["injury_risk"] == "medium":
            probability += 0

        elif player["injury_risk"] == "high":
            probability -= 0.20
            reasons.append(
                "risque blessure important"
            )

        # -----------------------------
        # SALARY RISK
        # -----------------------------
        if player["salary"] >= 18:
            probability -= 0.10
            reasons.append(
                "masse salariale élevée"
            )

        # -----------------------------
        # LIMITES
        # -----------------------------
        probability = max(0.01, min(probability, 0.99))

        # -----------------------------
        # RISK LEVEL
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

            "success_probability": round(probability, 2),

            "transfer_decision": decision,

            "risk_level": risk,

            "simulation_reasons": reasons
        }