"""Themes par affaire, retour arriere 303, bilan fiche metier, footer sans « Sans IA ».

Plan : ``docs/plan-theme-retour-bilan-metiers.md``, etape 1 (tester seul, rouge autorise).

Contrats figes PAR CE FICHIER (dev : ne jamais modifier ce fichier) :

- Classes de theme : ``theme-cyber``, ``theme-avocat``, ``theme-neutre``,
  appliquees sur ``<body class="...theme-<nom>...">`` (ou conteneur equivalent
  avec la classe exacte). Partie + bilan = ``theme-<nom>`` de l'affaire ;
  accueil + pages d'erreur = ``theme-neutre`` (clair et sobre), jamais
  ``theme-cyber`` ni ``theme-avocat``.
- ``static/style.css`` definit ``.theme-cyber`` (reprend le style sombre actuel),
  ``.theme-neutre`` (fond clair) et ``.theme-avocat`` (minimal).
- Retour arriere : ``POST /jouer`` avec une etape CONNUE de l'affaire mais
  differente de l'etape courante (retour en arriere) -> 303 vers ``/jouer``
  ou ``/partie`` (jamais ``/bilan``), message exact affiche une fois sur la
  page de l'etape courante : « Tu étais revenu en arrière : voici l'étape
  en cours. » ; la partie reste intacte. Etape INCONNUE -> reste 400 propre.
- ``data/metiers.json`` : dict indexe par code metier (``cyber``, ``avocat``,
  ``medecin`` au minimum), chaque entree avec ``titre`` (str non vide),
  ``quotidien`` (liste d'exactement 3 str non vides), ``qualites`` (liste non
  vide de str), ``formations`` (liste non vide de str), ``jouable`` (booleen ;
  seul l'expert cyber est jouable).
- Bilan : plus aucune section « Métiers proches de ton profil » (ni
  ``class="metiers-proches"``) ; garde profil (``data-testid="profil"``),
  5 barres (``data-trait`` + libelles accentues + mot « score »), citations
  (>= 2 vrais labels) ; ajoute fiche metier (``data-testid="fiche-metier"`` :
  titre du metier joue, quotidien en 3 points, qualites utiles, formations
  possibles) + bloc « Essaie un autre métier » (``data-testid="autre-metier"``)
  listant chaque metier de ``data/metiers.json`` avec badge « Jouable » ou
  « Bientôt ».
- Footer : plus de « Sans IA » (insensible casse/accents) ; garde
  « on te regarde jouer ».

Style : fixtures app/client Flask, helpers page_texte/assert_sans_traceback
comme tests/test_web.py. Phase rouge TDD normale : ces tests echouent tant
que dev n'a pas implemente donnees (etape 2), web/themes/footer (etape 3)
et bilan (etape 4).
"""

import html
import json
import re
import unicodedata
from pathlib import Path

import pytest

try:
    from app.web import creer_app
except ImportError:  # pragma: no cover - phase rouge TDD
    creer_app = None  # type: ignore[assignment]

RACINE = Path(__file__).resolve().parents[1]
AFFAIRE_ID = "cyber-alerte-serveur-rh"
AFFAIRE_JSON = RACINE / "data" / "affaires" / f"{AFFAIRE_ID}.json"
FORMAT_JSON = RACINE / "data" / "format-affaire.json"
METIERS_JSON = RACINE / "data" / "metiers.json"
CSS_PATH = RACINE / "static" / "style.css"

MESSAGE_RETOUR_ARRIERE = "Tu étais revenu en arrière : voici l'étape en cours."
TITRE_AUTRE_METIER = "Essaie un autre métier"

TRAITS = ("analyser", "convaincre", "enqueter", "aider", "proteger")
LIBELLES_ACCENTUES = ("Analyser", "Convaincre", "Enquêter", "Aider", "Protéger")
CODES_METIERS_ATTENDUS = ("cyber", "avocat", "medecin")


def page_texte(reponse):
    """Texte HTML decode (entites HTML resolues pour comparer au JSON)."""
    return html.unescape(reponse.get_data(as_text=True))


def assert_sans_traceback(reponse):
    texte = reponse.get_data(as_text=True)
    assert "traceback" not in texte.lower(), "page d'erreur brute (traceback visible)"


def normaliser(texte):
    """Minuscules sans accents (Enquêter -> enqueter, Bientôt -> bientot)."""
    décomposé = unicodedata.normalize("NFKD", texte.lower())
    return "".join(c for c in décomposé if not unicodedata.combining(c))


