Quelle donnée historique nous faut-il ?

Il nous faut idéalement un DataFrame comme :

player
fit_level
market_level
age
injury_risk
salary
transfer_success

Par exemple :

player          fit_level  market_level  age  injury_risk  salary  transfer_success
Player A        HIGH       GOOD          24   low          8       1
Player B        LOW        RISKY         31   high         22      0
Player C        HIGH       GOOD          25   low          7       1
Player D        MEDIUM     RISKY         29   medium       18      0
...

transfer_success doit être une vraie observation historique :

1 = transfert réussi
0 = transfert échoué

Il faudra plus tard définir précisément ce que signifie réussi dans notre plateforme : minutes jouées, performance, disponibilité, valeur créée, contribution sportive, etc.

C'est justement une future étape importante de notre Decision Intelligence.


4. Attention : une correction statistique importante

Je veux être transparent sur un point.

Le modèle ci-dessus est réellement bayésien dans sa structure, mais il utilise une hypothèse Naive Bayes :

P(X1,…,Xn∣S)≈i∏P(Xi∣S)

Cela signifie que nous supposons conditionnellement indépendantes les variables :

fit_level
market_level
age
injury_risk
salary

Ce n'est évidemment pas parfaitement vrai dans le football.

Par exemple :

âge ↔ salaire
âge ↔ valeur marchande
valeur ↔ niveau sportif
fit ↔ profil tactique

Mais c'est une bonne première architecture bayésienne, beaucoup plus rigoureuse que ton ancien :

probability += 0.15
probability += 0.10
probability -= 0.20