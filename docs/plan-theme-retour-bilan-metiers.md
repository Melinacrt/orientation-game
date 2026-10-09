# Plan — Thèmes par affaire, retour arrière 303, bilan fiche métier, footer sans « Sans IA »

## Contexte
- État actuel : `static/style.css` = thème unique sombre « salle de crise » ; `templates/base.html` sans classe de thème ; footer contient « Sans IA. » ; `POST /jouer` avec `etape != etape_courante` renvoie 400 « Cette étape ne correspond pas… Retour à l'accueil » (`app/web.py:95-99`) ; `templates/bilan.html` affiche « Métiers proches de ton profil » via `metiers_details` issus de `data/profils.json` avec badges Jouable/Bientôt ; pas de `data/metiers.json` ; `data/affaires/cyber-alerte-serveur-rh.json` a `metier: cyber` mais pas de champ `theme`.
- Demande (5 points, harness gelé, ordre tester → dev → reviewer) :
  1. Chaque affaire a `theme` (« cyber », « avocat »). Partie + bilan appliquent `theme-<nom>` ; accueil + erreurs = thème neutre clair et sobre. Style actuel devient `theme-cyber`.
  2. `POST /jouer` désynchronisé (retour arrière) ne renvoie plus 400 : 303 vers l'étape en cours + message « Tu étais revenu en arrière : voici l'étape en cours. »
  3. Bilan : supprimer « métiers proches » calculés depuis les traits ; garder profil (ce que le joueur a aimé faire), barres de scores, choix cités ; ajouter « fiche métier » du métier joué lue dans `data/metiers.json` (quotidien en 3 points, qualités utiles, formations possibles) + bloc « Essaie un autre métier » avec badges Jouable et Bientôt.
  4. Retirer « Sans IA » du pied de page.
  5. Ajouter des tests pour chaque point, garder les tests existants (sauf évolutions volontaires listées par tester).
- Règles : ne pas modifier `.opencode/`, `AGENTS.md` ; `dev` ne touche jamais `tests/` ; fin seulement si `ruff check .` et `pytest -q` verts ; validation des entrées + pages d'erreur propres FR conservées ; aucun commit sans demande explicite.

## Étape 1 — Tester : figer les contrats (tester seul, rouge autorisé)
- Objectif vérifiable : chaque point de la demande est couvert par un test qui échoue pour la bonne raison avant code.
- `tester` écrit (nouveau fichier `tests/test_themes_retour_bilan.py` suggéré, style existant fixtures `app`/`client` + helpers `page_texte`/`assert_sans_traceback`) :
  1. Thèmes : `data/affaires/cyber-alerte-serveur-rh.json` a `theme == "cyber"` (et `data/format-affaire.json` documente `theme` si tester le juge utile) ; `GET /partie?affaire=cyber-…` et `GET /bilan` (après parcours) contiennent `theme-cyber` (ex. `<body class="…theme-cyber…">` ou conteneur équivalent) ; `GET /` et page 404 ne contiennent aucun `theme-cyber`/`theme-avocat` et appliquent un thème neutre (ex. classe `theme-neutre` ou équivalent figé par tester, clair et sobre) ; `static/style.css` définit `.theme-cyber` (reprend le style actuel) + `.theme-neutre` clair + `.theme-avocat` minimal (même si aucune affaire avocat en prod).
  2. Retour arrière : démarrer partie, jouer 1er coup valide (PRG 303), puis `POST /jouer` avec l'ancienne `etape == debut` (valide mais plus courante) → assert 303 (pas 400), `Location` vers `/jouer` ou `/partie` (pas `/bilan`), suivi GET 200 affiche le texte de l'étape courante réelle + le message exact « Tu étais revenu en arrière : voici l'étape en cours. » ; la partie reste intacte (le coup rejoué depuis l'étape courante passe en 303 et le bilan reste consultable). Garder les 400 existants pour étape inconnue / choix inconnu / champs manquants (non-régression `test_web`, `test_prg_redirect`).
  3. Bilan sans métiers proches + fiche métier : après parcours complet, `GET /bilan` 200 ne contient plus la section « Métiers proches de ton profil » (ni `class="metiers-proches"`) ; contient toujours profil (`data-testid="profil"` + titre + texte), les 5 barres (`data-trait` + libellés accentués + mot « score »), les citations (≥2 vrais labels) ; contient une « fiche métier » du métier joué lue depuis `data/metiers.json` : titre du métier joué, quotidien en 3 points, qualités utiles, formations possibles (tester fige le schéma exact de `data/metiers.json`, ex. dict par code métier avec `titre`, `quotidien` = liste de 3 chaînes non vides, `qualites` = liste non vide, `formations` = liste non vide) ; contient un bloc « Essaie un autre métier » (titre ou `data-testid` figé par tester) listant chaque métier de `data/metiers.json` avec badge « Jouable » pour le(s) jouable(s) et « Bientôt » pour les autres.
  4. Footer : `GET /` (et si simple une page partie/bilan) ne contient plus « Sans IA » (ni `sans ia` insensible casse/accents) ; le texte restant garde « on te regarde jouer ».
  5. Non-régression : tous les autres tests existants restent verts sauf évolutions volontaires listées ci-dessous.
