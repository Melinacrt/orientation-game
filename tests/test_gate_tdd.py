"""Preuve gate TDD (étape 1, phase rouge) : `app.affaires.compter_etapes` manque encore.

Le test échoue par assertion (pas par ImportError) tant que la fonction
n'existe pas, puis vérifie son comportement une fois implémentée.
"""

from pathlib import Path

import pytest

try:
    from app.affaires import charger_affaire, compter_etapes
except ImportError:  # pragma: no cover - phase rouge TDD
    charger_affaire = None  # type: ignore[assignment]
    compter_etapes = None  # type: ignore[assignment]

AFFAIRE_REFERENCE = Path(__file__).resolve().parents[1] / "data" / "format-affaire.json"


def test_compter_etapes_retourne_le_nombre_d_etapes_et_valide_son_entree():
    assert compter_etapes is not None, (
        "fonction app.affaires.compter_etapes manquante (phase rouge TDD)"
    )
    affaire = charger_affaire(AFFAIRE_REFERENCE)
    assert compter_etapes(affaire) == 3
    with pytest.raises(ValueError):
        compter_etapes({})
    with pytest.raises(ValueError):
        compter_etapes({"etapes": "pas-un-dict"})
