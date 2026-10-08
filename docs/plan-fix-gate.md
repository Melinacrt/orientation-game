# Plan — Corriger le gate qualité `.opencode/plugin/gate.ts`

## Symptôme
Les agents `tester` et `dev` ont dû écrire leurs fichiers `.py` via PowerShell :
l'outil `write`/`edit` était bloqué par le hook, qui plantait avec
`` $`${ruff} check .`.quiet().nothrow().timeout is not a function ``.

## Cause réelle (vérifiée, pas supposée)
Ce n'est PAS le chemin Windows. En reproduisant le hook avec Bun 1.4.2 :

```
keys: constructor,cwd,env,quiet,nothrow,throws,text,json,lines,arrayBuffer,bytes,blob,run,then
has quiet: function nothrow: function timeout: undefined
```

`.timeout()` n'existe pas sur le `ShellPromise` de Bun. Le plantage touchait donc
**toute** écriture de `.py`, quel que soit le chemin (PATH ou `.venv`).

Cause secondaire (latente) : même sans `.timeout()`, passer le chemin d'un
exécutable par un shell reste fragile (antislashs Windows, espaces, `$`).

## Correctif
Supprimer complètement le shell dans le hook et exécuter les outils avec un
tableau d'arguments + un répertoire de travail explicite, via `Bun.spawnSync` :

- `resolveCommand(name, dir)` : `Bun.which` → `.venv/Scripts/<nom>.exe` (win32)
  ou `.venv/bin/<nom>` (unix) → `<venv>/python -m <nom>` en dernier recours.
- `run(argv, args, dir, timeout)` : `Bun.spawnSync` sans shell, `cwd: dir`,
  `timeout`, `maxBuffer`. Aucune interpolation, donc aucun problème de chemin.
- Si une commande ne peut pas être lancée du tout : contrôle ignoré (comme un
  outil absent), conformément à AGENTS.md — pas de blocage sur un bug du gate.
- `exitCode === null` (tué par le timeout) est traité comme un échec explicite.
- Le répertoire de travail est le répertoire du projet (`directory` fourni par
  opencode), plus le cwd de l'agent : les chemins relatifs `tests/` restent
  valables quelle que soit la façon dont opencode a été lancé.
- Sémantique inchangée par ailleurs : `ruff check .` toujours ; `pytest -q`
  seulement si le fichier édité n'est pas un test et que `tests/` en contient.

## Étapes
1. `dev` réécrit `.opencode/plugin/gate.ts` avec le contenu exact fourni.
2. Vérification (planificateur, avec Bun en local) :
   - hook sur une édition `app/*.py` dans le dépôt propre → aucune erreur ;
   - hook sur une édition `tests/*.py` → aucune erreur (exemption pytest) ;
   - copie temporaire du projet avec une erreur de lint → hook bloquant ;
   - copie temporaire avec un test en échec → hook bloquant sur `app/*.py`,
     non bloquant sur `tests/*.py`.

## Critères d'acceptation
- Le hook ne plante plus (plus de `.timeout is not a function`).
- Les écritures `.py` via les outils `edit`/`write` fonctionnent sans
  contournement par le shell.
- Le gate bloque toujours en cas d'échec réel de `ruff` ou `pytest`.
- `docs/plan-*.md` et le code applicatif ne sont pas modifiés par ce plan.

## Problèmes découverts et corrigés au passage
| # | Constat | Correctif |
| - | ------- | -------- |
| 1 | Le paquet `orientation-game` n'était pas installé dans le venv : `pytest.exe` (script console) ne peut pas importer `app`, alors que `python -m pytest` y arrive (le cwd est dans `sys.path`). Le gate bloquait donc toute édition dans `app/`. | `pip install -e ".[dev]"` (commande documentée dans AGENTS.md). |
| 2 | Cette installation échouait : « Multiple top-level packages discovered in a flat-layout: ['app', 'data', 'capture'] ». | Ajout de `[tool.setuptools] packages = ["app"]` dans `pyproject.toml`. |
| 3 | `ruff check .` annonçait « All checks passed! » alors qu'une violation I001 existait dans `tests/test_affaires.py` : faux négli du cache `.ruff_cache`, confirmé par `--no-cache`. | Le gate lance `ruff check . --no-cache` ; le tri d'imports du test a été corrigé par `tester` (une ligne vide, aucun changement de comportement). |

## Vérifications exécutées (hook réel, exécuté sous Bun 1.4.2)
Scénarios joués en appelant `tool.execute.before` du plugin corrigé :

| Scénario | Attendu | Résultat |
| -------- | ------- | -------- |
| Dépôt propre, édition `app/affaires.py` | autorisé | OK |
| Dépôt propre, édition `tests/test_affaires.py` | autorisé | OK |
| Dépôt propre, chemin Windows absolu | autorisé | OK |
| Fichier non `.py` | autorisé | OK |
| Violation ruff (F401) | bloqué, message ruff | OK |
| Test en échec, édition `app/*.py` | bloqué, message pytest | OK |
| Test en échec, édition du test fautif | autorisé (exemption AGENTS.md) | OK |

`pytest -q` : 4 passed. `ruff check .` et `ruff check . --no-cache` : toutes deux OK.

## Effet de bord attendu
Le plugin est chargé au démarrage d'opencode : **il faut quitter et relancer
opencode** pour que le nouveau `gate.ts` soit pris en compte.

Artefacts créés hors dépôt : `.venv` (install éditable, paquet
`orientation-game`, `orientation_game.egg-info/` généré à la racine — non
modifié, rien n'a été committé) et `C:\Users\melin\AppData\Local\Temp\opencode`
(outils de vérification Bun).
