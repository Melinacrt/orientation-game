"""Tests d'immersion salle de crise, etape 1 du plan (TDD, rouge autorise).

Contrat fige par le tester pour dev (ne pas modifier ce fichier) :

- Selecteurs :
  - Tableau de bord : conteneur data-testid=tableau-de-bord exige, en haut
    de chaque page d'etape. Trois indicateurs exiges via
    data-testid=machines-infectees, data-testid=confiance-direction et
    data-testid=temps-restant (entiers affiches dans l'element).
  - Chronometre : data-testid=chrono exige (class=chrono toleree en repli),
    contenant un temps de type MM:SS (regex \\d{1,3}:\\d{2}) ou le mot temps.
- Formule deterministe du tableau de bord (etat -> valeurs) :
  - machines_infectees = min(1 + gravite, 50) (1..50, croit avec gravite).
  - confiance_direction = clamp(80 + 5 * (convaincre + aider) - 10 * gravite,
    0, 100) (80 au depart, bonus convaincre/aider, malus gravite).
  - temps_restant = max(0, 120 - 15 * nb_coups) (minutes, 120 au depart,
    -15 par coup, plancher 0). Distinct du chronometre temps reel.
  - Reference executable : tableau_attendu(etat) ci-dessous. dev doit fournir
    une fonction pure equivalente (ex. app.moteur.tableau_de_bord) et afficher
    ces valeurs exactes.
- Image optionnelle :
  - Schema : etape[image] str <= 200, relatif sous img/, motif
    ^img/[a-z0-9\\-_/]+\\.(png|jpg|jpeg|webp|svg)$, interdit .., / absolu
    initial et http ; etape[image_alt] str non vide exigee si image presente.
  - URL figee cote test : /static/img/<fichier> (prefixe
    URL_IMAGE_ATTENDUE_PREFIX). Conflit connu static/ vs app/static/img/ :
    dev doit servir les PNG a cette URL.
  - Rendu : <img src=.../static/img/<fichier> alt=...> AU-DESSUS du texte
    d'etape (index <img < index texte) ; chemin inexistant -> 200 sans <img>
    casse ni traceback.
- Etapes SANS image : restent valides (charger_affaire ok, optionnel = peut,
  pas doit, 0..7 illustrees autorisees) et s'affichent sans <img> img/.
- Etapes AVEC image (0..7) : chacune respecte le schema (motif, <= 200,
  alt non vide) et s'affiche avec <img> au-dessus du texte.
- Prod reelle (plan §2, levee B1 reviewer) : au moins une etape cyber est
  illustree en prod (visible sans monkeypatch) ; objectif editorial 7/7.
  Les cas AVEC image via monkeypatch completent la couverture (affaire
  minimale en memoire, SANS modifier data/, fallback, position).

Style : fixtures app/client Flask, helpers page_texte / assert_sans_traceback
comme tests/test_web.py.
"""

import copy
import html
import json
import re
from pathlib import Path

import pytest

try:
    from app.web import creer_app
except ImportError:  # pragma: no cover - phase rouge TDD
    creer_app = None  # type: ignore[assignment]

from app import affaires

RACINE = Path(__file__).resolve().parents[1]
AFFAIRE_ID = "cyber-alerte-serveur-rh"
AFFAIRE_JSON = RACINE / "data" / "affaires" / f"{AFFAIRE_ID}.json"
CSS_PATH = RACINE / "static" / "style.css"

URL_IMAGE_ATTENDUE_PREFIX = "/static/img/"
MOTIF_IMAGE = re.compile(r"^img/[a-z0-9\-_/]+\.(png|jpg|jpeg|webp|svg)$")
LONGUEUR_MAX_IMAGE = 200
IMAGE_EXISTANTE_CONNUE = "img/02-alerte-rancon.png"
IMAGE_ALT_EXEMPLE = "Capture d'un ecran affichant une demande de rancon"
IMAGE_INEXISTANTE = "img/inexistante-xyz-123.png"

MACHINES_INITIAL = 1
MACHINES_MAX = 50
CONFIANCE_INITIAL = 80
CONFIANCE_GAIN_PAR_POINT = 5
CONFIANCE_PERTE_PAR_GRAVITE = 10
CONFIANCE_MIN = 0
CONFIANCE_MAX = 100
TEMPS_BUDGET_MINUTES = 120
TEMPS_COUT_PAR_COUP = 15


