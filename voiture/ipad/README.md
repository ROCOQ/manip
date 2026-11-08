# Version iPad (sans serveur, avec l'abonnement Claude)

- **App** : https://claude.ai/artifact/FrfmpfpUTk5vRkNTaU68DS (page hébergée sur claude.ai, privée).
  Source : `chasseur-voiture.html`. Données (profil, annonces, concessions, mémoire, rapports) dans la
  base de l'artifact ; le chat avec le chef utilise l'abonnement Claude de la personne qui l'ouvre.
- **Recherche non-stop** : tâche planifiée Claude Code « Chasseur de voiture : mission quotidienne »
  (chaque jour à 8 h 13, heure de Paris), qui ouvre une session cloud, fait les recherches web et écrit
  les résultats dans la base de l'app. Ses instructions : `mission-quotidienne.md`.
- Le bouton « Chercher maintenant » de l'app relance la tâche via le connecteur Claude Code Remote.
