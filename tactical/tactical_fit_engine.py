class TacticalFitEngine:

    def __init__(self):

        # ADN du jeu recherché (Flick + Barça)
        self.target_profile = {
            "high_pressing": True,
            "vertical_play": True,
            "offensive_intensity": True
        }

    def evaluate_player(self, player):

        score = 0
        reasons = []

        # -----------------------------
        # STYLE DE JEU
        # -----------------------------
        if player["style"] == "offensive_player":
            score += 3
            reasons.append(
                "profil offensif compatible pressing haut"
            )

        elif player["style"] == "balanced_player":
            score += 2
            reasons.append(
                "profil équilibré compatible possession"
            )

        elif player["style"] == "low_volume_player":
            score += 0
            reasons.append(
                "faible activité offensive"
            )

        # -----------------------------
        # EFFICACITÉ
        # -----------------------------
        if player["efficiency"] == "elite_finisher":
            score += 3
            reasons.append(
                "très forte efficacité offensive"
            )

        elif player["efficiency"] == "average_finisher":
            score += 1
            reasons.append(
                "efficacité correcte"
            )

        elif player["efficiency"] == "underperforming":
            score -= 1
            reasons.append(
                "manque d'efficacité devant le but"
            )

        # -----------------------------
        # PROBABILITÉ DE PERFORMANCE
        # -----------------------------
        if player["probability"] >= 0.70:
            score += 3
            reasons.append(
                "forte stabilité de performance"
            )

        elif player["probability"] >= 0.55:
            score += 2
            reasons.append(
                "bonne probabilité de réussite"
            )

        elif player["probability"] >= 0.40:
            score += 1
            reasons.append(
                "profil relativement fiable"
            )

        # -----------------------------
        # VOLUME OFFENSIF
        # -----------------------------
        if player["shots"] >= 20:
            score += 3
            reasons.append(
                "fort volume offensif"
            )

        elif player["shots"] >= 10:
            score += 2
            reasons.append(
                "activité offensive intéressante"
            )

        elif player["shots"] >= 5:
            score += 1
            reasons.append(
                "participation offensive moyenne"
            )

        # -----------------------------
        # xG TOTAL
        # -----------------------------
        if player["xg_total"] >= 5:
            score += 3
            reasons.append(
                "production xG élevée"
            )

        elif player["xg_total"] >= 2:
            score += 2
            reasons.append(
                "bonne création d'occasions"
            )

        elif player["xg_total"] >= 1:
            score += 1
            reasons.append(
                "impact offensif acceptable"
            )

        # -----------------------------
        # CLASSIFICATION FIT
        # -----------------------------
        if score >= 11:
            fit_level = "ELITE"

        elif score >= 8:
            fit_level = "HIGH"

        elif score >= 5:
            fit_level = "MEDIUM"

        else:
            fit_level = "LOW"

        return {
            "fit_score": score,
            "fit_level": fit_level,
            "fit_reasons": reasons
        }