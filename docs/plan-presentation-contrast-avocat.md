# Plan — Présentation, contraste, bilan sans gravité, thème avocat (polices locales)

## 0. Constat réel du dépôt (vérifié avant plan)

- `AGENTS.md` lu. Règles : pas de code applicatif par le planificateur, pas de modif
  des tests pour les faire passer (sauf `tester`), pas de commit, `ruff + pytest`
  verts pour finir, ordre tester → dev → reviewer.
- Structure réelle Flask (`app/web.py` → `creer_app()`) :
  - `template_folder = RACINE / "templates"` → `templates/accueil.html`,
    `templates/base.html`, `templates/partie.html`, `templates/bilan.html`,
    `templates/erreur.html`.
  - `static_folder = RACINE / "static"` → **le CSS réel est `static/style.css`**
    (pas `app/static/style.css` ; `app/static/` ne contient qu'un sous-dossier
    `img/` non servi). Ne pas supposer `app/static/`.
  - Images servies : `static/img/` (ex. `01-salle-serveurs.png`,
    `02-alerte-rancon.png`, `06-plaidoirie.jpg`, images avocat `01-garde-a-vue.jpg`,
    etc.). `app/static/img/` contient d'autres PNG non servis — ne pas les utiliser.
  - Polices locales **présentes** dans `static/fonts/` :
    `CormorantGaramond-VariableFont_wght.ttf`,
    `CormorantGaramond-Italic-VariableFont_wght.ttf`,
    `PinyonScript-Regular.ttf`. Donc intégration `@font-face` locale exigée
    (aucun chargement Google Fonts / réseau). Vérifier les noms exacts avant
    de les référencer ; ne rien renommer/déplacer sans nécessité.
- Ancienne phrase trouvée dans `templates/accueil.html:6-7`
  (« ...qui montre ce que tu as aimé faire et quels métiers te correspondent. »).
  `AGENTS.md:6` contient une variante (« ...ce qu'il a aimé faire et quels métiers
  lui correspondent. ») → **ne pas modifier AGENTS.md** (interdit).
  `README.md` ne contient pas l'ancienne phrase exacte mais une variante
  (« ...reçois un bilan qui cite tes vrais choix. ») → aligner si pertinent
  sans dénaturer.
- Bilan actuel (`templates/bilan.html:40-41`) affiche
  « Gravité de l'incident : ... (... / ...) » + `<meter>` ; `app/web.py`
  (`_page_bilan`, `_niveau_gravite_bilan`, `_gravite_max_bilan`) fournit les
  variables. Le calcul reste dans `app/moteur.py` (ne pas toucher).
- CSS actuel (`static/style.css`) : styles globaux sombres (salle de crise),
  puis blocs `.theme-cyber`, `.theme-neutre`, `.theme-avocat` minimaux.
  Cause probable du bug de contraste confirmée par lecture : `h1/h2`,
  `.barre`, `.point-fort`, `progress` globaux sombres s'appliquent aux thèmes
  clair/parchemin.
- Tests existants sensibles : `tests/test_bilan_enrichi.py::test_bilan_jauge_gravite_lisible_sans_texte_brut`
  exige la jauge → **rupture volontaire portée par `tester` seul**.
  `tests/test_themes_retour_bilan.py` fige thèmes/badges/fiche métier/footer.

## 1. Étapes (objectif vérifiable + critères d'acceptation)

### Étape 0 — Variables CSS + fix contraste (prioritaire, bilan avocat)
- Objectif : toute couleur de base passe par des variables
  `--fond, --carte, --texte, --titre, --accent, --accent-texte, --bordure,
  --surligne, --surligne-texte, --barre, --barre-fond` ; chaque thème
  (`.theme-neutre`, `.theme-cyber`, `.theme-avocat`) définit **TOUTES** ses
  variables ; aucune couleur propre à un thème écrite en dur hors de son bloc.
- Acceptation : bilan avocat lisible (h1/h2 bordeaux sur parchemin, Point fort
  lisible, barres bordeaux/beige pas bleues) ; rendu cyber inchangé à l'œil ;
  test variables-complètes + test contraste WCAG ≥ 4,5 vert.

### Étape 1 — Accueil thème neutre uniquement
- Objectif : pile système `system-ui, "Segoe UI", Roboto, Helvetica, Arial,
  sans-serif` sur l'accueil (thème neutre), sans dépendance externe ;
  cyber/avocat gardent leurs polices. En-tête (titre grand + accroche
  « Une orientation où on te regarde jouer, pas répondre à un questionnaire. »),
  grille cartes métiers (2 col. desktop / 1 mobile), image en haut par carte
  (cyber : `01-salle-serveurs.png` ou `02-alerte-rancon.png` ;
  avocat : `06-plaidoirie.jpg`), nom + phrase + badge « Jouable »/« Bientôt »,
  bouton + survol léger si jouable, atténuée non cliquable si Bientôt.
  Cyber + avocat « Jouable », médecin « Bientôt ».
  Palette sobre (fond gris clair, texte foncé, accent unique, arrondis, ombres
  douces, contraste, espacement). Supprimer « Avocat et médecin arrivent
  bientôt. » au profit des badges.
