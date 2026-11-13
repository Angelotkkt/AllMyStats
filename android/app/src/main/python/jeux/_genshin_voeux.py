"""Historique des vœux Genshin, récupéré automatiquement.

Quand tu ouvres l'historique des vœux dans le jeu (sur ce PC), Genshin garde un lien secret
dans son cache. On le lit, puis on télécharge tes vœux. Le lien expire au bout de 24 h :
il suffit de rouvrir l'historique en jeu pour en avoir un nouveau.
Tes vœux sont gardés pour toujours dans genshin_voeux.json (le jeu, lui, n'en garde qu'un an).
"""

import glob
import json
import os
import re
import time
import urllib.error
import urllib.request
from urllib.parse import parse_qs, urlencode, urlparse

URL_VOEUX = "https://public-operation-hk4e-sg.hoyoverse.com/gacha_info/api/getGachaLog"
BANNIERES = {
    "301": ("Événement personnage", 90),
    "302": ("Événement arme", 80),
    "500": ("Vœux chroniques", 90),
    "200": ("Vœu permanent", 90),
    "100": ("Vœux de débutant", 90),
}
MOTIF_LIEN = re.compile(r"https://[^\s\x00\"'<>]*?(?:getGachaLog|webview_gacha)[^\s\x00\"'<>]*")


class ErreurVoeux(Exception):
    pass


# ---------------------------------------------------------------- trouver le lien

def chercher_lien_dans_le_jeu():
    """Cherche le lien de l'historique des vœux dans le cache de Genshin (PC Windows)."""
    profil = os.environ.get("USERPROFILE") or os.path.expanduser("~")
    journaux = [
        os.path.join(profil, "AppData", "LocalLow", "miHoYo", "Genshin Impact", "output_log.txt"),
        os.path.join(profil, "AppData", "LocalLow", "miHoYo", "原神", "output_log.txt"),
    ]
    dossiers = set()
    for journal in journaux:
        try:
            with open(journal, "r", encoding="utf-8", errors="ignore") as f:
                texte = f.read()
        except OSError:
            continue
        for m in re.finditer(r"([A-Za-z]:[/\\][^\r\n:<>|\"]*?(?:GenshinImpact_Data|YuanShen_Data))", texte):
            dossiers.add(m.group(1))

    caches = []
    for dossier in dossiers:
        caches += glob.glob(os.path.join(dossier, "webCaches", "*", "Cache", "Cache_Data", "data_2"))
        caches += glob.glob(os.path.join(dossier, "webCaches", "Cache", "Cache_Data", "data_2"))
    caches = sorted(set(caches), key=lambda c: os.path.getmtime(c), reverse=True)

    for cache in caches:
        try:
            with open(cache, "rb") as f:
                contenu = f.read().decode("latin-1")
        except OSError:
            continue
        liens = [l for l in MOTIF_LIEN.findall(contenu) if "authkey=" in l]
        if liens:
            return liens[-1]
    return None


# ---------------------------------------------------------------- télécharger

def _page(params):
    requete = urllib.request.Request(URL_VOEUX + "?" + urlencode(params),
                                     headers={"User-Agent": "AllMyStats/1.0"})
    try:
        with urllib.request.urlopen(requete, timeout=20) as rep:
            data = json.loads(rep.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, OSError):
        raise ErreurVoeux("Impossible de joindre le serveur des vœux.")
    code = data.get("retcode")
    if code == -101:
        raise ErreurVoeux("le lien a expiré (24 h) : rouvre l'historique des vœux en jeu.")
    if code != 0:
        raise ErreurVoeux(f"{data.get('message', 'erreur')} (code {code}) : rouvre l'historique des vœux en jeu.")
    return (data.get("data") or {}).get("list") or []


