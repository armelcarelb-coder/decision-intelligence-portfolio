import numpy as np

class PlayerDecisionEngine:

    def __init__(self, model):
        if model.trace is None:
            raise ValueError("Model must be trained before decision.")
        
        self.model = model
        self.samples = model.trace.posterior["talent"].values

    def compute_probability(self, threshold=1.0):
        prob = (self.samples > threshold).mean()
        return prob

    def compute_expected_profit(
        self,
        transfer_cost,
        salary_cost,
        xg_total,
        market_value_factor=10
    ):
        """
        xg_total = volume d’occasions du joueur
        market_value_factor = conversion talent → argent
        """

        simulated_revenue = self.samples * xg_total * market_value_factor

        profit = simulated_revenue - (transfer_cost + salary_cost)

        return profit.mean()

    def make_decision(
        self,
        transfer_cost,
        salary_cost,
        xg_total,
        market_value_factor=10
    ):
        prob = self.compute_probability()

        expected_profit = self.compute_expected_profit(
            transfer_cost,
            salary_cost,
            xg_total,
            market_value_factor
        )

        decision = "RECRUTER" if expected_profit > 0 else "NE PAS RECRUTER"

        return {
            "probability_performance": prob,
            "expected_profit": expected_profit,
            "decision": decision
        }