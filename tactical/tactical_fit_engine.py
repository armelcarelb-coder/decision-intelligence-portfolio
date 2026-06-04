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

        # =============================
        # SAFE DATA EXTRACTION
        # =============================

        style = player.get(
            "style",
            "balanced_player"
        )

        efficiency = player.get(
            "efficiency",
            "average_finisher"
        )

        shots = player.get(
            "shots",
            0
        )

        xg_total = player.get(
            "xg_total",
            0
        )

        probability = player.get(
            "probability",
            player.get(
                "success_probability",
                None
            )
        )

        # -----------------------------
        # STYLE DE JEU
        # -----------------------------
        if style == "offensive_player":
            score += 3
            reasons.append(
                "profil offensif compatible pressing haut"
            )

        elif style == "low_volume_player":
            score += 2
            reasons.append(
                "profil équilibré compatible possession"
            )

        elif style == "low_volume_player":
            score += 0
            reasons.append(
                "faible activité offensive"
            )

        # -----------------------------
        # EFFICACITÉ
        # -----------------------------
        if efficiency == "elite_finisher":
            score += 3
            reasons.append(
                "très forte efficacité offensive"
            )

        elif efficiency == "average_finisher":
            score += 1
            reasons.append(
                "efficacité correcte"
            )

        elif efficiency == "underperforming":
            score -= 1
            reasons.append(
                "manque d'efficacité devant le but"
            )

        # -----------------------------
        # PROBABILITÉ DE PERFORMANCE
        # -----------------------------
        probability = player.get(
            "probability",
            player.get(
                "success_probability",
                None
            )
        )

        if probability is not None:

            if probability >= 0.70:
                score += 3
                reasons.append(
                    "forte stabilité de performance"
                )

            elif probability >= 0.55:
                score += 2
                reasons.append(
                    "bonne probabilité de réussite"
                )

            elif probability >= 0.40:
                score += 1
                reasons.append(
                    "profil relativement fiable"
                )
        # -----------------------------
        # VOLUME OFFENSIF
        # -----------------------------
        shots = player.get("shots", 0)

        if shots >= 20:

            score += 3

            reasons.append(
                "fort volume offensif"
            )

        elif shots >= 10:

            score += 2

            reasons.append(
                "activité offensive intéressante"
            )

        elif shots >= 5:

            score += 1

            reasons.append(
                "participation offensive moyenne"
            )

        # -----------------------------
        # xG TOTAL
        # -----------------------------
        xg_total = player.get("xg_total", 0)

        if xg_total >= 5:
            score += 3
            reasons.append(
                "production xG élevée"
            )

        elif xg_total >= 2:
            score += 2
            reasons.append(
                "bonne création d'occasions"
            )

        elif xg_total >= 1:
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