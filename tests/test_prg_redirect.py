"""Tests PRG 303, redirects vers l'accueil, 404/405 en français, debug off.

Plan : ``docs/plan-prg-redirect-erreurs-fr-debug.md``.

Contrats attendus (note pour ``dev``, implémentation dans ``app/`` uniquement) :
- ``POST /jouer`` valide ne rend plus 200 : il sauvegarde la session puis
  redirige (``code=303``, 302 toléré si Flask contraint, 303 préféré) vers la
  page GET de l'étape courante (``GET /jouer`` ou ``GET /partie`` sans
  paramètre) ou vers ``/bilan`` pour le dernier coup.
- ``GET /partie`` sans ``?affaire`` et ``GET /jouer`` sans partie en cours
  redirigent vers ``/`` (jamais de 400 technique) ; avec une session valide,
  ils affichent l'étape courante (200).
- Comportement retenu pour ``GET /bilan`` sans session : redirect vers ``/``
  (préféré, cohérent avec ``/partie`` et ``/jouer``).
- 404 et 405 : pages propres 100 % françaises (jamais la description anglaise
  de Flask), sans traceback, Content-Type HTML.
- ``creer_app()`` ne met jamais ``DEBUG`` ; aucun ``run(debug=True)``
  inconditionnel (défaut ``False`` ou variable d'environnement fausse
  par défaut).

Phase rouge TDD normale : ces tests échouent tant que ``app/web.py``
n'implémente pas le PRG / les redirects / les pages françaises / debug off.
"""

import html
import json
import re
from pathlib import Path

import pytest

try:
    from app.web import creer_app
except ImportError:  # pragma: no cover - phase rouge TDD
    creer_app = None  # type: ignore[assignment]

RACINE = Path(__file__).resolve().parents[1]
AFFAIRE_ID = "cyber-alerte-serveur-rh"
AFFAIRE_JSON = RACINE / "data" / "affaires" / f"{AFFAIRE_ID}.json"

CODES_REDIRECT = (301, 302, 303, 307, 308)
MOTS_PAGE_ERREUR = (
    "erreur",
    "oups",
    "désolé",
    "désolée",
    "introuvable",
    "trouv",
    "invalide",
    "incorrect",
    "impossible",
    "accueil",
    "retour",
    "400",
    "404",
    "500",
)
MOTS_FRANCAIS = (
    "introuvable",
    "retour",
    "accueil",
    "erreur",
    "non autorisée",
    "interdite",
)
PHRASES_ANGLAISES_INTERDITES = (
    "the requested url",
    "not found on the server",
    "method is not allowed",
)


def charger_affaire_json():
    with AFFAIRE_JSON.open(encoding="utf-8") as fichier:
        return json.load(fichier)


def page_texte(reponse):
    """Texte HTML décodé (entités HTML résolues pour comparer au JSON)."""
    return html.unescape(reponse.get_data(as_text=True))


def assert_sans_traceback(reponse):
    texte = reponse.get_data(as_text=True)
    assert "traceback" not in texte.lower(), "page d'erreur brute (traceback visible)"


def assert_page_erreur_propre(reponse, statuts):
    assert reponse.status_code in statuts, (
        f"statut {reponse.status_code} inattendu (attendus : {statuts})"
    )
    assert_sans_traceback(reponse)
    texte = page_texte(reponse).strip()
    assert texte != "", "page d'erreur vide"
    minuscules = texte.lower()
    assert any(mot in minuscules for mot in MOTS_PAGE_ERREUR), (
        "page d'erreur sans message propre en français"
    )


def assert_page_francaise_propre(reponse, statut_attendu):
    """404/405 : statut exact, HTML, 100 % français, sans traceback."""
    assert reponse.status_code == statut_attendu, (
        f"statut {reponse.status_code} inattendu (attendu : {statut_attendu})"
    )
    assert_sans_traceback(reponse)
    assert "text/html" in (reponse.content_type or ""), "la page d'erreur doit être HTML"
    texte = page_texte(reponse).strip()
    assert texte != "", "page d'erreur vide"
    minuscules = texte.lower()
    for phrase in PHRASES_ANGLAISES_INTERDITES:
        assert phrase not in minuscules, (
            f"page non française (contient {phrase!r} de Flask)"
        )
    assert any(mot in minuscules for mot in MOTS_FRANCAIS), (
        "page d'erreur sans mot français (introuvable, retour, accueil, erreur…)"
    )


