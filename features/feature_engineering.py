import numpy as np

class FeatureEngineer:

    def __init__(self):
        pass

    def compute_features(self, xg, goals):
        """
        Transforme les données brutes en features utiles
        """

        if len(xg) == 0:
            raise ValueError("Aucune donnée xG fournie.")

        xg = np.array(xg)
        goals = np.array(goals)

        xg_total = xg.sum()
        goals_total = goals.sum()
        shots = len(xg)

        # éviter division par zéro
        conversion_rate = goals_total / shots if shots > 0 else 0

        avg_xg_per_shot = xg.mean()

        return {
            "xg_total": xg_total,
            "goals_total": goals_total,
            "shots": shots,
            "conversion_rate": conversion_rate,
            "avg_xg_per_shot": avg_xg_per_shot
        }

    def normalize_features(self, features):
        """
        (Optionnel - V2)
        Normalisation simple pour stabiliser les modèles
        """

        normalized = features.copy()

        normalized["xg_total"] = features["xg_total"] / 10
        normalized["shots"] = features["shots"] / 10

        return normalized

    def build_player_profile(self, player_name, features):
        """
        Ajoute une couche 'interprétable' pour l'agent
        """

        profile = {
            "name": player_name,
            "style": self._infer_style(features),
            "efficiency": self._infer_efficiency(features),
            **features
        }

        return profile

    # =========================
    # 🧠 LOGIQUE MÉTIER (IMPORTANT)
    # =========================

    def _infer_style(self, features):
        """
        Détecte le profil du joueur
        """

        if features["shots"] > 10 and features["xg_total"] > 5:
            return "high_volume_attacker"

        elif features["shots"] < 5:
            return "low_volume_player"

        else:
            return "balanced_player"

    def _infer_efficiency(self, features):
        """
        Détecte efficacité
        """

        if features["conversion_rate"] > 1.2:
            return "clinical_finisher"

        elif features["conversion_rate"] < 0.8:
            return "underperforming"

        else:
            return "average_finisher"