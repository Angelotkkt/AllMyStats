"""Réglages des jeux (UID, pseudo...) enregistrés dans config.json."""

import json
import os
import threading

_verrou = threading.Lock()


class Config:
    def __init__(self, chemin):
        self.chemin = chemin

    def _lire(self):
        if not os.path.exists(self.chemin):
            return {}
        try:
            with open(self.chemin, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {}

    def reglages(self, id_jeu):
        return self._lire().get(id_jeu, {})

    def enregistrer(self, id_jeu, valeurs):
        with _verrou:
            tout = self._lire()
            tout[id_jeu] = {k: str(v).strip() for k, v in valeurs.items()}
            with open(self.chemin, "w", encoding="utf-8") as f:
                json.dump(tout, f, ensure_ascii=False, indent=2)
