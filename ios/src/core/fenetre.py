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


ACTIVE = None   # la fenêtre native en cours (pour ouvrir d'autres pages dans des fenêtres AllMyStats)


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
        self._pages = {}

    def lancer(self):
        global ACTIVE
        import webview
        ACTIVE = self
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
        self._fermer_pages()   # sinon les fenêtres de pages garderaient AllMyStats ouvert
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

    def ouvrir_page(self, titre, url, plein_ecran=False):
        """Ouvre un vrai site (ex. la carte HoYoLAB) dans une fenêtre AllMyStats à part. C'est la vraie page du
        site : on s'y connecte directement, AllMyStats ne voit ni le mot de passe ni les cookies. La session
        est gardée par le moteur d'affichage (profil de la fenêtre, chiffré par Windows) : connexion une fois,
        ensuite c'est retenu. Si la fenêtre est déjà ouverte, on la remet devant."""
        import webview
        deja = self._pages.get(url)
        if deja is not None:
            try:
                deja.show()
                deja.restore()
                return False
            except Exception:
                self._pages.pop(url, None)
        fenetre = webview.create_window(titre, url, width=1400, height=900, min_size=(800, 560),
                                        background_color="#141832", maximized=plein_ecran, text_select=True)
        fenetre.events.closed += lambda: self._pages.pop(url, None)
        self._pages[url] = fenetre
        return True

    # ----- une page posée DANS la fenêtre (ex. carte HoYoLAB à la place du cadre de la page)
    # C'est un second affichage WebView2 ajouté dans la même fenêtre Windows, placé exactement sur le cadre
    # mesuré par la page d'AllMyStats. Il partage le profil de la fenêtre : même connexion, gardée.
    # Le site est affiché tel quel (on ne contourne pas son refus d'être mis dans une autre page).

    def _sur_fil_fenetre(self, fonction):
        from System import Action
        forme = self.fenetre.native
        resultat = {}

        def faire():
            try:
                resultat["valeur"] = fonction(forme)
            except Exception as e:   # noqa: BLE001 — on remonte l'erreur au fil appelant
                resultat["erreur"] = e
        if forme.InvokeRequired:
            forme.Invoke(Action(faire))
        else:
            faire()
        if "erreur" in resultat:
            raise resultat["erreur"]
        return resultat.get("valeur")

    @staticmethod
    def _affichage_principal(controle):
        for c in controle.Controls:
            if c.GetType().Name == "WebView2":
                return c
            trouve = FenetreNative._affichage_principal(c)
            if trouve is not None:
                return trouve
        return None

    @staticmethod
    def _rectangle(zone):
        from System.Drawing import Rectangle
        dpr = float(zone.get("dpr") or 1)
        x, y = int(round(float(zone.get("x") or 0) * dpr)), int(round(float(zone.get("y") or 0) * dpr))
        l, h = int(round(float(zone.get("l") or 0) * dpr)), int(round(float(zone.get("h") or 0) * dpr))
        return Rectangle(max(0, x), max(0, y), max(50, l), max(50, h))

    def incruster(self, url, zone):
        def faire(forme):
            from System.Drawing import Color
            from Microsoft.Web.WebView2.WinForms import WebView2
            vue = getattr(self, "_incrust", None)
            if vue is None:
                principal = self._affichage_principal(forme)
                if principal is None or principal.CoreWebView2 is None:
                    raise RuntimeError("affichage principal introuvable")
                vue = WebView2()
                vue.DefaultBackgroundColor = Color.FromArgb(255, 20, 24, 50)
                forme.Controls.Add(vue)
                self._incrust, self._incrust_url, self._incrust_a_charger = vue, None, None

                def pret(expediteur, args):
                    if args.IsSuccess and self._incrust_a_charger:
                        expediteur.CoreWebView2.Navigate(self._incrust_a_charger)
                        self._incrust_url, self._incrust_a_charger = self._incrust_a_charger, None
                vue.CoreWebView2InitializationCompleted += pret
                vue.EnsureCoreWebView2Async(principal.CoreWebView2.Environment)
            vue.Bounds = self._rectangle(zone)
            vue.Visible = True
            vue.BringToFront()
            if url != self._incrust_url:
                if vue.CoreWebView2 is not None:
                    vue.CoreWebView2.Navigate(url)
                    self._incrust_url = url
                else:
                    self._incrust_a_charger = url
            return True
        return self._sur_fil_fenetre(faire)

    def placer_incrustation(self, zone):
        def faire(forme):
            vue = getattr(self, "_incrust", None)
            if vue is not None and vue.Visible:
                vue.Bounds = self._rectangle(zone)
            return True
        return self._sur_fil_fenetre(faire)

    def cacher_incrustation(self):
        def faire(forme):
            vue = getattr(self, "_incrust", None)
            if vue is not None:
                vue.Visible = False
            return True
        if getattr(self, "_incrust", None) is None:
            return True
        return self._sur_fil_fenetre(faire)

    def _fermer_pages(self):
        for f in list(self._pages.values()):
            try:
                f.destroy()
            except Exception:
                pass
        self._pages.clear()

    def fermer(self):
        """Ferme vraiment (Quitter, mise à jour)."""
        self._fermer_pages()
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