def tableau_attendu(etat):
    """Formule de reference etat -> valeurs (contrat pour dev)."""
    gravite = etat.get("gravite", 0)
    if not isinstance(gravite, int) or isinstance(gravite, bool) or gravite < 0:
        gravite = 0
    scores = etat.get("scores", {})
    if not isinstance(scores, dict):
        scores = {}
    convaincre = scores.get("convaincre", 0)
    aider = scores.get("aider", 0)
    if not isinstance(convaincre, int) or isinstance(convaincre, bool):
        convaincre = 0
    if not isinstance(aider, int) or isinstance(aider, bool):
        aider = 0
    historique = etat.get("historique", [])
    nb_coups = len(historique) if isinstance(historique, list) else 0
    machines = min(MACHINES_INITIAL + gravite, MACHINES_MAX)
    confiance = CONFIANCE_INITIAL + CONFIANCE_GAIN_PAR_POINT * (convaincre + aider)
    confiance -= CONFIANCE_PERTE_PAR_GRAVITE * gravite
    confiance = max(CONFIANCE_MIN, min(CONFIANCE_MAX, confiance))
    temps = max(0, TEMPS_BUDGET_MINUTES - TEMPS_COUT_PAR_COUP * nb_coups)
    return {
        "machines_infectees": machines,
        "confiance_direction": confiance,
        "temps_restant": temps,
    }


def page_texte(reponse):
    """Texte HTML decode (entites HTML resolues pour comparer au JSON)."""
    return html.unescape(reponse.get_data(as_text=True))


def assert_sans_traceback(reponse):
    texte = reponse.get_data(as_text=True)
    assert "traceback" not in texte.lower(), "page d'erreur brute (traceback visible)"


def assert_redirige_vers_accueil(reponse):
    assert reponse.status_code in (301, 302, 303, 307, 308), (
        f"statut {reponse.status_code} inattendu (redirect vers / attendu)"
    )
    location = reponse.headers.get("Location", "")
    assert location, "le redirect doit fournir un header Location"
    assert location.endswith("/"), f"le redirect devrait viser / (reçu : {location!r})"
    return location


def lire_css():
    return CSS_PATH.read_text(encoding="utf-8")


def charger_affaire_json():
    with AFFAIRE_JSON.open(encoding="utf-8") as fichier:
        return json.load(fichier)


def conteneur_tableau(html_texte):
    return 'data-testid="tableau-de-bord"' in html_texte


def extraire_indicateur(html_texte, testid):
    echappe = re.escape(testid)
    motif = re.compile(rf'data-testid="{echappe}"[^>]*>(.*?)<', re.DOTALL)
    trouve = motif.search(html_texte)
    assert trouve is not None, f"indicateur {testid!r} manquant (contrat data-testid)"
    chiffres = re.search(r"\d+", trouve.group(1))
    assert chiffres is not None, f"indicateur {testid!r} sans valeur entière"
    return int(chiffres.group(0))


def extraire_tableau(html_texte):
    assert conteneur_tableau(html_texte), "conteneur data-testid=tableau-de-bord manquant"
    return {
        "machines_infectees": extraire_indicateur(html_texte, "machines-infectees"),
        "confiance_direction": extraire_indicateur(html_texte, "confiance-direction"),
        "temps_restant": extraire_indicateur(html_texte, "temps-restant"),
    }


def bloc_chrono(html_texte):
    motif_testid = re.compile(r'data-testid="chrono"[^>]*>(.*?)<', re.DOTALL)
    trouve = motif_testid.search(html_texte)
    if trouve is not None:
        return trouve.group(0), trouve.group(1)
    motif_classe = re.compile(r'class="[^"]*\bchrono\b[^"]*"[^>]*>(.*?)<', re.DOTALL)
    trouve = motif_classe.search(html_texte)
    if trouve is not None:
        return trouve.group(0), trouve.group(1)
    return None, None


def images_avec_img(html_texte):
    return re.findall(r'<img[^>]+src="([^"]+)"[^>]*>', html_texte, re.IGNORECASE)


