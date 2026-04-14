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
        if self.trace is None : 
            print("Erreur: Le modèle doit etre entrainé avant de générer un resumé")
            return None
        # az.summary calcule la moyenne, l'ecart-type et les intervalles de confiance
        stats = az.summary(self.trace, round_to = 2)
        return stats
    
if __name__ == "__main__" :
    import arviz as az
    import matplotlib.pyplot as plt

    # Données de test
    xg = np.array([0.8 , 1.2 , 0.5, 1.5])
    goals = np.array([1, 2, 0, 1])

    analyst = FootballAnalystProbabilistic("Gavi")
    
    analyst.build_model(xg, goals)
    analyst.train()
    
    print(analyst.summary())

    # 3. Sauvegarde du graphique
    az.plot_trace(analyst.trace)
    import matplotlib.pyplot as plt
    plt.savefig("models/resultat_performance.png")



    # initialisation et execution
    model= Footballanalystprobabilistic("Gavi")
    analyst.build_model(xg, goals)
    resultats = analyst.train()
    # On recupère la trace ici
    
    # Affichage du resumé statistique 
    if resultats is not None : 
        print("\n Mise à jour du graphique...")
        az.plot_trace(resultats)
        plt.savefig("models/resultats_performance.png")
        print("Terminé! vérifié le fichier 'resultats_performance.png' et ton terminal. ")
    else:
        print("L'entrainement a échoué, verifie tes fonctions build_model et train. ")
    # 1. Visualisation 
    print("Génération du graphique...")
    az.plot_trace(model.trace)
    plt.savefig("models/resultats_performance.png")

    # 2. Statistiques chiffrées
    print("\n RESUME STATISTIQUE / ")
    print(model.summary())


# 1. On recupère les resultats (la trace)
trace = model.train()

# 2. On crée le graphique (Trace Plot)
az.plot_trace(trace)

# 3. CRUCIAL : On enregistre au lieu d'afficher
plt.savefig("models/resultat_performance.png")
print("Graphique enregistré dans models/resultat_performance.png")

    