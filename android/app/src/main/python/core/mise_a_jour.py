"""Mises à jour de AllMyStats sans refaire le .exe.

Une mise à jour, c'est simplement le fichier AllMyStats.zip (le même que d'habitude).
- AllMyStats la télécharge TOUT SEUL sur Internet (dépôt GitHub public, fichier maj.json) ;
- il repère aussi un AllMyStats.zip posé dans tes Téléchargements ou sur ton Bureau ;
- ou tu peux le choisir à la main dans les paramètres d'AllMyStats.
Le nouveau code est installé dans %APPDATA%\\AllMyStats\\app (l'ancien est gardé dans app_ancien
pour revenir en arrière si besoin), puis AllMyStats redémarre tout seul.
"""

import glob
import hashlib
import io
import json
import os
import re
import shutil
import time
import urllib.error
import urllib.request
import zipfile

from core import chemins, reseau
from core.version import VERSION, en_tuple

DOSSIERS_CODE = ("core", "jeux", "web")
_cache = {"quand": 0, "resultat": None}
DOSSIER_TELECHARGE = os.path.join(chemins.DONNEES, "mises_a_jour")   # zips téléchargés par AllMyStats
MOTIF_DEPOT = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
EN_LIGNE = {"quand": None, "erreur": None, "version": None}            # dernière vérification sur Internet


class ErreurMaj(Exception):
    pass


def _lire_zip(source):
    """source = chemin d'un fichier ou bytes. Renvoie (zipfile, préfixe, version, nouveautés)."""
    try:
        z = zipfile.ZipFile(io.BytesIO(source) if isinstance(source, (bytes, bytearray)) else source)
    except (zipfile.BadZipFile, OSError):
        raise ErreurMaj("Ce fichier n'est pas un zip valide.")
    noms = z.namelist()
    fichier_version = next((n for n in noms if n.endswith("core/version.py")), None)
    if not fichier_version:
        raise ErreurMaj("Ce zip n'est pas une version de AllMyStats.")
    prefixe = fichier_version[: -len("core/version.py")]
    if not all(f"{prefixe}{p}" in noms for p in ("core/serveur.py", "jeux/__init__.py", "web/index.html")):
        raise ErreurMaj("Ce zip de AllMyStats est incomplet.")
    texte = z.read(fichier_version).decode("utf-8", errors="ignore")
    m = re.search(r'VERSION\s*=\s*"([\d.]+)"', texte)
    if not m:
        raise ErreurMaj("Impossible de lire la version dans ce zip.")
    nouveautes = re.findall(r'^\s*"([^"]+)",\s*$', texte.split("NOUVEAUTES", 1)[-1].split("]", 1)[0], re.M)
    return z, prefixe, m.group(1), nouveautes


def chercher():
    """Cherche un AllMyStats*.zip plus récent dans Téléchargements / Bureau (résultat gardé 30 s)."""
    if time.time() - _cache["quand"] < 30:
        return _cache["resultat"]
    maison = os.path.expanduser("~")
    candidats = glob.glob(os.path.join(DOSSIER_TELECHARGE, "AllMyStats*.zip"))
    for dossier in ("Downloads", "Téléchargements", "Desktop", "Bureau", os.path.join("OneDrive", "Bureau"),
                    os.path.join("OneDrive", "Desktop")):
        for motif in ("AllMyStats*.zip", "MesStats*.zip"):
            candidats += glob.glob(os.path.join(maison, dossier, motif))
    meilleur = None
    for chemin in sorted(set(candidats), key=lambda c: os.path.getmtime(c), reverse=True)[:10]:
        try:
            z, _, version, nouveautes = _lire_zip(chemin)
            z.close()
        except ErreurMaj:
            continue
        if en_tuple(version) > en_tuple(VERSION) and (not meilleur or en_tuple(version) > en_tuple(meilleur["version"])):
            meilleur = {"version": version, "chemin": chemin, "nouveautes": nouveautes,
                        "en_ligne": os.path.dirname(os.path.abspath(chemin)) == os.path.abspath(DOSSIER_TELECHARGE)}
    _cache.update(quand=time.time(), resultat=meilleur)
    return meilleur


def installer(source):
    """Installe une mise à jour (chemin de zip ou bytes). Renvoie la nouvelle version."""
    z, prefixe, version, _ = _lire_zip(source)
    if en_tuple(version) < en_tuple(VERSION):
        raise ErreurMaj(f"Ce zip contient une version plus ancienne ({version}) que la tienne ({VERSION}).")
    app = chemins.DOSSIER_APP
    nouveau, ancien = app + "_nouveau", app + "_ancien"
    shutil.rmtree(nouveau, ignore_errors=True)
    try:
        for info in z.infolist():
            if info.is_dir() or not info.filename.startswith(prefixe):
                continue
            relatif = info.filename[len(prefixe):]
            if relatif.split("/", 1)[0] not in DOSSIERS_CODE or "__pycache__" in relatif:
                continue
            cible = os.path.normpath(os.path.join(nouveau, relatif))
            if not cible.startswith(os.path.normpath(nouveau) + os.sep):
                continue  # sécurité : pas de chemin bizarre
            os.makedirs(os.path.dirname(cible), exist_ok=True)
            with z.open(info) as src, open(cible, "wb") as dst:
                shutil.copyfileobj(src, dst)
    finally:
        z.close()

    # On garde la version actuelle de côté, puis on met la nouvelle à sa place
    shutil.rmtree(ancien, ignore_errors=True)
    if os.path.isdir(app):
        os.replace(app, ancien)
    elif os.path.isdir(os.path.join(chemins.RESSOURCES, "core")):
        shutil.copytree(chemins.RESSOURCES, ancien,
                        ignore=shutil.ignore_patterns("data", "__pycache__", "build", "*.zip"))
    os.replace(nouveau, app)
    _cache.update(quand=0, resultat=None)

    return version


