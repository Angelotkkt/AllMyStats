"""Blox Fruits (Roblox).

Automatique :
  - connexion avec ton compte Roblox (vraie fenêtre roblox.com) : pseudo, badges même privés avec leur date,
    game pass, présence et amis qui jouent à Blox Fruits. AllMyStats n'écrit JAMAIS ta session Roblox dans
    un fichier : elle reste dans la fenêtre de connexion (comme dans un navigateur normal) ;
  - profil Roblox (avec ton pseudo) et infos du jeu en direct ;
  - tes badges Blox Fruits (ton inventaire Roblox doit être visible par tout le monde) ;
  - ton temps de jeu, tes sessions et la mer la plus loin atteinte, lus dans les journaux
    que Roblox écrit sur ce PC (%LOCALAPPDATA%\\Roblox\\logs).
Niveau, Beli, fragments, prime : le jeu ne les donne à personne, donc AllMyStats les LIT SUR TON ÉCRAN
pendant que tu joues (OCR de Windows, toutes les minutes, la capture est effacée tout de suite).
Tu peux aussi les corriger à la main.
"""

import glob
import json
import os
import re
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

from core import connexion_navigateur as navigateur
from core import diagnostic_ecran as diag
from core import windows

from . import _bloxfruits_objets as objets
from .base import ErreurJeu, Jeu, Stat

UNIVERS_BF = 994732206
PROCESSUS_ROBLOX = ["RobloxPlayerBeta", "Windows10Universal"]
# La fenêtre de Roblox, quel que soit le lanceur : nom du programme ou titre (Bloxstrap met parfois « Blox Fruits »)
MOTIF_ROBLOX = r"roblox|blox\s*fruits?"
MOTIF_PROGRAMME_ROBLOX = r"^(robloxplayer\w*|roblox|windows10universal)\.exe$"
MERS = {2753915549: 1, 4442272183: 2, 7449423635: 3}  # lieux connus de Blox Fruits
NOMS_MERS = {1: "First Sea", 2: "Second Sea", 3: "Third Sea"}
UA = {"User-Agent": "AllMyStats/1.0", "Accept": "application/json"}

MOTIF_HEURE = re.compile(r"^(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d+)?)Z")
MOTIF_REJOINT = re.compile(r"! Joining game '[^']*' place (\d+)")
MOTIF_UNIVERS = re.compile(r"universeid:(\d+)", re.I)
MOTIFS_JOUEUR = [re.compile(p, re.I) for p in (r"userid:(\d+)", r"\buserId[\"']?\s*[:=]\s*[\"']?(\d{3,})")]
MOTIF_QUITTE = re.compile(r"Client:Disconnect|leaveUGCGameInternal|Time to disconnect replication data")
JOURS = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]


_CSRF = {"jeton": ""}


def _get(url, corps=None, timeout=15, session=None, _essai=0):
    """Appelle une API Roblox. `session` = connexion Roblox (gardée en mémoire seulement)."""
    data = json.dumps(corps).encode() if corps is not None else None
    entetes = dict(UA)
    if data:
        entetes["Content-Type"] = "application/json"
    if session:
        entetes["Cookie"] = f".ROBLOSECURITY={session}"
        if _CSRF["jeton"]:
            entetes["x-csrf-token"] = _CSRF["jeton"]
    req = urllib.request.Request(url, data=data, headers=entetes)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        jeton = e.headers.get("x-csrf-token") if e.headers else None
        if e.code == 403 and jeton and session and _essai == 0:
            _CSRF["jeton"] = jeton
            return _get(url, corps, timeout, session, 1)
        raise


