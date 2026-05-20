class MarketIntelligence:

    def evaluate_market(self, player):

        score = 0
        reasons = []

        # -------------------------
        # AGE ANALYSIS
        # -------------------------
        age = player.get("age", 25)

        if 20 <= age <= 26:
            score += 4
            reasons.append(
                "âge optimal performance + revente"
            )

        elif 27 <= age <= 30:
            score += 2
            reasons.append(
                "profil expérience immédiate"
            )

        elif age > 30:
            score -= 1
            reasons.append(
                "faible potentiel de revente"
            )

        # -------------------------
        # MARKET VALUE
        # -------------------------
        value = player.get("market_value", 50)

        if value <= 40:
            score += 4
            reasons.append(
                "opportunité financière intéressante"
            )

        elif value <= 80:
            score += 2
            reasons.append(
                "coût cohérent avec marché"
            )

        else:
            score -= 2
            reasons.append(
                "joueur très coûteux"
            )

        # -------------------------
        # CONTRACT SITUATION
        # -------------------------
        contract_years = player.get(
            "contract_years_left",
            3
        )

        if contract_years <= 1:
            score += 4
            reasons.append(
                "contrat court = opportunité"
            )

        elif contract_years <= 2:
            score += 2
            reasons.append(
                "situation contractuelle favorable"
            )

        # -------------------------
        # SALARY ESTIMATION
        # -------------------------
        salary = player.get("salary", 10)

        if salary <= 8:
            score += 3
            reasons.append(
                "salaire raisonnable"
            )

        elif salary <= 15:
            score += 1
            reasons.append(
                "salaire acceptable"
            )

        else:
            score -= 2
            reasons.append(
                "masse salariale importante"
            )

        # -------------------------
        # INJURY RISK
        # -------------------------
        injury_risk = player.get(
            "injury_risk",
            "medium"
        )

        if injury_risk == "low":
            score += 3
            reasons.append(
                "profil physique fiable"
            )

        elif injury_risk == "medium":
            score += 1
            reasons.append(
                "risque blessure modéré"
            )

        else:
            score -= 3
            reasons.append(
                "risque blessure élevé"
            )

        # -------------------------
        # FINAL CLASSIFICATION
        # -------------------------
        if score >= 14:
            market_level = "ELITE OPPORTUNITY"

        elif score >= 10:
            market_level = "VERY GOOD"

        elif score >= 6:
            market_level = "GOOD"

        else:
            market_level = "RISKY"

        return {
            "market_score": score,
            "market_level": market_level,
            "market_reasons": reasons
        }