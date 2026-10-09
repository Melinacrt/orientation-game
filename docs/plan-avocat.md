# Plan — Ajout du métier avocat de la défense

## 0. Contexte et prérequis (vérifiés le 09/10/2026)

- État actuel lu : `AGENTS.md`, `data/affaires/avocat-defense.json` (id `avocat-defense-001`, `metier: avocat`, `theme: avocat`, 7 étapes e1–e7, fins 2/6/99, images `img/avocat-*.jpg`), `data/metiers/fiche_avocat.json` (quotidien 3 pts, qualités 5, formations 7 objets `{etape, duree, description}`, `bon_a_savoir` 2 pts, `mentions`), `data/profiles/profile_avocat.json` (5 profils : analyser/convaincre/enqueter/aider/proteger, nom + description 2 phrases 2e personne — NON vide), `data/metiers.json` (cyber jouable, avocat non jouable à remplacer, medecin non jouable), `data/profils.json` (6 profils cyber : `id, titre, texte, traits_dominants, metiers_proches[{nom, lien, jouable}]`), `app/web.py` (thème par affaire, retour arrière 303, fiche métier + « Essaie un autre métier », footer sans « Sans IA »), `app/moteur.py` (`tableau_de_bord` cyber), `app/affaires.py` (validation `theme`, `image` optionnelle), `templates/` + `static/style.css`.
- Prérequis étape précédente VERT : `ruff check . --no-cache` → « All checks passed », `pytest -q` → 157 passed. Thème par affaire, `data/metiers.json`, bloc « Essaie un autre métier » présents en prod. → on ne s'arrête pas, on continue.
- Règles : ne pas modifier `.opencode/`, `AGENTS.md`. Ordre tester → dev → reviewer. Fin seulement si `ruff check . --no-cache` et `pytest -q` verts ensemble. Aucun commit sans demande explicite. Planificateur ne code pas (écriture autorisée uniquement dans `docs/`).
- ⚠️ Anomalie images constatée sur disque (à figer par tester/dev, à me signaler si bloquant) :
  - Dossier servi par Flask = `static/img/` (`app/web.py` : `static_folder=RACINE/static`, `_image_url_etape` cherche dans `RACINE/static/img`). `app/static/img/` n'est PAS servi et ne contient QUE les 7 PNG cyber.
  - `static/img/` contient : `01-garde-a-vue.jpg`, `02-etude-dossier.jpg`, `03-rencontre-cliente.jpg`, `04-interrogatoire-temoin.jpg`, `05-echange-parquet.jpg`, `06-plaidoirie.jpg` (+ PNG cyber).
  - La demande cite dans `app/static/img/` : `01-garde-a-vue, 02-etude-dossier, 03-rencontre-cliente, avocat-temoin, avocat-couloir, avocat-plaidoirie`. Les 3 derniers noms (`avocat-*`) N'EXISTENT sur aucun disque ; leurs équivalents probables sont `04-interrogatoire-temoin.jpg`, `05-echange-parquet.jpg`, `06-plaidoirie.jpg`. Tester doit vérifier l'existence réelle et dev doit pointer vers des fichiers existants dans le dossier servi, sans laisser de `<img>` cassé.

## 1. Étape tester — figer les contrats avocat (tester seul, rouge autorisé)

