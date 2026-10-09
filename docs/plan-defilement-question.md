# Plan — Ne plus revenir en haut après avoir répondu (ancre sur la question)

## 0. Constat réel du dépôt (vérifié avant plan)

- `AGENTS.md` lu : planificateur ne code pas ; ordre tester → dev → reviewer ;
  `dev` ne modifie jamais les tests ; fin d'étape seulement si `ruff check .`
  et `pytest -q` passent ; aucun commit sans demande explicite.
- Mécanisme actuel : le formulaire de `templates/partie.html` poste vers
  `url_for('jouer')` (`POST /jouer`). `app/web.py::jouer` sauvegarde l'état en
  session puis redirige en `303` vers `afficher_jouer` (`GET /jouer`), qui
  réaffiche l'étape. Le navigateur recharge la page en haut → la nouvelle
  question n'est pas visible sans scroller.
- Le bloc de la question est `<section class="carte">` (`templates/partie.html:31`)
  et ne possède aucun `id` ; l'en-tête `.bandeau` n'est pas `position: fixed`
  (aucun masquage à prévoir).
- Aucun test n'asserte la valeur exacte de l'attribut `action` du formulaire
  (`action=` absent des tests). Le fragment d'URL (`#...`) est retiré de la
  requête HTTP puis réappliqué par le navigateur après le redirect 303.
- Solution retenue, la plus simple et sans toucher au Python : un `id` stable
  sur le bloc question + une ancre `#question` dans l'`action` du formulaire.
  Seul `templates/partie.html` change ; `app/` et les affaires sont intacts.

## 1. Étapes

### Étape 1 — tester : figer le contrat d'ancre
- Objectif vérifiable : un test dans `tests/` vérifie que la page partie
  rendue contient un `id="question"` sur le bloc question ET que l'attribut
  `action` du formulaire cible cette ancre (`.../jouer#question`).
- `tester` : écrit le test (peut être rouge avant l'étape 2), ne touche à
  aucun autre fichier.
- Critères d'acceptation : test ajouté, exécutable, ciblé sur le rendu HTML.

### Étape 2 — dev : ancre minimale dans le template
- Objectif vérifiable : dans `templates/partie.html`, ajouter `id="question"`
  au `<section class="carte">` et faire pointer l'`action` du formulaire vers
  `{{ url_for('jouer') }}#question`.
- `dev` : modifie uniquement `templates/partie.html` ; ne touche jamais aux
  tests, à `app/` ni aux affaires.
- Critères d'acceptation : tests de l'étape 1 verts ; comportement inchangé
  côté serveur (aucune route ni validation modifiée).

### Étape 3 — reviewer (lecture seule)
- Relit `git diff` et vérifie : pas de modification de la logique du jeu,
  pas de test modifié, pas de clé d'API, `app/` et `data/` intacts.
- Critères d'acceptation : rapport écrit (écarts ou « RAS »).

## 2. Fin d'étape (obligatoire)
- Étape terminée seulement si `ruff check .` et `pytest -q` passent tous les
  deux. Aucun commit (non demandé). En cas de doute ou de rupture, reporter
  après la démo plutôt que risquer les vérifications finales.
