class RecruitmentNeedsEngine:

    def generate_needs(self, weaknesses):

        needs = []

        for weakness in weaknesses:

            # ⚡ Création offensive
            if weakness == "Création offensive insuffisante":

                needs.append({
                    "priority": "HIGH",
                    "position": "LW",
                    "profile": "creative winger",
                    "reason": "manque de création et percussion"
                })

            # ⚡ Efficacité offensive
            elif weakness == "Faible efficacité offensive":

                needs.append({
                    "priority": "HIGH",
                    "position": "ST",
                    "profile": "clinical finisher",
                    "reason": "faible conversion des occasions"
                })

            # ⚡ Peu de joueurs offensifs
            elif weakness == "Manque de profils offensifs":

                needs.append({
                    "priority": "MEDIUM",
                    "position": "AM/LW",
                    "profile": "offensive playmaker",
                    "reason": "manque de danger offensif"
                })

        return needs