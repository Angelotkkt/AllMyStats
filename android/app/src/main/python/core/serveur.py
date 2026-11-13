"""Petit serveur local : il sert l'interface (dossier web/) et une API JSON.

Tout tourne sur ton PC, à l'adresse http://localhost:<port>.
"""

import json
import mimetypes
import os
import re
import subprocess
import sys
import threading
import time
import traceback
import urllib.request
import webbrowser
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlparse

from core import ancrage, chemins, diagnostic_ecran, mise_a_jour, reseau, surveillance, telephone, windows
from core.version import DEPOT_MAJ, NOUVEAUTES, VERSION
from core.base_de_donnees import BaseDeDonnees, maintenant
from core.config import Config
from core.fenetre import ouvrir_fenetre
from jeux import charger_jeux
from jeux.base import ErreurJeu

DOSSIER_WEB = chemins.WEB
DOSSIER_DONNEES = chemins.DONNEES

BDD = BaseDeDonnees(chemins.FICHIER_BDD)
CONFIG = Config(chemins.FICHIER_CONFIG)
JEUX = charger_jeux()

# Connexions en cours (une par jeu) : {id_jeu: {"etat": "attente"|"ok"|"erreur", "message": ...}}
CONNEXIONS = {}


def lancer_connexion(jeu):
    if CONNEXIONS.get(jeu.id, {}).get("etat") == "attente":
        return

    def travail():
        try:
            trouves, message = jeu.connexion(CONFIG.reglages(jeu.cle_reglages), DOSSIER_DONNEES)
            CONFIG.enregistrer(jeu.cle_reglages, {**CONFIG.reglages(jeu.cle_reglages), **trouves})
            CONNEXIONS[jeu.id] = {"etat": "ok", "message": message}
        except ErreurJeu as e:
            CONNEXIONS[jeu.id] = {"etat": "erreur", "message": str(e)}
        except Exception as e:
            traceback.print_exc()
            CONNEXIONS[jeu.id] = {"etat": "erreur", "message": f"Erreur inattendue pendant la connexion "
                                                              f"({type(e).__name__} : {str(e)[:160]})."}

    CONNEXIONS[jeu.id] = {"etat": "attente", "message": "En attente de ta connexion…"}
    threading.Thread(target=travail, daemon=True).start()


# Pour fermer le programme tout seul quand la fenêtre est fermée
_presence = {"dernier_signe": None, "au_revoir": None}
SIGNATURE = "AllMyStats"
SIGNATURES_CONNUES = ("AllMyStats", "MesStats")


def resume_jeu(jeu):
    """Toutes les infos d'un jeu pour l'interface."""
    historique = BDD.historique(jeu.id)
    stats = {}
    for stat in jeu.stats:
        points = historique.get(stat.cle, [])
        stats[stat.cle] = {
            "actuelle": points[-1]["valeur"] if points else None,
            "precedente": points[-2]["valeur"] if len(points) > 1 else None,
            "premiere": points[0]["valeur"] if points else None,
            "historique": points,
        }
    details, date_details = BDD.lire_details(jeu.id)
    reglages = CONFIG.reglages(jeu.cle_reglages)
    return {
        "jeu": jeu.en_dict(),
        "reglages": reglages,
        "connecte": bool(jeu.connexion_nom) and jeu.est_connecte(reglages),
        "compte": jeu.nom_du_compte(reglages),
        "stats": stats,
        "details": details,
        "derniere_maj": date_details,
    }


VERROUS = {}


def enregistrer_valeurs(jeu, valeurs, source="auto"):
    """Ajoute un point à l'historique pour chaque stat qui a changé. Renvoie le nombre de stats changées."""
    cles_valides = {s.cle for s in jeu.stats}
    nouvelles = 0
    with VERROUS.setdefault(jeu.id, threading.RLock()):  # la surveillance et le bouton Actualiser en même temps
        for cle, valeur in (valeurs or {}).items():
            if cle not in cles_valides or valeur is None:
                continue
            # On n'ajoute un point que si la valeur a changé : ça garde l'historique propre
            if BDD.derniere_valeur(jeu.id, cle) != float(valeur):
                BDD.ajouter_mesure(jeu.id, cle, valeur, source)
                nouvelles += 1
    return nouvelles


