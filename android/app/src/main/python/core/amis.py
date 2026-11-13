"""Système d'amis d'AllMyStats : chacun publie un petit « profil » (ses stats, rien d'autre) et le partage avec
un code ami. Les amis ajoutent ce code et voient ses stats, comparées dans un classement.

Il n'y a pas de serveur AllMyStats : les profils passent par ntfy.sh, un service gratuit et sans compte fait
pour que des programmes s'envoient des messages. Chaque profil est publié dans un « sujet » ntfy au nom tiré au
hasard (impossible à deviner) : ce nom est le code ami. ntfy garde les messages 12 heures, donc AMS republie
toutes les 6 heures quand le PC est allumé, et garde chez toi les dernières stats connues de chaque ami.

Ce qui part sur Internet : le pseudo choisi dans AMS et la dernière valeur des stats des jeux partagés,
compressées. Jamais de connexion, de cookie, de clé, d'UID, d'adresse ou d'historique.

Limites, dites à l'utilisateur dans l'appli : n'importe qui qui a ton code peut voir ces stats (c'est le but),
et pourrait techniquement publier dans ton sujet ; AMS republie de toute façon dès que tes stats changent."""

import base64
import hashlib
import json
import os
import re
import secrets
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import zlib
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

# Adresse du service. Peut être changée (tests, serveur ntfy perso) sans toucher au code.
RELAIS = os.environ.get("AMS_RELAIS_AMIS", "https://ntfy.sh").rstrip("/")
UA = "AllMyStats/2 (amis ; https://github.com/Angelotkkt/AllMyStats)"
PREFIXE = "AMS-"
SUJET = "allmystats-{id}"
ENTETE_MESSAGE = "AMS1:"
TAILLE_MAX = 3900               # ntfy refuse les messages de plus de 4096 octets
CLE_CONFIG = "_amis"
REPUBLIER_APRES = 6 * 3600      # ntfy oublie les messages au bout de 12 h
CACHE_AMIS = 120                # secondes avant de relire le profil d'un ami
MAX_AMIS = 50
# Photo de profil : une petite image (envoyée dans son propre message) ou l'adresse d'une photo de compte de jeu
PHOTO_MAX = 2800
HOTES_PHOTO = ("enka.network", "avatars.steamstatic.com", "avatars.akamai.steamstatic.com", "steamcdn-a.akamaihd.net",
               "media.valorant-api.com")
# Stats qui n'ont pas de sens à comparer (elles parlent des autres, pas de toi)
STATS_EXCLUES = {"amis_en_jeu", "joueurs_en_ligne"}
# Stats où moins, c'est mieux
MOINS_C_EST_MIEUX = {"morts", "defaites"}


class ErreurAmis(Exception):
    pass


# ------------------------------------------------------------------ le code ami

def code_depuis_id(id_profil):
    return PREFIXE + id_profil if id_profil else ""


def nouvel_id():
    return secrets.token_hex(12)


def id_depuis_code(code):
    """« AMS-abc123… » ou juste l'id -> l'id, ou None si ça ne ressemble à rien."""
    texte = (code or "").strip().rstrip("/").rsplit("/", 1)[-1]
    if texte.upper().startswith(PREFIXE):
        texte = texte[len(PREFIXE):]
    if texte.lower().startswith("allmystats-"):
        texte = texte[len("allmystats-"):]
    texte = texte.strip().lower()
    return texte if re.fullmatch(r"[a-z0-9]{16,40}", texte) else None


# ------------------------------------------------------------------ échanges avec ntfy

