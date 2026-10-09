"""Tests du moteur de partie (étape 2).

Décrit ``app/moteur.py`` :
- ``nouvelle_partie(affaire)`` : scores à 0 pour les 5 traits, gravité 0,
  historique vide, étape courante = ``debut``.
- ``jouer_coup(affaire, état, etape_id, choix_id)`` : valide types / longueurs /
  valeurs, étape et choix existants (sinon ``ValueError`` en français) ; cumule
  traits + gravité, pousse ``{etape, choix, label, consequence}`` en historique,
  avance vers ``suite`` ou termine.
- ``calculer_bilan(affaire, état, profils)`` : scores, gravité, fin = première fin
  où ``gravite <= gravite_max``, citations = labels + conséquences réellement
  choisis, profil + métiers proches issus de ``profils``.

Affaire de référence : ``data/format-affaire.json``.
Phase rouge TDD normale : ces tests échouent tant que ``app/moteur.py``
n'est pas implémenté.
"""

from pathlib import Path

import pytest

from app import affaires, moteur

AFFAIRE_REFERENCE = Path(__file__).resolve().parents[1] / "data" / "format-affaire.json"

TRAITS_ATTENDUS = {"analyser", "convaincre", "enqueter", "aider", "proteger"}

PROFILS_EXEMPLE = [
    {
        "id": "analyste",
        "titre": "Analyste rigoureuse",
        "texte": "Tu aimes comprendre avant d'agir.",
        "traits_dominants": ["analyser", "proteger"],
        "metiers_proches": ["expert cyber"],
    },
    {
        "id": "orateur",
        "titre": "Orateur convaincant",
        "texte": "Tu sais expliquer et embarquer les autres.",
        "traits_dominants": ["convaincre", "aider"],
        "metiers_proches": ["avocat"],
    },
    {
        "id": "enqueteur",
        "titre": "Enquêteur de terrain",
        "texte": "Tu cherches des indices et tu aides les autres.",
        "traits_dominants": ["enqueter", "aider"],
        "metiers_proches": ["médecin"],
    },
]


def charger_reference():
    return affaires.charger_affaire(AFFAIRE_REFERENCE)


def jouer_parcours(affaire, coups):
    etat = moteur.nouvelle_partie(affaire)
    for etape_id, choix_id in coups:
        etat = moteur.jouer_coup(affaire, etat, etape_id, choix_id)
    return etat


def texte_citations(bilan):
    return " ".join(str(citation) for citation in bilan["citations"])


# --- nouvelle_partie -------------------------------------------------------


def test_nouvelle_partie_scores_initialises_a_zero_pour_les_cinq_traits():
    affaire = charger_reference()

    etat = moteur.nouvelle_partie(affaire)

    assert etat["scores"] == {trait: 0 for trait in TRAITS_ATTENDUS}


def test_nouvelle_partie_gravite_zero_historique_vide_etape_debut():
    affaire = charger_reference()

    etat = moteur.nouvelle_partie(affaire)

    assert etat["gravite"] == 0
    assert etat["historique"] == []
    assert etat["etape_courante"] == affaire["debut"]


def test_nouvelle_partie_affaire_invalide_leve_value_error():
    with pytest.raises(ValueError) as excinfo:
        moteur.nouvelle_partie({})

    assert str(excinfo.value).strip() != ""


# --- jouer_coup : parcours nominal ------------------------------------------


def test_jouer_coup_parcours_c1_c3_c5_cumule_les_traits_attendus():
    affaire = charger_reference()

    etat = jouer_parcours(affaire, [("e1", "c1"), ("e2", "c3"), ("e3", "c5")])

    assert etat["scores"]["analyser"] == 3
    assert etat["scores"]["proteger"] == 3
    assert etat["scores"]["convaincre"] == 2
    assert etat["scores"]["enqueter"] == 0
    assert etat["scores"]["aider"] == 0