def tester_ecran(jeu, delai):
    """Bouton « Tester la lecture d'écran » : attend `delai` secondes (le temps d'aller sur le jeu),
    capture, explique ce qui bloque, et enregistre les stats trouvées."""
    time.sleep(delai)
    windows.bip()
    res = jeu.tester_ecran(CONFIG.reglages(jeu.cle_reglages), DOSSIER_DONNEES) or {"etapes": []}
    cible = JEUX.get(res.get("cible")) or jeu
    stats = {s.cle: s for s in cible.stats}
    trouve = [{"nom": stats[k].nom, "valeur": v, "unite": stats[k].unite, "decimales": stats[k].decimales}
              for k, v in (res.get("valeurs") or {}).items() if k in stats and v is not None]
    for e in res["etapes"]:
        if e["titre"] == "Stats reconnues" and trouve:
            e["detail"] = f"{len(trouve)} stat(s) trouvée(s), rangée(s) dans {cible.nom}."
    if trouve:
        enregistrer_valeurs(cible, res["valeurs"])
    etapes = [diagnostic_ecran.etape(
        "ok" if arriere_plan_actif() else "alerte", "Lecture automatique",
        "« Toujours actif » est activé : AllMyStats lit l'écran toutes les minutes, même fenêtre fermée."
        if arriere_plan_actif() else
        "AllMyStats lit l'écran toutes les minutes, mais seulement tant qu'il est ouvert. Active « Toujours actif » "
        "dans Paramètres pour que ça continue quand tu fermes sa fenêtre.")]
    if res.get("dernier_essai"):
        etapes.append(diagnostic_ecran.etape("neutre", "Dernier essai automatique", res["dernier_essai"]))
    etapes += res["etapes"]
    reussi = bool(trouve) and not any(e["etat"] == "erreur" for e in res["etapes"])
    return {"reussi": reussi, "etapes": etapes, "lignes": res.get("lignes", []), "trouve": trouve,
            "cible_nom": cible.nom, "cible": cible.id}


def actualiser(jeu):
    with VERROUS.setdefault(jeu.id, threading.RLock()):
        valeurs, details, message = jeu.recuperer(CONFIG.reglages(jeu.cle_reglages), DOSSIER_DONNEES)
        nouvelles = enregistrer_valeurs(jeu, valeurs)
        if details is not None:
            BDD.enregistrer_details(jeu.id, details)
    if nouvelles:
        message += f" · {nouvelles} stat(s) ont bougé"
    else:
        message += " · rien n'a changé depuis la dernière fois"
    return message


# ---------------------------------------------------------------- l'appli elle-même

MODE = {"arriere_plan": False, "serveur": None}


def reglages_appli():
    return CONFIG.reglages("_appli")


def code_telephone():
    reglages = reglages_appli()
    if not reglages.get("code_tel"):
        reglages["code_tel"] = telephone.nouveau_code()
        CONFIG.enregistrer("_appli", reglages)
    return reglages["code_tel"]


def export_telephone():
    return telephone.exporter(DOSSIER_DONNEES, chemins.FICHIER_BDD, chemins.FICHIER_CONFIG, JEUX)


def infos_telephone():
    actif = reglages_appli().get("telephone") == "oui"
    port = telephone.port()
    infos = {"actif": actif, "ouvert": bool(port), "port": port, "adresses": telephone.adresses_locales() if actif else []}
    if actif:
        infos["code"] = code_telephone()
        if port and infos["adresses"]:
            infos["lien"] = f"allmystats://relier?h={infos['adresses'][0]}:{port}&c={infos['code']}"
        elif not port:
            infos["erreur"] = "Impossible d'ouvrir l'accès Wi-Fi (ports 8790 à 8794 déjà pris)."
    return infos


def regler_telephone(actif=None, nouveau_code=False):
    reglages = reglages_appli()
    if nouveau_code:
        reglages["code_tel"] = telephone.nouveau_code()   # les téléphones déjà reliés devront se relier à nouveau
    if actif is not None:
        reglages["telephone"] = "oui" if actif else ""
    CONFIG.enregistrer("_appli", reglages)
    if reglages.get("telephone") == "oui":
        telephone.demarrer(Gestionnaire, code_telephone, export_telephone)
    else:
        telephone.arreter()
    return infos_telephone()


def arriere_plan_actif():
    return MODE["arriere_plan"] or reglages_appli().get("arriere_plan") == "oui"


def _commande_demarrage():
    if chemins.FIGE:
        return f'"{sys.executable}" --arriere-plan'
    pythonw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    return f'"{pythonw if os.path.exists(pythonw) else sys.executable}" "{os.path.abspath(sys.argv[0])}" --arriere-plan'


