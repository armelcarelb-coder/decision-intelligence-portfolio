class LLMReasoner:

    def explain_recommendation(self, player):

        explanation = f"""
🧠 ANALYSE LLM

Le joueur recommandé est {player['player']}.

Pourquoi ?

- Profit attendu : {player['profit']:.2f}
- Probabilité de performance : {player['probability']:.2%}
- Style : {player['style']}
- Efficacité : {player['efficiency']}

Le système considère que ce joueur présente
le meilleur compromis entre :
- risque
- rentabilité
- potentiel offensif
- efficacité globale
"""

        return explanation

    def explain_comparison(self, player_a, player_b):

        return f"""
🧠 COMPARAISON LLM

{player_a['player']} :
- Profit : {player_a['profit']:.2f}
- Probabilité : {player_a['probability']:.2%}

VS

{player_b['player']} :
- Profit : {player_b['profit']:.2f}
- Probabilité : {player_b['probability']:.2%}

Le système détecte des profils différents :
- un profil plus sécurisé
- un profil plus offensif
- un profil plus rentable
"""