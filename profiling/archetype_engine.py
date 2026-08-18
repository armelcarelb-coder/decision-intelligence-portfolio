from interfaces.player_engine import PlayerEngine


class ArchetypeEngine(PlayerEngine):

    def __init__(self):
        pass

    # ============================================================
    # STANDARD ENGINE API
    # ============================================================

    def process(self, player):

        archetype_profile = self.classify_archetypes(player)

        player.update(archetype_profile)

        return player

    # ============================================================
    # ARCHETYPE CLASSIFICATION
    # ============================================================

    def classify_archetypes(self, player):

        archetypes = []

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

        assists = player.get(
            "assists_per90",
            0
        )

        # ========================================================
        # ARCHETYPES
        # ========================================================

        if shots >= 2 and pressures >= 6:

            archetypes.append(
                "pressing_forward"
            )

        if xg >= 0.45 and shots >= 2.5:

            archetypes.append(
                "box_poacher"
            )

        if (
            progressive_passes >= 4
            and key_passes >= 1.5
        ):

            archetypes.append(
                "vertical_creator"
            )

        if progressive_passes >= 6:

            archetypes.append(
                "possession_controller"
            )

        if (
            tackles >= 2
            and interceptions >= 1
        ):

            archetypes.append(
                "ball_winning_6"
            )

        if (
            dribbles >= 3
            and shots >= 1.5
        ):

            archetypes.append(
                "transition_monster"
            )

        if (
            dribbles >= 4
            and assists >= 0.2
        ):

            archetypes.append(
                "touchline_winger"
            )

        if (
            progressive_passes >= 7
            and key_passes >= 1
        ):

            archetypes.append(
                "deep_playmaker"
            )

        if (
            shots >= 1.8
            and key_passes >= 1.5
        ):

            archetypes.append(
                "inverted_creator"
            )

        if progressive_passes >= 8:

            archetypes.append(
                "elite_progressor"
            )

        # ========================================================
        # FALLBACK
        # ========================================================

        if not archetypes:

            archetypes.append(
                "balanced_player"
            )

        # ========================================================
        # PRIMARY / SECONDARY
        # ========================================================

        primary = archetypes[0]

        secondary = archetypes[1:]

        return {

            "primary_archetype":
                primary,

            "secondary_archetypes":
                secondary,

            "all_archetypes":
                archetypes
        }


# ================================================================
# DIRECT TEST
# ================================================================

if __name__ == "__main__":

    engine = ArchetypeEngine()

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
    print("ARCHETYPE ENGINE TEST")
    print("=" * 60)

    print(
        f"\nPlayer : "
        f"{result['player']}"
    )

    print(
        f"Position : "
        f"{result['position']}"
    )

    print(
        f"\nPrimary archetype : "
        f"{result['primary_archetype']}"
    )

    print(
        f"Secondary archetypes : "
        f"{result['secondary_archetypes']}"
    )

    print(
        f"All archetypes : "
        f"{result['all_archetypes']}"
    )

    print("\n" + "=" * 60)