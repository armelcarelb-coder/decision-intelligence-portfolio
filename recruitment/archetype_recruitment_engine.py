from interfaces.player_engine import PlayerEngine

class ArchetypeRecruitmentEngine:

    def generate_archetype_targets(self, needs):

        archetype_targets = []

        # =====================================
        # WEAKNESS NEEDS
        # =====================================

        for need in needs.get("weakness_needs", []):

            position = need.get("position", "")
            profile = need.get("profile", "")

            if profile == "clinical finisher":

                archetype_targets.append({

                    "need_type": "weakness",

                    "position": position,

                    "priority": need.get("priority"),

                    "required_archetypes": [

                        "box_poacher",
                        "pressing_forward"
                    ],

                    "reason": need.get("reason")
                })

            elif profile == "creative winger":

                archetype_targets.append({

                    "need_type": "weakness",

                    "position": position,

                    "priority": need.get("priority"),

                    "required_archetypes": [

                        "inverted_creator",
                        "touchline_winger"
                    ],

                    "reason": need.get("reason")
                })

            elif profile == "offensive playmaker":

                archetype_targets.append({

                    "need_type": "weakness",

                    "position": position,

                    "priority": need.get("priority"),

                    "required_archetypes": [

                        "vertical_creator",
                        "advanced_playmaker"
                    ],

                    "reason": need.get("reason")
                })

        # =====================================
        # SUCCESSION NEEDS
        # =====================================

        for need in needs.get("succession_needs", []):

            position = need.get("position", "")

            archetype_targets.append({

                "need_type": "succession",

                "position": position,

                "priority": need.get("priority"),

                "required_archetypes":
                    self._position_archetypes(position),

                "reason": need.get("reason")
            })

        # =====================================
        # DEPTH NEEDS
        # =====================================

        for need in needs.get("depth_needs", []):

            position = need.get("position", "")

            archetype_targets.append({

                "need_type": "depth",

                "position": position,

                "priority": need.get("priority"),

                "required_archetypes":
                    self._position_archetypes(position),

                "reason": need.get("reason")
            })

        # =====================================
        # UPGRADE NEEDS
        # =====================================

        for need in needs.get("upgrade_needs", []):

            position = need.get("position", "")

            archetype_targets.append({

                "need_type": "upgrade",

                "position": position,

                "priority": need.get("priority"),

                "required_archetypes":
                    self._position_archetypes(position),

                "reason": need.get("reason")
            })

        return archetype_targets

    # =====================================
    # POSITION → ARCHETYPES
    # =====================================

    def _position_archetypes(self, position):

        mapping = {

            "ST": [

                "pressing_forward",
                "box_poacher",
                "transition_monster"
            ],

            "LW": [

                "touchline_winger",
                "inverted_creator"
            ],

            "RW": [

                "touchline_winger",
                "inverted_creator"
            ],

            "AM": [

                "advanced_playmaker",
                "vertical_creator"
            ],

            "CM": [

                "vertical_creator",
                "deep_playmaker",
                "possession_controller"
            ],

            "DM": [

                "ball_winning_6",
                "deep_playmaker"
            ],

            "LB": [

                "attacking_fullback",
                "wide_progressor"
            ],

            "RB": [

                "attacking_fullback",
                "wide_progressor"
            ],

            "CB": [

                "ball_playing_defender",
                "aggressive_defender"
            ]
        }

        return mapping.get(position, [])