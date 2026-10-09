# Plan — Gate : avertissement visible si ruff introuvable + finir compter_etapes

## Contexte
`docs/plan-gate-tdd-fix.md` étape 5 : deux captures contradictoires en apparence.
- `verif-simple.ts` : `A-sale F401 => AUTORISE` (inattendu).
- `verif-msg.ts` : même `A-sale` => `BLOQUE` avec message `F401 'os' imported but unused`.

Cause vérifiée (pas supposée), dans `.opencode/plugin/gate.ts` :
- `resolveCommand("ruff", dir)` cherche dans l'ordre : `Bun.which("ruff")` (PATH),
  puis `<dir>/.venv/Scripts/ruff.exe` (win32), puis `<venv>/python -m ruff`.
- Les arbres temp (`Temp/opencode/gate-tdd-etape5/A-sale`, sans `.venv`) ne
  contiennent pas ruff, et ruff n'est pas sur le PATH global (il n'existe que
  dans `C:\Users\melin\orientation-game\.venv\Scripts`). Donc `resolveCommand`
  renvoie `null`, `runGate` renvoie `[]`, le hook autorise en silence.
- `verif-msg.ts` était lancé avec `PATH` prépendé de `.venv/Scripts` : `Bun.which`
  trouve ruff, `ruff check . --no-cache` voit le `F401`, le hook bloque avec le
  message ruff. D'où `AUTORISE` vs `BLOQUE` pour le même arbre sale.
- Sémantique actuelle (gate.ts:112-120 + AGENTS.md:47-48) : `if (ruff) { ... }`,
  sans `else` — outil introuvable = contrôle ignoré silencieusement.

Feu vert utilisateur : corriger la vérification (cas sale toujours bloqué) et
faire en sorte que le gate affiche un **avertissement visible quand il ne trouve
pas ruff**, au lieu d'ignorer en silence. Puis étape 4 : `dev` implémente
`compter_etapes` avec `edit` dans le vrai dépôt.

État actuel relevé : `app/affaires.py:49-67` contient déjà `compter_etapes`
(`len(affaire["etapes"])`, `ValueError` française). `tests/test_gate_tdd.py`
existe (29 lignes). L'étape 4 est donc à traiter en idempotent : ne pas
dupliquer, vérifier via `edit`, prouver vert.

## Étape 1 — tester confirme l'état d'entrée (tests/ uniquement)
- Objectif vérifiable : le comportement attendu de `compter_etapes` est figé par
  le test avant toute retouche du code.
- `tester` relit `tests/test_gate_tdd.py`, rejoue `pytest -q` et
  `ruff check . --no-cache` en lecture/vérification, ne modifie rien sauf si le
  test est absent ou non conforme au format (`data/format-affaire.json`,
  3 étapes, `ValueError` sur `{}` et `{"etapes": "pas-un-dict"}`).
- Critères d'acceptation : rapport pytest + ruff ; aucun fichier hors `tests/`
  touché ; si modification il y a, uniquement dans `tests/` et avec le même
  comportement exigé (3 + 2 `ValueError`).

## Étape 2 — dev corrige le gate : warning visible si ruff introuvable
- Objectif vérifiable : plus jamais d'autorisation silencieuse quand ruff est
  introuvable ; la vérification temp du cas sale est reproductible et bloquante.
- `dev` via outils `edit`/`write` (les `.ts`/`.md` ne sont pas bloqués par le
  gate) :
  - `.opencode/plugin/gate.ts` : quand `resolveCommand("ruff", dir)` renvoie
    `null`, émettre un avertissement **visible mais non bloquant** (ex.
    `console.warn` en français : ruff introuvable ni sur le PATH ni dans
    `<dir>/.venv`, contrôle ignoré, édition autorisée) ; l'édition reste
    autorisée dans ce cas (règle « outil absent = contrôle ignoré » conservée).
    Garder `ruff check . --no-cache` bloquant quand ruff est trouvable, et
    `pytest` toujours non bloquant. Commenter la cause AUTORISE-vs-BLOQUE.
  - `AGENTS.md` (puce hook uniquement) : remplacer « le contrôle est ignoré »
    par « avertissement visible, édition autorisée (contrôle ignoré) ».
  - Vérification corrigée hors dépôt (temp uniquement, jamais le vrai dépôt) :
    réexécuter l'invocation directe du hook via Bun **avec ruff sur le PATH**
    (prépendre `.venv/Scripts`) sur `A-sale` (F401 → BLOQUE avec message ruff),
    `B-propre` (→ AUTORISE), arbre sans ruff résolvable (→ AUTORISE +
    avertissement visible). Tableau bloqué/autorisé attendu.
- Critères d'acceptation : cas sale bloqué quand ruff résolvable ; cas sans ruff
  = AUTORISE + warning visible (preuve log) ; `tests/` intacts ; aucun `.py`
  écrit via shell.
- Interdiction : aucune écriture `.py` via shell (ni dans le dépôt ni en temp).

## Étape 3 — dev implémente/vérifie compter_etapes avec edit (vrai dépôt)
- Objectif vérifiable : `compter_etapes` verte via le chemin TDD normal (`edit`).
- `dev` via outil `edit` uniquement pour tout `.py` (shell interdit pour écrire
  du `.py`, sinon preuve invalide) :
  - Constater que `app/affaires.py:49-67` contient déjà `compter_etapes` ;
    ne pas dupliquer. Si la fonction manquait (dépôt revenu en arrière),
    l'implémenter : `def compter_etapes(affaire: dict) -> int`, `len` de
    `affaire["etapes"]`, `ValueError` française si non-dict ou `etapes`
    absente/non-dict/vide, style du module (docstring française).
  - Si déjà présente : faire une retouche minimale via `edit` si besoin de
    prouver le chemin (ex. docstring), sinon prouver qu'une édition `edit` est
    autorisée et que `ruff` + `pytest` sont verts. Noter « édition autorisée »
    ou « bloquée » (+ message du gate).
- Critères d'acceptation : `pytest -q` (5 passed dont gate TDD) et
  `ruff check . --no-cache` verts ; `tests/` intacts ; preuve `edit` rapportée.

## Étape 4 — reviewer relit (lecture seule)
- Relit `git status / git diff` + (`gate.ts`, `AGENTS.md`, `app/affaires.py`,
  `tests/test_gate_tdd.py`) ; vérifie conformité AGENTS.md (validation,
  messages français, pas de clé API, tests non modifiés par `dev`, aucun
  contournement shell pour les `.py`, warning ruff non bloquant).
- Critères d'acceptation : rapport écrit (écarts ou « RAS »).

## Fin d'étape (obligatoire)
- Finie seulement si `ruff check .` et `pytest -q` passent tous les deux.
- Interdictions : planificateur ne code pas ; `dev` ne modifie jamais les tests ;
  aucun commit sans demande explicite ; aucune écriture `.py` via shell.
