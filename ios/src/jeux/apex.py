"""Apex Legends — automatique, comme un tracker.

Source : l'API d'Apex Legends Status (apexlegendsapi.com, clé gratuite à coller dans les Réglages) : rang classé
et points (RP), niveau du compte, légende sélectionnée, stats de tes légendes (celles des trackers que tu
affiches sur tes bannières en jeu), statut en ligne. Le temps de jeu est aussi mesuré quand Apex est lancé ici.
"""

import os

from core.temps_de_jeu import SuiviJeu

from . import _api as api
from .base import ErreurJeu, Jeu, Stat

URL = "https://api.mozambiquehe.re/bridge"
PLATEFORMES = {"pc": "PC", "origin": "PC", "ea": "PC", "steam": "PC", "ps": "PS4", "ps4": "PS4", "ps5": "PS4",
               "playstation": "PS4", "xbox": "X1", "x1": "X1", "xbl": "X1", "switch": "SWITCH"}
RANGS = {"Rookie": "Recrue", "Bronze": "Bronze", "Silver": "Argent", "Gold": "Or", "Platinum": "Platine",
         "Diamond": "Diamant", "Master": "Maître", "Apex Predator": "Prédateur Apex", "Unranked": "Non classé"}
TRACKERS = {"kills": "Éliminations", "damage": "Dégâts", "wins": "Victoires", "games_played": "Parties",
            "kd": "K/D", "headshots": "Headshots", "top_3": "Top 3", "revives": "Réanimations"}


def _tracker(data, *motifs):
    """Cherche un tracker de bannière (« BR Kills », « Damage »…) dans la liste d'une légende."""
    for t in data or []:
        nom = (t.get("key") or t.get("name") or "").lower()
        if any(m in nom for m in motifs):
            return api.nombre(t.get("value"))
    return None


