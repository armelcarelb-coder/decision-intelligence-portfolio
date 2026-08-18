from interfaces.player_engine import PlayerEngine


class PlayerProfiler(PlayerEngine):

    def __init__(self):
        pass

    # ============================================================
    # STANDARD ENGINE API
    # ============================================================

    def process(self, player):

        profile = self.classify_player(player)

        player.update(profile)

        return player

    # ============================================================
    # PLAYER PROFILE
    # ============================================================

    def classify_player(self, player):

        # ========================================================
        # PER90 METRICS
        # ========================================================

        shots = player.get(
            "shots_per90",
            0
        )

        xg = player.get(
            "xg_per90",
            0
        )

        goals = player.get(
            "goals_per90",
            0
        )

        assists = player.get(
            "assists_per90",
            0
        )

        key_passes = player.get(
            "key_passes_per90",
            0
        )

        progressive_passes = player.get(
            "progressive_passes_per90",
            0
        )

        pressures = player.get(
            "pressures_per90",
            0
        )

        tackles = player.get(
            "tackles_per90",
            0
        )

        interceptions = player.get(
            "interceptions_per90",
            0
        )

        dribbles = player.get(
            "dribbles_per90",
            0
        )

        # ========================================================
        # STYLE SCORING
        # ========================================================

        attacking_score = 0

        creative_score = 0

        defensive_score = 0

        # --------------------------------------------------------
        # ATTACKING
        # --------------------------------------------------------

        attacking_score += shots

        attacking_score += (
            dribbles * 0.5
        )

        attacking_score += (
            xg * 4
        )

        # --------------------------------------------------------
        # CREATIVE
        # --------------------------------------------------------

        creative_score += (
            key_passes * 2
        )

        creative_score += (
            progressive_passes * 0.5
        )

        creative_score += (
            assists * 3
        )

        # --------------------------------------------------------
        # DEFENSIVE
        # --------------------------------------------------------

        defensive_score += (
            tackles * 2
        )

        defensive_score += (
            interceptions * 2
        )

        defensive_score += (
            pressures * 0.25
        )

        # ========================================================
        # GLOBAL STYLE
        # ========================================================

        max_score = max(
            attacking_score,
            creative_score,
            defensive_score
        )

        if max_score == attacking_score:

            style = "offensive_player"

        elif max_score == creative_score:

            style = "playmaker"

        else:

            style = "defensive_player"

        # ========================================================
        # FINISHING EFFICIENCY
        # ========================================================

        delta = goals - xg

        if delta >= 0.25:

            efficiency = "clinical_finisher"

        elif delta >= 0.10:

            efficiency = "elite_finisher"

        elif delta >= -0.05:

            efficiency = "average_finisher"

        else:

            efficiency = "underperforming"

        # ========================================================
        # RETURN PROFILE ONLY
        # ========================================================

        return {

            "style": style,

            "efficiency": efficiency,

            "attacking_score":
                round(
                    attacking_score,
                    2
                ),

            "creative_score":
                round(
                    creative_score,
                    2
                ),

            "defensive_score":
                round(
                    defensive_score,
                    2
                )
        }


# ================================================================
# DIRECT TEST
# ================================================================

if __name__ == "__main__":

    engine = PlayerProfiler()

    test_player = {

        "player": "Test Player",

        "position": "ST",

        "shots_per90": 3.0,

        "xg_per90": 0.50,

        "goals_per90": 0.60,

        "assists_per90": 0.20,

        "key_passes_per90": 1.6,

        "progressive_passes_per90": 4.5,

        "pressures_per90": 7.0,

        "tackles_per90": 1.0,

        "interceptions_per90": 0.5,

        "dribbles_per90": 3.5
    }

    result = engine.process(
        test_player
    )

    print("\n" + "=" * 60)
    print("PLAYER PROFILER TEST")
    print("=" * 60)

    print(
        f"\nPlayer : "
        f"{result['player']}"
    )

    print(
        f"Style : "
        f"{result['style']}"
    )

    print(
        f"Efficiency : "
        f"{result['efficiency']}"
    )

    print(
        f"Attacking score : "
        f"{result['attacking_score']}"
    )

    print(
        f"Creative score : "
        f"{result['creative_score']}"
    )

    print(
        f"Defensive score : "
        f"{result['defensive_score']}"
    )

    print(
        "\nArchetype fields present :",
        any(
            key in result
            for key in [
                "primary_archetype",
                "secondary_archetypes",
                "all_archetypes"
            ]
        )
    )

    print("\n" + "=" * 60)