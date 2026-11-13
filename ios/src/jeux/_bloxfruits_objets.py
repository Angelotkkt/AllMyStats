"""Blox Fruits : catalogue des objets (wiki officiel du jeu) + lecture de ton inventaire et de ton build à l'écran.

- Le catalogue vient du wiki Blox Fruits (blox-fruits.fandom.com) : nom, catégorie, rareté et image de chaque
  objet. Il est gardé 3 jours sur le PC, donc les nouveaux objets arrivent tout seuls.
- Quand ton INVENTAIRE est ouvert en jeu, AllMyStats reconnaît les noms d'objets lus à l'écran.
- Quand ton menu STATS est ouvert, il lit tes points (Mêlée, Défense, Épée, Arme à feu, Fruit).
L'inventaire se remplit au fil de ce qu'AllMyStats voit : ouvre chaque onglet de ton inventaire une fois.
"""

import difflib
import json
import os
import re
import time
import unicodedata
import urllib.parse
import urllib.request

API_WIKI = "https://blox-fruits.fandom.com/api.php"
UA = {"User-Agent": "AllMyStats/2.13 (appli de stats perso ; contact via github.com/Angelotkkt/AllMyStats)"}
GARDER_CATALOGUE = 3 * 86400

# (clé, catégories du wiki à essayer, nom affiché) — l'ordre est celui des onglets de l'inventaire
CATEGORIES = [
    ("fruits", ["Blox Fruits", "Fruits"], "Fruits"),
    ("epees", ["Swords"], "Épées"),
    ("armes", ["Guns"], "Armes à feu"),
    ("styles", ["Fighting Styles"], "Styles de combat"),
    ("accessoires", ["Accessories"], "Accessoires"),
    ("materiaux", ["Materials"], "Matériaux"),
]
RARETES = ["Mythical", "Legendary", "Rare", "Uncommon", "Common"]
NOMS_RARETES = {"Mythical": "Mythique", "Legendary": "Légendaire", "Rare": "Rare", "Uncommon": "Peu commun",
                "Common": "Commun"}

# Menu Stats : (clé, libellés possibles en anglais et en français)
STATS_BUILD = [
    ("melee", r"m[eé]l[eé]e"),
    ("defense", r"d[eé]fen[cs]e"),
    ("epee", r"sword|[eé]p[eé]e"),
    ("arme", r"\bgun\b|arme\s*[aà]\s*feu"),
    ("fruit", r"blox\s*fruit|demon\s*fruit|fruit"),
]
NOMS_BUILD = {"melee": "Mêlée", "defense": "Défense", "epee": "Épée", "arme": "Arme à feu", "fruit": "Fruit"}


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


def normaliser(texte):
    t = "".join(c for c in unicodedata.normalize("NFD", texte or "") if unicodedata.category(c) != "Mn").lower()
    t = re.sub(r"\(.*?\)", " ", t)                 # « Dragon (Fruit) » -> « dragon »
    return re.sub(r"[^a-z0-9]+", " ", t).strip()


# ---------------------------------------------------------------- catalogue (wiki)

def _api(params):
    url = API_WIKI + "?" + urllib.parse.urlencode({**params, "format": "json"})
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.loads(r.read().decode("utf-8"))


def _pages_de(categorie, images=True):
    """Pages (titre -> image) d'une catégorie du wiki, toutes pages comprises (le wiki répond par paquets)."""
    pages, suite = {}, {}
    for _ in range(10):
        params = {"action": "query", "generator": "categorymembers", "gcmtitle": f"Category:{categorie}",
                  "gcmlimit": "500", "gcmnamespace": "0", **suite}
        if images:
            params.update(prop="pageimages", piprop="thumbnail", pithumbsize="120", pilimit="500")
        data = _api(params)
        for p in ((data.get("query") or {}).get("pages") or {}).values():
            pages[p["title"]] = (p.get("thumbnail") or {}).get("source")
        if "continue" not in data:
            break
        suite = {k: v for k, v in data["continue"].items()}
    return pages


