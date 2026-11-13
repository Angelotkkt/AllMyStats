"""Valorant — tout automatique, comme un tracker.

Riot ne donne pas d'API Valorant pour un usage perso. AllMyStats fait donc comme le site officiel et le jeu :
  1. « Se connecter avec Riot » ouvre la vraie page de connexion Riot dans une fenêtre. Ta connexion reste dans
     cette fenêtre (comme dans un navigateur) ; AllMyStats y redemande un jeton temporaire quand il en a besoin.
  2. Sans connexion, il se branche sur le client Riot ouvert sur ce PC.
Avec ce jeton, il lit sur les serveurs de Valorant : rang et RR, niveau du compte, historique et détails de tes
parties (K/D, ACS, dégâts, headshots, agents, cartes). Mot de passe et jetons ne sont jamais enregistrés.
Les parties sont gardées sur ce PC : les stats couvrent toutes tes parties depuis que AMS tourne (+ ~20 au début).
Option : une clé HenrikDev (Réglages avancés) pour le rang même sans connexion.
Lecture seule : AllMyStats ne modifie rien dans le jeu ni dans ton compte.
"""

import base64
import json
import os
import re
import ssl
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime

from core import chemins
from core import connexion_navigateur as navigateur

from .base import ErreurJeu, Jeu, Stat

LOCAL = os.environ.get("LOCALAPPDATA", "")
LOCKFILE = os.path.join(LOCAL, "Riot Games", "Riot Client", "Config", "lockfile")
JOURNAL_JEU = os.path.join(LOCAL, "VALORANT", "Saved", "Logs", "ShooterGame.log")
PLATEFORME = base64.b64encode(json.dumps({
    "platformType": "PC", "platformOS": "Windows", "platformOSVersion": "10.0.19042.1.256.64bit",
    "platformChipset": "Unknown"}).encode()).decode()
SHARDS = {"na": "na", "latam": "na", "br": "na", "pbe": "pbe", "eu": "eu", "ap": "ap", "kr": "kr"}
URL_CONTENU = "https://valorant-api.com/v1/"
URL_HENRIK = "https://api.henrikdev.xyz/valorant/"
# Connexion Riot dans une fenêtre (comme sur le site officiel) : après la connexion, Riot renvoie vers
# playvalorant.com avec un jeton temporaire dans l'adresse. On empêche playvalorant.com de se charger
# pour que l'adresse reste lisible ; AllMyStats ne garde jamais le jeton sur le disque.
URL_AUTH = ("https://auth.riotgames.com/authorize?redirect_uri=https%3A%2F%2Fplayvalorant.com%2Fopt_in"
            "&client_id=play-valorant-web-prod&response_type=token%20id_token&nonce=1&scope=account%20openid")
DOSSIER_CONNEXION = "connexion_riot"
ARGS_RIOT = ("--host-resolver-rules=MAP playvalorant.com ~NOTFOUND",)
_JETONS_WEB = {}   # en mémoire seulement (valables ~1 h)
UA = {"User-Agent": "AllMyStats/2.6 (stats perso)"}
SYNCHRO_TOUTES = 5 * 60          # en arrière-plan, quand le client Riot est ouvert
NOUVELLES_PAR_SYNCHRO = 10       # détails de parties téléchargés au plus à chaque fois
GARDER = 1000                    # parties gardées sur ce PC

RANGS = (["Non classé"] * 3 + [f"{n} {i}" for n in ("Fer", "Bronze", "Argent", "Or", "Platine", "Diamant",
                                                      "Ascendant", "Immortel") for i in (1, 2, 3)] + ["Radiant"])
FILES = {"competitive": "Compétition", "unrated": "Non classée", "swiftplay": "Vélocité", "spikerush": "Spike Rush",
         "deathmatch": "Combat à mort", "ggteam": "Escalade", "onefa": "Réplication", "hurm": "Match à mort en équipe",
         "premier": "Premier", "snowball": "Bataille de boules de neige", "newmap": "Nouvelle carte",
         "": "Partie personnalisée"}
SANS_EQUIPE = {"deathmatch"}

# Contexte TLS pour le client Riot LOCAL uniquement (127.0.0.1, certificat auto-signé par Riot)
_TLS_LOCAL = ssl.create_default_context()
_TLS_LOCAL.check_hostname = False
_TLS_LOCAL.verify_mode = ssl.CERT_NONE
try:
    _TLS_LOCAL.set_ciphers("DEFAULT:@SECLEVEL=0")   # le certificat local de Riot est ancien
except ssl.SSLError:
    pass
# Jamais de proxy pour parler au client Riot sur ce PC (un proxy Windows/VPN casserait la connexion locale)
_OUVREUR_LOCAL = urllib.request.build_opener(urllib.request.ProxyHandler({}),
                                             urllib.request.HTTPSHandler(context=_TLS_LOCAL))
_verrou = threading.Lock()


class ClientFerme(Exception):
    pass


class ConnexionExpiree(ErreurJeu):
    pass


class RefusServeur(ErreurJeu):
    """Les serveurs de Valorant ont refusé une demande (code HTTP + raison donnée par Riot)."""

    def __init__(self, code, detail=""):
        self.code, self.detail = code, detail
        super().__init__(f"Les serveurs de Valorant refusent la demande (erreur {code}{' : ' + detail if detail else ''})")


SHARDS_A_ESSAYER = ("eu", "na", "ap", "kr")


def nom_rang(tier):
    return RANGS[tier] if isinstance(tier, int) and 0 <= tier < len(RANGS) else "Non classé"


def points_rang(tier, rr):
    """Fer 1 = 0, chaque division = 100 points, Radiant = 2400 + RR. Pratique pour suivre sa progression."""
    if not isinstance(tier, int) or tier < 3:
        return None
    return (tier - 3) * 100 + (rr or 0)


# ---------------------------------------------------------------- fichiers

