"""Ouvre AllMyStats dans sa propre fenêtre (sans barre d'adresse), comme une vraie appli.

On utilise le mode « application » de Microsoft Edge (présent sur tous les Windows 10/11)
ou de Chrome. Si aucun des deux n'est trouvé, on ouvre simplement le navigateur par défaut.
"""

import os
import shutil
import subprocess
import webbrowser


def _navigateurs_possibles():
    programmes = [os.environ.get(v) for v in ("PROGRAMFILES(X86)", "PROGRAMFILES", "LOCALAPPDATA")]
    relatifs = [
        r"Microsoft\Edge\Application\msedge.exe",
        r"Google\Chrome\Application\chrome.exe",
    ]
    for rel in relatifs:
        for base in programmes:
            if base:
                yield os.path.join(base, rel)
    for nom in ("msedge", "google-chrome", "chrome", "chromium"):
        chemin = shutil.which(nom)
        if chemin:
            yield chemin


def ouvrir_fenetre(adresse, dossier_donnees):
    profil = os.path.join(dossier_donnees, "fenetre")
    for exe in _navigateurs_possibles():
        if not os.path.isfile(exe):
            continue
        try:
            subprocess.Popen(
                [
                    exe,
                    f"--app={adresse}",
                    f"--user-data-dir={profil}",   # profil séparé = vraie fenêtre à part
                    "--window-size=1320,860",
                    "--no-first-run",
                    "--no-default-browser-check",
                ],
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            return True
        except OSError:
            continue
    webbrowser.open(adresse)
    return False