- Objectif vérifiable : chaque point §2–§3 est couvert par un test qui échoue pour la bonne raison avant code.
- `tester` écrit (nouveau fichier suggéré `tests/test_avocat.py`, style fixtures `app`/`client` + helpers `page_texte`/`assert_sans_traceback`) :
  1. Données affaire : `data/affaires/avocat-defense-001.json` existe, `data/affaires/avocat-defense.json` n'existe plus (renommé, un seul fichier avocat) ; `id == avocat-defense-001`, `metier == avocat`, `theme == avocat` ; c18 et c21 ont `gravite == 6` ; `fins[].gravite_max == [1, 4, 99]` triés ; tout le reste du texte inchangé (titres, contextes, textes, labels, conséquences) ; aucune suite orpheline (toute `suite` non nulle référence une étape), tous les traits ∈ {analyser, convaincre, enqueter, aider, proteger}, gravités entières ≥ 0, 3 fins triées, chaque `image` référencée respecte le motif `img/` + existe sur le disque servi (`static/img/`, pas de `<img>` cassé) avec `image_alt` non vide inchangé ; mapping : e1 → `01-garde-a-vue`, e2 → `03-rencontre-cliente`, e3 → `02-etude-dossier`, e4 → témoin, e5 → couloir/parquet, e6+e7 → plaidoirie (même image voulue, tester fige les noms réels existants).
  2. Calibrage : chemin tout gravité 0 → première fin (« Une défense rigoureuse ») ; c18 seul (reste 0) ou c21 seul → troisième fin (« Une défense compromise ») ; un chemin à 2–3 choix de gravité 1–2 totalisant 2–4 (ex. c5(1)+c14(1)=2 ou c3(2)+c5(1)=3, tester fige les ids exacts) → deuxième fin (« Une défense sous tension »).
  3. Métiers/profils : `data/metiers.json` entrée `avocat` = contenu `fiche_avocat.json` sans doublon, `jouable is True`, cyber/medecin présents ; schéma étendu figé par tester (ex. `formations` accepte str OU `{etape, duree, description}`, plus `bon_a_savoir` et `mentions` optionnels) avec migration cyber sans régression d'affichage ; 5 profils avocat intégrés dans `data/profils.json` au schéma existant (`id/titre/texte/traits_dominants/metiers_proches`), noms/descriptions style cyber 2e personne ; le profil affiché dépend du métier joué (avocat → profil avocat, cyber → profil cyber inchangé) ; fiche avocat visible dans le bilan (`data-testid="fiche-metier"` + titre + quotidien + qualités + formations + `bon_a_savoir`/mentions si schéma) ; accueil liste cyber + avocat jouables, autres badges « Bientôt ».
  4. Interface : partie + bilan avocat contiennent `theme-avocat` (jamais sur accueil/erreurs qui restent `theme-neutre`) ; `static/style.css` définit `.theme-avocat` (serif/empattement, bordeaux et or, ambiance tribunal) distinct de `.theme-cyber` ; tableau de bord avocat = 3 libellés exacts « Confiance d'Inès » / « Solidité du dossier » / « Temps avant l'audience » avec formules simples figées par tester dérivées traits+gravité (même logique que cyber : base + bonus − malus gravité, bornes, temps dégressif par coup) + fonction pure équivalente (ex. `tableau_de_bord` branché sur `theme`/`metier`) ; tableau cyber inchangé (libellés machines/confiance direction/temps restant + formule) ; chrono MM:SS + images optionnelles comme cyber ; mention exacte « Affaire fictive et simplifiée, ce n'est pas un conseil juridique. » visible sur page partie ET bilan avocat.
  5. Non-régression : tous les tests existants restent verts sauf évolution volontaire unique portée par tester seul : si un test suppose que la première étape n'a pas d'image, le limiter à l'affaire cyber (ne pas modifier le contenu avocat). Lister chaque retouche dans son rapport (`dev` ne touche jamais `tests/`).
- Critères d'acceptation : nouveaux tests rouges pour les bonnes raisons (fichier non renommé, gravités 3/2-6-99, images `avocat-*.jpg` inexistantes, avocat non jouable, pas de `theme-avocat`, dashboard cyber sur affaire avocat, disclaimer absent) ; `ruff check .` vert.

## 2. Étape dev données — affaire + fiche + profils + accueil (dev, sans toucher `tests/`)

- Objectif vérifiable : contenus conformes au contrat tester, `test_affaires` + tests données avocat verts.
- `dev` :
  - Renommer (pas copier) `data/affaires/avocat-defense.json` → `data/affaires/avocat-defense-001.json` ; appliquer calibrage : c18=6, c21=6, fins 1/4/99 ; garder tout autre texte tel quel.
  - Images : mettre à jour UNIQUEMENT les champs `image` selon mapping §1 (e1 01-garde-a-vue, e2 03-rencontre-cliente, e3 02-etude-dossier, e4 témoin, e5 couloir, e6+e7 plaidoirie), `image_alt` inchangés ; vérifier l'existence sur le disque servi (`static/img/`) et me signaler tout fichier manquant au lieu d'inventer un chemin ; si besoin copier/renommer vers le dossier servi sans casser les PNG cyber ni laisser de doublon d'affaire.
  - `data/metiers.json` : remplacer le contenu de l'entrée `avocat` par `fiche_avocat.json` sans doublon, `jouable: true` ; adapter au schéma (si extension : `formations` objets + `bon_a_savoir` + `mentions`, migrer la fiche cyber avec, affichage cyber inchangé) ; une seule source de vérité = `data/metiers.json`.
  - `data/profils.json` : intégrer les 5 profils avocat adaptés au schéma existant (profils cyber inchangés) ; routage du profil selon le métier de l'affaire jouée.
  - Accueil : cyber + avocat jouables (liens vers chaque affaire), autres métiers badge « Bientôt ».
  - Validation `app/affaires.py` inchangée sauf si contrat tester l'exige ; erreurs FR propres conservées.
