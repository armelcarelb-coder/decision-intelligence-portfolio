class StrategicSquadPlanningEngine:

    def generate_plan(
        self,
        squad,
        recruitment_targets=None
    ):

        plan = {

            "succession_plan": [],

            "departure_risks": [],

            "age_curve_risks": [],

            "archetype_gaps": [],

            "budget_scenarios": [],

            "roadmap_3_years": []
        }

        # =====================================
        # SUCCESSION PLAN
        # =====================================

        for player in squad:

            age = player.get("age", 25)

            if age >= 30:

                plan["succession_plan"].append({

                    "player":
                        player.get("player"),

                    "position":
                        player.get("position"),

                    "priority":
                        "HIGH",

                    "replacement_window":
                        "1-2 years"
                })

        # =====================================
        # DEPARTURE RISKS
        # =====================================

        for player in squad:

            contract = player.get(
                "contract_years_left",
                99
            )

            if contract <= 1:

                plan["departure_risks"].append({

                    "player":
                        player.get("player"),

                    "position":
                        player.get("position"),

                    "risk":
                        "HIGH",

                    "reason":
                        "contract expiring"
                })

        # =====================================
        # AGE CURVE RISKS
        # =====================================

        for player in squad:

            age = player.get("age", 25)

            if age >= 32:

                plan["age_curve_risks"].append({

                    "player":
                        player.get("player"),

                    "position":
                        player.get("position"),

                    "risk":
                        "DECLINE_RISK"
                })

        # =====================================
        # ARCHETYPE GAPS
        # =====================================

        existing_archetypes = set()

        for player in squad:

            existing_archetypes.add(

                player.get(
                    "primary_archetype",
                    ""
                )
            )

        desired_archetypes = [

            "pressing_forward",

            "box_poacher",

            "vertical_creator",

            "deep_playmaker",

            "ball_winning_6",

            "touchline_winger",

            "inverted_creator",

            "ball_playing_defender"
        ]

        for archetype in desired_archetypes:

            if archetype not in existing_archetypes:

                plan["archetype_gaps"].append({

                    "missing_archetype":
                        archetype,

                    "priority":
                        "MEDIUM"
                })

        # =====================================
        # BUDGET SCENARIOS
        # =====================================

        if recruitment_targets:

            total_cost = sum(

                p.get(
                    "market_value",
                    0
                )

                for p in recruitment_targets
            )

            plan["budget_scenarios"].append({

                "scenario":
                    "full_rebuild",

                "estimated_cost":
                    total_cost
            })

            plan["budget_scenarios"].append({

                "scenario":
                    "top_2_targets",

                "estimated_cost":
                    total_cost * 0.65
            })

            plan["budget_scenarios"].append({

                "scenario":
                    "minimum_reinforcement",

                "estimated_cost":
                    total_cost * 0.35
            })

        # =====================================
        # ROADMAP
        # =====================================

        year1 = []
        year2 = []
        year3 = []

        for item in plan["succession_plan"]:

            year1.append(

                f"Scout replacement for "
                f"{item['player']}"
            )

        for item in plan["departure_risks"]:

            year2.append(

                f"Replace "
                f"{item['player']}"
            )

        for item in plan["archetype_gaps"]:

            year3.append(

                f"Add archetype "
                f"{item['missing_archetype']}"
            )

        plan["roadmap_3_years"] = {

            "year_1": year1,

            "year_2": year2,

            "year_3": year3
        }

        return plan