def test_jouer_coup_parcours_c1_c3_c5_gravite_reste_a_zero():
    affaire = charger_reference()

    etat = jouer_parcours(affaire, [("e1", "c1"), ("e2", "c3"), ("e3", "c5")])

    assert etat["gravite"] == 0


def test_jouer_coup_avance_etape_courante_selon_la_suite():
    affaire = charger_reference()
    etat = moteur.nouvelle_partie(affaire)

    etat = moteur.jouer_coup(affaire, etat, "e1", "c1")

    assert etat["etape_courante"] == "e2"

    etat = moteur.jouer_coup(affaire, etat, "e2", "c3")

    assert etat["etape_courante"] == "e3"


def test_jouer_coup_termine_la_partie_quand_la_suite_est_nulle():
    affaire = charger_reference()

    etat = jouer_parcours(affaire, [("e1", "c1"), ("e2", "c3"), ("e3", "c5")])

    assert etat["etape_courante"] is None


def test_jouer_coup_historique_enregistre_etape_choix_label_consequence():
    affaire = charger_reference()

    etat = jouer_parcours(affaire, [("e1", "c1")])

    assert len(etat["historique"]) == 1
    entree = etat["historique"][0]
    assert entree["etape"] == "e1"
    assert entree["choix"] == "c1"
    assert entree["label"] == "Isoler la machine du réseau"
    assert "consequence" in entree
    assert entree["consequence"] != ""


def test_jouer_coup_cumule_la_gravite_des_mauvais_choix():
    affaire = charger_reference()

    etat = jouer_parcours(affaire, [("e1", "c2"), ("e2", "c4"), ("e3", "c6")])

    assert etat["gravite"] == 6


# --- jouer_coup : erreurs ----------------------------------------------------


def test_jouer_coup_etape_inconnue_leve_value_error_en_francais():
    affaire = charger_reference()
    etat = moteur.nouvelle_partie(affaire)

    with pytest.raises(ValueError) as excinfo:
        moteur.jouer_coup(affaire, etat, "etape-inexistante", "c1")

    assert str(excinfo.value).strip() != ""


def test_jouer_coup_choix_inconnu_leve_value_error_en_francais():
    affaire = charger_reference()
    etat = moteur.nouvelle_partie(affaire)

    with pytest.raises(ValueError) as excinfo:
        moteur.jouer_coup(affaire, etat, "e1", "choix-inexistant")

    assert str(excinfo.value).strip() != ""


@pytest.mark.parametrize(
    ("etape_id", "choix_id"),
    [(None, "c1"), ("e1", None), (123, "c1"), ("e1", 456)],
)
def test_jouer_coup_types_invalides_leve_value_error(etape_id, choix_id):
    affaire = charger_reference()
    etat = moteur.nouvelle_partie(affaire)

    with pytest.raises(ValueError) as excinfo:
        moteur.jouer_coup(affaire, etat, etape_id, choix_id)

    assert str(excinfo.value).strip() != ""


def test_jouer_coup_identifiants_trop_longs_leve_value_error():
    affaire = charger_reference()
    etat = moteur.nouvelle_partie(affaire)

    with pytest.raises(ValueError):
        moteur.jouer_coup(affaire, etat, "e" * 500, "c1")
    with pytest.raises(ValueError):
        moteur.jouer_coup(affaire, etat, "e1", "c" * 500)


# --- calculer_bilan ----------------------------------------------------------


def test_bilan_parcours_c1_c3_c5_scores_gravite_et_fin_crise_maitrisee():
    affaire = charger_reference()
    etat = jouer_parcours(affaire, [("e1", "c1"), ("e2", "c3"), ("e3", "c5")])

    bilan = moteur.calculer_bilan(affaire, etat, PROFILS_EXEMPLE)

    assert bilan["scores"] == {
        "analyser": 3,
        "convaincre": 2,
        "enqueter": 0,
        "aider": 0,
        "proteger": 3,
    }
    assert bilan["gravite"] == 0
    assert bilan["fin"]["titre"] == "Crise maîtrisée"


