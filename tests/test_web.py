"""Tests web Flask (étape 4, client de test uniquement).

Contrat attendu (note pour ``dev``) :
- Module ``app/web.py`` avec factory ``creer_app()`` qui renvoie l'app Flask.
  Si ``dev`` choisit un autre nom/chemin, adapter ces tests est interdit :
  c'est l'implémentation qui doit fournir ``app.web.creer_app``.
- Routes : ``GET /``, ``GET /partie?affaire=<id>``, ``POST /jouer``
  (formulaire ``affaire, etape, choix``, état en session), ``GET /bilan``.
- Toutes les entrées sont validées (type str, longueur ≤ 200, valeurs parmi
  l'affaire/les étapes/les choix autorisés) ; erreur → 400 (ou 404 pour une
  affaire inconnue via GET) avec page propre, jamais de traceback.
- 404 et 500 via gestionnaires dédiés avec pages propres en français.
- Affaire de référence : ``data/affaires/cyber-alerte-serveur-rh.json``.

Phase rouge TDD normale : ces tests échouent tant que ``app/web.py``
n'est pas implémenté (l'import est dégradé en assertion lisible).
"""

import html
import json
from pathlib import Path

import pytest

try:
    from app.web import creer_app
except ImportError:  # pragma: no cover - phase rouge TDD
    creer_app = None  # type: ignore[assignment]

RACINE = Path(__file__).resolve().parents[1]
AFFAIRE_ID = "cyber-alerte-serveur-rh"
AFFAIRE_JSON = RACINE / "data" / "affaires" / f"{AFFAIRE_ID}.json"

TRAITS = ("analyser", "convaincre", "enqueter", "aider", "proteger")
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


def jouer_coup(client, affaire_id, etape_id, choix_id):
    return client.post(
        "/jouer",
        data={"affaire": affaire_id, "etape": etape_id, "choix": choix_id},
    )


def corps_bilan(client):
    return client.get("/bilan")


def assert_etat_inchange_apres_refus(client, reponse_refus, etape_suivante, choix_suivant):
    """Le refus (400) ne doit pas corrompre la partie : suite rejouable + bilan stable."""
    assert reponse_refus.status_code == 400
    assert_sans_traceback(reponse_refus)
    bilan_avant = corps_bilan(client)
    # La partie doit pouvoir continuer depuis l'étape suivante attendue.
    reprise = jouer_coup(client, AFFAIRE_ID, etape_suivante, choix_suivant)
    assert reprise.status_code == 200, "la partie est corrompue après un choix refusé"
    assert_sans_traceback(reprise)
    bilan_apres = corps_bilan(client)
    if bilan_avant.status_code == 200 and bilan_apres.status_code == 200:
        # Si le bilan est consultable en cours de partie, il reste affiché.
        assert bilan_apres.get_data(as_text=True).strip() != ""


@pytest.fixture()
def app():
    assert creer_app is not None, (
        "factory app.web.creer_app manquante (phase rouge TDD, étape 4 non implémentée)"
    )
    application = creer_app()
    application.config.update(TESTING=True, SECRET_KEY="secret-test-tdd")
    application.config["PROPAGATE_EXCEPTIONS"] = False
    return application


@pytest.fixture()
def client(app):
    return app.test_client()


# --- accueil -----------------------------------------------------------------


def test_accueil_repond_200_et_mentionne_cyber(client):
    reponse = client.get("/")

    assert reponse.status_code == 200
    assert "cyber" in reponse.get_data(as_text=True).lower()


# --- page partie ---------------------------------------------------------------


def test_partie_cyber_affiche_le_contexte(client):
    affaire = charger_affaire_json()

    reponse = client.get(f"/partie?affaire={AFFAIRE_ID}")

    assert reponse.status_code == 200
    assert affaire["contexte"][:40] in page_texte(reponse)


def test_partie_cyber_affiche_le_premier_texte_d_etape(client):
    affaire = charger_affaire_json()
    premier_texte = affaire["etapes"][affaire["debut"]]["texte"]

    reponse = client.get(f"/partie?affaire={AFFAIRE_ID}")

    assert reponse.status_code == 200
    assert premier_texte[:40] in page_texte(reponse)


