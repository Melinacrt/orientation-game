# Plan — PRG 303, redirects accueil, 404/405 en français, debug off

## Contexte
- État actuel (`app/web.py` `creer_app`) : `GET /partie?affaire=<id>` démarre une partie et rend 200 ; `POST /jouer` (formulaire `affaire, etape, choix`) rend directement 200 (page étape suivante ou bilan) ; `GET /bilan` sans session rend 400 technique ; `GET /partie` sans `affaire` rend 400 technique ; pas de gestionnaire 405 (message Flask anglais par défaut) ; gestionnaire 404 reprend `exc.description` anglais de Flask ; `if __name__ == "__main__": creer_app().run(debug=True)`.
- Demande : (1) PRG après POST choix, (2) GET sans partie → accueil, (3) 404/405 en français, (4) debug désactivé par défaut. Chaque point avec tests.
- Harness gelé : ne pas modifier `.opencode/`, `AGENTS.md` ; `dev` ne touche jamais aux tests ; fin seulement si `ruff check .` et `pytest -q` verts.

## Étape 1 — POST/Redirect/GET (303) après un choix
- Objectif vérifiable : un rafraîchissement / retour après un choix ne redemande jamais de renvoyer le formulaire.
- `tester` écrit (nouveau fichier `tests/test_prg_redirect.py`, sans casser l'intention des tests existants — adapter les helpers `jouer_coup` / parcours complet à suivre les redirects car le contrat 200-direct change volontairement) :
  - `POST /jouer` valide (après `GET /partie?affaire=cyber-alerte-serveur-rh`) → 303 (ou 302 si Flask contraint, assert `in (303, 302)` avec préférence 303), header `Location` vers une page GET qui affiche l'étape courante (`/jouer` ou `/partie` sans param).
  - Suivre la redirection (`GET Location`) → 200, contient le texte de l'étape suivante ou la conséquence, sans traceback.
  - Dernier coup du parcours (suite `None`) → POST 303 vers `/bilan` (ou page GET bilan), suivi → 200 avec titre de fin.
  - `POST /jouer` invalide (étape/choix inconnu) → reste 400 page propre (pas de redirect), partie non corrompue.
- `dev` implémente dans `app/web.py` uniquement : `POST /jouer` sauvegarde `session["affaire_id"]` + `session["etat"]` puis `redirect(..., code=303)` vers la page GET d'étape (`GET /jouer`, voir étape 2) ou vers `/bilan` si `etape_courante is None` ; ne rend plus jamais 200 directement sur succès.
- `reviewer` vérifie PRG + pas de double-soumission au refresh.
- Critères d'acceptation : POST valide → 303 + `Location` GET ; refresh du GET ne rejoue pas le coup (scores stables via `GET /bilan`) ; `ruff` + `pytest` verts.

## Étape 2 — GET sans partie en cours → redirect accueil
- Objectif vérifiable : aucun 400 technique quand il n'y a rien à afficher.
- `tester` écrit dans le même nouveau fichier :
  - Client vierge (sans session) : `GET /partie` (sans `?affaire`) → 302 vers `/` (assert `status in (301, 302, 303, 307, 308)` + `Location` finit par `/`) ; suivre → 200 accueil.
  - Client vierge : `GET /jouer` (cible GET du PRG) → même redirect vers `/`.
  - Optionnel : `GET /bilan` sans session → soit redirect vers `/` (préféré, cohérent), soit 400 propre existant conservé — trancher dans le test : accepter redirect vers `/` comme succès (documenter le choix retenu).
  - `GET /partie?affaire=<id>` valide garde le comportement actuel (200 + démarrage partie).
- `dev` implémente : `GET /partie` sans param `affaire` : si session (`etat` dict + `affaire_id` str valides) affiche l'étape courante (ou redirect `/bilan` si terminée), sinon `redirect(url_for("accueil"))` ; ajoute `GET /jouer` avec la même logique (affiche étape courante / bilan, sinon redirect accueil). Aucune page 400 dans ces cas.
- `reviewer` vérifie redirects + session intacte.
- Critères d'acceptation : GET sans session → redirect `/` suivi en 200 accueil ; GET avec session → 200 étape courante ; `ruff` + `pytest` verts.

## Étape 3 — Messages 404 et 405 en français
- Objectif vérifiable : aucune phrase anglaise de Flask sur page inexistante / méthode interdite.
- `tester` écrit :
  - `GET /page-inexistante-qui-n-existe-pas` → 404, page propre, `assert_sans_traceback`, minuscules sans `the requested url`, `not found on the server`, `method is not allowed` ; contient au moins un mot français (`page introuvable`, `introuvable`, `retour`, `accueil`, `erreur`).
  - `GET /jouer` avec méthode interdite ? Choisir un cas 405 déterministe : ex. `GET` sur une route POST-only si conservée, ou `POST /` / `POST /partie` → 405 page propre française (même assertions anti-anglais). Si `GET /jouer` existe (étape 2), utiliser `POST /` et `DELETE /` comme cas 405.
  - Vérifier `Content-Type` HTML et absence de `traceback`.
- `dev` implémente : gestionnaires `@application.errorhandler(404)` et `@application.errorhandler(405)` qui ignorent `exc.description` anglais et rendent `erreur.html` avec messages français fixes (ex. 404 : « Page introuvable : ... Retour à l'accueil. », 405 : « Méthode non autorisée : ... Retour à l'accueil. ») ; ne jamais exposer la description Flask brute.
- `reviewer` vérifie français + conformité « erreurs propres ».
- Critères d'acceptation : 404 et 405 → pages propres 100 % françaises, sans traceback ; `ruff` + `pytest` verts.

## Étape 4 — Mode debug désactivé par défaut
- Objectif vérifiable : pas de debugger/Werkzeug exposé en prod par défaut.
- `tester` écrit :
  - `app = creer_app()` → `assert not app.debug` et `assert not app.config.get("DEBUG")`.
  - Inspection source `app/web.py` (ou `app/__init__.py` / lanceur) : aucun `run(debug=True)` inconditionnel ; si `debug=` présent, défaut `False` ou piloté par variable d'environnement (`os.environ.get(...)`) évaluée à faux sans env.
- `dev` implémente : remplacer `creer_app().run(debug=True)` par `run(debug=False)` ou `debug=os.environ.get("FLASK_DEBUG", "0") == "1"` (défaut faux) ; `creer_app()` ne met jamais `DEBUG=True`.
- `reviewer` vérifie aucune clé/Secret en dur ajoutée, `.env` toujours ignoré.
- Critères d'acceptation : tests debug verts ; `ruff` + `pytest` verts.

## Ordre de délégation (par étape, TDD)
1. `tester` → écrit les tests (rouge autorisé).
2. `dev` → implémente dans `app/` jusqu'au vert, sans modifier les tests.
3. `reviewer` → relit diff, conformité AGENTS.md (validation entrées, erreurs propres FR, sans IA, pas de clé API).
- Fin globale seulement si `ruff check .` et `pytest -q` passent ensemble.
- Interdictions : planificateur ne code pas ; aucun commit sans demande explicite ; écriture `.py` via shell interdite ; ne pas modifier `.opencode/` ni `AGENTS.md`.

## Risque connu — contrat `POST /jouer` 200 → 303
- Les helpers existants `tests/test_web.py::jouer_coup` assertent `200` direct. Le changement 303 est volontaire (demande explicite). `tester` seul est autorisé à faire évoluer ces helpers/appels vers `follow_redirects` ou suivi manuel de `Location` ; `dev` ne doit jamais éditer `tests/`.
