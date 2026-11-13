"""Connexion à un compte de jeu via une vraie fenêtre de navigateur.

AllMyStats ouvre Edge (ou Chrome) avec un profil à lui, sur la page de connexion du jeu.
Tu te connectes normalement (mot de passe, Google, captcha… tout marche).
Dès que c'est fait, AllMyStats lit les cookies de connexion de CETTE fenêtre (pas ceux de ton
navigateur habituel) grâce au protocole de débogage de Chrome, puis ferme la fenêtre.
Ton mot de passe ne passe jamais par AllMyStats.
"""

import base64
import json
import os
import socket
import struct
import subprocess
import time
import urllib.request
from urllib.parse import urlparse

from core.fenetre import _navigateurs_possibles


class ErreurConnexion(Exception):
    pass


# ---------------------------------------------------------------- mini client WebSocket

class _CDP:
    """Juste assez de WebSocket pour parler au navigateur (Chrome DevTools Protocol)."""

    def __init__(self, url_ws):
        u = urlparse(url_ws)
        self.sock = socket.create_connection((u.hostname, u.port), timeout=10)
        cle = base64.b64encode(os.urandom(16)).decode()
        self.sock.sendall((f"GET {u.path} HTTP/1.1\r\nHost: {u.hostname}:{u.port}\r\n"
                           f"Upgrade: websocket\r\nConnection: Upgrade\r\n"
                           f"Sec-WebSocket-Key: {cle}\r\nSec-WebSocket-Version: 13\r\n\r\n").encode())
        reponse = b""
        while b"\r\n\r\n" not in reponse:
            morceau = self.sock.recv(4096)
            if not morceau:
                raise ConnectionError("le navigateur a refusé la connexion")
            reponse += morceau
        entete, self.tampon = reponse.split(b"\r\n\r\n", 1)
        if b" 101 " not in entete.split(b"\r\n")[0]:
            raise ConnectionError("le navigateur a refusé la connexion")
        self.compteur = 0

    def _lire(self, n):
        while len(self.tampon) < n:
            morceau = self.sock.recv(65536)
            if not morceau:
                raise ConnectionError("connexion au navigateur perdue")
            self.tampon += morceau
        donnees, self.tampon = self.tampon[:n], self.tampon[n:]
        return donnees

    def _envoyer(self, texte, code=0x1):
        donnees = texte.encode() if isinstance(texte, str) else texte
        n = len(donnees)
        entete = bytes([0x80 | code])
        if n < 126:
            entete += bytes([0x80 | n])
        elif n < 65536:
            entete += bytes([0x80 | 126]) + struct.pack(">H", n)
        else:
            entete += bytes([0x80 | 127]) + struct.pack(">Q", n)
        masque = os.urandom(4)
        self.sock.sendall(entete + masque + bytes(b ^ masque[i % 4] for i, b in enumerate(donnees)))

    def _message(self):
        morceaux = b""
        while True:
            o1, o2 = self._lire(2)
            fin, code, n = o1 & 0x80, o1 & 0x0F, o2 & 0x7F
            if n == 126:
                n = struct.unpack(">H", self._lire(2))[0]
            elif n == 127:
                n = struct.unpack(">Q", self._lire(8))[0]
            masque = self._lire(4) if o2 & 0x80 else None
            donnees = self._lire(n)
            if masque:
                donnees = bytes(b ^ masque[i % 4] for i, b in enumerate(donnees))
            if code == 0x8:
                raise ConnectionError("le navigateur a fermé la connexion")
            if code == 0x9:  # ping -> pong
                self._envoyer(donnees, 0xA)
                continue
            if code in (0x0, 0x1, 0x2):
                morceaux += donnees
                if fin:
                    return morceaux.decode("utf-8", errors="replace")

    def appel(self, methode, params=None):
        self.compteur += 1
        self._envoyer(json.dumps({"id": self.compteur, "method": methode, "params": params or {}}))
        while True:
            msg = json.loads(self._message())
            if msg.get("id") == self.compteur:
                if "error" in msg:
                    raise ConnectionError(msg["error"].get("message", "erreur du navigateur"))
                return msg.get("result") or {}

    def fermer(self):
        try:
            self.sock.close()
        except OSError:
            pass


# ---------------------------------------------------------------- connexion

def _port_libre():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _lancer(url, dossier_profil, arguments_en_plus=()):
    exe = next((e for e in _navigateurs_possibles() if os.path.isfile(e)), None)
    if not exe:
        raise ErreurConnexion("Il faut Microsoft Edge ou Google Chrome pour la fenêtre de connexion.")
    port = _port_libre()
    os.makedirs(dossier_profil, exist_ok=True)
    processus = subprocess.Popen(
        [exe, f"--remote-debugging-port={port}", f"--user-data-dir={dossier_profil}",
         "--no-first-run", "--no-default-browser-check", "--window-size=560,820",
         f"--app={url}", *arguments_en_plus],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    for _ in range(60):
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=1) as r:
                return processus, json.loads(r.read())["webSocketDebuggerUrl"]
        except Exception:
            if processus.poll() is not None:
                break
            time.sleep(0.5)
    processus.kill()
    raise ErreurConnexion("La fenêtre n'a pas pu s'ouvrir (une fenêtre de connexion est peut-être déjà ouverte : "
                          "ferme-la puis réessaie).")


