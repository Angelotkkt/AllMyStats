"""Stockage des stats dans un petit fichier SQLite (data/stats.db)."""

import json
import sqlite3
import threading
from datetime import datetime


def maintenant():
    return datetime.now().isoformat(timespec="seconds")


class BaseDeDonnees:
    def __init__(self, chemin):
        self.chemin = chemin
        self.verrou = threading.Lock()
        with self._connexion() as con:
            con.executescript(
                """
                CREATE TABLE IF NOT EXISTS mesures (
                    id      INTEGER PRIMARY KEY AUTOINCREMENT,
                    jeu     TEXT NOT NULL,
                    cle     TEXT NOT NULL,
                    valeur  REAL NOT NULL,
                    date    TEXT NOT NULL,
                    source  TEXT NOT NULL,      -- 'auto' ou 'manuel'
                    note    TEXT DEFAULT ''
                );
                CREATE INDEX IF NOT EXISTS idx_mesures ON mesures (jeu, cle, date);

                CREATE TABLE IF NOT EXISTS details (
                    jeu   TEXT PRIMARY KEY,
                    data  TEXT NOT NULL,
                    date  TEXT NOT NULL
                );
                """
            )

    def _connexion(self):
        con = sqlite3.connect(self.chemin)
        con.row_factory = sqlite3.Row
        return con

    # ---------- Mesures ----------

    def ajouter_mesure(self, jeu, cle, valeur, source, note="", date=None):
        with self.verrou, self._connexion() as con:
            cur = con.execute(
                "INSERT INTO mesures (jeu, cle, valeur, date, source, note) VALUES (?, ?, ?, ?, ?, ?)",
                (jeu, cle, float(valeur), date or maintenant(), source, note or ""),
            )
            return cur.lastrowid

    def derniere_valeur(self, jeu, cle):
        with self._connexion() as con:
            ligne = con.execute(
                "SELECT valeur FROM mesures WHERE jeu = ? AND cle = ? ORDER BY date DESC, id DESC LIMIT 1",
                (jeu, cle),
            ).fetchone()
            return None if ligne is None else ligne["valeur"]

    def historique(self, jeu):
        """Renvoie {cle: [ {id, valeur, date, source, note}, ... ]} trié du plus ancien au plus récent."""
        resultat = {}
        with self._connexion() as con:
            for ligne in con.execute(
                "SELECT * FROM mesures WHERE jeu = ? ORDER BY date ASC, id ASC", (jeu,)
            ):
                resultat.setdefault(ligne["cle"], []).append(
                    {
                        "id": ligne["id"],
                        "valeur": ligne["valeur"],
                        "date": ligne["date"],
                        "source": ligne["source"],
                        "note": ligne["note"],
                    }
                )
        return resultat

    def supprimer_mesure(self, id_mesure):
        with self.verrou, self._connexion() as con:
            return con.execute("DELETE FROM mesures WHERE id = ?", (id_mesure,)).rowcount > 0

    # ---------- Détails (dernière fiche récupérée : persos, profil...) ----------

    def enregistrer_details(self, jeu, data):
        with self.verrou, self._connexion() as con:
            con.execute(
                "INSERT OR REPLACE INTO details (jeu, data, date) VALUES (?, ?, ?)",
                (jeu, json.dumps(data, ensure_ascii=False), maintenant()),
            )

    def lire_details(self, jeu):
        with self._connexion() as con:
            ligne = con.execute("SELECT data, date FROM details WHERE jeu = ?", (jeu,)).fetchone()
            if ligne is None:
                return None, None
            return json.loads(ligne["data"]), ligne["date"]