def affaire_dict_de_reference():
    with AFFAIRE_JSON.open(encoding="utf-8") as fichier:
        return json.load(fichier)


def affaire_minimale_dict(image=None, image_alt=None):
    """Affaire minimale valide (3 etapes) avec ou sans image sur e1."""
    etape_e1 = {
        "texte": "Premier incident a traiter en salle de crise.",
        "choix": [
            {
                "id": "c1",
                "label": "Isoler la machine du reseau",
                "traits": {"analyser": 1},
                "gravite": 0,
                "consequence": "La propagation s'arrete.",
                "suite": "e2",
            },
            {
                "id": "c2",
                "label": "Attendre et observer",
                "traits": {},
                "gravite": 2,
                "consequence": "L'attaque s'etend.",
                "suite": "e2",
            },
        ],
    }
    if image is not None:
        etape_e1["image"] = image
        if image_alt is not None:
            etape_e1["image_alt"] = image_alt
    return {
        "id": "test-immersion",
        "metier": "cyber",
        "titre": "Affaire minimale de test immersion",
        "contexte": "Contexte minimal pour tester le schema image.",
        "debut": "e1",
        "etapes": {
            "e1": etape_e1,
            "e2": {
                "texte": "Deuxieme etape de la crise.",
                "choix": [
                    {
                        "id": "c3",
                        "label": "Prevenir la direction",
                        "traits": {"convaincre": 1},
                        "gravite": 0,
                        "consequence": "La direction est informee.",
                        "suite": "e3",
                    }
                ],
            },
            "e3": {
                "texte": "Derniere etape de la crise.",
                "choix": [
                    {
                        "id": "c4",
                        "label": "Restaurer les sauvegardes",
                        "traits": {"proteger": 1},
                        "gravite": 0,
                        "consequence": "Le service repart.",
                        "suite": None,
                    }
                ],
            },
        },
        "fins": [
            {"gravite_max": 1, "titre": "Crise maitrisee", "texte": "Tout va bien."},
            {"gravite_max": 99, "titre": "Crise mal geree", "texte": "Tout va mal."},
        ],
    }


def ecrire_affaire_json(tmp_path, affaire_dict, nom="affaire-test.json"):
    chemin = tmp_path / nom
    chemin.write_text(json.dumps(affaire_dict, ensure_ascii=False), encoding="utf-8")
    return chemin


def patcher_affaire_web(monkeypatch, affaire_dict):
    import app.web as module_web

    copie = copy.deepcopy(affaire_dict)
    monkeypatch.setattr(module_web, "_charger_affaire", lambda _id: copie)


@pytest.fixture()
def app():
    assert creer_app is not None, (
        "factory app.web.creer_app manquante (phase rouge TDD, immersion non implementee)"
    )
    application = creer_app()
    application.config.update(TESTING=True, SECRET_KEY="secret-test-tdd")
    application.config["PROPAGATE_EXCEPTIONS"] = False
    return application


@pytest.fixture()
def client(app):
    return app.test_client()


def test_partie_cyber_repond_200(client):
    reponse = client.get(f"/partie?affaire={AFFAIRE_ID}")

    assert reponse.status_code == 200


def test_css_theme_sombre_fond_noir(client):
    _ = client
    css = lire_css().lower()

    assert "background" in css, "style.css doit definir un fond"
    sombre = re.search(r"--fond\s*:\s*#0|body\s*\{[^}]*background\s*:\s*#0", css)
    assert sombre is not None, "fond sombre attendu (ex. --fond:#0.. ou body{background:#0..})"


def test_css_theme_police_terminal_monospace(client):
    _ = client
    css = lire_css().lower()

    assert any(p in css for p in ("monospace", "jetbrains mono", "consolas", "terminal")), (
        "police terminal/monospace attendue dans style.css"
    )


def test_css_theme_accents_vert_et_rouge(client):
    _ = client
    css = lire_css().lower()

    vert = any(marque in css for marque in ("#00", "--vert", ".vert"))
    rouge = any(marque in css for marque in ("#ff", "--rouge", ".rouge"))
    assert vert, "accent vert attendu dans style.css (ex. #00.., --vert, .vert)"
    assert rouge, "accent rouge attendu dans style.css (ex. #ff.., --rouge, .rouge)"