def catalogue(dossier):
    """{"objets": {nom: {"cat", "image", "rarete"}}} — téléchargé au besoin, sinon la dernière version gardée."""
    chemin = os.path.join(dossier, "bf_catalogue.json")
    cat = _lire(chemin, {})
    if cat.get("objets") and time.time() - cat.get("quand", 0) < GARDER_CATALOGUE:
        return cat
    try:
        objets = {}
        for cle, noms_wiki, _ in CATEGORIES:
            for nom_wiki in noms_wiki:
                pages = _pages_de(nom_wiki)
                for titre, image in pages.items():
                    objets.setdefault(titre, {"cat": cle, "image": image, "rarete": None})
                if pages:
                    break
        for rarete in RARETES:
            try:
                for titre in _pages_de(rarete, images=False):
                    if titre in objets and not objets[titre]["rarete"]:
                        objets[titre]["rarete"] = rarete
            except Exception:
                pass
        if objets:
            cat = {"quand": time.time(), "objets": objets}
            _ecrire(chemin, cat)
    except Exception:
        pass   # pas d'Internet ou wiki indisponible : on garde l'ancienne version
    return cat


# ---------------------------------------------------------------- lecture de l'écran

def _index(objets):
    index = {}
    for nom, infos in objets.items():
        n = normaliser(nom)
        if len(n) >= 3:
            index.setdefault(n, nom)
            if infos.get("cat") == "fruits":   # dans l'inventaire, un fruit s'affiche « Dragon Fruit »
                index.setdefault(f"{n} fruit", nom)
    return index


def lire_inventaire(lignes, objets):
    """Objets du catalogue reconnus dans le texte de l'écran. Renvoie {nom: quantité ou None}."""
    if not objets:
        return {}
    index = _index(objets)
    cles = list(index)
    trouves = {}
    lignes = [l.strip() for l in lignes if l.strip()]
    candidats = []
    for i, ligne in enumerate(lignes):
        candidats.append((ligne, lignes[i + 1] if i + 1 < len(lignes) else ""))
        if i + 1 < len(lignes):   # nom coupé sur deux lignes
            candidats.append((f"{ligne} {lignes[i + 1]}", lignes[i + 2] if i + 2 < len(lignes) else ""))
    for texte, suivante in candidats:
        qte = None
        m = re.search(r"[x×]\s*(\d{1,5})\b", texte, re.I) or re.fullmatch(r"\s*[x×]?\s*(\d{1,5})\s*", suivante or "")
        if m:
            qte = int(m.group(1))
        n = normaliser(re.sub(r"[x×]\s*\d+", " ", texte, flags=re.I))
        if len(n) < 3:
            continue
        nom = index.get(n)
        if not nom and len(n) >= 5:
            proche = difflib.get_close_matches(n, cles, n=1, cutoff=0.88)
            nom = index[proche[0]] if proche else None
        if nom:
            trouves[nom] = qte if qte is not None else trouves.get(nom)
    return trouves


def lire_build(lignes):
    """Points du menu Stats. Renvoie {clé: points} (au moins 3 stats pour éviter les fausses lectures)."""
    lignes = [l.strip() for l in lignes if l.strip()]
    build = {}
    for i, ligne in enumerate(lignes):
        bas = normaliser(ligne)
        for cle, motif in STATS_BUILD:
            if cle in build:
                continue
            m = re.match(rf"^({motif})\b", bas)
            if not m:
                continue
            for morceau in (ligne[len(m.group(0)):], lignes[i + 1] if i + 1 < len(lignes) else ""):
                n = re.search(r"\b(\d{1,4})\b", morceau)
                if n and int(n.group(1)) <= 2800:
                    build[cle] = int(n.group(1))
                    break
            break
    return build if len(build) >= 3 else {}