def _terminer(cdp, processus):
    if cdp:
        try:
            cdp.appel("Browser.close")
        except Exception:
            pass
        cdp.fermer()
    try:
        processus.wait(timeout=5)
    except subprocess.TimeoutExpired:
        processus.kill()


def _cookies(cdp, domaine):
    """domaine : un texte ("hoyolab.com") ou une liste de textes ("callofduty.com", "activision.com")."""
    domaines = [domaine] if isinstance(domaine, str) else list(domaine)
    liste = cdp.appel("Storage.getCookies").get("cookies", [])
    cookies = {}
    for d in domaines:  # le premier domaine de la liste est prioritaire
        for c in liste:
            if d in c.get("domain", "") and c["name"] not in cookies:
                cookies[c["name"]] = c["value"]
    return cookies


def recuperer_cookies(url, dossier_profil, domaine, est_connecte, delai_max=600, arguments_en_plus=()):
    """Ouvre `url` dans une fenêtre dédiée et attend que `est_connecte(cookies)` soit vrai.

    `cookies` est un dict {nom: valeur} des cookies dont le domaine contient `domaine`.
    Renvoie ce dict. Lève ErreurConnexion si la fenêtre est fermée ou si c'est trop long.
    """
    processus, url_ws = _lancer(url, dossier_profil, arguments_en_plus)
    cdp = None
    try:
        try:
            cdp = _CDP(url_ws)
        except (ConnectionError, OSError) as e:
            raise ErreurConnexion(f"La fenêtre de connexion ne répond pas ({e}). Ferme-la et réessaie.")
        debut = time.time()
        while time.time() - debut < delai_max:
            try:
                cookies = _cookies(cdp, domaine)
            except (ConnectionError, OSError):
                cdp = None
                raise ErreurConnexion("Fenêtre de connexion fermée avant la fin.")
            if est_connecte(cookies):
                return cookies
            time.sleep(1.5)
        raise ErreurConnexion("Trop long : la connexion a été annulée au bout de 10 minutes.")
    finally:
        _terminer(cdp, processus)


def lire_session(url, dossier_profil, domaine, arguments_en_plus=()):
    """Relit, sans rien afficher, les cookies gardés par la fenêtre de connexion.
    Rien n'est écrit sur le disque par AllMyStats : la session reste dans le profil du navigateur."""
    processus, url_ws = _lancer(url, dossier_profil, ("--headless=new", *arguments_en_plus))
    cdp = None
    try:
        cdp = _CDP(url_ws)
        return _cookies(cdp, domaine)
    except (ConnectionError, OSError):
        raise ErreurConnexion("Impossible de relire ta connexion.")
    finally:
        _terminer(cdp, processus)


def _urls(cdp):
    return [t.get("url", "") for t in cdp.appel("Target.getTargets").get("targetInfos", [])
            if t.get("type") == "page"]


def attendre_url(url, dossier_profil, motif, delai_max=600, cache=False, arguments_en_plus=(), cookies_ok=None):
    """Ouvre `url` (fenêtre visible, ou cachée si cache=True) et attend qu'une page arrive sur une adresse
    contenant `motif` (ex : « access_token= » après une connexion). Renvoie (adresse, cookies).
    cookies_ok = (domaine, fonction) : on s'arrête aussi dès que fonction(cookies du domaine) est vraie
    (adresse vide dans ce cas). Lève ErreurConnexion si la fenêtre est fermée ou si c'est trop long."""
    extra = (("--headless=new",) if cache else ()) + tuple(arguments_en_plus)
    processus, url_ws = _lancer(url, dossier_profil, extra)
    cdp = None
    try:
        try:
            cdp = _CDP(url_ws)
        except (ConnectionError, OSError) as e:
            raise ErreurConnexion(f"La fenêtre de connexion ne répond pas ({e}). Ferme-la et réessaie.")
        debut = time.time()
        while time.time() - debut < delai_max:
            try:
                adresses = _urls(cdp)
            except (ConnectionError, OSError):
                cdp = None
                raise ErreurConnexion("Fenêtre de connexion fermée avant la fin.")
            trouvee = next((a for a in adresses if motif in a), None)
            cookies = {}
            if cookies_ok or trouvee:
                try:
                    cookies = _cookies(cdp, cookies_ok[0]) if cookies_ok else {}
                except (ConnectionError, OSError):
                    cookies = {}
            if trouvee:
                return trouvee, cookies
            if cookies_ok and cookies_ok[1](cookies) and time.time() - debut > 3:
                return "", cookies
            time.sleep(0.15 if not cookies_ok else 0.4)
        raise ErreurConnexion("Trop long : la connexion a été annulée." if not cache else "Session expirée.")
    finally:
        _terminer(cdp, processus)
