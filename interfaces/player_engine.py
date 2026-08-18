from abc import ABC, abstractmethod


class PlayerEngine(ABC):

    @abstractmethod
    def process(self, player):
        pass