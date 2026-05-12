from config.strategy_config import STRATEGIES


class StrategyManager:

    def detect_strategies(self, request):

        request = request.lower()

        detected = []

        for strategy in STRATEGIES.keys():

            if strategy in request:
                detected.append(strategy)

        return detected

    def apply_strategies(self, players, strategies):

        if not strategies:
            return players

        filtered = players

        for strategy in strategies:

            filtered = list(
                filter(
                    STRATEGIES[strategy],
                    filtered
                )
            )

        return filtered