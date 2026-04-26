class StrategyConfig:

    def __init__(self):
        self.transfer_cost = 10
        self.salary_cost = 5
        self.market_value_factor = 15

        # seuil décision
        self.min_profit = 0
        self.min_probability = 0.6