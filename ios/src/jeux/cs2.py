"""Counter-Strike 2 — automatique, comme un tracker.

Deux sources officielles, en lecture seule :
  1. Steam (API web de Valve, clé gratuite à coller dans les Réglages) : tes totaux à vie (éliminations, morts,
     headshots, précision, victoires, MVP, temps de jeu). Ton profil Steam doit avoir les « détails de jeu » publics.
  2. Leetify (API publique, sans clé) : ton Premier CS Rating, ton niveau FACEIT, tes notes Leetify et tes
     dernières parties — si tu as un compte Leetify (connexion avec Steam sur leetify.com).
Le temps de jeu est aussi mesuré quand CS2 est lancé sur ce PC.
"""

import os
import re
import time
from datetime import datetime

from core.temps_de_jeu import SuiviJeu

from . import _api as api
from .base import ErreurJeu, Jeu, Stat

URL_STEAM = "https://api.steampowered.com/"
URL_LEETIFY = "https://api-public.cs-prod.leetify.com/v3/"
APP_CS = 730
BANDES_PREMIER = [(30000, "Or", "#E9C046"), (25000, "Rouge", "#EB4B4B"), (20000, "Rose", "#D32CE6"),
                  (15000, "Violet", "#8847FF"), (10000, "Bleu", "#4B69FF"), (5000, "Bleu clair", "#5E98D9"),
                  (0, "Gris", "#B0C3D9")]
SOURCES = {"matchmaking": "Compétitif", "premier": "Premier", "faceit": "FACEIT", "wingman": "Partenaires",
           "renown": "Renown", "matchmaking_wingman": "Partenaires", "matchmaking_competitive": "Compétitif"}


def bande_premier(note):
    for seuil, nom, couleur in BANDES_PREMIER:
        if note is not None and note >= seuil:
            return nom, couleur
    return None, None


def steamid(texte, cle=""):
    """Lien de profil, ID à 17 chiffres ou pseudo personnalisé -> SteamID64."""
    t = (texte or "").strip().rstrip("/")
    m = re.search(r"(\d{17})", t)
    if m:
        return m.group(1)
    m = re.search(r"steamcommunity\.com/id/([^/?#]+)", t)
    perso = m.group(1) if m else t
    if not perso or "/" in perso:
        raise ErreurJeu("Lien de profil Steam non reconnu. Colle l'adresse de ton profil Steam (steamcommunity.com/…).")
    if cle:
        r = api.get_json(URL_STEAM + "ISteamUser/ResolveVanityURL/v1/", {"key": cle, "vanityurl": perso}, service="Steam")
        sid = ((r or {}).get("response") or {}).get("steamid") if isinstance(r, dict) else None
        if sid:
            return sid
    xml = api.get_json(f"https://steamcommunity.com/id/{perso}/", {"xml": 1}, service="Steam")
    m = re.search(r"<steamID64>(\d{17})</steamID64>", xml if isinstance(xml, str) else "")
    if m:
        return m.group(1)
    raise ErreurJeu(f"Profil Steam « {perso} » introuvable. Colle plutôt l'adresse complète de ton profil Steam.")


