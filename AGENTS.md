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
3. Il prend 5 à 8 décisions (objectif éditorial ; le moteur valide un minimum
   de 3 étapes par affaire). Chaque choix donne des points à des traits :
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

## Harness opencode (.opencode/)
Le projet se développe avec une équipe d'agents opencode :
- `planificateur` (agent principal) : lit la demande, écrit le plan dans `docs/plan-*.md`, délègue. Ne code pas.
- `tester` : écrit les tests pytest dans `tests/` uniquement (avant le code, ils peuvent échouer).
- `dev` : écrit le code applicatif (`app/`). Ne modifie jamais les tests.
- `reviewer` : lecture seule, relit le diff et vérifie la conformité aux règles ci-dessus.

Règles de collaboration :
- Ordre de délégation d'une étape : tester -> dev -> reviewer.
- Une étape n'est « finie » que si `ruff check .` et `pytest -q` passent.
- Hook bloquant `.opencode/plugin/gate.ts` : avant toute édition/écriture d'un `.py`,
  ruff doit passer, et pytest aussi — sauf si le fichier édité est un test
  (un test peut légitiment échouer avant implémentation). Si `ruff`/`pytest` sont
  introuvables (PATH ou `.venv/`), le contrôle correspondant est ignoré.
- Outils isolés dans le venv : `.venv\Scripts\python.exe -m pip install -e ".[dev]"`.