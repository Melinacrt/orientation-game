# Plan — Corriger le gate TDD (pytest non bloquant) puis finir vert

## Contexte
Preuve précédente (`docs/plan-gate-tdd.md`) : `tests/test_gate_tdd.py` rouge par
assertion (`compter_etapes` manquante) → toute édition `app/*.py` bloquée par le
gate, qui rejoue `pytest -q` **avant** l'édition. Deadlock TDD confirmé par `dev`
(édition bloquée) et `reviewer` (cause : `.opencode/plugin/gate.ts:132`,
`!isTestEdit`). État actuel : `ruff` vert, `pytest` 1 failed, 4 passed.

Feu vert utilisateur : **ruff reste bloquant** avant toute écriture `.py`, mais
**pytest ne doit plus bloquer les éditions** ; pytest reste le critère de fin
d'étape (`ruff check .` + `pytest -q` verts, cf. AGENTS.md).

## Étape 1 — tester confirme l'état rouge (lecture seule si possible)
- Objectif vérifiable : l'état d'entrée est bien « rouge par assertion ».
- `tester` relit `tests/test_gate_tdd.py`, rejoue `pytest -q` (1 failed par
  `AssertionError`, pas d'error) et `ruff check . --no-cache` (vert). Aucune
  modification nécessaire : ne toucher à rien si l'état est conforme.
- Critères d'acceptation : rapport pytest (1 failed par assertion) + ruff vert ;
  aucun fichier hors `tests/` touché ; le test est toujours rouge.

## Étape 2 — dev corrige le harness (gate.ts + AGENTS.md)
- Objectif vérifiable : le gate ne fait plus de `pytest` en pré-édition.
- `dev` via outils `edit`/`write` (les `.ts`/`.md` ne sont pas concernés par le
  gate, donc non bloqués) :
  - `.opencode/plugin/gate.ts` : `runGate` ne lance plus `pytest` ; supprimer le
    bloc pytest, `PYTEST_TIMEOUT_MS`, `hasTests`, le paramètre `isTestEdit` et
    `isTestFile` devenu inutile (ainsi que l'import `readdirSync`) ; garder
    `ruff check . --no-cache` bloquant + sémantique « outil introuvable =
    contrôle ignoré » ; commenter : pytest ne bloque jamais, le rouge TDD reste
    éditable, pytest reste critère de fin d'étape.
  - `AGENTS.md` (puce hook uniquement) : « avant toute édition/écriture d'un
    `.py`, `ruff check . --no-cache` doit passer, sinon l'édition est refusée ;
    `pytest` ne bloque jamais les éditions ». La règle « étape finie seulement
    si ruff + pytest verts » est inchangée.
- Critères d'acceptation : `gate.ts` ne rejoue plus `pytest` ; AGENTS.md
  cohérent ; `tests/` intacts (`dev` ne modifie jamais les tests).

## Étape 3 — rechargement du plugin
- Le plugin est chargé au démarrage d'opencode (cf. `docs/plan-fix-gate.md`) :
  si l'étape 4 rapporte encore un blocage **pytest**, s'arrêter et demander le
  redémarrage d'opencode avant de retenter. Un blocage **ruff** reste normal.

## Étape 4 — dev implémente compter_etapes avec test rouge (preuve live)
- Objectif vérifiable : l'écriture `app/` avec test rouge est désormais autorisée.
- `dev` via outil `edit` (**sans passer par le shell**, sinon la preuve est
  invalide), test encore rouge : implémente `compter_etapes(affaire: dict) ->
  int` dans `app/affaires.py` (nombre d'entrées de `affaire["etapes"]`,
  `ValueError` au message français si entrée invalide), style du module.
- Protocole : noter « édition app/ autorisée » ou « bloquée » (+ message du gate
  le cas échéant) ; si encore bloquée par pytest → stop, signaler (rechargement
  manquant, étape 3). Terminer jusqu'à `pytest -q` vert.
- Critères d'acceptation : édition autorisée avec test rouge ; `pytest -q` et
  `ruff check . --no-cache` verts après implémentation.

## Étape 5 — vérifier que ruff bloque toujours (hors dépôt, planificateur)
- Simulation en temp + invocation directe du hook via Bun : arbre avec violation
  F001/F401 → édition `.py` bloquée avec message ruff ; arbre propre → autorisée.
  Ne salit jamais le vrai dépôt.
- Critères d'acceptation : tableau bloqué/autorisé comme dans
  `docs/plan-fix-gate.md`.

## Étape 6 — reviewer relit (lecture seule)
- Relit `git status / git diff` + fichiers (`gate.ts`, `AGENTS.md`,
  `app/affaires.py`, `tests/test_gate_tdd.py`) ; vérifie conformité AGENTS.md
  (validation, messages français, pas de clé API, tests non modifiés par `dev`,
  aucun contournement shell pour les `.py`).
- Critères d'acceptation : rapport écrit (écarts ou « RAS »).

## Fin d'étape (obligatoire)
- Finie seulement si `ruff check .` et `pytest -q` passent tous les deux.
- Interdictions : planificateur ne code pas ; `dev` ne modifie jamais les tests ;
  aucun commit sans demande explicite ; aucune écriture `.py` via shell.
