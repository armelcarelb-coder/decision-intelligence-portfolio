class PlayerProfiler:

    def __init__(self):
        pass

    def classify_player(self, player):

        archetypes = []
        secondary = []

        # =========================
        # PER90 METRICS
        # =========================

        shots = player.get("shots_per90", 0)
        xg = player.get("xg_per90", 0)
        goals = player.get("goals_per90", 0)

        assists = player.get("assists_per90", 0)

        key_passes = player.get(
            "key_passes_per90", 0
        )

        progressive_passes = player.get(
            "progressive_passes_per90", 0
        )

        pressures = player.get(
            "pressures_per90", 0
        )

        tackles = player.get(
            "tackles_per90", 0
        )

        interceptions = player.get(
            "interceptions_per90", 0
        )

        dribbles = player.get(
            "dribbles_per90", 0
        )

        # =========================
        # ARCHETYPES
        # =========================

        if shots >= 2 and pressures >= 6:
            archetypes.append("pressing_forward")

        if xg >= 0.45 and shots >= 2.5:
            archetypes.append("box_poacher")

        if progressive_passes >= 4 and key_passes >= 1.5:
            archetypes.append("vertical_creator")

        if progressive_passes >= 6:
            archetypes.append("possession_controller")

        if tackles >= 2 and interceptions >= 1:
            archetypes.append("ball_winning_6")

        if dribbles >= 3 and shots >= 1.5:
            archetypes.append("transition_monster")

        if dribbles >= 4 and assists >= 0.2:
            archetypes.append("touchline_winger")

        if progressive_passes >= 7 and key_passes >= 1:
            archetypes.append("deep_playmaker")

        if shots >= 1.8 and key_passes >= 1.5:
            archetypes.append("inverted_creator")

        if progressive_passes >= 8:
            archetypes.append("elite_progressor")

        # =========================
        # FALLBACK
        # =========================

        if not archetypes:
            archetypes.append("balanced_player")

        primary = archetypes[0]

        if len(archetypes) > 1:
            secondary = archetypes[1:]

        # =========================
        # STYLE SCORING
        # =========================

        attacking_score = 0
        creative_score = 0
        defensive_score = 0

        attacking_score += shots
        attacking_score += dribbles * 0.5
        attacking_score += xg * 4

        creative_score += key_passes * 2
        creative_score += progressive_passes * 0.5
        creative_score += assists * 3

        defensive_score += tackles * 2
        defensive_score += interceptions * 2
        defensive_score += pressures * 0.25

        # =========================
        # STYLE GLOBAL
        # =========================

        max_score = max(
            attacking_score,
            creative_score,
            defensive_score
        )

        if max_score == attacking_score:
            style = "offensive_player"

        elif max_score == creative_score:
            style = "playmaker"

        elif max_score == defensive_score:
            style = "defensive_player"

        else:
            style = "balanced_player"

        # =========================
        # FINISHING EFFICIENCY
        # =========================

        delta = goals - xg

        if delta >= 0.25:
            efficiency = "clinical_finisher"

        elif delta >= 0.10:
            efficiency = "elite_finisher"

        elif delta >= -0.05:
            efficiency = "average_finisher"

        else:
            efficiency = "underperforming"

        # =========================
        # RETURN
        # =========================

        return {

            "primary_archetype": primary,

            "secondary_archetypes": secondary,

            "all_archetypes": archetypes,

            "style": style,

            "efficiency": efficiency,

            # Jour 7
            "attacking_score":
                round(attacking_score, 2),

            "creative_score":
                round(creative_score, 2),

            "defensive_score":
                round(defensive_score, 2)
        }