from interfaces.player_engine import PlayerEngine


class RecruitmentRankingEngine(PlayerEngine):

    """
    =====================================================
    FINAL RECRUITMENT DECISION ENGINE
    =====================================================

    Fusionne tous les moteurs :

    - Tactical Fit
    - Market Intelligence
    - Bayesian Simulation
    - Multi Scenario

    pour produire :

    - recruitment_score
    - recruitment_priority
    - recruitment_reasons

    """

    def __init__(self):

        pass

    # =====================================================
    # PUBLIC API
    # =====================================================

    def process(self, player):

        return self.rank(player)

    # =====================================================
    # MAIN RANKING
    # =====================================================

    def rank(self, player):

        score = 0
        reasons = []

        # ---------------------------------
        # Tactical Fit
        # ---------------------------------

        fit_score = player.get("fit_score", 0)

        score += fit_score * 3

        if fit_score >= 8:

            reasons.append(
                "forte compatibilité tactique"
            )

        elif fit_score >= 6:

            reasons.append(
                "bonne compatibilité tactique"
            )

        # ---------------------------------
        # Market Opportunity
        # ---------------------------------

        market_score = player.get("market_score", 0)

        score += market_score * 2

        if market_score >= 8:

            reasons.append(
                "bonne opportunité marché"
            )

        elif market_score <= 4:

            reasons.append(
                "coût ou risque marché élevé"
            )

        # ---------------------------------
        # Bayesian Success
        # ---------------------------------

        probability = player.get(
            "success_probability",
            0
        )

        score += probability * 20

        if probability >= 0.80:

            reasons.append(
                "forte probabilité de réussite"
            )

        elif probability <= 0.60:

            reasons.append(
                "transfert risqué"
            )

        # ---------------------------------
        # Multi Scenario
        # ---------------------------------

        score += player.get(
            "economic",
            0
        )

        score += player.get(
            "win_now",
            0
        )

        score += player.get(
            "young_talent",
            0
        )

        score += player.get(
            "injury_crisis",
            0
        )

        score += player.get(
            "star_departure",
            0
        )

        # ---------------------------------
        # Bonus jeune joueur
        # ---------------------------------

        age = player.get("age")

        if age is not None:

            if age <= 23:

                score += 5

                reasons.append(
                    "potentiel de progression"
                )

        # ---------------------------------
        # Bonus archetype demandé
        # ---------------------------------

        if player.get("primary_archetype"):

            score += 2

        # ---------------------------------
        # Final Priority
        # ---------------------------------

        priority = self._priority(score)

        player["recruitment_score"] = round(score)

        player["recruitment_priority"] = priority

        player["recruitment_reasons"] = reasons

        return player

    # =====================================================
    # PRIORITY
    # =====================================================

    def _priority(self, score):

        if score >= 80:

            return "HIGH"

        elif score >= 60:

            return "MEDIUM"

        elif score >= 40:

            return "MONITOR"

        else:

            return "LOW"

    # =====================================================
    # TEAM RANKING
    # =====================================================

    def rank_players(self, players):

        ranked = []

        for player in players:

            ranked.append(
                self.process(player)
            )

        ranked.sort(

            key=lambda p:
            p.get(
                "recruitment_score",
                0
            ),

            reverse=True
        )

        return ranked

    # =====================================================
    # TOP TARGETS
    # =====================================================

    def top_targets(

        self,

        players,

        n=10

    ):

        return self.rank_players(players)[:n]

    # =====================================================
    # SUMMARY
    # =====================================================

    def summary(self, players):

        ranking = self.rank_players(players)

        return {

            "players": len(ranking),

            "high_priority":

                len(

                    [

                        p

                        for p in ranking

                        if p["recruitment_priority"] == "HIGH"

                    ]

                ),

            "medium_priority":

                len(

                    [

                        p

                        for p in ranking

                        if p["recruitment_priority"] == "MEDIUM"

                    ]

                ),

            "monitor":

                len(

                    [

                        p

                        for p in ranking

                        if p["recruitment_priority"] == "MONITOR"

                    ]

                )

        }