# ---------------------------------------------------------------- mises à jour par Internet

def depot_valide(depot):
    depot = (depot or "").strip()
    return bool(MOTIF_DEPOT.match(depot)) and not any(p in ("", ".", "..") or p.startswith(".") for p in depot.split("/"))


def _telecharger(url, limite=50_000_000, entetes=None):
    req = urllib.request.Request(url, headers={"User-Agent": f"AllMyStats/{VERSION}", "Cache-Control": "no-cache",
                                               **(entetes or {})})
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            donnees = r.read(limite + 1)
    except urllib.error.HTTPError:
        raise
    except (urllib.error.URLError, OSError):
        if not urllib.request.getproxies():
            raise
        # Un proxy Windows est réglé mais ne marche pas : on réessaie en direct
        with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(req, timeout=40) as r:
            donnees = r.read(limite + 1)
    if len(donnees) > limite:
        raise ErreurMaj("Fichier de mise à jour trop gros.")
    return donnees


def _dernier_envoi(depot):
    """Code (sha) du dernier envoi sur la branche main, ou « main » si GitHub ne répond pas."""
    try:
        sha = _telecharger(f"https://api.github.com/repos/{depot}/commits/main", 1000,
                           {"Accept": "application/vnd.github.sha"}).decode("ascii", "ignore").strip()
        if re.fullmatch(r"[0-9a-f]{40}", sha):
            return sha
    except Exception:
        pass
    return "main"


def verifier_en_ligne(depot):
    """Regarde maj.json sur le dépôt GitHub `depot` (ex : « pseudo/AllMyStats »).
    Si une version plus récente existe, télécharge son zip dans DOSSIER_TELECHARGE.
    Renvoie la version téléchargée (ou None si tu es à jour). Lève ErreurMaj en cas de souci."""
    depot = (depot or "").strip()
    if not depot_valide(depot):
        raise ErreurMaj("Source des mises à jour invalide (il faut « pseudo/AllMyStats »).")
    # On lit les fichiers du tout dernier envoi (son code unique) : l'adresse « main » reste en cache
    # quelques minutes chez GitHub, et AllMyStats verrait encore l'ancienne version.
    base = f"https://raw.githubusercontent.com/{depot}/{_dernier_envoi(depot)}/"
    EN_LIGNE["quand"] = time.time()
    try:
        try:
            info = json.loads(_telecharger(base + f"maj.json?t={int(time.time())}", 200_000).decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 404:
                raise ErreurMaj("Aucune mise à jour publiée sur ce dépôt pour l'instant.")
            raise ErreurMaj(f"GitHub a répondu une erreur {e.code}.")
        except (urllib.error.URLError, OSError) as e:
            raise ErreurMaj(f"Pas de connexion à GitHub ({reseau.raison(e)}).")
        except ValueError:
            raise ErreurMaj("Le fichier maj.json du dépôt est illisible.")
        version = str(info.get("version", ""))
        if not re.fullmatch(r"\d+(\.\d+)*", version):
            raise ErreurMaj("Le fichier maj.json ne donne pas de version.")
        EN_LIGNE["version"] = version
        _nettoyer()
        if en_tuple(version) <= en_tuple(VERSION):
            EN_LIGNE["erreur"] = None
            return None
        chemin = os.path.join(DOSSIER_TELECHARGE, f"AllMyStats-{version}.zip")
        if not os.path.exists(chemin):
            fichier = str(info.get("fichier") or "AllMyStats.zip")
            if not re.fullmatch(r"[A-Za-z0-9_./-]+\.zip", fichier) or ".." in fichier:
                raise ErreurMaj("Le fichier maj.json indique un zip invalide.")
            try:
                donnees = _telecharger(base + fichier + f"?v={version}")
            except (urllib.error.URLError, OSError) as e:
                raise ErreurMaj(f"Le téléchargement de la mise à jour a échoué ({reseau.raison(e)}).")
            attendu = str(info.get("sha256", "")).lower()
            if attendu and hashlib.sha256(donnees).hexdigest() != attendu:
                raise ErreurMaj("La mise à jour téléchargée est abîmée (empreinte différente). Nouvel essai plus tard.")
            z, _, version_zip, _ = _lire_zip(donnees)
            z.close()
            if version_zip != version:
                raise ErreurMaj("Le zip publié ne correspond pas à maj.json.")
            os.makedirs(DOSSIER_TELECHARGE, exist_ok=True)
            with open(chemin + ".part", "wb") as f:
                f.write(donnees)
            os.replace(chemin + ".part", chemin)
            _cache.update(quand=0, resultat=None)
        EN_LIGNE["erreur"] = None
        return version
    except ErreurMaj as e:
        EN_LIGNE["erreur"] = str(e)
        raise


def _nettoyer():
    """Efface les zips téléchargés qui ne sont pas plus récents que la version installée."""
    for chemin in glob.glob(os.path.join(DOSSIER_TELECHARGE, "AllMyStats-*.zip")):
        m = re.search(r"AllMyStats-([\d.]+)\.zip$", chemin)
        if m and en_tuple(m.group(1).rstrip(".")) <= en_tuple(VERSION):
            try:
                os.remove(chemin)
            except OSError:
                pass
