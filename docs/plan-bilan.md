# Plan — Bilan enrichi : profil en tête, métiers réels, barres et jauge

## Contexte
- État actuel : `templates/bilan.html` affiche dans l'ordre fin + `Gravité finale : X` brut, liste texte des scores (`trait : N`), citations, puis profil en bas avec `metiers_proches` = pastilles de chaînes parmi {expert cyber, avocat, médecin}. `data/profils.json` = 4 profils contraints à ces 3 métiers. Affaire cyber : les « bons » choix donnent 1–3 pts sur 1–2 traits, les « mauvais » donnent `traits: {}` (score nul). Tests existants verrouillent l'ancien contrat : `test_contenu_cyber::test_profils_metiers_proches_parmi_les_trois_metiers`, `test_moteur::test_bilan_profil...` (`metier in (expert cyber, avocat, médecin)`), `test_web` bilan (`"score"`, chaque trait non accentué en minuscules, titres de fins, ≥2 labels cités).
- Demande : (2) profil en haut dans grande carte, (3) ≥6 profils réels avec 3–4 métiers variés + phrase de lien + badge jouable/bientôt [changement de règle volontaire], (4) chaque choix cyber = 1–3 pts sur 1–2 traits, (5) barres de progression + libellés accentués + 2 dominants en évidence, (6) jauge gravité lisible au lieu de « Gravité finale : 10 », (7) garder validation + tests existants, ajouter tests profil/barres/séparateur. Ordre imposé : tester d'abord (TDD), car règles changent volontairement.
- Harness gelé : ne pas modifier `.opencode/`, `AGENTS.md` ; `dev` ne touche jamais à `tests/` ; fin seulement si `ruff check .` et `pytest -q` verts.

## Étape 1 — Tester d'abord : nouveaux tests + évolution volontaire des contraintes (tester seul)
- Objectif vérifiable : le comportement attendu est figé par tests avant tout code ; les ruptures volontaires sont explicites et tracées.
- `tester` écrit (nouveau fichier `tests/test_bilan_enrichi.py`, style existant, client Flask + helpers `page_texte`/`assert_sans_traceback`) :
  1. Profil en haut : `GET /bilan` après parcours complet → 200 ; la carte profil (sélecteur `section.carte-profil` ou `data-testid="profil"`) apparaît AVANT la section scores/fin dans le HTML (index de position), contient titre + texte du `bilan.profil` + métiers proches.
  2. Profils réels : `data/profils.json` = liste ≥6 ; chaque profil a `id, titre, texte, traits_dominants` (parmi les 5) + `metiers` ou `metiers_proches` enrichi = 3–4 entrées, chacune avec nom de métier réel (ex. analyste SOC, administrateur systèmes, etc.) + phrase `lien`/`pourquoi` non vide expliquant le lien au profil + statut jouable (`jouable: true/false` ou équivalent). Tester définit le schéma exact et met à jour les anciens tests de contrainte (`test_contenu_cyber` métiers ⊆ 3 métiers, `test_moteur` métiers in 3 métiers) pour le nouveau contrat — lister chaque modification dans son rapport ; `dev` ne doit jamais le faire.
  3. Jouable/bientôt : page bilan affiche pour chaque métier proche un badge « Jouable » si métier = expert cyber (seule affaire existante) et « Bientôt » sinon ; test assert les deux mentions présentes quand le profil contient les deux cas.
  4. Scores significatifs : chaque choix de `cyber-alerte-serveur-rh.json` a `traits` = 1–2 clés parmi les 5, chaque valeur 1–3 ; test itère tous les choix ; garde les assertions existantes (embranchement, 6–8 étapes, suites valides).
  5. Barres + dominants : bilan contient 5 barres (`<progress>` ou `role="progressbar"` + `data-trait="enqueter"` non accentué pour compat) avec libellés accentués visibles (Analyser, Convaincre, Enquêter, Aider, Protéger) ; les 2 traits au meilleur score portent une classe/attribut d'évidence (`classe dominant` / `data-dominant="true"`, exactement 2 sauf ex æquo documenté) ; le mot « score » reste présent pour compat `test_web`.
  6. Jauge gravité : plus aucun texte « Gravité finale : N » brut ; présence d'une jauge (`<meter>` ou `role="meter"`/`gauge` + libellé lisible ex. Impact maîtrisé/limité/élevé selon seuils des fins) + valeur accessible (`aria-valuenow` ou `data-gravite`) ; sans traceback.
  7. Séparateur : présence d'un séparateur visible entre sections du bilan (`<hr>` ou `class="separateur"`, ≥1) ; validation et erreurs propres inchangées (400/404/405 FR, PRG 303, redirects accueil toujours verts).
- Critères d'acceptation : nouveaux tests rouges pour les bonnes raisons (profil pas en haut, pas de barres/jauge/séparateur, profils <6) ; rapport tester listant les anciens tests volontairement évolués ; `ruff check .` vert sur `tests/`.

