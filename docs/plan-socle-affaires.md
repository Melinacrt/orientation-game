# Plan — Socle affaires (étape 1)

## Contexte
Le dépôt ne contient encore aucun code applicatif (`app/`), aucun test (`tests/`)
et aucune donnée d'affaire (`data/affaires/` est vide). Seul existe
`data/format-affaire.json`, qui sert de référence au format des affaires.

## Objectif de l'étape
Poser un socle minimal et vérifiable : une fonction Python capable de charger
une affaire depuis un fichier JSON et de vérifier que ce JSON respecte le format.

Périmètre volontairement réduit (demande utilisateur : un test simple qui échoue).

## Étapes
1. `tester` écrit `tests/test_affaires.py` : quelques tests simples décrivant
   le comportement attendu de `app.affaires.charger_affaire`.
   - charger un JSON valide renvoie un dictionnaire avec les clés attendues
     (`id`, `metier`, `titre`, `etapes`) ;
   - un fichier JSON malformé ou incomplet lève une erreur propre (jamais de
     traceback brut), conformément aux règles AGENTS.md ;
   - les traits manipulés sont bien parmi : analyser, convaincre, enquêter,
     aider, protéger.
   Les tests échouent à ce stade (module `app` inexistant) : c'est la phase rouge.
2. `dev` implémente `app/affaires.py` jusqu'au passage des tests.
3. `reviewer` relit le diff et vérifie la conformité aux règles AGENTS.md.

## Critères d'acceptation
- `pytest -q` : les tests écrits par `tester` passent (après implémentation).
- `ruff check .` passe.
- Aucune entrée utilisateur non validée, aucune clé d'API dans le code.

## Hors périmètre de cette étape
- Routes Flask, moteur de traits, bilan, template.
- Ces éléments feront l'objet d'étapes ultérieures.
