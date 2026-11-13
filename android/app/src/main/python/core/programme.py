"""Remplace AllMyStats.exe par la dernière version du programme (celle qui ouvre une vraie fenêtre native).

Les mises à jour habituelles ne changent que le code (core, jeux, web). Le programme lui-même (le .exe) change
rarement : quand il faut, AllMyStats télécharge le nouveau AllMyStats.exe depuis la publication « windows » du
dépôt GitHub, le pose à côté de l'ancien, puis un petit script remplace l'ancien dès qu'il est fermé et relance
AllMyStats. Tes stats et tes réglages (dans %APPDATA%\\AllMyStats) ne bougent pas."""

import os
import subprocess
import sys
import tempfile
import urllib.request

URL = "https://github.com/{depot}/releases/download/windows/AllMyStats.exe"
TAILLE_MIN = 5_000_000
TAILLE_MAX = 200_000_000


class ErreurProgramme(Exception):
    pass


def installer_nouveau_programme(depot):
    if os.name != "nt" or not getattr(sys, "frozen", False):
        raise ErreurProgramme("Ça ne marche que depuis AllMyStats.exe, sur Windows.")
    if not depot:
        raise ErreurProgramme("La source des mises à jour n'est pas réglée (Paramètres > Mises à jour).")
    exe = os.path.abspath(sys.executable)
    dossier = os.path.dirname(exe)
    nouveau = os.path.join(dossier, "AllMyStats.nouveau.exe")
    if not os.access(dossier, os.W_OK):
        raise ErreurProgramme(f"AllMyStats ne peut pas écrire dans le dossier {dossier}. Télécharge le nouveau "
                              "AllMyStats.exe sur le site et remplace l'ancien toi-même.")
    req = urllib.request.Request(URL.format(depot=depot), headers={"User-Agent": "AllMyStats"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r, open(nouveau, "wb") as f:
            total = 0
            while True:
                morceau = r.read(1 << 20)
                if not morceau:
                    break
                total += len(morceau)
                if total > TAILLE_MAX:
                    raise ErreurProgramme("Le fichier téléchargé est anormalement gros : abandon.")
                f.write(morceau)
    except ErreurProgramme:
        _effacer(nouveau)
        raise
    except Exception as e:
        _effacer(nouveau)
        code = getattr(e, "code", None)
        if code == 404:
            raise ErreurProgramme("La nouvelle version du programme n'est pas encore publiée : réessaie dans quelques minutes.")
        raise ErreurProgramme(f"Téléchargement impossible ({getattr(e, 'reason', e)}).")
    with open(nouveau, "rb") as f:
        debut = f.read(2)
    if debut != b"MZ" or os.path.getsize(nouveau) < TAILLE_MIN:
        _effacer(nouveau)
        raise ErreurProgramme("Le fichier téléchargé n'est pas un programme valide : abandon.")

    # Le script attend la fin d'AllMyStats, remplace le .exe et relance
    script = os.path.join(tempfile.gettempdir(), "allmystats_maj_programme.cmd")
    with open(script, "w", encoding="mbcs" if os.name == "nt" else "utf-8") as f:
        # Le .exe reste verrouillé quelques instants après la fin d'AllMyStats : on réessaie pendant 60 s
        f.write(f"""@echo off
set /a essais=0
:attente
tasklist /fi "PID eq {os.getpid()}" 2>nul | find "{os.getpid()}" >nul && (timeout /t 1 /nobreak >nul & goto attente)
:remplacer
move /y "{nouveau}" "{exe}" >nul 2>nul && goto relancer
set /a essais+=1
if %essais% gtr 60 goto fin
timeout /t 1 /nobreak >nul
goto remplacer
:relancer
rem Le nouveau programme doit démarrer « neuf », sans les réglages internes de l'ancien
set _MEIPASS2=
for /f "delims==" %%v in ('set _PYI_ 2^>nul') do set "%%v="
set PYINSTALLER_RESET_ENVIRONMENT=1
start "" "{exe}"
:fin
del "%~f0"
""")
    # Sans ça, le nouveau AllMyStats.exe croirait être un « sous-processus » de l'ancien et chercherait ses
    # fichiers dans le dossier temporaire de l'ancien, effacé entre-temps : « Failed to load Python DLL ».
    env = {k: v for k, v in os.environ.items() if not k.startswith("_PYI_") and k != "_MEIPASS2"}
    env["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
    subprocess.Popen(["cmd", "/c", script], close_fds=True, env=env,
                     creationflags=subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP)
    return "Nouvelle version du programme téléchargée : AllMyStats redémarre…"


def _effacer(chemin):
    try:
        os.remove(chemin)
    except OSError:
        pass
