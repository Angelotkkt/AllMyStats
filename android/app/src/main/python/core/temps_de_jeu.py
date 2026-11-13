"""Mesure le temps de jeu en regardant si le jeu est lancé sur ce PC (utilisable par n'importe quel jeu).

Tant que AllMyStats tourne (fenêtre ouverte ou mode arrière-plan), il vérifie chaque minute si le
programme du jeu est lancé. L'heure exacte de lancement est demandée à Windows, donc même si
AllMyStats démarre en cours de partie, le début de la partie est juste.
"""

import json
import os
import time
from datetime import datetime, timedelta

from core import windows

JOURS = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]


class SuiviJeu:
    def __init__(self, fichier, programmes):
        self.fichier = fichier          # ex: data/genshin_temps.json
        self.programmes = programmes    # ex: ("GenshinImpact.exe", "YuanShen.exe")

    def _lire(self):
        try:
            with open(self.fichier, "r", encoding="utf-8") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError):
            return {"sessions": [], "en_cours": None}

    def _ecrire(self, data):
        with open(self.fichier, "w", encoding="utf-8") as f:
            json.dump(data, f)

    def verifier(self):
        """À appeler toutes les minutes. Met à jour les sessions."""
        data = self._lire()
        maintenant = time.time()
        lances = windows.processus_lances(self.programmes)
        en_cours = data.get("en_cours")
        if lances:
            if not en_cours or maintenant - en_cours["vu"] > 300:
                if en_cours:  # trou de plus de 5 min : l'ancienne session est finie
                    data["sessions"].append({"debut": en_cours["debut"], "fin": en_cours["vu"]})
                nom = next(iter(lances)).rsplit(".", 1)[0]
                debut = windows.debut_processus(nom) or maintenant
                if data["sessions"] and debut < data["sessions"][-1]["fin"]:
                    debut = data["sessions"][-1]["fin"]
                en_cours = {"debut": debut, "vu": maintenant}
            en_cours["vu"] = maintenant
            data["en_cours"] = en_cours
        elif en_cours:
            data["sessions"].append({"debut": en_cours["debut"], "fin": en_cours["vu"]})
            data["en_cours"] = None
        self._ecrire(data)
        return bool(lances)

    def resume(self, icone="horloge"):
        """Renvoie (valeurs, sections) : temps total, 7 derniers jours, nombre de parties."""
        data = self._lire()
        sessions = list(data.get("sessions") or [])
        if data.get("en_cours"):
            sessions.append({"debut": data["en_cours"]["debut"], "fin": data["en_cours"]["vu"], "live": True})
        if not sessions:
            return {}, []
        maintenant = time.time()
        duree = lambda s: max(0, min(s["fin"] - s["debut"], 16 * 3600))
        total = sum(duree(s) for s in sessions)
        semaine = sum(duree(s) for s in sessions if s["debut"] > maintenant - 7 * 86400)
        valeurs = {"temps_total": round(total / 3600, 1), "temps_7j": round(semaine / 3600, 1),
                   "sessions": len(sessions)}
        jours = []
        for i in range(6, -1, -1):
            jour = (datetime.now() - timedelta(days=i)).date()
            sec = sum(duree(s) for s in sessions if datetime.fromtimestamp(s["debut"]).date() == jour)
            jours.append([f"{JOURS[jour.weekday()]} {jour.day}", f"{sec / 3600:.1f} h".replace(".", ","), icone])
        dernieres = [[datetime.fromtimestamp(s["debut"]).strftime("%d/%m à %H:%M"),
                      f"{int(duree(s) // 60)} min" + (" · en cours" if s.get("live") else ""), "manette"]
                     for s in reversed(sessions[-8:])]
        sections = [{"titre": "Ton temps de jeu (7 derniers jours)", "icone": "calendrier_semaine", "lignes": jours},
                    {"titre": "Tes dernières parties", "icone": "manette", "lignes": dernieres}]
        return valeurs, sections
