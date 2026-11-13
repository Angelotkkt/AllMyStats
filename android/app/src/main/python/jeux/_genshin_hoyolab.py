"""Genshin via HoYoLAB (Battle Chronicle, notes en temps réel, journal du voyageur).

Il faut les cookies de ton compte HoYoLAB (ltoken_v2, ltuid_v2, ltmid_v2).
Ils restent sur ton PC, dans config.json : ne les partage avec personne.
"""

import hashlib
import json
import random
import string
import time
import urllib.error
import urllib.request
from datetime import datetime
from urllib.parse import urlencode

SEL_DS = "6s25p5ox5y14umn1p61aqyyvbvvl3lrt"
URL_RECORD = "https://sg-public-api.hoyolab.com/event/game_record/genshin/api/"
URL_CARTE = "https://bbs-api-os.hoyolab.com/game_record/card/wapi/"
URL_JOURNAL = "https://sg-hk4e-api.hoyolab.com/event/ysledgeros/month_info"
SERVEURS = {"6": "os_usa", "7": "os_euro", "8": "os_asia", "18": "os_asia", "9": "os_cht"}
NOMS_COOKIES = ("ltoken_v2", "ltuid_v2", "ltmid_v2")

MESSAGES = {
    -100: "Ta connexion HoYoLAB a expiré : clique sur « Se connecter avec HoYoLAB ».",
    10001: "Ta connexion HoYoLAB a expiré : clique sur « Se connecter avec HoYoLAB ».",
    10101: "HoYoLAB : trop de demandes aujourd'hui, réessaie demain.",
    10102: "Tes données ne sont pas visibles : clique sur « Se connecter avec HoYoLAB », AllMyStats les active tout seul.",
    1009: "HoYoLAB ne trouve pas ce compte Genshin (vérifie l'UID).",
    1034: "HoYoLAB demande une vérification : ouvre ton Battle Chronicle sur hoyolab.com une fois, puis réessaie.",
    5003: "HoYoLAB demande une vérification : ouvre ton Battle Chronicle sur hoyolab.com une fois, puis réessaie.",
}


class ErreurHoyolab(Exception):
    pass


def serveur_de(uid):
    return SERVEURS.get(str(uid)[:-8])


def lire_cookies(reglages):
    """Accepte « valeur » ou « ltoken_v2=valeur » (et même toute la ligne de cookies collée d'un coup)."""
    cookies = {}
    for nom in NOMS_COOKIES:
        brut = (reglages.get(nom) or "").strip().strip('"').strip(";").strip()
        for morceau in brut.split(";"):
            if "=" in morceau:
                cle, val = morceau.split("=", 1)
                if cle.strip() in NOMS_COOKIES and val.strip():
                    cookies[cle.strip()] = val.strip()
            elif morceau.strip() and nom not in cookies:
                cookies[nom] = morceau.strip()
    return cookies


def _ds():
    t = int(time.time())
    r = "".join(random.choices(string.ascii_letters, k=6))
    h = hashlib.md5(f"salt={SEL_DS}&t={t}&r={r}".encode()).hexdigest()
    return f"{t},{r},{h}"