def regler_arriere_plan(actif):
    if os.name != "nt":
        raise ErreurJeu("Le démarrage avec Windows ne marche que sur Windows.")
    import winreg
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run",
                        0, winreg.KEY_SET_VALUE) as cle:
        try:
            winreg.DeleteValue(cle, "MesStats")  # ancien nom de l'appli
        except FileNotFoundError:
            pass
        if actif:
            winreg.SetValueEx(cle, "AllMyStats", 0, winreg.REG_SZ, _commande_demarrage())
        else:
            try:
                winreg.DeleteValue(cle, "AllMyStats")
            except FileNotFoundError:
                pass
    CONFIG.enregistrer("_appli", {**reglages_appli(), "arriere_plan": "oui" if actif else ""})


def jeux_caches():
    return {c for c in (reglages_appli().get("jeux_caches") or "").split("|") if c}   # config.json : texte « a|b »


def est_cache(jeu):
    """Jeu masqué dans les Paramètres (lui-même ou toute sa famille) : pas affiché, pas surveillé."""
    caches = jeux_caches()
    return jeu.id in caches or bool(jeu.famille and f"famille:{jeu.famille}" in caches)


def depot_maj():
    return (reglages_appli().get("depot_maj") or DEPOT_MAJ or "").strip()


def maj_auto():
    return reglages_appli().get("maj_auto") != "non"


def etat_appli():
    return {
        "version": VERSION,
        "nouveautes": NOUVEAUTES,
        "arriere_plan": arriere_plan_actif(),
        "windows": os.name == "nt",
        "maj": mise_a_jour.chercher(),
        "en_ligne": {
            "depot": depot_maj(),
            "auto": maj_auto(),
            "quand": mise_a_jour.EN_LIGNE["quand"],
            "erreur": mise_a_jour.EN_LIGNE["erreur"],
        },
    }


# ---------------------------------------------------------------- mises à jour automatiques

VERIFIER_TOUTES = 10 * 60   # vérification des mises à jour en ligne : toutes les 10 minutes


def _fenetre_ouverte():
    dernier, au_revoir = _presence["dernier_signe"], _presence["au_revoir"]
    if not dernier or time.time() - dernier > 60:
        return False
    return not (au_revoir and au_revoir > dernier)


def verifier_maj_en_ligne():
    """Télécharge la nouvelle version si elle existe. Renvoie un message pour l'interface."""
    if not depot_maj():
        raise mise_a_jour.ErreurMaj("La source des mises à jour n'est pas encore réglée.")
    version = mise_a_jour.verifier_en_ligne(depot_maj())
    return f"AllMyStats {version} est téléchargé et prêt à être installé" if version else "Tu as déjà la dernière version"


def _maj_telechargee():
    maj = mise_a_jour.chercher()
    return maj if maj and maj.get("en_ligne") else None


def _boucle_maj():
    """Vérifie sur Internet toutes les 10 minutes. Si « Installer tout seul » est activé, installe la nouvelle
    version dès que la fenêtre d'AllMyStats est fermée (mode Toujours actif), sinon un bandeau la propose."""
    time.sleep(20)
    derniere = 0
    while True:
        if depot_maj() and time.time() - derniere > VERIFIER_TOUTES:
            derniere = time.time()
            try:
                verifier_maj_en_ligne()
            except mise_a_jour.ErreurMaj as e:
                print(f"[mise à jour] {e}")
            except Exception:
                traceback.print_exc()
        maj = _maj_telechargee()
        if maj and maj_auto() and not _fenetre_ouverte():
            try:
                print(f"[mise à jour] installation de {mise_a_jour.installer(maj['chemin'])}")
                return relancer()
            except mise_a_jour.ErreurMaj as e:
                print(f"[mise à jour] {e}")
        time.sleep(60)


