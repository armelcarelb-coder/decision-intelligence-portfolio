class Normalizer:

    def normalize_player(self, player):

        minutes = max(
            player.get("minutes", 1),
            1
        )

        factor = 90 / minutes

        return {

            **player,

            "shots_per90":
                round(player.get("shots", 0) * factor, 2),

            "xg_per90":
                round(player.get("xg_total", 0) * factor, 2),

            "goals_per90":
                round(player.get("goals", 0) * factor, 2),

            "assists_per90":
                round(player.get("assists", 0) * factor, 2),

            "key_passes_per90":
                round(player.get("key_passes", 0) * factor, 2),

            "progressive_passes_per90":
                round(
                    player.get("progressive_passes", 0)
                    * factor,
                    2
                ),

            "pressures_per90":
                round(
                    player.get("pressures", 0)
                    * factor,
                    2
                ),

            "tackles_per90":
                round(
                    player.get("tackles", 0)
                    * factor,
                    2
                ),

            "interceptions_per90":
                round(
                    player.get("interceptions", 0)
                    * factor,
                    2
                ),

            "dribbles_per90":
                round(
                    player.get("dribbles", 0)
                    * factor,
                    2
                )
        }