"""Sous-catégorie « Connexion quotidienne » de Genshin : la récompense de connexion HoYoLAB du jour.

Mêmes informations que la page officielle (jours du mois, récompenses, jour actuel) et un bouton pour
récupérer la récompense du jour, avec la connexion HoYoLAB de la page Genshin Impact. Rien n'est récupéré
tout seul : c'est toi qui cliques. Si HoYoLAB demande une vérification (« je ne suis pas un robot »),
AllMyStats ne la contourne pas : il ouvre la vraie page de connexion quotidienne, où tu la fais toi-même.
"""

import json
import urllib.error
import urllib.request
from urllib.parse import urlencode

from . import _genshin_hoyolab as hoyolab
from ._pages import PageEnLigne
from .base import ErreurJeu

ACT_ID = "e202102251931481"
URL_API = "https://sg-hk4e-api.hoyolab.com/event/sol/"
URL_PAGE = f"https://act.hoyolab.com/ys/event/signin-sea-v3/index.html?act_id={ACT_ID}&lang=fr-fr"
MESSAGES = {
    -100: "Ta connexion HoYoLAB a expiré : reconnecte-toi dans la page Genshin Impact.",
    10001: "Ta connexion HoYoLAB a expiré : reconnecte-toi dans la page Genshin Impact.",
    -10002: "HoYoLAB ne trouve pas de compte Genshin lié à ce compte.",
    -5003: "Tu as déjà récupéré la récompense d'aujourd'hui.",
}


class ConnexionQuotidienne(PageEnLigne):
    id = "genshin_connexion"
    nom = "Connexion quotidienne"
    icone = "connexion_quotidienne"
    couleur = "#5E86D6"
    famille = "Genshin Impact"
    ordre = 3
    page = "quotidien"
    stats = []
    reglages_source = "genshin"   # on se sert de la connexion HoYoLAB de la page Genshin Impact
    texte_connexion = "Page officielle ouverte : connecte-toi en haut si besoin, puis récupère ta récompense"
    cartes_en_ligne = [
        {"id": "officielle", "nom": "Connexion quotidienne (page officielle)", "url": URL_PAGE, "collee": True,
         "aide": "La vraie page de HoYoLAB, avec les missions et la compensation de connexion."},
    ]

    # ------------------------------------------------------------------ appels HoYoLAB

    @staticmethod
    def _appel(chemin, cookies, corps=None):
        url = URL_API + chemin + ("&" if "?" in chemin else "?") + urlencode({"lang": "fr-fr", "act_id": ACT_ID})
        entetes = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/124.0 Safari/537.36",
            "Accept": "application/json", "Referer": "https://act.hoyolab.com/", "Origin": "https://act.hoyolab.com",
            "Cookie": "; ".join(f"{k}={v}" for k, v in cookies.items()), "x-rpc-signgame": "hk4e",
            "x-rpc-lang": "fr-fr", "x-rpc-language": "fr-fr",
        }
        donnees = None
        if corps is not None:
            donnees = json.dumps(corps).encode()
            entetes["Content-Type"] = "application/json"
        req = urllib.request.Request(url, data=donnees, headers=entetes, method="POST" if corps is not None else "GET")
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                rep = json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            raise ErreurJeu(f"HoYoLAB ne répond pas correctement (code {e.code}).")
        except (urllib.error.URLError, TimeoutError, OSError, ValueError):
            raise ErreurJeu("Impossible de joindre HoYoLAB. Vérifie ta connexion internet.")
        return rep

    @staticmethod
    def _cookies(reglages):
        cookies = hoyolab.lire_cookies(reglages or {})
        if not (cookies.get("ltoken_v2") and cookies.get("ltuid_v2")):
            return None
        return cookies

    # ------------------------------------------------------------------ pour le serveur

    def page_donnees(self, chemin, dossier, reglages=None):
        """GET /api/jeux/genshin_connexion/page/etat : le calendrier du mois et où tu en es."""
        cookies = self._cookies(reglages)
        if not cookies:
            return {"connecte": False, "page_officielle": URL_PAGE}
        info = self._appel("info", cookies)
        if info.get("retcode") != 0:
            raise ErreurJeu(MESSAGES.get(info.get("retcode"), f"HoYoLAB : {info.get('message', '?')}"))
        home = self._appel("home", cookies)
        if home.get("retcode") != 0:
            raise ErreurJeu(MESSAGES.get(home.get("retcode"), f"HoYoLAB : {home.get('message', '?')}"))
        i, h = info.get("data") or {}, home.get("data") or {}
        recompenses = [{"nom": a.get("name") or "", "nombre": a.get("cnt") or 0, "image": a.get("icon")}
                       for a in h.get("awards") or []]
        return {
            "connecte": True,
            "mois": h.get("month"),
            "jours_faits": i.get("total_sign_day") or 0,
            "deja_fait": bool(i.get("is_sign")),
            "jours_manques": i.get("sign_cnt_missed") or 0,
            "aujourdhui": i.get("today"),
            "recompenses": recompenses,
            "page_officielle": URL_PAGE,
        }

    def page_action(self, chemin, corps, dossier, reglages=None):
        """POST /api/jeux/genshin_connexion/page/recuperer : récupère la récompense du jour (clic de l'utilisateur)."""
        if chemin != ["recuperer"]:
            raise ErreurJeu("Action inconnue.")
        cookies = self._cookies(reglages)
        if not cookies:
            raise ErreurJeu("Connecte-toi d'abord à HoYoLAB dans la page Genshin Impact.")
        rep = self._appel("sign", cookies, {"act_id": ACT_ID})
        code, data = rep.get("retcode"), rep.get("data") or {}
        risque = data.get("gt_result") or {}
        if code == 0 and (risque.get("is_risk") or (risque.get("risk_code") not in (None, 0))):
            # HoYoLAB veut vérifier que c'est bien toi : on ne contourne pas, on ouvre la vraie page
            return {"ok": False, "verification": True,
                    "message": "HoYoLAB demande une vérification : fais-la sur la page officielle, juste en dessous."}
        if code == -5003:
            return {"ok": True, "deja": True, "message": MESSAGES[-5003]}
        if code != 0:
            raise ErreurJeu(MESSAGES.get(code, f"HoYoLAB : {rep.get('message', '?')} (code {code})"))
        return {"ok": True, "message": "Récompense du jour récupérée !"}