def charger_affaire_json():
    with AFFAIRE_JSON.open(encoding="utf-8") as fichier:
        return json.load(fichier)


def charger_metiers():
    assert METIERS_JSON.exists(), "data/metiers.json manquant (contrat bilan fiche métier)"
    with METIERS_JSON.open(encoding="utf-8") as fichier:
        return json.load(fichier)


def charger_profils():
    with (RACINE / "data" / "profils.json").open(encoding="utf-8") as fichier:
        return json.load(fichier)


def lire_css():
    return CSS_PATH.read_text(encoding="utf-8")


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
    """POST /jouer brut, sans suivre le redirect (pour tester le statut)."""
    return client.post(
        "/jouer",
        data={"affaire": affaire_id, "etape": etape_id, "choix": choix_id},
        follow_redirects=False,
    )


def jouer_parcours_complet_prg(client, minimum_coups=6):
    """Joue un parcours complet en suivant chaque redirect PRG 303."""
    affaire = charger_affaire_json()
    chemin = chercher_chemin_complet(affaire, minimum_coups=minimum_coups)
    assert chemin is not None, "aucun chemin complet de 6 coups vers une fin"
    assert len(chemin) >= 6
    demarrer_partie(client)
    for etape_id, choix_id in chemin:
        reponse = poster_coup(client, AFFAIRE_ID, etape_id, choix_id)
        assert reponse.status_code in (302, 303), (
            f"POST /jouer devrait rediriger (PRG), reçu {reponse.status_code}"
        )
        location = reponse.headers.get("Location", "")
        assert location, "le redirect PRG doit fournir un header Location"
        suivi = client.get(location)
        assert suivi.status_code == 200
        assert_sans_traceback(suivi)
    bilan = client.get("/bilan")
    assert bilan.status_code == 200
    assert_sans_traceback(bilan)
    return affaire, chemin, bilan


@pytest.fixture()
def app():
    assert creer_app is not None, (
        "factory app.web.creer_app manquante (phase rouge TDD, étape non implémentée)"
    )
    application = creer_app()
    application.config.update(TESTING=True, SECRET_KEY="secret-test-tdd")
    application.config["PROPAGATE_EXCEPTIONS"] = False
    return application


@pytest.fixture()
def client(app):
    return app.test_client()


# --- 1. themes ---------------------------------------------------------------


def test_donnees_affaire_cyber_a_un_theme_cyber():
    affaire = charger_affaire_json()

    assert affaire.get("theme") == "cyber", (
        "l'affaire cyber doit déclarer theme == 'cyber' (cohérent avec metier)"
    )


def test_format_affaire_documente_le_champ_theme():
    with FORMAT_JSON.open(encoding="utf-8") as fichier:
        format_affaire = json.load(fichier)

    assert "theme" in format_affaire, (
        "data/format-affaire.json doit documenter le champ theme (exemple)"
    )


def test_partie_cyber_applique_le_theme_cyber(client):
    reponse = client.get(f"/partie?affaire={AFFAIRE_ID}")

    assert reponse.status_code == 200
    assert_sans_traceback(reponse)
    brut = reponse.get_data(as_text=True)
    assert re.search(r'class="[^"]*theme-cyber[^"]*"', brut) is not None, (
        "la page partie cyber doit appliquer theme-cyber (ex. <body class='...theme-cyber...'>)"
    )


def test_bilan_applique_le_theme_cyber(client):
    _affaire, _chemin, bilan = jouer_parcours_complet_prg(client)

    brut = bilan.get_data(as_text=True)
    assert re.search(r'class="[^"]*theme-cyber[^"]*"', brut) is not None, (
        "le bilan de l'affaire cyber doit appliquer theme-cyber"
    )


def test_accueil_applique_le_theme_neutre_sans_theme_metier(client):
    reponse = client.get("/")

    assert reponse.status_code == 200
    brut = reponse.get_data(as_text=True)
    assert re.search(r'class="[^"]*theme-neutre[^"]*"', brut) is not None, (
        "l'accueil doit appliquer un thème neutre (classe theme-neutre)"
    )
    assert "theme-cyber" not in brut, "l'accueil ne doit pas porter theme-cyber"
    assert "theme-avocat" not in brut, "l'accueil ne doit pas porter theme-avocat"


