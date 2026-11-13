"""Connexion à Internet : évite les proxys Windows « morts ».

Certains programmes (VPN, logiciels de contrôle, outils réseau) laissent un proxy réglé dans Windows même
une fois fermés. Les navigateurs s'en sortent, mais Python l'utilise tel quel et plus rien ne passe.
Au démarrage, AllMyStats vérifie que le proxy répond ; sinon, il se connecte en direct.
"""

import socket
import urllib.parse
import urllib.request

ETAT = {"proxy": None, "ignore": False}


def preparer():
    proxys = urllib.request.getproxies()
    proxy = proxys.get("https") or proxys.get("http")
    ETAT["proxy"] = proxy
    if not proxy:
        return
    adresse = urllib.parse.urlparse(proxy if "://" in proxy else "http://" + proxy)
    try:
        socket.create_connection((adresse.hostname, adresse.port or 80), timeout=3).close()
    except (OSError, TypeError, ValueError):
        ETAT["ignore"] = True
        urllib.request.install_opener(urllib.request.build_opener(urllib.request.ProxyHandler({})))
        print(f"[réseau] le proxy {proxy} ne répond pas : connexion directe")


def raison(e):
    """Explication courte d'une erreur réseau (pour l'afficher)."""
    r = getattr(e, "reason", None) or e
    texte = str(r)[:140] or type(r).__name__
    return f"{type(r).__name__} : {texte}"
