"""Chiffrement du système d'amis, avec seulement la bibliothèque standard de Python.

- Chaque joueur a une paire de clés Diffie-Hellman (groupe MODP 2048 bits de la RFC 3526). Deux joueurs en tirent
  une clé commune que personne d'autre ne peut calculer : elle protège les messages entre eux (demandes,
  réponses, clé de profil).
- Le profil (les stats) est chiffré avec une « clé de profil » donnée seulement aux amis acceptés.
- Chiffrement : flux HMAC-SHA256 en mode compteur, puis code d'authentification HMAC-SHA256 (chiffrer puis
  authentifier). Un message modifié ou forgé sans la clé est rejeté.
- Le code ami est l'empreinte (SHA-256) de la clé publique : impossible de se faire passer pour quelqu'un."""

import hashlib
import hmac
import secrets

# RFC 3526, groupe 14 (2048 bits), générateur 2
P = int(
    "FFFFFFFFFFFFFFFFC90FDAA22168C234C4C6628B80DC1CD129024E088A67CC74020BBEA63B139B22514A08798E3404DD"
    "EF9519B3CD3A431B302B0A6DF25F14374FE1356D6D51C245E485B576625E7EC6F44C42E9A637ED6B0BFF5CB6F406B7ED"
    "EE386BFB5A899FA5AE9F24117C4B1FE649286651ECE45B3DC2007CB8A163BF0598DA48361C55D39A69163FA8FD24CF5F"
    "83655D23DCA3AD961C62F356208552BB9ED529077096966D670C354E4ABC9804F1746C08CA18217C32905E462E36CE3B"
    "E39E772C180E86039B2783A2EC07A28FB5C55DF06F4C52C9DE2BCBF6955817183995497CEA956AE515D2261898FA0510"
    "15728E5A8AACAA68FFFFFFFFFFFFFFFF", 16)
G = 2
TAILLE = 256      # octets d'une clé publique


def nouvelle_paire():
    """(clé privée, clé publique) sous forme d'entiers."""
    prive = secrets.randbits(320) | (1 << 319)
    return prive, pow(G, prive, P)


def publique_valide(y):
    return isinstance(y, int) and 2 <= y <= P - 2


def en_hex(y):
    return y.to_bytes(TAILLE, "big").hex()


def depuis_hex(texte):
    try:
        y = int(texte, 16) if isinstance(texte, str) and len(texte) == TAILLE * 2 else None
    except ValueError:
        return None
    return y if y is not None and publique_valide(y) else None


def empreinte(y):
    """Le code ami : 24 caractères tirés de la clé publique."""
    return hashlib.sha256(b"AMS-code" + y.to_bytes(TAILLE, "big")).hexdigest()[:24]


def cle_commune(prive, publique_autre):
    """Clé partagée entre moi et l'autre (la même des deux côtés)."""
    if not publique_valide(publique_autre):
        raise ValueError("clé publique invalide")
    s = pow(publique_autre, prive, P)
    return hashlib.sha256(b"AMS-paire" + s.to_bytes(TAILLE, "big")).digest()


def _sous_cles(cle):
    return (hmac.new(cle, b"chiffrement", hashlib.sha256).digest(),
            hmac.new(cle, b"authentification", hashlib.sha256).digest())


def _flux(kc, nonce, n):
    blocs = []
    for i in range((n + 31) // 32):
        blocs.append(hmac.new(kc, nonce + i.to_bytes(4, "big"), hashlib.sha256).digest())
    return b"".join(blocs)[:n]


def chiffrer(cle, donnees):
    kc, km = _sous_cles(cle)
    nonce = secrets.token_bytes(16)
    chiffre = bytes(a ^ b for a, b in zip(donnees, _flux(kc, nonce, len(donnees))))
    tag = hmac.new(km, nonce + chiffre, hashlib.sha256).digest()[:16]
    return nonce + tag + chiffre


def dechiffrer(cle, paquet):
    """Les données, ou None si le paquet a été modifié ou n'est pas pour cette clé."""
    if not isinstance(paquet, (bytes, bytearray)) or len(paquet) < 32:
        return None
    kc, km = _sous_cles(cle)
    nonce, tag, chiffre = paquet[:16], paquet[16:32], paquet[32:]
    if not hmac.compare_digest(tag, hmac.new(km, nonce + chiffre, hashlib.sha256).digest()[:16]):
        return None
    return bytes(a ^ b for a, b in zip(chiffre, _flux(kc, nonce, len(chiffre))))