def test_page_404_applique_le_theme_neutre_sans_theme_metier(client):
    reponse = client.get("/page-inexistante-theme-neutre-xyz")

    assert reponse.status_code == 404
    assert_sans_traceback(reponse)
    brut = reponse.get_data(as_text=True)
    assert re.search(r'class="[^"]*theme-neutre[^"]*"', brut) is not None, (
        "la page 404 doit appliquer le thème neutre (classe theme-neutre)"
    )
    assert "theme-cyber" not in brut, "la 404 ne doit pas porter theme-cyber"
    assert "theme-avocat" not in brut, "la 404 ne doit pas porter theme-avocat"


def test_css_definit_theme_cyber_sombre_theme_neutre_clair_et_theme_avocat(client):
    _ = client
    css = lire_css()

    for theme in (".theme-cyber", ".theme-neutre", ".theme-avocat"):
        assert theme in css, f"sélecteur {theme} manquant dans static/style.css"
    bloc_cyber = re.search(r"\.theme-cyber[^{]*\{[^}]*\}", css, re.DOTALL)
    assert bloc_cyber is not None and "background" in bloc_cyber.group(0), (
        ".theme-cyber doit définir un fond (reprend le style sombre actuel)"
    )
    bloc_neutre = re.search(r"\.theme-neutre[^{]*\{[^}]*\}", css, re.DOTALL)
    assert bloc_neutre is not None and "background" in bloc_neutre.group(0), (
        ".theme-neutre doit définir un fond clair et sobre"
    )
    marqueurs_clairs = ("#f", "#e", "white", "ivory", "beige", "snow", "seashell")
    assert any(marque in bloc_neutre.group(0).lower() for marque in marqueurs_clairs), (
        ".theme-neutre doit utiliser un fond clair (blanc, #faf..., #eee...)"
    )


# --- 2. retour arriere 303 ---------------------------------------------------


def test_post_jouer_ancienne_etape_connue_renvoie_303_pas_400(client):
    affaire = charger_affaire_json()
    demarrer_partie(client)
    debut = affaire["debut"]
    premier_choix = affaire["etapes"][debut]["choix"][0]
    valide = poster_coup(client, AFFAIRE_ID, debut, premier_choix["id"])
    assert valide.status_code in (302, 303)
    assert valide.status_code == 303, "PRG : 303 attendu"

    reponse = poster_coup(client, AFFAIRE_ID, debut, premier_choix["id"])

    assert reponse.status_code == 303, (
        f"retour arrière (étape connue non courante) : 303 attendu, reçu {reponse.status_code}"
    )
    location = reponse.headers.get("Location", "")
    assert location, "le redirect retour arrière doit fournir un header Location"
    assert "jouer" in location or "partie" in location, (
        f"le redirect doit viser l'étape en cours (/jouer ou /partie), reçu {location!r}"
    )
    assert "bilan" not in location, (
        f"le retour arrière ne doit pas viser /bilan (reçu {location!r})"
    )


def test_retour_arriere_affiche_etape_courante_et_message_exact(client):
    affaire = charger_affaire_json()
    demarrer_partie(client)
    debut = affaire["debut"]
    premier_choix = affaire["etapes"][debut]["choix"][0]
    valide = poster_coup(client, AFFAIRE_ID, debut, premier_choix["id"])
    assert valide.status_code in (302, 303)
    suivante = premier_choix.get("suite")
    assert suivante is not None
    texte_courant = affaire["etapes"][suivante]["texte"][:30]

    retour = poster_coup(client, AFFAIRE_ID, debut, premier_choix["id"])

    assert retour.status_code == 303
    suivi = client.get(retour.headers["Location"])
    assert suivi.status_code == 200
    assert_sans_traceback(suivi)
    texte = page_texte(suivi)
    assert texte_courant in texte, "le redirect doit afficher l'étape en cours réelle"
    assert MESSAGE_RETOUR_ARRIERE in texte, (
        f"message exact attendu : {MESSAGE_RETOUR_ARRIERE!r}"
    )


def test_retour_arriere_ne_corrompt_pas_la_partie(client):
    affaire = charger_affaire_json()
    demarrer_partie(client)
    debut = affaire["debut"]
    premier_choix = affaire["etapes"][debut]["choix"][0]
    assert poster_coup(client, AFFAIRE_ID, debut, premier_choix["id"]).status_code == 303
    suivante = premier_choix.get("suite")
    assert suivante is not None
    choix_suivant = affaire["etapes"][suivante]["choix"][0]["id"]

    retour = poster_coup(client, AFFAIRE_ID, debut, premier_choix["id"])
    assert retour.status_code == 303

    reprise = poster_coup(client, AFFAIRE_ID, suivante, choix_suivant)
    assert reprise.status_code == 303, "la partie est corrompue après un retour arrière"
    suivi = client.get(reprise.headers["Location"])
    assert suivi.status_code == 200
    assert_sans_traceback(suivi)
    bilan = client.get("/bilan")
    assert bilan.status_code == 200
    assert_sans_traceback(bilan)
    assert bilan.get_data(as_text=True).strip() != ""