def _requete(methode, url, corps=None, timeout=15):
    req = urllib.request.Request(url, data=corps, method=methode, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read(400_000).decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        if e.code == 429:
            raise ErreurAmis("Le serveur des amis demande d'attendre un peu (trop de demandes) : réessaie dans quelques minutes.")
        return e.code, ""
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raison = getattr(e, "reason", e)
        if "CERTIFICATE" in str(raison).upper():
            raise ErreurAmis("Ton PC n'arrive pas à vérifier le certificat de sécurité du serveur des amis. Vérifie que "
                             "la date et l'heure de Windows sont justes, puis réessaie.")
        raise ErreurAmis(f"Impossible de joindre le serveur des amis ({raison}). Vérifie ta connexion.")


def emballer(compact):
    """Profil compact -> texte court (compressé) qui tient dans un message ntfy."""
    brut = json.dumps(compact, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return ENTETE_MESSAGE + base64.b64encode(zlib.compress(brut, 9)).decode("ascii")


def deballer(texte):
    if not isinstance(texte, str) or not texte.startswith(ENTETE_MESSAGE) or len(texte) > 6000:
        return None
    try:
        brut = zlib.decompressobj().decompress(base64.b64decode(texte[len(ENTETE_MESSAGE):], validate=True), 200_000)
        data = json.loads(brut.decode("utf-8"))
    except (ValueError, zlib.error, UnicodeDecodeError):
        return None
    return data if isinstance(data, dict) else None


def envoyer(id_profil, compact):
    texte = emballer(compact)
    if len(texte) > TAILLE_MAX:
        raise ErreurAmis("Trop de stats à partager d'un coup : décoche quelques jeux dans « Jeux partagés ».")
    code, _ = _requete("POST", f"{RELAIS}/{SUJET.format(id=id_profil)}", texte.encode("ascii"))
    if code not in (200, 201):
        raise ErreurAmis(f"Le serveur des amis a refusé la publication (erreur {code}).")


def photo_valide(v):
    """Une photo acceptable : petite image JPEG/PNG/WebP en base64, ou adresse https d'une photo de compte de jeu."""
    if not isinstance(v, str) or not v:
        return ""
    if re.fullmatch(r"data:image/(jpeg|png|webp);base64,[A-Za-z0-9+/]+={0,2}", v) and len(v) <= PHOTO_MAX:
        return v
    if len(v) < 400 and re.fullmatch(r"https://[\w.\-/%?=&~+]+", v):
        hote = urllib.parse.urlparse(v).hostname or ""
        if any(hote == h or hote.endswith("." + h) for h in HOTES_PHOTO):
            return v
    return ""


def _empreinte_photo(photo):
    return hashlib.sha256(photo.encode("utf-8")).hexdigest()[:12] if photo else ""


def recevoir(id_profil):
    """Le dernier profil publié dans le sujet de cet ami (dans les 12 dernières heures), ou None.
    Si sa photo est une image envoyée à part, elle est ajoutée au profil (champ « a »)."""
    code, texte = _requete("GET", f"{RELAIS}/{SUJET.format(id=id_profil)}/json?poll=1&since=all")
    if code != 200:
        raise ErreurAmis(f"Le serveur des amis a répondu une erreur {code}.")
    meilleur, photos = None, {}
    for ligne in texte.splitlines():
        try:
            m = json.loads(ligne)
        except ValueError:
            continue
        if not isinstance(m, dict) or m.get("event") != "message":
            continue
        data = deballer(m.get("message"))
        if not data:
            continue
        if data.get("type") == "photo":
            if isinstance(data.get("h"), str) and photo_valide(data.get("a")):
                photos[data["h"]] = data["a"]
        elif meilleur is None or (m.get("time") or 0) >= meilleur[0]:
            meilleur = (m.get("time") or 0, data)
    if not meilleur:
        return None
    profil = meilleur[1]
    if profil.get("ah") and not profil.get("a"):
        profil["a"] = photos.get(profil["ah"], "")
    return profil


# ------------------------------------------------------------------ le contenu d'un profil

def _texte(v, maxi):
    return str(v)[:maxi] if isinstance(v, (str, int, float)) and not isinstance(v, bool) else ""


def _couleur(v):
    return v if isinstance(v, str) and re.fullmatch(r"#[0-9a-fA-F]{6}", v) else "#8a8fa8"


def _nombre(v):
    if isinstance(v, bool) or not isinstance(v, (int, float)) or v != v or abs(v) > 1e15:
        return None
    return v


def construire_compact(reglages, jeux, derniere_valeur, est_cache):
    """Ce qui est publié : {p: pseudo, c: couleur, t: date, j: {jeu: {stat: valeur}}}. Les noms, unités et
    icônes ne voyagent pas : l'AMS de ton ami les connaît déjà."""
    partages = reglages.get("jeux_partages")   # None = tous
    j = {}
    for jeu in jeux.values():
        if not jeu.stats or est_cache(jeu) or (partages is not None and jeu.id not in partages):
            continue
        valeurs = {}
        for st in jeu.stats:
            if st.cle in STATS_EXCLUES:
                continue
            v = derniere_valeur(jeu.id, st.cle)
            if v is not None:
                v = round(float(v), 3)
                valeurs[st.cle] = int(v) if v == int(v) else v
        if valeurs:
            j[jeu.id] = valeurs
    compact = {"v": 1, "p": (reglages.get("pseudo") or "Joueur")[:24], "c": _couleur(reglages.get("couleur")),
               "t": datetime.now(timezone.utc).isoformat(timespec="seconds"), "j": j}
    photo = photo_valide(reglages.get("photo"))
    if photo.startswith("https://"):
        compact["a"] = photo                       # une adresse : elle tient dans le profil
    elif photo:
        compact["ah"] = _empreinte_photo(photo)    # une image : elle part dans son propre message
    return compact


def developper(compact, jeux):
    """Profil compact (le mien, ou celui d'un ami lu sur Internet) -> profil complet pour l'interface. On ne
    garde que ce qu'on attend, aux bons types : un profil venu d'ailleurs ne doit rien pouvoir glisser."""
    if not isinstance(compact, dict) or compact.get("v") != 1:
        return None
    liste = []
    brut_jeux = compact.get("j") if isinstance(compact.get("j"), dict) else {}
    for jeu in jeux.values():
        valeurs = brut_jeux.get(jeu.id)
        if not isinstance(valeurs, dict):
            continue
        stats = []
        for st in jeu.stats:
            v = _nombre(valeurs.get(st.cle))
            if v is None or st.cle in STATS_EXCLUES:
                continue
            stats.append({"cle": st.cle, "nom": st.nom, "unite": st.unite, "decimales": st.decimales,
                          "icone": st.icone, "groupe": st.groupe, "valeur": v})
        if stats:
            liste.append({"id": jeu.id, "nom": jeu.nom, "icone": jeu.icone or "", "couleur": jeu.couleur,
                          "famille": jeu.famille or "", "stats": stats})
    return {"pseudo": _texte(compact.get("p"), 24).strip() or "Joueur", "couleur": _couleur(compact.get("c")),
            "photo": photo_valide(compact.get("a")),
            "maj": _texte(compact.get("t"), 40), "jeux": liste, "ferme": compact.get("f") == 1}


def _empreinte(compact):
    sans_date = {k: v for k, v in compact.items() if k != "t"}
    return hashlib.sha256(json.dumps(sans_date, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


# ------------------------------------------------------------------ le gestionnaire (un par appli)

class Amis:
    def __init__(self, config, jeux, bdd, est_cache, version, dossier, mobile=False):
        self.config, self.jeux, self.bdd, self.est_cache = config, jeux, bdd, est_cache
        self.version, self.mobile = version, mobile
        self.fichier_cache = os.path.join(dossier, "amis_cache.json")
        self._verrou = threading.RLock()
        self._lus = {}            # id -> heure de la dernière lecture en ligne

    def reglages(self):
        # config.json ne garde que des textes : tout le système d'amis tient dans un seul champ JSON
        try:
            r = json.loads((self.config.reglages(CLE_CONFIG) or {}).get("donnees") or "{}")
        except ValueError:
            r = {}
        r = {"actif": False, "pseudo": "", "couleur": "#FFC44D", "id": "", "amis": [], "jeux_partages": None,
             **(r if isinstance(r, dict) else {})}
        r["amis"] = [a for a in r["amis"] if isinstance(a, dict) and id_depuis_code(a.get("id"))]
        if r.get("id") and not id_depuis_code(r["id"]):
            r["id"] = ""     # ancien format
        return r

    def _enregistrer(self, **valeurs):
        with self._verrou:
            r = self.reglages()
            r.update(valeurs)
            self.config.enregistrer(CLE_CONFIG, {"donnees": json.dumps(r, ensure_ascii=False)})
            return r

    # ----- les dernières stats connues de chaque ami, gardées sur le PC
    def _cache(self):
        try:
            with open(self.fichier_cache, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    def _garder(self, id_profil, compact):
        with self._verrou:
            data = self._cache()
            data[id_profil] = {"compact": compact, "lu_le": int(time.time())}
            gardes = {a["id"] for a in self.reglages()["amis"]} | {id_profil}
            data = {k: v for k, v in data.items() if k in gardes}
            try:
                with open(self.fichier_cache, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False)
            except OSError:
                pass

    def _compact(self):
        return construire_compact(self.reglages(), self.jeux, self.bdd.derniere_valeur, self.est_cache)

    def mon_profil(self):
        return {**developper(self._compact(), self.jeux), "photo": photo_valide(self.reglages().get("photo"))}

    def photos_de_jeux(self):
        """Les photos de compte connues (Genshin, Steam, Valorant…), pour s'en servir comme photo de profil."""
        res = []
        for j in self.jeux.values():
            try:
                details, _ = self.bdd.lire_details(j.id)
            except Exception:
                continue
            photo = photo_valide((details or {}).get("avatar") if isinstance(details, dict) else "")
            if photo.startswith("https://") and photo not in [r["photo"] for r in res]:
                res.append({"jeu": j.nom, "photo": photo})
        return res

    # ----- réglages

    def regler(self, actif=None, pseudo=None, couleur=None, jeux_partages=None, tous_les_jeux=False, photo=None):
        changes = {}
        if photo is not None:
            if photo and not photo_valide(photo):
                raise ErreurAmis("Cette photo ne convient pas (trop grande, ou d'un site inconnu). Choisis-en une autre.")
            changes["photo"] = photo_valide(photo)
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
        """Publie mon profil s'il a changé (ou s'il n'a pas été republié depuis 6 h). Renvoie un message."""
        if self.mobile:
            raise ErreurAmis("Ton profil est publié depuis ton PC.")
        with self._verrou:
            r = self.reglages()
            if not r["actif"]:
                return None
            compact = self._compact()
            empreinte = _empreinte(compact)
            if (not forcer and r.get("id") and r.get("empreinte") == empreinte
                    and time.time() - (r.get("publie_le") or 0) < REPUBLIER_APRES):
                return None
            id_profil = r.get("id") or nouvel_id()
            try:
                photo = photo_valide(r.get("photo"))
                if compact.get("ah"):   # d'abord la photo, pour qu'elle soit là quand le profil arrive
                    envoyer(id_profil, {"v": 1, "type": "photo", "h": compact["ah"], "a": photo})
                envoyer(id_profil, compact)
            except ErreurAmis as e:
                self._enregistrer(erreur=str(e))
                raise
            self._enregistrer(id=id_profil, empreinte=empreinte, publie_le=time.time(), erreur="")
            return "Profil publié"

    def publier_en_silence(self):
        try:
            self.publier()
        except ErreurAmis as e:
            print(f"[amis] {e}")

    def oublier_mon_profil(self):
        """Arrête de partager : un dernier message « fermé » remplace mes stats, et le code est oublié."""
        with self._verrou:
            r = self.reglages()
            if r.get("id") and not self.mobile:
                try:
                    envoyer(r["id"], {"v": 1, "p": r.get("pseudo") or "Joueur", "c": _couleur(r.get("couleur")),
                                      "t": datetime.now(timezone.utc).isoformat(timespec="seconds"), "j": {}, "f": 1})
                except ErreurAmis:
                    pass
            self._enregistrer(actif=False, id="", empreinte="", publie_le=0, erreur="")

    # ----- la liste d'amis

    def ajouter(self, code):
        id_profil = id_depuis_code(code)
        if not id_profil:
            raise ErreurAmis("Ce code ami n'a pas la bonne forme (il commence par AMS- et suit avec 24 lettres et chiffres).")
        r = self.reglages()
        if id_profil == r.get("id"):
            raise ErreurAmis("C'est ton propre code ami.")
        if any(a["id"] == id_profil for a in r["amis"]):
            raise ErreurAmis("Cet ami est déjà dans ta liste.")
        if len(r["amis"]) >= MAX_AMIS:
            raise ErreurAmis(f"{MAX_AMIS} amis maximum.")
        compact = recevoir(id_profil)
        profil = developper(compact, self.jeux) if compact else None
        if not profil:
            raise ErreurAmis("Aucun profil récent avec ce code : vérifie-le, ou demande à ton ami d'ouvrir AllMyStats "
                             "(son profil est republié quand son PC est allumé).")
        self._enregistrer(amis=r["amis"] + [{"id": id_profil, "pseudo": profil["pseudo"], "ajoute": int(time.time())}])
        self._garder(id_profil, compact)
        self._lus[id_profil] = time.time()
        return profil

    def retirer(self, id_profil):
        r = self.reglages()
        self._enregistrer(amis=[a for a in r["amis"] if a["id"] != id_profil])
        self._lus.pop(id_profil, None)
        with self._verrou:
            data = self._cache()
            if data.pop(id_profil, None) is not None:
                try:
                    with open(self.fichier_cache, "w", encoding="utf-8") as f:
                        json.dump(data, f, ensure_ascii=False)
                except OSError:
                    pass

    def _lire_ami(self, id_profil, forcer):
        """(profil complet ou None, erreur, lu_le). Si rien n'est en ligne (PC de l'ami éteint depuis plus de
        12 h), on montre les dernières stats connues."""
        erreur = ""
        if forcer or time.time() - self._lus.get(id_profil, 0) > CACHE_AMIS:
            try:
                compact = recevoir(id_profil)
                self._lus[id_profil] = time.time()
                if compact and developper(compact, self.jeux):
                    self._garder(id_profil, compact)
            except ErreurAmis as e:
                erreur = str(e)
        garde = self._cache().get(id_profil) or {}
        profil = developper(garde.get("compact"), self.jeux)
        if not profil:
            return None, erreur or "Pas encore de stats : ton ami doit ouvrir AllMyStats avec le partage activé.", 0
        return profil, erreur, garde.get("lu_le") or 0

    def tout(self, forcer=False):
        """Tout ce qu'il faut à la page Amis : mes réglages, mon profil, et le profil de chaque ami."""
        r = self.reglages()
        amis = r["amis"]
        with ThreadPoolExecutor(max_workers=6) as pool:
            lus = list(pool.map(lambda a: self._lire_ami(a["id"], forcer), amis))
        liste, pseudos_changes = [], False
        for a, (profil, erreur, lu_le) in zip(amis, lus):
            if not profil:
                liste.append({"id": a["id"], "code": code_depuis_id(a["id"]), "pseudo": a.get("pseudo") or "Ami",
                              "couleur": "#8a8fa8", "erreur": erreur, "jeux": []})
                continue
            if profil["pseudo"] != a.get("pseudo"):
                a["pseudo"] = profil["pseudo"]
                pseudos_changes = True
            liste.append({"id": a["id"], "code": code_depuis_id(a["id"]), **profil, "avertissement": erreur})
        if pseudos_changes:
            self._enregistrer(amis=amis)
        disponibles = [{"id": j.id, "nom": j.nom, "icone": j.icone or "", "famille": j.famille or ""}
                       for j in self.jeux.values() if j.stats and not self.est_cache(j)]
        return {
            "moi": {"actif": r["actif"], "pseudo": r["pseudo"], "couleur": r["couleur"], "code": code_depuis_id(r.get("id")),
                    "publie_le": r.get("publie_le") or 0, "erreur": r.get("erreur") or "",
                    "jeux_partages": r["jeux_partages"], "jeux_disponibles": disponibles, "mobile": self.mobile,
                    "photo": photo_valide(r.get("photo")), "photos_jeux": self.photos_de_jeux()},
            "mon_profil": self.mon_profil(),
            "amis": liste,
            "moins_c_est_mieux": sorted(MOINS_C_EST_MIEUX),
        }