def _lire(chemin, defaut):
    try:
        with open(chemin, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return defaut


def _ecrire(chemin, data):
    with open(chemin, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)


def _heure(ligne):
    m = MOTIF_HEURE.match(ligne)
    if not m:
        return None
    try:
        return datetime.fromisoformat(m.group(1)).replace(tzinfo=timezone.utc).timestamp()
    except ValueError:
        return None


def _nombre(texte):
    chiffres = re.sub(r"[^\d]", "", texte or "")
    return int(chiffres) if chiffres else None


def lire_stats_ecran(lignes):
    """Trouve niveau, Beli, fragments et prime dans le texte lu sur l'écran de Blox Fruits."""
    valeurs = {}
    texte = "\n".join(lignes)
    m = re.search(r"\b(?:Lv|Lvl|Level|Niveau|Niv)\s*[.:]?\s*(\d{1,4})\b", texte, re.I)
    if m and 1 <= int(m.group(1)) <= 2800:
        valeurs["niveau"] = int(m.group(1))
    for ligne in lignes:
        propre = ligne.replace(" ", "")
        # Beli : une ligne qui ne contient QUE « $1,234,567 » (le compteur en bas de l'écran)
        if re.fullmatch(r"\$\d{1,3}(?:[,.]\d{3})*|\$\d{1,11}", propre):
            n = _nombre(propre)
            if n is not None and n <= 50_000_000_000:
                valeurs.setdefault("beli", n)
        # Fragments : une ligne qui ne contient QUE « ƒ12,345 »
        elif re.fullmatch(r"[ƒfF]\d{1,3}(?:[,.]\d{3})*|[ƒfF]\d{1,9}", propre):
            n = _nombre(propre)
            if n is not None and n <= 10_000_000:
                valeurs.setdefault("fragments", n)
    m = re.search(r"(?:Bounty|Honor|Prime|Honneur)\s*[:\-]?\s*\$?\s*(\d{1,3}(?:[,.\s]\d{3})+|\d{1,9})", texte, re.I)
    if m:
        valeurs["prime"] = _nombre(m.group(1))
    return valeurs


class BloxFruits(Jeu):
    id = "bloxfruits"
    nom = "Blox Fruits"
    icone = ""
    couleur = "#f0904a"
    stat_vedette = "niveau"
    connexion_nom = "Roblox"
    cles_connexion = ("roblox_connecte",)
    dossier_connexion = "connexion_roblox"
    connexion_aide = ("Connecte-toi avec ton compte Roblox pour avoir aussi tes badges (même privés), tes game pass "
                      "et tes amis qui jouent à Blox Fruits.")

    reglages = [
        {
            "cle": "pseudo",
            "nom": "Pseudo Roblox",
            "aide": "Rempli tout seul avec « Se connecter ». Sinon : ton nom d'utilisateur Roblox "
                    "(celui avec @, pas le nom d'affichage).\n"
                    "Pour voir tes badges sans te connecter : sur Roblox, Paramètres > Confidentialité > "
                    "« Qui peut voir mon inventaire ? » > Tout le monde.",
        },
    ]

    P, B, T, M = "Ton perso", "Badges & game pass", "Temps de jeu", "En ce moment"
    stats = [
        # --- À noter (le jeu ne partage pas ces infos) ---
        Stat("niveau", "Niveau", "auto", groupe=P, icone="bf_niveau", modifiable=True, etiquette="écran",
             aide="Lu sur ton écran pendant que tu joues (niveau max : 2800)"),
        Stat("beli", "Beli", "auto", groupe=P, icone="beli", modifiable=True, etiquette="écran",
             aide="Lu sur ton écran pendant que tu joues"),
        Stat("fragments", "Fragments", "auto", groupe=P, icone="fragment", modifiable=True, etiquette="écran",
             aide="Lu sur ton écran pendant que tu joues"),
        Stat("prime", "Prime / Honneur", "auto", groupe=P, icone="prime", modifiable=True, etiquette="écran",
             aide="Lu sur ton écran quand ta prime est affichée"),
        Stat("maitrise", "Maîtrise du fruit", "manuel", groupe=P, icone="maitrise"),
        # --- Automatique : badges ---
        Stat("badges", "Badges obtenus", "auto", groupe=B, icone="badge"),
        Stat("badges_pourcent", "Badges complétés", "auto", unite="%", decimales=1, groupe=B, icone="badge_etoile"),
        Stat("passes", "Game pass possédés", "auto", groupe=B, icone="ticket"),
        # --- Automatique : journaux Roblox de ce PC ---
        Stat("temps_total", "Temps de jeu suivi", "auto", unite="h", decimales=1, groupe=T, icone="horloge",
             aide="Compté depuis que AllMyStats lit les journaux de Roblox sur ce PC"),
        Stat("temps_7j", "Ces 7 derniers jours", "auto", unite="h", decimales=1, groupe=T, icone="calendrier_semaine"),
        Stat("sessions", "Parties lancées", "auto", groupe=T, icone="manette"),
        Stat("mer_max", "Mer la plus loin", "auto", groupe=T, icone="mer", aide="1 = First Sea, 2 = Second Sea, 3 = Third Sea"),
        # --- Le jeu (pour tout le monde) ---
        Stat("amis_en_jeu", "Amis sur Blox Fruits", "auto", groupe=M, icone="amis",
             aide="Tes amis Roblox qui jouent à Blox Fruits en ce moment"),
        Stat("joueurs_en_ligne", "Joueurs connectés", "auto", groupe=M, icone="joueurs"),
    ]

    # ------------------------------------------------------------------ lecture de l'écran

    def _en_partie(self):
        """Vrai si les journaux Roblox montrent une partie de Blox Fruits en cours, faux si c'est un autre jeu.
        None quand on ne peut pas savoir (journaux introuvables, muets ou anciens) : on lit l'écran quand même."""
        fichiers = []
        for d in self._dossiers_journaux():
            fichiers += [f for f in glob.glob(os.path.join(d, "*.log")) if "bootstrapper" not in f.lower()]
        maintenant = time.time()
        recents = []
        for f in fichiers:
            try:
                quand = os.path.getmtime(f)
            except OSError:
                continue
            if maintenant - quand < 6 * 3600:
                recents.append((quand, f))
        # Roblox écrit plusieurs journaux en même temps : on regarde les plus récents, pas seulement le dernier
        dernier = None   # (heure, dans_bf, ligne, fichier) du dernier évènement de partie trouvé
        for quand, chemin in sorted(recents, reverse=True)[:6]:
            evenement = self._dernier_evenement(chemin)
            if evenement is None:
                continue
            heure = evenement[0] if evenement[0] is not None else quand
            if dernier is None or heure > dernier[0]:
                dernier = (heure, evenement[1], evenement[2], os.path.basename(chemin))
        self._preuve = dernier
        return None if dernier is None else dernier[1]

    _preuve = None

    def _texte_preuve(self):
        """Ce qui a été trouvé dans les journaux, pour le test : « … » (fichier, il y a X min)."""
        if not self._preuve:
            return ""
        heure, _, ligne, fichier = self._preuve
        ligne = re.sub(r"^\S+\s*", "", ligne.strip())[:140]
        il_y_a = max(0, int((time.time() - heure) // 60))
        return f" Dernière info trouvée (il y a {il_y_a} min, {fichier}) : « {ligne} »."

    @staticmethod
    def _dernier_evenement(chemin):
        """Dernier évènement « partie » d'un journal : (heure ou None, True/False/None).
        True = Blox Fruits, False = autre jeu ou partie quittée, None = lieu inconnu (on ne sait pas)."""
        try:
            with open(chemin, "r", encoding="utf-8", errors="ignore") as f:
                lignes = f.readlines()[-6000:]
        except OSError:
            return None
        evenement = None
        for ligne in lignes:
            m = MOTIF_REJOINT.search(ligne)
            if m:
                lieu = int(m.group(1))
                evenement = (_heure(ligne), True if lieu in MERS else None, ligne)
                continue
            bas = ligne.lower()
            # « placeid:…, universeid:… » : le compte rendu d'arrivée dans une partie (pas les autres mentions)
            u = MOTIF_UNIVERS.search(ligne) if "universeid" in bas and "placeid" in bas else None
            if u and int(u.group(1)) > 0:
                univers = int(u.group(1))
                evenement = (_heure(ligne), True if univers == UNIVERS_BF else False, ligne)
            elif MOTIF_QUITTE.search(ligne):
                evenement = (_heure(ligne), False, ligne)
        return evenement

    lit_ecran = True
    met_devant = True   # le test met lui-même la fenêtre de Roblox au premier plan
    consigne_ecran = "Va sur Roblox, dans une partie de Blox Fruits, avec ton niveau et tes Beli visibles (aucun menu ouvert)."
    _essai = None   # dernier essai automatique quand il n'y a pas eu de capture

    def surveiller(self, reglages, dossier):
        if os.name != "nt" or not self._roblox_lance():
            return None
        if self._en_partie() is False:
            self._essai = {"etat": "PAS_EN_PARTIE", "quand": time.time(),
                           "message": "Roblox est lancé, mais pas sur Blox Fruits"}
            return None
        self._essai = None
        r = windows.lire_ecran_complet(PROCESSUS_ROBLOX, motif=MOTIF_ROBLOX)
        if r["etat"] != "OK":
            return None
        self._lire_inventaire_et_build(r["lignes"], dossier)
        valeurs = self._garder_lecture(lire_stats_ecran(r["lignes"]), dossier)
        essai = windows.dernier_essai(PROCESSUS_ROBLOX)
        if essai:
            essai["trouve"] = len(valeurs)
        return valeurs

    def _roblox_lance(self):
        return bool(windows.processus_lances([p + ".exe" for p in PROCESSUS_ROBLOX])
                    or windows.processus_par_motif(MOTIF_PROGRAMME_ROBLOX))

    def _lire_inventaire_et_build(self, lignes, dossier):
        """Inventaire ouvert -> objets reconnus ; menu Stats ouvert -> points du build. Renvoie (objets, build)."""
        try:
            catalogue = objets.catalogue(dossier).get("objets") or {}
        except Exception:
            catalogue = {}
        inventaire = objets.lire_inventaire(lignes, catalogue)
        if len(inventaire) < 3:   # moins de 3 objets : sûrement du texte de quête ou de PNJ, pas l'inventaire
            inventaire = {}
        build = objets.lire_build(lignes)
        objets.garder(dossier, inventaire, build)
        return inventaire, build

    def oublier_objet(self, dossier, nom=None):
        objets.oublier(dossier, nom)

    def _garder_lecture(self, valeurs, dossier):
        # Le niveau ne peut pas baisser : une lecture plus basse est sûrement une erreur de l'OCR
        dernier = _lire(os.path.join(dossier, "bf_ecran.json"), {})
        if "niveau" in valeurs and valeurs["niveau"] < dernier.get("niveau", 0):
            del valeurs["niveau"]
        if valeurs:
            _ecrire(os.path.join(dossier, "bf_ecran.json"), {**dernier, **valeurs, "quand": time.time()})
        return valeurs

    def tester_ecran(self, reglages, dossier):
        auto = windows.dernier_essai(PROCESSUS_ROBLOX)
        if self._essai and (not auto or self._essai["quand"] > auto["quand"]):
            auto = self._essai
        resultat = {"etapes": [], "lignes": [], "valeurs": {}, "cible": self.id,
                    "dernier_essai": diag.resume_essai(auto)}
        etapes = resultat["etapes"]
        if os.name == "nt" and not self._roblox_lance():
            etapes.append(diag.etape("erreur", "Roblox lancé", "Roblox n'est pas ouvert. Lance une partie de Blox Fruits, "
                                     "puis refais le test."))
            return resultat
        if os.name == "nt":
            etapes.append(diag.etape("ok", "Roblox lancé"))
            en_partie = self._en_partie()
            if en_partie:
                etapes.append(diag.etape("ok", "Partie de Blox Fruits", "Trouvée dans les journaux de Roblox."))
            elif en_partie is None:
                etapes.append(diag.etape("neutre", "Partie de Blox Fruits",
                                         "Les journaux de Roblox ne disent pas à quoi tu joues : AllMyStats lit l'écran "
                                         "dès que Roblox est devant."))
            else:
                etapes.append(diag.etape("alerte", "Partie de Blox Fruits",
                                         "D'après les journaux de Roblox, tu n'es pas sur Blox Fruits. La lecture "
                                         "automatique attend que tu sois dans une partie de Blox Fruits."
                                         + self._texte_preuve()))
        r = windows.lire_ecran_complet(PROCESSUS_ROBLOX, garder_essai=False, motif=MOTIF_ROBLOX, activer=True)
        etapes_capture, lu = diag.etapes_capture(r, "Roblox")
        etapes += etapes_capture
        resultat["lignes"] = r["lignes"][:40]
        if lu:
            inventaire, build = self._lire_inventaire_et_build(r["lignes"], dossier)
            valeurs = lire_stats_ecran(r["lignes"])
            if valeurs:
                resultat["valeurs"] = self._garder_lecture(dict(valeurs), dossier)
                etapes.append(diag.etape("ok", "Stats reconnues"))
            elif not (inventaire or build):
                etapes.append(diag.etape("alerte", "Stats reconnues",
                                         "Aucun chiffre de Blox Fruits trouvé dans le texte lu. Ton niveau (« Lv. … ») "
                                         "et tes Beli (« $… ») doivent être visibles : ferme les menus qui les cachent."))
            if inventaire:
                etapes.append(diag.etape("ok", "Inventaire", f"{len(inventaire)} objet(s) reconnu(s) : "
                                         + ", ".join(sorted(inventaire)[:8]) + ("…" if len(inventaire) > 8 else "")))
            if build:
                etapes.append(diag.etape("ok", "Build", " · ".join(f"{objets.NOMS_BUILD[k]} {v}" for k, v in build.items())))
        return resultat

    # ------------------------------------------------------------------

    def _joueur_des_journaux(self):
        """Retrouve l'identifiant Roblox du joueur dans les journaux les plus récents de ce PC."""
        fichiers = []
        for d in self._dossiers_journaux():
            fichiers += glob.glob(os.path.join(d, "*.log"))
        fichiers.sort(key=os.path.getmtime, reverse=True)
        for fichier in fichiers[:30]:
            try:
                with open(fichier, "r", encoding="utf-8", errors="ignore") as f:
                    texte = f.read()
            except OSError:
                continue
            for motif in MOTIFS_JOUEUR:
                trouves = [t for t in motif.findall(texte) if t != "0"]
                if trouves:
                    return int(trouves[-1])
        return None

    def nom_du_compte(self, reglages):
        return f"@{reglages['pseudo']}" if reglages.get("pseudo") else ""

    def connexion(self, reglages, dossier):
        try:
            cookies = navigateur.recuperer_cookies(
                "https://www.roblox.com/login",
                os.path.join(dossier, "connexion_roblox"),
                domaine="roblox.com",
                est_connecte=lambda c: bool(c.get(".ROBLOSECURITY")),
            )
        except navigateur.ErreurConnexion as e:
            raise ErreurJeu(str(e))
        try:
            moi = _get("https://users.roblox.com/v1/users/authenticated", session=cookies[".ROBLOSECURITY"])
        except Exception:
            raise ErreurJeu("Connecté, mais Roblox ne répond pas. Réessaie dans un instant.")
        # La session n'est PAS renvoyée : seuls le pseudo et « connecté » sont enregistrés.
        return ({"pseudo": moi["name"], "roblox_connecte": "oui"},
                f"Connecté en tant que {moi.get('displayName') or moi['name']} (@{moi['name']})")

    def _trouver_par_journaux(self):
        id_joueur = self._joueur_des_journaux()
        if not id_joueur:
            raise ErreurJeu("Je n'ai pas trouvé ton compte : lance Roblox sur ce PC et rejoins un jeu "
                            "(Blox Fruits par exemple), puis réessaie. Tu peux aussi taper ton pseudo dans les Réglages.")
        try:
            infos = _get(f"https://users.roblox.com/v1/users/{id_joueur}")
        except Exception:
            raise ErreurJeu("Compte trouvé, mais impossible de joindre Roblox. Vérifie ta connexion internet.")
        return {"pseudo": infos["name"]}, f"Compte trouvé : {infos.get('displayName') or infos['name']} (@{infos['name']})"

    def recuperer(self, reglages, dossier):
        pseudo = (reglages.get("pseudo") or "").strip().lstrip("@")
        if not pseudo:
            try:
                pseudo = self._trouver_par_journaux()[0]["pseudo"]
            except ErreurJeu:
                raise ErreurJeu("Clique sur « Se connecter avec Roblox » ou mets ton pseudo dans les Réglages.")

        valeurs, sections, etat = {}, [], []
        id_joueur = None

        # 0) Connexion Roblox (relue sans fenêtre, jamais enregistrée par AllMyStats)
        session = None
        if reglages.get("roblox_connecte"):
            try:
                session = navigateur.lire_session("https://www.roblox.com/robots.txt",
                                                  os.path.join(dossier, "connexion_roblox"),
                                                  "roblox.com").get(".ROBLOSECURITY")
                moi = _get("https://users.roblox.com/v1/users/authenticated", session=session) if session else None
                if not moi:
                    raise ErreurJeu("expirée")
                pseudo = moi["name"]
                etat.append({"nom": "Compte Roblox", "icone": "ticket", "ok": True, "texte": "connecté"})
            except (ErreurJeu, navigateur.ErreurConnexion, urllib.error.URLError, OSError, KeyError):
                session = None
                etat.append({"nom": "Compte Roblox", "icone": "ticket", "ok": False,
                             "texte": "connexion expirée : clique sur « Se connecter avec Roblox »"})
        else:
            etat.append({"nom": "Compte Roblox", "icone": "ticket", "ok": None,
                         "texte": "pas connecté : clique sur « Se connecter avec Roblox » pour tes badges privés, "
                                  "tes game pass et tes amis"})

        # 1) Profil Roblox
        try:
            id_joueur, carte = self._profil(pseudo, dossier)
            sections.append({"titre": "Ton profil Roblox", "icone": "jeu_bloxfruits", "cartes": [carte]})
            etat.append({"nom": "Roblox", "icone": "jeu_bloxfruits", "ok": True, "texte": carte["titre"]})
        except ErreurJeu as e:
            etat.append({"nom": "Roblox", "icone": "jeu_bloxfruits", "ok": False, "texte": str(e)})

        # 2) Badges Blox Fruits
        if id_joueur:
            try:
                v, s, texte = self._badges(id_joueur, dossier, session)
                valeurs.update(v)
                sections += s
                etat.append({"nom": "Badges", "icone": "badge", "ok": True, "texte": texte})
            except ErreurJeu as e:
                etat.append({"nom": "Badges", "icone": "badge", "ok": False, "texte": str(e)})

        # 2 bis) Avec la connexion : présence, amis, game pass
        if id_joueur and session:
            v, s = self._social(id_joueur, session)
            valeurs.update(v)
            sections = s[:1] + sections + s[1:] if s and s[0]["titre"] == "En ce moment" else sections + s

        # 3) Temps de jeu depuis les journaux Roblox
        try:
            v, s, texte = self._temps_de_jeu(dossier)
            valeurs.update(v)
            sections += s
            etat.append({"nom": "Temps de jeu", "icone": "horloge", "ok": True if v else None, "texte": texte})
        except Exception as e:  # un journal bizarre ne doit pas tout casser
            etat.append({"nom": "Temps de jeu", "icone": "horloge", "ok": False, "texte": f"lecture impossible ({e})"})

        # 4) Le jeu en direct
        try:
            jeu = _get(f"https://games.roblox.com/v1/games?universeIds={UNIVERS_BF}")["data"][0]
            valeurs["joueurs_en_ligne"] = jeu.get("playing", 0)
            sections.append({"titre": "Blox Fruits en ce moment", "icone": "joueurs", "lignes": [
                ["Joueurs connectés", f"{jeu.get('playing', 0):,}".replace(",", " "), "joueurs"],
                ["Visites", f"{jeu.get('visits', 0):,}".replace(",", " "), "visites"],
                ["Favoris", f"{jeu.get('favoritedCount', 0):,}".replace(",", " "), "amitie"],
                ["Dernière mise à jour", (jeu.get("updated") or "")[:10], "calendrier_semaine"],
            ]})
        except Exception:
            pass

        if not valeurs and not any(e["ok"] for e in etat):
            raise ErreurJeu(" / ".join(f"{e['nom']} : {e['texte']}" for e in etat if e["ok"] is False)
                            or "Aucune donnée récupérée.")

        reussies = [e["nom"] for e in etat if e["ok"]]
        message = "Récupéré : " + ", ".join(reussies) if reussies else "Rien de nouveau"
        try:   # Build et Inventaire (lus à l'écran) en haut de la page
            sections = objets.sections(dossier) + sections
        except Exception as e:
            etat.append({"nom": "Inventaire", "icone": "bf_inventaire", "ok": False, "texte": f"catalogue indisponible ({e})"})
        return valeurs, {"etat": etat, "sections": sections}, message

    # ------------------------------------------------------------------ profil

    def _profil(self, pseudo, dossier):
        cache = _lire(os.path.join(dossier, "bf_profil.json"), {})
        try:
            rep = _get("https://users.roblox.com/v1/usernames/users",
                       {"usernames": [pseudo], "excludeBannedUsers": False})
            if not rep.get("data"):
                raise ErreurJeu(f"Aucun compte Roblox « {pseudo} ». Vérifie le pseudo (sans le @).")
            joueur = rep["data"][0]
            id_joueur = joueur["id"]
            infos = _get(f"https://users.roblox.com/v1/users/{id_joueur}")
            image = None
            try:
                image = _get(f"https://thumbnails.roblox.com/v1/users/avatar-headshot?userIds={id_joueur}"
                             f"&size=150x150&format=Png&isCircular=false")["data"][0].get("imageUrl")
            except Exception:
                pass
            cache = {"pseudo": pseudo, "id": id_joueur, "infos": infos, "image": image}
            _ecrire(os.path.join(dossier, "bf_profil.json"), cache)
        except ErreurJeu:
            raise
        except (urllib.error.URLError, TimeoutError, OSError, KeyError, IndexError):
            if cache.get("pseudo") != pseudo:
                raise ErreurJeu("Impossible de joindre Roblox. Vérifie ta connexion internet.")

        infos = cache["infos"]
        cree = (infos.get("created") or "")[:10]
        carte = {
            "titre": infos.get("displayName") or pseudo,
            "sous_titre": f"@{infos.get('name', pseudo)}",
            "image": cache.get("image"),
            "icone": "jeu_bloxfruits",
            "couleur": self.couleur,
            "lignes": [["Compte créé le", cree or "?"], ["Identifiant", str(cache["id"])]],
        }
        if infos.get("description"):
            carte["lignes"].append(["Description", infos["description"][:120]])
        return cache["id"], carte

    # ------------------------------------------------------------------ badges

    def _badges(self, id_joueur, dossier, session=None):
        # Liste de tous les badges du jeu (gardée 1 jour)
        chemin = os.path.join(dossier, "bf_badges_jeu.json")
        cache = _lire(chemin, {})
        if cache.get("expire", 0) < time.time():
            tous, curseur = [], ""
            try:
                for _ in range(20):
                    rep = _get(f"https://badges.roblox.com/v1/universes/{UNIVERS_BF}/badges"
                               f"?limit=100&sortOrder=Asc&cursor={curseur}")
                    tous += rep.get("data") or []
                    curseur = rep.get("nextPageCursor")
                    if not curseur:
                        break
                cache = {"expire": time.time() + 86400, "badges": tous}
                _ecrire(chemin, cache)
            except Exception:
                if not cache.get("badges"):
                    raise ErreurJeu("Impossible de lire la liste des badges du jeu.")
        badges_jeu = {b["id"]: b for b in cache["badges"] if b.get("enabled", True)}
        if not badges_jeu:
            raise ErreurJeu("Le jeu n'a pas de badges visibles.")

        # Badges du joueur
        obtenus, curseur = [], ""
        try:
            for _ in range(40):
                rep = _get(f"https://badges.roblox.com/v1/users/{id_joueur}/badges"
                           f"?limit=100&sortOrder=Desc&cursor={curseur}", session=session)
                obtenus += [b["id"] for b in rep.get("data") or [] if b.get("id") in badges_jeu]
                curseur = rep.get("nextPageCursor")
                if not curseur:
                    break
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                raise ErreurJeu("Roblox ne montre pas tes badges : mets ton inventaire visible par "
                                "« Tout le monde » (Paramètres > Confidentialité).")
            raise ErreurJeu(f"Roblox a répondu une erreur (code {e.code}).")
        except (urllib.error.URLError, TimeoutError, OSError):
            raise ErreurJeu("Impossible de joindre Roblox.")

        dates = {}
        if session and obtenus:
            try:
                for i in range(0, len(obtenus), 100):
                    ids = ",".join(str(x) for x in obtenus[i:i + 100])
                    for d in _get(f"https://badges.roblox.com/v1/users/{id_joueur}/badges/awarded-dates"
                                  f"?badgeIds={ids}", session=session).get("data") or []:
                        dates[d["badgeId"]] = d.get("awardedDate") or ""
                obtenus.sort(key=lambda i: dates.get(i, ""), reverse=True)
            except Exception:
                pass

        icones = {}
        try:
            ids = ",".join(str(i) for i in list(badges_jeu)[:100])
            for d in _get(f"https://thumbnails.roblox.com/v1/badges/icons?badgeIds={ids}"
                          f"&size=150x150&format=Png")["data"]:
                icones[d["targetId"]] = d.get("imageUrl")
        except Exception:
            pass

        def carte(b, eu):
            taux = (b.get("statistics") or {}).get("winRatePercentage")
            desc = (b.get("displayDescription") or b.get("description") or "").strip()
            lignes = []
            if eu and dates.get(b["id"]):
                d = dates[b["id"]][:10]
                lignes.append(["Obtenu le", f"{d[8:10]}/{d[5:7]}/{d[:4]}"])
            if isinstance(taux, (int, float)):
                lignes.append(["Obtenu par", f"{taux * 100:.1f} % des joueurs".replace(".", ",")])
            return {
                "titre": b.get("displayName") or b.get("name"),
                "sous_titre": desc[:70] + ("…" if len(desc) > 70 else ""),
                "image": icones.get(b["id"]),
                "icone": "badge" if eu else "badge_verrou",
                "couleur": "#f0904a" if eu else "#5a6078",
                "lignes": lignes,
            }

        restants = [b for i, b in badges_jeu.items() if i not in set(obtenus)]
        restants.sort(key=lambda b: -((b.get("statistics") or {}).get("winRatePercentage") or 0))
        sections = []
        if obtenus:
            sections.append({"titre": "Tes badges Blox Fruits", "icone": "badge",
                             "cartes": [carte(badges_jeu[i], True) for i in obtenus]})
        if restants:
            sections.append({"titre": "Badges à débloquer", "icone": "badge_verrou", "compact": True,
                             "cartes": [{"titre": b.get("displayName") or b.get("name"),
                                         "sous_titre": "",
                                         "image": icones.get(b["id"]), "icone": "badge_verrou",
                                         "couleur": "#5a6078"} for b in restants]})
        total = len(badges_jeu)
        valeurs = {"badges": len(obtenus), "badges_pourcent": round(len(obtenus) * 100 / total, 1)}
        return valeurs, sections, f"{len(obtenus)}/{total}"

    # ------------------------------------------------------------------ avec la connexion

    def _social(self, id_joueur, session):
        valeurs, sections, lignes = {}, [], []
        PRESENCE = "https://presence.roblox.com/v1/presence/users"

        def lieu(p):
            mer = MERS.get(p.get("placeId") or p.get("rootPlaceId"))
            return NOMS_MERS.get(mer, "Blox Fruits")

        # Où es-tu en ce moment ?
        try:
            p = _get(PRESENCE, {"userIds": [id_joueur]}, session=session)["userPresences"][0]
            type_p = p.get("userPresenceType")
            if type_p == 2 and p.get("universeId") == UNIVERS_BF:
                texte = f"en train de jouer · {lieu(p)}"
            elif type_p == 2:
                texte = f"dans un autre jeu{' · ' + p['lastLocation'] if p.get('lastLocation') else ''}"
            elif type_p == 1:
                texte = "en ligne sur Roblox"
            elif type_p == 3:
                texte = "dans Roblox Studio"
            else:
                texte = "hors ligne"
            lignes.append(["Toi", texte, "manette"])
        except Exception:
            pass

        # Tes amis sur Blox Fruits
        try:
            amis = [a["id"] for a in _get(f"https://friends.roblox.com/v1/users/{id_joueur}/friends",
                                          session=session).get("data") or []]
            presences = []
            for i in range(0, len(amis), 100):
                presences += _get(PRESENCE, {"userIds": amis[i:i + 100]}, session=session).get("userPresences") or []
            en_jeu = [p for p in presences if p.get("userPresenceType") == 2 and p.get("universeId") == UNIVERS_BF]
            valeurs["amis_en_jeu"] = len(en_jeu)
            lignes.append(["Amis sur Blox Fruits", f"{len(en_jeu)} sur {len(amis)} amis", "amis"])
            if en_jeu:
                ids = [p["userId"] for p in en_jeu][:50]
                noms, images = {}, {}
                try:
                    for u in _get("https://users.roblox.com/v1/users", {"userIds": ids,
                                                                         "excludeBannedUsers": True})["data"]:
                        noms[u["id"]] = u.get("displayName") or u.get("name")
                    for t in _get("https://thumbnails.roblox.com/v1/users/avatar-headshot?userIds="
                                  + ",".join(map(str, ids)) + "&size=150x150&format=Png")["data"]:
                        images[t["targetId"]] = t.get("imageUrl")
                except Exception:
                    pass
                sections.append({"titre": "Tes amis qui jouent en ce moment", "icone": "amis", "compact": True,
                                 "cartes": [{"titre": noms.get(p["userId"], f"#{p['userId']}"),
                                             "sous_titre": lieu(p), "image": images.get(p["userId"]),
                                             "icone": "amis", "couleur": "#4ed39a"} for p in en_jeu[:50]]})
        except Exception:
            pass

        if lignes:
            sections.insert(0, {"titre": "En ce moment", "icone": "manette", "lignes": lignes})

        # Tes game pass Blox Fruits
        try:
            passes = _get(f"https://games.roblox.com/v1/games/{UNIVERS_BF}/game-passes"
                          f"?limit=100&sortOrder=Asc").get("data") or []
            possedes = set()
            for gp in passes:
                try:
                    if _get(f"https://inventory.roblox.com/v1/users/{id_joueur}/items/GamePass/{gp['id']}",
                            session=session).get("data"):
                        possedes.add(gp["id"])
                except Exception:
                    pass
            images = {}
            try:
                for t in _get("https://thumbnails.roblox.com/v1/game-passes?gamePassIds="
                              + ",".join(str(g["id"]) for g in passes) + "&size=150x150&format=Png")["data"]:
                    images[t["targetId"]] = t.get("imageUrl")
            except Exception:
                pass
            if passes:
                valeurs["passes"] = len(possedes)
                passes.sort(key=lambda g: (g["id"] not in possedes, g.get("name", "")))
                sections.append({"titre": f"Tes game pass ({len(possedes)}/{len(passes)})", "icone": "ticket",
                                 "compact": True, "cartes": [{
                                     "titre": g.get("displayName") or g.get("name"),
                                     "sous_titre": "possédé" if g["id"] in possedes
                                     else (f"{g['price']} Robux" if g.get("price") else "pas encore"),
                                     "image": images.get(g["id"]),
                                     "icone": "ticket" if g["id"] in possedes else "badge_verrou",
                                     "couleur": "#f0904a" if g["id"] in possedes else "#5a6078"} for g in passes]})
        except Exception:
            pass
        return valeurs, sections

    # ------------------------------------------------------------------ temps de jeu

    def _dossiers_journaux(self):
        local = os.environ.get("LOCALAPPDATA") or os.path.join(os.path.expanduser("~"), "AppData", "Local")
        return [os.path.join(local, "Roblox", "logs")] + \
            glob.glob(os.path.join(local, "Packages", "ROBLOXCORPORATION.ROBLOX_*", "LocalState", "logs"))

    def _univers_du_lieu(self, lieu, cache):
        cle = str(lieu)
        if cle not in cache:
            if lieu in MERS:
                cache[cle] = UNIVERS_BF
            else:
                try:
                    cache[cle] = _get(f"https://apis.roblox.com/universes/v1/places/{lieu}/universe").get("universeId")
                except Exception:
                    return None  # on réessaiera la prochaine fois
        return cache[cle]

    def _temps_de_jeu(self, dossier):
        chemin_sessions = os.path.join(dossier, "bf_sessions.json")
        chemin_lieux = os.path.join(dossier, "bf_lieux.json")
        sessions = _lire(chemin_sessions, {})
        lieux = _lire(chemin_lieux, {})

        fichiers = []
        for d in self._dossiers_journaux():
            fichiers += glob.glob(os.path.join(d, "*.log"))
        fichiers = [f for f in fichiers if "bootstrapper" not in os.path.basename(f).lower()]

        for fichier in fichiers:
            try:
                with open(fichier, "r", encoding="utf-8", errors="ignore") as f:
                    lignes = f.readlines()
            except OSError:
                continue
            en_cours = None  # (heure, lieu, univers)
            derniere_heure = None
            trouvees = []
            for ligne in lignes:
                h = _heure(ligne) or derniere_heure
                if h:
                    derniere_heure = h
                m = MOTIF_REJOINT.search(ligne)
                if m and h:
                    if en_cours:
                        trouvees.append((*en_cours, h))
                    en_cours = [h, int(m.group(1)), None]
                    continue
                if en_cours:
                    u = MOTIF_UNIVERS.search(ligne)
                    if u and en_cours[2] is None:
                        en_cours[2] = int(u.group(1))
                    if MOTIF_QUITTE.search(ligne) and h:
                        trouvees.append((*en_cours, h))
                        en_cours = None
            if en_cours and derniere_heure:
                trouvees.append((*en_cours, derniere_heure))

            for debut, lieu, univers, fin in trouvees:
                univers = univers or self._univers_du_lieu(lieu, lieux)
                if univers != UNIVERS_BF:
                    continue
                duree = max(0, min(fin - debut, 12 * 3600))  # une partie ne dure pas 12 h…
                cle = f"{os.path.basename(fichier)}|{int(debut)}"
                sessions[cle] = {"debut": debut, "duree": duree, "lieu": lieu}

        _ecrire(chemin_sessions, sessions)
        _ecrire(chemin_lieux, lieux)

        if not sessions:
            if not fichiers:
                return {}, [], "pas de journaux Roblox sur ce PC (tu joues sur téléphone ?)"
            return {}, [], "aucune partie de Blox Fruits trouvée pour l'instant"

        liste = sorted(sessions.values(), key=lambda s: s["debut"])
        maintenant = time.time()
        total = sum(s["duree"] for s in liste)
        semaine = sum(s["duree"] for s in liste if s["debut"] > maintenant - 7 * 86400)
        mers = [MERS[s["lieu"]] for s in liste if s["lieu"] in MERS]
        valeurs = {
            "temps_total": round(total / 3600, 1),
            "temps_7j": round(semaine / 3600, 1),
            "sessions": len(liste),
        }
        if mers:
            valeurs["mer_max"] = max(mers)

        # Section : temps par jour sur les 7 derniers jours + dernières parties
        jours = []
        for i in range(6, -1, -1):
            jour = (datetime.now() - timedelta(days=i)).date()
            sec = sum(s["duree"] for s in liste if datetime.fromtimestamp(s["debut"]).date() == jour)
            jours.append([f"{JOURS[jour.weekday()]} {jour.day}", f"{sec / 3600:.1f} h".replace(".", ","), "horloge"])
        dernieres = []
        for s in reversed(liste[-8:]):
            mer = NOMS_MERS.get(MERS.get(s["lieu"]), "Blox Fruits")
            dernieres.append([datetime.fromtimestamp(s["debut"]).strftime("%d/%m à %H:%M"),
                              f"{int(s['duree'] // 60)} min · {mer}", "mer"])
        sections = [
            {"titre": "Tes 7 derniers jours", "icone": "calendrier_semaine", "lignes": jours},
            {"titre": "Tes dernières parties", "icone": "manette", "lignes": dernieres},
        ]
        texte = f"{len(liste)} partie(s) · {total / 3600:.1f} h".replace(".", ",")
        return valeurs, sections, texte
