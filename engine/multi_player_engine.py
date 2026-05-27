from engine.scout_system import ScoutSystem


class MultiPlayerEngine:

    def __init__(self, loader):

        self.scout = ScoutSystem(loader)

    # =====================================================
    # SAFE PLAYER TEMPLATE
    # =====================================================
    def build_complete_profile(self, res):

        return {

            # =========================================
            # IDENTITÉ
            # =========================================
            "player": res.get("player", "Unknown"),

            # =========================================
            # PERFORMANCE CORE
            # =========================================
            "profit": res.get("profit", 0),

            "probability": res.get("probability", 0),

            "style": res.get(
                "style",
                "balanced_player"
            ),

            "efficiency": res.get(
                "efficiency",
                "average"
            ),

            # =========================================
            # MINUTES
            # =========================================
            "minutes": res.get("minutes", 0),

            # =========================================
            # OFFENSIVE STATS
            # =========================================
            "shots": res.get("shots", 0),

            "xg_total": res.get("xg_total", 0),

            "goals": res.get("goals", 0),

            "assists": res.get("assists", 0),

            "dribbles": res.get("dribbles", 0),

            # =========================================
            # CREATION
            # =========================================
            "key_passes": res.get(
                "key_passes",
                0
            ),

            "progressive_passes": res.get(
                "progressive_passes",
                0
            ),

            # =========================================
            # DEFENSIVE
            # =========================================
            "pressures": res.get(
                "pressures",
                0
            ),

            "tackles": res.get(
                "tackles",
                0
            ),

            "interceptions": res.get(
                "interceptions",
                0
            )
        }

    # =====================================================
    # ANALYZE MULTIPLE PLAYERS
    # =====================================================
    def analyze_players(self, players, match_ids):

        results = []

        for player in players:

            print(f"\nAnalyse de {player}...")

            try:

                res = self.scout.analyze_player(
                    player,
                    match_ids
                )

                if res is None:
                    continue

                # ✅ PROFIL COMPLET GARANTI
                complete_profile = (
                    self.build_complete_profile(res)
                )

                results.append(
                    complete_profile
                )

            except Exception as e:

                print(
                    f"❌ Erreur analyse {player}: {e}"
                )

        return results

    # =====================================================
    # RANKING
    # =====================================================
    def rank_players(self, results):

        return sorted(
            results,
            key=lambda x: x["profit"],
            reverse=True
        )

    # =====================================================
    # RECOMMENDATION
    # =====================================================
    def recommend(self, ranked_players):

        if len(ranked_players) == 0:

            return "❌ Aucun joueur analysé"

        best = ranked_players[0]

        if best["profit"] <= 0:

            return (
                f"❌ Aucun joueur rentable. "
                f"Meilleur candidat: "
                f"{best['player']} "
                f"({best['profit']:.2f})"
            )

        return (
            f"✅ Recruter {best['player']} "
            f"(Profit attendu: "
            f"{best['profit']:.2f})"
        )