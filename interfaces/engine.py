from abc import ABC, abstractmethod


class BaseEngine(ABC):
    """
    Interface commune à tous les moteurs de la plateforme.

    Tous les engines doivent hériter de cette classe
    et implémenter process().
    """

    @abstractmethod
    def process(self, data):
        """
        Exécute le moteur.

        Parameters
        ----------
        data : dict | list | DataFrame
            Objet à enrichir.

        Returns
        -------
        Même objet enrichi.
        """
        pass

    @property
    def name(self):

        return self.__class__.__name__

    def __repr__(self):

        return f"<{self.name}>"