- Ruptures volontaires à faire porter par `tester` seul (lister chacune dans son rapport, `dev` ne doit jamais modifier `tests/`) :
  - `tests/test_bilan_enrichi.py` §§ 1/3 (`test_bilan_profil_contient_titre_texte_et_metiers_proches`, `test_bilan_badges_jouable_pour_expert_cyber_et_bientot_pour_les_autres`) et `tests/test_contenu_cyber.py::test_profils_metiers_proches_parmi_les_trois_metiers` si incompatibles avec la suppression des métiers proches traits → à réécrire vers fiche métier + « Essaie un autre métier ».
  - `tests/test_web.py::test_jouer_etape_inconnue_400…` / `tests/test_prg_redirect.py::test_post_jouer_etape_inconnue…` si tester distingue « étape inconnue de l'affaire » (reste 400) vs « étape connue mais plus courante = retour arrière » (devient 303) → préciser l'intitulé et le cas testé.
  - `tests/test_immersion.py` CSS sombre global si le neutre clair l'assouplit → restreindre l'assertion sombre à `.theme-cyber`.
- Critères d'acceptation : nouveaux tests rouges pour les bonnes raisons (pas de `theme-*`, 400 au lieu de 303, métiers proches encore présents, « Sans IA » encore là) ; `ruff check .` vert sur `tests/`.

## Étape 2 — Dev données : `theme` + `data/metiers.json` (dev, sans toucher `tests/`)
- Objectif vérifiable : contenus et schémas conformes au contrat figé par tester.
- `dev` (données uniquement) :
  - `data/affaires/cyber-alerte-serveur-rh.json` : ajouter `theme: "cyber"` (cohérent avec `metier: cyber`) ; ne rien casser (6–8 étapes, embranchement, suites, traits 1–2 clés 1–3 pts, fins).
  - `data/format-affaire.json` : documenter `theme` (exemple) si le schéma tester l'exige, sans casser `test_affaires`.
  - Créer `data/metiers.json` selon schéma tester : au minimum entrée `cyber` (Expert cyber : quotidien 3 points, qualités utiles, formations possibles) + entrées `avocat` (non jouable) et `medecin` (non jouable) pour nourrir « Essaie un autre métier » (badges Jouable/Bientôt) ; français soigné, sans clé, sans IA. Exemple de métiers : Expert cyber (jouable), Avocat, Médecin (bientôt).
  - `app/affaires.py` : valider `theme` si tester l'exige (chaîne non vide, motif `^[a-z0-9-]+$`, valeurs autorisées restreintes si contrat, erreur FR sinon), en gardant étapes sans image valides.
- Critères d'acceptation : tests thèmes-données + `test_affaires`/`test_contenu_cyber` (après évolution tester) verts.

