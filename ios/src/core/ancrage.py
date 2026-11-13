"""« Carte collée » : une vraie fenêtre de navigateur (connectée à ton compte, comme sur le site) posée
exactement sur une zone de la fenêtre d'AllMyStats. Le travail Windows est fait par ancrage.ps1, qui reste
lancé en fond tant qu'une carte est affichée et reçoit ses ordres ligne par ligne."""

import hashlib
import json
import os
import queue
import subprocess
import threading

from core import chemins
from core.fenetre import _navigateurs_possibles

SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ancrage.ps1")
SANS_FENETRE = getattr(subprocess, "CREATE_NO_WINDOW", 0)
_etat = {"proc": None, "file": None, "url": None, "mode": None, "garder": False, "gardees": {}}
FICHIER_ETAT = os.path.join(chemins.DONNEES, "carte_collee.json")


def _memoriser(**infos):
    try:
        ancien = json.load(open(FICHIER_ETAT, encoding="utf-8"))
    except (OSError, ValueError):
        ancien = {}
    try:
        with open(FICHIER_ETAT, "w", encoding="utf-8") as f:
            json.dump({**ancien, **infos}, f)
    except OSError:
        pass


def _nettoyer_ancienne(ordre):
    """Après une mise à jour, l'ancienne version a pu laisser sa carte et son assistant : on les ferme."""
    try:
        ancien = json.load(open(FICHIER_ETAT, encoding="utf-8"))
    except (OSError, ValueError):
        return
    if ancien.get("pid") and ancien["pid"] != _etat["proc"].pid:
        subprocess.run(["taskkill", "/PID", str(ancien["pid"]), "/F"], capture_output=True, creationflags=SANS_FENETRE)
    for fenetre in [ancien.get("fenetre")] + list(ancien.get("gardees") or []):
        if fenetre:
            ordre(f"ANCIENNE {int(fenetre)}")
_verrou = threading.Lock()


def _assistant():
    p = _etat["proc"]
    if p and p.poll() is None:
        return p
    p = subprocess.Popen(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", SCRIPT],
                         stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                         creationflags=SANS_FENETRE, text=True, encoding="utf-8", errors="replace", bufsize=1)
    file = queue.Queue()

    def lire():
        for ligne in p.stdout:
            file.put(ligne.strip().lstrip("﻿"))
    threading.Thread(target=lire, daemon=True).start()
    _etat.update(proc=p, file=file, url=None, garder=False, gardees={})
    _nettoyer_ancienne(lambda ligne: _ecrire_ordre(p, file, ligne))
    _memoriser(pid=p.pid, fenetre=None, gardees=[])
    return p


def _ecrire_ordre(p, file, ligne, attente=8):
    try:
        p.stdin.write(ligne + "\n")
        p.stdin.flush()
        return file.get(timeout=attente)
    except (OSError, queue.Empty):
        return "DELAI"


def _ordre(ligne, attente=8):
    p = _assistant()
    file = _etat["file"]
    while not file.empty():
        file.get_nowait()
    try:
        p.stdin.write(ligne + "\n")
        p.stdin.flush()
        return file.get(timeout=attente)
    except (OSError, queue.Empty):
        return "DELAI"


def _ligne_placer(zone):
    valeurs = [zone.get(k, 0) for k in ("x", "y", "l", "h", "lv", "hv", "dpr")]
    return "PLACER " + " ".join(f"{float(v):.3f}" for v in valeurs)


def _cle(url):
    return hashlib.sha1(url.encode("utf-8")).hexdigest()[:12]


def _afficher(zone):
    _ordre(_ligne_placer(zone))
    _ordre("MONTRER")
    _etat["mode"] = _ordre(_ligne_placer(zone))   # une fois visible, la mesure est la plus juste
    return {"ok": True, "mode": _etat["mode"]}


def montrer(url, profil, zone, garder=False):
    """Affiche (ou ouvre) la carte collée sur la zone donnée. Renvoie {"ok": bool, "raison": texte}.
    garder=True (Spotify) : quand une autre page prend la place, cette fenêtre est cachée au lieu d'être
    fermée, et reprise telle quelle au retour (la musique continue)."""
    if os.name != "nt":
        return {"ok": False, "raison": "La carte collée ne marche que sur Windows."}
    with _verrou:
        if _etat["url"] == url and _ordre("EXISTE") == "True":
            return _afficher(zone)
        if _etat["url"]:
            if _etat["garder"]:
                r = _ordre(f"GARDER {_cle(_etat['url'])}")
                if r.startswith("OK"):
                    _etat["gardees"][_etat["url"]] = r.split()[1] if len(r.split()) > 1 else ""
                    _memoriser(fenetre=None, gardees=[h for h in _etat["gardees"].values() if h])
            else:
                _ordre("FERMER")
            _etat["url"] = None
        if url in _etat["gardees"]:
            _etat["gardees"].pop(url)
            _memoriser(gardees=[h for h in _etat["gardees"].values() if h])
            if _ordre(f"REPRENDRE {_cle(url)}") == "OK":
                _etat.update(url=url, garder=garder)
                return _afficher(zone)
        if _ordre("AMS") != "OK":
            return {"ok": False, "raison": "Clique dans la fenêtre d'AllMyStats puis réessaie."}
        _ordre("PHOTO")
        exe = next((e for e in _navigateurs_possibles() if os.path.isfile(e)), None)
        if not exe:
            return {"ok": False, "raison": "Il faut Microsoft Edge ou Google Chrome."}
        subprocess.Popen([exe, f"--app={url}", f"--user-data-dir={profil}", "--window-size=1200,800",
                          "--no-first-run", "--no-default-browser-check"], creationflags=SANS_FENETRE)
        trouvee = _ordre("TROUVER 15000", attente=20)
        if not trouvee.startswith("OK"):
            return {"ok": False, "raison": "La fenêtre de la carte n'a pas été trouvée."}
        _memoriser(fenetre=trouvee.split()[1] if len(trouvee.split()) > 1 else None)
        _etat.update(url=url, garder=garder)
        return _afficher(zone)   # après le premier placement, la page a sa vraie taille


def placer(zone):
    with _verrou:
        if _etat["url"]:
            _ordre(_ligne_placer(zone))
    return {"ok": True}


def cacher():
    with _verrou:
        if _etat["url"] and _etat["proc"] and _etat["proc"].poll() is None:
            _ordre("CACHER")
    return {"ok": True}
