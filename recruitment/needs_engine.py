class RecruitmentNeedsEngine:

    def generate_needs(
        self,
        weaknesses,
        squad=None,
        market_targets=None
    ):

        needs = {

            "weakness_needs": [],

            "succession_needs": [],

            "depth_needs": [],

            "market_opportunities": [],

            "upgrade_needs": []
        }

        # =====================================
        # WEAKNESS NEEDS
        # =====================================

        for weakness in weaknesses:

            if weakness == "Création offensive insuffisante":

                needs["weakness_needs"].append({

                    "priority": "HIGH",

                    "position": "LW",

                    "profile": "creative winger",

                    "reason":
                        "manque de création et percussion"
                })

            elif weakness == "Faible efficacité offensive":

                needs["weakness_needs"].append({

                    "priority": "HIGH",

                    "position": "ST",

                    "profile": "clinical finisher",

                    "reason":
                        "faible conversion des occasions"
                })

            elif weakness == "Manque de profils offensifs":

                needs["weakness_needs"].append({

                    "priority": "MEDIUM",

                    "position": "AM/LW",

                    "profile": "offensive playmaker",

                    "reason":
                        "manque de danger offensif"
                })

        # =====================================
        # SQUAD ANALYSIS
        # =====================================

        if squad:

            for player in squad:

                age = player.get("age", 0)

                position = player.get(
                    "position",
                    "UNKNOWN"
                )

                # Succession planning

                if age >= 30:

                    needs["succession_needs"].append({

                        "position": position,

                        "priority": "MEDIUM",

                        "profile":
                            "future starter",

                        "reason":
                            f"anticiper remplacement joueur {age} ans"
                    })

                # Depth planning

                if player.get(
                    "minutes",
                    0
                ) > 3000:

                    needs["depth_needs"].append({

                        "position": position,

                        "priority": "MEDIUM",

                        "profile":
                            "rotation player",

                        "reason":
                            "charge de minutes importante"
                    })

        # =====================================
        # MARKET OPPORTUNITIES
        # =====================================

        if market_targets:

            for target in market_targets:

                market_level = target.get(
                    "market_level",
                    ""
                )

                contract = target.get(
                    "contract_years_left",
                    99
                )

                if (
                    market_level == "GOOD"
                    and contract <= 1
                ):

                    needs[
                        "market_opportunities"
                    ].append({

                        "player":
                            target["player"],

                        "priority":
                            "OPPORTUNITY",

                        "reason":
                            "fin de contrat proche"
                    })

        # =====================================
        # UPGRADE NEEDS
        # =====================================

        if squad:

            for player in squad:

                attacking_score = player.get(
                    "attacking_score",
                    0
                )

                position = player.get(
                    "position",
                    "UNKNOWN"
                )

                if attacking_score < 40:

                    needs["upgrade_needs"].append({

                        "position":
                            position,

                        "priority":
                            "LOW",

                        "profile":
                            "higher ceiling player",

                        "reason":
                            "titulaire améliorable"
                    })

        return needs