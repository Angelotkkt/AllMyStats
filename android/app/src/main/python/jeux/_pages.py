"""Pages « en ligne » d'AllMyStats : un vrai site (carte interactive…) affiché dans la fenêtre
d'AllMyStats, dans une fenêtre de navigateur collée sur la page (voir core/ancrage.py)."""

import os
import subprocess
import urllib.request

from core.fenetre import _navigateurs_possibles
from .base import Jeu


class PageEnLigne(Jeu):
    page = "carte"
    stats = []
    # ouvrir() : texte affiché selon le mode (remplaçable)
    texte_connexion = "Fenêtre ouverte avec ton compte : connecte-toi une fois, ce sera gardé"

    _integrable = {}

    def integrable(self, id_carte):
        """Le site accepte-t-il d'être affiché DANS AllMyStats ? On lit simplement ses règles d'affichage
        (en-têtes X-Frame-Options et Content-Security-Policy). True / False / None (on ne sait pas)."""
        carte = next((c for c in self.cartes_en_ligne if c["id"] == id_carte), None)
        if not carte:
            return None
        if id_carte in self._integrable:
            return self._integrable[id_carte]
        try:
            req = urllib.request.Request(carte["url"], headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
            with urllib.request.urlopen(req, timeout=10) as r:
                xfo = (r.headers.get("X-Frame-Options") or "").lower()
                csp = (r.headers.get("Content-Security-Policy") or "").lower()
        except Exception:
            return None
        resultat = True
        if "deny" in xfo or "sameorigin" in xfo:
            resultat = False
        for regle in csp.split(";"):
            regle = regle.strip()
            if regle.startswith("frame-ancestors"):
                sources = regle.split()[1:]
                if "*" not in sources and not any("localhost" in x or "127.0.0.1" in x for x in sources):
                    resultat = False
        self._integrable[id_carte] = resultat
        return resultat

    def ouvrir(self, id_carte, dossier, mode="fenetre"):
        """mode « fenetre » : plein écran · « connexion » : petite fenêtre pour se connecter ·
        « navigateur » : ton navigateur habituel (et ses comptes, Google compris)."""
        import webbrowser
        carte = next((c for c in self.cartes_en_ligne if c["id"] == id_carte), self.cartes_en_ligne[0])
        if mode == "navigateur":
            webbrowser.open(carte["url"])
            return f"{carte['nom']} ouverte dans ton navigateur"
        # Même profil que la fenêtre d'AllMyStats : une connexion faite ici sert aussi à la carte intégrée
        profil = os.path.join(dossier, "fenetre")
        taille = ["--window-size=1280,820"] if mode == "connexion" else ["--start-maximized"]
        for exe in _navigateurs_possibles():
            if os.path.isfile(exe):
                try:
                    subprocess.Popen([exe, f"--app={carte['url']}", f"--user-data-dir={profil}", *taille,
                                      "--no-first-run", "--no-default-browser-check"],
                                     creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                    if mode == "connexion":
                        return self.texte_connexion
                    return f"{carte['nom']} ouverte"
                except OSError:
                    continue
        webbrowser.open(carte["url"])
        return f"{carte['nom']} ouverte dans ton navigateur"
