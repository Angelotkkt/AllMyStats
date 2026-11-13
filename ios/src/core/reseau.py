"""Connexion à Internet : évite les proxys Windows « morts ».

Certains programmes (VPN, logiciels de contrôle, outils réseau) laissent un proxy réglé dans Windows même
une fois fermés. Les navigateurs s'en sortent, mais Python l'utilise tel quel et plus rien ne passe.
Au démarrage, AllMyStats vérifie que le proxy répond ; sinon, il se connecte en direct.
"""

import os
import socket
import ssl
import urllib.parse
import urllib.request

ETAT = {"proxy": None, "ignore": False}
CERTIFICATS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cacert.pem")


def contexte_https():
    """Les autorités de confiance de Windows + la liste à jour de Mozilla livrée avec AllMyStats (cacert.pem).
    Certains Windows gardent d'anciens certificats Let's Encrypt expirés : Python construit alors une chaîne
    qui passe par eux et refuse le site (« certificate has expired »), alors que les navigateurs s'en sortent.
    Avec la liste de Mozilla en plus, la bonne chaîne est trouvée. La vérification reste complète."""
    ctx = ssl.create_default_context()
    if os.path.exists(CERTIFICATS):
        try:
            ctx.load_verify_locations(CERTIFICATS)
        except (ssl.SSLError, OSError):
            pass
    return ctx


def preparer():
    gestionnaires = [urllib.request.HTTPSHandler(context=contexte_https())]
    proxys = urllib.request.getproxies()
    proxy = proxys.get("https") or proxys.get("http")
    ETAT["proxy"] = proxy
    if proxy:
        adresse = urllib.parse.urlparse(proxy if "://" in proxy else "http://" + proxy)
        try:
            socket.create_connection((adresse.hostname, adresse.port or 80), timeout=3).close()
        except (OSError, TypeError, ValueError):
            ETAT["ignore"] = True
            gestionnaires.append(urllib.request.ProxyHandler({}))
            print(f"[réseau] le proxy {proxy} ne répond pas : connexion directe")
    urllib.request.install_opener(urllib.request.build_opener(*gestionnaires))


def raison(e):
    """Explication courte d'une erreur réseau (pour l'afficher)."""
    r = getattr(e, "reason", None) or e
    texte = str(r)[:140] or type(r).__name__
    return f"{type(r).__name__} : {texte}"
