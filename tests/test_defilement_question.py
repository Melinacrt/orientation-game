"""Contrat d'ancre UX : ne pas revenir en haut après avoir répondu.

Étape 1 du ``docs/plan-defilement-question.md``.

Comportement attendu après l'étape 2 (``dev``) :
- la page ``GET /partie?affaire=cyber-alerte-serveur-rh`` contient un bloc
  portant l'attribut exact ``id="question"`` ;
- le formulaire de choix (``method="post"``) a une action ciblant le fragment
  ``#question`` (par ex. ``/jouer#question``), pour que le navigateur revienne
  sur la question après le redirect 303 du PRG.

Phase rouge TDD normale : ces tests échouent tant que ``templates/partie.html``
n'a pas reçu l'``id`` et l'ancre (l'implémentation ne doit pas modifier ce test).
"""

import re
from html.parser import HTMLParser

import pytest

try:
    from app.web import creer_app
except ImportError:  # pragma: no cover - phase rouge TDD
    creer_app = None  # type: ignore[assignment]

AFFAIRE_ID = "cyber-alerte-serveur-rh"


class _ParseurBalisage(HTMLParser):
    """Collecte les ``id`` présents et les attributs des balises ``<form>``."""

    def __init__(self):
        super().__init__()
        self.ids = set()
        self.formulaires = []

    def handle_starttag(self, tag, attrs):
        attributs = dict(attrs)
        if "id" in attributs:
            self.ids.add(attributs["id"])
        if tag == "form":
            self.formulaires.append(attributs)


@pytest.fixture()
def app():
    assert creer_app is not None, (
        "factory app.web.creer_app manquante (phase rouge TDD)"
    )
    application = creer_app()
    application.config.update(TESTING=True, SECRET_KEY="secret-test-tdd")
    application.config["PROPAGATE_EXCEPTIONS"] = False
    return application


@pytest.fixture()
def client(app):
    return app.test_client()


def page_partie(client):
    reponse = client.get(f"/partie?affaire={AFFAIRE_ID}")
    assert reponse.status_code == 200
    return reponse.get_data(as_text=True)


def test_page_partie_contient_le_bloc_id_question(client):
    html = page_partie(client)

    assert re.search(r'id="question"', html), (
        'le bloc question doit porter l\'attribut exact id="question"'
    )

    parseur = _ParseurBalisage()
    parseur.feed(html)
    assert "question" in parseur.ids, "aucune balise ne porte id=\"question\""


def test_formulaire_de_choix_cible_l_ancre_question(client):
    html = page_partie(client)

    # Contrat brut : l'action contient le fragment #question (robuste à l'espacement).
    assert re.search(r'action="[^"]*#question"', html), (
        'le formulaire doit avoir action=".../jouer#question"'
    )

    parseur = _ParseurBalisage()
    parseur.feed(html)
    formulaires_post = [
        attrs for attrs in parseur.formulaires if attrs.get("method", "").lower() == "post"
    ]
    assert formulaires_post, "aucun formulaire method=post sur la page partie"

    actions = [attrs.get("action", "") for attrs in formulaires_post]
    assert any(action.endswith("#question") for action in actions), (
        f"aucune action de formulaire ne termine par #question : {actions}"
    )