def _environnement_neuf():
    """Variables d'environnement pour relancer AllMyStats.exe comme un programme NEUF.
    Sans ça, le nouveau AllMyStats.exe croit être un « sous-processus » de l'ancien et réutilise ses fichiers
    décompressés… que l'ancien efface en se fermant : « Failed to import encodings module »."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("_PYI_") and k != "_MEIPASS2"}
    env["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
    return env


def _relancer_le_programme(arguments):
    args = [sys.executable] + ([] if chemins.FIGE else [os.path.abspath(sys.argv[0])]) + arguments
    options = {"env": _environnement_neuf()}
    if os.name == "nt":
        options["creationflags"] = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    subprocess.Popen(args, close_fds=True, **options)


def _installer_au_demarrage():
    """Une version téléchargée attend ? On l'installe avant d'ouvrir la fenêtre, puis on relance."""
    maj = _maj_telechargee()
    if not maj or not maj_auto():
        return
    try:
        version = mise_a_jour.installer(maj["chemin"])
    except Exception as e:
        print(f"[mise à jour] installation impossible : {e}")
        return
    print(f"[mise à jour] AllMyStats {version} installé, redémarrage…")
    _relancer_le_programme(sys.argv[1:])
    os._exit(0)


def _arreter_serveur():
    serveur = MODE["serveur"]
    if serveur:
        serveur.shutdown()
        serveur.server_close()


def relancer():
    """Redémarre AllMyStats (après une mise à jour). La fenêtre ouverte se recharge toute seule."""
    def travail():
        time.sleep(0.6)
        _arreter_serveur()
        _relancer_le_programme(["--arriere-plan" if MODE["arriere_plan"] else "--relance"])
        os._exit(0)
    # Pas « daemon » : le programme doit attendre d'avoir relancé la nouvelle version avant de s'arrêter
    threading.Thread(target=travail, daemon=False).start()


def quitter():
    def travail():
        time.sleep(0.4)
        _arreter_serveur()
        os._exit(0)
    threading.Thread(target=travail, daemon=True).start()


class Gestionnaire(BaseHTTPRequestHandler):
    def log_message(self, format, *args):  # pas de spam dans la console
        pass

    # ---------- utilitaires ----------

    def _json(self, data, code=200):
        corps = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(corps)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(corps)

    def _erreur(self, message, code=400):
        self._json({"erreur": message}, code)

    def _corps(self):
        taille = int(self.headers.get("Content-Length") or 0)
        if not taille:
            return {}
        try:
            return json.loads(self.rfile.read(taille).decode("utf-8"))
        except json.JSONDecodeError:
            return {}

    def _fichier(self, chemin):
        chemin = os.path.normpath(os.path.join(DOSSIER_WEB, chemin.lstrip("/")))
        if not chemin.startswith(DOSSIER_WEB) or not os.path.isfile(chemin):
            self.send_error(404)
            return
        type_mime = mimetypes.guess_type(chemin)[0] or "application/octet-stream"
        with open(chemin, "rb") as f:
            corps = f.read()
        self.send_response(200)
        self.send_header("Content-Type", type_mime + ("; charset=utf-8" if type_mime.startswith("text") else ""))
        self.send_header("Content-Length", str(len(corps)))
        self.end_headers()
        self.wfile.write(corps)

    def _morceaux(self):
        return [unquote(m) for m in urlparse(self.path).path.strip("/").split("/") if m]

    def _jeu(self, id_jeu):
        jeu = JEUX.get(id_jeu)
        if jeu is None:
            self._erreur("Jeu inconnu.", 404)
        return jeu

    def _protege(self, action):
        try:
            action()
        except ErreurJeu as e:
            self._erreur(str(e), 400)
        except Exception as e:
            traceback.print_exc()
            self._erreur(f"Erreur inattendue ({type(e).__name__} : {str(e)[:160]}). "
                         f"Les détails sont dans journal.txt, dans le dossier d'AllMyStats.", 500)

    # ---------- routes ----------

    def do_GET(self):
        m = self._morceaux()
        if not m or m[0] != "api":
            return self._fichier("index.html" if not m else "/".join(m))

        def action():
            if m == ["api", "ping"]:
                _presence["dernier_signe"] = time.time()
                return self._json({"appli": SIGNATURE})
            if m == ["api", "jeux"]:
                liste = []
                for j in JEUX.values():
                    reglages = CONFIG.reglages(j.cle_reglages)
                    connecte = bool(j.connexion_nom) and j.est_connecte(reglages)
                    liste.append({**j.en_dict(), "connecte": connecte, "cache": est_cache(j),
                                  "famille_cachee": bool(j.famille and f"famille:{j.famille}" in jeux_caches()),
                                  "masque_seul": j.id in jeux_caches(),
                                  "compte": j.nom_du_compte(reglages) if connecte or not j.connexion_nom else ""})
                return self._json(liste)
            if m == ["api", "appli"]:
                return self._json({**etat_appli(), "distant": getattr(self, "distant", False), "android": chemins.ANDROID,
                                   "mobile": chemins.MOBILE, "ios": chemins.IOS,
                                   "lie": os.path.exists(os.path.join(DOSSIER_DONNEES, "synchro.json"))})
            if m == ["api", "appli", "telephone"]:
                if getattr(self, "distant", False):
                    return self._erreur("Ça se règle sur le PC.", 403)
                return self._json(infos_telephone())
            if len(m) == 4 and m[1] == "jeux" and m[3] == "connexion":
                return self._json(CONNEXIONS.get(m[2], {"etat": "aucune"}))
            if len(m) >= 5 and m[1] == "jeux" and m[3] == "page":   # données d'une page spéciale (Builds & Teams…)
                jeu = self._jeu(m[2])
                if not jeu:
                    return
                if not hasattr(jeu, "page_donnees"):
                    return self._erreur("Cette catégorie n'a pas de données de page.")
                try:
                    return self._json(jeu.page_donnees(m[4:], DOSSIER_DONNEES))
                except ErreurJeu as e:
                    return self._erreur(str(e))
            if len(m) == 5 and m[1] == "jeux" and m[3] == "integrable":   # carte affichable dans l'appli ?
                jeu = self._jeu(m[2])
                if not jeu:
                    return
                return self._json({"integrable": jeu.integrable(m[4]) if hasattr(jeu, "integrable") else None})
            if len(m) == 3 and m[1] == "jeux":
                jeu = self._jeu(m[2])
                if jeu:
                    if jeu.famille and CONFIG.reglages(jeu.cle_reglages).get("dernier_titre") != jeu.id:
                        # Le dernier jeu de la famille regardé (sert à deviner à quoi tu joues)
                        CONFIG.enregistrer(jeu.cle_reglages, {**CONFIG.reglages(jeu.cle_reglages),
                                                              "dernier_titre": jeu.id})
                    self._json(resume_jeu(jeu))
                return
            self._erreur("Route inconnue.", 404)

        self._protege(action)

    def do_POST(self):
        m = self._morceaux()
        if m == ["api", "maj", "fichier"]:  # zip envoyé depuis l'interface
            taille = int(self.headers.get("Content-Length") or 0)
            if not 0 < taille < 50_000_000:
                return self._erreur("Fichier vide ou trop gros.")
            donnees = self.rfile.read(taille)

            def installer_fichier():
                try:
                    version = mise_a_jour.installer(donnees)
                except mise_a_jour.ErreurMaj as e:
                    return self._erreur(str(e))
                self._json({"message": f"AllMyStats {version} installé, redémarrage…", "version": version})
                relancer()
            return self._protege(installer_fichier)
        if len(m) == 4 and m[:2] == ["api", "jeux"] and m[3] == "image":  # capture d'écran glissée dans l'appli
            return self._protege(lambda: self._recevoir_image(m[2]))
        if len(m) == 4 and m[:2] == ["api", "jeux"] and m[3] == "donnees":  # fichier de données (Activision…)
            return self._protege(lambda: self._recevoir_donnees(m[2]))
        corps = self._corps()

        def action():
            if m == ["api", "maj", "installer"]:
                maj = mise_a_jour.chercher()
                if not maj:
                    return self._erreur("Aucune mise à jour trouvée.")
                try:
                    version = mise_a_jour.installer(maj["chemin"])
                except mise_a_jour.ErreurMaj as e:
                    return self._erreur(str(e))
                self._json({"message": f"AllMyStats {version} installé, redémarrage…", "version": version})
                return relancer()
            if m == ["api", "maj", "verifier"]:
                try:
                    message = verifier_maj_en_ligne()
                except mise_a_jour.ErreurMaj as e:
                    return self._erreur(str(e))
                return self._json({"message": message, **etat_appli()})
            if m == ["api", "carte-collee"]:   # la carte connectée posée dans la fenêtre d'AllMyStats
                action = corps.get("action")
                if action == "cacher":
                    return self._json(ancrage.cacher())
                if action == "placer":
                    return self._json(ancrage.placer(corps.get("zone") or {}))
                jeu = JEUX.get(str(corps.get("jeu") or ""))
                carte = next((c for c in getattr(jeu, "cartes_en_ligne", []) if c["id"] == corps.get("carte")), None)
                if not carte:
                    return self._erreur("Carte inconnue.")
                return self._json(ancrage.montrer(carte["url"], os.path.join(DOSSIER_DONNEES, "fenetre"),
                                                  corps.get("zone") or {}, garder=bool(carte.get("garder"))))
            if m == ["api", "appli", "jeux-caches"]:
                connus = {j.id for j in JEUX.values()} | {f"famille:{j.famille}" for j in JEUX.values() if j.famille}
                caches = sorted({c for c in (corps.get("caches") or []) if c in connus})
                CONFIG.enregistrer("_appli", {**reglages_appli(), "jeux_caches": "|".join(caches)})
                return self._json({"caches": caches})
            if m == ["api", "appli", "mises-a-jour"]:
                reglages = reglages_appli()
                if "auto" in corps:
                    reglages["maj_auto"] = "" if corps["auto"] else "non"
                if "depot" in corps:
                    depot = str(corps["depot"] or "").strip()
                    depot = re.sub(r"^https?://(www\.)?github\.com/", "", depot).strip("/")
                    if depot.endswith(".git"):
                        depot = depot[:-4]
                    if depot and not mise_a_jour.depot_valide(depot):
                        return self._erreur("Écris la source sous la forme « pseudo/AllMyStats ».")
                    reglages["depot_maj"] = depot
                CONFIG.enregistrer("_appli", reglages)
                return self._json(etat_appli())
            if m == ["api", "appli", "telephone"]:
                return self._json(regler_telephone(corps.get("actif") if "actif" in corps else None,
                                                   bool(corps.get("nouveau_code"))))
            if m == ["api", "mobile", "relier"]:   # téléphone : copie une fois les comptes et les stats du PC
                if not chemins.MOBILE:
                    return self._erreur("Seulement dans l'appli du téléphone.", 403)
                nb = telephone.importer_depuis_pc(str(corps.get("hote") or ""), str(corps.get("code") or ""),
                                                  DOSSIER_DONNEES)
                return self._json({"ok": True, "fichiers": nb})
            if m == ["api", "appli", "arriere-plan"]:
                regler_arriere_plan(bool(corps.get("actif")))
                return self._json(etat_appli())
            if m == ["api", "appli", "quitter"]:
                self._json({"message": "À plus !"})
                return quitter()
            if m == ["api", "au-revoir"]:  # la fenêtre se ferme (ou la page se recharge)
                _presence["au_revoir"] = time.time()
                return self._json({})
            if len(m) == 4 and m[:2] == ["api", "jeux"]:
                jeu = self._jeu(m[2])
                if not jeu:
                    return

                if m[3] == "connexion":
                    if not jeu.connexion_nom:
                        return self._erreur("Ce jeu n'a pas de connexion directe.")
                    lancer_connexion(jeu)
                    return self._json(CONNEXIONS[jeu.id])

                if m[3] == "deconnexion":
                    reglages = {k: v for k, v in CONFIG.reglages(jeu.cle_reglages).items()
                                if k not in jeu.cles_connexion and k != "pseudo_compte"}
                    if hasattr(jeu, "deconnecter"):  # ex : Valorant (pas de fenêtre de connexion à effacer)
                        reglages.update(jeu.deconnecter(DOSSIER_DONNEES) or {})
                    CONFIG.enregistrer(jeu.cle_reglages, reglages)
                    if jeu.dossier_connexion:  # on oublie aussi la session de la fenêtre de connexion
                        import shutil
                        shutil.rmtree(os.path.join(DOSSIER_DONNEES, jeu.dossier_connexion), ignore_errors=True)
                    return self._json({"message": f"Déconnecté de {jeu.connexion_nom}", **resume_jeu(jeu)})

                if m[3] == "inventaire":   # retirer un objet (ou tout) de l'inventaire lu à l'écran
                    if not hasattr(jeu, "oublier_objet"):
                        return self._erreur("Pas d'inventaire pour ce jeu.")
                    jeu.oublier_objet(DOSSIER_DONNEES, corps.get("nom") or None)
                    details = BDD.lire_details(jeu.id)[0] or {}
                    from jeux import _bloxfruits_objets as bf_objets
                    garde = [x for x in details.get("sections", []) if x.get("titre") not in ("Build", "Inventaire")]
                    BDD.enregistrer_details(jeu.id, {**details, "sections": bf_objets.sections(DOSSIER_DONNEES) + garde})
                    return self._json({"message": "Inventaire mis à jour", **resume_jeu(jeu)})

                if m[3] == "ouvrir":   # page « carte » : ouvre une carte interactive dans sa fenêtre
                    if not hasattr(jeu, "ouvrir"):
                        return self._erreur("Rien à ouvrir pour ce jeu.")
                    mode = corps.get("mode") if corps.get("mode") in ("fenetre", "connexion", "navigateur") else "fenetre"
                    return self._json({"message": jeu.ouvrir(str(corps.get("carte") or ""), DOSSIER_DONNEES, mode)})

                if m[3] == "test-ecran":
                    if not jeu.lit_ecran:
                        return self._erreur("Ce jeu ne lit pas l'écran.")
                    try:
                        delai = min(max(int(corps.get("delai", 8)), 0), 20)
                    except (TypeError, ValueError):
                        delai = 8
                    return self._json({**tester_ecran(jeu, delai), **resume_jeu(jeu)})

                if m[3] == "actualiser":
                    message = actualiser(jeu)
                    return self._json({"message": message, **resume_jeu(jeu)})

                if m[3] == "reglages":
                    cles = {r["cle"] for r in jeu.reglages}
                    CONFIG.enregistrer(jeu.cle_reglages, {**CONFIG.reglages(jeu.cle_reglages),
                                                **{k: v for k, v in corps.items() if k in cles}})
                    return self._json({"message": "Réglages enregistrés", **resume_jeu(jeu)})

                if m[3] == "mesure":
                    stat = next((s for s in jeu.stats if s.cle == corps.get("cle")), None)
                    if stat is None:
                        return self._erreur("Stat inconnue.")
                    try:
                        valeur = float(str(corps.get("valeur")).replace(",", ".").replace(" ", ""))
                    except ValueError:
                        return self._erreur("La valeur doit être un nombre.")
                    date = corps.get("date") or ""
                    if not date or date == datetime.now().date().isoformat():
                        date = maintenant()
                    else:
                        date = f"{date}T12:00:00"
                    BDD.ajouter_mesure(jeu.id, stat.cle, valeur, "manuel", corps.get("note", ""), date)
                    return self._json({"message": f"{stat.nom} : ajouté", **resume_jeu(jeu)})

            self._erreur("Route inconnue.", 404)

        self._protege(action)

    def _recevoir_donnees(self, id_jeu):
        jeu = self._jeu(id_jeu)
        if not jeu:
            return
        if not jeu.import_donnees:
            return self._erreur("Ce jeu n'importe pas de fichier.")
        taille = int(self.headers.get("Content-Length") or 0)
        if not 0 < taille < 400_000_000:
            return self._erreur("Fichier vide ou trop gros.")
        contenu = self.rfile.read(taille)   # lu en mémoire seulement : jamais enregistré
        nom = unquote(self.headers.get("X-Nom-Fichier") or "donnees.html")[:120]
        try:
            resultats, rapport = jeu.importer_donnees(contenu, nom, DOSSIER_DONNEES)
        except ErreurJeu as e:
            return self._erreur(str(e))
        except Exception as e:
            return self._erreur(f"Fichier illisible ({e.__class__.__name__}).")
        finally:
            del contenu
        if not resultats:
            return self._json({"ok": False, "message": "Aucune partie reconnue dans ce fichier.", "rapport": rapport})
        jeux = []
        for id_cible, valeurs in resultats.items():
            cible = JEUX.get(id_cible)
            if not cible:
                continue
            try:
                actualiser(cible)
            except ErreurJeu:
                enregistrer_valeurs(cible, valeurs)
            jeux.append({"id": cible.id, "nom": cible.nom, "stats": len(valeurs)})
        return self._json({"ok": True, "message": f"Données importées pour {len(jeux)} jeu(x)", "jeux": jeux,
                           "rapport": rapport, **resume_jeu(jeu)})

    def _recevoir_image(self, id_jeu):
        jeu = self._jeu(id_jeu)
        if not jeu:
            return
        if not jeu.import_images:
            return self._erreur("Ce jeu ne lit pas de captures.")
        taille = int(self.headers.get("Content-Length") or 0)
        if not 0 < taille < 25_000_000:
            return self._erreur("Image vide ou trop grosse.")
        donnees = self.rfile.read(taille)
        type_image = (self.headers.get("Content-Type") or "").lower()
        extension = {"image/png": ".png", "image/jpeg": ".jpg", "image/jpg": ".jpg", "image/bmp": ".bmp"}.get(type_image)
        if not extension:
            return self._erreur("Format non lu : envoie une capture en PNG ou JPG (pas HEIC).")
        nom = unquote(self.headers.get("X-Nom-Fichier") or "capture")[:120]
        chemin = os.path.join(DOSSIER_DONNEES, f"capture_importee_{threading.get_ident()}{extension}")
        try:
            with open(chemin, "wb") as f:
                f.write(donnees)
            valeurs, lignes, message = jeu.lire_capture(chemin, DOSSIER_DONNEES, nom)
        finally:
            try:
                os.remove(chemin)  # on ne garde jamais l'image
            except OSError:
                pass
        nouvelles = enregistrer_valeurs(jeu, valeurs)
        if hasattr(jeu, "fiche"):
            BDD.enregistrer_details(jeu.id, jeu.fiche(CONFIG.reglages(jeu.cle_reglages), DOSSIER_DONNEES))
        stats = {s.cle: s for s in jeu.stats}
        trouve = [{"nom": stats[k].nom, "valeur": v, "unite": stats[k].unite, "decimales": stats[k].decimales}
                  for k, v in valeurs.items() if k in stats]
        self._json({"message": f"{nom} : {message}", "trouve": trouve, "nouvelles": nouvelles,
                    "lignes": lignes[:40], **resume_jeu(jeu)})

    def do_DELETE(self):
        m = self._morceaux()

        def action():
            if len(m) == 3 and m[:2] == ["api", "mesures"] and m[2].isdigit():
                if BDD.supprimer_mesure(int(m[2])):
                    return self._json({"message": "Supprimé"})
                return self._erreur("Mesure introuvable.", 404)
            self._erreur("Route inconnue.", 404)

        self._protege(action)


def _deja_lance(port):
    """Vrai si AllMyStats tourne déjà sur ce port (on ne lance pas deux fois l'appli)."""
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/ping", timeout=1.5) as r:
            return json.loads(r.read()).get("appli") in SIGNATURES_CONNUES
    except Exception:
        return False


def _surveiller_fermeture(serveur):
    """Arrête le programme quand plus aucune fenêtre AllMyStats n'est ouverte."""
    debut = time.time()
    while True:
        time.sleep(1)
        maintenant_ = time.time()
        dernier = _presence["dernier_signe"]
        au_revoir = _presence["au_revoir"]
        if arriere_plan_actif():  # mode arrière-plan : on reste allumé
            continue
        if dernier is None:
            if maintenant_ - debut > 120:  # la fenêtre ne s'est jamais connectée
                break
            continue
        # Fenêtre fermée : « au revoir » reçu et pas de nouveau signe de vie depuis 4 s
        if au_revoir and au_revoir > dernier and maintenant_ - au_revoir > 4:
            break
        # Sécurité : plus aucun signe de vie depuis 3 min (fenêtre plantée, PC en veille...)
        if maintenant_ - dernier > 180:
            break
    serveur.shutdown()


def demarrer(port=8765, ouvrir_navigateur=True, mode_appli=False, arriere_plan=False):
    MODE["arriere_plan"] = arriere_plan
    if (mode_appli or arriere_plan) and _deja_lance(port):
        if not arriere_plan and "--relance" not in sys.argv:
            ouvrir_fenetre(f"http://localhost:{port}", DOSSIER_DONNEES)
        return

    reseau.preparer()
    if not chemins.MOBILE:   # sur le téléphone, c'est l'appli (APK / iPhone) qui se met à jour
        _installer_au_demarrage()
        threading.Thread(target=_boucle_maj, daemon=True, name="mises-a-jour").start()

    serveur = None
    for essai in range(port, port + 20):
        try:
            serveur = ThreadingHTTPServer(("127.0.0.1", essai), Gestionnaire)
            port = essai
            break
        except OSError:
            continue
    if serveur is None:
        raise SystemExit("Aucun port libre trouvé.")

    adresse = f"http://localhost:{port}"
    print("=" * 52)
    print("  AllMyStats est lancé !")
    print(f"  Ouvre {adresse} dans ton navigateur")
    print(f"  Jeux chargés : {', '.join(j.nom for j in JEUX.values()) or 'aucun'}")
    print(f"  Version {VERSION} · code : {chemins.RESSOURCES}")
    print(f"  Données : {DOSSIER_DONNEES}")
    print("  Pour arrêter : ferme cette fenêtre (ou Ctrl+C)")
    print("=" * 52)
    MODE["serveur"] = serveur
    if chemins.MOBILE:   # l'appli du téléphone lit le port ici pour afficher l'interface
        with open(os.path.join(DOSSIER_DONNEES, "port.txt"), "w") as f:
            f.write(str(port))
    elif reglages_appli().get("telephone") == "oui":
        telephone.demarrer(Gestionnaire, code_telephone, export_telephone)
    surveillance.demarrer(JEUX, CONFIG, DOSSIER_DONNEES, enregistrer_valeurs, actualiser, est_cache)
    if arriere_plan:
        pass  # pas de fenêtre : AllMyStats tourne en silence
    elif mode_appli:
        if "--relance" not in sys.argv:
            threading.Timer(0.3, lambda: ouvrir_fenetre(adresse, DOSSIER_DONNEES)).start()
        threading.Thread(target=_surveiller_fermeture, args=(serveur,), daemon=True).start()
    elif ouvrir_navigateur:
        threading.Timer(0.8, lambda: webbrowser.open(adresse)).start()
    try:
        serveur.serve_forever()
    except KeyboardInterrupt:
        print("\nÀ plus !")
    finally:
        serveur.server_close()
