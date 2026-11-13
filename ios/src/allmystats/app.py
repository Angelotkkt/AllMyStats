"""AllMyStats sur iPhone : lance le moteur d'AllMyStats dans le téléphone et affiche son interface.

La première fois, l'interface demande de relier l'iPhone au PC (adresse + code affichés dans
Paramètres > Téléphone sur le PC) : il copie tes comptes et tes stats, puis marche tout seul."""

import asyncio
import os
import threading
import traceback
import urllib.request

import toga
from toga.style import Pack

PORT = 8765
CHARGEMENT = """<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<body style="margin:0;height:100vh;display:flex;flex-direction:column;align-items:center;justify-content:center;
background:#141832;color:#EEF0FA;font:17px -apple-system,system-ui;text-align:center;gap:14px">
<div style="width:40px;height:40px;border-radius:50%;border:4px solid #2E3570;border-top-color:#FFC44D;
animation:t .9s linear infinite"></div><p>%s</p>
<style>@keyframes t{to{transform:rotate(360deg)}}</style></body>"""


class AllMyStats(toga.App):
    def startup(self):
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

        self.vue = toga.WebView(style=Pack(flex=1))
        self.main_window = toga.MainWindow(title=self.formal_name)
        self.main_window.content = self.vue
        self.vue.set_content("http://127.0.0.1/", CHARGEMENT % "Démarrage d'AllMyStats…")
        self.main_window.show()
        asyncio.get_event_loop().create_task(self._attendre())

    def _moteur(self):
        try:
            from core import serveur
            serveur.demarrer(PORT, ouvrir_navigateur=False)
        except BaseException:
            with open(os.path.join(self.donnees, "erreur_demarrage.txt"), "w", encoding="utf-8") as f:
                f.write(traceback.format_exc())

    @staticmethod
    def _repond(port):
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/ping", timeout=1.5) as r:
                return r.status == 200
        except OSError:
            return False

    async def _attendre(self):
        boucle = asyncio.get_event_loop()
        for _ in range(300):
            erreur = os.path.join(self.donnees, "erreur_demarrage.txt")
            if os.path.exists(erreur):
                derniere = open(erreur, encoding="utf-8").read().strip().splitlines()[-1:]
                self.vue.set_content("http://127.0.0.1/", CHARGEMENT % ("AllMyStats n'a pas pu démarrer : "
                                                                       + (derniere[0] if derniere else "?")))
                return
            fichier_port = os.path.join(self.donnees, "port.txt")
            if os.path.exists(fichier_port):
                port = int(open(fichier_port).read().strip() or PORT)
                if await boucle.run_in_executor(None, self._repond, port):
                    self.vue.url = f"http://127.0.0.1:{port}/?app=ios"
                    return
            await asyncio.sleep(0.3)
        self.vue.set_content("http://127.0.0.1/", CHARGEMENT % "AllMyStats met trop de temps à démarrer. Ferme l'appli et rouvre-la.")


def main():
    return AllMyStats()
