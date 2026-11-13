"""Call of Duty : import du fichier « Mes données personnelles » envoyé par Activision.

Activision envoie, sur simple demande (portail « Confidentialité et protection des données », demande
d'accès), un fichier HTML avec chacune de tes parties depuis Vanguard (2021) : éliminations, morts,
résultat, tirs, score… AllMyStats lit ce fichier SANS lecture d'écran et en tire tes stats par jeu.

Le fichier contient aussi des données sensibles (adresses IP…) : AllMyStats le lit en mémoire, ne garde
que les totaux (K/D, victoires…) et ne l'enregistre jamais.

Le format exact n'est pas documenté par Activision : la lecture se fait par les titres des tableaux
(« Black Ops 6 … Multiplayer … ») et les noms de colonnes (« Kills », « Deaths », « Match Outcome »…),
en tolérant les variantes. Le rapport d'import dit ce qui a été reconnu ou pas.
"""

import html
import io
import re
import zipfile
from datetime import datetime, timezone

from . import _cod_commun as cod

# Codes internes parfois utilisés à la place du nom du jeu
CODES_TITRE = {"jup": "cod_mw3", "mw3": "cod_mw3", "t10": "cod_bo6", "bo6": "cod_bo6", "t11": "cod_bo7",
               "bo7": "cod_bo7", "mw2": "cod_mw2", "cod22": "cod_mw2", "mw4": "cod_mw4", "cw": "cod_coldwar"}
IGNORES = r"vanguard|campaign|campagne|purchase|achat|transaction|login|connexion|ip address|adresse ip|ban|report"


# ---------------------------------------------------------------- lecture du HTML

_BALISE = re.compile(r"<(/?)(table|tr|td|th|h[1-6]|p|div|span|b|strong|caption|summary|br)\b[^>]*>", re.I)


def _texte(fragment):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", fragment))).strip()


class _Tableaux:
    """Récupère chaque <table> avec le dernier texte de titre vu juste avant.
    (Lecture « à la main » : le .exe d'AllMyStats n'embarque pas html.parser.)"""

    def __init__(self):
        self.tableaux = []

    def feed(self, source):
        titre, pile, ligne, cellule, pos, texte_hors = "", [], None, None, 0, []
        for m in _BALISE.finditer(source):
            entre = source[pos:m.start()]
            pos = m.end()
            fermante, tag = m.group(1) == "/", m.group(2).lower()
            if cellule is not None:
                cellule.append(entre)
            elif not pile:
                texte_hors.append(entre)
            if tag == "table":
                if not fermante:
                    pile.append({"titre": titre, "lignes": []})
                elif pile:
                    self.tableaux.append(pile.pop())
            elif tag == "tr" and pile:
                if not fermante:
                    ligne = []
                elif ligne is not None:
                    if any(ligne):
                        pile[-1]["lignes"].append(ligne)
                    ligne = None
            elif tag in ("td", "th") and pile:
                if not fermante:
                    cellule = []
                elif cellule is not None:
                    if ligne is not None:
                        ligne.append(_texte("".join(cellule)))
                    cellule = None
            elif tag == "br":
                if cellule is not None:
                    cellule.append(" ")
            elif fermante and not pile:
                t = _texte("".join(texte_hors))
                if t:
                    titre = t[:200]
                texte_hors = []

    def close(self):
        pass


def _textes_html(contenu, nom):
    """Le ou les fichiers HTML (le fichier lui-même, ou ceux d'un .zip)."""
    if contenu[:2] == b"PK":
        with zipfile.ZipFile(io.BytesIO(contenu)) as z:
            for info in z.infolist():
                if info.filename.lower().endswith((".html", ".htm")) and info.file_size < 400_000_000:
                    yield info.filename, z.read(info).decode("utf-8", errors="replace")
        return
    yield nom, contenu.decode("utf-8", errors="replace")


# ---------------------------------------------------------------- colonnes

def _norme(t):
    return re.sub(r"[^a-z0-9]+", " ", (t or "").lower()).strip()


