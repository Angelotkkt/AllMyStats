"""Système d'amis d'AllMyStats : chacun publie un petit « profil » (ses stats, rien d'autre) et le partage avec
un code ami. Les amis ajoutent ce code et voient ses stats, comparées dans un classement.

Il n'y a pas de serveur AllMyStats : les profils sont rangés sur jsonblob.com, un service gratuit de stockage
de JSON, sans compte. Chaque profil est un petit fichier JSON public ; son adresse (son « id ») est le code ami.
Ce qui part sur Internet : le pseudo choisi dans AMS, et la dernière valeur des stats affichées des jeux
partagés. Jamais de connexion, de cookie, de clé, d'UID, d'adresse ou d'historique.

Limites, dites à l'utilisateur dans l'appli :
  - n'importe qui qui a ton code peut voir ces stats (c'est le but) ;
  - jsonblob n'a pas de mot de passe : quelqu'un qui a ton code pourrait techniquement réécrire ton profil.
    AMS le republie de toute façon dès que tes stats changent, et au moins une fois par jour ;
  - un profil qui n'est lu par personne pendant 75 jours est effacé par jsonblob : AMS en recrée un (le code
    change alors, l'appli le dit)."""

import hashlib
import json
import os
import re
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

# Adresse du service de stockage. Peut être changée (tests, autre service compatible) sans toucher au code.
RELAIS = os.environ.get("AMS_RELAIS_AMIS", "https://jsonblob.com/api/jsonBlob").rstrip("/")
UA = "AllMyStats/2 (amis ; https://github.com/Angelotkkt/AllMyStats)"
PREFIXE = "AMS-"
CLE_CONFIG = "_amis"
REPUBLIER_APRES = 24 * 3600     # même sans changement, pour que le profil reste en vie chez jsonblob
CACHE_AMIS = 120                # secondes avant de relire le profil d'un ami
MAX_AMIS = 50
# Stats qui n'ont pas de sens à comparer (elles parlent des autres, pas de toi)
STATS_EXCLUES = {"amis_en_jeu", "joueurs_en_ligne"}
# Stats où moins, c'est mieux
MOINS_C_EST_MIEUX = {"morts", "defaites"}


class ErreurAmis(Exception):
    pass


# ------------------------------------------------------------------ le code ami

def code_depuis_id(id_blob):
    return PREFIXE + id_blob if id_blob else ""


def id_depuis_code(code):
    """« AMS-abc123… », une adresse jsonblob complète ou juste l'id -> l'id, ou None si ça ne ressemble à rien."""
    texte = (code or "").strip()
    texte = re.sub(r"^.*?/jsonBlob/", "", texte)
    if texte.upper().startswith(PREFIXE):
        texte = texte[len(PREFIXE):]
    texte = texte.strip().strip("/")
    return texte if re.fullmatch(r"[A-Za-z0-9-]{8,64}", texte) else None


# ------------------------------------------------------------------ échanges avec le stockage

