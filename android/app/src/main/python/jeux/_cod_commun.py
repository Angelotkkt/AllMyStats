"""Call of Duty : tout ce que les 8 jeux de la famille partagent.

Quatre sources :
0. Le fichier « Mes données » d'Activision (sans lecture d'écran, voir _cod_donnees.py) : toutes tes parties
   depuis Vanguard, importées d'un coup.
1. Le Combat Record lu sur l'écran : quand tu ouvres ton « Combat Record » / « Dossier de combat » en jeu,
   AllMyStats le lit (OCR de Windows) et range les stats dans le bon jeu.
2. Le compte Activision (connexion sur callofduty.com) : stats officielles pour Cold War et MW2 (2022),
   les seuls jeux récents qu'Activision partage encore. La session reste dans la fenêtre de connexion.
3. Le temps de jeu : mesuré quand un Call of Duty est lancé sur ce PC.
"""

import json
import os
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

from core import connexion_navigateur as navigateur
from core import windows

# Warzone est passé sur Modern Warfare 4 avec la Saison 1 (6 novembre 2026, 5 h GMT)
DEBUT_WARZONE_MW4 = datetime(2026, 11, 6, 5, 0, tzinfo=timezone.utc).timestamp()

PROCESSUS_COD = ["cod", "cod23-cod", "cod24-cod", "cod25-cod", "cod26-cod", "BlackOpsColdWar"]
TITRE_PAR_PROCESSUS = {"blackopscoldwar": "cod_coldwar", "cod23-cod": "cod_mw3", "cod24-cod": "cod_bo6",
                       "cod25-cod": "cod_bo7", "cod26-cod": "cod_mw4"}
# Mots qui trahissent le jeu dans le titre de la fenêtre ou sur l'écran (du plus précis au plus vague)
MOTS_TITRE = [
    ("cod_bo7", r"black\s*ops\s*(7|vii)\b|\bbo7\b"),
    ("cod_bo6", r"black\s*ops\s*(6|vi)\b|\bbo6\b"),
    ("cod_coldwar", r"cold\s*war"),
    ("cod_mw4", r"modern\s*warfare\s*(4|iv)\b|\bmw4\b"),
    ("cod_mw3", r"modern\s*warfare\s*(iii|3)\b|\bmw3\b"),
    ("cod_mw2", r"modern\s*warfare\s*(ii|2)\b|\bmw2\b"),
]
# Pour reconnaître un Call of Duty dont le nom de programme n'est pas encore dans la liste
MOTIF_PROCESSUS_COD = r"^(cod(\d{2})?(-cod)?|cod\d{2}\w*|blackops\w*|modernwarfare\w*)\.exe$"
MOTS_WARZONE = r"warzone|battle\s*royale|resurgence|r[ée]surgence|\bbutin\b|plunder"
MOTS_ZOMBIES = r"zombies?"

URL_COD = "https://my.callofduty.com/api/papi-client/"
DOSSIER_CONNEXION = "connexion_activision"
URL_CONNEXION = "https://www.callofduty.com/"   # l'accueil : la page de connexion change souvent d'adresse
DOMAINES = ("callofduty.com", "activision.com")
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0 Safari/537.36", "Accept": "application/json"}


