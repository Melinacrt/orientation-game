# Plan — Vérifier que le gate n'empêche pas le cycle TDD (test rouge → fix dev)

## Contexte
`.opencode/plugin/gate.ts` lance `ruff check . --no-cache` avant toute
écriture `.py`, et `pytest -q` avant toute écriture `.py` qui n'est pas dans
`tests/` (exemption test prévue par AGENTS.md).

Risque soulevé par l'utilisateur : quand un test est rouge « pour de bon »
(échec par assertion, avant que le dev ait écrit le code), le dev qui veut
écrire dans `app/` pour le faire passer se fait bloquer par le gate, car le
gate rejoue `pytest` sur l'état rouge *avant* l'édition. C'est un deadlock TDD
classique : le rouge empêche le vert.

Ce plan organise la preuve dans le vrai dépôt, sans contournement par shell.

## Étape 1 — tester écrit un test rouge par assertion (phase rouge)
- Objectif vérifiable : un nouveau fichier `tests/test_gate_tdd.py` existe,
  ruff-clean, qui échoue par `AssertionError` (pas par `ImportError` ni erreur
  de collection).
- Contenu imposé pour garantir « échec par assertion » :
  - le test cible une petite fonction utile et inexistante à ce jour dans
    `app/affaires.py`, par exemple `compter_etapes(affaire: dict) -> int`
    (nombre d'entrées de `affaire["etapes"]`, avec validation d'entrée en
    `ValueError` message français).
  - pour ne pas échouer en `ImportError` (erreur de collection), le test
    importe avec `try/except ImportError` et fait `assert False, ...` si la
    fonction manque. Ainsi `pytest -q` est rouge par assertion.
  - le test vérifie ensuite le comportement attendu sur
    `data/format-affaire.json` (3 étapes) + un cas d'entrée invalide qui doit
    lever `ValueError`.
- Critères d'acceptation :
  - `tests/test_gate_tdd.py` seul en échec par assertion (`pytest -q`
    montre 1 failed, pas d'error).
  - l'écriture du test par l'outil `write`/`edit` n'est PAS bloquée par le
    gate (exemption `tests/`).
  - `ruff check . --no-cache` reste vert après l'ajout du test (sinon le
    prochain `app/` serait bloqué pour une mauvaise raison).

## Étape 2 — dev fait passer le test en écrivant dans app/ (phase verte)
- Objectif vérifiable : `dev` implémente la fonction dans `app/affaires.py`
  (uniquement `app/`, jamais `tests/`) jusqu'à ce que `pytest -q` passe.
- Protocole d'observation du gate (point central de la demande) :
  1. `dev` tente une première écriture dans `app/affaires.py` alors que le
     test de l'étape 1 est encore rouge.
  2. `dev` note explicitement dans sa réponse : « édition app/ autorisée » ou
     « édition app/ bloquée par le gate, message pytest : ... ».
  3. Aucun contournement par PowerShell/shell pour écrire le `.py` : on utilise
     les outils `edit`/`write` afin que le hook soit réellement exercé.
- Critères d'acceptation :
  - le cas demandé est testé pour de vrai : test rouge par assertion + tentative
    d'écriture `app/` par `dev`.
  - si « autorisée » : `dev` termine l'implémentation, `pytest -q` passe.
  - si « bloquée » : `dev` le signale sans bidouiller, le planificateur tranche
    (voir Étape 4) — on ne laisse pas le dépôt rouge.

## Étape 3 — reviewer relit (lecture seule)
- Objectif vérifiable : relecture du diff `git status / git diff` + fichiers.
- Vérifie : conformité AGENTS.md (validation entrées, messages français propres,
  pas de clé API, pas de modification de tests par `dev`, JSON respecté),
  pertinence de la fonction ajoutée, et cohérence du rapport de blocage/non
  blocage du gate.
- Critères d'acceptation : rapport écrit listant écarts ou « RAS ».

## Étape 4 — décision gate (planificateur, hors sous-agents)
- Si l'étape 2 rapporte « bloquée » : c'est la preuve du deadlock TDD. Le gate
  ne doit pas bloquer une édition `app/` sur un `pytest` rouge (le rouge est
  l'état normal du TDD). Correctif envisagé en suivi : ne garder bloquant que
  `ruff`, et laisser `pytest -q` comme critère de fin d'étape, pas comme
  pré-condition d'édition. Ne pas modifier le gate dans ce plan sans demande
  explicite ; rouvrir un `docs/plan-*.md` dédié.
- Si « autorisée » : le gate actuel convient au TDD ; clore avec les logs.

## Fin d'étape (obligatoire)
- Une étape n'est « finie » que si `ruff check .` et `pytest -q` passent tous
  les deux (AGENTS.md). Le dépôt doit donc finir vert : soit le test est
  passé, soit le fichier de reproduction est retiré dans un suivi explicite.
- Interdictions rappelées : planificateur ne code pas, `dev` ne modifie jamais
  les tests, aucun commit sans demande explicite de l'utilisateur.
