class AgentMemory:

    def __init__(self):
        self.history = []
        self.last_results = None
        self.last_recommendation = None
        self.last_strategies = []

    def save_interaction(self, request, response):
        self.history.append({
            "request": request,
            "response": response
        })

    def save_results(self, results):
        self.last_results = results

    def save_recommendation(self, player):
        self.last_recommendation = player

    def save_strategies(self, strategies):
        self.last_strategies = strategies

    def get_last_recommendation(self):
        return self.last_recommendation

    def get_history(self):
        return self.history