def test_bilan_gravite_2_donne_la_fin_degats_limites():
    affaire = charger_reference()
    etat = jouer_parcours(affaire, [("e1", "c2"), ("e2", "c3"), ("e3", "c5")])
    assert etat["gravite"] == 2

    bilan = moteur.calculer_bilan(affaire, etat, PROFILS_EXEMPLE)

    assert bilan["fin"]["titre"] == "Dégâts limités"


def test_bilan_gravite_6_donne_la_fin_crise_mal_geree():
    affaire = charger_reference()
    etat = jouer_parcours(affaire, [("e1", "c2"), ("e2", "c4"), ("e3", "c6")])
    assert etat["gravite"] == 6

    bilan = moteur.calculer_bilan(affaire, etat, PROFILS_EXEMPLE)

    assert bilan["fin"]["titre"] == "Crise mal gérée"


def test_bilan_citations_reprennent_les_vrais_labels_choisis():
    affaire = charger_reference()
    etat = jouer_parcours(affaire, [("e1", "c1"), ("e2", "c3"), ("e3", "c5")])

    bilan = moteur.calculer_bilan(affaire, etat, PROFILS_EXEMPLE)

    citations = texte_citations(bilan)
    assert "Isoler la machine du réseau" in citations
    assert "Faire un point clair et factuel" in citations
    assert "Restaurer les sauvegardes" in citations


def test_bilan_citations_excluent_les_labels_non_choisis():
    affaire = charger_reference()
    etat = jouer_parcours(affaire, [("e1", "c1"), ("e2", "c3"), ("e3", "c5")])

    bilan = moteur.calculer_bilan(affaire, etat, PROFILS_EXEMPLE)

    citations = texte_citations(bilan)
    assert "Redémarrer la machine pour voir" not in citations
    assert "Payer la rançon" not in citations


def test_bilan_citations_reprennent_les_consequences_reellement_choisies():
    affaire = charger_reference()
    etat = jouer_parcours(affaire, [("e1", "c1"), ("e2", "c3"), ("e3", "c5")])

    bilan = moteur.calculer_bilan(affaire, etat, PROFILS_EXEMPLE)

    citations = texte_citations(bilan)
    assert "La machine est coupée" in citations
    assert "Les données reviennent sans rien payer." in citations


def test_bilan_profil_et_metiers_proches_issus_des_profils_fournis():
    affaire = charger_reference()
    etat = jouer_parcours(affaire, [("e1", "c1"), ("e2", "c3"), ("e3", "c5")])

    bilan = moteur.calculer_bilan(affaire, etat, PROFILS_EXEMPLE)

    assert "profil" in bilan
    assert "metiers_proches" in bilan
    profil = bilan["profil"]
    if isinstance(profil, dict):
        identifiants = {p["id"] for p in PROFILS_EXEMPLE} | {p["titre"] for p in PROFILS_EXEMPLE}
        identifiant = profil.get("id", profil.get("titre"))
        assert identifiant in identifiants
        attendu = next(
            p
            for p in PROFILS_EXEMPLE
            if p["id"] == profil.get("id") or p["titre"] == profil.get("titre")
        )
        assert bilan["metiers_proches"] == attendu["metiers_proches"]
    else:
        identifiants = {p["id"] for p in PROFILS_EXEMPLE} | {p["titre"] for p in PROFILS_EXEMPLE}
        assert profil in identifiants
    for metier in bilan["metiers_proches"]:
        # Nouveau contrat (plan-bilan étape 1, rupture volontaire tester) : métiers
        # réels (noms non vides ; dicts enrichis acceptés avec phrase de lien).
        if isinstance(metier, dict):
            nom = metier.get("nom", metier.get("titre", ""))
            assert isinstance(nom, str) and nom.strip() != ""
        else:
            assert isinstance(metier, str) and metier.strip() != ""
