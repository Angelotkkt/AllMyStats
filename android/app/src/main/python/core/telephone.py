"""AllMyStats sur ton téléphone : l'appli Android se relie à AllMyStats sur ton PC, par ton Wi-Fi.

- Désactivé par défaut. Quand tu l'actives (Paramètres > Téléphone), un 2e accès s'ouvre sur ton réseau local,
  à côté de celui de la fenêtre du PC (qui reste réservé au PC lui-même).
- Rien ne passe sans le code de liaison (8 caractères, affiché sur le PC et dans le QR code). Après une bonne
  liaison, le téléphone garde un jeton dans un cookie. « Nouveau code » délie tous les téléphones.
- Ce qui n'a de sens que sur le PC (installer une mise à jour, quitter, carte collée, lecture d'écran, fenêtres
  de connexion…) est refusé depuis le téléphone.
"""

import hmac
import io
import json
import os
import secrets
import sqlite3
import tempfile
import socket
import threading
import time
import zipfile
from http.server import ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

PORTS = range(8790, 8795)
ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"   # sans 0/O, 1/I/L : faciles à recopier
COOKIE = "ams_tel"

_etat = {"serveur": None, "port": None, "fil": None}
_essais = {}   # adresse IP -> [heures des mauvais codes]


def nouveau_code():
    return "".join(secrets.choice(ALPHABET) for _ in range(8))


def adresses_locales():
    """Les adresses du PC sur le réseau local (192.168…, 10…), la plus probable en premier."""
    trouvees = []
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))   # aucun paquet envoyé : sert juste à connaître la bonne carte réseau
        trouvees.append(s.getsockname()[0])
        s.close()
    except OSError:
        pass
    try:
        for ip in socket.gethostbyname_ex(socket.gethostname())[2]:
            if ip not in trouvees:
                trouvees.append(ip)
    except OSError:
        pass
    privee = lambda ip: ip.startswith(("192.168.", "10.")) or (ip.startswith("172.") and 16 <= int(ip.split(".")[1]) <= 31)
    return [ip for ip in trouvees if privee(ip)] or [ip for ip in trouvees if not ip.startswith("127.")]


def _trop_d_essais(ip):
    maintenant = time.time()
    liste = [t for t in _essais.get(ip, []) if maintenant - t < 600]
    _essais[ip] = liste
    return len(liste) >= 10


# Ce que le téléphone reçoit au moment de la liaison : tes réglages (clés d'API comprises), tes stats et les
# fichiers des jeux. JAMAIS les sessions de connexion (elles restent dans les fenêtres de connexion du PC).
FICHIERS_EXCLUS = {"carte_collee.json", "config.json"}


def exporter(dossier_donnees, fichier_bdd, fichier_config, jeux):
    """Le paquet pour le téléphone (zip en mémoire)."""
    tampon = io.BytesIO()
    with zipfile.ZipFile(tampon, "w", zipfile.ZIP_DEFLATED) as z:
        # Base de stats : copie propre même si AllMyStats écrit dedans en ce moment
        if os.path.exists(fichier_bdd):
            fd, tmp = tempfile.mkstemp(suffix=".db")
            os.close(fd)
            try:
                source, cible = sqlite3.connect(fichier_bdd), sqlite3.connect(tmp)
                with cible:
                    source.backup(cible)
                source.close()
                cible.close()
                z.write(tmp, "stats.db")
            finally:
                os.remove(tmp)
        # Réglages, sans ce qui est propre au PC ni les marques de connexion
        try:
            with open(fichier_config, encoding="utf-8") as f:
                config = json.load(f)
        except (OSError, ValueError):
            config = {}
        cles_session = {c for j in jeux.values() for c in (getattr(j, "cles_connexion", ()) or ())}
        propre = {}
        for id_jeu, reglages in config.items():
            if not isinstance(reglages, dict):
                continue
            if id_jeu == "_appli":
                propre[id_jeu] = {k: v for k, v in reglages.items() if k in ("jeux_caches",)}
                continue
            propre[id_jeu] = {k: v for k, v in reglages.items()
                              if k not in cles_session and not k.endswith("_connecte")}
        z.writestr("config.json", json.dumps(propre, ensure_ascii=False))
        # Fichiers des jeux (parties Valorant, profil Genshin, imports Call of Duty…)
        for nom in os.listdir(dossier_donnees):
            chemin = os.path.join(dossier_donnees, nom)
            if nom.endswith(".json") and nom not in FICHIERS_EXCLUS and os.path.isfile(chemin) \
                    and os.path.getsize(chemin) < 30_000_000:
                z.write(chemin, nom)
        z.writestr("synchro.json", json.dumps({"quand": time.time(), "pc": socket.gethostname()}))
    return tampon.getvalue()


