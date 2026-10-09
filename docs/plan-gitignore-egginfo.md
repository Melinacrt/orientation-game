# Plan — .gitignore : ignorer *.egg-info/

## Contexte
Demande : `echo "*.egg-info/" >> .gitignore`.
État relevé : `.gitignore` contient déjà `*.egg-info/` (ligne 8). L'ajout doit donc être idempotent : ne pas dupliquer la ligne.

## Étape 1 — tester : confirmer aucun test requis
- Objectif vérifiable : aucun comportement applicatif modifié, donc aucun test pytest à ajouter.
- `tester` : ne touche à rien, rapporte « aucun test requis ».
- Critères d'acceptation : aucun fichier modifié par `tester`.

## Étape 2 — dev : ajout idempotent dans .gitignore
- Objectif vérifiable : `.gitignore` contient exactement une ligne `*.egg-info/`, sans doublon, sans toucher au reste.
- `dev` via outils `edit`/`write` (pas via shell, `.gitignore` n'est pas un `.py` donc non bloqué par le gate, mais préférer `edit`/`read`) :
  - Relire `.gitignore`, si `*.egg-info/` déjà présent : ne rien modifier.
  - Sinon : ajouter `*.egg-info/` en fin de fichier avec newline.
  - Ne jamais modifier les tests.
- Critères d'acceptation : `grep *.egg-info` = 1 occurrence ; `git diff -- .gitignore` vide ou ajout unique ; `tests/` intacts.

## Étape 3 — reviewer relit (lecture seule)
- Relit `git status / git diff -- .gitignore` ; vérifie conformité AGENTS.md (pas de clé API, pas de contournement).
- Critères d'acceptation : rapport écrit (écarts ou « RAS »).

## Fin d'étape (obligatoire)
- Finie seulement si `ruff check .` et `pytest -q` passent tous les deux.
- Interdictions : planificateur ne code pas ; `dev` ne modifie jamais les tests ; aucun commit sans demande explicite.
