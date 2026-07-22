class PlayerPipeline:

    def __init__(self):

        self.steps = []

    def add_step(self, engine):

        self.steps.append(engine)

    def process(self, player):

        for engine in self.steps:

            player = engine.process(player)

        return player