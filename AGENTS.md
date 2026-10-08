# Orientation Game

## Pitch
Une orientation où on te regarde jouer, pas répondre à un questionnaire.
Le joueur choisit un métier, vit une affaire, prend des décisions, et reçoit
un bilan qui montre ce qu'il a aimé faire et quels métiers lui correspondent.

## Métiers (dans cet ordre)
1. Expert cyber (fini en premier)
2. Avocat
3. Médecin

## Déroulé d'une partie
1. Le joueur choisit un métier.
2. Une affaire lui est donnée (contexte + situation).
3. Il prend 5 à 8 décisions. Chaque choix donne des points à des traits :
   analyser, convaincre, enquêter, aider, protéger.
4. Un bilan cite ses vrais choix et en déduit son profil et des métiers proches.

## Stack
- Backend : Python + Flask
- Frontend : HTML / CSS / JS simple, servi par Flask
- Données : affaires en JSON dans `data/affaires/`
- Tests : pytest. Lint : ruff.

## Règles du projet
- Le jeu doit fonctionner SANS IA. L'IA est un ajout facultatif.
- Les affaires respectent le format JSON défini dans `data/format-affaire.json`.
- Toute entrée utilisateur est validée (longueur, type, valeurs autorisées).
- Les erreurs renvoient un message propre, jamais une page d'erreur brute.
- Aucune clé d'API dans le code : variables d'environnement, fichier `.env` ignoré par git.
- Ne pas modifier les tests pour les faire passer.