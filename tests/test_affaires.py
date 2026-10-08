"""Tests du socle « affaires » : chargement et validation d'un fichier JSON d'affaire.

Ces tests décrivent le comportement attendu de ``app.affaires.charger_affaire``.
Ils échouent tant que le module applicatif n'existe pas (phase rouge).
"""

import json
from pathlib import Path

import pytest

from app.affaires import charger_affaire

AFFAIRE_REFERENCE = Path(__file__).resolve().parents[1] / "data" / "format-affaire.json"

TRAITS_AUTORISES = {"analyser", "convaincre", "enqueter", "aider", "proteger"}


def test_charger_affaire_valide_renvoie_un_dict_avec_les_cles_attendues():
    affaire = charger_affaire(AFFAIRE_REFERENCE)

    assert isinstance(affaire, dict)
    for cle in ("id", "metier", "titre", "etapes"):
        assert cle in affaire, f"clé manquante : {cle}"


def test_charger_affaire_json_malforme_leve_value_error(tmp_path):
    mauvais = tmp_path / "affaire-malformee.json"
    mauvais.write_text("{ ceci n'est pas du json", encoding="utf-8")

    with pytest.raises(ValueError):
        charger_affaire(mauvais)


def test_charger_affaire_sans_cles_obligatoires_leve_value_error(tmp_path):
    incomplet = tmp_path / "affaire-incomplete.json"
    incomplet.write_text(json.dumps({"titre": "Affaire sans rien d'autre"}), encoding="utf-8")

    with pytest.raises(ValueError):
        charger_affaire(incomplet)


def test_les_traits_des_choix_sont_parmi_ceux_autorises():
    affaire = charger_affaire(AFFAIRE_REFERENCE)

    for etape in affaire["etapes"].values():
        for choix in etape["choix"]:
            assert set(choix["traits"]) <= TRAITS_AUTORISES
