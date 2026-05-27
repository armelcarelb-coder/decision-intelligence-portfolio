class Normalizer:

    def __init__(self):
        pass

    def per90(self, value, minutes):

        if minutes is None or minutes <= 0:
            return 0

        return round((value / minutes) * 90, 2)

    def normalize_player(self, player):

        minutes = player.get("minutes", 0)

        player["shots_per90"] = self.per90(
            player.get("shots", 0),
            minutes
        )

        player["xg_per90"] = self.per90(
            player.get("xg_total", 0),
            minutes
        )

        player["goals_per90"] = self.per90(
            player.get("goals", 0),
            minutes
        )

        return player