"""Système d'amis d'AllMyStats : demandes d'amis à accepter, amitié des deux côtés, classement entre amis.

Il n'y a pas de serveur AllMyStats : tout passe par ntfy.sh, un service gratuit et sans compte fait pour que des
programmes s'envoient des messages. Chaque joueur a deux « sujets » ntfy :
  - allmystats-<code>        : sa clé publique, et son profil (ses stats) CHIFFRÉ ;
  - allmystats-<code>-boite  : sa boîte de réception (demandes, réponses), chaque message chiffré pour lui.

Demande : A envoie à B (dans la boîte de B) sa clé de profil, chiffrée pour B seul. Si B accepte, B garde A dans
ses amis et lui renvoie sa propre clé de profil : chacun peut alors lire les stats de l'autre, et personne
d'autre (le code ami seul ne suffit plus). Retirer un ami prévient l'autre côté et change la clé de profil.
Le chiffrement est décrit dans core/amis_crypto.py ; le code ami est l'empreinte de la clé publique.

ntfy garde les messages 12 heures : AMS republie le profil toutes les 6 heures quand le PC est allumé, renvoie
les demandes et réponses pendant 7 jours, et garde chez toi les dernières stats connues de chaque ami.
Ce qui part sur Internet : ton pseudo, ta couleur, ta photo et la dernière valeur des stats partagées, chiffrés.
Jamais de connexion, de cookie, de clé d'API, d'UID ou d'historique."""

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

from core import amis_crypto as crypto

RELAIS = os.environ.get("AMS_RELAIS_AMIS", "https://ntfy.sh").rstrip("/")
UA = "AllMyStats/2 (amis ; https://github.com/Angelotkkt/AllMyStats)"
PREFIXE = "AMS-"
SUJET = "allmystats-{id}"
BOITE = "allmystats-{id}-boite"
TAILLE_MAX = 3900               # ntfy refuse les messages de plus de 4096 octets
CLE_CONFIG = "_amis"
REPUBLIER_APRES = 6 * 3600      # ntfy oublie les messages au bout de 12 h
RELANCES_PENDANT = 7 * 86400    # demandes et réponses renvoyées pendant 7 jours
LIRE_BOITE_APRES = 60
BLOQUE_APRES_REFUS = 24 * 3600  # après un refus, la même personne peut redemander le lendemain
CACHE_AMIS = 120
MAX_AMIS = 50
PHOTO_MAX = 2800
HOTES_PHOTO = ("enka.network", "avatars.steamstatic.com", "avatars.akamai.steamstatic.com", "steamcdn-a.akamaihd.net",
               "media.valorant-api.com")
STATS_EXCLUES = {"amis_en_jeu", "joueurs_en_ligne"}
MOINS_C_EST_MIEUX = {"morts", "defaites"}


class ErreurAmis(Exception):
    pass


# ------------------------------------------------------------------ le code ami

def code_depuis_id(id_profil):
    return PREFIXE + id_profil if id_profil else ""


def id_depuis_code(code):
    """« AMS-abc123… » ou juste l'id -> l'id, ou None si ça ne ressemble à rien."""
    texte = (code or "").strip().rstrip("/").rsplit("/", 1)[-1]
    if texte.upper().startswith(PREFIXE):
        texte = texte[len(PREFIXE):]
    texte = texte.strip().lower()
    return texte if re.fullmatch(r"[0-9a-f]{24}", texte) else None


# ------------------------------------------------------------------ échanges avec ntfy