COLONNES = {   # clé -> noms de colonne possibles (déjà « normés »), du plus précis au plus vague
    "quand": ["utc timestamp", "match start timestamp", "match start", "start time", "timestamp", "date"],
    "debut": ["match start timestamp", "match start", "start time"],
    "fin": ["match end timestamp", "match end", "end time"],
    "titre": ["game title", "title", "game"],
    "mode": ["game type", "game mode", "mode", "playlist"],
    "resultat": ["match outcome", "outcome", "result", "win loss"],
    "kills": ["kills", "eliminations"],
    "deaths": ["deaths"],
    "shots": ["shots fired", "shots"],
    "hits": ["shots hit", "hits"],
    "score": ["score"],
    "place": ["team placement", "final placement", "placement", "position"],
    "manche": ["highest round", "round reached", "rounds", "round"],
    "rang": ["rank at end", "level at end", "rank"],
    "prestige": ["prestige at end", "prestige"],
    "l_kills": ["lifetime kills"], "l_deaths": ["lifetime deaths"], "l_wins": ["lifetime wins"],
    "l_losses": ["lifetime losses"], "l_games": ["lifetime games played", "lifetime matches played"],
    "l_hits": ["lifetime hits"], "l_misses": ["lifetime misses"], "l_temps": ["lifetime time played"],
}


def _colonnes(entete):
    noms = [_norme(c) for c in entete]
    trouvees = {}
    for cle, possibles in COLONNES.items():
        for p in possibles:
            if p in noms:
                i = noms.index(p)
                if i not in trouvees.values():
                    trouvees[cle] = i
                    break
    return trouvees


def _nombre(t):
    t = (t or "").strip().replace(" ", "").replace(" ", "")
    if not t or t in ("-", "—"):
        return None
    t = t.replace("%", "")
    if re.fullmatch(r"-?\d{1,3}(,\d{3})+(\.\d+)?", t):
        t = t.replace(",", "")
    t = t.replace(",", ".")
    try:
        return float(t)
    except ValueError:
        return None


