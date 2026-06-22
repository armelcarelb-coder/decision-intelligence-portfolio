class RecruitmentPrioritizationEngine:

    def __init__(self):

        pass

    def evaluate_player(self, player):

        score = 0

        reasons = []

        # =====================================
        # TACTICAL FIT
        # =====================================

        fit_level = player.get(
            "fit_level",
            "LOW"
        )

        if fit_level == "ELITE":

            score += 30

            reasons.append(
                "fit tactique exceptionnel"
            )

        elif fit_level == "HIGH":

            score += 20

            reasons.append(
                "forte compatibilité tactique"
            )

        elif fit_level == "MEDIUM":

            score += 10

        # =====================================
        # MARKET INTELLIGENCE
        # =====================================

        market_level = player.get(
            "market_level",
            "RISKY"
        )

        if market_level == "EXCELLENT":

            score += 25

            reasons.append(
                "opportunité marché exceptionnelle"
            )

        elif market_level == "GOOD":

            score += 15

            reasons.append(
                "bonne opportunité marché"
            )

        elif market_level == "RISKY":

            score -= 10

            reasons.append(
                "coût ou risque marché élevé"
            )

        # =====================================
        # BAYESIAN SIMULATION
        # =====================================

        probability = player.get(
            "success_probability",
            0.50
        )

        score += int(probability * 30)

        if probability >= 0.80:

            reasons.append(
                "forte probabilité de réussite"
            )

        elif probability < 0.60:

            reasons.append(
                "incertitude importante"
            )

        # =====================================
        # WIN NOW SCENARIO
        # =====================================

        score += player.get(
            "win_now",
            {}
        ).get(
            "scenario_score",
            0
        )

        # =====================================
        # STAR DEPARTURE SCENARIO
        # =====================================

        score += player.get(
            "star_departure",
            {}
        ).get(
            "scenario_score",
            0
        )

        # =====================================
        # YOUNG TALENT BONUS
        # =====================================

        age = player.get(
            "age",
            30
        )

        if age <= 24:

            score += 5

            reasons.append(
                "potentiel de progression"
            )

        # =====================================
        # INJURY PENALTY
        # =====================================

        injury_risk = player.get(
            "injury_risk",
            "medium"
        )

        if injury_risk == "high":

            score -= 10

            reasons.append(
                "risque blessure élevé"
            )

        # =====================================
        # SALARY PENALTY
        # =====================================

        salary = player.get(
            "salary",
            0
        )

        if salary >= 18:

            score -= 5

            reasons.append(
                "impact salarial important"
            )

        # =====================================
        # SCORE LIMITS
        # =====================================

        score = max(
            0,
            min(score, 100)
        )

        # =====================================
        # PRIORITY
        # =====================================

        if score >= 85:

            priority = "CRITICAL"

        elif score >= 70:

            priority = "HIGH"

        elif score >= 55:

            priority = "MEDIUM"

        else:

            priority = "MONITOR"

        return {

            "player": player["player"],

            "recruitment_score": score,

            "priority": priority,

            "reasons": reasons
        }

    def rank_targets(self, players):

        rankings = []

        for player in players:

            rankings.append(
                self.evaluate_player(player)
            )

        rankings = sorted(

            rankings,

            key=lambda x:
            x["recruitment_score"],

            reverse=True
        )

        for rank, player in enumerate(
            rankings,
            start=1
        ):

            player["ranking"] = rank

        return rankings