def _requete(methode, url, corps=None, timeout=15):
    req = urllib.request.Request(url, data=corps, method=methode, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read(600_000).decode("utf-8", errors="replace")
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


def _poster(sujet, texte):
    if len(texte) > TAILLE_MAX:
        raise ErreurAmis("Trop de stats à partager d'un coup : décoche quelques jeux dans « Jeux partagés ».")
    code, _ = _requete("POST", f"{RELAIS}/{sujet}", texte.encode("ascii"))
    if code not in (200, 201):
        raise ErreurAmis(f"Le serveur des amis a refusé l'envoi (erreur {code}).")


def _lire_sujet(sujet):
    """Les messages gardés par ntfy (12 dernières heures) : [(id, heure, texte)], du plus ancien au plus récent."""
    code, texte = _requete("GET", f"{RELAIS}/{sujet}/json?poll=1&since=all")
    if code != 200:
        raise ErreurAmis(f"Le serveur des amis a répondu une erreur {code}.")
    res = []
    for ligne in texte.splitlines():
        try:
            m = json.loads(ligne)
        except ValueError:
            continue
        if isinstance(m, dict) and m.get("event") == "message" and isinstance(m.get("message"), str):
            res.append((str(m.get("id") or ""), m.get("time") or 0, m["message"]))
    res.sort(key=lambda x: x[1])
    return res


def _b64(octets):
    return base64.b64encode(octets).decode("ascii")


def _de_b64(texte):
    try:
        return base64.b64decode(texte, validate=True)
    except (ValueError, TypeError):
        return None


def _sceller(cle, objet):
    """Objet -> texte chiffré (compressé avant)."""
    return _b64(crypto.chiffrer(cle, zlib.compress(json.dumps(objet, separators=(",", ":"), ensure_ascii=False).encode("utf-8"), 9)))


def _ouvrir(cle, texte):
    paquet = _de_b64(texte)
    donnees = crypto.dechiffrer(cle, paquet) if paquet else None
    if donnees is None:
        return None
    try:
        objet = json.loads(zlib.decompressobj().decompress(donnees, 300_000).decode("utf-8"))
    except (ValueError, zlib.error, UnicodeDecodeError):
        return None
    return objet if isinstance(objet, dict) else None


def lire_cle_publique(id_profil):
    """La clé publique annoncée par ce code (vérifiée : son empreinte doit être le code)."""
    for _, _, texte in reversed(_lire_sujet(SUJET.format(id=id_profil))):
        if texte.startswith("AMS2K:"):
            y = crypto.depuis_hex(texte[6:])
            if y and crypto.empreinte(y) == id_profil:
                return y
    return None


def lire_profil(id_profil, cle):
    """Le dernier profil chiffré de cet ami que sa clé ouvre (avec sa photo), ou None."""
    profil, photos = None, {}
    for _, _, texte in _lire_sujet(SUJET.format(id=id_profil)):
        if texte.startswith("AMS2P:"):
            p = _ouvrir(cle, texte[6:])
            if p and p.get("v") == 1:
                profil = p
        elif texte.startswith("AMS2F:"):
            f = _ouvrir(cle, texte[6:])
            if f and isinstance(f.get("h"), str) and photo_valide(f.get("a")):
                photos[f["h"]] = f["a"]
    if profil and profil.get("ah") and not profil.get("a"):
        profil["a"] = photos.get(profil["ah"], "")
    return profil


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
        self._lus = {}
        self._boite_lue = 0

    # ----- réglages (config.json ne garde que des textes : tout tient dans un seul champ JSON)

    def reglages(self):
        try:
            r = json.loads((self.config.reglages(CLE_CONFIG) or {}).get("donnees") or "{}")
        except ValueError:
            r = {}
        r = r if isinstance(r, dict) else {}
        if r.get("version") != 2:   # ancien système (codes publics) : on garde le profil, pas les amis
            r = {k: v for k, v in r.items() if k in ("actif", "pseudo", "couleur", "photo", "jeux_partages")}
            r["version"] = 2
        base = {"version": 2, "actif": False, "pseudo": "", "couleur": "#FFC44D", "photo": "", "jeux_partages": None,
                "id": "", "prive": "", "k": "", "amis": [], "envoyees": [], "recues": [], "refuses": {},
                "vus": [], "notifs": []}
        r = {**base, **r}
        for liste in ("amis", "envoyees", "recues"):
            r[liste] = [a for a in r[liste] if isinstance(a, dict) and id_depuis_code(a.get("id"))]
        return r

    def _enregistrer(self, **valeurs):
        with self._verrou:
            r = self.reglages()
            r.update(valeurs)
            self.config.enregistrer(CLE_CONFIG, {"donnees": json.dumps(r, ensure_ascii=False)})
            return r

    def _identite(self):
        """(clé privée, clé publique, code, clé de profil). Créées la première fois."""
        with self._verrou:
            r = self.reglages()
            try:
                prive = int(r["prive"], 16) if r.get("prive") else None
            except ValueError:
                prive = None
            if not prive or not r.get("k"):
                prive, publique = crypto.nouvelle_paire()
                r = self._enregistrer(prive=format(prive, "x"), id=crypto.empreinte(publique),
                                      k=secrets.token_hex(32), publie_le=0, cle_annoncee_le=0)
            publique = pow(crypto.G, prive, crypto.P)
            return prive, publique, r["id"], bytes.fromhex(r["k"])

    # ----- les dernières stats connues de chaque ami, gardées sur le PC

    def _cache(self):
        try:
            with open(self.fichier_cache, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    def _ecrire_cache(self, data):
        try:
            with open(self.fichier_cache, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
        except OSError:
            pass

    def _garder(self, id_profil, compact):
        with self._verrou:
            data = self._cache()
            data[id_profil] = {"compact": compact, "lu_le": int(time.time())}
            gardes = {a["id"] for a in self.reglages()["amis"]} | {id_profil}
            self._ecrire_cache({k: v for k, v in data.items() if k in gardes})

    def _oublier_cache(self, id_profil):
        with self._verrou:
            data = self._cache()
            if data.pop(id_profil, None) is not None:
                self._ecrire_cache(data)

    # ----- mon profil

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
            if photo.startswith("https://") and photo not in [x["photo"] for x in res]:
                res.append({"jeu": j.nom, "photo": photo})
        return res

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
            self._identite()
            message = self.publier(forcer=True)
            if changes.get("pseudo") or "couleur" in changes or "photo" in changes:
                self._relancer_amis()   # le nouveau pseudo arrive aussi dans les demandes en cours
            return message
        return None

    def publier(self, forcer=False):
        """Publie ma clé publique et mon profil chiffré s'il a changé (ou toutes les 6 h). Renvoie un message."""
        if self.mobile:
            raise ErreurAmis("Ton profil est publié depuis ton PC.")
        with self._verrou:
            r = self.reglages()
            if not r["actif"]:
                return None
            _, publique, id_moi, cle = self._identite()
            r = self.reglages()
            compact = self._compact()
            empreinte = _empreinte({**compact, "_k": r["k"]})
            vieux = time.time() - (r.get("publie_le") or 0) >= REPUBLIER_APRES
            if not forcer and r.get("empreinte") == empreinte and not vieux:
                return None
            sujet = SUJET.format(id=id_moi)
            try:
                if forcer or vieux or time.time() - (r.get("cle_annoncee_le") or 0) >= REPUBLIER_APRES:
                    _poster(sujet, "AMS2K:" + crypto.en_hex(publique))
                    r = self._enregistrer(cle_annoncee_le=time.time())
                photo = photo_valide(r.get("photo"))
                if compact.get("ah"):
                    _poster(sujet, "AMS2F:" + _sceller(cle, {"h": compact["ah"], "a": photo}))
                _poster(sujet, "AMS2P:" + _sceller(cle, compact))
            except ErreurAmis as e:
                self._enregistrer(erreur=str(e))
                raise
            self._enregistrer(empreinte=empreinte, publie_le=time.time(), erreur="")
            return "Profil publié"

    # ----- messages entre deux joueurs (dans la boîte de l'autre)

    def _ecrire_a(self, id_autre, publique_autre, type_, **contenu):
        prive, publique, id_moi, cle = self._identite()
        r = self.reglages()
        charge = {"t": type_, "pour": id_autre, "q": int(time.time()), "p": r["pseudo"] or "Joueur",
                  "c": _couleur(r["couleur"]), **contenu}
        photo = photo_valide(r.get("photo"))
        if photo.startswith("https://"):
            charge["a"] = photo
        enveloppe = {"de": id_moi, "pk": crypto.en_hex(publique),
                     "x": _sceller(crypto.cle_commune(prive, publique_autre), charge)}
        _poster(BOITE.format(id=id_autre), "AMS2B:" + _b64(json.dumps(enveloppe, separators=(",", ":")).encode("ascii")))

    def _notifier(self, texte):
        r = self.reglages()
        self._enregistrer(notifs=(r["notifs"] + [{"texte": texte, "le": int(time.time())}])[-10:])

    def lire_boite(self, forcer=False):
        """Lit ma boîte : demandes reçues, réponses, retraits. Rien sur le téléphone (c'est le PC qui gère)."""
        if self.mobile:
            return
        r = self.reglages()
        if not r["actif"] or not r.get("prive"):
            return
        if not forcer and time.time() - self._boite_lue < LIRE_BOITE_APRES:
            return
        with self._verrou:
            prive, _, id_moi, cle_moi = self._identite()
            messages = _lire_sujet(BOITE.format(id=id_moi))
            self._boite_lue = time.time()
            r = self.reglages()
            vus = list(r["vus"])
            for id_msg, _, texte in messages:
                if id_msg in vus or not texte.startswith("AMS2B:"):
                    continue
                vus.append(id_msg)
                try:
                    enveloppe = json.loads((_de_b64(texte[6:]) or b"").decode("ascii") or "{}")
                    publique = crypto.depuis_hex(enveloppe.get("pk"))
                    de = id_depuis_code(enveloppe.get("de"))
                    if not publique or not de or crypto.empreinte(publique) != de or de == id_moi:
                        continue
                    charge = _ouvrir(crypto.cle_commune(prive, publique), enveloppe.get("x") or "")
                except (ValueError, UnicodeDecodeError, AttributeError):
                    continue
                if not charge or charge.get("pour") != id_moi:
                    continue
                self._traiter(de, crypto.en_hex(publique), charge)
            self._enregistrer(vus=vus[-400:])

    def _traiter(self, de, pk, charge):
        r = self.reglages()
        t = charge.get("t")
        infos = {"pseudo": _texte(charge.get("p"), 24).strip() or "Joueur", "couleur": _couleur(charge.get("c")),
                 "photo": photo_valide(charge.get("a"))}
        k = charge.get("k") if isinstance(charge.get("k"), str) and re.fullmatch(r"[0-9a-f]{64}", charge["k"]) else None
        ami = next((a for a in r["amis"] if a["id"] == de), None)
        envoyee = next((a for a in r["envoyees"] if a["id"] == de), None)
        if t == "demande" and k:
            if ami:   # déjà amis (il a peut-être réinstallé) : on met sa clé à jour et on lui redonne la mienne
                ami.update(k=k, pk=pk, **infos)
                ami["relancer_jusqua"] = time.time() + RELANCES_PENDANT
                self._enregistrer(amis=r["amis"])
                self._repondre(de, pk, "accepte")
            elif envoyee:   # demandes croisées : on devient amis tout de suite
                self._devenir_amis(r, de, pk, k, infos, envoyee_aussi=True)
            elif time.time() - (r["refuses"].get(de) or 0) > BLOQUE_APRES_REFUS:
                recues = [a for a in r["recues"] if a["id"] != de] + [{"id": de, "pk": pk, "k": k, "le": int(time.time()), **infos}]
                self._enregistrer(recues=recues)
                if not any(a["id"] == de for a in r["recues"]):
                    self._notifier(f"{infos['pseudo']} veut être ton ami")
        elif t == "accepte" and k:
            if envoyee:
                self._devenir_amis(r, de, pk, k, infos, envoyee_aussi=True, notif=f"{infos['pseudo']} a accepté ta demande !")
            elif ami:
                ami.update(k=k, pk=pk, **infos)
                self._enregistrer(amis=r["amis"])
        elif t == "refuse" and envoyee:
            self._enregistrer(envoyees=[a for a in r["envoyees"] if a["id"] != de])
            self._notifier(f"{infos['pseudo']} a refusé ta demande")
        elif t == "annule":
            self._enregistrer(recues=[a for a in r["recues"] if a["id"] != de])
        elif t == "retire" and ami:
            self._enregistrer(amis=[a for a in r["amis"] if a["id"] != de])
            self._oublier_cache(de)
            self._notifier(f"{ami.get('pseudo') or infos['pseudo']} n'est plus dans tes amis")
            self._changer_cle()

    def _devenir_amis(self, r, de, pk, k, infos, envoyee_aussi=False, notif=None):
        amis = [a for a in r["amis"] if a["id"] != de] + [{"id": de, "pk": pk, "k": k, "depuis": int(time.time()),
                                                           "relancer_jusqua": time.time() + RELANCES_PENDANT, **infos}]
        self._enregistrer(amis=amis, envoyees=[a for a in r["envoyees"] if a["id"] != de],
                          recues=[a for a in r["recues"] if a["id"] != de])
        self._repondre(de, pk, "accepte")
        if notif:
            self._notifier(notif)

    def _repondre(self, de, pk, type_, **contenu):
        publique = crypto.depuis_hex(pk)
        if not publique:
            return
        if type_ in ("demande", "accepte"):
            contenu["k"] = self.reglages()["k"]
        try:
            self._ecrire_a(de, publique, type_, **contenu)
        except ErreurAmis as e:
            print(f"[amis] {e}")

    def _changer_cle(self):
        """Nouvelle clé de profil (après un retrait) : envoyée aux amis restants, puis profil republié."""
        self._enregistrer(k=secrets.token_hex(32))
        for a in self.reglages()["amis"]:
            a["relancer_jusqua"] = time.time() + RELANCES_PENDANT
            a["relance_le"] = time.time()
            self._repondre(a["id"], a["pk"], "accepte")
        r = self.reglages()
        self._enregistrer(amis=[{**a, "relancer_jusqua": time.time() + RELANCES_PENDANT, "relance_le": time.time()}
                                for a in r["amis"]])
        try:
            self.publier(forcer=True)
        except ErreurAmis as e:
            print(f"[amis] {e}")

    def _relancer_amis(self):
        r = self.reglages()
        for a in r["envoyees"]:
            self._repondre(a["id"], a["pk"], "demande")
        for a in r["amis"]:
            self._repondre(a["id"], a["pk"], "accepte")

    def relances(self):
        """ntfy oublie tout au bout de 12 h : on renvoie les demandes en attente et les réponses récentes
        toutes les 6 h, pendant 7 jours, au cas où l'autre PC était éteint."""
        if self.mobile or not self.reglages()["actif"]:
            return
        with self._verrou:
            r = self.reglages()
            maintenant = time.time()
            change = False
            for liste, type_ in (("envoyees", "demande"), ("amis", "accepte")):
                for a in r[liste]:
                    limite = a.get("jusqua") if liste == "envoyees" else a.get("relancer_jusqua")
                    if limite and maintenant < limite and maintenant - (a.get("relance_le") or 0) >= REPUBLIER_APRES:
                        self._repondre(a["id"], a["pk"], type_)
                        a["relance_le"] = maintenant
                        change = True
            if change:
                self._enregistrer(envoyees=r["envoyees"], amis=r["amis"])

    def entretien(self):
        """Ce que fait la boucle de fond : publier, lire la boîte, relancer."""
        for action in (self.publier, self.lire_boite, self.relances):
            try:
                action()
            except ErreurAmis as e:
                print(f"[amis] {e}")

    # ----- actions de l'interface

    def _verifier_pret(self):
        if self.mobile:
            raise ErreurAmis("Les demandes d'amis se gèrent depuis AllMyStats sur ton PC.")
        if not self.reglages()["actif"]:
            raise ErreurAmis("Active d'abord le partage (choisis un pseudo) : il faut un profil pour avoir des amis.")

    def demander(self, code):
        self._verifier_pret()
        id_autre = id_depuis_code(code)
        if not id_autre:
            raise ErreurAmis("Ce code ami n'a pas la bonne forme : AMS- suivi de 24 lettres et chiffres.")
        r = self.reglages()
        if id_autre == r.get("id"):
            raise ErreurAmis("C'est ton propre code ami.")
        if any(a["id"] == id_autre for a in r["amis"]):
            raise ErreurAmis("Vous êtes déjà amis.")
        recue = next((a for a in r["recues"] if a["id"] == id_autre), None)
        if recue:
            return self.accepter(id_autre)
        if any(a["id"] == id_autre for a in r["envoyees"]):
            raise ErreurAmis("Tu lui as déjà envoyé une demande : elle attend sa réponse.")
        if len(r["amis"]) + len(r["envoyees"]) >= MAX_AMIS:
            raise ErreurAmis(f"{MAX_AMIS} amis maximum.")
        publique = lire_cle_publique(id_autre)
        if not publique:
            raise ErreurAmis("Aucun profil récent avec ce code : vérifie-le, ou demande à ton ami d'ouvrir AllMyStats "
                             "avec le partage activé (son profil est republié quand son PC est allumé).")
        pk = crypto.en_hex(publique)
        self._repondre(id_autre, pk, "demande")
        envoyees = r["envoyees"] + [{"id": id_autre, "pk": pk, "le": int(time.time()), "relance_le": time.time(),
                                     "jusqua": time.time() + RELANCES_PENDANT}]
        self._enregistrer(envoyees=envoyees, refuses={k: v for k, v in r["refuses"].items() if k != id_autre})
        return "Demande envoyée : elle apparaîtra chez ton ami dans quelques minutes."

    def accepter(self, id_autre):
        self._verifier_pret()
        r = self.reglages()
        recue = next((a for a in r["recues"] if a["id"] == id_autre), None)
        if not recue:
            raise ErreurAmis("Cette demande n'existe plus.")
        infos = {k: recue.get(k) for k in ("pseudo", "couleur", "photo")}
        self._devenir_amis(r, id_autre, recue["pk"], recue["k"], infos)
        return f"{recue.get('pseudo') or 'Ton ami'} et toi êtes maintenant amis !"

    def refuser(self, id_autre):
        self._verifier_pret()
        r = self.reglages()
        recue = next((a for a in r["recues"] if a["id"] == id_autre), None)
        if recue:
            self._repondre(id_autre, recue["pk"], "refuse")
        self._enregistrer(recues=[a for a in r["recues"] if a["id"] != id_autre],
                          refuses={**r["refuses"], id_autre: int(time.time())})
        return "Demande refusée"

    def annuler(self, id_autre):
        self._verifier_pret()
        r = self.reglages()
        envoyee = next((a for a in r["envoyees"] if a["id"] == id_autre), None)
        if envoyee:
            self._repondre(id_autre, envoyee["pk"], "annule")
        self._enregistrer(envoyees=[a for a in r["envoyees"] if a["id"] != id_autre])
        return "Demande annulée"

    def retirer(self, id_autre):
        self._verifier_pret()
        r = self.reglages()
        ami = next((a for a in r["amis"] if a["id"] == id_autre), None)
        if ami:
            self._repondre(id_autre, ami["pk"], "retire")
        self._enregistrer(amis=[a for a in r["amis"] if a["id"] != id_autre])
        self._oublier_cache(id_autre)
        if ami:
            self._changer_cle()   # il avait ma clé de profil : on en change
        return "Vous n'êtes plus amis"

    def oublier_mon_profil(self):
        """Arrête de partager : prévient mes amis, efface mon identité (nouveau code si je reviens)."""
        with self._verrou:
            r = self.reglages()
            if not self.mobile:
                for a in r["amis"]:
                    self._repondre(a["id"], a["pk"], "retire")
                for a in r["envoyees"]:
                    self._repondre(a["id"], a["pk"], "annule")
            for a in r["amis"]:
                self._oublier_cache(a["id"])
            self._enregistrer(actif=False, id="", prive="", k="", amis=[], envoyees=[], recues=[], empreinte="",
                              publie_le=0, cle_annoncee_le=0, erreur="")

    # ----- lecture des amis

    def _lire_ami(self, ami, forcer):
        erreur = ""
        if forcer or time.time() - self._lus.get(ami["id"], 0) > CACHE_AMIS:
            try:
                compact = lire_profil(ami["id"], bytes.fromhex(ami["k"]))
                self._lus[ami["id"]] = time.time()
                if compact and developper(compact, self.jeux):
                    self._garder(ami["id"], compact)
            except (ErreurAmis, ValueError) as e:
                erreur = str(e)
        garde = self._cache().get(ami["id"]) or {}
        profil = developper(garde.get("compact"), self.jeux)
        if not profil:
            return None, erreur or "Pas encore de stats reçues : elles arrivent quand son AllMyStats est ouvert.", 0
        return profil, erreur, garde.get("lu_le") or 0

    def tout(self, forcer=False):
        """Tout ce qu'il faut à la page Amis."""
        erreur_boite = ""
        try:
            self.lire_boite(forcer=forcer)
        except ErreurAmis as e:
            erreur_boite = str(e)
        r = self.reglages()
        amis = r["amis"]
        with ThreadPoolExecutor(max_workers=6) as pool:
            lus = list(pool.map(lambda a: self._lire_ami(a, forcer), amis))
        liste = []
        for a, (profil, erreur, _) in zip(amis, lus):
            infos = {"id": a["id"], "code": code_depuis_id(a["id"])}
            if not profil:
                liste.append({**infos, "pseudo": a.get("pseudo") or "Ami", "couleur": a.get("couleur") or "#8a8fa8",
                              "photo": a.get("photo") or "", "erreur": erreur, "jeux": []})
            else:
                liste.append({**infos, **profil, "avertissement": erreur})
        notifs = r["notifs"]
        if notifs:
            self._enregistrer(notifs=[])
        disponibles = [{"id": j.id, "nom": j.nom, "icone": j.icone or "", "famille": j.famille or ""}
                       for j in self.jeux.values() if j.stats and not self.est_cache(j)]
        return {
            "moi": {"actif": r["actif"], "pseudo": r["pseudo"], "couleur": r["couleur"], "code": code_depuis_id(r.get("id")),
                    "publie_le": r.get("publie_le") or 0, "erreur": r.get("erreur") or erreur_boite,
                    "jeux_partages": r["jeux_partages"], "jeux_disponibles": disponibles, "mobile": self.mobile,
                    "photo": photo_valide(r.get("photo")), "photos_jeux": self.photos_de_jeux()},
            "mon_profil": self.mon_profil(),
            "amis": liste,
            "recues": [{"id": a["id"], "code": code_depuis_id(a["id"]), "pseudo": a.get("pseudo") or "Joueur",
                        "couleur": a.get("couleur"), "photo": a.get("photo") or "", "le": a.get("le")} for a in r["recues"]],
            "envoyees": [{"id": a["id"], "code": code_depuis_id(a["id"]), "le": a.get("le")} for a in r["envoyees"]],
            "notifs": [n["texte"] for n in notifs],
            "moins_c_est_mieux": sorted(MOINS_C_EST_MIEUX),
        }

    def nb_demandes(self):
        return len(self.reglages()["recues"])
