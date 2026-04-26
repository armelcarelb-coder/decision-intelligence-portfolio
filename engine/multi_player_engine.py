from engine.scout_system import ScoutSystem

class MultiPlayerEngine:

    def __init__(self, loader):
        self.scout = ScoutSystem(loader)

    def analyze_players(self, players, match_ids):
        results = []

        for player in players:
            print(f"\nAnalyse de {player}...")
            res = self.scout.analyze_player(player, match_ids)

            if res is not None:
                results.append(res)

        return results

    def rank_players(self, results):
        return sorted(results, key=lambda x: x["profit"], reverse=True)

    def recommend(self, ranked_players):
        if len(ranked_players) == 0:
            return "Aucun joueur analysé"

        best = ranked_players[0]

        if best["profit"] <= 0:
            return f"❌ Aucun joueur rentable. Meilleur candidat: {best['player']} ({best['profit']:.2f})"

        return f"✅ Recruter {best['player']} (Profit attendu: {best['profit']:.2f})"