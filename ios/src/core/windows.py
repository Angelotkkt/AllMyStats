"""Petits outils Windows : jeux lancés, capture de la fenêtre d'un jeu + lecture du texte (OCR de Windows).

Tout passe par des commandes déjà présentes dans Windows 10/11 (tasklist, PowerShell) :
rien à installer. Sur un autre système, ces fonctions ne font simplement rien.
"""

import os
import re
import subprocess
import threading
import time
from datetime import datetime

from core import chemins

SANS_FENETRE = getattr(subprocess, "CREATE_NO_WINDOW", 0)
SCRIPT_ECRAN = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lire_ecran.ps1")


def _executer(args, timeout=30):
    try:
        r = subprocess.run(args, capture_output=True, timeout=timeout, creationflags=SANS_FENETRE)
    except (OSError, subprocess.TimeoutExpired):
        return ""
    for codage in ("utf-8", "cp850", "cp1252"):
        try:
            return r.stdout.decode(codage)
        except UnicodeDecodeError:
            continue
    return r.stdout.decode("utf-8", errors="ignore")


def processus_lances(noms):
    """Renvoie l'ensemble des programmes de `noms` (ex: "GenshinImpact.exe") qui tournent."""
    if os.name != "nt":
        return set()
    voulus = {n.lower(): n for n in noms}
    trouves = set()
    for ligne in _executer(["tasklist", "/FO", "CSV", "/NH"]).splitlines():
        nom = ligne.split('","')[0].strip().strip('"')
        if nom.lower() in voulus:
            trouves.add(voulus[nom.lower()])
    return trouves


def debut_processus(nom_sans_exe):
    """Heure (timestamp) à laquelle le programme a été lancé, ou None."""
    if os.name != "nt":
        return None
    sortie = _executer(["powershell", "-NoProfile", "-Command",
                        f"(Get-Process -Name '{nom_sans_exe}' -ErrorAction SilentlyContinue | "
                        f"Sort-Object StartTime | Select-Object -First 1).StartTime.ToUniversalTime()"
                        f".ToString('yyyy-MM-ddTHH:mm:ss')"]).strip()
    try:
        return datetime.fromisoformat(sortie + "+00:00").timestamp()
    except ValueError:
        return None


def processus_par_motif(motif):
    """Noms (avec .exe) des programmes lancés dont le nom correspond à l'expression `motif`."""
    if os.name != "nt":
        return set()
    trouves = set()
    for ligne in _executer(["tasklist", "/FO", "CSV", "/NH"]).splitlines():
        nom = ligne.split('","')[0].strip().strip('"')
        if nom and re.match(motif, nom, re.I):
            trouves.add(nom)
    return trouves


# ---------------------------------------------------------------- lecture de l'écran

_VERROU_ECRAN = threading.Lock()   # une seule capture à la fois (surveillance + bouton « Tester »)
DERNIERS_ESSAIS = {}               # dernier résultat de lecture, par liste de programmes


def analyser_sortie_ecran(sortie):
    """Transforme ce qu'écrit lire_ecran.ps1 en dictionnaire (voir le haut du script)."""
    r = {"etat": "SANS_REPONSE", "message": "", "lignes": []}
    dans_texte = False
    for brute in (sortie or "").splitlines():
        ligne = brute.strip().lstrip("﻿")
        if dans_texte:
            if ligne:
                r["lignes"].append(ligne)
            continue
        if not ligne or ":" not in ligne:
            continue
        cle, valeur = ligne.split(":", 1)
        cle, valeur = cle.strip().upper(), valeur.strip()
        if cle == "TEXTE":
            dans_texte = True
        elif cle == "ETAT":
            etat, _, message = valeur.partition(" ")
            r["etat"], r["message"] = etat or "ERREUR", message.strip()
        elif cle == "DEVANT":
            prog, _, titre = valeur.partition("|")
            r["devant"] = {"processus": prog, "titre": titre}
        elif cle in ("PROCESSUS", "TITRE", "FENETRE", "LUMINOSITE", "LANGUE"):
            r[cle.lower()] = valeur
    return r


