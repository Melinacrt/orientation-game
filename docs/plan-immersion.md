# Plan — Immersion salle de crise (branche `immersion`)

## Contexte et garde-fous de temps
- `main` sécurisé avant travaux : commit `fe376e8` « Bilan enrichi… (ruff+pytest verts) » (97 passed), puis `git checkout -b immersion`. Tout le travail ci-dessous se fait SUR `immersion` uniquement.
- Retour en arrière si ça se passe mal : `git checkout main` (version saine), puis optionnel `git branch -D immersion`. Ne jamais merger vers `main` sans demande explicite ; aucun commit sur `main` pendant la mission.
- État de départ (sur `immersion`, arbre propre) : `templates/partie.html` (titre, contexte, conséquence, carte étape + formulaire), `templates/base.html` + `static/style.css` (thème clair actuel), `app/web.py::_page_partie` (transmet affaire/etape/numero/total, sans image ni tableau de bord), Flask sert `RACINE/static` alors que 7 PNG existent dans `app/static/img/` (orphelin, cf. reviewer précédent) ; affaire cyber : étapes `{texte, choix}` SANS champ image ; aucun tableau de bord.
- Harness gelé : ne pas modifier `.opencode/`, `AGENTS.md` ; `dev` ne touche jamais à `tests/` ; fin seulement si `ruff check .` et `pytest -q` verts sur `immersion`.

## Étape 1 — Tester d'abord : thème, image optionnelle, tableau de bord (tester seul, rouge autorisé)
- Objectif vérifiable : le contrat immersif est figé par tests avant tout code applicatif.
- `tester` crée `tests/test_immersion.py` (style existant : fixtures app/client, `page_texte`/`assert_sans_traceback`) :
  1. Thème salle de crise : `GET /partie?affaire=cyber-alerte-serveur-rh` → 200 ; CSS (`static/style.css`) contient fond sombre (ex. variable `--fond`/`body{background:#0…}`), police terminal/monospace (`monospace`, `JetBrains Mono`, `Consolas` ou `terminal`), accents vert ET rouge (deux couleurs, ex. `#00…`/`#ff…` ou classes `.vert/.rouge`, `succes/danger`, `consequence`) ; page étape contient un chronomètre visible (`data-testid="chrono"` ou `class="chrono"`, texte type `00:00`/`temps`).
  2. Image optionnelle : schéma EXACT figé par tester : étape peut contenir `image` (str ≤200, chemin relatif sous `img/`, caractères `[a-z0-9-_/\. ]`, extension png/jpg/webp/svg, interdit `..`, `/` absolu, `http`) + `image_alt` (str non vide si image) ; `charger_affaire` accepte une étape SANS image et AVEC image valide ; page étape AVEC image → 200 avec `<img src="...img/..." alt="...">` en grand AU-DESSUS du texte d'étape (index `<img>` < texte) ; page étape SANS image → 200 sans `<img>` ; image au chemin inexistant → 200 quand même, sans `<img>` cassé ni traceback (fallback gracieux).
  3. Tableau de bord : en haut de CHAQUE étape (`GET /partie` initiale + `GET /jouer` après chaque POST 303 suivi) : `data-testid="tableau-de-bord"` (ou `class="tableau-de-bord"`) avec trois indicateurs `machines-infectees`, `confiance-direction`, `temps-restant` (data-testid ou libellés exacts figés par tester) ; valeurs DÉTERMINISTES calculées depuis les choix déjà faits (formule exacte figée par tester, ex. fonction pure `etat -> {machines, confiance, temps}` : machines croît avec gravité cumulée, confiance décroît avec gravité et croît avec convaincre/aider, temps décroît avec nb coups ; bornes documentées) ; le tableau ÉVOLUE entre le début et après 1er choix (deux GET comparés, au moins un indicateur change) ; sans session → redirect accueil inchangé.
  4. Non-régression : tous les tests existants (97 : PRG 303, redirects, 404/405 FR, debug off, bilan enrichi, scores/fins/citations, format, 6–8 étapes, embranchement) restent verts et NE SONT PAS affaiblis ; seules évolutions autorisées à tester : ajout du champ optionnel au format (pas de contrainte durcie sur les anciennes affaires).
- Critères d'acceptation : nouveaux tests rouges pour les bonnes raisons (pas de chrono/tableau/img, CSS clair) ; `ruff check .` vert sur `tests/` ; rapport listant sélecteurs et formule dashboard figés.

