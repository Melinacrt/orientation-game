"""Bilan enrichi (plan ``docs/plan-bilan.md``, étape 1 — TDD, rouge attendu).

Schéma exact des profils figé PAR CE FICHIER (tester seul) :
- ``data/profils.json`` : liste d'au moins 6 dicts, chacun avec
  ``id`` (str non vide), ``titre`` (str non vide), ``texte`` (str non vide),
  ``traits_dominants`` (liste non vide ⊆ {analyser, convaincre, enqueter,
  aider, proteger}) et une clé métiers ``metiers`` ou ``metiers_proches``
  (liste de 3 à 4 entrées).
- Chaque entrée métier est un dict avec un nom réel (``nom``), une courte
  phrase de lien (``lien`` ou ``pourquoi``, non vide) et un statut jouable
  (``jouable`` booléen) : seul « expert cyber » (seule affaire existante)
  est jouable, les autres sont « Bientôt ».

Ruptures volontaires portées par les tests (dev : ne jamais les modifier) :
- l'ancien contrat « métiers ⊆ {expert cyber, avocat, médecin} » (listes de
  chaînes) est remplacé par le contrat enrichi ci-dessus (voir aussi
  ``test_contenu_cyber.py`` et ``test_moteur.py`` évolués par tester) ;
- le repérage des traits utilise ``data-trait`` non accentué + normalisation
  ``unicodedata`` (les libellés visibles sont accentués : Enquêter…).

Phase rouge TDD normale : ces tests échouent tant que ``dev`` n'a pas fourni
les données (étape 2), le moteur/web (étape 3) et le template (étape 4).
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
PROFILS_JSON = RACINE / "data" / "profils.json"
METIERS_JSON = RACINE / "data" / "metiers.json"
TITRE_AUTRE_METIER = "Essaie un autre métier"

TRAITS = ("analyser", "convaincre", "enqueter", "aider", "proteger")
LIBELLES_ACCENTUES = ("Analyser", "Convaincre", "Enquêter", "Aider", "Protéger")


def page_texte(reponse):
    """Texte HTML décodé (entités HTML résolues pour comparer au JSON)."""
    return html.unescape(reponse.get_data(as_text=True))


def assert_sans_traceback(reponse):
    texte = reponse.get_data(as_text=True)
    assert "traceback" not in texte.lower(), "page d'erreur brute (traceback visible)"


def normaliser(texte):
    """Minuscules sans accents (Enquêter → enqueter, Bientôt → bientot)."""
    décomposé = unicodedata.normalize("NFKD", texte.lower())
    return "".join(c for c in décomposé if not unicodedata.combining(c))


def charger_affaire_json():
    with AFFAIRE_JSON.open(encoding="utf-8") as fichier:
        return json.load(fichier)


def charger_profils():
    with PROFILS_JSON.open(encoding="utf-8") as fichier:
        return json.load(fichier)


def charger_metiers():
    with METIERS_JSON.open(encoding="utf-8") as fichier:
        return json.load(fichier)


def liste_metiers(profil):
    """Entrées métiers enrichies (clé ``metiers`` ou ``metiers_proches``)."""
    metiers = profil.get("metiers", profil.get("metiers_proches"))
    assert isinstance(metiers, list), "chaque profil doit avoir une liste de métiers"
    return metiers


def nom_metier(entree):
    return entree.get("nom", entree.get("nom_metier", entree.get("titre", "")))


def lien_metier(entree):
    return entree.get("lien", entree.get("pourquoi", entree.get("lien_profil", "")))


def jouable_metier(entree):
    if "jouable" in entree:
        return entree["jouable"]
    return entree.get("disponible")


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


def poster_coup_prg(client, affaire_id, etape_id, choix_id):
    """POST /jouer brut, sans suivre le redirect (pour vérifier le PRG 303)."""
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
        reponse = poster_coup_prg(client, AFFAIRE_ID, etape_id, choix_id)
        assert reponse.status_code in (302, 303), (
            f"POST /jouer devrait rediriger (PRG), reçu {reponse.status_code}"
        )
        assert reponse.status_code == 303, "PRG : 303 attendu (302 seulement toléré)"
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
        "factory app.web.creer_app manquante (phase rouge TDD, étape 4 non implémentée)"
    )
    application = creer_app()
    application.config.update(TESTING=True, SECRET_KEY="secret-test-tdd")
    application.config["PROPAGATE_EXCEPTIONS"] = False
    return application


@pytest.fixture()
def client(app):
    return app.test_client()


# --- 1. profil en haut ---------------------------------------------------------


def test_bilan_apres_parcours_complet_prg_repond_200(client):
    _affaire, _chemin, bilan = jouer_parcours_complet_prg(client)

    assert bilan.status_code == 200
    assert_sans_traceback(bilan)
    assert page_texte(bilan).strip() != ""


def test_bilan_profil_affiche_avant_scores_et_fin(client):
    _affaire, _chemin, bilan = jouer_parcours_complet_prg(client)
    brut = bilan.get_data(as_text=True).lower()

    marqueurs_profil = ("carte-profil", 'data-testid="profil"', "data-testid='profil'")
    positions_profil = [brut.find(m) for m in marqueurs_profil if m in brut]
    assert positions_profil, "carte profil absente (section.carte-profil ou data-testid=profil)"
    index_profil = min(positions_profil)
    index_scores = brut.find("data-trait")
    if index_scores == -1:
        index_scores = brut.find("scores")
    index_fin = brut.find("fin :")
    if index_fin == -1:
        index_fin = brut.find("fin")
    assert index_scores != -1, "section scores introuvable dans le bilan"
    assert index_fin != -1, "section fin introuvable dans le bilan"
    assert index_profil < index_scores, "le profil doit apparaître AVANT les scores"
    assert index_profil < index_fin, "le profil doit apparaître AVANT la fin"


def test_bilan_profil_contient_titre_texte_et_metiers_proches(client):
    """Rupture volontaire (plan theme-retour-bilan-metiers point 3) :
    le bilan ne calcule plus les « métiers proches » depuis
    data/profils.json ; le profil (titre + texte) reste affiché et le bilan
    montre désormais la fiche métier du métier joué (data-testid=fiche-metier,
    schéma figé dans tests/test_themes_retour_bilan.py) + le bloc
    « Essaie un autre métier » (nom conservé pour traçabilité).
    """
    _affaire, _chemin, bilan = jouer_parcours_complet_prg(client)
    texte = page_texte(bilan)
    brut = bilan.get_data(as_text=True)
    profils = charger_profils()

    correspondances = [p for p in profils if p.get("titre") and p["titre"] in texte]
    assert correspondances, "aucun titre de profil de data/profils.json dans le bilan"
    profil = correspondances[0]
    assert profil.get("texte") and profil["texte"][:40] in texte, (
        "le texte du profil affiché est absent du bilan"
    )
    metiers = charger_metiers()
    fiche = metiers["cyber"]
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
    assert TITRE_AUTRE_METIER in texte, (
        f"bloc {TITRE_AUTRE_METIER!r} absent du bilan"
    )
    assert 'data-testid="autre-metier"' in brut or "data-testid='autre-metier'" in brut, (
        "le bloc autre métier (data-testid=autre-metier) est absent"
    )


# --- 2. profils réels ----------------------------------------------------------


def test_profils_json_contient_au_moins_six_profils():
    profils = charger_profils()

    assert isinstance(profils, list)
    assert len(profils) >= 6, f"attendus ≥ 6 profils, reçus {len(profils)}"


def test_profils_schema_exact_id_titre_texte_dominants_et_3_a_4_metiers():
    profils = charger_profils()

    for profil in profils:
        assert isinstance(profil, dict)
        assert isinstance(profil.get("id"), str) and profil["id"].strip() != ""
        assert isinstance(profil.get("titre"), str) and profil["titre"].strip() != ""
        assert isinstance(profil.get("texte"), str) and len(profil["texte"].strip()) >= 20
        dominants = profil.get("traits_dominants")
        assert isinstance(dominants, list) and dominants, "traits_dominants vide"
        assert set(dominants) <= set(TRAITS), f"traits inconnus : {dominants}"
        metiers = liste_metiers(profil)
        assert 3 <= len(metiers) <= 4, (
            f"profil {profil.get('id')!r} : attendus 3-4 métiers, reçus {len(metiers)}"
        )


def test_profils_chaque_metier_a_nom_reel_phrase_de_lien_et_statut_jouable():
    profils = charger_profils()

    for profil in profils:
        for entree in liste_metiers(profil):
            assert isinstance(entree, dict), "chaque métier doit être un objet enrichi"
            nom = nom_metier(entree)
            assert isinstance(nom, str) and nom.strip() != "", "nom de métier réel manquant"
            lien = lien_metier(entree)
            assert isinstance(lien, str) and len(lien.strip()) >= 10, (
                f"métier {nom!r} : phrase de lien manquante ou trop courte"
            )
            assert isinstance(jouable_metier(entree), bool), (
                f"métier {nom!r} : statut jouable (booléen) manquant"
            )


# --- 3. badges jouable / bientôt ------------------------------------------------


def test_bilan_badges_jouable_pour_expert_cyber_et_bientot_pour_les_autres(client):
    _affaire, _chemin, bilan = jouer_parcours_complet_prg(client)
    normalisé = normaliser(page_texte(bilan))

    assert "jouable" in normalisé, "badge « Jouable » absent du bilan"
    assert "bientot" in normalisé, "badge « Bientôt » absent du bilan"
    assert "expert cyber" in normalisé, "le métier jouable (expert cyber) est absent du bilan"


# --- 4. scores significatifs ----------------------------------------------------


def test_cyber_chaque_choix_rapporte_1_a_2_traits_significatifs():
    affaire = charger_affaire_json()

    for etape_id, etape in affaire["etapes"].items():
        for choix in etape["choix"]:
            traits = choix.get("traits", {})
            assert isinstance(traits, dict), f"{etape_id}/{choix['id']} : traits non dict"
            assert 1 <= len(traits) <= 2, (
                f"{etape_id}/{choix['id']} : attendus 1-2 traits, reçus {len(traits)}"
            )
            assert set(traits) <= set(TRAITS), (
                f"{etape_id}/{choix['id']} : traits inconnus {sorted(traits)}"
            )
            for trait, valeur in traits.items():
                assert valeur in (1, 2, 3), (
                    f"{etape_id}/{choix['id']} : {trait}={valeur!r}, attendu 1-3"
                )


# --- 5. barres + dominants ------------------------------------------------------


def test_bilan_cinq_barres_de_score_avec_data_trait(client):
    _affaire, _chemin, bilan = jouer_parcours_complet_prg(client)
    brut = bilan.get_data(as_text=True).lower()

    nb_progress = len(re.findall(r"<progress\b", brut))
    nb_role = brut.count('role="progressbar"') + brut.count("role='progressbar'")
    assert nb_progress + nb_role >= 5, "attendues 5 barres (progress ou role=progressbar)"
    for trait in TRAITS:
        assert f'data-trait="{trait}"' in brut or f"data-trait='{trait}'" in brut, (
            f"barre manquante pour le trait : {trait}"
        )


def test_bilan_libelles_accentues_visibles_et_mot_score(client):
    _affaire, _chemin, bilan = jouer_parcours_complet_prg(client)
    texte = page_texte(bilan)

    for libellé in LIBELLES_ACCENTUES:
        assert libellé in texte, f"libellé accentué manquant dans le bilan : {libellé}"
    assert "score" in normaliser(texte), "le mot « score » doit rester présent"


def test_bilan_top_2_traits_dominants_mis_en_evidence(client):
    _affaire, _chemin, bilan = jouer_parcours_complet_prg(client)
    brut = bilan.get_data(as_text=True)

    balises = re.findall(
        r"<[^>]+(?:data-dominant=[\"']true[\"']|class=[\"'][^\"']*dominant[^\"']*[\"'])[^>]*>",
        brut,
        flags=re.IGNORECASE,
    )
    assert len(balises) == 2, (
        f"attendus exactement 2 traits dominants en évidence, trouvés {len(balises)}"
    )


# --- 6. jauge gravité -----------------------------------------------------------


def test_bilan_jauge_gravite_lisible_sans_texte_brut(client):
    _affaire, _chemin, bilan = jouer_parcours_complet_prg(client)
    brut = bilan.get_data(as_text=True)
    normalisé = normaliser(brut)

    assert "gravite finale" not in normalisé, "texte brut « Gravité finale : N » à supprimer"
    assert re.search(r"gravite\s+finale\s*:\s*\d", normalisé) is None, (
        "texte brut « Gravité finale : N » à supprimer"
    )
    bas = brut.lower()
    assert "<meter" in bas or "role=" in bas and ("meter" in bas or "gauge" in bas), (
        "jauge de gravité absente (<meter> ou role=meter/gauge)"
    )
    assert any(mot in normalisé for mot in ("impact", "maitris", "limit", "elev", "gravit")), (
        "libellé lisible de gravité absent (ex. Impact maîtrisé/limité/élevé)"
    )
    assert "aria-valuenow" in normalisé or "data-gravite" in normalisé, (
        "valeur de gravité inaccessible (aria-valuenow ou data-gravite attendu)"
    )


# --- 7. séparateur + non-régression ---------------------------------------------


def test_bilan_sections_separees_par_un_separateur_visible(client):
    _affaire, _chemin, bilan = jouer_parcours_complet_prg(client)
    brut = bilan.get_data(as_text=True)

    assert "<hr" in brut.lower() or "separateur" in normaliser(brut), (
        "séparateur visible attendu entre les sections (<hr> ou .separateur)"
    )


def test_bilan_non_regression_prg_et_bilan_sans_session_redirige(client):
    affaire = charger_affaire_json()
    demarrer_partie(client)
    debut = affaire["debut"]
    premier_choix = affaire["etapes"][debut]["choix"][0]["id"]

    reponse = poster_coup_prg(client, AFFAIRE_ID, debut, premier_choix)

    assert reponse.status_code == 303, "PRG : POST /jouer valide doit répondre 303"
    assert reponse.headers.get("Location", ""), "le redirect PRG doit viser une page GET"

    vierge = creer_app()
    vierge.config.update(TESTING=True, SECRET_KEY="secret-test-tdd")
    sans_session = vierge.test_client().get("/bilan", follow_redirects=False)

    assert sans_session.status_code in (301, 302, 303, 307, 308), (
        "GET /bilan sans session doit rediriger vers l'accueil"
    )
    assert sans_session.headers.get("Location", "").endswith("/"), (
        "GET /bilan sans session doit viser /"
    )


def test_bilan_404_et_405_restent_propres_et_francaises(client):
    inconnue = client.get("/page-inexistante-bilan-enrichi")

    assert inconnue.status_code == 404
    assert_sans_traceback(inconnue)
    assert "text/html" in (inconnue.content_type or "")
    assert "the requested url" not in page_texte(inconnue).lower()

    interdite = client.post("/", data={}, follow_redirects=False)

    assert interdite.status_code == 405
    assert_sans_traceback(interdite)
    assert "method is not allowed" not in page_texte(interdite).lower()
