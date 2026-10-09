# Plan — Étapes 2 à 4 : moteur, affaire cyber, web + CI + README

## Contexte
Étape 1 finie : `app/affaires.py` (`charger_affaire`, `compter_etapes`, validation du format `data/format-affaire.json`), tests `test_affaires.py` + `test_gate_tdd.py` verts, `ruff` vert. Harness gelé : **ne pas modifier `.opencode/` ni `AGENTS.md`** dans ces étapes.

## Étape 2 — Moteur de partie (scores, gravité, fin, bilan cité)
- Objectif vérifiable : une partie se joue sans IA ni Flask, à partir d'une affaire validée : cumul des points par trait, cumul de gravité, choix de la fin, bilan qui cite les vrais choix du joueur.
- `tester` écrit `tests/test_moteur.py` (peut échouer) :
  - `app/moteur.py` expose au minimum : `nouvelle_partie(affaire) -> état` (scores à 0 pour les 5 traits, gravité 0, historique vide, étape courante = `debut`) ; `jouer_coup(affaire, état, etape_id, choix_id) -> état` (valide : types, longueurs, `etape_id` existe, `choix_id` existe dans l'étape ; ajoute traits + gravité du choix, pousse `{etape, choix, label, conséquence}` dans l'historique, avance `suite` ou termine) ; `calculer_bilan(affaire, état, profils) -> dict` (`scores`, `gravite`, `fin` = première fin où `gravite <= gravite_max`, `citations` = labels + conséquences réellement choisis, `profil` + `metiers_proches` issus de `profils`).
  - Cas : 3 coups de `format-affaire.json` (isoler c1 + point c3 + restaurer c5 → scores `analyser 3, proteger 3, convaincre 2`, gravité 0, fin « Crise maîtrisée ») ; choix invalide (étape inconnue, choix inconnu, types faux) → `ValueError` française ; fin choisie selon seuils (gravité 0/2/6 → les 3 fins).
- `dev` implémente `app/moteur.py` (+ `data/profils.json` minimal si besoin du bilan : 5 traits → profils + métiers proches expert cyber / avocat / médecin) jusqu'au vert, sans toucher aux tests ni au harness.
- `reviewer` relit diff + fichiers, conformité AGENTS.md.
- Critères d'acceptation : `pytest -q tests/test_moteur.py` vert après implémentation ; `ruff check .` vert ; erreurs en français propres ; sans IA ; aucune modification du harness.

## Étape 3 — Affaire cyber complète 6 à 8 étapes + profils
- Objectif vérifiable : la première affaire jouable « Expert cyber », 6 à 8 étapes avec au moins un embranchement (deux chemins qui divergent puis divergent vraiment : `suite` différentes selon le choix à une étape), conforme au format.
- `tester` écrit `tests/test_contenu_cyber.py` (peut échouer) :
  - `data/affaires/cyber-alerte-serveur-rh.json` : `charger_affaire` OK, `compter_etapes` entre 6 et 8 inclus, `metier == "cyber"`, au moins une étape dont deux choix mènent à deux `suite` différentes non nulles, toutes les `suite` non nulles référencent une étape existante, au moins un chemin complet atteint une fin en ≥ 3 coups via le moteur, traits tous autorisés.
  - `data/profils.json` : chargeable, chaque entrée a `traits_dominants` (parmi les 5), `titre`, `texte`, `metiers_proches` (sous-ensemble de expert cyber / avocat / médecin) ; `calculer_bilan` sur une partie type renvoie un profil existant et cite les vrais labels.
- `dev` écrit `data/affaires/cyber-alerte-serveur-rh.json` (6 à 8 étapes, embranchement, conséquences et fins en français soigné) et `data/profils.json` (≥ 3 profils couvrant les 5 traits + métiers proches) jusqu'au vert, sans toucher aux tests ni au harness.
- `reviewer` relit (dont relecture éditoriale : français, pas de clé API, sans IA).
- Critères d'acceptation : `pytest -q` vert ; `ruff check .` vert ; affaire conforme au format ; 6–8 étapes ; embranchement réel.

## Étape 4 — Routes Flask + pages + validation + erreurs propres + CI + README
- Objectif vérifiable : on joue à l'affaire cyber dans le navigateur, avec style soigné, entrées validées, erreurs propres, CI et README.
- `tester` écrit `tests/test_web.py` (peut échouer, client Flask) :
  - `GET /` (accueil, choix Expert cyber) → 200, contient « cyber ».
  - `GET /partie?affaire=cyber-alerte-serveur-rh` → 200, affiche le contexte + premier texte d'étape ; `affaire` inconnue / trop longue / caractères interdits → 400 ou 404 avec page propre (pas de traceback).
  - `POST /jouer` (formulaire `affaire, etape, choix`, historique en session ou champ caché) : choix valide → 200 étape suivante ou bilan ; `etape`/`choix` inconnus, types faux, champs manquants/trop longs → 400 page propre, scores inchangés.
  - Parcours complet simulé (6+ coups valides) → `GET /bilan` 200, contient la fin, les scores, et au moins 2 labels réellement choisis (citations).
  - `GET /page-inexistante` → 404 page propre ; erreur interne simulée → 500 page propre.
- `dev` implémente jusqu'au vert, sans toucher aux tests ni au harness :
  - `app/web.py` (factory `creer_app()` + `app.py` ou équivalent qui sert Flask) : routes `/`, `/partie`, `/jouer`, `/bilan`, gestionnaires 404/400/500 avec templates propres, validation de TOUTES les entrées (longueur ≤ 200, type str, valeurs parmi affaire/étapes/choix autorisés), session Flask avec `secret_key` via variable d'environnement (défaut dev uniquement, jamais de clé en dur), sans IA.
  - `templates/` (base + accueil + partie + bilan + erreur) et `static/style.css` soigné (lisible, responsive minimal, sans framework).
  - `.github/workflows/ci.yml` : `ruff check .` + `pytest -q` sur push/PR (Python 3.12, `pip install -e ".[dev]"`).
  - `README.md` court : pitch, install venv, lancer (`flask`/`python`), jouer, `ruff` + `pytest`, sans IA.
- `reviewer` relit diff + pages + CI + README, conformité AGENTS.md.
- Critères d'acceptation : `pytest -q` vert ; `ruff check .` vert ; parcours navigateur complet possible ; entrées invalides → pages propres ; aucune clé en dur ; harness intact.

## Fin d'étape (obligatoire, chaque étape 2/3/4)
- Finie seulement si `ruff check .` et `pytest -q` passent tous les deux.
- Interdictions : planificateur ne code pas ; `dev` ne modifie jamais les tests ; aucun commit sans demande explicite ; aucune écriture `.py` via shell ; ne pas modifier `.opencode/` ni `AGENTS.md`.
