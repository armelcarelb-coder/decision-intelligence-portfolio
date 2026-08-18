from interfaces.player_engine import PlayerEngine


class TacticalFitEngine(PlayerEngine):

    def __init__(self):
        pass

    # ============================================================
    # PUBLIC API
    # ============================================================

    def process(self, player):

        result = self.evaluate_fit(player)

        player.update(result)

        return player

    # ============================================================
    # TACTICAL FIT
    # ============================================================

    def evaluate_fit(self, player):

        position = player.get(
            "position",
            ""
        )

        primary_archetype = player.get(
            "primary_archetype",
            ""
        )

        secondary_archetypes = player.get(
            "secondary_archetypes",
            []
        )

        style = player.get(
            "style",
            ""
        )

        efficiency = player.get(
            "efficiency",
            ""
        )

        attacking_score = player.get(
            "attacking_score",
            0
        )

        creative_score = player.get(
            "creative_score",
            0
        )

        defensive_score = player.get(
            "defensive_score",
            0
        )

        # ========================================================
        # SCORE
        # ========================================================

        fit_score = 0

        fit_reasons = []

        # ========================================================
        # ARCHETYPE FIT
        # ========================================================

        if primary_archetype:

            fit_score += self._archetype_score(
                primary_archetype
            )

            fit_reasons.append(
                f"archetype principal : "
                f"{primary_archetype}"
            )

        # ========================================================
        # SECONDARY ARCHETYPES
        # ========================================================

        if secondary_archetypes:

            fit_score += min(
                len(secondary_archetypes),
                2
            )

        # ========================================================
        # STYLE
        # ========================================================

        style_score = self._style_score(
            style
        )

        fit_score += style_score

        if style:

            fit_reasons.append(
                f"style : {style}"
            )

        # ========================================================
        # EFFICIENCY
        # ========================================================

        efficiency_score = (
            self._efficiency_score(
                efficiency
            )
        )

        fit_score += efficiency_score

        if efficiency:

            fit_reasons.append(
                f"efficacité : {efficiency}"
            )

        # ========================================================
        # PERFORMANCE DIMENSIONS
        # ========================================================

        performance_score = (
            self._performance_score(
                attacking_score,
                creative_score,
                defensive_score,
                position
            )
        )

        fit_score += performance_score

        # ========================================================
        # NORMALISATION
        # ========================================================

        fit_score = min(
            round(fit_score),
            10
        )

        # ========================================================
        # FIT LEVEL
        # ========================================================

        fit_level = self._fit_level(
            fit_score
        )

        return {

            "fit_score":
                fit_score,

            "fit_level":
                fit_level,

            "fit_reasons":
                fit_reasons
        }

    # ============================================================
    # ARCHETYPE SCORE
    # ============================================================

    def _archetype_score(
        self,
        archetype
    ):

        high_value_archetypes = {

            "pressing_forward",
            "box_poacher",
            "vertical_creator",
            "possession_controller",
            "ball_winning_6",
            "transition_monster",
            "touchline_winger",
            "deep_playmaker",
            "inverted_creator",
            "elite_progressor"
        }

        if archetype in high_value_archetypes:

            return 3

        return 1

    # ============================================================
    # STYLE SCORE
    # ============================================================

    def _style_score(
        self,
        style
    ):

        if style in {

            "offensive_player",
            "playmaker",
            "defensive_player"

        }:

            return 1

        return 0

    # ============================================================
    # EFFICIENCY SCORE
    # ============================================================

    def _efficiency_score(
        self,
        efficiency
    ):

        scores = {

            "clinical_finisher": 2,

            "elite_finisher": 2,

            "average_finisher": 1,

            "underperforming": 0
        }

        return scores.get(
            efficiency,
            0
        )

    # ============================================================
    # PERFORMANCE SCORE
    # ============================================================

    def _performance_score(
        self,
        attacking_score,
        creative_score,
        defensive_score,
        position
    ):

        if position in {
            "ST",
            "LW",
            "RW"
        }:

            if attacking_score >= 5:

                return 2

            if attacking_score >= 3:

                return 1

        elif position in {
            "AM",
            "CM"
        }:

            if creative_score >= 5:

                return 2

            if creative_score >= 3:

                return 1

        elif position in {
            "DM",
            "CB"
        }:

            if defensive_score >= 5:

                return 2

            if defensive_score >= 3:

                return 1

        return 0

    # ============================================================
    # FIT LEVEL
    # ============================================================

    def _fit_level(
        self,
        fit_score
    ):

        if fit_score >= 8:

            return "HIGH"

        elif fit_score >= 5:

            return "MEDIUM"

        return "LOW"


# ================================================================
# DIRECT TEST
# ================================================================

if __name__ == "__main__":

    engine = TacticalFitEngine()

    player = {

        "player":
            "Test Player",

        "position":
            "ST",

        "primary_archetype":
            "pressing_forward",

        "secondary_archetypes":
            [
                "box_poacher",
                "transition_monster"
            ],

        "style":
            "offensive_player",

        "efficiency":
            "clinical_finisher",

        "attacking_score":
            8.0,

        "creative_score":
            3.0,

        "defensive_score":
            2.0
    }

    result = engine.process(
        player
    )

    print(
        "\n========================================"
    )

    print(
        "TACTICAL FIT ENGINE TEST"
    )

    print(
        "========================================"
    )

    print(
        f"Player : "
        f"{result['player']}"
    )

    print(
        f"Position : "
        f"{result['position']}"
    )

    print(
        f"Primary archetype : "
        f"{result['primary_archetype']}"
    )

    print(
        f"Fit score : "
        f"{result['fit_score']}"
    )

    print(
        f"Fit level : "
        f"{result['fit_level']}"
    )

    print(
        "Reasons :"
    )

    for reason in result["fit_reasons"]:

        print(
            f"- {reason}"
        )