def _requete(methode, url, corps=None, timeout=15):
    donnees = json.dumps(corps, ensure_ascii=False).encode("utf-8") if corps is not None else None
    req = urllib.request.Request(url, data=donnees, method=methode, headers={
        "User-Agent": UA, "Accept": "application/json", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            texte = r.read(200_000).decode("utf-8", errors="replace")
            return r.status, dict(r.headers), texte
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers or {}), ""
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise ErreurAmis(f"Impossible de joindre le serveur des amis ({getattr(e, 'reason', e)}). Vérifie ta connexion.")


def _creer(profil):
    code, entetes, _ = _requete("POST", RELAIS, profil)
    if code not in (200, 201):
        raise ErreurAmis(f"Le serveur des amis a refusé la création du profil (erreur {code}).")
    lieu = entetes.get("Location") or entetes.get("location") or ""
    id_blob = lieu.rstrip("/").rsplit("/", 1)[-1] if lieu else ""
    if not id_depuis_code(id_blob):
        raise ErreurAmis("Le serveur des amis n'a pas donné d'adresse pour le profil.")
    return id_blob


def _mettre_a_jour(id_blob, profil):
    """True si c'est fait, False si le profil n'existe plus (effacé)."""
    code, _, _ = _requete("PUT", f"{RELAIS}/{id_blob}", profil)
    if code == 404:
        return False
    if code not in (200, 201, 204):
        raise ErreurAmis(f"Le serveur des amis a refusé la mise à jour (erreur {code}).")
    return True


def lire_profil(id_blob):
    code, _, texte = _requete("GET", f"{RELAIS}/{id_blob}")
    if code == 404:
        raise ErreurAmis("Aucun profil avec ce code : vérifie-le, ou demande à ton ami de rouvrir AllMyStats (son code a peut-être changé).")
    if code != 200:
        raise ErreurAmis(f"Le serveur des amis a répondu une erreur {code}.")
    try:
        return nettoyer_profil(json.loads(texte))
    except ValueError:
        raise ErreurAmis("Ce code ne mène pas à un profil AllMyStats.")


# ------------------------------------------------------------------ le contenu d'un profil

def _texte(v, maxi):
    return str(v)[:maxi] if isinstance(v, (str, int, float)) and not isinstance(v, bool) else ""


def _couleur(v):
    return v if isinstance(v, str) and re.fullmatch(r"#[0-9a-fA-F]{6}", v) else "#8a8fa8"


def _nom_icone(v):
    return v if isinstance(v, str) and re.fullmatch(r"[a-z0-9_]{1,40}", v) else ""


def nettoyer_profil(brut):
    """Un profil lu sur Internet : on ne garde que ce qu'on attend, aux bons types et tailles (il vient d'un
    autre PC, il ne doit rien pouvoir glisser dans l'appli)."""
    if not isinstance(brut, dict) or brut.get("ams") != 1:
        raise ErreurAmis("Ce code ne mène pas à un profil AllMyStats.")
    jeux = []
    for j in (brut.get("jeux") or [])[:40]:
        if not isinstance(j, dict) or not _nom_icone(j.get("id")):
            continue
        stats = []
        for s in (j.get("stats") or [])[:40]:
            if not isinstance(s, dict) or not _nom_icone(s.get("cle")):
                continue
            v = s.get("valeur")
            if isinstance(v, bool) or not isinstance(v, (int, float)) or v != v or abs(v) > 1e15:
                continue
            stats.append({"cle": s["cle"], "nom": _texte(s.get("nom"), 60) or s["cle"], "unite": _texte(s.get("unite"), 6),
                          "decimales": max(0, min(3, int(s.get("decimales") or 0))) if isinstance(s.get("decimales"), int) else 0,
                          "icone": _nom_icone(s.get("icone")), "groupe": _texte(s.get("groupe"), 40), "valeur": v})
        if stats:
            jeux.append({"id": j["id"], "nom": _texte(j.get("nom"), 40) or j["id"], "icone": _nom_icone(j.get("icone")),
                         "couleur": _couleur(j.get("couleur")), "famille": _texte(j.get("famille"), 40), "stats": stats})
    return {"ams": 1, "pseudo": _texte(brut.get("pseudo"), 24).strip() or "Joueur", "couleur": _couleur(brut.get("couleur")),
            "maj": _texte(brut.get("maj"), 40), "version": _texte(brut.get("version"), 16), "jeux": jeux,
            "ferme": brut.get("ferme") is True}


def construire_profil(reglages, jeux, derniere_valeur, est_cache, version):
    """Mon profil à publier : seulement la dernière valeur des stats des jeux partagés."""
    partages = reglages.get("jeux_partages")   # None = tous
    liste = []
    for j in jeux.values():
        if not j.stats or est_cache(j) or (partages is not None and j.id not in partages):
            continue
        stats = []
        for s in j.stats:
            if s.cle in STATS_EXCLUES:
                continue
            v = derniere_valeur(j.id, s.cle)
            if v is None:
                continue
            stats.append({"cle": s.cle, "nom": s.nom, "unite": s.unite, "decimales": s.decimales, "icone": s.icone,
                          "groupe": s.groupe, "valeur": round(float(v), 4)})
        if stats:
            liste.append({"id": j.id, "nom": j.nom, "icone": j.icone or "", "couleur": j.couleur, "famille": j.famille or "",
                          "stats": stats})
    return {"ams": 1, "pseudo": (reglages.get("pseudo") or "Joueur")[:24], "couleur": _couleur(reglages.get("couleur")),
            "maj": datetime.now(timezone.utc).isoformat(timespec="seconds"), "version": version, "jeux": liste}


def _empreinte(profil):
    sans_date = {k: v for k, v in profil.items() if k != "maj"}
    return hashlib.sha256(json.dumps(sans_date, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


# ------------------------------------------------------------------ le gestionnaire (un par appli)

class Amis:
    def __init__(self, config, jeux, bdd, est_cache, version, mobile=False):
        self.config, self.jeux, self.bdd, self.est_cache = config, jeux, bdd, est_cache
        self.version, self.mobile = version, mobile
        self._verrou = threading.RLock()
        self._cache = {}          # id -> (heure, profil ou erreur)

    def reglages(self):
        # config.json ne garde que des textes : tout le système d'amis tient dans un seul champ JSON
        try:
            r = json.loads((self.config.reglages(CLE_CONFIG) or {}).get("donnees") or "{}")
        except ValueError:
            r = {}
        r = {"actif": False, "pseudo": "", "couleur": "#FFC44D", "id": "", "amis": [], "jeux_partages": None,
             **(r if isinstance(r, dict) else {})}
        r["amis"] = [a for a in r["amis"] if isinstance(a, dict) and id_depuis_code(a.get("id"))]
        return r

    def _enregistrer(self, **valeurs):
        with self._verrou:
            r = self.reglages()
            r.update(valeurs)
            self.config.enregistrer(CLE_CONFIG, {"donnees": json.dumps(r, ensure_ascii=False)})
            return r

    def mon_profil(self):
        return construire_profil(self.reglages(), self.jeux, self.bdd.derniere_valeur, self.est_cache, self.version)

    # ----- réglages

    def regler(self, actif=None, pseudo=None, couleur=None, jeux_partages=None, tous_les_jeux=False):
        changes = {}
        if pseudo is not None:
            pseudo = re.sub(r"\s+", " ", str(pseudo)).strip()[:24]
            if not pseudo:
                raise ErreurAmis("Choisis un pseudo (24 caractères maximum).")
            changes["pseudo"] = pseudo
        if couleur is not None:
            changes["couleur"] = _couleur(couleur)
        if tous_les_jeux:
            changes["jeux_partages"] = None
        elif jeux_partages is not None:
            changes["jeux_partages"] = [j for j in jeux_partages if j in self.jeux]
        if actif is not None:
            if actif and not (changes.get("pseudo") or self.reglages().get("pseudo")):
                raise ErreurAmis("Choisis d'abord un pseudo : c'est le nom que tes amis verront.")
            changes["actif"] = bool(actif)
        self._enregistrer(**changes)
        if self.reglages()["actif"] and not self.mobile:
            return self.publier(forcer=True)
        return None

    # ----- publication

    def publier(self, forcer=False):
        """Publie mon profil s'il a changé (ou s'il n'a pas été publié depuis un jour). Renvoie un message."""
        if self.mobile:
            raise ErreurAmis("Ton profil est publié depuis ton PC.")
        with self._verrou:
            r = self.reglages()
            if not r["actif"]:
                return None
            profil = self.mon_profil()
            empreinte = _empreinte(profil)
            if (not forcer and r.get("id") and r.get("empreinte") == empreinte
                    and time.time() - (r.get("publie_le") or 0) < REPUBLIER_APRES):
                return None
            message = None
            try:
                id_blob = r.get("id")
                if id_blob and not _mettre_a_jour(id_blob, profil):
                    id_blob = None
                    message = "Ton ancien profil avait été effacé : ton code ami a changé, renvoie-le à tes amis."
                if not id_blob:
                    id_blob = _creer(profil)
            except ErreurAmis as e:
                self._enregistrer(erreur=str(e))
                raise
            self._enregistrer(id=id_blob, empreinte=empreinte, publie_le=time.time(), erreur="")
            return message or "Profil publié"

    def publier_en_silence(self):
        try:
            self.publier()
        except ErreurAmis as e:
            print(f"[amis] {e}")

    def oublier_mon_profil(self):
        """Arrête de partager : le profil en ligne est vidé (et le code oublié)."""
        with self._verrou:
            r = self.reglages()
            if r.get("id") and not self.mobile:
                try:
                    _mettre_a_jour(r["id"], {"ams": 1, "pseudo": r.get("pseudo") or "Joueur", "jeux": [], "ferme": True})
                except ErreurAmis:
                    pass
            self._enregistrer(actif=False, id="", empreinte="", publie_le=0)

    # ----- la liste d'amis

    def ajouter(self, code):
        id_blob = id_depuis_code(code)
        if not id_blob:
            raise ErreurAmis("Ce code ami n'a pas la bonne forme (il commence par AMS-).")
        r = self.reglages()
        if id_blob == r.get("id"):
            raise ErreurAmis("C'est ton propre code ami.")
        if any(a["id"] == id_blob for a in r["amis"]):
            raise ErreurAmis("Cet ami est déjà dans ta liste.")
        if len(r["amis"]) >= MAX_AMIS:
            raise ErreurAmis(f"{MAX_AMIS} amis maximum.")
        profil = lire_profil(id_blob)
        self._cache[id_blob] = (time.time(), profil)
        self._enregistrer(amis=r["amis"] + [{"id": id_blob, "pseudo": profil["pseudo"], "ajoute": int(time.time())}])
        return profil

    def retirer(self, id_blob):
        r = self.reglages()
        self._enregistrer(amis=[a for a in r["amis"] if a["id"] != id_blob])
        self._cache.pop(id_blob, None)

    def _lire_ami(self, id_blob, forcer):
        heure, valeur = self._cache.get(id_blob, (0, None))
        if not forcer and valeur is not None and time.time() - heure < CACHE_AMIS:
            return valeur
        try:
            valeur = lire_profil(id_blob)
        except ErreurAmis as e:
            valeur = {"erreur": str(e)}
        self._cache[id_blob] = (time.time(), valeur)
        return valeur

    def tout(self, forcer=False):
        """Tout ce qu'il faut à la page Amis : mes réglages, mon profil, et le profil de chaque ami."""
        r = self.reglages()
        amis = r["amis"]
        with ThreadPoolExecutor(max_workers=8) as pool:
            profils = list(pool.map(lambda a: self._lire_ami(a["id"], forcer), amis))
        liste, pseudos_changes = [], False
        for a, p in zip(amis, profils):
            if "erreur" in p:
                liste.append({"id": a["id"], "code": code_depuis_id(a["id"]), "pseudo": a.get("pseudo") or "Ami",
                              "erreur": p["erreur"]})
            else:
                if p["pseudo"] != a.get("pseudo"):
                    a["pseudo"] = p["pseudo"]
                    pseudos_changes = True
                liste.append({"id": a["id"], "code": code_depuis_id(a["id"]), **p})
        if pseudos_changes:
            self._enregistrer(amis=amis)
        disponibles = [{"id": j.id, "nom": j.nom, "icone": j.icone or "", "famille": j.famille or ""}
                       for j in self.jeux.values() if j.stats and not self.est_cache(j)]
        return {
            "moi": {"actif": r["actif"], "pseudo": r["pseudo"], "couleur": r["couleur"], "code": code_depuis_id(r.get("id")),
                    "publie_le": r.get("publie_le") or 0, "erreur": r.get("erreur") or "",
                    "jeux_partages": r["jeux_partages"], "jeux_disponibles": disponibles, "mobile": self.mobile},
            "mon_profil": self.mon_profil(),
            "amis": liste,
            "moins_c_est_mieux": sorted(MOINS_C_EST_MIEUX),
        }
