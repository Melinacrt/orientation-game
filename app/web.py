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

from flask import Flask, redirect, render_template, request, session, url_for

from app.affaires import charger_affaire
from app.moteur import TRAITS, calculer_bilan, jouer_coup, nouvelle_partie

RACINE = Path(__file__).resolve().parents[1]
DOSSIER_AFFAIRES = RACINE / "data" / "affaires"
FICHIER_PROFILS = RACINE / "data" / "profils.json"
LONGUEUR_MAX = 200
MOTIF_AFFAIRE = re.compile(r"^[a-z0-9-]+$")
CLE_SECRETE_DEV = "cle-dev-locale-non-secrete-a-changer"
LIBELLES_TRAITS = {
    "analyser": "Analyser",
    "convaincre": "Convaincre",
    "enqueter": "Enquêter",
    "aider": "Aider",
    "proteger": "Protéger",
}


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
    def partie() -> Any:
        if "affaire" not in request.args:
            return _reponse_etape_ou_accueil()
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

    @application.get("/jouer")
    def afficher_jouer() -> Any:
        return _reponse_etape_ou_accueil()

    @application.post("/jouer")
    def jouer() -> Any:
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
                return redirect(url_for("bilan"), code=303)
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
            return redirect(url_for("bilan"), code=303)
        return redirect(url_for("afficher_jouer"), code=303)

    @application.get("/bilan")
    def bilan() -> Any:
        etat_brut = session.get("etat")
        affaire_stockee = session.get("affaire_id")
        if not isinstance(etat_brut, dict) or not isinstance(affaire_stockee, str):
            return redirect(url_for("accueil"))
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
        _ = exc
        return _page_erreur(
            404,
            "Page introuvable : cette page n'existe pas. "
            "Retour à l'accueil pour recommencer.",
        )

    @application.errorhandler(405)
    def erreur_405(exc: Any) -> tuple[str, int]:
        _ = exc
        return _page_erreur(
            405,
            "Méthode non autorisée : cette méthode n'est pas autorisée ici. "
            "Retour à l'accueil pour recommencer.",
        )

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


def _consequence_derniere(etat: dict) -> str | None:
    historique = etat.get("historique")
    if isinstance(historique, list) and historique:
        derniere = historique[-1]
        if isinstance(derniere, dict):
            valeur = derniere.get("consequence", "")
            if isinstance(valeur, str) and valeur:
                return valeur
    return None


def _reponse_etape_ou_accueil() -> Any:
    etat_brut = session.get("etat")
    affaire_stockee = session.get("affaire_id")
    if not isinstance(etat_brut, dict) or not isinstance(affaire_stockee, str):
        return redirect(url_for("accueil"))
    try:
        affaire_id = _valider_id_affaire(affaire_stockee)
        affaire = _charger_affaire(affaire_id)
    except ValueError:
        return redirect(url_for("accueil"))
    etat = copy.deepcopy(etat_brut)
    if etat.get("etape_courante") is None:
        return redirect(url_for("bilan"))
    courante = etat.get("etape_courante")
    etapes = affaire.get("etapes", {})
    if not isinstance(courante, str) or courante not in etapes:
        return redirect(url_for("accueil"))
    return _page_partie(affaire, affaire_id, etat, _consequence_derniere(etat)), 200


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
        libelles=dict(LIBELLES_TRAITS),
        score_max=_score_max_bilan(bilan),
        traits_dominants=_dominants_bilan(bilan),
        metiers_details=_metiers_details_bilan(bilan),
        niveau_gravite=_niveau_gravite_bilan(bilan),
        gravite_max=_gravite_max_bilan(bilan),
    )


def _scores_bilan(bilan: dict) -> dict:
    scores = bilan.get("scores")
    return dict(scores) if isinstance(scores, dict) else {}


def _score_max_bilan(bilan: dict) -> int:
    maximum = 0
    for trait in TRAITS:
        valeur = _scores_bilan(bilan).get(trait, 0)
        if isinstance(valeur, int) and not isinstance(valeur, bool):
            if valeur > maximum:
                maximum = valeur
    return maximum


def _dominants_bilan(bilan: dict) -> list:
    dominants = bilan.get("traits_dominants")
    if isinstance(dominants, list):
        choisis = [trait for trait in dominants if trait in TRAITS]
    else:
        choisis = []
    if len(choisis) >= 2:
        return choisis[:2]
    scores = _scores_bilan(bilan)
    ordre = sorted(
        TRAITS, key=lambda nom: (-_score_nombre(scores, nom), TRAITS.index(nom))
    )
    for trait in ordre:
        if trait not in choisis:
            choisis.append(trait)
        if len(choisis) == 2:
            break
    return choisis


def _score_nombre(scores: dict, trait: str) -> int:
    valeur = scores.get(trait, 0)
    if isinstance(valeur, int) and not isinstance(valeur, bool) and valeur > 0:
        return valeur
    return 0


def _metiers_details_bilan(bilan: dict) -> list:
    details = bilan.get("metiers_details")
    if isinstance(details, list) and details:
        return list(details)
    proches = bilan.get("metiers_proches")
    if not isinstance(proches, list):
        return []
    normalises = []
    for entree in proches:
        if isinstance(entree, dict):
            nom = str(entree.get("nom", entree.get("titre", "")))
            lien = str(entree.get("lien", entree.get("pourquoi", "")))
            jouable = entree.get("jouable", entree.get("disponible"))
        else:
            nom, lien, jouable = str(entree), "", None
        if not isinstance(jouable, bool):
            jouable = nom.strip().lower() == "expert cyber"
        normalises.append({"nom": nom, "lien": lien, "jouable": jouable})
    return normalises


def _niveau_gravite_bilan(bilan: dict) -> str:
    niveau = bilan.get("niveau_gravite")
    if isinstance(niveau, str) and niveau.strip():
        return niveau
    gravite = bilan.get("gravite", 0)
    if not isinstance(gravite, int) or isinstance(gravite, bool):
        gravite = 0
    if gravite <= 2:
        return "Impact maîtrisé"
    if gravite <= 6:
        return "Impact limité"
    return "Impact élevé"


def _gravite_max_bilan(bilan: dict) -> int:
    maximum = bilan.get("gravite_max")
    if isinstance(maximum, int) and not isinstance(maximum, bool) and maximum > 0:
        return maximum
    return 99


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
    creer_app().run(debug=os.environ.get("FLASK_DEBUG", "0") == "1")