- Critères d'acceptation : affaire chargeable, tests calibrage + images + schéma verts ; `test_affaires`/`test_contenu_cyber` toujours verts.

## 3. Étape dev web — thème, dashboard, disclaimer, bilan (dev, `app/` + `templates/` + `static/`)

- Objectif vérifiable : habillage et bilan avocat conformes sans régression cyber/PRG/erreurs.
- `dev` :
  - Thème : `theme-avocat` (serif, bordeaux/or, tribunal) appliqué aux pages partie + bilan de l'affaire avocat ; accueil + erreurs restent neutres ; `static/style.css` : `.theme-avocat` distinct, `.theme-cyber` et `.theme-neutre` inchangés.
  - `tableau_de_bord` dépendant du thème/métier : avocat → « Confiance d'Inès / Solidité du dossier / Temps avant l'audience » (formules simples testées, dérivées traits+gravité, même logique que cyber) ; cyber → inchangé. Chrono + images optionnelles comme cyber (pas de `<img>` cassé, 200 + sans traceback si fichier absent).
  - Partie + bilan avocat affichent « Affaire fictive et simplifiée, ce n'est pas un conseil juridique. ».
  - Bilan : fiche avocat + bloc « Essaie un autre métier » (badges Jouable/Bientôt), profil selon métier, scores/barres/citations/fins inchangés.
  - À la fin : supprimer les dossiers `data/metiers/` et `data/profiles/` une fois intégrés (une seule source de vérité), SAUF s'ils sont utilisés par l'appli — auquel cas ne rien supprimer et me le dire. Vérifier par grep qu'aucun code ne les lit (`app/` ne lit que `data/metiers.json` et `data/profils.json`).
- Critères d'acceptation : `tests/test_avocat.py` (ou équivalent tester) entièrement vert + `test_web`, `test_immersion`, `test_themes_retour_bilan` toujours verts ; `ruff check . --no-cache` et `pytest -q` verts ensemble.

## 4. Ordre de délégation (imposé)

1. `tester` → tests + unique évolution volontaire (première étape sans image → scope cyber), rouge autorisé.
2. `dev` → données puis code jusqu'au vert, sans modifier `tests/`, sans committer, avec signalement si image manquante ou si `data/metiers/`/`data/profiles/` encore utilisés.
3. `reviewer` → relit le diff, conformité AGENTS.md (validation entrées, erreurs propres FR, sans IA obligatoire, pas de clé, harness intact, pas de modif tests par dev, texte affaire conservé, une seule source de vérité).
- Fin globale seulement si `ruff check . --no-cache` et `pytest -q` passent ensemble. Résumé des changements, rien committé.

## Risques connus

- Noms d'images `avocat-*` inexistants vs `04-interrogatoire-temoin / 05-echange-parquet / 06-plaidoirie` réels + dossier servi `static/img/` vs `app/static/img/` — à trancher par tester (figer les vrais chemins) puis dev (pointer vers l'existant, me signaler les manquants).
- Schéma `data/metiers.json` actuel (formations = liste de str) incompatible avec `fiche_avocat.json` (objets + `bon_a_savoir`/`mentions`) — tester fige l'extension, dev migre cyber sans régression (bilan cyber garde quotidien/qualités/formations).
- Calibrage fins 1/4/99 : chemin « 2–3 choix à 1–2 » ne passe en fin 2 que si total ∈ [2,4] — tester doit figer des ids totalisant 2–4, pas 6.
- Profils : `profile_avocat.json` (`trait/nom/description`) → `profils.json` (`traits_dominants/titre/texte/metiers_proches`) + routage par métier — tester fige la correspondance, dev garde les 6 cyber intacts.
