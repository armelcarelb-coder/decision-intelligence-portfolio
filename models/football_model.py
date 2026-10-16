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

    def train(self, random_seed=42, chains=4):
        if self.model is None:
            raise ValueError("Model not built yet.")

        with self.model:
            self.trace = pm.sample(
                draws=2000,
                tune=1000,
                chains=chains,
                target_accept=0.9,
                random_seed=random_seed,
            )

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

    def diagnostics(self, rhat_threshold=1.01, min_ess=400):
        if self.trace is None:
            raise ValueError("Model not trained yet.")

        summary = az.summary(self.trace, var_names=["talent"])

        r_hat = float(summary.loc["talent", "r_hat"])
        ess_bulk = float(summary.loc["talent", "ess_bulk"])
        ess_tail = float(summary.loc["talent", "ess_tail"])
        hdi_low = float(summary.loc["talent", "hdi_3%"])
        hdi_high = float(summary.loc["talent", "hdi_97%"])

        checks = {
            "r_hat_pass": r_hat < rhat_threshold,
            "ess_bulk_pass": ess_bulk >= min_ess,
            "ess_tail_pass": ess_tail >= min_ess,
        }

        diagnostics = {
            "r_hat": r_hat,
            "ess_bulk": ess_bulk,
            "ess_tail": ess_tail,
            "hdi_94": (hdi_low, hdi_high),
            "thresholds": {
                "r_hat_max": rhat_threshold,
                "min_ess": min_ess,
            },
            "checks": checks,
            "all_checks_passed": all(checks.values()),
        }

        return diagnostics

    def report(self):
        if self.trace is None:
            raise ValueError("Model not trained yet.")

        diagnostics = self.diagnostics()
        posterior = self.trace.posterior["talent"].values.flatten()
        prob_performant = (posterior > 1).mean()

        return {
            "player": self.player_name,
            "posterior_mean": float(posterior.mean()),
            "probability_talent_above_1": float(prob_performant),
            "credible_interval_94": diagnostics["hdi_94"],
            "diagnostics": diagnostics,
        }


if __name__ == "__main__":
    
    xg = np.array([0.8, 1.2, 0.5, 1.5])
    goals = np.array([1, 2, 0, 1])

    analyst = FootballAnalystProbabilistic("Ivan Rakitić")
    
    analyst.build_model(xg, goals)
    analyst.train()
    analyst.evaluate_player()
    analyst.plot_result()
    
    print(analyst.summary())

    