def _lire(chemin, defaut):
    try:
        with open(chemin, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return defaut


def _ecrire(chemin, data):
    with open(chemin, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)


def titre_warzone(quand=None):
    return "cod_warzone_mw4" if (quand or time.time()) >= DEBUT_WARZONE_MW4 else "cod_warzone"


# ---------------------------------------------------------------- lecture du Combat Record

LIBELLES = [  # (clé, motifs du libellé en anglais et en français) — l'ordre compte
    ("zm_zombies", r"zombies?\s*(killed|kills|tu[ée]s)|[ée]liminations?\s*de\s*zombies"),
    ("zm_manche_max", r"highest\s*round|manche\s*(la\s*plus\s*haute|max\w*)|best\s*round"),
    ("kd", r"k\s*/\s*d(\s*ratio)?|ratio\s*[ée]\s*/\s*m|ratio\s*e\s*/\s*m|\bkdr\b"),
    ("ratio_victoires", r"win\s*%|win\s*(rate|ratio)|w\s*/\s*l|%\s*de\s*victoires|taux\s*de\s*victoire|ratio\s*v\s*/\s*d"),
    ("score_min", r"score\s*/\s*min|\bspm\b|score\s*par\s*minute"),
    ("eliminations", r"kills|[ée]liminations|[ée]limin[ée]s"),
    ("morts", r"deaths|morts"),
    ("victoires", r"wins|victoires"),
    ("defaites", r"losses|d[ée]faites"),
    ("top5", r"top\s*5"),
    ("top10", r"top\s*10"),
    ("parties", r"(matches|games)\s*played|parties\s*jou[ée]es|matchs\s*jou[ée]s|\bmatchs\b|\bparties\b"),
    ("temps_jeu", r"time\s*played|temps\s*de\s*jeu|temps\s*jou[ée]"),
    ("precision", r"accuracy|pr[ée]cision"),
    ("prestige", r"prestige"),
    ("niveau", r"\blevel\b|\bniveau\b|\brank\b|\brang\b"),
]
DECIMAUX = {"kd", "ratio_victoires", "precision", "score_min"}
LIMITES = {"kd": 50, "ratio_victoires": 100, "precision": 100, "score_min": 5000, "niveau": 1000,
           "prestige": 50, "zm_manche_max": 5000, "temps_jeu": 50000}


def _heures(texte):
    """« 3D 4H 12M », « 3j 4h 12min », « 76h 12m » -> heures."""
    t = texte.lower()
    j = re.search(r"(\d+)\s*(d|j)\b", t)
    h = re.search(r"(\d+)\s*h", t)
    m = re.search(r"(\d+)\s*m", t)
    if not (j or h or m):
        return None
    return round((int(j.group(1)) * 24 if j else 0) + (int(h.group(1)) if h else 0)
                 + (int(m.group(1)) / 60 if m else 0), 1)


def _nombre(texte, cle):
    if cle == "temps_jeu":
        return _heures(texte)
    m = re.search(r"\d[\d\s,.'’]*", texte)
    if not m:
        return None
    brut = m.group(0).strip().rstrip(",.")
    if cle in DECIMAUX:
        brut = brut.replace(" ", "").replace("'", "").replace("’", "")
        if brut.count(",") == 1 and "." not in brut:
            brut = brut.replace(",", ".")
        brut = brut.replace(",", "")
        try:
            return float(brut)
        except ValueError:
            return None
    chiffres = re.sub(r"[^\d]", "", brut)
    return int(chiffres) if chiffres else None


def lire_combat_record(lignes):
    """Trouve les stats dans le texte d'un Combat Record. Renvoie {clé: valeur}."""
    valeurs = {}
    lignes = [l.strip() for l in lignes if l.strip()]
    for i, ligne in enumerate(lignes):
        bas = ligne.lower()
        for cle, motif in LIBELLES:
            m = re.match(rf"\s*(?:{motif})\s*[:\-]?\s*", bas)
            if not m:
                continue
            reste = ligne[m.end():]
            valeur = _nombre(reste, cle) if re.search(r"\d", reste) else None
            if valeur is None and i + 1 < len(lignes):  # valeur sur la ligne d'en dessous
                valeur = _nombre(lignes[i + 1], cle)
            if valeur is not None and valeur <= LIMITES.get(cle, 100_000_000) and cle not in valeurs:
                valeurs[cle] = valeur
            break
    if "precision" in valeurs and valeurs["precision"] <= 1:  # 0,23 -> 23 %
        valeurs["precision"] = round(valeurs["precision"] * 100, 1)
    # Calculs utiles si le jeu ne les affiche pas
    if "kd" not in valeurs and valeurs.get("eliminations") and valeurs.get("morts"):
        valeurs["kd"] = round(valeurs["eliminations"] / valeurs["morts"], 2)
    if "ratio_victoires" not in valeurs and valeurs.get("victoires") and valeurs.get("defaites") is not None:
        total = valeurs["victoires"] + valeurs["defaites"]
        if total:
            valeurs["ratio_victoires"] = round(valeurs["victoires"] * 100 / total, 1)
    return valeurs if len(valeurs) >= 2 else {}


def titre_dans(texte):
    """Le jeu nommé dans un texte (titre de fenêtre, écran…), ou None."""
    bas = (texte or "").lower()
    for titre, motif in MOTS_TITRE:
        if re.search(motif, bas):
            return titre
    return None


def deviner_titre(infos, texte, dernier_titre):
    """À quel Call of Duty tu joues : programme, puis titre de fenêtre, puis l'écran, puis le dernier regardé."""
    proc = (infos.get("processus") or "").lower()
    bas = f"{infos.get('titre', '')}\n{texte}".lower()
    if re.search(MOTS_WARZONE, bas):
        return titre_warzone(), "warzone"
    mode = "zombies" if re.search(MOTS_ZOMBIES, bas) else "multijoueur"
    if proc in TITRE_PAR_PROCESSUS:
        return TITRE_PAR_PROCESSUS[proc], mode
    for titre, motif in MOTS_TITRE:
        if re.search(motif, bas):
            return titre, mode
    if dernier_titre and "warzone" not in dernier_titre:
        return dernier_titre, mode
    return "cod_mw4", mode


# ---------------------------------------------------------------- surveillance partagée (une fois par minute)

_verrou = threading.Lock()
_derniere_minute = {"quand": 0}


def surveiller_famille(reglages, dossier):
    """Lit l'écran et mesure le temps de jeu une seule fois par minute pour toute la famille.
    Range les résultats dans cod_ecran.json et cod_temps.json."""
    with _verrou:
        if time.time() - _derniere_minute["quand"] < 50:
            return
        _derniere_minute["quand"] = time.time()
    lances = programmes_cod()
    try:
        if lances:
            r = windows.lire_ecran_complet(noms_sans_exe(lances))
            DERNIER_ESSAI.clear()
            DERNIER_ESSAI.update({k: v for k, v in r.items() if k != "lignes"}, nb_lignes=len(r["lignes"]))
            if r["etat"] == "OK":
                _, _, valeurs = ranger_lecture(r, r["lignes"], reglages, dossier)
                DERNIER_ESSAI["trouve"] = len(valeurs)
    finally:
        _mesurer_temps(lances, reglages, dossier)  # après la lecture : on sait mieux à quel jeu tu joues


DERNIER_ESSAI = {}


def programmes_cod():
    """Les programmes Call of Duty lancés (avec .exe), connus ou reconnus à leur nom."""
    return windows.processus_lances([p + ".exe" for p in PROCESSUS_COD]) or windows.processus_par_motif(MOTIF_PROCESSUS_COD)


def noms_sans_exe(lances):
    return sorted(set(PROCESSUS_COD) | {n.rsplit(".", 1)[0] for n in lances})


def ranger_lecture(infos, lignes, reglages, dossier):
    """Range le Combat Record lu dans le bon jeu. Renvoie (titre, mode, valeurs)."""
    valeurs = lire_combat_record(lignes)
    titre, mode = deviner_titre(infos, "\n".join(lignes), reglages.get("dernier_titre"))
    _ecrire(os.path.join(dossier, "cod_dernier_jeu.json"), {"titre": titre, "quand": time.time()})
    if not valeurs:
        return titre, mode, {}
    if mode == "zombies":
        valeurs = {("zm_" + k if not k.startswith("zm_") else k): v for k, v in valeurs.items()
                   if k in ("zm_zombies", "zm_manche_max", "parties", "eliminations", "morts")}
        valeurs = {("zm_zombies" if k == "zm_eliminations" else k): v for k, v in valeurs.items()}
    chemin = os.path.join(dossier, "cod_ecran.json")
    tout = _lire(chemin, {})
    tout[titre] = {**tout.get(titre, {}), **valeurs, "_quand": time.time()}
    _ecrire(chemin, tout)
    return titre, mode, valeurs


def valeurs_ecran(titre, dossier):
    data = _lire(os.path.join(dossier, "cod_ecran.json"), {}).get(titre, {})
    return {k: v for k, v in data.items() if not k.startswith("_")}, data.get("_quand")


# ---------------------------------------------------------------- fichier « Mes données » d'Activision

def garder_import(resultats, dossier):
    """Range les totaux tirés du fichier d'Activision (jamais le fichier lui-même)."""
    chemin = os.path.join(dossier, "cod_import.json")
    tout = _lire(chemin, {})
    for titre, valeurs in resultats.items():
        tout[titre] = {**valeurs, "_quand": time.time()}
    _ecrire(chemin, tout)


def valeurs_import(titre, dossier):
    data = _lire(os.path.join(dossier, "cod_import.json"), {}).get(titre, {})
    return {k: v for k, v in data.items() if not k.startswith("_")}, data.get("_derniere_partie") or data.get("_quand"), data


# ---------------------------------------------------------------- temps de jeu (par jeu)

def _mesurer_temps(lances, reglages, dossier):
    chemin = os.path.join(dossier, "cod_temps.json")
    data = _lire(chemin, {"sessions": [], "en_cours": None})
    maintenant = time.time()
    en_cours = data.get("en_cours")
    if lances:
        nom = next(iter(lances)).rsplit(".", 1)[0]
        titre = TITRE_PAR_PROCESSUS.get(nom.lower())
        if not titre:
            titre = titre_dans(windows.titre_fenetre(nom))
        if not titre:  # le dernier jeu vu à l'écran pendant les 3 dernières heures
            vu = _lire(os.path.join(dossier, "cod_dernier_jeu.json"), {})
            if maintenant - vu.get("quand", 0) < 3 * 3600:
                titre = vu.get("titre")
        titre = titre or reglages.get("dernier_titre") or "cod_mw4"
        if not en_cours or maintenant - en_cours["vu"] > 300 or en_cours["titre"] != titre:
            if en_cours:
                data["sessions"].append({k: en_cours[k] for k in ("debut", "vu", "titre")})
            en_cours = {"debut": maintenant if en_cours else (windows.debut_processus(nom) or maintenant),
                        "vu": maintenant, "titre": titre}
        en_cours["vu"] = maintenant
        data["en_cours"] = en_cours
    elif en_cours:
        data["sessions"].append({k: en_cours[k] for k in ("debut", "vu", "titre")})
        data["en_cours"] = None
    _ecrire(chemin, data)


def valeurs_temps(titre, dossier):
    data = _lire(os.path.join(dossier, "cod_temps.json"), {"sessions": []})
    sessions = [s for s in data.get("sessions", []) if s.get("titre") == titre]
    if data.get("en_cours") and data["en_cours"].get("titre") == titre:
        sessions.append(data["en_cours"])
    if not sessions:
        return {}
    duree = lambda s: max(0, min(s["vu"] - s["debut"], 16 * 3600))
    semaine = time.time() - 7 * 86400
    return {"temps_suivi": round(sum(map(duree, sessions)) / 3600, 1),
            "temps_7j": round(sum(duree(s) for s in sessions if s["debut"] > semaine) / 3600, 1),
            "sessions": len(sessions)}


# ---------------------------------------------------------------- compte Activision

class ErreurActivision(Exception):
    pass


def lire_session(dossier):
    cookies = navigateur.lire_session("https://www.callofduty.com/robots.txt",
                                      os.path.join(dossier, DOSSIER_CONNEXION), DOMAINES)
    if not cookies.get("ACT_SSO_COOKIE"):
        raise ErreurActivision("connexion expirée : clique sur « Se connecter avec Activision »")
    return cookies


def appel_activision(chemin, cookies):
    req = urllib.request.Request(URL_COD + chemin, headers={
        **UA, "Cookie": "; ".join(f"{k}={v}" for k, v in cookies.items())})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            rep = json.loads(r.read().decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as e:
        raise ErreurActivision(f"Activision a répondu une erreur (code {e.code})")
    except (urllib.error.URLError, TimeoutError, OSError):
        raise ErreurActivision("impossible de joindre Activision")
    except ValueError:  # une page web au lieu de données
        raise ErreurActivision("Activision ne donne pas ces stats pour le moment")
    if not isinstance(rep, dict):
        raise ErreurActivision("Activision a répondu quelque chose d'inattendu")
    if rep.get("status") != "success":
        message = str((rep.get("data") or {}).get("message", "")).lower()
        if "not permitted" in message or "private" in message:
            raise ErreurActivision("tes stats sont privées : sur callofduty.com, Préférences > Liaison de comptes, "
                                   "mets « Données visibles » sur « Tout le monde »")
        raise ErreurActivision("Activision ne donne pas ces stats")
    return rep.get("data") or {}


def identites(cookies):
    data = appel_activision("crm/cod/v2/identities", cookies)
    return data.get("titleIdentities") or []


def stats_activision(code_titre, mode, cookies):
    """code_titre : "cw" (Cold War) ou "mw2" (MW2 2022). mode : "mp" ou "zm"."""
    ids = identites(cookies)
    ident = next((i for i in ids if i.get("title") == code_titre), None) or (ids[0] if ids else None)
    if not ident:
        raise ErreurActivision("aucun compte de jeu lié à ce compte Activision")
    gamer = urllib.parse.quote(ident["username"], safe="")
    data = appel_activision(f"stats/cod/v1/title/{code_titre}/platform/{ident['platform']}/gamer/{gamer}"
                            f"/profile/type/{mode}", cookies)
    p = ((data.get("lifetime") or {}).get("all") or {}).get("properties") or {}

    def nb(*cles):
        for c in cles:
            if isinstance(p.get(c), (int, float)):
                return p[c]
        return None

    if mode == "zm":
        brut = {"zm_manche_max": nb("highestRound", "bestRound", "roundsMax"),
                "zm_zombies": nb("kills"), "zm_parties": nb("totalGamesPlayed", "gamesPlayed")}
    else:
        temps = nb("timePlayedTotal", "timePlayed")
        precision = nb("accuracy")
        brut = {
            "niveau": data.get("level"), "prestige": data.get("prestige"),
            "kd": round(nb("kdRatio") or 0, 2) if nb("kdRatio") is not None else None,
            "eliminations": nb("kills"), "morts": nb("deaths"), "victoires": nb("wins"),
            "defaites": nb("losses"), "parties": nb("totalGamesPlayed", "gamesPlayed"),
            "temps_jeu": round(temps / 3600, 1) if temps else None,
            "precision": round(precision * 100, 1) if precision is not None and precision <= 1 else precision,
            "score_min": round(nb("scorePerMinute") or 0) if nb("scorePerMinute") is not None else None,
        }
        if brut["victoires"] is not None and brut["defaites"]:
            brut["ratio_victoires"] = round(brut["victoires"] * 100 / (brut["victoires"] + brut["defaites"]), 1)
    return {k: v for k, v in brut.items() if isinstance(v, (int, float))}, ident
