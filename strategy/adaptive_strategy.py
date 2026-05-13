class AdaptiveStrategy:

    def adapt(self, strategies):

        relaxed = strategies.copy()

        if "rentable" in relaxed:
            relaxed.remove("rentable")

        return relaxed