def _date(t):
    t = (t or "").strip()
    if not t:
        return None
    if re.fullmatch(r"\d{10}(\.\d+)?", t):
        return float(t)
    if re.fullmatch(r"\d{13}", t):
        return int(t) / 1000
    t = t.replace("Z", "+00:00").replace(" UTC", "+00:00")
    for essai in (t, t.replace(" ", "T", 1)):
        try:
            d = datetime.fromisoformat(essai)
            return (d if d.tzinfo else d.replace(tzinfo=timezone.utc)).timestamp()
        except ValueError:
            pass
    for f in ("%m/%d/%Y %H:%M", "%m/%d/%Y %H:%M:%S", "%d/%m/%Y %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(t, f).replace(tzinfo=timezone.utc).timestamp()
        except ValueError:
            pass
    return None


def _duree_heures(t):
    """« 123:45:06 », « 5d 3h », secondes… -> heures."""
    t = (t or "").strip().lower()
    if not t:
        return None
    m = re.fullmatch(r"(\d+):(\d{2}):(\d{2})", t)
    if m:
        return int(m[1]) + int(m[2]) / 60 + int(m[3]) / 3600
    parties = re.findall(r"(\d+(?:\.\d+)?)\s*([dhms])", t)
    if parties:
        mult = {"d": 24, "h": 1, "m": 1 / 60, "s": 1 / 3600}
        return sum(float(n) * mult[u] for n, u in parties)
    n = _nombre(t)
    return n / 3600 if n is not None and n > 1000 else None


# ---------------------------------------------------------------- jeu et mode d'un tableau

def _titre_du_texte(texte):
    texte_bas = (texte or "").lower()
    for titre, motif in cod.MOTS_TITRE:
        if re.search(motif, texte_bas):
            return titre
    code = _norme(texte).replace(" ", "")
    return CODES_TITRE.get(code)


def _mode_du_texte(texte):
    t = (texte or "").lower()
    if re.search(cod.MOTS_ZOMBIES, t):
        return "zombies"
    if re.search(cod.MOTS_WARZONE + r"|\bbr\b|\bwz\b", t):
        return "warzone"
    if re.search(r"multi\s*-?\s*player|multijoueur|\bmp\b", t):
        return "mp"
    return None


def _cible(titre, mode, quand):
    if mode == "warzone":
        return cod.titre_warzone(quand) if quand else "cod_warzone_mw4"
    return titre


# ---------------------------------------------------------------- calcul des stats

class _Cumul:
    def __init__(self):
        self.parties = self.kills = self.deaths = self.wins = self.losses = 0
        self.shots = self.hits = self.score = self.minutes = 0.0
        self.top5 = self.top10 = 0
        self.manche_max = 0
        self.dernier = None   # (quand, ligne, colonnes) : la partie la plus récente, pour les « Lifetime »
        self.premier = self.derniere_partie = None


def _ajouter(c, ligne, col, mode):
    val = lambda cle: _nombre(ligne[col[cle]]) if cle in col and col[cle] < len(ligne) else None
    texte = lambda cle: ligne[col[cle]] if cle in col and col[cle] < len(ligne) else ""
    quand = _date(texte("quand"))
    c.parties += 1
    c.kills += val("kills") or 0
    c.deaths += val("deaths") or 0
    c.shots += val("shots") or 0
    c.hits += val("hits") or 0
    resultat = texte("resultat").lower()
    place = val("place")
    if re.search(r"\bwin|victo|won\b|gagn", resultat) or (mode == "warzone" and place == 1):
        c.wins += 1
    elif re.search(r"loss|lose|lost|d[ée]faite|perd", resultat):
        c.losses += 1
    if place:
        c.top5 += place <= 5
        c.top10 += place <= 10
    if val("manche"):
        c.manche_max = max(c.manche_max, int(val("manche")))
    debut, fin = _date(texte("debut")) or quand, _date(texte("fin"))
    if debut and fin and 0 < fin - debut < 4 * 3600:
        c.minutes += (fin - debut) / 60
        c.score += val("score") or 0
    if quand:
        if not c.dernier or quand > c.dernier[0]:
            c.dernier = (quand, ligne, col)
        c.derniere_partie = max(c.derniere_partie or 0, quand)
        c.premier = min(c.premier or quand, quand)


def _stats(c, mode):
    v = {}
    # Les colonnes « Lifetime » de la partie la plus récente sont les totaux officiels du jeu
    vie = {}
    if c.dernier:
        _, ligne, col = c.dernier
        for cle in ("l_kills", "l_deaths", "l_wins", "l_losses", "l_games", "l_hits", "l_misses", "rang", "prestige"):
            if cle in col and col[cle] < len(ligne):
                n = _nombre(ligne[col[cle]])
                if n is not None:
                    vie[cle] = n
        if "l_temps" in col and col["l_temps"] < len(ligne):
            h = _duree_heures(ligne[col["l_temps"]])
            if h:
                vie["l_temps"] = h
    kills, deaths = vie.get("l_kills", c.kills), vie.get("l_deaths", c.deaths)
    wins, losses = vie.get("l_wins", c.wins), vie.get("l_losses", c.losses)
    parties = vie.get("l_games", c.parties)
    if mode == "zombies":
        v["zm_parties"] = int(c.parties)
        if c.kills:
            v["zm_zombies"] = int(c.kills)
        if c.manche_max:
            v["zm_manche_max"] = c.manche_max
        return v
    v["parties"] = int(parties)
    if kills:
        v["eliminations"] = int(kills)
    if deaths:
        v["morts"] = int(deaths)
    if deaths:
        v["kd"] = round(kills / deaths, 2)
    if wins or losses or mode == "warzone":
        v["victoires"] = int(wins)
    if mode == "warzone":
        if c.top5:
            v["top5"] = int(c.top5)
        if c.top10:
            v["top10"] = int(c.top10)
    else:
        if losses:
            v["defaites"] = int(losses)
        if wins + losses:
            v["ratio_victoires"] = round(100 * wins / (wins + losses), 1)
        hits, tirs = vie.get("l_hits"), (vie.get("l_hits", 0) + vie.get("l_misses", 0))
        if hits is not None and tirs:
            v["precision"] = round(100 * hits / tirs, 1)
        elif c.shots:
            v["precision"] = round(100 * c.hits / c.shots, 1)
        if c.minutes > 5 and c.score:
            v["score_min"] = round(c.score / c.minutes)
    if "rang" in vie and 0 < vie["rang"] < 1000:
        v["niveau"] = int(vie["rang"])
    if "prestige" in vie and 0 <= vie["prestige"] < 100:
        v["prestige"] = int(vie["prestige"])
    if "l_temps" in vie:
        v["temps_jeu"] = round(vie["l_temps"], 1)
    return v


# ---------------------------------------------------------------- import

def lire(contenu, nom="donnees.html"):
    """Renvoie (stats par jeu {id_jeu: {clé: valeur, "_derniere_partie": ts}}, rapport [lignes de texte])."""
    cumuls, rapport, vus = {}, [], 0
    for nom_fichier, html in _textes_html(contenu, nom):
        lecteur = _Tableaux()
        try:
            lecteur.feed(html)
            lecteur.close()
        except Exception as e:  # HTML abîmé : on garde ce qui a été lu
            rapport.append(f"{nom_fichier} : lecture incomplète ({e.__class__.__name__})")
        for t in lecteur.tableaux:
            vus += 1
            lignes = t["lignes"]
            if len(lignes) < 2:
                continue
            entete, corps = lignes[0], lignes[1:]
            col = _colonnes(entete)
            nom_tableau = t["titre"] or "(sans titre)"
            if re.search(IGNORES, nom_tableau.lower()) and not ("kills" in col and "deaths" in col):
                continue
            if "kills" not in col and "manche" not in col:
                continue   # pas un tableau de parties
            titre_tableau, mode_tableau = _titre_du_texte(nom_tableau), _mode_du_texte(nom_tableau)
            comptees = 0
            for ligne in corps:
                titre = titre_tableau or (_titre_du_texte(ligne[col["titre"]]) if "titre" in col and col["titre"] < len(ligne) else None)
                mode = mode_tableau or (_mode_du_texte(ligne[col["mode"]]) if "mode" in col and col["mode"] < len(ligne) else None) or "mp"
                if "manche" in col and "kills" in col and mode == "mp" and not titre_tableau:
                    mode = "zombies"
                quand = _date(ligne[col["quand"]]) if "quand" in col and col["quand"] < len(ligne) else None
                cible = _cible(titre, mode, quand)
                if not cible:
                    continue
                cumul = cumuls.setdefault((cible, "zombies" if mode == "zombies" else mode), _Cumul())
                _ajouter(cumul, ligne, col, mode)
                comptees += 1
            if comptees:
                rapport.append(f"« {nom_tableau[:80]} » : {comptees} partie(s)")
            elif re.search(r"vanguard", nom_tableau.lower()):
                rapport.append(f"« {nom_tableau[:80]} » : ignoré (Vanguard n'est pas dans AllMyStats)")
            else:
                rapport.append(f"« {nom_tableau[:80]} » : jeu non reconnu (colonnes : {', '.join(entete[:8])}…)")

    resultats = {}
    for (cible, mode), c in cumuls.items():
        v = _stats(c, mode)
        r = resultats.setdefault(cible, {})
        r.update(v)
        r["_derniere_partie"] = max(r.get("_derniere_partie") or 0, c.derniere_partie or 0) or None
        r.setdefault("_parties", 0)
        r["_parties"] += c.parties
    if not vus:
        rapport.insert(0, "Aucun tableau trouvé : est-ce bien le fichier HTML envoyé par Activision ?")
    return resultats, rapport