def test_page_etape_contient_un_chronometre_visible(client):
    reponse = client.get(f"/partie?affaire={AFFAIRE_ID}")

    assert reponse.status_code == 200
    assert_sans_traceback(reponse)
    texte = page_texte(reponse)
    _bloc, contenu = bloc_chrono(texte)
    assert contenu is not None, "chronometre manquant (data-testid=chrono ou class=chrono)"
    temps = re.search(r"\d{1,3}:\d{2}", contenu) is not None
    assert temps or "temps" in contenu.lower(), "le chrono doit afficher un temps (ex. 00:00)"


def _chemin_vers_etape(affaire, cible):
    """Chemin [choix_id] du debut vers cible (BFS), [] si debut, None si injoignable."""
    etapes = affaire.get("etapes", {})
    debut = affaire.get("debut")
    if cible == debut:
        return []
    visites = {debut}
    file = [(debut, [])]
    while file:
        courant, chemin = file.pop(0)
        etape = etapes.get(courant, {})
        for choix in etape.get("choix", []):
            suite = choix.get("suite")
            if suite is None or suite in visites:
                continue
            nouveau = chemin + [choix["id"]]
            if suite == cible:
                return nouveau
            visites.add(suite)
            file.append((suite, nouveau))
    return None


def _naviguer_vers_etape(client, affaire_id, affaire, cible):
    """Redemarre la partie puis joue jusqu'a cible, retourne la reponse GET finale."""
    chemin = _chemin_vers_etape(affaire, cible)
    assert chemin is not None, f"etape {cible!r} injoignable depuis le debut"
    reponse = client.get(f"/partie?affaire={affaire_id}")
    assert reponse.status_code == 200
    courant = affaire["debut"]
    if not chemin:
        return reponse
    for choix_id in chemin:
        suite = next(
            c.get("suite")
            for c in affaire["etapes"][courant]["choix"]
            if c["id"] == choix_id
        )
        poste = client.post(
            "/jouer",
            data={"affaire": affaire_id, "etape": courant, "choix": choix_id},
            follow_redirects=False,
        )
        assert poste.status_code == 303, f"PRG 303 attendu (reçu {poste.status_code})"
        reponse = client.get(poste.headers["Location"])
        assert reponse.status_code == 200
        courant = suite
    assert courant == cible
    return reponse


def test_etapes_cyber_sans_image_restent_valides_et_sans_img(client):
    affaire = affaires.charger_affaire(AFFAIRE_JSON)
    sans_image = [eid for eid, etape in affaire["etapes"].items() if "image" not in etape]
    illustrees = [eid for eid in affaire["etapes"] if eid not in sans_image]
    assert len(illustrees) + len(sans_image) == len(affaire["etapes"])
    assert 0 <= len(illustrees) <= 7, "optionnel = peut, pas doit (0..7 illustrees)"
    for etape_id in sans_image:
        reponse = _naviguer_vers_etape(client, AFFAIRE_ID, affaire, etape_id)
        assert_sans_traceback(reponse)
        texte = page_texte(reponse)
        assert affaire["etapes"][etape_id]["texte"][:30] in texte
        for source in images_avec_img(texte):
            assert "img/" not in source, f"<img> inattendu sur {etape_id} : {source!r}"


def test_etapes_cyber_avec_image_respectent_schema_et_rendu(client):
    affaire = affaires.charger_affaire(AFFAIRE_JSON)
    illustrees = {
        eid: etape for eid, etape in affaire["etapes"].items() if "image" in etape
    }
    assert len(illustrees) <= 7, "7 etapes cyber au maximum"
    for etape_id, etape in illustrees.items():
        image = etape.get("image")
        alt = etape.get("image_alt")
        assert isinstance(image, str) and 0 < len(image) <= LONGUEUR_MAX_IMAGE
        assert MOTIF_IMAGE.match(image), f"etape {etape_id} : image {image!r} hors motif"
        assert ".." not in image and not image.startswith(("/", "http"))
        assert isinstance(alt, str) and alt.strip(), f"etape {etape_id} : alt vide"
        reponse = _naviguer_vers_etape(client, AFFAIRE_ID, affaire, etape_id)
        assert reponse.status_code == 200
        assert_sans_traceback(reponse)
        texte = page_texte(reponse)
        sources = images_avec_img(texte)
        assert sources, f"etape {etape_id} AVEC image : <img> manquant en prod"
        assert any(URL_IMAGE_ATTENDUE_PREFIX in src for src in sources)
        assert alt[:20] in texte, f"etape {etape_id} : <img> sans image_alt"
        index_img = texte.lower().find("<img")
        index_texte = texte.find(etape["texte"][:30])
        assert index_texte != -1, "texte d'etape introuvable dans la page"
        assert 0 <= index_img < index_texte, "<img> doit apparaitre AU-DESSUS du texte"