BLOQUES = {("api", "maj", "fichier"), ("api", "maj", "installer"), ("api", "appli", "quitter"),
           ("api", "appli", "arriere-plan"), ("api", "appli", "telephone"), ("api", "appli", "mises-a-jour"),
           ("api", "carte-collee"), ("api", "au-revoir")}
BLOQUES_JEU = {"test-ecran", "ouvrir", "connexion"}


def classe_distante(Gestionnaire, code_actuel, export=None):
    """Le gestionnaire HTTP du téléphone : celui du PC, plus la vérification du code."""

    class GestionnaireTelephone(Gestionnaire):
        distant = True

        def _code_ok(self, propose):
            code = code_actuel()
            return bool(code and propose) and hmac.compare_digest(str(propose).upper().replace("-", ""), code)

        def _autorise(self):
            for morceau in (self.headers.get("Cookie") or "").split(";"):
                nom, _, valeur = morceau.strip().partition("=")
                if nom == COOKIE and self._code_ok(valeur):
                    return True
            return self._code_ok(self.headers.get("X-AMS-Code"))

        def _refuser(self):
            corps = ("<!doctype html><meta charset=utf-8><meta name=viewport content='width=device-width'>"
                     "<body style='font:16px system-ui;background:#141832;color:#EEF0FA;padding:30px'>"
                     "<h2>Téléphone pas encore relié</h2><p>Sur ton PC : AllMyStats &gt; Paramètres &gt; Téléphone. "
                     "Puis, dans l'appli AllMyStats du téléphone, scanne le QR code ou tape le code.</p>").encode()
            self.send_response(401)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(corps)))
            self.end_headers()
            self.wfile.write(corps)

        def _bloque(self, m):
            if tuple(m) in BLOQUES:
                return True
            return len(m) >= 4 and m[:2] == ["api", "jeux"] and m[3] in BLOQUES_JEU

        def do_GET(self):
            url = urlparse(self.path)
            if url.path == "/api/telephone/bonjour":   # l'appli vérifie qu'elle parle bien à AllMyStats
                return self._json({"appli": "AllMyStats", "nom": socket.gethostname(), "relie": self._autorise()})
            if url.path == "/relier":
                ip = self.client_address[0]
                if _trop_d_essais(ip):
                    return self._erreur("Trop d'essais : attends 10 minutes.", 429)
                code = (parse_qs(url.query).get("c") or [""])[0]
                if not self._code_ok(code):
                    _essais.setdefault(ip, []).append(time.time())
                    return self._erreur("Code incorrect : regarde le code dans Paramètres > Téléphone, sur ton PC.", 403)
                self.send_response(302)
                self.send_header("Set-Cookie", f"{COOKIE}={code_actuel()}; Max-Age=31536000; Path=/; HttpOnly; SameSite=Lax")
                self.send_header("Location", "/")
                self.end_headers()
                return
            if not self._autorise():
                return self._refuser() if not url.path.startswith("/api/") else self._erreur("Téléphone pas relié.", 401)
            if url.path == "/api/telephone/export" and export:   # la liaison : tout ce qu'il faut au téléphone
                corps = export()
                self.send_response(200)
                self.send_header("Content-Type", "application/zip")
                self.send_header("Content-Length", str(len(corps)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(corps)
                return
            if url.path == "/api/ping":
                return self._json({"appli": "AllMyStats"})   # ne compte pas comme « fenêtre du PC ouverte »
            return super().do_GET()

        def do_POST(self):
            if not self._autorise():
                return self._erreur("Téléphone pas relié.", 401)
            if self._bloque(self._morceaux()):
                return self._erreur("Ça se fait sur le PC, pas depuis le téléphone.", 403)
            return super().do_POST()

        def do_DELETE(self):
            if not self._autorise():
                return self._erreur("Téléphone pas relié.", 401)
            return super().do_DELETE()

    return GestionnaireTelephone


def demarrer(Gestionnaire, code_actuel, export=None):
    """Ouvre l'accès Wi-Fi (si pas déjà ouvert). Renvoie le port, ou None si impossible."""
    if _etat["serveur"]:
        return _etat["port"]
    classe = classe_distante(Gestionnaire, code_actuel, export)
    for port in PORTS:
        try:
            serveur = ThreadingHTTPServer(("0.0.0.0", port), classe)
        except OSError:
            continue
        fil = threading.Thread(target=serveur.serve_forever, daemon=True, name="telephone")
        fil.start()
        _etat.update(serveur=serveur, port=port, fil=fil)
        return port
    return None


def arreter():
    serveur = _etat["serveur"]
    if serveur:
        _etat.update(serveur=None, port=None, fil=None)
        threading.Thread(target=lambda: (serveur.shutdown(), serveur.server_close()), daemon=True).start()


def port():
    return _etat["port"]