def charger_stock(chemin):
    try:
        with open(chemin, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def mettre_a_jour(lien, chemin_stock):
    """Télécharge les nouveaux vœux. Renvoie (stock, nombre_de_nouveaux)."""
    q = {k: v[0] for k, v in parse_qs(urlparse(lien.strip()).query).items()}
    if "authkey" not in q:
        raise ErreurVoeux("le lien ne contient pas de clé (authkey).")
    base = {k: q[k] for k in ("authkey", "authkey_ver", "sign_type", "auth_appid", "game_biz", "region") if k in q}
    base.setdefault("authkey_ver", "1")
    base.setdefault("sign_type", "2")
    base.setdefault("auth_appid", "webview_gacha")
    base.setdefault("game_biz", "hk4e_global")
    base.update({"lang": "fr", "size": "20", "page": "1"})

    stock = charger_stock(chemin_stock)
    nouveaux = 0
    for type_banniere in BANNIERES:
        fin = "0"
        while True:
            liste = _page({**base, "gacha_type": type_banniere, "end_id": fin})
            deja_connu = False
            for v in liste:
                if v["id"] in stock:
                    deja_connu = True
                    break
                stock[v["id"]] = {
                    "id": v["id"], "uid": v.get("uid"), "banniere": type_banniere,
                    "nom": v.get("name"), "type": v.get("item_type"),
                    "rarete": int(v.get("rank_type") or 3), "date": v.get("time"),
                }
                nouveaux += 1
            if deja_connu or len(liste) < 20:
                break
            fin = liste[-1]["id"]
            time.sleep(0.35)  # on ne bombarde pas le serveur
        time.sleep(0.2)

    with open(chemin_stock, "w", encoding="utf-8") as f:
        json.dump(stock, f, ensure_ascii=False)
    return stock, nouveaux


# ---------------------------------------------------------------- analyser

def analyser(stock, uid, image_de=None):
    """Calcule les stats et la section à afficher à partir des vœux enregistrés."""
    voeux = list(stock.values())
    if uid and any(v.get("uid") == uid for v in voeux):
        voeux = [v for v in voeux if v.get("uid") == uid]
    if not voeux:
        return {}, None
    voeux.sort(key=lambda v: int(v["id"]))

    par_banniere = {}
    for v in voeux:
        par_banniere.setdefault(v["banniere"], []).append(v)

    lignes, cinq = [], []
    pity_actuel = {}
    for code, (nom, max_pity) in BANNIERES.items():
        liste = par_banniere.get(code)
        if not liste:
            continue
        compteur = 0
        for v in liste:
            compteur += 1
            if v["rarete"] == 5:
                cinq.append({**v, "pity": compteur, "nom_banniere": nom})
                compteur = 0
        pity_actuel[code] = compteur
        nb5 = sum(1 for v in liste if v["rarete"] == 5)
        lignes.append([nom, f"{len(liste)} vœux · {nb5} × 5★ · pity {compteur}/{max_pity}", "voeu"])

    valeurs = {
        "voeux_total": len(voeux),
        "primos_depensees": len(voeux) * 160,
        "cinq_etoiles": len(cinq),
        "quatre_etoiles": sum(1 for v in voeux if v["rarete"] == 4),
    }
    if "301" in pity_actuel:
        valeurs["pity_perso"] = pity_actuel["301"]
    if "302" in pity_actuel:
        valeurs["pity_arme"] = pity_actuel["302"]
    if cinq:
        valeurs["pity_moyen"] = round(sum(c["pity"] for c in cinq) / len(cinq), 1)

    cartes = []
    for c in reversed(cinq[-12:]):
        est_perso = (c.get("type") or "").lower().startswith(("perso", "charac"))
        cartes.append({
            "titre": c["nom"],
            "sous_titre": (c.get("date") or "")[:10],
            "image": image_de(c["nom"]) if image_de else None,   # perso ou arme
            "icone": "cinq_etoiles" if est_perso else "arme",
            "couleur": "#e6b85c",
            "badges": [c["nom_banniere"], f"Pity {c['pity']}"],
        })

    section = {"titre": "Vœux", "icone": "voeu", "lignes": lignes}
    sections = [section]
    if cartes:
        sections.append({"titre": "Tes derniers 5★", "icone": "cinq_etoiles", "cartes": cartes})
    return valeurs, sections