def lire_ecran_complet(processus, garder_essai=True, motif="", activer=False):
    """Capture la fenêtre au premier plan si c'est l'un des `processus` (noms sans .exe) et la lit.
    Renvoie toujours un dictionnaire : r["etat"] == "OK" quand le texte a été lu (dans r["lignes"])."""
    if os.name != "nt":
        return {"etat": "PAS_WINDOWS", "message": "", "lignes": [], "quand": time.time()}
    r = _lancer_script(["-Processus", ",".join(processus)] + (["-Motif", motif] if motif else [])
                       + (["-Activer"] if activer else []))
    if garder_essai:
        DERNIERS_ESSAIS[",".join(processus)] = {k: v for k, v in r.items() if k != "lignes"} | {
            "nb_lignes": len(r["lignes"])}
    return r


def lire_image(chemin):
    """Lit le texte d'une image déjà enregistrée (ex : capture d'écran du téléphone). Même résultat que
    lire_ecran_complet : r["etat"] == "OK" et le texte dans r["lignes"]."""
    if os.name != "nt":
        return {"etat": "PAS_WINDOWS", "message": "", "lignes": [], "quand": time.time()}
    return _lancer_script(["-Fichier", os.path.abspath(chemin)])


def _lancer_script(arguments):
    if not os.path.exists(SCRIPT_ECRAN):
        return {"etat": "ERREUR", "message": "le fichier lire_ecran.ps1 est introuvable", "lignes": [],
                "quand": time.time()}
    with _VERROU_ECRAN:
        image = os.path.join(chemins.DONNEES, "capture_temp.png")
        try:
            p = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", SCRIPT_ECRAN,
                                "-Image", image] + arguments,
                               capture_output=True, timeout=60, creationflags=SANS_FENETRE)
            sortie = p.stdout.decode("utf-8", errors="replace")
            erreurs = p.stderr.decode("utf-8", errors="replace").strip()
        except subprocess.TimeoutExpired:
            sortie, erreurs = "", "PowerShell n'a pas répondu en 60 secondes"
        except OSError as e:
            sortie, erreurs = "", f"PowerShell ne se lance pas ({e})"
        finally:
            try:
                os.remove(image)  # on ne garde jamais la capture
            except OSError:
                pass
    r = analyser_sortie_ecran(sortie)
    if r["etat"] == "SANS_REPONSE":
        r["message"] = (erreurs.splitlines() or [""])[0][:300]
    r["quand"] = time.time()
    return r


def lire_ecran(processus):
    """Si la fenêtre au premier plan appartient à l'un de `processus` (noms sans .exe),
    la capture et renvoie les lignes de texte lues par l'OCR de Windows. Sinon None."""
    resultat = lire_ecran_details(processus)
    return resultat[1] if resultat else None


def lire_ecran_details(processus):
    """Comme lire_ecran, mais renvoie (infos, lignes) avec infos = {"processus": ..., "titre": ...}."""
    r = lire_ecran_complet(processus)
    if r["etat"] != "OK":
        return None
    return {"processus": r.get("processus", ""), "titre": r.get("titre", "")}, r["lignes"]


def dernier_essai(processus):
    return DERNIERS_ESSAIS.get(",".join(processus))


def bip():
    """Petit son Windows (pour prévenir qu'une capture vient d'être faite)."""
    if os.name != "nt":
        return
    try:
        subprocess.Popen(["powershell", "-NoProfile", "-Command",
                          "[System.Media.SystemSounds]::Asterisk.Play(); Start-Sleep -Milliseconds 800"],
                         creationflags=SANS_FENETRE)
    except OSError:
        pass


def titre_fenetre(nom_sans_exe):
    """Titre de la fenêtre principale d'un programme lancé (ou "")."""
    if os.name != "nt":
        return ""
    return _executer(["powershell", "-NoProfile", "-Command",
                      f"(Get-Process -Name '{nom_sans_exe}' -ErrorAction SilentlyContinue | "
                      f"Where-Object {{ $_.MainWindowTitle }} | Select-Object -First 1).MainWindowTitle"]).strip()
