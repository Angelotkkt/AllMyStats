"""Détecte automatiquement tous les jeux présents dans ce dossier."""

import importlib
import inspect
import pkgutil
import sys
import traceback

from .base import Jeu


def _noms_des_modules():
    noms = {m.name for m in pkgutil.iter_modules(__path__)}
    # Dans le .exe, on regarde aussi la liste des modules emballés par PyInstaller
    for importeur in sys.meta_path:
        toc = getattr(importeur, "toc", None)
        if toc:
            for nom in toc:
                if nom.startswith(__name__ + ".") and nom.count(".") == 1:
                    noms.add(nom.split(".", 1)[1])
    return sorted(noms)


def charger_jeux():
    jeux = {}
    for nom in _noms_des_modules():
        if nom.startswith("_") or nom == "base":
            continue
        try:
            mod = importlib.import_module(f"{__name__}.{nom}")
        except Exception:
            print(f"[!] Impossible de charger le jeu « {nom} » :")
            traceback.print_exc()
            continue
        for _, classe in inspect.getmembers(mod, inspect.isclass):
            if issubclass(classe, Jeu) and classe is not Jeu and classe.id:
                jeux[classe.id] = classe()
    # Tri : par famille (ou nom du jeu), puis ordre dans la famille
    return dict(sorted(jeux.items(), key=lambda e: ((e[1].famille or e[1].nom).lower(), e[1].ordre, e[1].nom.lower())))
