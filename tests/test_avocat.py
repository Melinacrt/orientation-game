"""Tests de l'étape avocat (plan ``docs/plan-avocat.md`` §1 — TDD, rouge autorisé).

Contrats figés PAR CE FICHIER (dev : ne jamais modifier ce fichier) :

- Données : ``data/affaires/avocat-defense-001.json`` existe,
  ``data/affaires/avocat-defense.json`` n'existe plus (renommé) ;
  ``id == avocat-defense-001``, ``metier == avocat``, ``theme == avocat`` ;
  c18 et c21 ont ``gravite == 6`` ; ``fins[].gravite_max == [1, 4, 99]`` triés ;
  titres des fins : « Une défense rigoureuse » / « Une défense sous tension »
  / « Une défense compromise ».
- Images RÉELLES figées (vérifiées dans ``static/img/``, dossier servi par Flask) :
  e1 → ``img/01-garde-a-vue.jpg``, e2 → ``img/03-rencontre-cliente.jpg``,
  e3 → ``img/02-etude-dossier.jpg``, e4 → ``img/04-interrogatoire-temoin.jpg``,
  e5 → ``img/05-echange-parquet.jpg``, e6+e7 → ``img/06-plaidoirie.jpg``.
  Les noms ``avocat-temoin / avocat-couloir / avocat-plaidoirie`` n'existent pas.
- Calibrage figé (moteur, gravité totale → fin) :
  tout 0 → 1re fin ; c18 seul ou c21 seul (reste 0) → 3e fin ;
  c5(1)+c14(1)=2 (reste 0) → 2e fin. Chemins complets figés ci-dessous.
- Dashboard avocat figé (même logique que cyber : base + bonus − malus,
  bornes, temps dégressif) : ``tableau_avocat_attendu`` ci-dessous.
  Confiance d'Inès = clamp(80 + 5*(convaincre+aider) − 10*gravite, 0, 100) ;
  Solidité du dossier = clamp(10 + (analyser+enqueter) − 2*gravite, 0, 20) ;
  Temps avant l'audience = max(0, 120 − 15*nb_coups).
  Cyber inchangé (formule ``tableau_cyber_attendu``, libellés historiques).
- Schéma ``data/metiers.json`` étendu figé : ``formations`` accepte
  str non vide OU ``{etape, duree, description}`` (str non vides) ;
  ``bon_a_savoir`` (liste de str) et ``mentions`` (str) optionnels.
- Profils avocat : 5 profils (un par trait) intégrés à ``data/profils.json``
  au schéma existant ; correspondance trait → titre figée ci-dessous ;
  le bilan affiche un profil du métier joué (avocat → avocat, cyber → cyber).
- Disclaimer exact : « Affaire fictive et simplifiée, ce n'est pas un conseil
  juridique. » sur partie ET bilan avocat.

Style : fixtures app/client + helpers page_texte/assert_sans_traceback
comme tests/test_web.py et tests/test_themes_retour_bilan.py.
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

from app import affaires, moteur

RACINE = Path(__file__).resolve().parents[1]
ANCIEN_FICHIER = RACINE / "data" / "affaires" / "avocat-defense.json"
NOUVEAU_FICHIER = RACINE / "data" / "affaires" / "avocat-defense-001.json"
AFFAIRE_ID = "avocat-defense-001"
CYBER_ID = "cyber-alerte-serveur-rh"
METIERS_JSON = RACINE / "data" / "metiers.json"
PROFILS_JSON = RACINE / "data" / "profils.json"
CSS_PATH = RACINE / "static" / "style.css"
DOSSIER_IMG_SERVI = RACINE / "static" / "img"

TRAITS = ("analyser", "convaincre", "enqueter", "aider", "proteger")
DISCLAIMER = "Affaire fictive et simplifiée, ce n'est pas un conseil juridique."
LIBELLES_AVOCAT = (
    "Confiance d'Inès",
    "Solidité du dossier",
    "Temps avant l'audience",
)

# Mapping étape → image réelle figée (fichiers existants dans static/img/).
IMAGES_ATTENDUES = {
    "e1": "img/01-garde-a-vue.jpg",
    "e2": "img/03-rencontre-cliente.jpg",
    "e3": "img/02-etude-dossier.jpg",
    "e4": "img/04-interrogatoire-temoin.jpg",
    "e5": "img/05-echange-parquet.jpg",
    "e6": "img/06-plaidoirie.jpg",
    "e7": "img/06-plaidoirie.jpg",
}

FINS_ATTENDUES = [
    (1, "Une défense rigoureuse"),
    (4, "Une défense sous tension"),
    (99, "Une défense compromise"),
]

# Correspondance trait → titre de profil avocat (contenu figé en dur ci-dessous :
# ce fichier n'ouvre jamais les dossiers sources atomiques, seule source unique
# = data/metiers.json + data/profils.json).
PROFILS_AVOCAT_ATTENDUS = {
    "analyser": "Stratège du dossier",
    "convaincre": "Orateur de l'audience",
    "enqueter": "Enquêteur du contradictoire",
    "aider": "Défenseur à l'écoute",
    "proteger": "Gardien des droits",
}

# Contenu avocat figé en dur (reproduit à l'identique depuis les anciennes
# fiches sources, sans les ouvrir pour permettre leur suppression).
QUOTIDIEN_AVOCAT_ATTENDU = [
    "Recevoir des clients, préparer des entretiens confidentiels et, selon "
    "les dossiers, assister une personne pendant une garde à vue ou une "
    "audition.",
    "Étudier les pièces d'un dossier pénal, vérifier les déclarations et "
    "les éléments matériels, préparer des demandes d'actes et organiser la "
    "stratégie avec le client.",
    "Échanger avec les autres professionnels de la procédure, préparer les "
    "audiences, interroger les témoins lorsque la procédure le permet et "
    "plaider devant le tribunal.",
]

QUALITES_AVOCAT_ATTENDUES = [
    "Rigueur et esprit d'analyse",
    "Écoute et capacité à instaurer une relation de confiance",
    "Expression orale et écrite claire",
    "Résistance au stress et capacité à gérer les imprévus",
    "Indépendance, discrétion et respect de la déontologie",
]

FORMATIONS_AVOCAT_ATTENDUES = [
    {
        "etape": "Licence de droit",
        "duree": "3 ans",
        "description": "Études universitaires portant notamment sur le droit, "
        "les institutions, le raisonnement juridique et les méthodes de "
        "travail.",
    },
    {
        "etape": "Master 1 en droit",
        "duree": "1 an",
        "description": "Approfondissement des connaissances juridiques. Un "
        "parcours en droit privé ou en droit pénal peut être pertinent.",
    },
    {
        "etape": "Master 2 adapté au droit pénal",
        "duree": "1 an supplémentaire, généralement",
        "description": "Spécialisation possible en droit pénal, sciences "
        "criminelles ou dans un domaine voisin. Le choix du master dépend du "
        "projet et des conditions d'accès.",
    },
    {
        "etape": "Examen d'accès à l'école d'avocats (CRFPA)",
        "duree": "Préparation variable, souvent plusieurs mois",
        "description": "L'examen d'accès est sélectif. Les conditions "
        "d'inscription et le niveau universitaire requis doivent être "
        "vérifiés auprès des organismes compétents ; un master 1 en droit "
        "constitue le niveau de référence pour l'accès à l'examen.",
    },
    {
        "etape": "Formation en école d'avocats",
        "duree": "Environ 18 mois",
        "description": "Formation professionnelle mêlant enseignements, "
        "projets pédagogiques et stages, avec une préparation à l'exercice "
        "concret du métier.",
    },
    {
        "etape": "Certificat d'aptitude à la profession d'avocat (CAPA)",
        "duree": "Évaluation à l'issue de la formation",
        "description": "Obtention du certificat après validation des "
        "épreuves et des exigences de la formation professionnelle.",
    },
    {
        "etape": "Serment et inscription au barreau",
        "duree": "Quelques semaines à plusieurs mois selon les démarches",
        "description": "Après le CAPA, le futur avocat prête serment et "
        "accomplit les formalités d'inscription au barreau pour exercer. "
        "Les modalités exactes sont à confirmer auprès du barreau concerné.",
    },
]

BON_A_SAVOIR_AVOCAT_ATTENDU = [
    "Les horaires peuvent être irréguliers : une garde à vue, une audience "
    "ou une échéance urgente peut bouleverser une journée. La préparation "
    "des dossiers et la rédaction prennent souvent beaucoup de temps en "
    "dehors des audiences.",
    "Les revenus varient selon l'expérience, le lieu d'exercice, le statut "
    "et la clientèle. Les honoraires sont encadrés par des règles "
    "professionnelles ; l'aide juridictionnelle peut permettre à des "
    "personnes disposant de ressources limitées d'accéder à un avocat, "
    "selon les conditions applicables.",
]

# Descriptions des 5 profils avocat figées en dur (reproduites à l'identique
# depuis les anciennes fiches sources, sans les ouvrir).
DESCRIPTIONS_PROFILS_AVOCAT_ATTENDUES = {
    "analyser": "Tu as aimé comparer les déclarations, repérer les "
    "contradictions et distinguer les faits des suppositions. Tu prends le "
    "temps de comprendre les détails avant de construire une argumentation "
    "solide.",
    "convaincre": "Tu as aimé formuler une stratégie, poser des questions "
    "précises et présenter des arguments clairs. Tu sais que convaincre ne "
    "consiste pas à parler plus fort, mais à défendre une position avec "
    "méthode et crédibilité.",
    "enqueter": "Tu as aimé reconstituer la chronologie, chercher les "
    "informations manquantes et examiner les versions des témoins. Tu es "
    "attiré par le travail de recherche qui permet de comprendre ce qui "
    "s'est réellement passé.",
    "aider": "Tu as aimé écouter Inès, comprendre ses inquiétudes et "
    "l'aider à prendre des décisions éclairées. Tu accordes de l'importance "
    "à la relation humaine, surtout lorsqu'une personne traverse une "
    "situation difficile.",
    "proteger": "Tu as aimé veiller au respect des droits de ta cliente, "
    "préserver la confidentialité et éviter les décisions précipitées. Tu "
    "es sensible à l'équilibre entre la protection d'une personne et le "
    "respect des règles de justice.",
}

TITRES_CYBER_CONNUS = {
    "Sentinelle méthodique",
    "Enquêteur tenace",
    "Médiateur convaincant",
    "Protecteur attentionné",
    "Stratège lucide",
    "Gardien vigilant",
}

# Chemins complets figés (7 coups, e1→e7) pour le calibrage.
CHEMIN_TOUT_ZERO = [
    ("e1", "c1"),
    ("e2", "c4"),
    ("e3", "c7"),
    ("e4", "c10"),
    ("e5", "c13"),
    ("e6", "c16"),
    ("e7", "c19"),
]
CHEMIN_C18_SEUL = [
    ("e1", "c1"),
    ("e2", "c4"),
    ("e3", "c7"),
    ("e4", "c10"),
    ("e5", "c13"),
    ("e6", "c18"),
    ("e7", "c19"),
]
CHEMIN_C21_SEUL = [
    ("e1", "c1"),
    ("e2", "c4"),
    ("e3", "c7"),
    ("e4", "c10"),
    ("e5", "c13"),
    ("e6", "c16"),
    ("e7", "c21"),
]
# c5(1) + c14(1) = 2 → 2e fin (fins [1, 4, 99]).
CHEMIN_TENSION_C5_C14 = [
    ("e1", "c1"),
    ("e2", "c5"),
    ("e3", "c7"),
    ("e4", "c10"),
    ("e5", "c14"),
    ("e6", "c16"),
    ("e7", "c19"),
]


def tableau_avocat_attendu(etat):
    """Formule de référence du dashboard avocat (contrat pour dev)."""
    gravite = etat.get("gravite", 0)
    if not isinstance(gravite, int) or isinstance(gravite, bool) or gravite < 0:
        gravite = 0
    scores = etat.get("scores", {})
    if not isinstance(scores, dict):
        scores = {}


    def points(trait):
        valeur = scores.get(trait, 0)
        if not isinstance(valeur, int) or isinstance(valeur, bool):
            return 0
        return valeur

    convaincre = points("convaincre")
    aider = points("aider")
    analyser = points("analyser")
    enqueter = points("enqueter")
    historique = etat.get("historique", [])
    nb_coups = len(historique) if isinstance(historique, list) else 0
    confiance = max(0, min(100, 80 + 5 * (convaincre + aider) - 10 * gravite))
    solidite = max(0, min(20, 10 + (analyser + enqueter) - 2 * gravite))
    temps = max(0, 120 - 15 * nb_coups)
    return {
        "confiance": confiance,
        "solidite": solidite,
        "temps": temps,
    }


def tableau_cyber_attendu(etat):
    """Formule cyber inchangée (non-régression, cf. tests/test_immersion.py)."""
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
    return {
        "machines_infectees": min(1 + gravite, 50),
        "confiance_direction": max(0, min(100, 80 + 5 * (convaincre + aider) - 10 * gravite)),
        "temps_restant": max(0, 120 - 15 * nb_coups),
    }


def page_texte(reponse):
    """Texte HTML décodé (entités HTML résolues pour comparer au JSON)."""
    return html.unescape(reponse.get_data(as_text=True))


def assert_sans_traceback(reponse):
    texte = reponse.get_data(as_text=True)
    assert "traceback" not in texte.lower(), "page d'erreur brute (traceback visible)"


def charger_affaire_avocat():
    cible = NOUVEAU_FICHIER if NOUVEAU_FICHIER.exists() else ANCIEN_FICHIER
    return affaires.charger_affaire(cible)

def charger_metiers():
    with METIERS_JSON.open(encoding="utf-8") as fichier:
        return json.load(fichier)


def charger_profils():
    with PROFILS_JSON.open(encoding="utf-8") as fichier:
        return json.load(fichier)


def jouer_chemin(affaire, chemin):
    etat = moteur.nouvelle_partie(affaire)
    for etape_id, choix_id in chemin:
        etat = moteur.jouer_coup(affaire, etat, etape_id, choix_id)
    return etat


def gravite_choix(affaire, etape_id, choix_id):
    for choix in affaire["etapes"][etape_id]["choix"]:
        if choix["id"] == choix_id:
            return choix.get("gravite")
    raise AssertionError(f"choix {etape_id}/{choix_id} introuvable")


@pytest.fixture()
def app():
    assert creer_app is not None, "factory app.web.creer_app manquante"
    application = creer_app()
    application.config.update(TESTING=True, SECRET_KEY="secret-test-tdd")
    application.config["PROPAGATE_EXCEPTIONS"] = False
    return application


@pytest.fixture()
def client(app):
    return app.test_client()


def poster_coup(client, affaire_id, etape_id, choix_id):
    return client.post(
        "/jouer",
        data={"affaire": affaire_id, "etape": etape_id, "choix": choix_id},
        follow_redirects=False,
    )


def jouer_chemin_web(client, affaire_id, chemin):
    demarrage = client.get(f"/partie?affaire={affaire_id}")
    assert demarrage.status_code == 200
    for etape_id, choix_id in chemin:
        reponse = poster_coup(client, affaire_id, etape_id, choix_id)
        assert reponse.status_code in (302, 303), f"PRG attendu, reçu {reponse.status_code}"
        suivi = client.get(reponse.headers["Location"])
        assert suivi.status_code == 200
        assert_sans_traceback(suivi)
    return client.get("/bilan")


# --- 1. données affaire : renommage + identité -------------------------------


def test_fichier_affaire_renomme_avocat_defense_001():
    assert NOUVEAU_FICHIER.exists(), (
        "data/affaires/avocat-defense-001.json manquant (renommage attendu)"
    )
    assert not ANCIEN_FICHIER.exists(), (
        "data/affaires/avocat-defense.json existe encore (un seul fichier avocat attendu)"
    )


def test_affaire_avocat_id_metier_theme():
    affaire = charger_affaire_avocat()

    assert affaire["id"] == "avocat-defense-001"
    assert affaire["metier"] == "avocat"
    assert affaire.get("theme") == "avocat"


def test_affaire_avocat_texte_principal_inchange():
    affaire = charger_affaire_avocat()

    assert affaire["titre"] == "L'affaire du dernier métro"
    assert "Inès Morel" in affaire["contexte"]
    assert affaire["debut"] == "e1"
    assert set(affaire["etapes"]) == {"e1", "e2", "e3", "e4", "e5", "e6", "e7"}
    assert "garde à vue" in affaire["etapes"]["e1"]["texte"]
    labels_e1 = [c["label"] for c in affaire["etapes"]["e1"]["choix"]]
    assert "M'entretenir confidentiellement avec Inès" in labels_e1


# --- 1b. calibrage données : gravités + fins ---------------------------------


def test_choix_c18_et_c21_ont_une_gravite_de_6():
    affaire = charger_affaire_avocat()

    assert gravite_choix(affaire, "e6", "c18") == 6, "c18 (alibi inventé) doit valoir 6"
    assert gravite_choix(affaire, "e7", "c21") == 6, "c21 (détruire des traces) doit valoir 6"


def test_fins_avocat_gravite_max_1_4_99_triees_et_titrees():
    affaire = charger_affaire_avocat()
    maximums = [fin["gravite_max"] for fin in affaire["fins"]]

    assert maximums == [1, 4, 99], f"gravite_max [1, 4, 99] triés attendus, reçus {maximums}"
    assert [fin["titre"] for fin in affaire["fins"]] == [titre for _, titre in FINS_ATTENDUES]


# --- 1c. cohérence données : suites, traits, gravités, fins ------------------


def test_affaire_avocat_suites_referencent_des_etapes_existantes():
    affaire = charger_affaire_avocat()
    existantes = set(affaire["etapes"])

    for etape_id, etape in affaire["etapes"].items():
        for choix in etape["choix"]:
            suite = choix.get("suite")
            assert suite is None or suite in existantes, (
                f"suite orpheline {etape_id}/{choix['id']} → {suite!r}"
            )


def test_affaire_avocat_traits_connus_et_gravites_entieres_positives():
    affaire = charger_affaire_avocat()

    for etape in affaire["etapes"].values():
        for choix in etape["choix"]:
            assert set(choix.get("traits", {})) <= set(TRAITS), (
                f"traits inconnus dans {choix['id']}"
            )
            gravite = choix.get("gravite")
            assert isinstance(gravite, int) and not isinstance(gravite, bool), (
                f"gravité entière attendue pour {choix['id']}"
            )
            assert gravite >= 0


def test_affaire_avocat_trois_fins_triees():
    affaire = charger_affaire_avocat()
    maximums = [fin["gravite_max"] for fin in affaire["fins"]]

    assert len(affaire["fins"]) == 3
    assert maximums == sorted(maximums)


# --- 1d. images réelles -------------------------------------------------------


def test_affaire_avocat_mapping_images_reelles_fine():
    affaire = charger_affaire_avocat()

    for etape_id, image_attendue in IMAGES_ATTENDUES.items():
        assert affaire["etapes"][etape_id].get("image") == image_attendue, (
            f"{etape_id} : attendu {image_attendue!r}, "
            f"reçu {affaire['etapes'][etape_id].get('image')!r}"
        )


def test_affaire_avocat_images_motif_existence_et_alt():
    affaire = charger_affaire_avocat()
    motif = re.compile(r"^img/[a-z0-9\-_/]+\.(png|jpg|jpeg|webp|svg)$")

    for etape_id, etape in affaire["etapes"].items():
        image = etape.get("image")
        alt = etape.get("image_alt")
        assert isinstance(image, str) and motif.match(image), f"{etape_id} : motif img/ attendu"
        assert "avocat-temoin" not in image and "avocat-couloir" not in image, (
            f"{etape_id} : nom avocat-* inexistant figé comme interdit"
        )
        assert "avocat-plaidoirie" not in image, f"{etape_id} : nom avocat-* inexistant"
        assert isinstance(alt, str) and alt.strip() != "", f"{etape_id} : image_alt non vide"
        disque = DOSSIER_IMG_SERVI / image[len("img/") :]
        assert disque.is_file(), f"{etape_id} : {image!r} absent du disque servi (static/img/)"


# --- 2. calibrage moteur ------------------------------------------------------


def test_calibrage_tout_gravite_zero_mene_a_la_premiere_fin():
    affaire = charger_affaire_avocat()
    assert sum(gravite_choix(affaire, e, c) for e, c in CHEMIN_TOUT_ZERO) == 0
    etat = jouer_chemin(affaire, CHEMIN_TOUT_ZERO)

    bilan = moteur.calculer_bilan(affaire, etat, PROFILS_JSON)

    assert bilan["gravite"] == 0
    assert bilan["fin"]["titre"] == "Une défense rigoureuse"


def test_calibrage_c18_seul_mene_a_la_troisieme_fin():
    affaire = charger_affaire_avocat()
    assert gravite_choix(affaire, "e6", "c18") == 6
    etat = jouer_chemin(affaire, CHEMIN_C18_SEUL)

    bilan = moteur.calculer_bilan(affaire, etat, PROFILS_JSON)

    assert etat["gravite"] == 6
    assert bilan["fin"]["titre"] == "Une défense compromise"


def test_calibrage_c21_seul_mene_a_la_troisieme_fin():
    affaire = charger_affaire_avocat()
    assert gravite_choix(affaire, "e7", "c21") == 6
    etat = jouer_chemin(affaire, CHEMIN_C21_SEUL)

    bilan = moteur.calculer_bilan(affaire, etat, PROFILS_JSON)

    assert etat["gravite"] == 6
    assert bilan["fin"]["titre"] == "Une défense compromise"


def test_calibrage_c5_c14_total_2_mene_a_la_deuxieme_fin():
    affaire = charger_affaire_avocat()
    assert gravite_choix(affaire, "e2", "c5") == 1
    assert gravite_choix(affaire, "e5", "c14") == 1
    total = sum(gravite_choix(affaire, e, c) for e, c in CHEMIN_TENSION_C5_C14)
    assert 2 <= total <= 4, f"chemin figé c5+c14 : total 2-4 attendu, reçu {total}"
    etat = jouer_chemin(affaire, CHEMIN_TENSION_C5_C14)

    bilan = moteur.calculer_bilan(affaire, etat, PROFILS_JSON)

    assert bilan["fin"]["titre"] == "Une défense sous tension"


# --- 3. métiers / profils -----------------------------------------------------


def test_metiers_json_entree_avocat_egale_fiche_sans_doublon_et_jouable():
    metiers = charger_metiers()
    avocat = metiers.get("avocat")

    assert isinstance(avocat, dict), "entrée avocat manquante dans data/metiers.json"
    assert avocat.get("jouable") is True, "l'avocat doit être jouable"
    assert avocat.get("titre") == "Avocat de la défense"
    assert avocat.get("quotidien") == QUOTIDIEN_AVOCAT_ATTENDU, "quotidien avocat ≠ attendu"
    assert avocat.get("qualites") == QUALITES_AVOCAT_ATTENDUES, "qualités avocat ≠ attendu"
    assert avocat.get("formations") == FORMATIONS_AVOCAT_ATTENDUES, "formations ≠ attendu"
    assert avocat.get("bon_a_savoir") == BON_A_SAVOIR_AVOCAT_ATTENDU, "bon_a_savoir ≠ attendu"
    assert avocat.get("mentions") == DISCLAIMER, "mentions avocat ≠ disclaimer attendu"
    assert len(set(avocat["quotidien"])) == 3, "quotidien sans doublon"
    assert metiers.get("cyber") is not None and metiers.get("medecin") is not None
    assert metiers["cyber"]["jouable"] is True
    assert metiers["medecin"]["jouable"] is False


def test_metiers_json_schema_etendu_formations_bon_a_savoir_mentions():
    metiers = charger_metiers()

    for code, entree in metiers.items():
        assert isinstance(entree.get("titre"), str) and entree["titre"].strip() != ""
        quotidien = entree.get("quotidien")
        assert isinstance(quotidien, list) and len(quotidien) == 3
        assert all(isinstance(p, str) and p.strip() for p in quotidien)
        qualites = entree.get("qualites")
        assert isinstance(qualites, list) and qualites
        assert all(isinstance(q, str) and q.strip() for q in qualites)
        formations = entree.get("formations")
        assert isinstance(formations, list) and formations
        for formation in formations:
            if isinstance(formation, str):
                assert formation.strip() != "", f"{code} : formation vide"
            else:
                assert isinstance(formation, dict), f"{code} : formation str ou objet attendue"
                for cle in ("etape", "duree", "description"):
                    valeur = formation.get(cle)
                    assert isinstance(valeur, str) and valeur.strip() != "", (
                        f"{code} : formation.{cle} non vide attendue"
                    )
        assert isinstance(entree.get("jouable"), bool), f"{code} : jouable booléen manquant"
        bon_a_savoir = entree.get("bon_a_savoir")
        if bon_a_savoir is not None:
            assert isinstance(bon_a_savoir, list) and bon_a_savoir
            assert all(isinstance(b, str) and b.strip() for b in bon_a_savoir)
        mentions = entree.get("mentions")
        if mentions is not None:
            assert isinstance(mentions, str) and mentions.strip() != ""
    avocat = metiers["avocat"]
    assert isinstance(avocat.get("bon_a_savoir"), list) and len(avocat["bon_a_savoir"]) == 2
    assert isinstance(avocat.get("mentions"), str) and avocat["mentions"].strip() != ""


def test_profils_json_contient_les_cinq_profils_avocat_au_schema_existant():
    profils = charger_profils()
    assert isinstance(profils, list) and len(profils) >= 11, (
        "6 profils cyber + 5 profils avocat attendus (≥ 11)"
    )
    for trait, titre in PROFILS_AVOCAT_ATTENDUS.items():
        trouves = [p for p in profils if p.get("titre") == titre]
        assert trouves, f"profil avocat manquant : {titre!r}"
        profil = trouves[0]
        assert profil.get("texte") == DESCRIPTIONS_PROFILS_AVOCAT_ATTENDUES[trait], (
            f"{titre!r} : description ≠ contenu attendu figé en dur"
        )
        assert isinstance(profil.get("id"), str) and profil["id"].strip() != ""
        assert isinstance(profil.get("texte"), str) and len(profil["texte"].strip()) >= 20
        assert "tu" in profil["texte"].lower(), f"{titre!r} : style 2e personne attendu"
        assert trait in profil.get("traits_dominants", []), (
            f"{titre!r} : trait dominant {trait!r} attendu"
        )
        metiers = profil.get("metiers", profil.get("metiers_proches"))
        assert isinstance(metiers, list) and 3 <= len(metiers) <= 4


def test_bilan_avocat_affiche_un_profil_avocat_et_cyber_un_profil_cyber(client):
    bilan_avocat = jouer_chemin_web(client, AFFAIRE_ID, CHEMIN_TOUT_ZERO)

    assert bilan_avocat.status_code == 200
    texte_avocat = page_texte(bilan_avocat)
    assert any(titre in texte_avocat for titre in PROFILS_AVOCAT_ATTENDUS.values()), (
        "le bilan avocat doit afficher un profil avocat"
    )
    assert not any(titre in texte_avocat for titre in TITRES_CYBER_CONNUS), (
        "le bilan avocat ne doit pas afficher un profil cyber"
    )

    cyber = affaires.charger_affaire(
        RACINE / "data" / "affaires" / f"{CYBER_ID}.json"
    )
    chemin_cyber = [(cyber["debut"], cyber["etapes"][cyber["debut"]]["choix"][0]["id"])]
    etat = moteur.nouvelle_partie(cyber)
    for _ in range(10):
        if etat["etape_courante"] is None:
            break
        etape = cyber["etapes"][etat["etape_courante"]]
        etat = moteur.jouer_coup(cyber, etat, etat["etape_courante"], etape["choix"][0]["id"])
    assert chemin_cyber  # traçabilité du parcours cyber minimal
    bilan_moteur = moteur.calculer_bilan(cyber, etat, PROFILS_JSON)
    profil_cyber = bilan_moteur["profil"]
    titre_cyber = profil_cyber.get("titre") if isinstance(profil_cyber, dict) else profil_cyber
    assert titre_cyber in TITRES_CYBER_CONNUS, (
        f"le profil cyber doit rester cyber, reçu {titre_cyber!r}"
    )


def test_bilan_avocat_affiche_la_fiche_avocat_complete(client):
    bilan = jouer_chemin_web(client, AFFAIRE_ID, CHEMIN_TOUT_ZERO)
    metiers = charger_metiers()
    fiche = metiers["avocat"]
    texte = page_texte(bilan)
    brut = bilan.get_data(as_text=True)

    assert 'data-testid="fiche-metier"' in brut or "data-testid='fiche-metier'" in brut
    assert fiche["titre"] in texte
    for point in fiche["quotidien"]:
        assert point in texte, f"quotidien absent : {point[:30]!r}"
    assert any(q in texte for q in fiche["qualites"])
    assert any(
        (f if isinstance(f, str) else f.get("etape", "")) in texte for f in fiche["formations"]
    ), "aucune formation avocat dans le bilan"
    assert any(b in texte for b in fiche["bon_a_savoir"]), "bon_a_savoir absent du bilan"
    assert fiche["mentions"] in texte, "mentions absentes du bilan"


def test_accueil_liste_cyber_et_avocat_jouables_autres_bientot(client):
    reponse = client.get("/")

    assert reponse.status_code == 200
    texte = page_texte(reponse)
    assert "cyber" in texte.lower()
    assert "avocat" in texte.lower()
    assert AFFAIRE_ID in reponse.get_data(as_text=True) or AFFAIRE_ID in texte, (
        "l'accueil doit lier l'affaire avocat jouable"
    )
    assert "Bientôt" in texte, "badge « Bientôt » attendu pour les métiers non jouables"


# --- 4. interface : thèmes ----------------------------------------------------


def test_partie_et_bilan_avocat_appliquent_theme_avocat(client):
    partie = client.get(f"/partie?affaire={AFFAIRE_ID}")

    assert partie.status_code == 200
    brut_partie = partie.get_data(as_text=True)
    assert re.search(r'class="[^"]*theme-avocat[^"]*"', brut_partie) is not None, (
        "la partie avocat doit appliquer theme-avocat"
    )

    bilan = jouer_chemin_web(client, AFFAIRE_ID, CHEMIN_TOUT_ZERO)
    brut_bilan = bilan.get_data(as_text=True)
    assert re.search(r'class="[^"]*theme-avocat[^"]*"', brut_bilan) is not None, (
        "le bilan avocat doit appliquer theme-avocat"
    )


def test_accueil_et_erreurs_restent_neutres(client):
    accueil = client.get("/")

    assert re.search(r'class="[^"]*theme-neutre[^"]*"', accueil.get_data(as_text=True)) is not None
    assert "theme-avocat" not in accueil.get_data(as_text=True)

    introuvable = client.get("/page-inexistante-avocat-neutre-xyz")
    assert introuvable.status_code == 404
    assert_sans_traceback(introuvable)
    brut = introuvable.get_data(as_text=True)
    assert re.search(r'class="[^"]*theme-neutre[^"]*"', brut) is not None
    assert "theme-avocat" not in brut


def test_css_theme_avocat_serif_bordeaux_or_distinct_de_cyber():
    css = CSS_PATH.read_text(encoding="utf-8")

    assert ".theme-avocat" in css, "sélecteur .theme-avocat manquant dans static/style.css"
    bloc = re.search(r"\.theme-avocat[^{]*\{[^}]*\}", css, re.DOTALL)
    assert bloc is not None
    texte_bloc = bloc.group(0).lower()
    assert "serif" in css.lower() and "serif" in texte_bloc, (
        ".theme-avocat : police serif/empattement attendue (ambiance tribunal)"
    )
    bordeaux = ("bordeaux", "#6d", "#7f", "#5c1a", "#722f", "#800020", "#7b1e")
    assert any(marque in texte_bloc for marque in bordeaux), (
        ".theme-avocat : bordeaux attendu (rouge sombre de tribunal)"
    )
    Esperluette_or = ("#b08d3e", "gold", "#d4af", "#c9a")
    assert any(marque in texte_bloc for marque in Esperluette_or), (
        ".theme-avocat : doré attendu (or du tribunal)"
    )
    bloc_cyber = re.search(r"\.theme-cyber[^{]*\{[^}]*\}", css, re.DOTALL)
    assert bloc_cyber is not None and bloc_cyber.group(0) != bloc.group(0), (
        ".theme-avocat doit être distinct de .theme-cyber"
    )


# --- 4b. dashboard avocat -----------------------------------------------------


def test_moteur_tableau_de_bord_avocat_applique_la_formule_figee():
    affaire = charger_affaire_avocat()
    cas = [
        {"gravite": 0, "scores": {}, "historique": []},
        {
            "gravite": 2,
            "scores": {"convaincre": 1, "aider": 1, "analyser": 2, "enqueter": 1},
            "historique": [{"etape": "e1", "choix": "c1"}],
        },
        {
            "gravite": 100,
            "scores": {"convaincre": 30, "aider": 30, "analyser": 30, "enqueter": 30},
            "historique": [{"etape": "e", "choix": "c"}] * 20,
        },
    ]

    assert hasattr(moteur, "tableau_de_bord"), "app.moteur.tableau_de_bord manquante"
    for etat in cas:
        assert moteur.tableau_de_bord(affaire, etat) == tableau_avocat_attendu(etat)


def test_tableau_avocat_formule_reference_valeurs_initiales_et_bornes():
    assert tableau_avocat_attendu({"gravite": 0, "scores": {}, "historique": []}) == {
        "confiance": 80,
        "solidite": 10,
        "temps": 120,
    }
    sature = tableau_avocat_attendu(
        {
            "gravite": 100,
            "scores": {"convaincre": 30, "aider": 30, "analyser": 30, "enqueter": 30},
            "historique": [{"etape": "e", "choix": "c"}] * 20,
        }
    )

    assert sature["confiance"] == 0
    assert sature["solidite"] == 0
    assert sature["temps"] == 0


def test_partie_avocat_affiche_les_trois_libelles_du_tableau(client):
    reponse = client.get(f"/partie?affaire={AFFAIRE_ID}")

    assert reponse.status_code == 200
    assert_sans_traceback(reponse)
    texte = page_texte(reponse)
    assert 'data-testid="tableau-de-bord"' in reponse.get_data(as_text=True)
    for libelle in LIBELLES_AVOCAT:
        assert libelle in texte, f"libellé dashboard manquant : {libelle!r}"
    assert "Machines infectées" not in texte, "le dashboard cyber fuit sur l'affaire avocat"


def test_tableau_avocat_valeurs_initiales_suivent_la_formule(client):
    reponse = client.get(f"/partie?affaire={AFFAIRE_ID}")

    assert reponse.status_code == 200
    texte = page_texte(reponse)
    attendu = tableau_avocat_attendu({"gravite": 0, "scores": {}, "historique": []})
    for valeur in attendu.values():
        assert str(valeur) in texte, f"valeur dashboard {valeur} absente de la partie avocat"


def test_tableau_cyber_inchange_libelles_et_formule(client):
    reponse = client.get(f"/partie?affaire={CYBER_ID}")

    assert reponse.status_code == 200
    texte = page_texte(reponse)
    assert "Machines infectées" in texte
    assert "Confiance de la direction" in texte
    assert "Temps restant" in texte
    for libelle in LIBELLES_AVOCAT:
        assert libelle not in texte, f"libellé avocat {libelle!r} sur la partie cyber"
    affaire = affaires.charger_affaire(RACINE / "data" / "affaires" / f"{CYBER_ID}.json")
    assert moteur.tableau_de_bord(affaire, {"gravite": 0, "scores": {}, "historique": []}) == (
        tableau_cyber_attendu({"gravite": 0, "scores": {}, "historique": []})
    )


# --- 4c. chrono, images, disclaimer -------------------------------------------


def test_partie_avocat_chrono_mmss_comme_cyber(client):
    reponse = client.get(f"/partie?affaire={AFFAIRE_ID}")

    assert reponse.status_code == 200
    assert_sans_traceback(reponse)
    brut = reponse.get_data(as_text=True)
    assert 'data-testid="chrono"' in brut or 'class="chrono"' in brut
    assert re.search(r"\d{1,3}:\d{2}", brut) is not None, "chrono MM:SS attendu"


def test_partie_avocat_premiere_etape_illustree_au_dessus_du_texte(client):
    affaire = charger_affaire_avocat()
    reponse = client.get(f"/partie?affaire={AFFAIRE_ID}")

    assert reponse.status_code == 200
    assert_sans_traceback(reponse)
    texte = page_texte(reponse)
    sources = re.findall(r'<img[^>]+src="([^"]+)"[^>]*>', texte, re.IGNORECASE)
    assert sources, "e1 avocat illustrée : <img> manquant"
    assert any("/static/img/01-garde-a-vue" in src for src in sources)
    assert affaire["etapes"]["e1"]["image_alt"][:20] in texte
    index_img = texte.lower().find("<img")
    index_texte = texte.find(affaire["etapes"]["e1"]["texte"][:30])
    assert 0 <= index_img < index_texte, "<img> au-dessus du texte attendue"


def test_partie_et_bilan_avocat_affichent_le_disclaimer_juridique(client):
    partie = client.get(f"/partie?affaire={AFFAIRE_ID}")

    assert partie.status_code == 200
    assert DISCLAIMER in page_texte(partie), "disclaimer absent de la partie avocat"

    bilan = jouer_chemin_web(client, AFFAIRE_ID, CHEMIN_TOUT_ZERO)

    assert bilan.status_code == 200
    assert DISCLAIMER in page_texte(bilan), "disclaimer absent du bilan avocat"