- Acceptation : tests accueil (pas de monospace, cartes+badges, nouvelle phrase)
  verts ; pages cyber/avocat inchangées typographiquement.

### Étape 2 — Texte de présentation aligné partout (sauf AGENTS.md)
- Objectif : remplacer « ...qui montre ce que tu as aimé faire et quels métiers
  te correspondent » par « Choisis un métier, vis une affaire, prends des
  décisions, puis découvre ce que tu as aimé faire et les études qui mènent
  à ce métier. » dans `templates/accueil.html` (+ `README.md` et tout template
  contenant l'ancienne phrase). Ne pas modifier `AGENTS.md`, ni la logique,
  ni les affaires.
- Acceptation : `grep` ancienne phrase vide hors `AGENTS.md` ; nouvelle phrase
  présente ; tests verts.

### Étape 3 — Bilan sans affichage gravité (calcul conservé)
- Objectif : supprimer du template `bilan.html` le texte
  « Gravité de l'incident : ... (x / 99) » et la jauge `<meter>` associée.
  Moteur (`app/moteur.py`) et données inchangés. `tester` fait évoluer les tests
  du bilan exigeant la jauge (rupture volontaire) : le bilan ne contient plus
  « Gravité de l'incident » ni « / 99 » (côté gravité) et affiche toujours
  fin, profil, barres, choix cités, fiche métier + études.
- Acceptation : bilan sans « Gravité de l'incident » ni jauge, avec tout le
  reste ; `test_moteur.py` / calcul gravité toujours verts.

### Étape 4 — Thème avocat refonte complète + polices locales
- Objectif : pages partie/bilan/erreur de l'affaire avocat (thème avocat seul,
  cyber inchangé) : fond marron foncé boiserie (dégradé/motif CSS, sans image
  externe) ; cartes parchemin crème + double bordure dorée fine + ombre douce ;
  texte courant serif via `@font-face` Cormorant Garamond depuis
  `static/fonts/` (secours `"Palatino Linotype", "Book Antiqua", Georgia, serif`) ;
  titres h1/h2 + noms de profil en Pinyon Script via `@font-face` local
  (secours `"Segoe Script", "Lucida Handwriting", "Brush Script MT", cursive`),
  calligraphie limitée aux titres (jamais choix/conséquences/scores) ;
  titres bordeaux sur parchemin, texte brun très foncé, accents dorés,
  boutons bordeaux/texte crème, « Point fort » fond doré très clair + texte brun
  + libellé bordeaux, barres bordeaux sur beige, tableau de bord + chrono
  lisibles même style ; séparateurs filet doré + ornement SVG inline
  (balance ou étoile) entre grandes sections du bilan ; disclaimer
  « Affaire fictive et simplifiée, ce n'est pas un conseil juridique. »
  visible, lisible, petit sur parchemin. Aucune dépendance réseau ; page correcte
  même si polices absentes ; URL statiques des polices fonctionnelles.
- Acceptation : pages avocat 200 avec/sans fichiers de polices (test),
  aucun `@import`/lien Google Fonts, aucun code couleur cyber en dur dans
  `.theme-avocat`, contraste WCAG ≥ 4,5 sur les 4 couples.

## 2. Ordre de délégation

1. `tester` : ajoute `tests/test_presentation_contraste.py` (ou nom cohérent) :
   police accueil sans monospace ; cartes + badges Jouable/Bientôt ;
   nouvelle phrase ; absence gravité bilan ; variables complètes par thème ;
   contraste WCAG ≥ 4,5 sur `(--texte/--carte, --titre/--carte,
   --surligne-texte/--surligne, --accent-texte/--accent)` par thème ;
   pas de couleur cyber en dur dans `.theme-avocat` ; pages avocat 200
   avec/sans polices ; `@font-face` locales sans URL externe.
   Fait évoluer le test jauge gravité (rupture volontaire).
   Tests existants sinon inchangés et verts.
2. `dev` : implémente dans `static/style.css`, `templates/` (accueil, bilan,
   base si besoin), sans toucher `app/moteur.py`, `data/affaires/`,
   `.opencode/`, `AGENTS.md`, ni aux tests. Référence les 3 fichiers
   `static/fonts/` par `@font-face` avec bons formats/chemins (`url_for`
   ou chemins `/static/fonts/...`). Rendu cyber inchangé.
3. `reviewer` : relit le diff, vérifie AGENTS.md (validation entrées, erreurs
   propres, pas de clé API, pas de modif tests, hors-ligne, logique/affaires
   intactes).

## 3. Fini quand

`ruff check . --no-cache` et `pytest -q` tous deux verts, rien committé,
résumé + fichiers modifiés + résultats tests + statut polices locales.
