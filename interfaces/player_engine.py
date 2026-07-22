from abc import abstractmethod

from interfaces.engine import BaseEngine


class PlayerEngine(BaseEngine):

    @abstractmethod
    def process(self, player):

        pass