def assert_redirige_vers_accueil(reponse):
    assert reponse.status_code in CODES_REDIRECT, (
        f"statut {reponse.status_code} inattendu (redirect vers / attendu)"
    )
    location = reponse.headers.get("Location", "")
    assert location, "le redirect doit fournir un header Location"
    assert location.endswith("/"), f"le redirect devrait viser / (reçu : {location!r})"
    return location


def chercher_chemin_complet(affaire, minimum_coups=6):
    """Cherche en profondeur un chemin vers une fin (suite None)."""
    pile = [(affaire["debut"], [])]
    visites = set()
    while pile:
        etape_id, coups = pile.pop()
        if etape_id is None:
            if len(coups) >= minimum_coups:
                return coups
            continue
        if len(coups) > 20:
            continue
        etape = affaire["etapes"][etape_id]
        for choix in etape["choix"]:
            nouveau = coups + [(etape_id, choix["id"])]
            suite = choix.get("suite")
            if suite is None:
                if len(nouveau) >= minimum_coups:
                    return nouveau
            elif (suite, len(nouveau)) not in visites:
                visites.add((suite, len(nouveau)))
                pile.append((suite, nouveau))
    return None


def demarrer_partie(client, affaire_id=AFFAIRE_ID):
    reponse = client.get(f"/partie?affaire={affaire_id}")
    assert reponse.status_code == 200
    return reponse


def poster_coup(client, affaire_id, etape_id, choix_id):
    """POST /jouer brut, sans suivre le redirect (pour tester le PRG)."""
    return client.post(
        "/jouer",
        data={"affaire": affaire_id, "etape": etape_id, "choix": choix_id},
        follow_redirects=False,
    )


def suivre_redirect(client, reponse):
    location = reponse.headers.get("Location", "")
    assert location, "redirect sans header Location"
    return location, client.get(location)


@pytest.fixture()
def app():
    assert creer_app is not None, (
        "factory app.web.creer_app manquante (phase rouge TDD, PRG non implémenté)"
    )
    application = creer_app()
    application.config.update(TESTING=True, SECRET_KEY="secret-test-tdd")
    application.config["PROPAGATE_EXCEPTIONS"] = False
    return application


@pytest.fixture()
def client(app):
    return app.test_client()


# --- étape 1 : POST/Redirect/GET (303) après un choix ---------------------------


def test_post_jouer_valide_renvoie_303_avec_location_vers_etape(client):
    affaire = charger_affaire_json()
    demarrer_partie(client)
    debut = affaire["debut"]
    premier_choix = affaire["etapes"][debut]["choix"][0]

    reponse = poster_coup(client, AFFAIRE_ID, debut, premier_choix["id"])

    assert reponse.status_code in (302, 303), (
        f"POST /jouer valide devrait rediriger (303, 302 toléré), reçu {reponse.status_code}"
    )
    assert reponse.status_code == 303, "PRG : 303 attendu (302 seulement toléré)"
    location = reponse.headers.get("Location", "")
    assert location, "le redirect PRG doit fournir un header Location"
    assert "jouer" in location or "partie" in location, (
        f"la Location devrait viser la page GET de l'étape (/jouer ou /partie), reçu {location!r}"
    )


def test_post_jouer_suivi_du_redirect_affiche_l_etape_suivante(client):
    affaire = charger_affaire_json()
    demarrer_partie(client)
    debut = affaire["debut"]
    premier_choix = affaire["etapes"][debut]["choix"][0]
    suite = premier_choix.get("suite")

    reponse = poster_coup(client, AFFAIRE_ID, debut, premier_choix["id"])

    assert reponse.status_code in (302, 303)
    _location, suivi = suivre_redirect(client, reponse)
    assert suivi.status_code == 200
    assert_sans_traceback(suivi)
    texte = page_texte(suivi)
    if suite is not None:
        texte_suite = affaire["etapes"][suite]["texte"][:30]
        consequence = premier_choix.get("consequence", "")[:30]
        assert texte_suite in texte or consequence in texte or "bilan" in texte.lower()
    else:
        assert "bilan" in texte.lower() or "fin" in texte.lower()