def _lire(chemin, defaut):
    try:
        with open(chemin, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return defaut


def _ecrire(chemin, data):
    tmp = chemin + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    os.replace(tmp, chemin)


def _fichier(dossier, nom):
    return os.path.join(dossier, nom)


# ---------------------------------------------------------------- client Riot local

def _lockfile():
    try:
        with open(LOCKFILE, "r", encoding="utf-8") as f:
            morceaux = f.read().strip().split(":")
        return morceaux[2], morceaux[3]          # port, mot de passe (changent à chaque lancement)
    except (OSError, IndexError):
        return None


def client_ouvert():
    return _lockfile() is not None


def _local(chemin, lf):
    port, mdp = lf
    auth = base64.b64encode(f"riot:{mdp}".encode()).decode()
    derniere = None
    for hote in ("127.0.0.1", "localhost"):
        req = urllib.request.Request(f"https://{hote}:{port}{chemin}", headers={"Authorization": "Basic " + auth})
        try:
            with _OUVREUR_LOCAL.open(req, timeout=8) as r:
                return json.loads(r.read().decode("utf-8") or "null")
        except urllib.error.HTTPError:
            raise                      # le client a répondu : inutile d'essayer l'autre adresse
        except (urllib.error.URLError, OSError) as e:
            derniere = e
    raise derniere


def _raison(e):
    raison = getattr(e, "reason", None) or e
    return f"{type(raison).__name__} : {str(raison)[:120]}"


def _journal():
    try:
        with open(JOURNAL_JEU, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()[-3_000_000:]
    except OSError:
        return ""


def _versions(journal):
    """Versions possibles du jeu (les serveurs refusent une version trop vieille)."""
    trouvees = []
    try:
        req = urllib.request.Request(URL_CONTENU + "version", headers=UA)
        with urllib.request.urlopen(req, timeout=10) as r:
            v = json.loads(r.read())["data"].get("riotClientVersion")
            if v:
                trouvees.append(v)
    except Exception:
        pass
    m = re.findall(r"CI server version:\s*(release-[\d.]+)-shipping-(\d+)-(\d+)", journal)
    if m:
        branche, build, num = m[-1]
        trouvees.append(f"{branche}-shipping-{build}-{num}")
    return trouvees or ["release-00.00-shipping-0-0"]


def ouvrir_session(region_reglee=""):
    """Se branche sur le client Riot ouvert. Renvoie de quoi interroger les serveurs de Valorant."""
    lf = _lockfile()
    if not lf:
        raise ClientFerme("Le client Riot n'est pas ouvert")
    try:
        jetons = _local("/entitlements/v1/token", lf)
    except urllib.error.HTTPError as e:
        # Le client est ouvert mais n'a pas encore de session (écran de connexion, ou connexion en cours)
        raise ClientFerme(f"Le client Riot est ouvert mais pas encore connecté à ton compte (réponse {e.code})")
    except ConnectionRefusedError:
        raise ClientFerme("Le client Riot semble fermé (il a laissé un ancien fichier de connexion)")
    except (urllib.error.URLError, OSError) as e:
        if isinstance(getattr(e, "reason", None), ConnectionRefusedError):
            raise ClientFerme("Le client Riot semble fermé (il a laissé un ancien fichier de connexion)")
        raise ClientFerme(f"Le client Riot ne répond pas ({_raison(e)})")
    except ValueError:
        raise ClientFerme("Le client Riot a répondu quelque chose d'illisible")
    if not jetons or not jetons.get("accessToken") or not jetons.get("token"):
        raise ClientFerme("Le client Riot est ouvert mais pas encore connecté à ton compte")
    journal = _journal()
    region = (region_reglee or "").strip().lower()
    versions = []
    try:   # VALORANT lancé : sa session donne la région (-ares-deployment=eu) et sa version exacte
        for sess in (_local("/product-session/v1/external-sessions", lf) or {}).values():
            if (sess.get("productId") or "").lower() != "valorant":
                continue
            if sess.get("version"):
                versions.append(sess["version"])
            for arg in (sess.get("launchConfiguration") or {}).get("arguments") or []:
                m = re.match(r"-ares-deployment=(\w+)", str(arg))
                if m and not region:
                    region = m.group(1).lower()
    except Exception:
        pass
    if not region:
        m = re.findall(r"https://glz-([a-z]+)-1\.([a-z]+)\.a\.pvp\.net", journal)
        if m:
            region = m[-1][1]
    if not region:
        try:
            infos = _local("/riotclient/region-locale", lf) or {}
            region = (infos.get("webRegion") or infos.get("region") or "").lower()
        except Exception:
            pass
    shard = SHARDS.get(region, "eu")
    nom = ""
    try:
        s = _local("/chat/v1/session", lf) or {}
        if s.get("game_name"):
            nom = f"{s['game_name']}#{s.get('game_tag', '')}"
    except Exception:
        pass
    return {"puuid": jetons["subject"], "acces": jetons["accessToken"], "droits": jetons["token"],
            "shard": shard, "region": region or shard, "nom": nom,
            "versions": list(dict.fromkeys(versions + _versions(journal))), "version": (versions + _versions(journal))[0]}


# ---------------------------------------------------------------- connexion Riot (fenêtre)

def _web(url, methode="GET", corps=None, jeton=None):
    entetes = {**UA, "Content-Type": "application/json"}
    if jeton:
        entetes["Authorization"] = "Bearer " + jeton
    req = urllib.request.Request(url, method=methode, headers=entetes,
                                 data=json.dumps(corps).encode() if corps is not None else None)
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode("utf-8") or "null")


def _contenu_jeton(jeton):
    """Ce qui est écrit dans un jeton Riot (JWT), lu sur place."""
    try:
        charge = (jeton or "").split(".")[1]
        return json.loads(base64.urlsafe_b64decode(charge + "=" * (-len(charge) % 4))) or {}
    except (IndexError, ValueError):
        return {}


def _sujet(jeton):
    """L'identifiant du joueur (puuid), lu dans le jeton (sans rien demander à personne)."""
    return _contenu_jeton(jeton).get("sub", "")


def session_depuis_adresse(adresse, region_reglee=""):
    """Transforme l'adresse de retour de Riot (…#access_token=…&id_token=…) en session pour les serveurs."""
    morceaux = urllib.parse.parse_qs(urllib.parse.urlparse(adresse).fragment)
    acces = (morceaux.get("access_token") or [""])[0]
    id_jeton = (morceaux.get("id_token") or [""])[0]
    if not acces:
        raise ErreurJeu("Riot n'a pas renvoyé de jeton de connexion.")
    try:   # facultatif : sert seulement à lire les serveurs de Valorant sans HenrikDev
        droits = (_web("https://entitlements.auth.riotgames.com/api/token/v1", "POST", {}, acces) or {}).get("entitlements_token", "")
    except Exception:
        droits = ""
    region = (region_reglee or "").strip().lower()
    if not region and id_jeton:
        try:
            geo = _web("https://riot-geo.pas.si.riotgames.com/pas/v1/product/valorant", "PUT", {"id_token": id_jeton}, acces)
            region = ((geo or {}).get("affinities") or {}).get("live", "")
        except Exception:
            pass
    # Ton Riot ID est écrit dans le jeton d'identité que Riot vient de renvoyer : rien à redemander
    acct = _contenu_jeton(id_jeton).get("acct") or {}
    nom = f"{acct['game_name']}#{acct.get('tag_line', '')}" if acct.get("game_name") else ""
    if not nom:
        try:
            info = (_web("https://auth.riotgames.com/userinfo", jeton=acces) or {}).get("acct") or {}
            if info.get("game_name"):
                nom = f"{info['game_name']}#{info.get('tag_line', '')}"
        except Exception:
            pass
    versions = _versions(_journal())
    return {"puuid": _sujet(acces), "acces": acces, "droits": droits, "shard": SHARDS.get(region, "eu"),
            "region": region or "eu", "nom": nom, "versions": versions, "version": versions[0], "web": True}


def session_web(dossier, region_reglee=""):
    """Session à partir de la connexion Riot gardée dans la fenêtre de connexion (sans rien afficher)."""
    if _JETONS_WEB.get("session") and time.time() - _JETONS_WEB["quand"] < 50 * 60:
        return dict(_JETONS_WEB["session"])
    profil = os.path.join(dossier, DOSSIER_CONNEXION)
    try:
        adresse, _ = navigateur.attendre_url(URL_AUTH, profil, "access_token=", delai_max=25, cache=True,
                                             arguments_en_plus=ARGS_RIOT)
    except navigateur.ErreurConnexion:
        adresse = ""
    if not adresse:
        raise ConnexionExpiree("Ta connexion Riot a expiré : clique sur « Reconnecter » (coche « Rester connecté »)")
    session = session_depuis_adresse(adresse, region_reglee)
    _JETONS_WEB.update(session=dict(session), quand=time.time())
    return session


def images_carte(carte):
    """La carte de joueur Valorant (son identifiant) -> photo de profil et bannière, comme dans le jeu.
    Images publiques de valorant-api.com."""
    if not isinstance(carte, str) or not re.fullmatch(r"[0-9a-fA-F-]{36}", carte):
        return {}
    base = f"https://media.valorant-api.com/playercards/{carte.lower()}/"
    return {"avatar": base + "smallart.png", "banniere": base + "wideart.png"}


def _pd(session, chemin, methode="GET", corps=None):
    req = urllib.request.Request(
        f"https://pd.{session['shard']}.a.pvp.net{chemin}", method=methode,
        data=json.dumps(corps).encode() if corps is not None else None,
        headers={"Authorization": "Bearer " + session["acces"], "X-Riot-Entitlements-JWT": session["droits"],
                 "X-Riot-ClientPlatform": PLATEFORME, "X-Riot-ClientVersion": session["version"],
                 "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read().decode("utf-8") or "null")
    except urllib.error.HTTPError as e:
        if e.code == 429:
            raise ErreurJeu("Les serveurs de Valorant demandent de patienter un peu (trop de demandes).")
        detail = ""
        try:
            corps_erreur = json.loads(e.read(2000).decode("utf-8", "ignore") or "{}")
            detail = corps_erreur.get("errorCode") or corps_erreur.get("message") or ""
        except Exception:
            pass
        raise RefusServeur(e.code, detail)
    except (urllib.error.URLError, OSError) as e:
        raise ErreurJeu(f"Pas de connexion aux serveurs de Valorant ({_raison(e)}).")


# ---------------------------------------------------------------- noms des agents et des cartes

def _noms(dossier):
    """Noms (en français) et images des agents, des cartes et des rangs, depuis valorant-api.com (gardés 7 jours).
    Les clés acceptent l'identifiant du jeu ET le nom anglais (c'est ce que donne HenrikDev)."""
    chemin = _fichier(dossier, "valo_noms.json")
    noms = _lire(chemin, {})
    if noms.get("v") == 2 and time.time() - noms.get("quand", 0) < 7 * 86400 and noms.get("agents"):
        return noms
    try:
        def charger(quoi):
            req = urllib.request.Request(URL_CONTENU + quoi, headers=UA)
            with urllib.request.urlopen(req, timeout=20) as r:
                return json.loads(r.read())["data"]
        nouv = {"v": 2, "quand": time.time(), "agents": {}, "img_agents": {}, "cartes": {}, "img_cartes": {}, "rangs": {}}
        anglais = {a["uuid"]: a["displayName"] for a in charger("agents?isPlayableCharacter=true")}
        for a in charger("agents?isPlayableCharacter=true&language=fr-FR"):
            for cle in {a["uuid"].lower(), (anglais.get(a["uuid"]) or "").lower(), a["displayName"].lower()} - {""}:
                nouv["agents"][cle] = a["displayName"]
                nouv["img_agents"][cle] = a.get("displayIcon") or a.get("displayIconSmall")
        anglais = {c["uuid"]: c["displayName"] for c in charger("maps")}
        for c in charger("maps?language=fr-FR"):
            image = c.get("listViewIconTall") or c.get("listViewIcon") or c.get("splash")
            for cle in {c["uuid"].lower(), (c.get("mapUrl") or ""), (anglais.get(c["uuid"]) or "").lower(),
                        c["displayName"].lower()} - {""}:
                nouv["cartes"][cle] = c["displayName"]
                nouv["img_cartes"][cle] = c.get("listViewIcon") or image
        episodes = charger("competitivetiers")
        for t in (episodes[-1].get("tiers") if episodes else []) or []:
            nouv["rangs"][str(t.get("tier"))] = t.get("largeIcon") or t.get("smallIcon")
        noms = nouv
        _ecrire(chemin, noms)
    except Exception:
        pass
    return noms


# ---------------------------------------------------------------- parties

def resumer_partie(d, puuid):
    """Résumé compact d'une partie (ce qu'on garde sur le PC)."""
    info = d.get("matchInfo") or {}
    if not info.get("isCompleted", True):
        return None
    moi = next((p for p in d.get("players") or [] if p.get("subject") == puuid), None)
    if not moi:
        return None
    st = moi.get("stats") or {}
    equipes = {t.get("teamId"): t for t in d.get("teams") or []}
    file = info.get("queueID") or info.get("queueId") or ""
    mon_equipe = equipes.get(moi.get("teamId"), {})
    autres = [t for i, t in equipes.items() if i != moi.get("teamId")]
    pour, contre = mon_equipe.get("roundsWon", 0), max((t.get("roundsWon", 0) for t in autres), default=0)
    if file in SANS_EQUIPE:
        resultat = "victoire" if mon_equipe.get("won") else "defaite"
        score = ""
    else:
        resultat = "victoire" if mon_equipe.get("won") else ("egalite" if pour == contre and pour else "defaite")
        score = f"{pour}-{contre}"
    degats = tete = corps = jambes = 0
    tours = d.get("roundResults") or []
    for tour in tours:
        for ps in tour.get("playerStats") or []:
            if ps.get("subject") == puuid:
                for dg in ps.get("damage") or []:
                    degats += dg.get("damage", 0)
                    tete += dg.get("headshots", 0)
                    corps += dg.get("bodyshots", 0)
                    jambes += dg.get("legshots", 0)
    return {
        "id": info.get("matchId", ""),
        "debut": (info.get("gameStartMillis") or 0) / 1000,
        "duree": (st.get("playtimeMillis") or info.get("gameLengthMillis") or 0) / 1000,
        "file": file, "carte": info.get("mapId", ""), "agent": (moi.get("characterId") or "").lower(),
        "k": st.get("kills", 0), "d": st.get("deaths", 0), "a": st.get("assists", 0),
        "score": st.get("score", 0), "tours": st.get("roundsPlayed") or len(tours),
        "resultat": resultat, "marque": score, "degats": degats, "tete": tete, "tirs": tete + corps + jambes,
        "rang": moi.get("competitiveTier"),
    }


# ---------------------------------------------------------------- HenrikDev (API utilisée par les trackers)

REGIONS_HENRIK = {"eu", "na", "ap", "kr", "latam", "br"}


def _detail_henrik(e):
    """Le message d'erreur que HenrikDev met dans sa réponse (il peut y en avoir plusieurs)."""
    try:
        corps = json.loads(e.read(4000).decode("utf-8", "ignore") or "{}")
    except (ValueError, OSError):
        return ""
    erreurs = corps.get("errors") or ([corps.get("error")] if corps.get("error") else [])
    textes = []
    for err in erreurs:
        if isinstance(err, dict):
            textes.append(f"{err.get('message') or err.get('details') or ''} (code {err.get('code', '?')})".strip())
        elif err:
            textes.append(str(err))
    return " · ".join(t for t in textes if t)[:200]


def _henrik(chemin, cle, etape=""):
    req = urllib.request.Request(URL_HENRIK + chemin, headers={**UA, "Authorization": cle, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            return json.loads(r.read().decode("utf-8") or "{}").get("data")
    except urllib.error.HTTPError as e:
        detail = _detail_henrik(e)
        if e.code == 400:
            raise ErreurJeu(f"HenrikDev refuse la demande ({etape or 'stats'}) : {detail or 'erreur 400'}")
        if e.code in (401, 403):
            raise ErreurJeu("Clé HenrikDev refusée : vérifie-la dans les Réglages de Valorant.")
        if e.code == 404:
            raise ErreurJeu("HenrikDev ne trouve pas ce compte : vérifie ton Riot ID (ex : Pseudo#EUW) dans les Réglages.")
        if e.code == 429:
            raise ErreurJeu("HenrikDev demande de patienter un peu (trop de demandes). Réessaie dans une minute.")
        raise ErreurJeu(f"HenrikDev a répondu une erreur {e.code}.")
    except (urllib.error.URLError, OSError, ValueError) as e:
        raise ErreurJeu(f"Pas de connexion à HenrikDev ({_raison(e)}).")


def _horodatage(iso):
    try:
        return datetime.fromisoformat(str(iso).replace("Z", "+00:00")).timestamp()
    except ValueError:
        return time.time()


def resumer_partie_henrik(m, puuid, riot_id):
    """Résumé compact d'une partie venant de HenrikDev (même format que resumer_partie)."""
    meta = m.get("metadata") or {}
    if meta.get("is_completed") is False:
        return None
    nom, _, tag = riot_id.partition("#")
    joueurs = m.get("players") or []
    moi = next((p for p in joueurs if puuid and p.get("puuid") == puuid), None) or next(
        (p for p in joueurs if (p.get("name") or "").lower() == nom.lower() and (p.get("tag") or "").lower() == tag.lower()),
        None)
    if not moi:
        return None
    st = moi.get("stats") or {}
    equipes = {t.get("team_id"): t for t in m.get("teams") or []}
    queue = meta.get("queue") or {}
    file = (queue.get("id") or "").lower()
    mon_equipe = equipes.get(moi.get("team_id"), {})
    manches = mon_equipe.get("rounds") or {}
    pour, contre = manches.get("won", 0) or 0, manches.get("lost", 0) or 0
    if file in SANS_EQUIPE or not equipes:
        resultat, marque = ("victoire" if mon_equipe.get("won") else "defaite"), ""
    else:
        resultat = "victoire" if mon_equipe.get("won") else ("egalite" if pour == contre and pour else "defaite")
        marque = f"{pour}-{contre}"
    tete, corps, jambes = st.get("headshots", 0) or 0, st.get("bodyshots", 0) or 0, st.get("legshots", 0) or 0
    return {
        "id": meta.get("match_id", ""), "debut": _horodatage(meta.get("started_at")),
        "duree": (meta.get("game_length_in_ms") or 0) / 1000,
        "file": file, "file_nom": queue.get("name") or "",
        "carte": ((meta.get("map") or {}).get("id") or (meta.get("map") or {}).get("name") or "").lower(),
        "agent": ((moi.get("agent") or {}).get("id") or (moi.get("agent") or {}).get("name") or "").lower(),
        "k": st.get("kills", 0) or 0, "d": st.get("deaths", 0) or 0, "a": st.get("assists", 0) or 0,
        "score": st.get("score", 0) or 0, "tours": (pour + contre) or 1,
        "resultat": resultat, "marque": marque, "degats": (st.get("damage") or {}).get("dealt", 0) or 0,
        "tete": tete, "tirs": tete + corps + jambes, "rang": None,
    }


def lire_mmr_henrik(data):
    data = data or {}
    actuel = data.get("current") or {}
    saisons = data.get("seasonal") or []
    acte = saisons[-1] if saisons else {}
    pic = ((data.get("peak") or {}).get("tier") or {}).get("id")
    return {"tier": (actuel.get("tier") or {}).get("id"), "rr": actuel.get("rr"), "meilleur": pic or None,
            "victoires_acte": acte.get("wins"), "parties_acte": acte.get("games"), "classement": None}


def calculer(parties):
    """Stats globales sur les parties gardées."""
    if not parties:
        return {}
    k = sum(p["k"] for p in parties)
    d = sum(p["d"] for p in parties)
    tours = sum(p["tours"] for p in parties) or 1
    avec_equipe = [p for p in parties if p["file"] not in SANS_EQUIPE]
    tirs = sum(p["tirs"] for p in parties)
    v = {
        "parties_suivies": len(parties),
        "eliminations": k,
        "kd": round(k / d, 2) if d else float(k),
        "acs": round(sum(p["score"] for p in parties) / tours),
        "adr": round(sum(p["degats"] for p in parties) / tours),
        "temps_suivi": round(sum(p["duree"] for p in parties) / 3600, 1),
    }
    if tirs:
        v["hs"] = round(sum(p["tete"] for p in parties) * 100 / tirs, 1)
    if avec_equipe:
        v["victoires_pct"] = round(sum(p["resultat"] == "victoire" for p in avec_equipe) * 100 / len(avec_equipe), 1)
    return v


def lire_mmr(mmr):
    """Rang actuel, RR, meilleur rang et cet acte, depuis la réponse /mmr/v1/players."""
    mmr = mmr or {}
    derniere = mmr.get("LatestCompetitiveUpdate") or {}
    saisons = ((mmr.get("QueueSkills") or {}).get("competitive") or {}).get("SeasonalInfoBySeasonID") or {}
    acte = saisons.get(derniere.get("SeasonID")) or {}
    tier = acte.get("CompetitiveTier", derniere.get("TierAfterUpdate"))
    rr = acte.get("RankedRating", derniere.get("RankedRatingAfterUpdate"))
    meilleur = 0
    for s in saisons.values():
        for t, victoires in (s.get("WinsByTier") or {}).items():
            if victoires and str(t).isdigit():
                meilleur = max(meilleur, int(t))
    return {"tier": tier, "rr": rr, "meilleur": meilleur or None,
            "victoires_acte": acte.get("NumberOfWinsWithPlacements", acte.get("NumberOfWins")),
            "parties_acte": acte.get("NumberOfGames"), "classement": acte.get("LeaderboardRank") or None}


# ---------------------------------------------------------------- le jeu

class Valorant(Jeu):
    id = "valorant"
    nom = "Valorant"
    icone = ""
    couleur = "#FF4655"
    stat_vedette = "kd"
    connexion_nom = "Riot"
    connexion_aide = ("Connecte-toi une fois avec ton compte Riot : ensuite tout est automatique, même jeu fermé. "
                      "(Sans connexion, AllMyStats se branche sur le client Riot quand il est ouvert.)")
    connexion_consigne = "Connecte-toi avec ton compte Riot et coche « Rester connecté »."
    cles_connexion = ("riot_connecte",)
    dossier_connexion = DOSSIER_CONNEXION

    reglages = [
        {"cle": "cle_henrikdev", "nom": "Clé HenrikDev", "optionnel": True, "secret": True,
         "aide": "Pour tes stats (comme les trackers). Clé gratuite : api.henrikdev.xyz > Dashboard > API Keys > "
                 "Create First Key. Colle-la ici : ne la partage avec personne.",
         "lien": "https://api.henrikdev.xyz/dashboard/api-keys"},
        {"cle": "riot_id", "nom": "Riot ID", "optionnel": True,
         "aide": "Rempli tout seul avec « Se connecter avec Riot ». Sinon : Pseudo#TAG (ex : Angelo#EUW)."},
        {"cle": "region", "nom": "Région (facultatif)", "optionnel": True, "avance": True,
         "aide": "Trouvée toute seule. Sinon : eu, na, ap ou kr."},
    ]

    R, C, A = "Rang", "Combat (parties suivies)", "Compte"
    stats = [
        Stat("points_rang", "Rang", "auto", groupe=R, icone="valo_rang",
             aide="Ton rang en classé. La courbe compte 100 points par division (+ ton RR) pour suivre ta progression."),
        Stat("rr", "RR", "auto", groupe=R, icone="valo_rr", aide="Points de ta division actuelle (0 à 100)"),
        Stat("victoires_acte", "Victoires classées (cet acte)", "auto", groupe=R, icone="valo_victoire"),
        Stat("parties_acte", "Parties classées (cet acte)", "auto", groupe=R, icone="manette"),
        Stat("kd", "Ratio K/D", "auto", decimales=2, groupe=C, icone="valo_viseur"),
        Stat("acs", "Score moyen (ACS)", "auto", groupe=C, icone="valo_acs", aide="Score de combat moyen par manche"),
        Stat("adr", "Dégâts par manche (ADR)", "auto", groupe=C, icone="valo_degats"),
        Stat("hs", "Headshots", "auto", unite="%", decimales=1, groupe=C, icone="valo_tete"),
        Stat("victoires_pct", "Victoires", "auto", unite="%", decimales=1, groupe=C, icone="valo_victoire"),
        Stat("eliminations", "Éliminations", "auto", groupe=C, icone="valo_viseur"),
        Stat("niveau", "Niveau du compte", "auto", groupe=A, icone="valo_niveau"),
        Stat("parties_suivies", "Parties suivies", "auto", groupe=A, icone="manette"),
        Stat("temps_suivi", "Temps de jeu suivi", "auto", unite="h", decimales=1, groupe=A, icone="horloge"),
    ]

    # ------------------------------------------------------------------ compte

    def _compte(self, dossier=None):
        return _lire(_fichier(dossier or chemins.DONNEES, "valo_compte.json"), {})

    def est_connecte(self, reglages):
        return bool(self._compte().get("puuid")) and reglages.get("valo_pause") != "oui"

    def nom_du_compte(self, reglages):
        return self._compte().get("nom", "")

    def connexion(self, reglages, dossier):
        """Fenêtre de connexion Riot : on attend le retour de Riot avec le jeton dans l'adresse."""
        profil = os.path.join(dossier, DOSSIER_CONNEXION)
        try:
            adresse, _ = navigateur.attendre_url(URL_AUTH, profil, "access_token=", arguments_en_plus=ARGS_RIOT)
        except navigateur.ErreurConnexion as e:
            raise ErreurJeu(f"Fenêtre de connexion Riot : {e}")
        session = session_depuis_adresse(adresse, reglages.get("region"))
        _JETONS_WEB.update(session=dict(session), quand=time.time())
        compte = self._compte(dossier)
        if compte.get("puuid") and session["puuid"] and compte["puuid"] != session["puuid"]:
            self._oublier_parties(dossier)
            compte = {}
        compte.update(puuid=session["puuid"] or compte.get("puuid"), nom=session["nom"] or compte.get("nom", ""),
                      region=session["region"])
        _ecrire(_fichier(dossier, "valo_compte.json"), compte)
        trouves = {"riot_connecte": "oui", "valo_pause": ""}
        if compte.get("nom"):
            trouves["riot_id"] = compte["nom"]
        nom = compte.get("nom") or "ton compte"
        if not (reglages.get("cle_henrikdev") or "").strip():
            return trouves, (f"Connecté à Riot : {nom}. Dernière étape : colle ta clé HenrikDev dans les "
                             f"Réglages de Valorant pour récupérer tes stats.")
        try:
            with _verrou:
                self._synchroniser({**reglages, **trouves}, dossier, session)
        except (ErreurJeu, ClientFerme) as e:   # la connexion est faite, seules les stats ont coincé
            return trouves, f"Connecté à Riot : {nom}. Stats pas encore récupérées : {e}"
        return trouves, f"Connecté à Riot : {nom} · stats à jour"

    def _oublier_parties(self, dossier):
        try:
            os.remove(_fichier(dossier, "valo_parties.json"))
        except OSError:
            pass

    def _riot_id(self, reglages, dossier):
        return (reglages.get("riot_id") or self._compte(dossier).get("nom") or "").strip()

    def _session(self, reglages, dossier):
        """La connexion Riot (fenêtre) en priorité, sinon le client Riot ouvert sur ce PC."""
        if reglages.get("riot_connecte"):
            try:
                return session_web(dossier, reglages.get("region"))
            except ConnexionExpiree:
                if not client_ouvert():
                    raise
            except ErreurJeu:
                if not client_ouvert():
                    raise
        return ouvrir_session(reglages.get("region"))

    def deconnecter(self, dossier):
        _JETONS_WEB.clear()
        try:
            os.remove(_fichier(dossier, "valo_compte.json"))
        except OSError:
            pass
        return {"valo_pause": "oui"}   # plus de synchro tant que tu ne reconnectes pas

    # ------------------------------------------------------------------ synchronisation

    def _synchroniser(self, reglages, dossier, session=None):
        """Met à jour tes stats. Avec une clé HenrikDev : par HenrikDev (le plus fiable).
        Sinon : directement auprès des serveurs de Valorant (connexion Riot ou client ouvert). Renvoie le compte."""
        cle = (reglages.get("cle_henrikdev") or "").strip()
        riot_id = self._riot_id(reglages, dossier)
        if cle and "#" in riot_id:
            return self._synchroniser_henrik(cle, riot_id, reglages, dossier)
        return self._synchroniser_riot(reglages, dossier, session)

    def _synchroniser_henrik(self, cle, riot_id, reglages, dossier):
        nom, _, tag = riot_id.partition("#")
        q = lambda t: urllib.parse.quote(t.strip(), safe="")
        compte = self._compte(dossier)
        puuid = compte.get("puuid") or ""
        # Avec la connexion Riot, on connaît ton identifiant de compte (PUUID) : on s'en sert plutôt que du pseudo
        # (pas de souci avec les caractères spéciaux, ni si tu changes de pseudo)
        if puuid:
            compte_hd = _henrik(f"v2/by-puuid/account/{q(puuid)}", cle, "compte") or {}
        else:
            compte_hd = _henrik(f"v2/account/{q(nom)}/{q(tag)}", cle, "compte") or {}
        if compte.get("puuid") and compte_hd.get("puuid") and compte["puuid"] != compte_hd["puuid"]:
            self._oublier_parties(dossier)   # autre compte : on repart de zéro
            compte = {}
        puuid = compte_hd.get("puuid") or puuid
        region = (reglages.get("region") or compte_hd.get("region") or compte.get("region") or "eu").lower()
        if region not in REGIONS_HENRIK:
            region = "eu"
        a_puuid = f"{q(region)}/pc/{q(puuid)}" if puuid else None
        a_nom = f"{q(region)}/pc/{q(nom)}/{q(tag)}"
        problemes = []
        try:
            mmr = lire_mmr_henrik(_henrik(f"v3/by-puuid/mmr/{a_puuid}" if a_puuid else f"v3/mmr/{a_nom}", cle, "rang"))
        except ErreurJeu as e:
            mmr = compte.get("mmr") or {}
            problemes.append(str(e))
        chemin_parties = _fichier(dossier, "valo_parties.json")
        parties = _lire(chemin_parties, {})
        try:
            liste = _henrik(f"v4/by-puuid/matches/{a_puuid}?size=10" if a_puuid else f"v4/matches/{a_nom}?size=10",
                            cle, "parties") or []
        except ErreurJeu as e:
            liste = []
            problemes.append(str(e))
        for m in liste:
            resume = resumer_partie_henrik(m, puuid, riot_id)
            if resume and resume["id"] and resume["id"] not in parties:
                parties[resume["id"]] = resume
        if len(parties) > GARDER:
            parties = dict(sorted(parties.items(), key=lambda e: e[1].get("debut", 0))[-GARDER:])
        _ecrire(chemin_parties, parties)
        if problemes and len(problemes) == 2 and not compte_hd:
            raise ErreurJeu(problemes[0])
        nom_hd = f"{compte_hd.get('name') or nom}#{compte_hd.get('tag') or tag}"
        carte = compte_hd.get("card")
        compte = {**compte, "puuid": puuid or compte.get("puuid"), "nom": nom_hd, "region": region,
                  "carte": (carte.get("id") if isinstance(carte, dict) else carte) or compte.get("carte"),
                  "niveau": compte_hd.get("account_level", compte.get("niveau")), "mmr": mmr,
                  "quand": time.time(), "source": "henrik", "reste": 0, "problemes": problemes}
        _ecrire(_fichier(dossier, "valo_compte.json"), compte)
        return compte

    def _synchroniser_riot(self, reglages, dossier, session=None):
        session = session or self._session(reglages, dossier)
        puuid = session["puuid"]
        compte = self._compte(dossier)
        if compte.get("puuid") and compte["puuid"] != puuid:   # autre compte Riot : on repart de zéro
            self._oublier_parties(dossier)
            compte = {}
        niveau = self._trouver_reglages(session, compte, reglages)
        if not session["nom"]:
            try:
                n = _pd(session, "/name-service/v2/players", "PUT", [puuid]) or []
                if n and n[0].get("GameName"):
                    session["nom"] = f"{n[0]['GameName']}#{n[0].get('TagLine', '')}"
            except ErreurJeu:
                pass
        try:
            mmr = lire_mmr(_pd(session, f"/mmr/v1/players/{puuid}"))
        except ErreurJeu:
            mmr = compte.get("mmr") or {}

        # Historique : on ne télécharge que les parties qu'on n'a pas encore
        chemin_parties = _fichier(dossier, "valo_parties.json")
        parties = _lire(chemin_parties, {})
        try:
            historique = (_pd(session, f"/match-history/v1/history/{puuid}?startIndex=0&endIndex=20") or {}).get("History") or []
        except ErreurJeu:
            historique = []
        nouvelles = [h["MatchID"] for h in historique if h.get("MatchID") and h["MatchID"] not in parties]
        for id_partie in nouvelles[:NOUVELLES_PAR_SYNCHRO]:
            try:
                resume = resumer_partie(_pd(session, f"/match-details/v1/matches/{id_partie}") or {}, puuid)
            except ErreurJeu:
                break
            parties[id_partie] = resume or {"ignoree": True, "debut": time.time()}
        if len(parties) > GARDER:
            parties = dict(sorted(parties.items(), key=lambda e: e[1].get("debut", 0))[-GARDER:])
        _ecrire(chemin_parties, parties)

        carte = compte.get("carte")
        try:   # la carte de joueur équipée dans le jeu (pour la photo de profil)
            identite = (_pd(session, f"/personalization/v2/players/{puuid}/playerloadout") or {}).get("Identity") or {}
            carte = identite.get("PlayerCardID") or carte
        except ErreurJeu:
            pass
        compte = {**compte, "puuid": puuid, "nom": session["nom"] or compte.get("nom", ""), "carte": carte,
                  "region": session["region"], "shard": session["shard"], "version": session["version"],
                  "source": "web" if session.get("web") else "client", "niveau": niveau, "mmr": mmr, "quand": time.time(),
                  "reste": max(0, len(nouvelles) - NOUVELLES_PAR_SYNCHRO)}
        _ecrire(_fichier(dossier, "valo_compte.json"), compte)
        return compte

    def _trouver_reglages(self, session, compte, reglages):
        """Trouve la région (shard) et la version que les serveurs acceptent, en lisant le niveau du compte
        (petite demande). Renvoie le niveau. Ce qui a marché est retenu pour la prochaine fois."""
        shards = [session["shard"]]
        if compte.get("shard") and not reglages.get("region"):
            shards.insert(0, compte["shard"])
        if not reglages.get("region"):
            shards += [x for x in SHARDS_A_ESSAYER if x not in shards]
        versions = list(dict.fromkeys(([compte["version"]] if compte.get("version") else []) + session["versions"]))
        derniere = None
        for shard in dict.fromkeys(shards):
            for version in versions:
                session.update(shard=shard, version=version)
                try:
                    xp = _pd(session, f"/account-xp/v1/players/{session['puuid']}") or {}
                    if shard != SHARDS.get(session["region"]):
                        session["region"] = shard
                    return (xp.get("Progress") or {}).get("Level")
                except RefusServeur as e:
                    derniere = e
                    if e.code == 404:   # pas la bonne région : inutile d'essayer d'autres versions ici
                        break
        raise ErreurJeu(f"{derniere}. Colle ta clé HenrikDev dans les Réglages de Valorant : AllMyStats passera "
                        f"par elle, comme les trackers.")

    def surveiller(self, reglages, dossier):
        """Toutes les minutes : si le client Riot est ouvert, on se resynchronise toutes les 5 minutes
        (tes nouvelles parties arrivent toutes seules, comme sur un tracker)."""
        avec_cle = bool((reglages.get("cle_henrikdev") or "").strip()) and "#" in self._riot_id(reglages, dossier)
        if reglages.get("valo_pause") == "oui" or not (avec_cle or reglages.get("riot_connecte") or client_ouvert()):
            return None
        if time.time() - self._compte(dossier).get("quand", 0) < SYNCHRO_TOUTES:
            return None
        if not _verrou.acquire(blocking=False):
            return None
        try:
            self._synchroniser(reglages, dossier)
        except (ClientFerme, ErreurJeu, navigateur.ErreurConnexion):
            return None
        finally:
            _verrou.release()
        return self._valeurs(dossier)

    # ------------------------------------------------------------------ valeurs et fiche

    def _parties(self, dossier):
        parties = [p for p in _lire(_fichier(dossier, "valo_parties.json"), {}).values() if not p.get("ignoree")]
        return sorted(parties, key=lambda p: p.get("debut", 0), reverse=True)

    def _valeurs(self, dossier):
        compte = self._compte(dossier)
        mmr = compte.get("mmr") or {}
        valeurs = calculer(self._parties(dossier))
        valeurs.update({
            "points_rang": points_rang(mmr.get("tier"), mmr.get("rr")),
            "rr": mmr.get("rr") if (mmr.get("tier") or 0) >= 3 else None,
            "victoires_acte": mmr.get("victoires_acte"),
            "parties_acte": mmr.get("parties_acte"),
            "niveau": compte.get("niveau"),
        })
        return {k: v for k, v in valeurs.items() if v is not None}

    def recuperer(self, reglages, dossier):
        if reglages.get("valo_pause") == "oui":
            raise ErreurJeu("Valorant est déconnecté : clique sur « Se connecter avec Riot » pour reprendre.")
        source, message = "client", ""
        try:
            with _verrou:
                compte = self._synchroniser(reglages, dossier)
            source = compte.get("source", "client")
            message = "Stats à jour" + {"henrik": " (HenrikDev)", "web": " (connexion Riot)"}.get(source, " (client Riot)")
            if compte.get("problemes"):
                message += " · en partie : " + " / ".join(compte["problemes"])
            if compte.get("reste"):
                message += f" · {compte['reste']} partie(s) arrivent à la prochaine actualisation"
        except (ClientFerme, ConnexionExpiree) as e:
            if not self._compte(dossier).get("puuid"):
                raise ErreurJeu(f"{e}. Clique sur « Se connecter avec Riot », puis colle ta clé HenrikDev dans les Réglages.")
            source = "memoire"
            message = f"{e} · dernières stats gardées"
        return self._valeurs(dossier), self.fiche(reglages, dossier, source), message

    def fiche(self, reglages, dossier, source="client"):
        compte = self._compte(dossier)
        mmr = compte.get("mmr") or {}
        noms = _noms(dossier)
        agents, cartes = noms.get("agents", {}), noms.get("cartes", {})
        parties = self._parties(dossier)
        quand = datetime.fromtimestamp(compte.get("quand", time.time())).strftime("%d/%m à %H:%M")

        rang = nom_rang(mmr.get("tier"))
        badge = rang + (f" · {mmr['rr']} RR" if (mmr.get("tier") or 0) >= 3 and mmr.get("rr") is not None else "")
        if mmr.get("classement"):
            badge += f" · n°{mmr['classement']}"
        etat = [
            {"nom": {"henrik": "HenrikDev", "web": "Connexion Riot"}.get(source, "Client Riot" if source == "client"
                                                                          else "Source"),
             "icone": "cle" if source == "henrik" else "valo_client",
             "ok": True if source in ("client", "web", "henrik") else None,
             "texte": "stats à jour" if source in ("client", "web", "henrik") else f"dernière synchro le {quand}"},
            {"nom": "Parties suivies", "icone": "manette", "ok": True if parties else None,
             "texte": f"{len(parties)} partie(s)" if parties else "aucune pour l'instant"},
        ]
        if not (reglages.get("cle_henrikdev") or "").strip():
            etat.append({"nom": "Clé HenrikDev", "icone": "cle", "ok": False, "texte": "à ajouter dans les Réglages"})

        sections = [{"titre": "Rang", "icone": "valo_rang", "lignes": [
            ["Rang actuel", badge, "valo_rang"],
            ["Meilleur rang", nom_rang(mmr.get("meilleur")) if mmr.get("meilleur") else "—", "valo_victoire"],
            ["Cet acte", f"{mmr.get('victoires_acte') or 0} victoire(s) sur {mmr.get('parties_acte') or 0} partie(s)",
             "manette"],
        ]}]

        img_agents, img_cartes, img_rangs = noms.get("img_agents", {}), noms.get("img_cartes", {}), noms.get("rangs", {})

        def cle(k):
            return k if (k or "").startswith("/") else (k or "").lower()

        def nom_agent(k):
            return agents.get(cle(k)) or (k if k and not re.fullmatch(r"[0-9a-f-]{36}", k) else "Agent")

        def nom_carte(k):
            return cartes.get(cle(k)) or (k if k and not k.startswith("/") else "")

        def fiche_partie(p):
            couleur = {"victoire": "#33D19A", "defaite": "#FF6B5E"}.get(p["resultat"], "#9AA3C7")
            titre = {"victoire": "Victoire", "defaite": "Défaite", "egalite": "Égalité"}[p["resultat"]]
            tours = p["tours"] or 1
            return {
                "titre": f"{titre} {p['marque']}".strip(),
                "sous_titre": " · ".join(x for x in (nom_agent(p["agent"]), nom_carte(p["carte"]),
                                                      FILES.get(p["file"]) or p.get("file_nom") or p["file"].capitalize(),
                                                      datetime.fromtimestamp(p["debut"]).strftime("%d/%m %H:%M")) if x),
                "icone": "valo_agent", "couleur": couleur,
                "image": img_agents.get(cle(p["agent"])), "banniere": img_cartes.get(cle(p["carte"])),
                "lignes": [["K / D / A", f"{p['k']} / {p['d']} / {p['a']}"],
                           ["ACS", str(round(p["score"] / tours))],
                           ["Dégâts / manche", str(round(p["degats"] / tours))],
                           ["Headshots", f"{round(p['tete'] * 100 / p['tirs'])} %" if p["tirs"] else "—"]],
            }

        if parties:
            sections.append({"titre": "Dernières parties", "icone": "manette",
                             "cartes": [fiche_partie(p) for p in parties[:12]]})

            def regrouper(champ, nommer, images, icone_secours):
                groupes = {}
                for p in parties:   # regroupé par nom : les anciennes parties gardaient le nom, les nouvelles l'identifiant
                    groupes.setdefault(nommer(p[champ]) or "Inconnue", []).append(p)
                lignes = []
                for nom, ps in sorted(groupes.items(), key=lambda e: -len(e[1]))[:8]:
                    st = calculer(ps)
                    txt = f"{len(ps)} partie(s) · K/D {st['kd']:.2f}".replace(".", ",")
                    if "victoires_pct" in st:
                        txt += f" · {st['victoires_pct']:.0f} % de victoires"
                    image = next((images.get(cle(p[champ])) for p in ps if images.get(cle(p[champ]))), None)
                    lignes.append([nom, txt, image or icone_secours])
                return lignes

            sections.append({"titre": "Tes agents", "icone": "valo_agent",
                             "lignes": regrouper("agent", nom_agent, img_agents, "valo_agent")})
            sections.append({"titre": "Tes cartes", "icone": "valo_carte",
                             "lignes": regrouper("carte", nom_carte, img_cartes, "valo_carte")})
        else:
            sections.append({"titre": "Comment ça marche", "icone": "astuce", "conseils": [
                ("valo_client", "Clique sur **Se connecter avec Riot** et connecte-toi (coche « Rester connecté »)."),
                ("cle", "Colle ta **clé HenrikDev** gratuite dans les Réglages de Valorant (api.henrikdev.xyz > "
                        "Dashboard > API Keys)."),
                ("actualiser", "AllMyStats lit ensuite ton rang, ton niveau et tes parties toutes les 5 minutes, même "
                               "jeu fermé. Active **Toujours actif** pour ne rien rater."),
            ]})
        image_rang = img_rangs.get(str(mmr.get("tier"))) if (mmr.get("tier") or 0) >= 3 else None
        tuiles = {}
        if mmr.get("tier") is not None:
            tuiles["points_rang"] = {"texte": rang, "image": image_rang}   # les RR ont déjà leur propre case
        return {"etat": etat, "sections": sections, "tuiles": tuiles,
                "badge": {"texte": badge, "icone": "valo_rang", "image": image_rang}, **images_carte(compte.get("carte"))}
