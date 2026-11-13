"""Fortnite — automatique, comme un tracker.

Source : Fortnite-API.com (API communautaire gratuite, clé à coller dans les Réglages), qui lit tes stats
Battle Royale officielles d'Epic : victoires, tops, éliminations, K/D, parties, temps de jeu, niveau du passe.
Tes stats doivent être publiques dans Fortnite. Le temps de jeu est aussi mesuré quand Fortnite est lancé ici.
"""

import os

from core.temps_de_jeu import SuiviJeu

from . import _api as api
from .base import ErreurJeu, Jeu, Stat

URL = "https://fortnite-api.com/v2/stats/br/v2"
MODES = [("solo", "Solo"), ("duo", "Duo"), ("trio", "Trio"), ("squad", "Escouade"), ("ltm", "Modes temporaires")]
COMPTES = {"epic": "epic", "psn": "psn", "playstation": "psn", "ps": "psn", "xbl": "xbl", "xbox": "xbl"}


class Fortnite(Jeu):
    id = "fortnite"
    nom = "Fortnite"
    icone = "jeu_fortnite"
    couleur = "#9D6BFF"
    stat_vedette = "victoires"

    reglages = [
        {"cle": "pseudo_epic", "nom": "Pseudo Epic Games", "aide": "Ton nom d'affichage Epic, exactement comme en jeu."},
        {"cle": "cle_fortnite_api", "nom": "Clé Fortnite-API", "secret": True,
         "aide": "Gratuite : connecte-toi sur dash.fortnite-api.com (avec Discord), puis copie ta clé. "
                 "Colle-la ici : ne la partage avec personne.",
         "lien": "https://dash.fortnite-api.com/"},
        {"cle": "type_compte", "nom": "Compte (facultatif)", "optionnel": True, "avance": True,
         "aide": "epic (par défaut), psn ou xbl si ton pseudo est celui de ta console."},
    ]

    V, S, P, T = "Victoires", "Combat", "Saison en cours", "Temps de jeu"
    stats = [
        Stat("victoires", "Victoires Royales", "auto", groupe=V, icone="fn_victoire"),
        Stat("victoires_pct", "Taux de victoire", "auto", unite="%", decimales=1, groupe=V, icone="cod_ratio"),
        Stat("top10", "Tops", "auto", groupe=V, icone="cod_podium",
             aide="Top 10 en solo + top 5 en duo + top 3 en escouade (comme les trackers)"),
        Stat("parties", "Parties jouées", "auto", groupe=V, icone="manette"),
        Stat("kd", "Ratio K/D", "auto", decimales=2, groupe=S, icone="cod_kd"),
        Stat("eliminations", "Éliminations", "auto", groupe=S, icone="cod_elimination"),
        Stat("elim_partie", "Éliminations par partie", "auto", decimales=2, groupe=S, icone="valo_viseur"),
        Stat("score_partie", "Score par partie", "auto", groupe=S, icone="cod_score"),
        Stat("niveau_passe", "Niveau du passe de combat", "auto", groupe=P, icone="fn_passe"),
        Stat("victoires_saison", "Victoires cette saison", "auto", groupe=P, icone="fn_victoire"),
        Stat("kd_saison", "K/D cette saison", "auto", decimales=2, groupe=P, icone="cod_kd"),
        Stat("parties_saison", "Parties cette saison", "auto", groupe=P, icone="manette"),
        Stat("temps_jeu", "Temps de jeu (Epic)", "auto", unite="h", decimales=1, groupe=T, icone="horloge"),
        Stat("temps_total", "Temps suivi par AMS", "auto", unite="h", decimales=1, groupe=T, icone="historique"),
        Stat("sessions", "Sessions", "auto", groupe=T, icone="manette"),
    ]

    def _suivi(self, dossier):
        return SuiviJeu(os.path.join(dossier, "fortnite_temps.json"), ("FortniteClient-Win64-Shipping.exe",))

    def surveiller(self, reglages, dossier):
        suivi = self._suivi(dossier)
        suivi.verifier()
        return suivi.resume()[0]

    def nom_du_compte(self, reglages):
        return api.pseudo_garde(self.id) or reglages.get("pseudo_epic", "")

    def _stats(self, pseudo, cle, compte, periode):
        try:
            r = api.get_json(URL, {"name": pseudo, "accountType": compte, "timeWindow": periode, "image": "none"},
                             {"Authorization": cle}, service="Fortnite-API")
        except api.ErreurApi as e:
            if e.code == 401:
                raise ErreurJeu("Clé Fortnite-API refusée : vérifie-la dans les Réglages (dash.fortnite-api.com).")
            if e.code == 403:
                raise ErreurJeu("Tes stats Fortnite sont privées. En jeu : Réglages > Compte et confidentialité > "
                                "active « Afficher dans le classement de carrière » (stats publiques), puis réessaie.")
            if e.code == 404:
                raise ErreurJeu(f"Compte « {pseudo} » introuvable. Vérifie ton pseudo Epic (ou le type de compte "
                                "dans les Réglages avancés : psn / xbl).")
            if e.code == 429:
                raise ErreurJeu("Fortnite-API demande d'attendre un peu : réessaie dans une minute.")
            raise
        return (r or {}).get("data") or {}

    def recuperer(self, reglages, dossier):
        pseudo = (reglages.get("pseudo_epic") or "").strip()
        cle = (reglages.get("cle_fortnite_api") or "").strip()
        if not pseudo or not cle:
            raise ErreurJeu("Mets ton pseudo Epic et ta clé Fortnite-API gratuite dans les Réglages.")
        compte = COMPTES.get((reglages.get("type_compte") or "epic").strip().lower(), "epic")
        vie = self._stats(pseudo, cle, compte, "lifetime")
        try:
            saison = self._stats(pseudo, cle, compte, "season")
        except ErreurJeu:
            saison = {}

        tout = ((vie.get("stats") or {}).get("all") or {})
        g = tout.get("overall") or {}
        n = lambda d, k: api.nombre(d.get(k)) or 0
        valeurs = {
            "victoires": int(n(g, "wins")), "parties": int(n(g, "matches")),
            "eliminations": int(n(g, "kills")), "kd": round(n(g, "kd"), 2),
            "victoires_pct": round(n(g, "winRate"), 1), "elim_partie": round(n(g, "killsPerMatch"), 2),
            "score_partie": round(n(g, "scorePerMatch")),
            "top10": int(n(tout.get("solo") or {}, "top10") + n(tout.get("duo") or {}, "top5")
                         + n(tout.get("squad") or {}, "top3")),
        }
        if n(g, "minutesPlayed"):
            valeurs["temps_jeu"] = round(n(g, "minutesPlayed") / 60, 1)
        passe = vie.get("battlePass") or {}
        if passe.get("level") is not None:
            valeurs["niveau_passe"] = int(passe["level"])
        gs = (((saison.get("stats") or {}).get("all") or {}).get("overall")) or {}
        if gs:
            valeurs.update({"victoires_saison": int(n(gs, "wins")), "kd_saison": round(n(gs, "kd"), 2),
                            "parties_saison": int(n(gs, "matches"))})
        temps, sections_temps = self._suivi(dossier).resume()
        valeurs.update(temps)
        nom = (vie.get("account") or {}).get("name") or pseudo
        api.garder_pseudo(self.id, nom)

        sections = []
        lignes = []
        for cle_mode, nom_mode in MODES:
            m = tout.get(cle_mode)
            if not m or not n(m, "matches"):
                continue
            lignes.append([nom_mode, f"{int(n(m, 'wins'))} victoire(s) · {int(n(m, 'matches'))} parties · "
                                     f"K/D {n(m, 'kd'):.2f}".replace(".", ","), "fn_victoire"])
        if lignes:
            sections.append({"titre": "Par mode (à vie)", "icone": "manette", "lignes": lignes})
        appareils = []
        for cle_app, nom_app, ic in (("keyboardMouse", "Clavier-souris", "manette"), ("gamepad", "Manette", "manette"),
                                     ("touch", "Tactile", "manette")):
            a = (((vie.get("stats") or {}).get(cle_app) or {}).get("overall")) or {}
            if n(a, "matches"):
                appareils.append([nom_app, f"{int(n(a, 'wins'))} victoire(s) · {int(n(a, 'matches'))} parties · "
                                           f"K/D {n(a, 'kd'):.2f}".replace(".", ","), ic])
        if appareils:
            sections.append({"titre": "Par appareil", "icone": "manette", "lignes": appareils})
        if gs:
            sections.append({"titre": "Cette saison", "icone": "fn_passe", "lignes": [
                ["Victoires", str(int(n(gs, "wins"))), "fn_victoire"],
                ["Parties", str(int(n(gs, "matches"))), "manette"],
                ["Éliminations", str(int(n(gs, "kills"))), "cod_elimination"],
                ["Taux de victoire", f"{n(gs, 'winRate'):.1f} %".replace(".", ","), "cod_ratio"],
            ]})
        sections += sections_temps
        etat = [{"nom": "Fortnite-API", "icone": "cle", "ok": True, "texte": f"stats de {nom} à jour"},
                {"nom": "Temps de jeu", "icone": "horloge", "ok": True if temps else None,
                 "texte": f"{temps.get('sessions', 0)} session(s) suivie(s)" if temps
                 else "lance Fortnite sur ce PC avec AllMyStats allumé"}]
        badge = {"texte": f"{valeurs['victoires']} Victoire(s) Royale(s)", "icone": "fn_victoire"}
        if valeurs.get("niveau_passe") is not None:
            badge["texte"] += f" · passe niv. {valeurs['niveau_passe']}"
        return valeurs, {"etat": etat, "sections": sections, "badge": badge}, f"Stats Fortnite de {nom} à jour"