class CounterStrike2(Jeu):
    id = "cs2"
    nom = "Counter-Strike 2"
    icone = "jeu_cs2"
    couleur = "#E8A33A"
    stat_vedette = "premier"

    reglages = [
        {"cle": "profil_steam", "nom": "Ton profil Steam",
         "aide": "L'adresse de ton profil (Steam > ton pseudo > Profil, puis clic droit > Copier l'adresse), "
                 "ou ton ID Steam à 17 chiffres."},
        {"cle": "cle_steam", "nom": "Clé API Steam", "optionnel": True, "secret": True,
         "aide": "Pour tes totaux à vie (K/D, headshots, précision, temps de jeu). Gratuite : connecte-toi sur la page "
                 "et écris « localhost » comme domaine. Colle-la ici : ne la partage avec personne.",
         "lien": "https://steamcommunity.com/dev/apikey"},
    ]

    C, L, T = "Compétitif", "Combat (à vie)", "Temps de jeu"
    stats = [
        Stat("premier", "Premier CS Rating", "auto", groupe=C, icone="cs_premier",
             aide="Ta note Premier (via Leetify)"),
        Stat("faceit_elo", "ELO FACEIT", "auto", groupe=C, icone="cs_faceit"),
        Stat("victoires_pct", "Victoires (récentes)", "auto", unite="%", decimales=1, groupe=C, icone="cod_victoire",
             aide="Sur les parties suivies par Leetify"),
        Stat("note_visee", "Note de visée Leetify", "auto", groupe=C, icone="valo_viseur"),
        Stat("kd", "Ratio K/D", "auto", decimales=2, groupe=L, icone="cod_kd"),
        Stat("eliminations", "Éliminations", "auto", groupe=L, icone="cod_elimination"),
        Stat("morts", "Morts", "auto", groupe=L, icone="cod_mort"),
        Stat("hs", "Headshots", "auto", unite="%", decimales=1, groupe=L, icone="valo_tete"),
        Stat("precision", "Précision", "auto", unite="%", decimales=1, groupe=L, icone="cod_precision"),
        Stat("victoires", "Parties gagnées", "auto", groupe=L, icone="cod_victoire"),
        Stat("parties", "Parties jouées", "auto", groupe=L, icone="manette"),
        Stat("mvp", "MVP", "auto", groupe=L, icone="etoile"),
        Stat("temps_jeu", "Temps de jeu (Steam)", "auto", unite="h", decimales=1, groupe=T, icone="horloge"),
        Stat("temps_2sem", "Ces 2 dernières semaines", "auto", unite="h", decimales=1, groupe=T, icone="calendrier_semaine"),
        Stat("temps_total", "Temps suivi par AMS", "auto", unite="h", decimales=1, groupe=T, icone="historique"),
        Stat("sessions", "Sessions", "auto", groupe=T, icone="manette"),
    ]

    def _suivi(self, dossier):
        return SuiviJeu(os.path.join(dossier, "cs2_temps.json"), ("cs2.exe",))

    def surveiller(self, reglages, dossier):
        suivi = self._suivi(dossier)
        suivi.verifier()
        return suivi.resume()[0]

    def nom_du_compte(self, reglages):
        return api.pseudo_garde(self.id)

    # ------------------------------------------------------------------ Steam

    def _steam(self, sid, cle):
        valeurs, profil = {}, {}
        r = api.get_json(URL_STEAM + "ISteamUserStats/GetUserStatsForGame/v2/",
                         {"appid": APP_CS, "steamid": sid, "key": cle}, service="Steam")
        brut = {s["name"]: s.get("value") for s in ((r or {}).get("playerstats") or {}).get("stats", [])
                if isinstance(s, dict) and "name" in s}
        n = lambda k: api.nombre(brut.get(k)) or 0
        if n("total_kills"):
            valeurs["eliminations"] = int(n("total_kills"))
        if n("total_deaths"):
            valeurs["morts"] = int(n("total_deaths"))
            valeurs["kd"] = round(n("total_kills") / n("total_deaths"), 2)
        if n("total_kills"):
            valeurs["hs"] = round(100 * n("total_kills_headshot") / n("total_kills"), 1)
        if n("total_shots_fired"):
            valeurs["precision"] = round(100 * n("total_shots_hit") / n("total_shots_fired"), 1)
        if n("total_matches_played"):
            valeurs["parties"] = int(n("total_matches_played"))
            valeurs["victoires"] = int(n("total_matches_won"))
        if n("total_mvps"):
            valeurs["mvp"] = int(n("total_mvps"))
        profil["degats"] = int(n("total_damage_done")) or None
        profil["manches"] = int(n("total_rounds_played")) or None
        profil["cartes"] = sorted(((k[len("total_wins_map_"):], int(v or 0)) for k, v in brut.items()
                                   if k.startswith("total_wins_map_") and v), key=lambda e: -e[1])[:8]
        try:
            jeux = api.get_json(URL_STEAM + "IPlayerService/GetOwnedGames/v1/",
                                {"key": cle, "steamid": sid, "appids_filter[0]": APP_CS, "include_played_free_games": 1},
                                service="Steam")
            for g in ((jeux or {}).get("response") or {}).get("games", []):
                if g.get("appid") == APP_CS:
                    valeurs["temps_jeu"] = round((g.get("playtime_forever") or 0) / 60, 1)
                    valeurs["temps_2sem"] = round((g.get("playtime_2weeks") or 0) / 60, 1)
        except api.ErreurApi:
            pass
        try:
            res = api.get_json(URL_STEAM + "ISteamUser/GetPlayerSummaries/v2/", {"key": cle, "steamids": sid},
                               service="Steam")
            joueur = (((res or {}).get("response") or {}).get("players") or [{}])[0]
            profil["pseudo"], profil["avatar"] = joueur.get("personaname"), joueur.get("avatarfull")
        except api.ErreurApi:
            pass
        return valeurs, profil

    # ------------------------------------------------------------------ Leetify

    @staticmethod
    def _leetify(sid):
        r = api.get_json(URL_LEETIFY + "profile", {"steam64_id": sid}, service="Leetify")
        if not isinstance(r, dict):
            raise api.ErreurApi("Leetify a renvoyé une réponse illisible.")
        valeurs = {}
        rangs = r.get("ranks") or {}
        premier = api.nombre(rangs.get("premier"))
        if premier:
            valeurs["premier"] = int(premier)
        elo = api.nombre(rangs.get("faceit_elo"))
        if elo:
            valeurs["faceit_elo"] = int(elo)
        win = api.nombre(r.get("winrate"))
        if win is not None:
            valeurs["victoires_pct"] = round(win * 100 if win <= 1 else win, 1)
        visee = api.nombre((r.get("rating") or {}).get("aim"))
        if visee is not None:
            valeurs["note_visee"] = round(visee)
        return valeurs, r

    # ------------------------------------------------------------------ actualisation

    def recuperer(self, reglages, dossier):
        if not (reglages.get("profil_steam") or "").strip():
            raise ErreurJeu("Colle l'adresse de ton profil Steam dans les Réglages.")
        cle = (reglages.get("cle_steam") or "").strip()
        sid = steamid(reglages["profil_steam"], cle)
        valeurs, etat, profil, leet = {}, [], {}, None

        if cle:
            try:
                v, profil = self._steam(sid, cle)
                valeurs.update(v)
                etat.append({"nom": "Steam", "icone": "cle", "ok": bool(v),
                             "texte": "totaux à vie à jour" if v else "rien reçu : rends tes « détails de jeu » publics"})
            except api.ErreurApi as e:
                texte = str(e)
                if e.code in (401, 403):
                    texte = "clé refusée par Steam : vérifie ta clé API dans les Réglages"
                elif e.code == 500 or e.code == 400:
                    texte = "Steam ne montre pas tes stats : rends tes « détails de jeu » publics (Confidentialité du profil)"
                etat.append({"nom": "Steam", "icone": "cle", "ok": False, "texte": texte})
        else:
            etat.append({"nom": "Steam", "icone": "cle", "ok": None,
                         "texte": "ajoute ta clé API Steam gratuite dans les Réglages pour tes totaux à vie"})

        try:
            v, leet = self._leetify(sid)
            valeurs.update(v)
            etat.append({"nom": "Leetify", "icone": "cs_premier", "ok": True, "texte": "rang et dernières parties à jour"})
        except api.ErreurApi as e:
            texte = ("pas de compte Leetify : connecte-toi une fois avec Steam sur leetify.com pour ton rang Premier"
                     if e.code in (403, 404) else str(e))
            etat.append({"nom": "Leetify", "icone": "cs_premier", "ok": None if e.code in (403, 404) else False,
                         "texte": texte})

        v, sections_temps = self._suivi(dossier).resume()
        valeurs.update(v)
        if not any(e["ok"] for e in etat):
            raise ErreurJeu(" · ".join(f"{e['nom']} : {e['texte']}" for e in etat))
        pseudo = profil.get("pseudo") or (leet or {}).get("name")
        if pseudo:
            api.garder_pseudo(self.id, pseudo)
        details = self._fiche(valeurs, profil, leet, etat, sections_temps)
        return valeurs, details, f"Stats CS2 de {pseudo or 'ton compte'} à jour"

    def _fiche(self, valeurs, profil, leet, etat, sections_temps):
        sections = []
        rangs = (leet or {}).get("ranks") or {}
        lignes_rang = []
        premier = valeurs.get("premier")
        if premier:
            bande, _ = bande_premier(premier)
            lignes_rang.append(["Premier", f"{premier:,} · bande {bande}".replace(",", " "), "cs_premier"])
        if rangs.get("faceit"):
            lignes_rang.append(["FACEIT", f"niveau {rangs['faceit']}" + (f" · {int(rangs['faceit_elo'])} ELO"
                                                                          if rangs.get("faceit_elo") else ""), "cs_faceit"])
        if rangs.get("wingman"):
            lignes_rang.append(["Partenaires", str(rangs["wingman"]), "amis"])
        for r in (rangs.get("competitive") or [])[:6]:
            if isinstance(r, dict) and r.get("rank"):
                lignes_rang.append([f"Compétitif · {r.get('map_name', '').replace('de_', '').capitalize()}",
                                    str(r["rank"]), "cs_carte"])
        note = (leet or {}).get("rating") or {}
        for cle, nom in (("aim", "Visée"), ("utility", "Utilitaires"), ("positioning", "Placement"),
                         ("clutch", "Clutchs"), ("opening", "Duels d'ouverture")):
            if api.nombre(note.get(cle)) is not None:
                v = api.nombre(note[cle])
                lignes_rang.append([f"Note Leetify · {nom}", f"{v:.0f}" if abs(v) >= 1 else f"{v:+.2f}", "graphique"])
        if lignes_rang:
            sections.append({"titre": "Rangs et notes", "icone": "cs_premier", "lignes": lignes_rang})

        parties = []
        for m in ((leet or {}).get("recent_matches") or [])[:12]:
            if not isinstance(m, dict):
                continue
            resultat = (m.get("outcome") or "").lower()
            couleur = {"win": "#33D19A", "loss": "#FF6B5E"}.get(resultat, "#9AA3C7")
            score = m.get("score") or []
            quand = m.get("finished_at") or ""
            try:
                quand = datetime.fromisoformat(quand.replace("Z", "+00:00")).astimezone().strftime("%d/%m %H:%M")
            except ValueError:
                quand = ""
            carte = (m.get("map_name") or "").replace("de_", "").replace("_", " ").capitalize()
            lignes = []
            if api.nombre(m.get("leetify_rating")) is not None:
                lignes.append(["Note Leetify", f"{api.nombre(m['leetify_rating']):+.2f}"])
            if m.get("rank"):
                lignes.append(["Rang", str(m["rank"])])
            parties.append({
                "titre": {"win": "Victoire", "loss": "Défaite", "tie": "Égalité"}.get(resultat, "Partie")
                         + (f" {score[0]}-{score[1]}" if isinstance(score, list) and len(score) == 2 else ""),
                "sous_titre": " · ".join(x for x in (carte, SOURCES.get(m.get("data_source"), m.get("data_source") or ""),
                                                      quand) if x),
                "icone": "cs_carte", "couleur": couleur, "lignes": lignes,
            })
        if parties:
            sections.append({"titre": "Dernières parties", "icone": "manette", "cartes": parties})

        if profil.get("cartes"):
            sections.append({"titre": "Tes cartes (victoires à vie)", "icone": "cs_carte",
                             "lignes": [[c.replace("de_", "").replace("cs_", "").capitalize(), f"{n} manche(s) gagnée(s)",
                                         "cs_carte"] for c, n in profil["cartes"]]})
        if profil.get("degats") or profil.get("manches"):
            lignes = []
            if profil.get("manches"):
                lignes.append(["Manches jouées", f"{profil['manches']:,}".replace(",", " "), "manette"])
            if profil.get("degats") and profil.get("manches"):
                lignes.append(["Dégâts par manche", str(round(profil["degats"] / profil["manches"])), "valo_degats"])
            sections.append({"titre": "À vie (CS:GO + CS2)", "icone": "historique", "lignes": lignes})
        sections += sections_temps
        sections.append({"titre": "Pour tout avoir", "icone": "astuce", "conseils": [
            ("cle", "Colle ta **clé API Steam** gratuite dans les Réglages (steamcommunity.com/dev/apikey)."),
            ("profil", "Sur Steam : Profil > Modifier > Confidentialité > **Détails de jeu : Public**."),
            ("cs_premier", "Pour le rang **Premier**, connecte-toi une fois avec Steam sur **leetify.com** (gratuit)."),
        ]})
        badge = None
        tuiles = {}
        if premier:
            bande, couleur = bande_premier(premier)
            badge = {"texte": f"Premier {premier:,}".replace(",", " "), "icone": "cs_premier"}
            tuiles["premier"] = {"texte": f"{premier:,}".replace(",", " ") + f" · {bande}"}
        return {"etat": etat, "sections": sections, "tuiles": tuiles, **({"badge": badge} if badge else {})}