def test_partie_affaire_inconnue_renvoie_une_page_propre(client):
    reponse = client.get("/partie?affaire=affaire-qui-n-existe-pas")

    assert_page_erreur_propre(reponse, (400, 404))


def test_partie_affaire_trop_longue_renvoie_une_page_propre(client):
    reponse = client.get(f"/partie?affaire={'a' * 250}")

    assert_page_erreur_propre(reponse, (400, 404))


@pytest.mark.parametrize(
    "affaire_invalide",
    [
        "../../secret",
        "cyber;ls",
        "<script>alert(1)</script>",
        "cyber-alerte-serveur-rh!",
    ],
)
def test_partie_affaire_aux_caracteres_interdits_renvoie_une_page_propre(
    client, affaire_invalide
):
    reponse = client.get(f"/partie?affaire={affaire_invalide}")

    assert_page_erreur_propre(reponse, (400, 404))


# --- jouer un coup -------------------------------------------------------------


def test_jouer_coup_valide_mene_a_l_etape_suivante_ou_au_bilan(client):
    affaire = charger_affaire_json()
    demarrer_partie(client)
    debut = affaire["debut"]
    premier_choix = affaire["etapes"][debut]["choix"][0]
    suite = premier_choix.get("suite")

    reponse = jouer_coup(client, AFFAIRE_ID, debut, premier_choix["id"])

    assert reponse.status_code == 200
    assert_sans_traceback(reponse)
    texte = page_texte(reponse)
    if suite is not None:
        texte_suite = affaire["etapes"][suite]["texte"][:30]
        consequence = premier_choix.get("consequence", "")[:30]
        assert texte_suite in texte or consequence in texte or "bilan" in texte.lower()
    else:
        assert "bilan" in texte.lower() or "fin" in texte.lower()


def test_jouer_etape_inconnue_400_et_n_avance_pas(client):
    affaire = charger_affaire_json()
    demarrer_partie(client)
    debut = affaire["debut"]
    premier_choix = affaire["etapes"][debut]["choix"][0]
    assert jouer_coup(client, AFFAIRE_ID, debut, premier_choix["id"]).status_code == 200
    suivante = premier_choix.get("suite")
    choix_suivant = affaire["etapes"][suivante]["choix"][0]["id"]

    reponse = jouer_coup(client, AFFAIRE_ID, "etape-inexistante", premier_choix["id"])

    assert_etat_inchange_apres_refus(client, reponse, suivante, choix_suivant)


def test_jouer_choix_inconnu_400_et_n_avance_pas(client):
    affaire = charger_affaire_json()
    demarrer_partie(client)
    debut = affaire["debut"]
    premier_choix = affaire["etapes"][debut]["choix"][0]
    assert jouer_coup(client, AFFAIRE_ID, debut, premier_choix["id"]).status_code == 200
    suivante = premier_choix.get("suite")
    choix_suivant = affaire["etapes"][suivante]["choix"][0]["id"]

    reponse = jouer_coup(client, AFFAIRE_ID, suivante, "choix-inexistant")

    assert_etat_inchange_apres_refus(client, reponse, suivante, choix_suivant)


@pytest.mark.parametrize("champ_manquant", ["affaire", "etape", "choix"])
def test_jouer_champ_manquant_400_et_n_avance_pas(client, champ_manquant):
    affaire = charger_affaire_json()
    demarrer_partie(client)
    debut = affaire["debut"]
    premier_choix = affaire["etapes"][debut]["choix"][0]
    assert jouer_coup(client, AFFAIRE_ID, debut, premier_choix["id"]).status_code == 200
    suivante = premier_choix.get("suite")
    choix_suivant = affaire["etapes"][suivante]["choix"][0]["id"]
    donnees = {"affaire": AFFAIRE_ID, "etape": suivante, "choix": choix_suivant}
    del donnees[champ_manquant]

    reponse = client.post("/jouer", data=donnees)

    assert_etat_inchange_apres_refus(client, reponse, suivante, choix_suivant)


