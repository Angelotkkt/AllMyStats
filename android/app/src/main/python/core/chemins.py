"""Où se trouvent les fichiers, que le programme soit lancé en .py ou en .exe."""

import os
import shutil
import sys

FIGE = getattr(sys, "frozen", False)  # True quand on tourne depuis AllMyStats.exe

# Le code (core, jeux, web) : là où se trouve ce fichier
RESSOURCES = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.environ.get("AMS_WEB") or os.path.join(RESSOURCES, "web")
# Sur le téléphone (appli Android autonome) : pas de mises à jour du PC, pas de Windows
ANDROID = os.environ.get("AMS_ANDROID") == "1"

# Tes données : %APPDATA%\AllMyStats avec le .exe, dossier data/ avec la version .py
DONNEES = os.environ.get("MESSTATS_DONNEES") or (
    os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"), "AllMyStats") if FIGE
    else os.path.join(RESSOURCES, "data"))
os.makedirs(DONNEES, exist_ok=True)

FICHIER_BDD = os.path.join(DONNEES, "stats.db")
FICHIER_CONFIG = os.path.join(DONNEES, "config.json")
FICHIER_JOURNAL = os.path.join(DONNEES, "journal.txt")
DOSSIER_APP = os.path.join(DONNEES, "app")


def recuperer_anciennes_donnees():
    """Si tu as déjà utilisé la version .py (dossier data/ à côté du .exe), on reprend ses données."""
    if not FIGE or os.path.exists(FICHIER_BDD):
        return
    dossier_exe = os.path.dirname(sys.executable)
    for source, cible in [
        (os.path.join(dossier_exe, "data", "stats.db"), FICHIER_BDD),
        (os.path.join(dossier_exe, "data", "config.json"), FICHIER_CONFIG),
        (os.path.join(dossier_exe, "config.json"), FICHIER_CONFIG),
    ]:
        if os.path.exists(source) and not os.path.exists(cible):
            try:
                shutil.copy2(source, cible)
            except OSError:
                pass


recuperer_anciennes_donnees()