def test_au_moins_une_etape_cyber_illustree_en_prod(client):
    affaire = affaires.charger_affaire(AFFAIRE_JSON)
    illustrees = [eid for eid, etape in affaire["etapes"].items() if "image" in etape]
    assert illustrees, (
        "plan §2 (levee B1) : au moins une etape cyber illustree attendue "
        f"en prod reelle (0 trouve sur {len(affaire['etapes'])} etapes, "
        "objectif editorial 7/7, visible sans monkeypatch)"
    )
    premiere = illustrees[0]
    reponse = _naviguer_vers_etape(client, AFFAIRE_ID, affaire, premiere)
    assert reponse.status_code == 200
    assert_sans_traceback(reponse)
    assert images_avec_img(page_texte(reponse)), "image prod non visible (<img> manquant)"


def test_charger_affaire_accepte_etape_sans_image(tmp_path):
    chemin = ecrire_affaire_json(tmp_path, affaire_minimale_dict())

    affaire = affaires.charger_affaire(chemin)

    assert affaire["etapes"]["e1"]["texte"] != ""


def test_charger_affaire_accepte_etape_avec_image_valide(tmp_path):
    affaire_dict = affaire_minimale_dict(image=IMAGE_EXISTANTE_CONNUE, image_alt=IMAGE_ALT_EXEMPLE)
    chemin = ecrire_affaire_json(tmp_path, affaire_dict)

    affaire = affaires.charger_affaire(chemin)

    assert affaire["etapes"]["e1"]["image"] == IMAGE_EXISTANTE_CONNUE
    assert affaire["etapes"]["e1"]["image_alt"] == IMAGE_ALT_EXEMPLE


@pytest.mark.parametrize(
    "image_invalide",
    [
        "/img/e1.png",
        "img/../secret.png",
        "img/..\\secret.png",
        "http://exemple.fr/img/e1.png",
        "https://exemple.fr/x.png",
        "img/Mon Image!.png",
        "img/MAJUSCULES.png",
        "img/e1.gif",
        "img/e1",
        "img/e1.bmp",
        123,
        "",
        "img/" + "a" * 200 + ".png",
    ],
)
def test_charger_affaire_refuse_image_invalide(tmp_path, image_invalide):
    affaire_dict = affaire_minimale_dict(image=image_invalide, image_alt=IMAGE_ALT_EXEMPLE)
    chemin = ecrire_affaire_json(tmp_path, affaire_dict)

    with pytest.raises(ValueError):
        affaires.charger_affaire(chemin)


@pytest.mark.parametrize("alt_invalide", ["", "   ", 123, None])
def test_charger_affaire_refuse_image_alt_vide_ou_invalide(tmp_path, alt_invalide):
    affaire_dict = affaire_minimale_dict(image=IMAGE_EXISTANTE_CONNUE, image_alt=alt_invalide)
    chemin = ecrire_affaire_json(tmp_path, affaire_dict)

    with pytest.raises(ValueError):
        affaires.charger_affaire(chemin)


def test_charger_affaire_refuse_image_sans_alt(tmp_path):
    affaire_dict = affaire_minimale_dict(image=IMAGE_EXISTANTE_CONNUE)
    assert "image_alt" not in affaire_dict["etapes"]["e1"]
    chemin = ecrire_affaire_json(tmp_path, affaire_dict)

    with pytest.raises(ValueError):
        affaires.charger_affaire(chemin)


