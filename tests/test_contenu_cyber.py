"""Tests du contenu « Expert cyber » (étape 3).

Exigent :
- ``data/affaires/cyber-alerte-serveur-rh.json`` : chargeable via
  ``charger_affaire``, 6 à 8 étapes, ``metier == "cyber"``, au moins un
  embranchement réel (deux choix d'une même étape vers deux ``suite``
  différentes non nulles), toutes les ``suite`` non nulles référencent une
  étape existante, au moins un chemin complet ≥ 3 coups via le moteur,
  traits tous autorisés.
- ``data/profils.json`` : liste JSON chargeable, chaque entrée avec
  ``traits_dominants`` (parmi les 5), ``titre``, ``texte``,
  ``metiers_proches`` (sous-ensemble de expert cyber / avocat / médecin) ;
  ``calculer_bilan`` sur un parcours type renvoie un profil existant et
  cite au moins 2 vrais labels.

Phase rouge TDD normale : ces tests échouent tant que les fichiers
``data/`` ne sont pas écrits.
"""

import json
from pathlib import Path

from app import affaires, moteur

AFFAIRE_CYBER = (
    Path(__file__).resolve().parents[1] / "data" / "affaires" / "cyber-alerte-serveur-rh.json"
)
PROFILS_JSON = Path(__file__).resolve().parents[1] / "data" / "profils.json"

TRAITS_AUTORISES = {"analyser", "convaincre", "enqueter", "aider", "proteger"}
METIERS_AUTORISES = {"expert cyber", "avocat", "médecin"}


def charger_affaire_cyber():
    return affaires.charger_affaire(AFFAIRE_CYBER)


def charger_profils():
    with PROFILS_JSON.open(encoding="utf-8") as fichier:
        return json.load(fichier)


def jouer_premier_chemin(affaire):
    """Joue le premier choix de chaque étape jusqu'à la fin (via le moteur)."""
    etat = moteur.nouvelle_partie(affaire)
    for _ in range(20):
        etape_id = etat["etape_courante"]
        if etape_id is None:
            break
        etape = affaire["etapes"][etape_id]
        premier_choix = etape["choix"][0]["id"]
        etat = moteur.jouer_coup(affaire, etat, etape_id, premier_choix)
    return etat


def chercher_chemin_complet(affaire, minimum_coups=3):
    """Cherche en profondeur un chemin de ``minimum_coups`` coups vers une fin."""
    debut = affaire["debut"]
    pile = [(debut, [])]
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


# --- affaire cyber : chargement et volume ------------------------------------


def test_affaire_cyber_se_charge_sans_erreur():
    affaire = charger_affaire_cyber()

    assert isinstance(affaire, dict)
    assert affaire["etapes"]


def test_affaire_cyber_compte_entre_6_et_8_etapes():
    affaire = charger_affaire_cyber()

    assert 6 <= affaires.compter_etapes(affaire) <= 8


def test_affaire_cyber_metier_est_cyber():
    affaire = charger_affaire_cyber()

    assert affaire["metier"] == "cyber"


# --- affaire cyber : embranchements et cohérence ------------------------------


def test_affaire_cyber_possede_un_embranchement_reel():
    affaire = charger_affaire_cyber()

    embranchement = False
    for etape in affaire["etapes"].values():
        suites = [choix.get("suite") for choix in etape["choix"]]
        non_nulles = {suite for suite in suites if suite is not None}
        if len(non_nulles) >= 2:
            embranchement = True
            break

    assert embranchement, "aucune étape ne propose deux suites différentes non nulles"


def test_affaire_cyber_suites_referencent_des_etapes_existantes():
    affaire = charger_affaire_cyber()

    existantes = set(affaire["etapes"])
    for etape in affaire["etapes"].values():
        for choix in etape["choix"]:
            suite = choix.get("suite")
            assert suite is None or suite in existantes