def test_post_jouer_etape_inconnue_reste_400(client):
    """Distinction figée : étape INEXISTANTE -> 400, étape connue non courante -> 303."""
    affaire = charger_affaire_json()
    demarrer_partie(client)
    debut = affaire["debut"]
    premier_choix = affaire["etapes"][debut]["choix"][0]
    assert poster_coup(client, AFFAIRE_ID, debut, premier_choix["id"]).status_code == 303

    reponse = poster_coup(client, AFFAIRE_ID, "etape-inexistante", premier_choix["id"])

    assert reponse.status_code == 400, (
        f"étape inconnue de l'affaire : 400 attendu, reçu {reponse.status_code}"
    )
    assert_sans_traceback(reponse)
    assert page_texte(reponse).strip() != ""


# --- 3. bilan sans metiers proches + fiche metier ----------------------------


def test_bilan_ne_contient_plus_les_metiers_proches(client):
    _affaire, _chemin, bilan = jouer_parcours_complet_prg(client)
    texte = page_texte(bilan)
    brut = bilan.get_data(as_text=True)

    assert "Métiers proches de ton profil" not in texte, (
        "la section « Métiers proches de ton profil » doit être supprimée du bilan"
    )
    assert 'class="metiers-proches"' not in brut and "metiers-proches" not in brut, (
        "le bilan ne doit plus contenir la liste metiers-proches"
    )


def test_bilan_garde_le_profil_titre_et_texte(client):
    _affaire, _chemin, bilan = jouer_parcours_complet_prg(client)
    texte = page_texte(bilan)
    brut = bilan.get_data(as_text=True)
    profils = charger_profils()

    assert 'data-testid="profil"' in brut or "data-testid='profil'" in brut, (
        "la carte profil (data-testid=profil) doit être gardée"
    )
    correspondances = [p for p in profils if p.get("titre") and p["titre"] in texte]
    assert correspondances, "aucun titre de profil de data/profils.json dans le bilan"
    profil = correspondances[0]
    assert profil.get("texte") and profil["texte"][:40] in texte, (
        "le texte du profil affiché est absent du bilan"
    )


def test_bilan_garde_les_cinq_barres_libelles_et_mot_score(client):
    _affaire, _chemin, bilan = jouer_parcours_complet_prg(client)
    texte = page_texte(bilan)
    brut = bilan.get_data(as_text=True).lower()

    for trait in TRAITS:
        assert f'data-trait="{trait}"' in brut or f"data-trait='{trait}'" in brut, (
            f"barre manquante pour le trait : {trait}"
        )
    for libellé in LIBELLES_ACCENTUES:
        assert libellé in texte, f"libellé accentué manquant dans le bilan : {libellé}"
    assert "score" in normaliser(texte), "le mot « score » doit rester présent"


def test_bilan_cite_au_moins_deux_vrais_choix(client):
    affaire, chemin, bilan = jouer_parcours_complet_prg(client)
    labels_choisis = [
        next(
            choix["label"]
            for choix in affaire["etapes"][etape_id]["choix"]
            if choix["id"] == choix_id
        )
        for etape_id, choix_id in chemin
    ]
    texte = page_texte(bilan)

    trouves = [label for label in labels_choisis if label in texte]
    assert len(trouves) >= 2, "le bilan cite moins de 2 vrais choix du joueur"


