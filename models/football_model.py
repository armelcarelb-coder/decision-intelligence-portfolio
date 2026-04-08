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
            self.trace = pm.sample(1000, tune=1000)
        
        return self.trace

    def summary(self):
        if self.trace is None:
            raise ValueError("Model not trained yet.")
        
        return az.summary(self.trace)

    def plot_trace(self, filename="trace.png"):
        az.plot_posterior(analyst.trace) 
        import matplotlib.pyplot as plt
        plt.savefig(filename)

if __name__ == "__main__":
    
    xg = np.array([0.8, 1.2, 0.5, 1.5])
    goals = np.array([1, 2, 0, 1])

    analyst = FootballAnalystProbabilistic("Gavi")
    
    analyst.build_model(xg, goals)
    analyst.train()
    
    print(analyst.summary())
    
    analyst.plot_trace("models/resultat.png")

  