def test_post_dernier_coup_redirige_vers_bilan_puis_affiche_la_fin(client):
    affaire = charger_affaire_json()
    chemin = chercher_chemin_complet(affaire, minimum_coups=6)
    assert chemin is not None, "aucun chemin complet de 6 coups vers une fin"
    demarrer_partie(client)
    for etape_id, choix_id in chemin[:-1]:
        reponse = poster_coup(client, AFFAIRE_ID, etape_id, choix_id)
        assert reponse.status_code in (302, 303)
        _location, suivi = suivre_redirect(client, reponse)
        assert suivi.status_code == 200
    derniere_etape, dernier_choix = chemin[-1]

    reponse = poster_coup(client, AFFAIRE_ID, derniere_etape, dernier_choix)

    assert reponse.status_code in (302, 303), (
        f"le dernier coup devrait rediriger vers /bilan, reçu {reponse.status_code}"
    )
    assert reponse.status_code == 303, "PRG : 303 attendu (302 seulement toléré)"
    location = reponse.headers.get("Location", "")
    assert "bilan" in location, f"le dernier coup devrait viser /bilan, reçu {location!r}"
    _location, suivi = suivre_redirect(client, reponse)
    assert suivi.status_code == 200
    assert_sans_traceback(suivi)
    texte = page_texte(suivi)
    titres_fins = [fin["titre"] for fin in affaire["fins"]]
    assert any(titre in texte for titre in titres_fins), (
        "le bilan suivi du redirect n'affiche aucune fin de l'affaire"
    )


def test_post_jouer_etape_inconnue_reste_400_et_partie_intacte(client):
    affaire = charger_affaire_json()
    demarrer_partie(client)
    debut = affaire["debut"]
    premier_choix = affaire["etapes"][debut]["choix"][0]
    valide = poster_coup(client, AFFAIRE_ID, debut, premier_choix["id"])
    assert valide.status_code in (302, 303)
    suivante = premier_choix.get("suite")
    assert suivante is not None
    choix_suivant = affaire["etapes"][suivante]["choix"][0]["id"]

    reponse = poster_coup(client, AFFAIRE_ID, "etape-inexistante", premier_choix["id"])

    assert_page_erreur_propre(reponse, (400,))
    reprise = poster_coup(client, AFFAIRE_ID, suivante, choix_suivant)
    assert reprise.status_code in (302, 303), "la partie est corrompue après un choix refusé"
    _location, suivi = suivre_redirect(client, reprise)
    assert suivi.status_code == 200
    assert_sans_traceback(suivi)


def test_post_jouer_choix_inconnu_reste_400_et_partie_intacte(client):
    affaire = charger_affaire_json()
    demarrer_partie(client)
    debut = affaire["debut"]
    premier_choix = affaire["etapes"][debut]["choix"][0]
    valide = poster_coup(client, AFFAIRE_ID, debut, premier_choix["id"])
    assert valide.status_code in (302, 303)
    suivante = premier_choix.get("suite")
    assert suivante is not None
    choix_suivant = affaire["etapes"][suivante]["choix"][0]["id"]

    reponse = poster_coup(client, AFFAIRE_ID, suivante, "choix-inexistant")

    assert_page_erreur_propre(reponse, (400,))
    reprise = poster_coup(client, AFFAIRE_ID, suivante, choix_suivant)
    assert reprise.status_code in (302, 303), "la partie est corrompue après un choix refusé"
    _location, suivi = suivre_redirect(client, reprise)
    assert suivi.status_code == 200
    assert_sans_traceback(suivi)


def test_refresh_apres_prg_ne_rejoue_pas_le_coup(client):
    affaire = charger_affaire_json()
    demarrer_partie(client)
    debut = affaire["debut"]
    premier_choix = affaire["etapes"][debut]["choix"][0]

    reponse = poster_coup(client, AFFAIRE_ID, debut, premier_choix["id"])

    assert reponse.status_code in (302, 303)
    location = reponse.headers.get("Location", "")
    assert location
    bilan_avant = client.get("/bilan")
    assert bilan_avant.status_code == 200
    corps_avant = bilan_avant.get_data()
    assert corps_avant.strip() != ""
    rafraichi = client.get(location)
    assert rafraichi.status_code == 200
    bilan_apres = client.get("/bilan")
    assert bilan_apres.status_code == 200
    assert bilan_apres.get_data() == corps_avant, (
        "le refresh de la page GET a rejoué le coup (scores instables)"
    )


# --- étape 2 : GET sans partie → redirect accueil -------------------------------