class ApexLegends(Jeu):
    id = "apex"
    nom = "Apex Legends"
    icone = "jeu_apex"
    couleur = "#DA3A35"
    stat_vedette = "points_rang"

    reglages = [
        {"cle": "pseudo_apex", "nom": "Pseudo (compte EA)", "aide": "Ton pseudo EA / Origin (ou PSN / Xbox, voir plus bas)."},
        {"cle": "cle_apex", "nom": "Clé Apex Legends API", "secret": True,
         "aide": "Gratuite : connecte-toi sur portal.apexlegendsapi.com, puis copie ta clé. "
                 "Colle-la ici : ne la partage avec personne.",
         "lien": "https://portal.apexlegendsapi.com/"},
        {"cle": "plateforme_apex", "nom": "Plateforme (facultatif)", "optionnel": True, "avance": True,
         "aide": "PC (par défaut), PS4 (PlayStation), X1 (Xbox) ou SWITCH."},
    ]

    R, C, T = "Classé", "Combat (trackers de tes bannières)", "Temps de jeu"
    stats = [
        Stat("points_rang", "Rang", "auto", groupe=R, icone="apex_rang", aide="Tes points de classé (RP)"),
        Stat("niveau", "Niveau du compte", "auto", groupe=R, icone="cod_niveau"),
        Stat("eliminations", "Éliminations", "auto", groupe=C, icone="cod_elimination",
             aide="Somme des trackers « éliminations » visibles sur tes bannières"),
        Stat("degats", "Dégâts", "auto", groupe=C, icone="valo_degats"),
        Stat("victoires", "Victoires", "auto", groupe=C, icone="cod_victoire"),
        Stat("kd", "Ratio K/D", "auto", decimales=2, groupe=C, icone="cod_kd"),
        Stat("legendes_suivies", "Légendes avec des stats", "auto", groupe=C, icone="apex_legende"),
        Stat("temps_total", "Temps suivi par AMS", "auto", unite="h", decimales=1, groupe=T, icone="historique"),
        Stat("temps_7j", "Ces 7 derniers jours", "auto", unite="h", decimales=1, groupe=T, icone="calendrier_semaine"),
        Stat("sessions", "Sessions", "auto", groupe=T, icone="manette"),
    ]

    def _suivi(self, dossier):
        return SuiviJeu(os.path.join(dossier, "apex_temps.json"), ("r5apex.exe", "r5apex_dx12.exe"))

    def surveiller(self, reglages, dossier):
        suivi = self._suivi(dossier)
        suivi.verifier()
        return suivi.resume()[0]

    def nom_du_compte(self, reglages):
        return api.pseudo_garde(self.id) or reglages.get("pseudo_apex", "")

    def recuperer(self, reglages, dossier):
        pseudo = (reglages.get("pseudo_apex") or "").strip()
        cle = (reglages.get("cle_apex") or "").strip()
        if not pseudo or not cle:
            raise ErreurJeu("Mets ton pseudo et ta clé Apex Legends API gratuite dans les Réglages.")
        plateforme = PLATEFORMES.get((reglages.get("plateforme_apex") or "pc").strip().lower(), "PC")
        try:
            r = api.get_json(URL, {"auth": cle, "player": pseudo, "platform": plateforme}, service="Apex Legends API")
        except api.ErreurApi as e:
            if e.code in (401, 403):
                raise ErreurJeu("Clé Apex Legends API refusée : vérifie-la dans les Réglages.")
            if e.code == 404:
                raise ErreurJeu(f"Joueur « {pseudo} » introuvable sur {plateforme}. Vérifie ton pseudo EA et la plateforme.")
            if e.code == 429:
                raise ErreurJeu("Apex Legends API demande d'attendre un peu : réessaie dans une minute.")
            raise
        if not isinstance(r, dict) or r.get("Error") or r.get("error"):
            raise ErreurJeu(f"Apex Legends API : {(r or {}).get('Error') or (r or {}).get('error') or 'réponse vide'}")

        glob = r.get("global") or {}
        rang = glob.get("rank") or {}
        valeurs = {}
        if api.nombre(rang.get("rankScore")) is not None:
            valeurs["points_rang"] = int(api.nombre(rang["rankScore"]))
        if api.nombre(glob.get("level")) is not None:
            valeurs["niveau"] = int(api.nombre(glob["level"]))

        legendes = ((r.get("legends") or {}).get("all")) or {}
        total = {"kills": 0, "damage": 0, "wins": 0}
        suivies, lignes_legendes = 0, []
        for nom, infos in legendes.items():
            data = (infos or {}).get("data") or []
            if not data:
                continue
            suivies += 1
            k = _tracker(data, "kills")
            d = _tracker(data, "damage")
            w = _tracker(data, "wins")
            total["kills"] += k or 0
            total["damage"] += d or 0
            total["wins"] += w or 0
            texte = " · ".join(f"{(t.get('name') or '').strip()} {int(api.nombre(t.get('value')) or 0):,}".replace(",", " ")
                               for t in data[:3])
            image = ((infos or {}).get("ImgAssets") or {}).get("icon")
            lignes_legendes.append((k or 0, [nom, texte, image or "apex_legende"]))
        tot = r.get("total") or {}
        kills = api.nombre((tot.get("kills") or {}).get("value")) or total["kills"]
        if kills:
            valeurs["eliminations"] = int(kills)
        degats = api.nombre((tot.get("damage") or {}).get("value")) or total["damage"]
        if degats:
            valeurs["degats"] = int(degats)
        if total["wins"]:
            valeurs["victoires"] = int(total["wins"])
        kd = api.nombre((tot.get("kd") or {}).get("value"))
        if kd and kd > 0:
            valeurs["kd"] = round(kd, 2)
        valeurs["legendes_suivies"] = suivies
        temps, sections_temps = self._suivi(dossier).resume()
        valeurs.update(temps)
        nom_joueur = glob.get("name") or pseudo
        api.garder_pseudo(self.id, nom_joueur)

        nom_rang = RANGS.get(rang.get("rankName"), rang.get("rankName") or "Non classé")
        if rang.get("rankDiv") and rang.get("rankName") not in ("Master", "Apex Predator", "Unranked"):
            nom_rang += f" {rang['rankDiv']}"
        temps_reel = r.get("realtime") or {}
        selection = ((r.get("legends") or {}).get("selected")) or {}
        sections = [{"titre": "Ton compte", "icone": "apex_rang", "lignes": [
            ["Rang", f"{nom_rang} · {valeurs.get('points_rang', 0):,} RP".replace(",", " "), rang.get("rankImg") or "apex_rang"],
            ["Niveau", str(valeurs.get("niveau", "—")), "cod_niveau"],
            ["Passe de combat", f"niveau {(glob.get('battlepass') or {}).get('level', '—')}", "fn_passe"],
            ["Légende sélectionnée", selection.get("LegendName") or temps_reel.get("selectedLegend") or "—",
             ((selection.get("ImgAssets") or {}).get("icon")) or "apex_legende"],
            ["Statut", temps_reel.get("currentStateAsText") or ("En ligne" if temps_reel.get("isOnline") else "Hors ligne"),
             "connecte" if temps_reel.get("isOnline") else "neutre"],
        ]}]
        if lignes_legendes:
            sections.append({"titre": "Tes légendes", "icone": "apex_legende",
                             "note": "Apex ne partage que les trackers que tu affiches sur tes bannières en jeu : "
                                     "équipe « Éliminations » et « Dégâts » sur tes légendes pour tout suivre.",
                             "lignes": [l for _, l in sorted(lignes_legendes, key=lambda e: -e[0])[:12]]})
        sections += sections_temps
        etat = [{"nom": "Apex Legends API", "icone": "cle", "ok": True, "texte": f"stats de {nom_joueur} à jour"},
                {"nom": "Temps de jeu", "icone": "horloge", "ok": True if temps else None,
                 "texte": f"{temps.get('sessions', 0)} session(s) suivie(s)" if temps
                 else "lance Apex sur ce PC avec AllMyStats allumé"}]
        tuiles = {"points_rang": {"texte": nom_rang, "image": rang.get("rankImg")}} if rang else {}
        badge = {"texte": f"{nom_rang} · {valeurs.get('points_rang', 0):,} RP".replace(",", " "), "icone": "apex_rang",
                 "image": rang.get("rankImg")}
        return valeurs, {"etat": etat, "sections": sections, "tuiles": tuiles, "badge": badge}, \
            f"Stats Apex de {nom_joueur} à jour"
