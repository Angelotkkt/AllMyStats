"""Petits outils communs pour les jeux qui lisent leurs stats sur une API web (CS2, Fortnite, Apex…)."""

import json
import urllib.error
import urllib.parse
import urllib.request

from .base import ErreurJeu

UA = "AllMyStats/2 (appli de stats perso ; https://github.com/Angelotkkt/AllMyStats)"


class ErreurApi(ErreurJeu):
    def __init__(self, message, code=None):
        self.code = code
        super().__init__(message)


def _message(data):
    """Le message d'erreur que le service a renvoyé, quelle que soit sa forme."""
    if isinstance(data, dict):
        for cle in ("error", "Error", "message", "msg", "detail", "errors"):
            v = data.get(cle)
            if isinstance(v, str) and v.strip():
                return v.strip()
            if isinstance(v, list) and v:
                premier = v[0]
                return (premier.get("message") if isinstance(premier, dict) else str(premier)) or ""
            if isinstance(v, dict):
                return v.get("message") or ""
    return ""


def get_json(url, params=None, entetes=None, service="le service", timeout=20):
    """GET JSON. Lève ErreurApi avec un message clair (code HTTP + raison donnée par le service)."""
    if params:
        url += ("&" if "?" in url else "?") + urllib.parse.urlencode(params, doseq=True)
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json", **(entetes or {})})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            texte = r.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        try:
            data = json.loads(e.read().decode("utf-8", errors="replace"))
        except Exception:
            data = None
        raise ErreurApi(_message(data) or f"{service} a répondu une erreur {e.code}", e.code)
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise ErreurApi(f"Impossible de joindre {service} ({getattr(e, 'reason', e)}). Vérifie ta connexion.")
    try:
        return json.loads(texte)
    except ValueError:
        if texte.lstrip().startswith("<"):
            return texte   # du XML/HTML (profil Steam public)
        raise ErreurApi(f"{service} a renvoyé une réponse illisible.")


def nombre(v):
    try:
        if v is None or v == "":
            return None
        return float(str(v).replace(",", "").replace(" ", ""))
    except (TypeError, ValueError):
        return None


def garder_pseudo(id_jeu, pseudo):
    """Retient le pseudo affiché dans la barre de gauche (data/<jeu>_compte.json)."""
    import os
    from core import chemins
    chemin = os.path.join(chemins.DONNEES, f"{id_jeu}_compte.json")
    try:
        with open(chemin, "w", encoding="utf-8") as f:
            json.dump({"pseudo": pseudo}, f, ensure_ascii=False)
    except OSError:
        pass


def pseudo_garde(id_jeu):
    import os
    from core import chemins
    try:
        with open(os.path.join(chemins.DONNEES, f"{id_jeu}_compte.json"), encoding="utf-8") as f:
            return json.load(f).get("pseudo") or ""
    except (OSError, ValueError):
        return ""
