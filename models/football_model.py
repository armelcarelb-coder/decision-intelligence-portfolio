import os
os.environ['PYTENSOR_FLAGS'] = 'device=cpu, floatX=float64, cxx='

import pymc as pm
import numpy as np
import arviz as az

class FootballAnalystProbabilistic:
    
    def __init__(self, player_name, prior_mu=1.0):
        self.player_name = player_name
        self.prior_mu = prior_mu
        self.model = None
        self.trace = None

    def build_model(self, xg_data, goals_data):
        with pm.Model() as self.model:
            
            # PRIOR
            self.talent = pm.LogNormal(
                "talent", 
                mu=np.log(self.prior_mu), 
                sigma=0.5
            )
            
            # LIKELIHOOD
            lambda_ = self.talent * xg_data
            pm.Poisson("goals", mu=lambda_, observed=goals_data)

    def train(self):
        if self.model is None:
            raise ValueError("Model not built yet.")
        
        with self.model:
            self.trace = pm.sample(2000, tune=1000, target_accept=0.9)
        
        return self.trace

    def summary(self):
        if self.trace is None:
            raise ValueError("Model not trained yet.")
        
        return az.summary(self.trace)
    
    def evaluate_player(self):
        if self.trace is None :
            print("Erreur : Entrainez le modèle d'abord !")
            return None
        samples = self.trace.posterior["talent"].values
        prob = (samples > 1).mean()
        print(f"Probabilité que {self.player_name} soit performant : {prob: .2%}")
        return prob

    def plot_trace(self, filename="trace.png"):
        import matplotlib.pyplot as plt
        az.plot_trace(self.trace)
        plt.savefig(filename)
    
    def plot_result(self, filename="models/resultat.png"):
        import matplotlib.pyplot as plt
        import arviz as az

        az.plot_trace(self.trace)
        plt.savefig(filename)
        print(f"Graphique sauvegardé sous : {filename}")

    def decision_recruitment(self):
        samples = self.trace.posterior["talent"].values
    
        prob_good = (samples > 1).mean()
    
        # Hypothèses métier
        gain_good = 10
        loss_bad = -5
    
        expected_value = prob_good * gain_good + (1 - prob_good) * loss_bad
    
        print(f"Probabilité joueur performant : {prob_good:.2%}")
        print(f"Valeur attendue du recrutement : {expected_value:.2f}")
    
        if expected_value > 0:
          print("Décision : RECRUTER")
        else:
          print("Décision : NE PAS RECRUTER")

if __name__ == "__main__":
    
    xg = np.array([0.8, 1.2, 0.5, 1.5])
    goals = np.array([1, 2, 0, 1])

    analyst = FootballAnalystProbabilistic("Gavi")
    
    analyst.build_model(xg, goals)
    analyst.train()
    analyst.evaluate_player()
    analyst.plot_result()
    analyst.decision_recruitment()
    
    print(analyst.summary())

    