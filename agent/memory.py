class AgentMemory:

    def __init__(self):

        self.history = []

        self.last_results = None
        self.last_filtered = None

        self.last_recommendation = None

        self.last_request = None

        self.last_strategies = []

        self.context = {}

    def save_interaction(self, request, response):

        self.history.append({
            "request": request,
            "response": response
        })

        self.last_request = request

    def save_results(self, results):
        self.last_results = results

    def save_filtered(self, filtered):
        self.last_filtered = filtered

    def save_recommendation(self, player):
        self.last_recommendation = player

    def save_strategies(self, strategies):
        self.last_strategies = strategies

    def update_context(self, key, value):
        self.context[key] = value

    def get_context(self):
        return self.context

    def get_last_recommendation(self):
        return self.last_recommendation

    def get_history(self):
        return self.history