def test_page_sans_image_ne_contient_pas_d_img_casse(client):
    reponse = client.get(f"/partie?affaire={AFFAIRE_ID}")

    assert reponse.status_code == 200
    assert_sans_traceback(reponse)
    texte = page_texte(reponse)
    for source in images_avec_img(texte):
        assert "img/" not in source, f"<img> inattendu sans image : {source!r}"


def test_page_avec_image_affiche_img_au_dessus_du_texte(client, monkeypatch):
    affaire_dict = affaire_dict_de_reference()
    debut = affaire_dict["debut"]
    affaire_dict["etapes"][debut]["image"] = IMAGE_EXISTANTE_CONNUE
    affaire_dict["etapes"][debut]["image_alt"] = IMAGE_ALT_EXEMPLE
    patcher_affaire_web(monkeypatch, affaire_dict)

    reponse = client.get(f"/partie?affaire={AFFAIRE_ID}")

    assert reponse.status_code == 200
    assert_sans_traceback(reponse)
    texte = page_texte(reponse)
    sources = images_avec_img(texte)
    assert sources, "page AVEC image : <img> manquant"
    assert any(URL_IMAGE_ATTENDUE_PREFIX in src for src in sources), (
        f"URL statique attendue {URL_IMAGE_ATTENDUE_PREFIX}<fichier> (reçu : {sources!r})"
    )
    assert "alt=" in texte.lower(), "<img> sans attribut alt"
    assert IMAGE_ALT_EXEMPLE[:20] in texte, "<img> sans image_alt de l'etape"
    index_img = texte.lower().find("<img")
    index_texte = texte.find(affaire_dict["etapes"][debut]["texte"][:30])
    assert index_texte != -1, "texte d'etape introuvable dans la page"
    assert 0 <= index_img < index_texte, "<img> doit apparaitre AU-DESSUS du texte d'etape"


def test_page_image_inexistante_reste_200_sans_img_casse_ni_traceback(client, monkeypatch):
    affaire_dict = affaire_dict_de_reference()
    debut = affaire_dict["debut"]
    affaire_dict["etapes"][debut]["image"] = IMAGE_INEXISTANTE
    affaire_dict["etapes"][debut]["image_alt"] = IMAGE_ALT_EXEMPLE
    patcher_affaire_web(monkeypatch, affaire_dict)

    reponse = client.get(f"/partie?affaire={AFFAIRE_ID}")

    assert reponse.status_code == 200
    assert_sans_traceback(reponse)
    texte = page_texte(reponse)
    assert "inexistante-xyz-123" not in texte, "chemin inexistant : aucun <img> casse attendu"
    assert affaire_dict["etapes"][debut]["texte"][:30] in texte


def test_tableau_de_bord_present_sur_partie_initiale(client):
    reponse = client.get(f"/partie?affaire={AFFAIRE_ID}")

    assert reponse.status_code == 200
    assert_sans_traceback(reponse)
    texte = page_texte(reponse)
    assert conteneur_tableau(texte), "conteneur data-testid=tableau-de-bord manquant"
    valeurs = extraire_tableau(texte)
    assert set(valeurs) == {"machines_infectees", "confiance_direction", "temps_restant"}


def test_tableau_de_bord_present_apres_un_choix_prg_suivi(client):
    affaire = charger_affaire_json()
    assert client.get(f"/partie?affaire={AFFAIRE_ID}").status_code == 200
    debut = affaire["debut"]
    premier_choix = affaire["etapes"][debut]["choix"][0]["id"]

    poste = client.post(
        "/jouer",
        data={"affaire": AFFAIRE_ID, "etape": debut, "choix": premier_choix},
        follow_redirects=False,
    )

    assert poste.status_code == 303, f"PRG 303 attendu (reçu {poste.status_code})"
    location = poste.headers.get("Location", "")
    assert location, "le redirect PRG doit fournir un header Location"
    suivi = client.get(location)

    assert suivi.status_code == 200
    assert_sans_traceback(suivi)
    texte = page_texte(suivi)
    assert conteneur_tableau(texte), "tableau manquant apres POST 303 suivi (GET /jouer)"
    extraire_tableau(texte)


