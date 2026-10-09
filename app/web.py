"""Application web Flask du jeu Orientation Game (sans IA).

Le jeu se joue dans le navigateur à partir des affaires JSON validées :
``GET /`` (accueil), ``GET /partie`` (contexte + étape), ``POST /jouer``
(un choix, état en session) et ``GET /bilan`` (fin + scores + citations).
Toute entrée utilisateur est validée et toute erreur renvoie une page
propre en français, jamais une traceback brute.
"""

from __future__ import annotations

import copy
import os
import re
from pathlib import Path
from typing import Any

from flask import Flask, render_template, request, session

from app.affaires import charger_affaire
from app.moteur import TRAITS, calculer_bilan, jouer_coup, nouvelle_partie

RACINE = Path(__file__).resolve().parents[1]
DOSSIER_AFFAIRES = RACINE / "data" / "affaires"
FICHIER_PROFILS = RACINE / "data" / "profils.json"
LONGUEUR_MAX = 200
MOTIF_AFFAIRE = re.compile(r"^[a-z0-9-]+$")
CLE_SECRETE_DEV = "cle-dev-locale-non-secrete-a-changer"


def creer_app() -> Flask:
    """Crée et configure l'application Flask du jeu.

    Returns:
        L'application Flask prête à servir (templates + statiques inclus).
    """
    application = Flask(
        __name__,
        template_folder=str(RACINE / "templates"),
        static_folder=str(RACINE / "static"),
    )
    application.secret_key = os.environ.get("SECRET_KEY", CLE_SECRETE_DEV)

    @application.get("/")
    def accueil() -> str:
        return render_template("accueil.html")

    @application.get("/partie")
    def partie() -> tuple[str, int]:
        try:
            affaire_id = _valider_id_affaire(request.args.get("affaire"))
        except ValueError as exc:
            return _page_erreur(400, str(exc))
        try:
            affaire = _charger_affaire(affaire_id)
        except ValueError as exc:
            return _page_erreur(404, str(exc))
        etat = nouvelle_partie(affaire)
        session["affaire_id"] = affaire_id
        session["etat"] = etat
        return _page_partie(affaire, affaire_id, etat, consequence=None), 200

    @application.post("/jouer")
    def jouer() -> tuple[str, int]:
        try:
            affaire_id = _valider_id_affaire(request.form.get("affaire"))
            etape_id = _exiger_champ(request.form.get("etape"), "etape")
            choix_id = _exiger_champ(request.form.get("choix"), "choix")
            affaire = _charger_affaire(affaire_id)
        except ValueError as exc:
            return _page_erreur(400, str(exc))
        try:
            etat = _etat_session(affaire, affaire_id)
            courante = etat.get("etape_courante")
            if courante is None:
                bilan = calculer_bilan(affaire, etat, FICHIER_PROFILS)
                return _page_bilan(affaire, affaire_id, etat, bilan), 200
            if etape_id != courante:
                raise ValueError(
                    "Cette étape ne correspond pas à la partie en cours : "
                    "choix invalide. Retour à l'accueil pour recommencer."
                )
            etat = jouer_coup(affaire, etat, etape_id, choix_id)
        except ValueError as exc:
            return _page_erreur(400, str(exc))
        session["affaire_id"] = affaire_id
        session["etat"] = etat
        if etat.get("etape_courante") is None:
            try:
                bilan = calculer_bilan(affaire, etat, FICHIER_PROFILS)
            except ValueError as exc:
                return _page_erreur(400, str(exc))
            return _page_bilan(affaire, affaire_id, etat, bilan), 200
        consequence = ""
        if isinstance(etat.get("historique"), list) and etat["historique"]:
            derniere = etat["historique"][-1]
            if isinstance(derniere, dict):
                valeur = derniere.get("consequence", "")
                if isinstance(valeur, str):
                    consequence = valeur
        return _page_partie(affaire, affaire_id, etat, consequence or None), 200

    @application.get("/bilan")
    def bilan() -> tuple[str, int]:
        etat_brut = session.get("etat")
        affaire_stockee = session.get("affaire_id")
        if not isinstance(etat_brut, dict) or not isinstance(affaire_stockee, str):
            return _page_erreur(
                400,
                "Aucune partie en cours : demande invalide. "
                "Retour à l'accueil pour commencer une affaire.",
            )
        try:
            affaire_id = _valider_id_affaire(affaire_stockee)
            affaire = _charger_affaire(affaire_id)
            etat = copy.deepcopy(etat_brut)
            resultat = calculer_bilan(affaire, etat, FICHIER_PROFILS)
        except ValueError as exc:
            return _page_erreur(400, str(exc))
        return _page_bilan(affaire, affaire_id, etat, resultat), 200

    @application.errorhandler(400)
    def erreur_400(exc: Any) -> tuple[str, int]:
        message = _message_erreur(exc, "Demande invalide ou incorrecte.")
        return _page_erreur(400, f"{message} Retour à l'accueil.")

    @application.errorhandler(404)
    def erreur_404(exc: Any) -> tuple[str, int]:
        message = _message_erreur(exc, "Page introuvable.")
        return _page_erreur(404, f"{message} Retour à l'accueil.")

    @application.errorhandler(500)
    def erreur_500(exc: Any) -> tuple[str, int]:
        _ = exc
        return _page_erreur(
            500,
            "Oups, une erreur interne est survenue. Désolée, "
            "un problème technique nous empêche d'afficher cette page. "
            "Retour à l'accueil pour recommencer.",
        )

    return application