## Étape 2 — Données + statiques : images accessibles et étapes illustrées (dev, sans toucher tests)
- Objectif vérifiable : chaque étape peut montrer une image, jamais bloquante.
- `dev` :
  - Résoudre l'orphelin `app/static/img/` : solution au choix (documentée) — ex. servir aussi `app/static` (dossier statique Flask supplémentaire ou `send_from_directory` avec validation) OU copier/référencer vers `static/img/` ; les 7 PNG existants doivent être servis en HTTP 200 avec bon Content-Type ; aucune URL externe, aucun `..`.
  - Ajouter aux 7 étapes cyber un champ optionnel `image` (+ `image_alt`) cohérent éditorialement (ex. e1 → alerte rançon) ; valider que `charger_affaire` + format acceptent l'optionnel (étendre `app/affaires.py` + `data/format-affaire.json` SI besoin, sans casser les anciennes affaires sans image) ; chemin manquant → `web.py` n'émet aucun `<img>` (vérifié côté template, pas d'exception).
- Critères d'acceptation : tests §2 verts ; `test_affaires`/`test_contenu_cyber` (format, 6–8 étapes) toujours verts.

## Étape 3 — Moteur/web : tableau de bord + chrono + image robuste (dev, `app/` uniquement)
- Objectif vérifiable : indicateurs et chrono calculés côté serveur, entrées validées, erreurs propres.
- `dev` (`app/moteur.py` et/ou `app/web.py`, helpers purs testables) :
  - Fonction pure (ex. `tableau_de_bord(affaire, etat) -> {machines_infectees, confiance_direction, temps_restant}`) appliquant EXACTEMENT la formule du tester, bornée, sans IA, sans session cachée ; `_page_partie` la transmet au template + heure de début de partie en session (ex. `session["debut_ts"]` à la création, jamais écrasée par la suite) pour le chrono (temps écoulé affiché, mise à jour JS optionnelle progressive) ; temps restant = budget fictif décrémenté (distinct du chrono).
  - Image : `_page_partie` ne transmet `image_url` que si champ présent + fichier existant + extension autorisée (sinon `None`) ; validation stricte (longueur ≤200, motif, anti `..`/URL) ; toute entrée invalide → pas d'image, jamais 500/traceback.
  - Conserver : PRG 303, redirects accueil, 404/405 FR, debug off, bilan enrichi, validation FR.
- Critères d'acceptation : tests §3 verts ; aucun test existant cassé.

## Étape 4 — Interface : thème salle de crise sur les étapes (dev, `templates/` + `static/` uniquement)
- Objectif vérifiable : moins scolaire, plus crise, sans perdre le jouable.
- `dev` (`templates/partie.html`, `templates/base.html` si besoin, `static/style.css`) :
  - Thème : fond sombre, police terminal/monospace, accents vert (succès/confiance) et rouge (alerte/gravité) ; tableau de bord EN HAUT de l'étape (3 indicateurs + libellés) ; chronomètre visible (`data-testid="chrono"`) ; image en grand au-dessus du texte (`<img class="illustration" src alt>`, `loading` paresseux accepté) ; formulaire/choix et conséquence conservés et lisibles (contraste) ; responsive minimal, sans framework, sans IA.
  - Compat : conserver textes attendus par anciens tests (contexte, texte étape, conséquence, « cyber », bilan) ; pas de traceback.
- Critères d'acceptation : tests §1 verts + 97 existants verts ; `ruff` + `pytest -q` verts ensemble.

## Ordre de délégation (TDD)
1. `tester` → `tests/test_immersion.py` (rouge autorisé).
2. `dev` → données/statiques puis `app/` puis `templates/`+`static/` jusqu'au vert, sans modifier `tests/`.
3. `reviewer` → relit diff `immersion` vs `main` (`git diff main...immersion -- …`), conformité AGENTS.md (validation, erreurs propres FR, sans IA, pas de clé, pas de `..`/URL externe, images locales uniquement).
- Fin seulement si `ruff check .` et `pytest -q` passent ensemble SUR `immersion`.
- Interdictions : planificateur ne code pas ; aucun commit sans demande explicite (les commits `immersion` éventuels seront demandés à l'utilisateur avant exécution) ; aucun merge vers `main` ; écriture `.py` via shell interdite ; ne pas modifier `.opencode/` ni `AGENTS.md`.

## Risques connus
- Conflit statiques `static/` vs `app/static/img/` : à trancher par tester (URL attendue `.../img/<fichier>`) puis dev (servir le bon dossier, fallback si absent).
- Chrono temps réel vs tests déterministes : tester fige un contrat stable (présence + format, pas valeur exacte) ; dev calcule côté serveur depuis `session["debut_ts"]`, JS seulement en rehaussement.
- Dashboard : formules inventées = risque d'arbitraire ; tester DOIT documenter la formule exacte dans le test pour la rendre vérifiable.
