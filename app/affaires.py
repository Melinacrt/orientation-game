"""Chargement et validation d'une affaire (format ``data/format-affaire.json``).

Le jeu fonctionne sans IA : ce module se contente de lire un JSON et de
vérifier sa cohérence structurelle. Toute erreur est signalée par une
``ValueError`` au message rédigé en français, jamais par une traceback brute.
"""

import json
from pathlib import Path

TRAITS_AUTORISES = frozenset({"analyser", "convaincre", "enqueter", "aider", "proteger"})

CLES_OBLIGATOIRES = ("id", "metier", "titre", "contexte", "debut", "etapes", "fins")


def charger_affaire(chemin: str | Path) -> dict:
    """Charge une affaire depuis un fichier JSON et valide sa structure.

    Args:
        chemin: Chemin (``str`` ou ``pathlib.Path``) vers le fichier JSON.

    Returns:
        Le dictionnaire de l'affaire dont la structure a été validée.

    Raises:
        ValueError: Si le fichier est introuvable, si le JSON est malformé ou
            si la structure ne respecte pas le format attendu.
    """
    fichier = _vers_chemin(chemin)

    try:
        contenu = fichier.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise ValueError(f"Fichier d'affaire introuvable : {fichier}") from exc
    except OSError as exc:
        raise ValueError(f"Impossible de lire le fichier d'affaire : {exc}") from exc

    try:
        affaire = json.loads(contenu)
    except json.JSONDecodeError as exc:
        message = f"JSON malformé dans {fichier.name} : {exc.msg} "
        message += f"(ligne {exc.lineno}, colonne {exc.colno})."
        raise ValueError(message) from exc

    _valider_structure(affaire)
    return affaire


def _vers_chemin(chemin: str | Path) -> Path:
    if isinstance(chemin, Path):
        return chemin
    if isinstance(chemin, str):
        if not chemin.strip():
            raise ValueError("Le chemin fourni est vide.")
        return Path(chemin)
    raise ValueError("Le chemin doit être une chaîne de caractères ou un pathlib.Path.")


def _valider_structure(affaire: object) -> None:
    if not isinstance(affaire, dict):
        raise ValueError("L'affaire doit être un objet JSON.")

    manquantes = [cle for cle in CLES_OBLIGATOIRES if cle not in affaire]
    if manquantes:
        raise ValueError(f"Clés obligatoires manquantes : {', '.join(manquantes)}.")

    for cle in ("id", "metier", "titre", "contexte"):
        if not _est_texte_non_vide(affaire[cle]):
            raise ValueError(f"La clé « {cle} » doit être une chaîne non vide.")

    etapes = affaire["etapes"]
    if not isinstance(etapes, dict) or not etapes:
        raise ValueError("La clé « etapes » doit être un objet JSON non vide.")

    for identifiant, etape in etapes.items():
        _valider_etape(identifiant, etape, etapes)

    if not isinstance(affaire["debut"], str) or affaire["debut"] not in etapes:
        raise ValueError("La clé « debut » doit référencer une étape existante.")

    fins = affaire["fins"]
    if not isinstance(fins, list) or not fins:
        raise ValueError("La clé « fins » doit être une liste non vide.")

    for fin in fins:
        _valider_fin(fin)


def _valider_etape(identifiant: str, etape: object, etapes: dict) -> None:
    if not isinstance(etape, dict):
        raise ValueError(f"L'étape « {identifiant} » doit être un objet JSON.")

    if not _est_texte_non_vide(etape.get("texte")):
        raise ValueError(f"L'étape « {identifiant} » doit avoir un « texte » non vide.")

    choix_liste = etape.get("choix")
    if not isinstance(choix_liste, list) or not choix_liste:
        raise ValueError(f"L'étape « {identifiant} » doit avoir une liste « choix » non vide.")

    for choix in choix_liste:
        _valider_choix(identifiant, choix, etapes)


def _valider_choix(etape_id: str, choix: object, etapes: dict) -> None:
    if not isinstance(choix, dict):
        raise ValueError(f"Un choix de l'étape « {etape_id} » doit être un objet JSON.")

    for cle in ("id", "label"):
        if not _est_texte_non_vide(choix.get(cle)):
            raise ValueError(
                f"Choix de l'étape « {etape_id} » : « {cle} » doit être une chaîne non vide."
            )

    traits = choix.get("traits")
    if not isinstance(traits, dict):
        raise ValueError(
            f"Les « traits » d'un choix de l'étape « {etape_id} » doivent être un objet JSON."
        )
    for trait, points in traits.items():
        if trait not in TRAITS_AUTORISES:
            autorises = ", ".join(sorted(TRAITS_AUTORISES))
            raise ValueError(f"Trait non autorisé « {trait} » (autorisés : {autorises}).")
        if not _est_entier(points):
            raise ValueError(f"Le score du trait « {trait} » doit être un entier.")

    gravite = choix.get("gravite")
    if not _est_entier(gravite):
        raise ValueError(
            f"La « gravite » du choix de l'étape « {etape_id} » doit être un entier."
        )
    if gravite < 0:
        raise ValueError(f"La « gravite » du choix de l'étape « {etape_id} » doit être >= 0.")

    suite = choix.get("suite")
    if suite is not None and suite not in etapes:
        raise ValueError(
            f"La « suite » d'un choix de l'étape « {etape_id} » doit référencer une étape "
            "existante ou être nulle."
        )


def _valider_fin(fin: object) -> None:
    if not isinstance(fin, dict):
        raise ValueError("Chaque fin doit être un objet JSON.")

    for cle in ("gravite_max", "titre"):
        if cle not in fin:
            raise ValueError(f"Une fin doit contenir la clé « {cle} ».")

    if not _est_entier(fin["gravite_max"]):
        raise ValueError("Le « gravite_max » d'une fin doit être un entier.")


def _est_texte_non_vide(valeur: object) -> bool:
    return isinstance(valeur, str) and bool(valeur.strip())


def _est_entier(valeur: object) -> bool:
    return isinstance(valeur, int) and not isinstance(valeur, bool)