def _page_partie(
    affaire: dict, affaire_id: str, etat: dict, consequence: str | None
) -> str:
    etape_id = str(etat.get("etape_courante"))
    etape = affaire["etapes"][etape_id]
    historique = etat.get("historique")
    numero = len(historique) + 1 if isinstance(historique, list) else 1
    return render_template(
        "partie.html",
        affaire=affaire,
        affaire_id=affaire_id,
        etape_id=etape_id,
        etape=etape,
        consequence=consequence,
        numero=numero,
        total=len(affaire["etapes"]),
    )


def _page_bilan(affaire: dict, affaire_id: str, etat: dict, bilan: dict) -> str:
    _ = etat
    return render_template(
        "bilan.html",
        affaire=affaire,
        affaire_id=affaire_id,
        bilan=bilan,
        traits=list(TRAITS),
    )


def _page_erreur(code: int, message: str) -> tuple[str, int]:
    return render_template("erreur.html", code=code, message=message), code


def _message_erreur(exc: Any, defaut: str) -> str:
    description = getattr(exc, "description", None)
    if isinstance(description, str) and description.strip():
        return description
    return defaut


def _exiger_champ(valeur: object, nom: str) -> str:
    if not isinstance(valeur, str):
        raise ValueError(
            f"Le champ « {nom} » doit être une chaîne de caractères : "
            "choix invalide. Retour à l'accueil pour recommencer."
        )
    if not valeur.strip():
        raise ValueError(
            f"Le champ « {nom} » est manquant ou vide : choix invalide. "
            "Retour à l'accueil pour recommencer."
        )
    if len(valeur) > LONGUEUR_MAX:
        raise ValueError(
            f"Le champ « {nom} » ne doit pas dépasser {LONGUEUR_MAX} caractères : "
            "choix invalide. Retour à l'accueil pour recommencer."
        )
    return valeur


def _valider_id_affaire(valeur: object) -> str:
    identifiant = _exiger_champ(valeur, "affaire")
    if not MOTIF_AFFAIRE.match(identifiant):
        raise ValueError(
            "L'identifiant d'affaire est invalide : caractères incorrects "
            "(lettres minuscules, chiffres et tirets uniquement). "
            "Retour à l'accueil pour recommencer."
        )
    return identifiant


def _charger_affaire(affaire_id: str) -> dict:
    chemin = DOSSIER_AFFAIRES / f"{affaire_id}.json"
    try:
        return charger_affaire(chemin)
    except ValueError as exc:
        texte = str(exc)
        if "introuvable" in texte:
            raise ValueError(
                f"L'affaire « {affaire_id} » est introuvable : affaire inconnue. "
                "Retour à l'accueil pour choisir une affaire."
            ) from exc
        raise ValueError(
            f"L'affaire « {affaire_id} » est invalide et impossible à charger. "
            "Retour à l'accueil pour recommencer."
        ) from exc


def _etat_session(affaire: dict, affaire_id: str) -> dict:
    etat_brut = session.get("etat")
    affaire_stockee = session.get("affaire_id")
    if isinstance(etat_brut, dict) and affaire_stockee == affaire_id:
        return copy.deepcopy(etat_brut)
    return nouvelle_partie(affaire)


if __name__ == "__main__":
    creer_app().run(debug=True)