def test_tableau_de_bord_sans_session_redirige_accueil():
    assert creer_app is not None
    application = creer_app()
    application.config.update(TESTING=True, SECRET_KEY="secret-test-tdd")
    application.config["PROPAGATE_EXCEPTIONS"] = False
    frais = application.test_client()

    reponse = frais.get("/jouer", follow_redirects=False)

    location = assert_redirige_vers_accueil(reponse)
    suivi = frais.get(location)
    assert suivi.status_code == 200


def test_tableau_formule_reference_etat_initial():
    etat = {"gravite": 0, "scores": {"convaincre": 0, "aider": 0}, "historique": []}

    assert tableau_attendu(etat) == {
        "machines_infectees": 1,
        "confiance_direction": 80,
        "temps_restant": 120,
    }


def test_tableau_formule_reference_bornes():
    etat_sature = {
        "gravite": 100,
        "scores": {"convaincre": 30, "aider": 30},
        "historique": [{"etape": "e", "choix": "c"}] * 20,
    }

    attendu = tableau_attendu(etat_sature)

    assert attendu["machines_infectees"] == MACHINES_MAX
    assert CONFIANCE_MIN <= attendu["confiance_direction"] <= CONFIANCE_MAX
    assert attendu["temps_restant"] == 0


def test_tableau_valeurs_initiales_suivent_la_formule(client):
    reponse = client.get(f"/partie?affaire={AFFAIRE_ID}")

    assert reponse.status_code == 200
    valeurs = extraire_tableau(page_texte(reponse))
    attendu = tableau_attendu({"gravite": 0, "scores": {}, "historique": []})

    assert valeurs == attendu


def test_tableau_valeurs_apres_un_coup_suivent_la_formule(client):
    affaire = charger_affaire_json()
    assert client.get(f"/partie?affaire={AFFAIRE_ID}").status_code == 200
    debut = affaire["debut"]
    premier_choix = affaire["etapes"][debut]["choix"][0]
    poste = client.post(
        "/jouer",
        data={"affaire": AFFAIRE_ID, "etape": debut, "choix": premier_choix["id"]},
        follow_redirects=False,
    )
    assert poste.status_code == 303
    suivi = client.get(poste.headers["Location"])
    assert suivi.status_code == 200

    valeurs = extraire_tableau(page_texte(suivi))
    etat_apres = {
        "gravite": premier_choix.get("gravite", 0),
        "scores": dict(premier_choix.get("traits", {})),
        "historique": [{"etape": debut, "choix": premier_choix["id"]}],
    }

    assert valeurs == tableau_attendu(etat_apres)


def test_tableau_evolue_apres_le_premier_choix(client):
    avant = client.get(f"/partie?affaire={AFFAIRE_ID}")
    assert avant.status_code == 200
    valeurs_avant = extraire_tableau(page_texte(avant))
    affaire = charger_affaire_json()
    debut = affaire["debut"]
    premier_choix = affaire["etapes"][debut]["choix"][0]["id"]
    poste = client.post(
        "/jouer",
        data={"affaire": AFFAIRE_ID, "etape": debut, "choix": premier_choix},
        follow_redirects=False,
    )
    assert poste.status_code == 303
    apres = client.get(poste.headers["Location"])
    assert apres.status_code == 200
    valeurs_apres = extraire_tableau(page_texte(apres))

    assert valeurs_apres != valeurs_avant, "le tableau doit evoluer apres le 1er choix"


def test_moteur_tableau_de_bord_applique_exactement_la_formule():
    import app.moteur as moteur

    assert hasattr(moteur, "tableau_de_bord"), (
        "fonction pure app.moteur.tableau_de_bord manquante (contrat immersion)"
    )
    cas = [
        {"gravite": 0, "scores": {}, "historique": []},
        {
            "gravite": 2,
            "scores": {"convaincre": 1, "aider": 1},
            "historique": [{"etape": "e1", "choix": "c1"}],
        },
        {
            "gravite": 100,
            "scores": {"convaincre": 30, "aider": 30},
            "historique": [{"etape": "e", "choix": "c"}] * 20,
        },
    ]
    for etat in cas:
        assert moteur.tableau_de_bord({}, etat) == tableau_attendu(etat)
