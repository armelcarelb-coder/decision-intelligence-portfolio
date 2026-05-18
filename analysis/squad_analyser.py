import numpy as np

class SquadAnalyzer:

    def analyze_team(self, players_data):

        total_xg = 0
        total_goals = 0
        total_shots = 0

        offensive_players = 0

        for p in players_data:

            total_xg += p["xg_total"]
            total_goals += p["goals_total"]
            total_shots += p["shots"]

            if p["shots"] >= 10:
                offensive_players += 1

        conversion_rate = (
            total_goals / total_shots
            if total_shots > 0 else 0
        )

        report = {
            "team_xg": round(total_xg, 2),
            "team_goals": int(total_goals),
            "team_shots": int(total_shots),
            "conversion_rate": round(conversion_rate, 2),
            "offensive_players": offensive_players
        }

        return report
    
    def detect_weaknesses(self, report):

        weaknesses = []

        if report["conversion_rate"] <= 0.18:
            weaknesses.append(
                "Faible efficacité offensive"
            )

        if report["offensive_players"] <= 3:
            weaknesses.append(
                "Manque de profils offensifs"
            )

        if report["team_xg"] <= 8:
            weaknesses.append(
                "Création offensive insuffisante"
            )

        return weaknesses