def test_get_partie_sans_affaire_redirige_vers_accueil(client):
    reponse = client.get("/partie", follow_redirects=False)

    location = assert_redirige_vers_accueil(reponse)
    suivi = client.get(location)
    assert suivi.status_code == 200
    assert "cyber" in suivi.get_data(as_text=True).lower()


def test_get_jouer_sans_partie_redirige_vers_accueil(client):
    reponse = client.get("/jouer", follow_redirects=False)

    location = assert_redirige_vers_accueil(reponse)
    suivi = client.get(location)
    assert suivi.status_code == 200
    assert "cyber" in suivi.get_data(as_text=True).lower()


def test_get_partie_avec_affaire_valide_garde_200(client):
    affaire = charger_affaire_json()

    reponse = client.get(f"/partie?affaire={AFFAIRE_ID}")

    assert reponse.status_code == 200
    assert affaire["contexte"][:40] in page_texte(reponse)


def test_get_partie_sans_param_avec_session_affiche_etape_courante(client):
    affaire = charger_affaire_json()
    demarrer_partie(client)
    debut = affaire["debut"]
    premier_choix = affaire["etapes"][debut]["choix"][0]
    valide = poster_coup(client, AFFAIRE_ID, debut, premier_choix["id"])
    assert valide.status_code in (302, 303)
    suivante = premier_choix.get("suite")
    assert suivante is not None
    texte_suivant = affaire["etapes"][suivante]["texte"][:30]

    reponse = client.get("/partie", follow_redirects=False)
    if reponse.status_code in CODES_REDIRECT:
        # Tolère un redirect interne vers la page GET de l'étape (/jouer).
        _location, reponse = suivre_redirect(client, reponse)

    assert reponse.status_code == 200
    assert texte_suivant in page_texte(reponse)


def test_get_jouer_avec_session_affiche_etape_courante(client):
    affaire = charger_affaire_json()
    demarrer_partie(client)
    debut = affaire["debut"]
    premier_choix = affaire["etapes"][debut]["choix"][0]
    valide = poster_coup(client, AFFAIRE_ID, debut, premier_choix["id"])
    assert valide.status_code in (302, 303)
    suivante = premier_choix.get("suite")
    assert suivante is not None
    texte_suivant = affaire["etapes"][suivante]["texte"][:30]

    reponse = client.get("/jouer")

    assert reponse.status_code == 200
    assert_sans_traceback(reponse)
    assert texte_suivant in page_texte(reponse)


def test_get_bilan_sans_session_redirige_vers_accueil(client):
    """Comportement retenu : redirect vers / (cohérent avec /partie et /jouer)."""
    reponse = client.get("/bilan", follow_redirects=False)

    location = assert_redirige_vers_accueil(reponse)
    suivi = client.get(location)
    assert suivi.status_code == 200
    assert "cyber" in suivi.get_data(as_text=True).lower()


# --- étape 3 : 404/405 en français ----------------------------------------------


def test_404_page_inexistante_propre_et_francaise(client):
    reponse = client.get("/page-inexistante-qui-n-existe-pas")

    assert_page_francaise_propre(reponse, 404)


def test_405_post_accueil_propre_et_francaise(client):
    reponse = client.post("/", data={}, follow_redirects=False)

    assert_page_francaise_propre(reponse, 405)


def test_405_delete_accueil_propre_et_francaise(client):
    reponse = client.delete("/", follow_redirects=False)

    assert_page_francaise_propre(reponse, 405)


# --- étape 4 : debug désactivé par défaut ----------------------------------------


def test_creer_app_debug_desactive_par_defaut(app):
    assert not app.debug, "creer_app() ne doit pas activer le mode debug"
    assert not app.config.get("DEBUG"), "la config DEBUG doit rester fausse"


def test_source_sans_debug_true_inconditionnel():
    sources = []
    for chemin in sorted((RACINE / "app").glob("*.py")):
        sources.append(chemin.read_text(encoding="utf-8"))
    assert sources, "aucun fichier source trouvé dans app/"
    combine = "\n".join(sources)

    assert re.search(r"debug\s*=\s*True", combine) is None, (
        "aucun run(debug=True) ou DEBUG=True inconditionnel dans app/"
    )
    for valeur in re.findall(r"debug\s*=\s*([^\s,)]+)", combine):
        assert valeur == "False" or "environ" in valeur or "getenv" in valeur, (
            f"le mode debug doit rester False par défaut (reçu : {valeur!r})"
        )