def test_metiers_json_schema_exact_titre_quotidien_qualites_formations_jouable():
    metiers = charger_metiers()

    assert isinstance(metiers, dict), "data/metiers.json doit être un dict par code métier"
    for code in CODES_METIERS_ATTENDUS:
        assert code in metiers, f"entrée manquante dans data/metiers.json : {code!r}"
    for code, entree in metiers.items():
        assert isinstance(entree, dict), f"métier {code!r} : entrée dict attendue"
        assert isinstance(entree.get("titre"), str) and entree["titre"].strip() != "", (
            f"métier {code!r} : titre non vide attendu"
        )
        quotidien = entree.get("quotidien")
        assert isinstance(quotidien, list) and len(quotidien) == 3, (
            f"métier {code!r} : quotidien = exactement 3 points attendus"
        )
        for point in quotidien:
            assert isinstance(point, str) and point.strip() != "", (
                f"métier {code!r} : chaque point du quotidien doit être non vide"
            )
        for cle in ("qualites", "formations"):
            valeurs = entree.get(cle)
            assert isinstance(valeurs, list) and valeurs, (
                f"métier {code!r} : {cle} = liste non vide attendue"
            )
            for valeur in valeurs:
                assert isinstance(valeur, str) and valeur.strip() != "", (
                    f"métier {code!r} : {cle} ne doit contenir que des chaînes non vides"
                )
        assert isinstance(entree.get("jouable"), bool), (
            f"métier {code!r} : jouable (booléen) manquant"
        )
    assert metiers["cyber"]["jouable"] is True, "l'expert cyber doit être jouable"
    assert metiers["avocat"]["jouable"] is False, "l'avocat doit être « Bientôt »"
    assert metiers["medecin"]["jouable"] is False, "le médecin doit être « Bientôt »"


def test_bilan_fiche_metier_du_metier_joue(client):
    _affaire, _chemin, bilan = jouer_parcours_complet_prg(client)
    metiers = charger_metiers()
    fiche = metiers["cyber"]
    texte = page_texte(bilan)
    brut = bilan.get_data(as_text=True)

    assert 'data-testid="fiche-metier"' in brut or "data-testid='fiche-metier'" in brut, (
        "la fiche métier (data-testid=fiche-metier) est absente du bilan"
    )
    assert fiche["titre"] in texte, "le titre du métier joué est absent de la fiche"
    for point in fiche["quotidien"]:
        assert point in texte, f"point du quotidien absent de la fiche : {point[:30]!r}"
    assert any(q in texte for q in fiche["qualites"]), (
        "aucune qualité utile de la fiche dans le bilan"
    )
    assert any(f in texte for f in fiche["formations"]), (
        "aucune formation possible de la fiche dans le bilan"
    )


def test_bilan_bloc_essaie_un_autre_metier_avec_badges(client):
    _affaire, _chemin, bilan = jouer_parcours_complet_prg(client)
    metiers = charger_metiers()
    texte = page_texte(bilan)
    brut = bilan.get_data(as_text=True)
    normalisé = normaliser(texte)

    assert TITRE_AUTRE_METIER in texte, (
        f"bloc {TITRE_AUTRE_METIER!r} absent du bilan"
    )
    assert 'data-testid="autre-metier"' in brut or "data-testid='autre-metier'" in brut, (
        "le bloc autre métier (data-testid=autre-metier) est absent"
    )
    for _code, entree in metiers.items():
        assert entree["titre"] in texte, (
            f"métier {entree['titre']!r} absent du bloc « {TITRE_AUTRE_METIER} »"
        )
    assert "jouable" in normalisé, "badge « Jouable » absent du bilan"
    assert "bientot" in normalisé, "badge « Bientôt » absent du bilan"
    assert "badge-jouable" in brut, "classe badge-jouable absente du bilan"
    assert "badge-bientot" in brut, "classe badge-bientot absente du bilan"


# --- 4. footer -----------------------------------------------------------------


def test_footer_accueil_sans_sans_ia_et_garde_accroche(client):
    reponse = client.get("/")

    assert reponse.status_code == 200
    compact = normaliser(page_texte(reponse)).replace(" ", "").replace("-", "")
    assert "sansia" not in compact, "le footer ne doit plus contenir « Sans IA »"
    assert "on te regarde jouer" in normaliser(page_texte(reponse)), (
        "le footer doit garder « on te regarde jouer »"
    )


def test_footer_partie_et_bilan_sans_sans_ia(client):
    partie = client.get(f"/partie?affaire={AFFAIRE_ID}")
    assert partie.status_code == 200
    compact_partie = normaliser(page_texte(partie)).replace(" ", "").replace("-", "")
    assert "sansia" not in compact_partie, "le footer partie contient encore « Sans IA »"

    _affaire, _chemin, bilan = jouer_parcours_complet_prg(client)
    compact_bilan = normaliser(page_texte(bilan)).replace(" ", "").replace("-", "")
    assert "sansia" not in compact_bilan, "le footer bilan contient encore « Sans IA »"