def test_jouer_champs_trop_longs_400_et_n_avance_pas(client):
    affaire = charger_affaire_json()
    demarrer_partie(client)
    debut = affaire["debut"]
    premier_choix = affaire["etapes"][debut]["choix"][0]
    assert jouer_coup(client, AFFAIRE_ID, debut, premier_choix["id"]).status_code == 200
    suivante = premier_choix.get("suite")
    choix_suivant = affaire["etapes"][suivante]["choix"][0]["id"]

    reponse = jouer_coup(client, "a" * 250, "e" * 250, "c" * 250)

    assert_etat_inchange_apres_refus(client, reponse, suivante, choix_suivant)


@pytest.mark.parametrize(
    ("etape", "choix"),
    [("", "c1"), ("e1", ""), ("", "")],
)
def test_jouer_champs_vides_400_et_n_avance_pas(client, etape, choix):
    affaire = charger_affaire_json()
    demarrer_partie(client)
    debut = affaire["debut"]
    premier_choix = affaire["etapes"][debut]["choix"][0]
    assert jouer_coup(client, AFFAIRE_ID, debut, premier_choix["id"]).status_code == 200
    suivante = premier_choix.get("suite")
    choix_suivant = affaire["etapes"][suivante]["choix"][0]["id"]

    reponse = jouer_coup(client, AFFAIRE_ID, etape, choix)

    assert_etat_inchange_apres_refus(client, reponse, suivante, choix_suivant)


# --- parcours complet + bilan --------------------------------------------------


def jouer_parcours_complet(client):
    affaire = charger_affaire_json()
    chemin = chercher_chemin_complet(affaire, minimum_coups=6)
    assert chemin is not None, "aucun chemin complet de 6 coups vers une fin"
    assert len(chemin) >= 6
    demarrer_partie(client)
    for etape_id, choix_id in chemin:
        reponse = jouer_coup(client, AFFAIRE_ID, etape_id, choix_id)
        assert reponse.status_code == 200
        assert_sans_traceback(reponse)
    return affaire, chemin


def test_parcours_complet_6_coups_le_bilan_affiche_la_fin(client):
    affaire, _chemin = jouer_parcours_complet(client)

    reponse = corps_bilan(client)

    assert reponse.status_code == 200
    texte = page_texte(reponse)
    titres_fins = [fin["titre"] for fin in affaire["fins"]]
    assert any(titre in texte for titre in titres_fins), (
        "le bilan n'affiche aucune fin de l'affaire"
    )


def test_bilan_du_parcours_complet_affiche_les_scores_par_trait(client):
    jouer_parcours_complet(client)

    reponse = corps_bilan(client)

    assert reponse.status_code == 200
    minuscules = page_texte(reponse).lower()
    assert "score" in minuscules
    for trait in TRAITS:
        assert trait in minuscules, f"trait manquant dans le bilan : {trait}"


def test_bilan_du_parcours_complet_cite_au_moins_deux_labels_choisis(client):
    affaire, chemin = jouer_parcours_complet(client)
    labels_choisis = [
        next(
            choix["label"]
            for choix in affaire["etapes"][etape_id]["choix"]
            if choix["id"] == choix_id
        )
        for etape_id, choix_id in chemin
    ]

    reponse = corps_bilan(client)

    assert reponse.status_code == 200
    texte = page_texte(reponse)
    trouves = [label for label in labels_choisis if label in texte]
    assert len(trouves) >= 2, "le bilan cite moins de 2 vrais choix du joueur"


# --- erreurs -------------------------------------------------------------------


def test_page_inexistante_renvoie_404_propre(client):
    reponse = client.get("/page-inexistante-qui-n-existe-pas")

    assert reponse.status_code == 404
    assert_page_erreur_propre(reponse, (404,))


def test_erreur_interne_renvoie_500_page_propre(client, app):
    def _planter():
        raise RuntimeError("panne simulée pour tester la page 500")

    app.add_url_rule(
        "/__provoquer-erreur-test__",
        endpoint="__provoquer-erreur-test__",
        view_func=_planter,
    )

    reponse = client.get("/__provoquer-erreur-test__")

    assert reponse.status_code == 500
    assert_sans_traceback(reponse)
    minuscules = page_texte(reponse).lower()
    assert any(mot in minuscules for mot in ("erreur", "oups", "désolé", "problème"))
