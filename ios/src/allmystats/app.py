"""AllMyStats sur iPhone : lance le moteur d'AllMyStats dans le téléphone et affiche son interface.

La première fois, l'interface demande de relier l'iPhone au PC (adresse + code affichés dans
Paramètres > Téléphone sur le PC) : il copie tes comptes et tes stats, puis marche tout seul.
En cas de problème, un message s'affiche à l'écran et le détail est écrit dans
Fichiers > Sur mon iPhone > AllMyStats > journal.txt."""

import asyncio
import os
import threading
import time
import traceback
import urllib.request
from pathlib import Path

import toga
from toga.style import Pack
from toga.style.pack import COLUMN

PORT = 8765
CHARGEMENT = """<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>Chargement</title></head><body style="margin:0;min-height:100vh;display:flex;flex-direction:column;
align-items:center;justify-content:center;background:#141832;color:#EEF0FA;font:17px -apple-system,system-ui;
text-align:center;gap:14px;padding:24px;box-sizing:border-box"><div style="width:40px;height:40px;border-radius:50%;
border:4px solid #2E3570;border-top-color:#FFC44D;animation:t .9s linear infinite"></div><p>{MESSAGE}</p>
<style>@keyframes t{to{transform:rotate(360deg)}}</style></body></html>"""


def page_attente(message):
    # (pas de « % » : le CSS contient « 50% », c'est ce qui laissait l'écran blanc)
    return CHARGEMENT.replace("{MESSAGE}", message)


class AllMyStats(toga.App):
    def journal(self, texte):
        try:
            with open(self.fichier_journal, "a", encoding="utf-8") as f:
                f.write(time.strftime("%d/%m %H:%M:%S ") + texte + "\n")
        except OSError:
            pass

    def startup(self):
        documents = Path.home() / "Documents"
        documents.mkdir(parents=True, exist_ok=True)
        self.fichier_journal = str(documents / "journal.txt")
        self.journal("--- démarrage de l'appli")

        self.boite = toga.Box(style=Pack(direction=COLUMN, flex=1, background_color="#141832"))
        self.message = toga.Label("Démarrage d'AllMyStats…", style=Pack(padding=20, color="#EEF0FA"))
        self.main_window = toga.MainWindow(title=self.formal_name)
        self.main_window.content = self.boite
        self.boite.add(self.message)
        self.main_window.show()

        try:
            ici = os.path.dirname(os.path.abspath(__file__))
            self.donnees = str(self.paths.data)
            os.makedirs(self.donnees, exist_ok=True)
            os.environ["MESSTATS_DONNEES"] = self.donnees
            os.environ["AMS_WEB"] = os.path.join(ici, "web")
            os.environ["AMS_IOS"] = "1"
            for nom in ("port.txt", "erreur_demarrage.txt"):
                try:
                    os.remove(os.path.join(self.donnees, nom))
                except OSError:
                    pass
            threading.Thread(target=self._moteur, daemon=True, name="moteur").start()

            self.vue = toga.WebView(style=Pack(flex=1), on_webview_load=self._page_chargee)
            self.boite.remove(self.message)
            self.boite.add(self.vue)
            self.vue.set_content("http://127.0.0.1/", page_attente("Démarrage d'AllMyStats…"))
            self.loop.create_task(self._attendre())
        except Exception:
            self._erreur("L'appli n'a pas pu démarrer.", traceback.format_exc())

    def _erreur(self, titre, detail=""):
        """Message lisible à l'écran (sans passer par la page web), et détail dans le journal."""
        self.journal(titre + "\n" + detail)
        dernier = detail.strip().splitlines()[-1] if detail.strip() else ""
        texte = f"{titre}\n\n{dernier}\n\nDétail : Fichiers > Sur mon iPhone > AllMyStats > journal.txt"
        for enfant in list(self.boite.children):
            self.boite.remove(enfant)
        self.boite.add(toga.Label(texte, style=Pack(padding=20, color="#EEF0FA")))

    def _moteur(self):
        try:
            from core import serveur
            self.journal("moteur : lancement")
            serveur.demarrer(PORT, ouvrir_navigateur=False)
        except BaseException:
            detail = traceback.format_exc()
            self.journal("moteur : ERREUR\n" + detail)
            with open(os.path.join(self.donnees, "erreur_demarrage.txt"), "w", encoding="utf-8") as f:
                f.write(detail)

    @staticmethod
    def _repond(port):
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/ping", timeout=1.5) as r:
                return r.status == 200
        except OSError:
            return False

    def _page_chargee(self, widget, **kwargs):
        self.journal(f"page chargée : {getattr(widget, 'url', '')}")

    async def _attendre(self):
        boucle = asyncio.get_running_loop()
        for _ in range(300):
            erreur = os.path.join(self.donnees, "erreur_demarrage.txt")
            if os.path.exists(erreur):
                return self._erreur("Le moteur d'AllMyStats n'a pas pu démarrer.", open(erreur, encoding="utf-8").read())
            fichier_port = os.path.join(self.donnees, "port.txt")
            if os.path.exists(fichier_port):
                port = int(open(fichier_port).read().strip() or PORT)
                if await boucle.run_in_executor(None, self._repond, port):
                    adresse = f"http://127.0.0.1:{port}/?app=ios"
                    self.journal("moteur prêt, ouverture de " + adresse)
                    self.vue.url = adresse
                    await asyncio.sleep(8)
                    await self._verifier_affichage(adresse)
                    return
            await asyncio.sleep(0.3)
        self._erreur("AllMyStats met trop de temps à démarrer.", "Ferme l'appli (glisse-la vers le haut) et rouvre-la.")

    async def _verifier_affichage(self, adresse):
        """Si la page reste vide, on réessaie une fois, puis on l'explique à l'écran."""
        for essai in range(2):
            try:
                titre = await self.vue.evaluate_javascript("document.title")
            except Exception as e:
                titre = f"(erreur : {e})"
            self.journal(f"titre de la page : {titre!r}")
            if titre == "AllMyStats":
                return
            if essai == 0:
                self.vue.url = adresse
                await asyncio.sleep(6)
        self._erreur("La page d'AllMyStats ne s'affiche pas.",
                     f"Le moteur répond, mais la vue web reste vide (titre : {titre!r}).")


def main():
    return AllMyStats()
