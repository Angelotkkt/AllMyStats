"""Travail automatique en fond, tant que AllMyStats est allumé (fenêtre ouverte ou mode arrière-plan).

Toutes les minutes :
  - chaque jeu peut « surveiller » (temps de jeu, lecture de l'écran pendant une partie…) ;
Toutes les 30 minutes :
  - chaque jeu configuré est actualisé (comme le bouton Actualiser).
"""

import threading
import time
import traceback

INTERVALLE = 60
ACTUALISATION = 30 * 60
_lance = {"oui": False}


def _configure(jeu, reglages):
    return all(r.get("optionnel") or reglages.get(r["cle"]) for r in jeu.reglages)


def demarrer(jeux, config, dossier, enregistrer, actualiser, est_cache=None):
    if _lance["oui"]:
        return
    _lance["oui"] = True
    # Première actualisation 2 minutes après le démarrage (la fenêtre s'en charge si elle est ouverte)
    derniere = {j: time.time() - ACTUALISATION + 120 for j in jeux}

    def boucle():
        while True:
            for jeu in list(jeux.values()):
                if est_cache and est_cache(jeu):  # jeu masqué dans les Paramètres : on ne le surveille plus
                    continue
                reglages = config.reglages(jeu.cle_reglages)
                try:
                    valeurs = jeu.surveiller(reglages, dossier)
                    if valeurs:
                        enregistrer(jeu, valeurs)
                except Exception:
                    traceback.print_exc()
                if jeu.a_des_stats_auto() and time.time() - derniere.get(jeu.id, 0) > ACTUALISATION:
                    derniere[jeu.id] = time.time()
                    if _configure(jeu, reglages):
                        try:
                            actualiser(jeu)
                        except Exception as e:
                            print(f"[actualisation auto] {jeu.nom} : {e}")
            time.sleep(INTERVALLE)

    threading.Thread(target=boucle, daemon=True, name="surveillance").start()