## Étape 3 — Dev web : retour arrière 303 + thèmes + footer (dev, `app/` + `templates/` + `static/` sauf bilan détaillé étape 4)
- Objectif vérifiable : navigation et habillage conformes sans régression PRG/erreurs.
- `dev` :
  - `app/web.py` : dans `POST /jouer`, si `etape_id` est une étape connue de l'affaire mais `!= etape_courante` (retour arrière / avant), ne plus lever 400 : stocker le message « Tu étais revenu en arrière : voici l'étape en cours. » (ex. `session["message_retour"]` consommé une fois, ou flash) sans modifier `session["etat"]`, puis `redirect(url_for("afficher_jouer"), code=303)` ; `GET /jouer` / `GET /partie` sans param affichent l'étape courante + ce message une fois puis l'effacent ; cas `etape inconnue de l'affaire` / `choix inconnu` / champs manquants restent 400 propres ; dernier coup → 303 vers `/bilan` inchangé ; validation (types, ≤200, motif affaire) et 404/405 FR inchangées.
  - Thèmes : transmettre le thème (`affaire.get("theme", "cyber")` validé, repli « cyber » pour anciennes sessions) à `partie.html`/`bilan.html` ; `base.html` expose un bloc/classe (`<body class="theme-{{ theme|default('neutre') }}">` ou équivalent selon contrat tester) ; `accueil.html` + `erreur.html` utilisent `theme-neutre` ; `partie.html`/`bilan.html` utilisent `theme-<nom>`.
  - `static/style.css` : déplacer le style actuel sous `.theme-cyber` (même rendu sombre/terminal/accents) ; ajouter `.theme-neutre` clair et sobre (fond clair, texte sombre, contraste AA) + `.theme-avocat` distinct minimal ; garder les sélecteurs existants (`tableau-de-bord`, `chrono`, `barre`, badges…) fonctionnels dans chaque thème.
  - `templates/base.html` : retirer « Sans IA » du footer (ex. « Un jeu d'orientation : on te regarde jouer, pas répondre à un questionnaire. »), sans autre changement de structure.
- Critères d'acceptation : tests retour-303 + thèmes + footer verts ; PRG 303, redirects accueil, 404/405 FR, debug off toujours verts.

## Étape 4 — Dev bilan : fiche métier + « Essaie un autre métier », sans métiers proches (dev)
- Objectif vérifiable : bilan conforme à la demande et accessible.
- `dev` (`app/web.py` `_page_bilan` + `templates/bilan.html`, lecture `data/metiers.json` avec repli propre FR si illisible) :
  - Supprimer toute section « Métiers proches de ton profil » / `metiers_details` calculés depuis `profils.json` (ne plus les transmettre ni les afficher ; garder `calculer_bilan` moteur intact pour compat tests moteur, seul l'affichage change).
  - Garder en premier la carte profil (`section.carte-profil`, `data-testid="profil"`, titre + texte = ce que le joueur a aimé faire), puis scores (5 `<progress data-trait>` + libellés accentués + top 2 `dominant`/`data-dominant`, mot « score »), fin + jauge gravité (`<meter>` + libellé), citations (≥2 vrais labels), séparateurs `<hr>` — inchangés.
  - Ajouter « fiche métier » du métier joué (résolu via `affaire["metier"]`/`theme` → entrée `data/metiers.json`) : titre, « Au quotidien » en 3 points (liste), « Qualités utiles », « Formations possibles » ; si métier inconnu/illisible → repli propre (pas de traceback, pas de 500).
  - Ajouter bloc « Essaie un autre métier » (titre exact + `data-testid` selon contrat tester) listant chaque métier de `data/metiers.json` avec badge « Jouable » si jouable (seul expert cyber en prod) sinon « Bientôt ».
- Critères d'acceptation : `tests/test_themes_retour_bilan.py` (ou équivalent tester) entièrement vert + `test_web` bilan (scores/fins/citations) toujours vert ; `ruff check .` et `pytest -q` verts ensemble.

## Ordre de délégation (imposé)
1. `tester` → tests + évolutions volontaires listées (rouge autorisé).
2. `dev` → données puis code jusqu'au vert, sans modifier `tests/`.
3. `reviewer` → relit diff, conformité AGENTS.md (validation, erreurs propres FR, sans IA obligatoire, pas de clé, harness intact, pas de modif tests par dev).
- Fin globale seulement si `ruff check .` et `pytest -q` passent ensemble.
- Interdictions : planificateur ne code pas ; aucun commit sans demande explicite ; écriture `.py` via shell interdite ; ne pas modifier `.opencode/` ni `AGENTS.md`.

## Risques connus
- Distinction 400 vs 303 : étape inexistante (400) vs étape valide mais non courante (303 retour arrière) — à figer par tester pour ne pas casser `test_prg_redirect`.
- Accents/casse : message retour arrière exact à assert en brut décodé (`page_texte`) ; « Sans IA » à assert insensible casse.
- CSS : le neutre clair ne doit pas casser les asserts sombre de `test_immersion` → les scoper à `.theme-cyber` (évolution tester).
- Bilan : suppression métiers proches casse volontairement 2–3 anciens tests → évolutions tester obligatoires et listées.
