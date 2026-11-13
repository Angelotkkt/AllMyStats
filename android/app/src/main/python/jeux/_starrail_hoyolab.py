"""Honkai: Star Rail via HoYoLAB (Battle Chronicle, notes en temps réel, calendrier mensuel du Pionnier).

Mêmes cookies HoYoLAB que pour Genshin (c'est le même compte HoYoverse). Ils restent sur ton PC.
"""

import time
from datetime import datetime

from ._genshin_hoyolab import ErreurHoyolab, _appel, lire_cookies, NOMS_COOKIES  # noqa: F401

URL_RECORD = "https://bbs-api-os.hoyolab.com/game_record/hkrpg/api/"
URL_CARTE = "https://bbs-api-os.hoyolab.com/game_record/card/wapi/"
URL_CALENDRIER = "https://sg-public-api.hoyolab.com/event/srledger/month"
SERVEURS = {"6": "prod_official_usa", "7": "prod_official_euro", "8": "prod_official_asia",
            "9": "prod_official_cht"}
ID_JEU = 6   # Honkai: Star Rail sur HoYoLAB


def serveur_de(uid):
    return SERVEURS.get(str(uid)[:-8])


def recuperer(uid, cookies):
    """Renvoie (valeurs, sections, avertissements)."""
    serveur = serveur_de(uid)
    if not serveur:
        raise ErreurHoyolab("Cet UID n'est pas sur un serveur HoYoLAB international.")
    p = {"server": serveur, "role_id": uid}
    index = _appel(URL_RECORD + "index", p, cookies)   # si ça échoue, toute la source échoue
    valeurs, sections, avertissements = {}, [], []

    stats = index.get("stats") or {}
    for cle, nom in (("active_days", "jours_actifs"), ("avatar_num", "persos_total"),
                     ("achievement_num", "succes"), ("chest_num", "coffres")):
        if isinstance(stats.get(cle), (int, float)):
            valeurs[nom] = stats[cle]

    # --- Tous les persos ---
    persos = []
    try:
        persos = _appel(URL_RECORD + "avatar/info", {**p, "need_wiki": "true"}, cookies).get("avatar_list") or []
    except ErreurHoyolab:
        pass
    persos = persos or index.get("avatar_list") or []
    if persos:
        persos.sort(key=lambda a: (-(a.get("rarity") or 0), -(a.get("level") or 0), a.get("name", "")))
        sections.append({
            "titre": "Tous tes personnages",
            "icone": "persos",
            "compact": True,
            "cartes": [{
                "titre": a.get("name", "?"),
                "sous_titre": f"Niv. {a.get('level', '?')} · E{a.get('rank', 0)}",
                "image": a.get("icon") or a.get("image"),
                "couleur": "#e6b85c" if a.get("rarity") == 5 else "#a77fd8",
                "badges": [a.get("element").capitalize()] if a.get("element") else [],
            } for a in persos],
        })
        valeurs["persos_5"] = sum(1 for a in persos if a.get("rarity") == 5)

    # --- Notes en temps réel ---
    try:
        notes = _appel(URL_RECORD + "note", p, cookies)
        lignes = []
        puissance, maxi = notes.get("current_stamina"), notes.get("max_stamina")
        if puissance is not None:
            reste = int(notes.get("stamina_recover_time") or 0)
            pleine = "pleine !" if reste <= 0 else f"pleine à {datetime.fromtimestamp(time.time() + reste):%H:%M}"
            lignes.append(["Puissance de Pionnier", f"{puissance}/{maxi} · {pleine}", "resine"])
        if notes.get("current_reserve_stamina"):
            lignes.append(["Réserve de puissance", f"{notes['current_reserve_stamina']}"
                           + (" (pleine)" if notes.get("is_reserve_stamina_full") else ""), "resine"])
        if notes.get("max_train_score"):
            lignes.append(["Entraînement quotidien", f"{notes.get('current_train_score', 0)}/{notes['max_train_score']}",
                           "commission"])
        if notes.get("max_rogue_score"):
            lignes.append(["Univers simulé (points de la semaine)",
                           f"{notes.get('current_rogue_score', 0)}/{notes['max_rogue_score']}", "exploration"])
        if notes.get("weekly_cocoon_limit"):
            restants = notes.get("weekly_cocoon_cnt", 0)
            lignes.append(["Échos de guerre (récompenses restantes)", f"{restants}/{notes['weekly_cocoon_limit']}",
                           "abysse"])
        missions = notes.get("expeditions") or []
        if missions:
            finies = sum(1 for e in missions if e.get("status") == "Finished")
            lignes.append(["Missions terminées", f"{finies}/{len(missions)}", "expedition"])
        if lignes:
            sections.insert(0, {"titre": "En ce moment", "icone": "resine", "lignes": lignes})
    except ErreurHoyolab as e:
        avertissements.append(f"Notes en temps réel : {e}")

    # --- Calendrier du Pionnier (Jade stellaire et passes gagnés) ---
    try:
        cal = _appel(URL_CALENDRIER, {"uid": uid, "region": serveur, "month": datetime.now().strftime("%Y%m"),
                                      "lang": "fr-fr"}, cookies)
        mois, jour = cal.get("month_data") or {}, cal.get("day_data") or {}
        if "current_hcoin" in mois:
            valeurs["jade_mois"] = mois["current_hcoin"]
        if "current_rails_pass" in mois:
            valeurs["passes_mois"] = mois["current_rails_pass"]
        if "current_hcoin" in jour:
            valeurs["jade_jour"] = jour["current_hcoin"]
        sources = mois.get("group_by") or []
        if sources:
            sections.append({
                "titre": "D'où vient ton Jade stellaire ce mois-ci",
                "icone": "jade_stellaire",
                "lignes": [[s.get("action_name") or s.get("action") or "?",
                            f"{s.get('num', 0)} ({s.get('percent', 0)} %)", "jade_stellaire"]
                           for s in sorted(sources, key=lambda s: -(s.get("num") or 0))],
            })
    except ErreurHoyolab as e:
        avertissements.append(f"Calendrier du Pionnier : {e}")

    return valeurs, sections, avertissements


# ---------------------------------------------------------------- après la connexion

def comptes_starrail(cookies):
    """Liste les comptes Star Rail liés au compte HoYoLAB (avec UID, pseudo, niveau)."""
    def lire():
        data = _appel(URL_CARTE + "getGameRecordCard", {"uid": cookies.get("ltuid_v2")}, cookies)
        return [c for c in data.get("list") or [] if c.get("game_id") == ID_JEU]

    try:
        comptes = lire()
    except ErreurHoyolab:
        comptes = []
    if not comptes:   # le Battle Chronicle est peut-être caché : on le rend visible puis on réessaie
        changer_visibilite(cookies, 1)
        comptes = lire()
    return comptes


def changer_visibilite(cookies, reglage, public=True):
    try:
        _appel(URL_CARTE + "changeDataSwitch", None, cookies,
               {"switch_id": reglage, "is_public": public, "game_id": ID_JEU})
        return True
    except ErreurHoyolab:
        return False


def tout_rendre_visible(cookies, compte):
    interrupteurs = compte.get("data_switches") or [{"switch_id": i, "is_public": False} for i in (1, 2, 3)]
    for s in interrupteurs:
        if not s.get("is_public"):
            changer_visibilite(cookies, s.get("switch_id"))
