from engine.multi_player_engine import MultiPlayerEngine

class ScoutAgent:

    def __init__(self, loader):
        self.engine = MultiPlayerEngine(loader)

    def run(self, players, match_ids):
        results = self.engine.analyze_players(players, match_ids)
        ranked = self.engine.rank_players(results)

        recommendation = self.engine.recommend(ranked)

        return {
            "ranking": ranked,
            "recommendation": recommendation
        }