## Étape 2 — Données : 6 profils réels + affaire cyber scorée (dev, sans toucher tests)
- Objectif vérifiable : contenus significatifs sans casser le format ni le moteur.
- `dev` écrit (données uniquement, pas de Python sauf validation si besoin) :
  - `data/profils.json` : ≥6 profils selon schéma figé par tester (3–4 métiers réels variés chacun + phrase de lien + statut jouable). Exemples de métiers réels : analyste SOC, administrateur systèmes et réseaux, expert cyber, développeur, data analyst, avocat (droit du numérique), médecin, infirmier, technicien support, chef de projet. Seul « expert cyber » (affaire existante) = jouable ; tous les autres = bientôt. Français soigné, sans IA, sans clé.
  - `data/affaires/cyber-alerte-serveur-rh.json` : chaque choix (y compris les « mauvais » c2/c4/c6/c8/c10/c12/c14) reçoit 1–3 pts sur 1–2 traits cohérents éditorialement (ex. choix précipité → convaincre/aider maladroits mais non nuls) ; valeurs 1–3, 1–2 clés, traits autorisés ; gravités, suites, embranchement, 6–8 étapes, fins inchangées (seuils 2/6/99).
- Critères d'acceptation : tests étape 1 §§ 2 et 4 verts ; `test_affaires` (format) + parcours moteur ≥3 coups toujours verts ; `ruff` + `pytest` ciblés verts.

## Étape 3 — Moteur/web : porter les métiers enrichis sans régression (dev)
- Objectif vérifiable : `calculer_bilan` et `GET /bilan` exposent le nouveau modèle tout en gardant l'ancien contrat lisible.
- `dev` (Python `app/` uniquement) :
  - `app/moteur.py` : accepter/forward le nouveau champ métiers (noms + liens + jouable) ; `bilan["metiers_proches"]` reste la liste des noms (compat) + nouveau `bilan["metiers_details"]` (ou équivalent tester) avec phrases ; `bilan["traits_dominants"]` (top 2, ex æquo = premier rencontré, documenté) + `bilan["gravite_max"/"niveau"]` si besoin de la jauge ; validation FR inchangée (types, longueurs, traits parmi 5).
  - `app/web.py` : `_page_bilan` transmet `traits_dominants`, détails métiers, mapping libellés accentués (`Analyser, Convaincre, Enquêter, Aider, Protéger`), max score pour barres ; conserve PRG 303, redirects, 404/405 FR, debug off.
- Critères d'acceptation : tests moteur existants (après évolution volontaire tester) + nouveaux tests données verts ; aucun autre test cassé.

## Étape 4 — Interface bilan : carte profil haute, barres, jauge, séparateur (dev)
- Objectif vérifiable : bilan lisible et accessible, compatible anciens tests.
- `dev` (`templates/bilan.html` + `static/style.css` uniquement) :
  - Carte profil en PREMIER (`<section class="carte carte-profil" data-testid="profil">`, nom en `h2`, description, métiers proches avec phrase de lien + badge « Jouable » / « Bientôt »).
  - Scores : 5 lignes avec libellé accentué visible + `<progress max=X value=N>` (ou `role=progressbar` + `aria-valuenow`) + `data-trait` non accentué + valeur chiffrée ; top 2 = `class="dominant"` + `data-dominant="true"` ; garder le mot « score(s) » dans un titre/aide.
  - Gravité : `<meter>` (ou `role=meter`) + libellé (ex. « Impact maîtrisé / limité / élevé ») + `data-gravite`/`aria-valuenow` ; supprimer le texte brut « Gravité finale : N ».
  - Fin + citations (titres de fins, ≥2 vrais labels) conservées en dessous ; `<hr class="separateur">` (ou équivalent) entre sections ; citations inchangées ; responsive/contraste soignés, sans framework, sans IA.
  - Compat : page contient toujours « score », chaque `data-trait` non accentué, titres de fins, labels cités, « cyber » où attendu.
- Critères d'acceptation : `tests/test_bilan_enrichi.py` entièrement vert + `test_web` bilan (scores/fins/citations) toujours vert ; `ruff` + `pytest -q` verts.

## Ordre de délégation (TDD, imposé par la demande)
1. `tester` → tests + évolutions volontaires listées (rouge autorisé).
2. `dev` → données puis code jusqu'au vert, sans modifier `tests/`.
3. `reviewer` → relit diff, conformité AGENTS.md (validation, erreurs propres FR, sans IA, pas de clé, harness intact).
- Fin globale seulement si `ruff check .` et `pytest -q` passent ensemble.
- Interdictions : planificateur ne code pas ; aucun commit sans demande explicite ; écriture `.py` via shell interdite ; ne pas modifier `.opencode/` ni `AGENTS.md`.

## Risques connus
- Ruptures volontaires à faire porter par `tester` seul : contrainte métiers ⊆ 3 métiers, assertion `metier in (expert cyber, avocat, médecin)`, matching exact `trait in page.lower()` (accents : `Enquêter` vs `enqueter` → prévoir `data-trait` + normalisation dans les nouveaux tests), texte « Gravité finale : N » supprimé au profit de la jauge.
