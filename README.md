# Orientation Game

Une orientation où on te regarde jouer, pas répondre à un questionnaire.
Choisis un métier (d'abord Expert cyber), vis une affaire, prends des
décisions et reçois un bilan qui cite tes vrais choix.

## Installer (venv)

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

## Lancer le jeu

```powershell
$env:SECRET_KEY = "une-phrase-secrete-locale"
.venv\Scripts\python.exe -m flask --app "app.web:creer_app()" run
```

Puis ouvre http://127.0.0.1:5000.

Sans variable `SECRET_KEY`, une clé de développement locale est utilisée
(dev uniquement, jamais en production).

## Jouer

1. Sur l'accueil, clique « Jouer l'affaire cyber ».
2. Lis le contexte et choisis une décision à chaque étape.
3. À la fin (ou via « Voir mon bilan »), lis ta fin, tes scores par trait
   (analyser, convaincre, enquêter, aider, protéger) et ton profil.

## Contrôles

```powershell
.venv\Scripts\ruff.exe check . --no-cache
.venv\Scripts\python.exe -m pytest -q
```

Le jeu fonctionne sans IA : aucune clé d'API, aucune donnée d'affaire
n'est envoyée nulle part.
