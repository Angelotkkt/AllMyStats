"""La fenêtre d'AllMyStats.

1) Fenêtre native (AllMyStats.exe récent) : une vraie fenêtre Windows qui appartient à AllMyStats, avec son
   icône dans la barre des tâches, sans aucun morceau de navigateur. L'affichage passe par WebView2, le moteur
   d'affichage intégré à Windows 10/11, via la bibliothèque pywebview (emballée dans le .exe).
2) Secours (ancien AllMyStats.exe, ou WebView2 absent) : le mode « application » de Microsoft Edge ou Chrome,
   sinon le navigateur par défaut.
"""

import os
import shutil
import subprocess
import threading
import time
import webbrowser


def natif_disponible():
    """Vrai si ce programme sait ouvrir une fenêtre native (pywebview emballé dans le .exe, sous Windows)."""
    if os.name != "nt" or os.environ.get("AMS_SANS_FENETRE_NATIVE"):
        return False
    try:
        import webview  # noqa: F401
        return True
    except Exception:
        return False


class FenetreNative:
    """La fenêtre native. lancer() doit tourner sur le fil principal et ne rend la main qu'à la fermeture
    définitive. Si AllMyStats doit rester actif (mode « Toujours actif »), fermer la fenêtre la cache."""

    def __init__(self, adresse, dossier_donnees, cachee=False, rester_actif=lambda: False):
        self.adresse, self.dossier = adresse, dossier_donnees
        self.cachee, self.rester_actif = cachee, rester_actif
        self.fenetre = None
        self.visible = not cachee
        self.prete = threading.Event()
        self._quitter = False

    def lancer(self):
        import webview
        self.fenetre = webview.create_window(
            "AllMyStats", self.adresse, width=1320, height=860, min_size=(900, 600),
            background_color="#141832", hidden=self.cachee, text_select=False, zoomable=False)
        self.fenetre.events.closing += self._fermeture
        self.fenetre.events.shown += lambda: self._visible(True)
        self.fenetre.events.loaded += lambda: self.prete.set()
        webview.start(gui="edgechromium", private_mode=False, debug=False,
                      storage_path=os.path.join(self.dossier, "fenetre_appli"))

    def _visible(self, v):
        self.visible = v

    def _fermeture(self):
        if not self._quitter and self.rester_actif():
            # Toujours actif : on cache la fenêtre au lieu de fermer AllMyStats
            threading.Timer(0.05, self._cacher).start()
            return False
        return True

    def _cacher(self):
        try:
            self.fenetre.hide()
        finally:
            self.visible = False

    def montrer(self):
        if not self.fenetre:
            return
        try:
            self.fenetre.show()
            self.fenetre.restore()
        except Exception:
            pass
        self.visible = True

    def fermer(self):
        """Ferme vraiment (Quitter, mise à jour)."""
        self._quitter = True
        if self.fenetre:
            try:
                self.fenetre.destroy()
            except Exception:
                pass


def _navigateurs_possibles():
    programmes = [os.environ.get(v) for v in ("PROGRAMFILES(X86)", "PROGRAMFILES", "LOCALAPPDATA")]
    relatifs = [
        r"Microsoft\Edge\Application\msedge.exe",
        r"Google\Chrome\Application\chrome.exe",
    ]
    for rel in relatifs:
        for base in programmes:
            if base:
                yield os.path.join(base, rel)
    for nom in ("msedge", "google-chrome", "chrome", "chromium"):
        chemin = shutil.which(nom)
        if chemin:
            yield chemin


def ouvrir_fenetre(adresse, dossier_donnees):
    profil = os.path.join(dossier_donnees, "fenetre")
    for exe in _navigateurs_possibles():
        if not os.path.isfile(exe):
            continue
        try:
            subprocess.Popen(
                [
                    exe,
                    f"--app={adresse}",
                    f"--user-data-dir={profil}",   # profil séparé = vraie fenêtre à part
                    "--window-size=1320,860",
                    "--no-first-run",
                    "--no-default-browser-check",
                ],
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            return True
        except OSError:
            continue
    webbrowser.open(adresse)
    return False
