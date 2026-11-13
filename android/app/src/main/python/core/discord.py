"""Discord : affiche AllMyStats dans ton statut (« Joue à AllMyStats ») avec son logo et une courte description
(Rich Presence).

Ça passe par le canal local que l'application Discord ouvre sur le PC (\\\\.\\pipe\\discord-ipc-0 sous Windows) :
rien ne part sur Internet depuis AllMyStats, aucun compte ni jeton Discord n'est utilisé. Discord a seulement
besoin de l'identifiant public de « l'application Discord » AllMyStats (créée sur discord.com/developers) : c'est
elle qui donne le nom affiché et le logo."""

import json
import os
import socket
import struct
import threading
import time
import uuid

# Identifiant public de l'application Discord « AllMyStats » (Discord Developer Portal > Applications).
# Peut aussi être collé dans Paramètres > Discord.
ID_APPLICATION = ""
SITE = "https://angelotkkt.github.io/AllMyStats/"
LOGO = "https://angelotkkt.github.io/AllMyStats/icone.png"
DESCRIPTION = "Toutes mes stats de jeux au même endroit"

OP_HANDSHAKE, OP_FRAME, OP_CLOSE = 0, 1, 2


class ErreurDiscord(Exception):
    pass


class _Canal:
    """Le canal local vers l'application Discord (tube nommé sous Windows, socket ailleurs)."""

    def __init__(self):
        self.f = self.sock = None
        for i in range(10):
            try:
                if os.name == "nt":
                    self.f = open(rf"\\.\pipe\discord-ipc-{i}", "r+b", buffering=0)
                else:
                    base = os.environ.get("XDG_RUNTIME_DIR") or os.environ.get("TMPDIR") or "/tmp"
                    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                    s.settimeout(5)
                    s.connect(os.path.join(base, f"discord-ipc-{i}"))
                    self.sock = s
                return
            except (OSError, AttributeError):
                continue
        raise ErreurDiscord("Discord n'est pas ouvert sur ce PC.")

    def _ecrire(self, donnees):
        if self.f:
            self.f.write(donnees)
        else:
            self.sock.sendall(donnees)

    def _lire(self, n):
        morceaux, reste = [], n
        while reste:
            m = self.f.read(reste) if self.f else self.sock.recv(reste)
            if not m:
                raise ErreurDiscord("Discord a fermé la connexion.")
            morceaux.append(m)
            reste -= len(m)
        return b"".join(morceaux)

    def envoyer(self, op, data):
        corps = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self._ecrire(struct.pack("<II", op, len(corps)) + corps)
        op_r, taille = struct.unpack("<II", self._lire(8))
        reponse = json.loads(self._lire(taille).decode("utf-8") or "{}")
        if op_r == OP_CLOSE:
            raise ErreurDiscord(reponse.get("message") or "Discord a refusé la connexion.")
        if reponse.get("evt") == "ERROR":
            raise ErreurDiscord((reponse.get("data") or {}).get("message") or "Discord a refusé le statut.")
        return reponse

    def fermer(self):
        try:
            if self.f:
                self.f.close()
            if self.sock:
                self.sock.close()
        except OSError:
            pass


class Presence:
    def __init__(self):
        self._canal = None
        self._id = None
        self._derniere = None
        self._verrou = threading.Lock()
        self.debut = int(time.time())
        self.erreur = ""
        self.connecte = False

    def _connecter(self, id_application):
        if self._canal and self._id == id_application:
            return
        self.fermer()
        canal = _Canal()
        try:
            canal.envoyer(OP_HANDSHAKE, {"v": 1, "client_id": id_application})
        except Exception:
            canal.fermer()
            raise
        self._canal, self._id, self._derniere = canal, id_application, None

    def mettre(self, id_application, page=""):   # page : gardé pour compatibilité, plus affiché
        """Affiche (ou met à jour) le statut. Ne fait rien si rien n'a changé."""
        activite = {
            "type": 0,
            "details": DESCRIPTION,
            "timestamps": {"start": self.debut},
            "assets": {"large_image": LOGO, "large_text": "AllMyStats : stats de Genshin, Valorant, CS2, Fortnite…"},
        }
        with self._verrou:
            if self._canal and self._derniere == activite and self._id == id_application:
                return
            try:
                self._connecter(id_application)
                self._canal.envoyer(OP_FRAME, {"cmd": "SET_ACTIVITY", "nonce": str(uuid.uuid4()),
                                               "args": {"pid": os.getpid(), "activity": activite}})
                self._derniere, self.erreur, self.connecte = activite, "", True
            except (ErreurDiscord, OSError, ValueError, struct.error) as e:
                self.fermer()
                texte = str(e) or "Discord ne répond pas."
                if "client" in texte.lower() and "id" in texte.lower():
                    texte = "Discord refuse cet identifiant d'application : vérifie l'Application ID."
                self.erreur = texte

    def effacer(self):
        with self._verrou:
            if not self._canal:
                return
            try:
                self._canal.envoyer(OP_FRAME, {"cmd": "SET_ACTIVITY", "nonce": str(uuid.uuid4()),
                                               "args": {"pid": os.getpid()}})
            except (ErreurDiscord, OSError, ValueError, struct.error):
                pass
            self.fermer()

    def fermer(self):
        if self._canal:
            self._canal.fermer()
        self._canal, self._derniere, self.connecte = None, None, False
