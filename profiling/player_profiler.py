class PlayerProfiler:

    def __init__(self):

        pass

    def classify_player(self, player):

        archetypes = []

        secondary = []

        # =====================================
        # VARIABLES
        # =====================================
        shots = player.get("shots_per90", 0)

        xg = player.get("xg_per90", 0)

        assists = player.get("assists_per90", 0)

        key_passes = player.get("key_passes_per90", 0)

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

        # =====================================
        # PRESSING FORWARD
        # =====================================
        if shots >= 2.5 and pressures >= 15:

            archetypes.append(
                "pressing_forward"
            )

        # =====================================
        # BOX POACHER
        # =====================================
        if xg >= 0.45 and shots >= 3:

            archetypes.append(
                "box_poacher"
            )

        # =====================================
        # VERTICAL CREATOR
        # =====================================
        if progressive_passes >= 6 and key_passes >= 2:

            archetypes.append(
                "vertical_creator"
            )

        # =====================================
        # POSSESSION CONTROLLER
        # =====================================
        if progressive_passes >= 8 and pressures >= 10:

            archetypes.append(
                "possession_controller"
            )

        # =====================================
        # BALL WINNING 6
        # =====================================
        if tackles >= 3 and interceptions >= 2:

            archetypes.append(
                "ball_winning_6"
            )

        # =====================================
        # TRANSITION MONSTER
        # =====================================
        if dribbles >= 4 and shots >= 2:

            archetypes.append(
                "transition_monster"
            )

        # =====================================
        # TOUCHLINE WINGER
        # =====================================
        if dribbles >= 5 and assists >= 0.25:

            archetypes.append(
                "touchline_winger"
            )

        # =====================================
        # DEEP PLAYMAKER
        # =====================================
        if progressive_passes >= 9 and key_passes >= 1:

            archetypes.append(
                "deep_playmaker"
            )

        # =====================================
        # INVERTED CREATOR
        # =====================================
        if shots >= 2 and key_passes >= 2:

            archetypes.append(
                "inverted_creator"
            )

        # =====================================
        # ELITE PROGRESSOR
        # =====================================
        if progressive_passes >= 10:

            archetypes.append(
                "elite_progressor"
            )

        # =====================================
        # FALLBACK
        # =====================================
        if len(archetypes) == 0:

            archetypes.append(
                "balanced_player"
            )

        # =====================================
        # ARCHETYPE PRINCIPAL
        # =====================================
        primary = archetypes[0]

        # =====================================
        # ARCHETYPE SECONDAIRE
        # =====================================
        if len(archetypes) > 1:

            secondary = archetypes[1:]

        # =====================================
        # RETOUR
        # =====================================
        return {

            "primary_archetype": primary,

            "secondary_archetypes": secondary,

            "all_archetypes": archetypes
        }