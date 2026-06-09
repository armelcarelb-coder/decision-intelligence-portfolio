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

        succession_positions = set()
        depth_positions = set()
        upgrade_positions = set()

        # =====================================
        # WEAKNESS NEEDS
        # =====================================

        for weakness in weaknesses:

            if weakness == "Création offensive insuffisante":

                needs["weakness_needs"].append({

                    "priority": "HIGH",
                    "position": "LW",
                    "profile": "creative winger",
                    "reason": "manque de création et percussion"
                })

            elif weakness == "Faible efficacité offensive":

                needs["weakness_needs"].append({

                    "priority": "HIGH",
                    "position": "ST",
                    "profile": "clinical finisher",
                    "reason": "faible conversion des occasions"
                })

            elif weakness == "Manque de profils offensifs":

                needs["weakness_needs"].append({

                    "priority": "MEDIUM",
                    "position": "AM/LW",
                    "profile": "offensive playmaker",
                    "reason": "manque de danger offensif"
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

                contract = player.get(
                    "contract_years_left",
                    99
                )

                minutes = player.get(
                    "minutes",
                    0
                )

                injury_risk = player.get(
                    "injury_risk",
                    "low"
                )

                player_score = max(

                    player.get(
                        "attacking_score",
                        0
                    ),

                    player.get(
                        "creative_score",
                        0
                    ),

                    player.get(
                        "defensive_score",
                        0
                    )
                )

                # -------------------------
                # SUCCESSION
                # -------------------------

                if (
                    age >= 32
                    and position not in succession_positions
                ):

                    succession_positions.add(position)

                    needs["succession_needs"].append({

                        "position": position,
                        "priority": "MEDIUM",
                        "profile": "future starter",
                        "reason":
                            f"anticiper remplacement joueur {age} ans"
                    })

                if (
                    contract <= 1
                    and position not in succession_positions
                ):

                    succession_positions.add(position)

                    needs["succession_needs"].append({

                        "position": position,
                        "priority": "HIGH",
                        "profile": "replacement",
                        "reason":
                            "contrat proche expiration"
                    })

                # -------------------------
                # DEPTH
                # -------------------------

                if (
                    minutes > 3000
                    and position not in depth_positions
                ):

                    depth_positions.add(position)

                    needs["depth_needs"].append({

                        "position": position,
                        "priority": "MEDIUM",
                        "profile": "rotation player",
                        "reason":
                            "charge de minutes importante"
                    })

                elif (
                    injury_risk == "high"
                    and position not in depth_positions
                ):

                    depth_positions.add(position)

                    needs["depth_needs"].append({

                        "position": position,
                        "priority": "HIGH",
                        "profile": "reliable backup",
                        "reason":
                            "risque blessure élevé"
                    })

                # -------------------------
                # UPGRADE
                # -------------------------

                if (
                    player_score < 40
                    and position not in upgrade_positions
                ):

                    upgrade_positions.add(position)

                    needs["upgrade_needs"].append({

                        "position": position,
                        "priority": "LOW",
                        "profile": "higher ceiling player",
                        "reason":
                            "titulaire améliorable"
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

                    needs["market_opportunities"].append({

                        "player":
                            target.get(
                                "player",
                                "Unknown"
                            ),

                        "priority":
                            "OPPORTUNITY",

                        "reason":
                            "fin de contrat proche"
                    })

        return needs