def _appel(url, params, cookies, corps=None):
    if params:
        url += "?" + urlencode(params)
    entetes = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/124.0 Safari/537.36",
        "Accept": "application/json",
        "Cookie": "; ".join(f"{k}={v}" for k, v in cookies.items()),
        "Referer": "https://act.hoyolab.com/",
        "Origin": "https://act.hoyolab.com",
        "ds": _ds(),
        "x-rpc-app_version": "1.5.0",
        "x-rpc-client_type": "5",
        "x-rpc-language": "fr-fr",
        "x-rpc-lang": "fr-fr",
    }
    donnees = None
    if corps is not None:
        donnees = json.dumps(corps).encode()
        entetes["Content-Type"] = "application/json"
    requete = urllib.request.Request(url, data=donnees, headers=entetes)
    try:
        with urllib.request.urlopen(requete, timeout=20) as rep:
            reponse = json.loads(rep.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise ErreurHoyolab(f"HoYoLAB ne répond pas correctement (code {e.code}).")
    except (urllib.error.URLError, TimeoutError, OSError):
        raise ErreurHoyolab("Impossible de joindre HoYoLAB. Vérifie ta connexion internet.")
    code = reponse.get("retcode")
    if code != 0:
        raise ErreurHoyolab(MESSAGES.get(code, f"HoYoLAB : {reponse.get('message', '?')} (code {code})"))
    return reponse.get("data") or {}


def recuperer(uid, cookies):
    """Renvoie (valeurs, sections, avertissements)."""
    serveur = serveur_de(uid)
    if not serveur:
        raise ErreurHoyolab("Cet UID n'est pas sur un serveur HoYoLAB international.")
    p = {"server": serveur, "role_id": uid}

    index = _appel(URL_RECORD + "index", p, cookies)  # si ça échoue, toute la source échoue
    valeurs, sections, avertissements = {}, [], []

    stats = index.get("stats") or {}

    def nb(cle):
        v = stats.get(cle)
        return v if isinstance(v, (int, float)) else 0

    if "active_day_number" in stats:
        valeurs["jours_actifs"] = nb("active_day_number")
    if "avatar_number" in stats:
        valeurs["persos_total"] = nb("avatar_number")
    coffres = sum(nb(k) for k in stats if k.endswith("chest_number"))
    oculi = sum(nb(k) for k in stats if k.endswith("culus_number"))
    if coffres:
        valeurs["coffres"] = coffres
    if oculi:
        valeurs["oculi"] = oculi
    if "way_point_number" in stats:
        valeurs["teleporteurs"] = nb("way_point_number")
    if "domain_number" in stats:
        valeurs["domaines"] = nb("domain_number")

    # --- Exploration par région ---
    regions = [r for r in index.get("world_explorations") or [] if not r.get("parent_id")]
    if regions:
        pourcents = [(r.get("exploration_percentage") or 0) / 10 for r in regions]
        valeurs["exploration"] = round(sum(pourcents) / len(pourcents), 1)
        cartes = []
        for r in sorted(regions, key=lambda r: r.get("id", 0)):
            lignes = []
            if r.get("level"):
                lignes.append(["Réputation / offrande", f"Niv. {r['level']}"])
            for o in r.get("offerings") or []:
                lignes.append([o.get("name", "?"), f"Niv. {o.get('level', '?')}"])
            cartes.append({
                "titre": r.get("name", "?"),
                "sous_titre": f"{(r.get('exploration_percentage') or 0) / 10:.1f} % exploré".replace(".", ","),
                "image": r.get("icon"),
                "icone": "exploration",
                "couleur": "#6fc4a8",
                "progression": (r.get("exploration_percentage") or 0) / 1000,
                "lignes": lignes,
            })
        sections.append({"titre": "Exploration", "icone": "exploration", "cartes": cartes})

    # --- Tous les persos ---
    persos = []
    try:
        persos = (_appel(URL_RECORD + "character/list", None, cookies, {"role_id": uid, "server": serveur})
                  .get("list") or [])
    except ErreurHoyolab:
        persos = index.get("avatars") or []
    if persos:
        persos.sort(key=lambda a: (-(a.get("rarity") or 0), -(a.get("level") or 0), a.get("name", "")))
        sections.append({
            "titre": "Tous tes personnages",
            "icone": "persos",
            "compact": True,
            "cartes": [{
                "titre": a.get("name", "?"),
                "sous_titre": f"Niv. {a.get('level', '?')} · C{a.get('actived_constellation_num', 0)}",
                "image": a.get("icon") or a.get("image"),
                "couleur": "#e6b85c" if a.get("rarity") == 5 else "#a77fd8",
                "badges": [a.get("element")] if a.get("element") else [],
            } for a in persos],
        })
        valeurs["persos_5"] = sum(1 for a in persos if a.get("rarity") == 5)

    # --- Notes en temps réel ---
    try:
        notes = _appel(URL_RECORD + "dailyNote", p, cookies)
        lignes = []
        resine, resine_max = notes.get("current_resin"), notes.get("max_resin")
        if resine is not None:
            reste = int(notes.get("resin_recovery_time") or 0)
            pleine = "pleine !" if reste <= 0 else f"pleine à {datetime.fromtimestamp(time.time() + reste):%H:%M}"
            lignes.append(["Résine originelle", f"{resine}/{resine_max} · {pleine}", "resine"])
        if notes.get("total_task_num"):
            bonus = " · bonus récupéré" if notes.get("is_extra_task_reward_received") else ""
            lignes.append(["Commissions", f"{notes.get('finished_task_num', 0)}/{notes['total_task_num']}{bonus}",
                           "commission"])
        if notes.get("max_home_coin"):
            lignes.append(["Monnaie du royaume", f"{notes.get('current_home_coin', 0)}/{notes['max_home_coin']}",
                           "royaume"])
        exp = notes.get("expeditions") or []
        if exp:
            finies = sum(1 for e in exp if e.get("status") == "Finished")
            lignes.append(["Expéditions terminées", f"{finies}/{len(exp)}", "expedition"])
        transfo = notes.get("transformer") or {}
        if transfo.get("obtained"):
            pret = (transfo.get("recovery_time") or {}).get("reached")
            lignes.append(["Transformateur paramétrique", "prêt !" if pret else "en recharge", "transformateur"])
        if lignes:
            sections.insert(0, {"titre": "En ce moment", "icone": "resine", "lignes": lignes})
    except ErreurHoyolab as e:
        avertissements.append(f"Notes en temps réel : {e}")

    # --- Journal du voyageur (primogemmes et mora gagnées) ---
    try:
        journal = _appel(URL_JOURNAL, {"month": datetime.now().month, "region": serveur, "uid": uid,
                                       "lang": "fr-fr"}, cookies)
        mois = journal.get("month_data") or {}
        jour = journal.get("day_data") or {}
        if "current_primogems" in mois:
            valeurs["primos_mois"] = mois["current_primogems"]
        if "current_mora" in mois:
            valeurs["mora_mois"] = mois["current_mora"]
        if "current_primogems" in jour:
            valeurs["primos_jour"] = jour["current_primogems"]
        sources = mois.get("group_by") or []
        if sources:
            sections.append({
                "titre": "D'où viennent tes primogemmes ce mois-ci",
                "icone": "primogemme",
                "lignes": [[s.get("action", "?"), f"{s.get('num', 0)} ({s.get('percent', 0)} %)", "primogemme"]
                           for s in sorted(sources, key=lambda s: -(s.get("num") or 0))],
            })
    except ErreurHoyolab as e:
        avertissements.append(f"Journal du voyageur : {e}")

    return valeurs, sections, avertissements


# ---------------------------------------------------------------- après la connexion

def comptes_genshin(cookies):
    """Liste les comptes Genshin liés au compte HoYoLAB (avec UID, pseudo, niveau)."""
    def lire():
        data = _appel(URL_CARTE + "getGameRecordCard", {"uid": cookies.get("ltuid_v2")}, cookies)
        return [c for c in data.get("list") or [] if c.get("game_id") == 2]

    try:
        comptes = lire()
    except ErreurHoyolab:
        comptes = []
    if not comptes:  # le Battle Chronicle est peut-être caché : on le rend visible puis on réessaie
        changer_visibilite(cookies, 1)
        comptes = lire()
    return comptes


def changer_visibilite(cookies, reglage, public=True):
    """1 = Battle Chronicle visible, 2 = détails des persos, 3 = notes en temps réel."""
    try:
        _appel(URL_CARTE + "changeDataSwitch", None, cookies,
               {"switch_id": reglage, "is_public": public, "game_id": 2})
        return True
    except ErreurHoyolab:
        return False


def tout_rendre_visible(cookies, compte):
    interrupteurs = compte.get("data_switches") or [{"switch_id": i, "is_public": False} for i in (1, 2, 3)]
    actives = 0
    for s in interrupteurs:
        if not s.get("is_public") and changer_visibilite(cookies, s.get("switch_id")):
            actives += 1
    return actives