def test_affaire_cyber_traits_tous_autorises():
    affaire = charger_affaire_cyber()

    for etape in affaire["etapes"].values():
        for choix in etape["choix"]:
            assert set(choix.get("traits", {})) <= TRAITS_AUTORISES


def test_affaire_cyber_au_moins_un_chemin_complet_d_au_moins_trois_coups():
    affaire = charger_affaire_cyber()

    chemin = chercher_chemin_complet(affaire, minimum_coups=3)

    assert chemin is not None, "aucun chemin complet de 3 coups vers une fin"
    assert len(chemin) >= 3
    etat = moteur.nouvelle_partie(affaire)
    for etape_id, choix_id in chemin:
        etat = moteur.jouer_coup(affaire, etat, etape_id, choix_id)
    assert etat["etape_courante"] is None


# --- profils.json --------------------------------------------------------------


def test_profils_json_est_une_liste_chargeable_non_vide():
    profils = charger_profils()

    assert isinstance(profils, list)
    assert len(profils) >= 1


def test_profils_chaque_entree_a_les_cles_attendues():
    profils = charger_profils()

    for profil in profils:
        assert isinstance(profil, dict)
        for cle in ("traits_dominants", "titre", "texte", "metiers_proches"):
            assert cle in profil, f"clé manquante : {cle}"


def test_profils_traits_dominants_parmi_les_cinq_traits():
    profils = charger_profils()

    for profil in profils:
        dominants = profil["traits_dominants"]
        assert isinstance(dominants, list) and dominants
        assert set(dominants) <= TRAITS_AUTORISES


def test_profils_metiers_proches_parmi_les_trois_metiers():
    """Nouveau contrat (plan-bilan étape 1, rupture volontaire tester) : métiers réels.

    Chaque profil liste 3-4 métiers enrichis (dicts : nom réel + phrase de lien
    + statut jouable) au lieu d'un sous-ensemble de chaînes parmi les trois
    métiers. Seul « expert cyber » (seule affaire existante) est jouable.
    """
    profils = charger_profils()

    for profil in profils:
        proches = profil.get("metiers", profil.get("metiers_proches"))
        assert isinstance(proches, list)
        assert 3 <= len(proches) <= 4
        for entree in proches:
            assert isinstance(entree, dict)
            nom = entree.get("nom", entree.get("nom_metier", entree.get("titre", "")))
            lien = entree.get("lien", entree.get("pourquoi", ""))
            jouable = entree.get("jouable", entree.get("disponible"))
            assert isinstance(nom, str) and nom.strip() != ""
            assert isinstance(lien, str) and lien.strip() != ""
            assert isinstance(jouable, bool)
            if nom.strip().lower() == "expert cyber":
                assert jouable is True, "« expert cyber » (affaire existante) doit être jouable"
            else:
                assert jouable is False, f"« {nom} » doit être « Bientôt » (non jouable)"


def test_bilan_sur_parcours_type_renvoie_un_profil_existant():
    affaire = charger_affaire_cyber()
    profils = charger_profils()
    etat = jouer_premier_chemin(affaire)

    bilan = moteur.calculer_bilan(affaire, etat, profils)

    identifiants = {p.get("id") for p in profils} | {p.get("titre") for p in profils}
    profil = bilan["profil"]
    if isinstance(profil, dict):
        identifiant = profil.get("id", profil.get("titre"))
    else:
        identifiant = profil
    assert identifiant in identifiants


def test_bilan_sur_parcours_type_cite_au_moins_deux_vrais_labels():
    affaire = charger_affaire_cyber()
    profils = charger_profils()
    etat = jouer_premier_chemin(affaire)
    vrais_labels = [entree["label"] for entree in etat["historique"]]

    bilan = moteur.calculer_bilan(affaire, etat, profils)

    texte_citations = " ".join(str(citation) for citation in bilan["citations"])
    trouves = [label for label in vrais_labels if label in texte_citations]
    assert len(trouves) >= 2