# ---------------------------------------------------------------- ce qu'on garde

def fichier_inventaire(dossier):
    return os.path.join(dossier, "bf_inventaire.json")


def garder(dossier, inventaire=None, build=None):
    """Ajoute à l'inventaire gardé ce qui vient d'être lu, et remplace le build. Renvoie (nb nouveaux, build ok)."""
    chemin = fichier_inventaire(dossier)
    data = _lire(chemin, {"objets": {}, "build": {}})
    nouveaux = 0
    for nom, qte in (inventaire or {}).items():
        if nom not in data["objets"]:
            nouveaux += 1
        ancien = data["objets"].get(nom, {})
        data["objets"][nom] = {"vu": time.time(), "qte": qte if qte is not None else ancien.get("qte")}
    if build:
        data["build"] = {**build, "quand": time.time()}
    if inventaire or build:
        _ecrire(chemin, data)
    return nouveaux, bool(build)


def oublier(dossier, nom=None):
    chemin = fichier_inventaire(dossier)
    data = _lire(chemin, {"objets": {}, "build": {}})
    if nom:
        data["objets"].pop(nom, None)
    else:
        data["objets"] = {}
    _ecrire(chemin, data)


def sections(dossier):
    """Les blocs « Build » et « Inventaire » de la page Blox Fruits."""
    data = _lire(fichier_inventaire(dossier), {"objets": {}, "build": {}})
    objets = (catalogue(dossier).get("objets") or {})
    resultat = []

    build = data.get("build") or {}
    if build:
        quand = time.strftime("%d/%m à %H:%M", time.localtime(build.get("quand", time.time())))
        icones = {"melee": "bf_melee", "defense": "bf_defense", "epee": "bf_epee", "arme": "bf_arme", "fruit": "bf_fruit"}
        resultat.append({"titre": "Build", "icone": "bf_build", "note": f"Lu sur ton menu Stats le {quand}.",
                         "build": [{"cle": c, "nom": NOMS_BUILD[c], "points": build[c], "icone": icones[c]}
                                   for c, _ in STATS_BUILD if c in build]})
    else:
        resultat.append({"titre": "Build", "icone": "bf_build", "conseils": [
            ("ecran", "Ouvre ton menu **Stats** en jeu (Mêlée, Défense, Épée, Arme à feu, Fruit) : AllMyStats lit tes "
                      "points toutes les minutes, ou tout de suite avec « Tester la lecture d'écran »."),
        ]})

    onglets = []
    for cle, _, nom_onglet in CATEGORIES:
        dans = []
        for nom, infos in data.get("objets", {}).items():
            fiche = objets.get(nom) or {}
            if (fiche.get("cat") or "materiaux") != cle:
                continue
            dans.append({"nom": re.sub(r"\s*\(.*?\)", "", nom), "id": nom, "image": fiche.get("image"),
                         "rarete": (fiche.get("rarete") or "Common").lower(),
                         "rarete_nom": NOMS_RARETES.get(fiche.get("rarete") or "Common"), "qte": infos.get("qte")})
        ordre = {r.lower(): i for i, r in enumerate(RARETES)}
        dans.sort(key=lambda o: (ordre.get(o["rarete"], 9), o["nom"]))
        onglets.append({"cle": cle, "nom": nom_onglet, "objets": dans})
    total = sum(len(o["objets"]) for o in onglets)
    resultat.append({"titre": "Inventaire", "icone": "bf_inventaire", "compte_total": total,
                     "inventaire": {"onglets": onglets, "catalogue": len(objets)},
                     "note": ("Ouvre ton inventaire en jeu et passe sur chaque onglet : AllMyStats ajoute ce qu'il voit."
                              if total else "Ton inventaire est vide pour l'instant : ouvre-le en jeu (chaque onglet), "
                                            "AllMyStats ajoute les objets qu'il reconnaît.")})
    return resultat
