"""Sous-catégorie « Builds & Teams » de Genshin Impact : tu choisis un perso, AllMyStats affiche ses
meilleurs builds (armes, artefacts, stats) et ses meilleures équipes.

Les conseils viennent de Genshin-Builds (genshin-builds.com), qui publie pour ça une API publique en lecture
seule et sans compte : https://genshin-builds.com/api/llms.txt . Ils sont mis à jour chaque jour au plus,
donc AllMyStats les garde 24 h sur le PC (une seule demande par perso et par jour)."""

import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request

from .base import ErreurJeu, Jeu
from .genshin import ELEMENTS, _Noms, _ecrire_json, _lire_json

URL_API = "https://genshin-builds.com/api/genshin/{quoi}?{params}"
URL_SITE = "https://genshin-builds.com/fr/character/{slug}"
DUREE_CACHE = 24 * 3600
ENTETES = {"User-Agent": "AllMyStats/2 (appli de stats ; https://github.com/Angelotkkt/AllMyStats)",
           "Accept": "application/json"}

# Le Voyageur : un perso par élément chez Genshin-Builds
VOYAGEUR = [("Wind", "anemo", "Anémo"), ("Rock", "geo", "Géo"), ("Electric", "electro", "Électro"),
            ("Grass", "dendro", "Dendro"), ("Water", "hydro", "Hydro"), ("Fire", "pyro", "Pyro"),
            ("Ice", "cryo", "Cryo")]
ARMES = {"WEAPON_SWORD_ONE_HAND": "Épée", "WEAPON_CLAYMORE": "Espadon", "WEAPON_POLE": "Arme d'hast",
         "WEAPON_BOW": "Arc", "WEAPON_CATALYST": "Catalyseur"}
PIECES = [("sands", "Sablier"), ("goblet", "Coupe"), ("circlet", "Diadème"), ("flower", "Fleur"), ("plume", "Plume")]
APTITUDES = {"normal attack": "Attaque normale", "normal": "Attaque normale", "skill": "Compétence",
             "elemental skill": "Compétence", "burst": "Déchaînement", "elemental burst": "Déchaînement"}


# Sets d'artefacts dont le bonus 4 pièces profite à toute l'équipe mais ne se cumule pas s'il est porté deux fois
# (noms français puis anglais, comparés sans accents ni majuscules)
SETS_SOUTIEN = {
    "noblesse": ("noblesse oblige",),
    "millelith": ("millelith",),
    "instructeur": ("instructeur", "instructor"),
    "foret": ("souvenirs de la foret", "deepwood"),
    "verdure": ("verdure", "viridescent"),
    "petra": ("roche ancienne", "archaic petra"),
    "cendres": ("cite des cendres", "cinder city"),
}

# Résonances élémentaires (2 persos du même élément, ou 4 éléments différents)
RESONANCES = {
    "Pyro": "+25 % d'ATQ",
    "Hydro": "+25 % de PV max",
    "Cryo": "+15 % de taux CRIT contre les ennemis gelés ou affectés par Cryo",
    "Electro": "Les réactions Électro génèrent des particules d'énergie",
    "Geo": "+15 % de force des boucliers ; sous bouclier, +15 % de DGT et RÉS Géo des ennemis touchés réduite",
    "Anemo": "Moins d'endurance consommée, déplacement plus rapide et temps de recharge réduits de 5 %",
    "Dendro": "+50 de maîtrise élémentaire (davantage après certaines réactions)",
}


def _sans_accents(texte):
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFD", str(texte or "").lower()) if unicodedata.category(c) != "Mn")


def _set_soutien(option):
    """Une option d'artefacts (4 pièces d'un seul set) -> clé du set de soutien, ou None."""
    ensembles = (option or {}).get("ensembles") or []
    if len(ensembles) != 1:
        return None
    nom = _sans_accents(ensembles[0])
    return next((cle for cle, mots in SETS_SOUTIEN.items() if any(m in nom for m in mots)), None)


def _resonances(elements):
    elements = [e for e in elements if e]
    res = []
    for e, effet in RESONANCES.items():
        if elements.count(e) >= 2:
            res.append({"element": e, "nom": f"2 {e}", "effet": effet})
    if len(elements) == 4 and len(set(elements)) == 4:
        res.append({"element": None, "nom": "4 éléments différents", "effet": "+15 % de RÉS à tous les éléments et aux DGT physiques"})
    return res


def slug(nom_anglais):
    """« Kamisato Ayaka » -> « kamisato_ayaka » (forme des adresses de Genshin-Builds)."""
    texte = re.sub(r"['’.]", "", (nom_anglais or "").lower())
    return re.sub(r"[^a-z0-9]+", "_", texte).strip("_")


def _demander(quoi, **params):
    url = URL_API.format(quoi=quoi, params=urllib.parse.urlencode(params))
    req = urllib.request.Request(url, headers=ENTETES)
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode("utf-8"))


class BuildsGenshin(Jeu):
    id = "genshin_builds"
    nom = "Builds & Teams"
    icone = "builds_genshin"
    couleur = "#E8B04B"
    famille = "Genshin Impact"
    ordre = 2
    page = "builds"
    stats = []

    _noms = None

    def _enka(self, dossier):
        if self._noms is None:
            self._noms = _Noms(dossier)
        return self._noms

    # ------------------------------------------------------------------ la liste des persos

    def persos(self, dossier):
        """Tous les persos jouables (d'après Enka, toujours à jour), avec leur image et leur élément."""
        noms = self._enka(dossier)
        liste = []
        for cle, infos in noms.persos.items():
            if "-" in cle or not cle.isdigit():
                continue
            if cle in ("10000005", "10000007"):
                continue   # le Voyageur est ajouté plus bas, un par élément
            nom_fr = noms.texte(infos.get("NameTextMapHash"))
            nom_en = noms.textes_en.get(str(infos.get("NameTextMapHash"))) or nom_fr
            if not nom_fr or not infos.get("SideIconName"):
                continue
            element, couleur = ELEMENTS.get(infos.get("Element"), (None, "#8a8fa8"))
            liste.append({
                "id": slug(nom_en), "nom": nom_fr, "element": element, "couleur": couleur,
                "rarete": 5 if infos.get("QualityType") in ("QUALITY_ORANGE", "QUALITY_ORANGE_SP") else 4,
                "arme": ARMES.get(infos.get("WeaponType"), ""),
                "image": noms._url(infos["SideIconName"].replace("_Side", "")),
                "splash": noms._url(infos["SideIconName"].replace("UI_AvatarIcon_Side_", "UI_Gacha_AvatarImg_")),
                "ordre": int(cle),
            })
        voyageuse = noms.persos.get("10000007") or {}
        image_v = noms._url(voyageuse["SideIconName"].replace("_Side", "")) if voyageuse.get("SideIconName") else None
        splash_v = noms._url(voyageuse["SideIconName"].replace("UI_AvatarIcon_Side_", "UI_Gacha_AvatarImg_")) if voyageuse.get("SideIconName") else None
        for code, suffixe, nom_element in VOYAGEUR:
            element, couleur = ELEMENTS.get(code, (nom_element, "#8a8fa8"))
            liste.append({"id": f"traveler_{suffixe}", "nom": f"Voyageur ({nom_element})", "element": element,
                          "couleur": couleur, "rarete": 5, "arme": "Épée", "image": image_v, "splash": splash_v,
                          "ordre": 10000007})
        # Les plus récents d'abord (ce sont eux qu'on cherche le plus souvent)
        liste.sort(key=lambda p: -p["ordre"])
        return liste

    # ------------------------------------------------------------------ le build d'un perso

    def build(self, id_perso, dossier):
        id_perso = slug(id_perso)
        if not id_perso:
            raise ErreurJeu("Perso inconnu.")
        cache_dossier = os.path.join(dossier, "genshin_builds")
        os.makedirs(cache_dossier, exist_ok=True)
        chemin = os.path.join(cache_dossier, f"{id_perso}.json")
        brut = _lire_json(chemin) if os.path.exists(chemin) else None
        if not brut or time.time() - os.path.getmtime(chemin) > DUREE_CACHE:
            try:
                nouveau = self._telecharger(id_perso)
                if nouveau:
                    brut = nouveau
                    _ecrire_json(chemin, brut)
            except urllib.error.HTTPError as e:
                if not brut:
                    if e.code == 404:
                        raise ErreurJeu("Genshin-Builds n'a pas encore de build pour ce perso.")
                    if e.code == 429:
                        raise ErreurJeu("Genshin-Builds demande d'attendre un peu (trop de demandes) : réessaie dans une minute.")
                    raise ErreurJeu(f"Genshin-Builds a répondu une erreur {e.code}.")
            except Exception as e:
                if not brut:
                    raise ErreurJeu(f"Impossible de joindre Genshin-Builds ({e.__class__.__name__}). Vérifie ta connexion.")
        if not brut:
            raise ErreurJeu("Genshin-Builds n'a pas encore de build pour ce perso.")
        return self._mettre_en_forme(brut, id_perso, dossier, time.time() - os.path.getmtime(chemin)
                                     if os.path.exists(chemin) else 0)

    @staticmethod
    def _telecharger(id_perso):
        try:
            data = _demander("character", id=id_perso, lang="french")
        except urllib.error.HTTPError as e:
            if e.code != 404:
                raise
            data = None
        if not data or not isinstance(data, dict) or not (data.get("build") or data.get("builds")):
            # Nom un peu différent chez eux : on demande à leur recherche
            trouve = BuildsGenshin._chercher(id_perso.replace("_", " "))
            if trouve and trouve != id_perso:
                data = _demander("character", id=trouve, lang="french")
        return data if isinstance(data, dict) and (data.get("build") or data.get("builds")) else None

    @staticmethod
    def _chercher(texte):
        try:
            res = _demander("search", q=texte, lang="english")
        except Exception:
            return None
        if isinstance(res, dict):
            res = res.get("results") or res.get("data") or res.get("characters") or []
        for r in res if isinstance(res, list) else []:
            if isinstance(r, dict) and r.get("id"):
                return str(r["id"])
        return None

    def _mettre_en_forme(self, brut, id_perso, dossier, age):
        noms = self._enka(dossier)

        def image(nom):
            return noms.image_par_nom(nom) if nom else None

        def liste(x):
            if x is None:
                return []
            return x if isinstance(x, list) else [x]

        def nom_de(x):
            if isinstance(x, dict):
                return x.get("name") or x.get("nom") or x.get("id") or ""
            return str(x)

        builds_bruts = liste(brut.get("builds")) or [brut.get("build") or {}]
        builds = []
        for b in builds_bruts:
            if not isinstance(b, dict):
                continue
            armes = [{"nom": nom_de(a), "image": image(nom_de(a))} for a in liste(b.get("weapons")) if nom_de(a)]
            artefacts = []
            for option in liste(b.get("artifacts")):
                ensembles = [nom_de(x) for x in liste(option) if nom_de(x)]
                if ensembles:
                    artefacts.append({"ensembles": ensembles,
                                      "pieces": "4 pièces" if len(ensembles) == 1 else " + ".join("2" for _ in ensembles)})
            principales = b.get("main_stats") or b.get("stats_priority") or {}
            stats = [{"piece": nom, "valeurs": [nom_de(v) for v in liste(principales.get(cle))]}
                     for cle, nom in PIECES if principales.get(cle)]
            aptitudes = [APTITUDES.get(str(nom_de(t)).lower(), nom_de(t)) for t in liste(b.get("talent_priority"))]
            builds.append({
                "nom": b.get("role") or b.get("name") or "",
                "armes": armes,
                "artefacts": artefacts,
                "stats": stats,
                "sous_stats": [nom_de(s) for s in liste(b.get("sub_stats")) if nom_de(s)],
                "aptitudes": aptitudes,
                "note": b.get("note") or b.get("notes") or "",
            })
        equipes = []
        for t in liste(brut.get("teams")):
            if not isinstance(t, dict):
                continue
            membres = [{"nom": nom_de(c), "image": image(nom_de(c))} for c in liste(t.get("characters")) if nom_de(c)]
            if membres:
                equipes.append({"nom": t.get("name") or "", "membres": membres})
        element = brut.get("element")
        couleur = next((c for e, c in ELEMENTS.values() if e and element and e.lower() == str(element).lower()), None)
        site = brut.get("url") or ""
        return {
            "id": brut.get("id") or id_perso,
            "nom": brut.get("name") or id_perso,
            "titre": brut.get("title") or "",
            "element": element,
            "couleur": couleur,
            "arme": brut.get("weapon_type") or "",
            "rarete": brut.get("rarity"),
            "stat_bonus": brut.get("substat") or "",
            "image": image(brut.get("name")),
            "builds": builds,
            "equipes": equipes,
            "source": "Genshin-Builds",
            "lien": URL_SITE.format(slug=brut.get("id") or id_perso) if not site.startswith("http") else site,
            "age": int(age),
        }

    # ------------------------------------------------------------------ compléter une équipe

    def completer(self, ids, dossier):
        """Jusqu'à 3 persos choisis -> les persos qui vont le mieux avec eux.

        On réunit les équipes conseillées par Genshin-Builds pour chacun des persos choisis, puis on compte
        qui revient le plus souvent à leurs côtés : une équipe qui contient plusieurs des persos choisis compte
        beaucoup plus, et les premières équipes de chaque liste (les meilleures) comptent plus que les dernières."""
        choisis = []
        for i in ids:
            i = slug(i)
            if i and i not in choisis:
                choisis.append(i)
        if not choisis:
            raise ErreurJeu("Choisis au moins un perso.")
        if len(choisis) > 3:
            raise ErreurJeu("Choisis 3 persos au maximum : AllMyStats propose le reste.")
        tous = {p["id"]: p for p in self.persos(dossier)}

        def fiche(id_perso, nom=None):
            p = tous.get(id_perso)
            if p:
                return {k: p.get(k) for k in ("id", "nom", "element", "couleur", "rarete", "arme", "image")}
            noms = self._enka(dossier)
            return {"id": id_perso, "nom": nom or id_perso, "element": None, "couleur": None, "rarete": None,
                    "arme": "", "image": noms.image_par_nom(nom) if nom else None}

        # Les équipes conseillées de chaque perso choisi (gardées 24 h comme les fiches)
        equipes = {}          # membres (frozenset d'ids) -> infos
        manquants = []
        alias = {}            # autre nom chez Genshin-Builds -> id choisi
        for c in choisis:
            try:
                d = self.build(c, dossier)
            except ErreurJeu:
                manquants.append(fiche(c)["nom"])
                continue
            for autre in (d.get("id"), d.get("nom")):
                if autre and slug(autre) != c:
                    alias[slug(autre)] = c
            for rang, t in enumerate(d.get("equipes") or []):
                membres = []
                for m in t.get("membres") or []:
                    mid = slug(m.get("nom"))
                    if mid and mid not in [x for x, _ in membres]:
                        membres.append((mid, m.get("nom")))
                if len(membres) < 2:
                    continue
                cle = frozenset(x for x, _ in membres)
                poids = 1 / (1 + 0.25 * rang)
                e = equipes.setdefault(cle, {"nom": t.get("nom") or "", "membres": membres, "poids": 0, "sources": 0})
                e["poids"] = max(e["poids"], poids)
                e["sources"] += 1
        # Les noms de Genshin-Builds qui désignent un perso choisi sous un autre nom
        if alias:
            for e in list(equipes.values()):
                e["membres"] = [(alias.get(x, x), n) for x, n in e["membres"]]
            equipes = {frozenset(x for x, _ in e["membres"]): e for e in equipes.values()}

        def scores(selection):
            sel = set(selection)
            res = {}
            for e in equipes.values():
                ids_e = [x for x, _ in e["membres"]]
                communs = len(sel.intersection(ids_e))
                if not communs:
                    continue
                w = e["poids"] * (communs / len(sel)) ** 2 * (1 + 0.3 * (e["sources"] - 1))
                for x, nom in e["membres"]:
                    if x in sel:
                        continue
                    r = res.setdefault(x, {"score": 0.0, "nom": nom, "equipes": []})
                    r["score"] += w
                    if e["nom"] and e["nom"] not in r["equipes"]:
                        r["equipes"].append(e["nom"])
            return res

        # Les meilleurs coéquipiers pour la sélection
        brut = scores(choisis)
        meilleurs = sorted(brut.items(), key=lambda kv: -kv[1]["score"])[:10]
        haut = meilleurs[0][1]["score"] if meilleurs else 1
        suggestions = []
        for x, r in meilleurs:
            part = r["score"] / haut
            suggestions.append({**fiche(x, r["nom"]), "score": round(100 * part),
                                "avis": "Excellent choix" if part >= .75 else "Très bon choix" if part >= .45 else "Bon choix",
                                "nb_equipes": len(r["equipes"]), "equipes_vues": r["equipes"][:3]})

        # L'équipe complète proposée : on ajoute un par un celui qui va le mieux avec ceux déjà là
        equipe = list(choisis)
        while len(equipe) < 4:
            s = scores(equipe)
            if not s:
                break
            equipe.append(max(s.items(), key=lambda kv: kv[1]["score"])[0])
        proposition = [{**fiche(x), "propose": x not in choisis} for x in equipe]

        # Les équipes conseillées qui contiennent le plus de persos choisis
        connues = []
        for e in equipes.values():
            ids_e = [x for x, _ in e["membres"]]
            communs = len(set(choisis).intersection(ids_e))
            if communs:
                connues.append((communs, e["poids"], e))
        connues.sort(key=lambda t: (-t[0], -t[1]))
        return {
            "selection": [fiche(c) for c in choisis],
            "proposition": proposition,
            "suggestions": suggestions,
            "equipes": [{"nom": e["nom"], "communs": n, "complete": n == len(choisis),
                         "membres": [{**fiche(x, nom), "choisi": x in choisis} for x, nom in e["membres"]]}
                        for n, _, e in connues[:6]],
            "manquants": manquants,
            "source": "Genshin-Builds",
        }

    # ------------------------------------------------------------------ builder une équipe de 4

    def builds_equipe(self, ids, dossier):
        """4 persos -> le build de chacun (arme, artefacts, stats, aptitudes) avec des alternatives, en tenant
        compte de l'équipe : deux persos qui veulent la même arme ou le même set de soutien (dont le bonus ne se
        cumule pas) se voient proposer une alternative, et les résonances élémentaires sont affichées."""
        choisis = []
        for i in ids:
            i = slug(i)
            if i and i not in choisis:
                choisis.append(i)
        if len(choisis) != 4:
            raise ErreurJeu("Choisis exactement 4 persos différents.")
        tous = {p["id"]: p for p in self.persos(dossier)}
        membres, notes = [], []
        for c in choisis:
            p = tous.get(c) or {"id": c, "nom": c}
            m = {k: p.get(k) for k in ("id", "nom", "element", "couleur", "rarete", "arme", "image")}
            try:
                d = self.build(c, dossier)
            except ErreurJeu as e:
                m["erreur"] = str(e)
                membres.append(m)
                continue
            b = (d.get("builds") or [{}])[0]
            m.update({
                "role": b.get("nom") or "",
                "autres_roles": [x.get("nom") for x in (d.get("builds") or [])[1:] if x.get("nom")],
                "armes": list(b.get("armes") or []),
                "artefacts": list(b.get("artefacts") or []),
                "stats": [x for x in b.get("stats") or [] if x.get("piece") not in ("Fleur", "Plume")],
                "sous_stats": b.get("sous_stats") or [],
                "aptitudes": b.get("aptitudes") or [],
                "note": b.get("note") or "",
                "element": m.get("element") or d.get("element"),
                "couleur": m.get("couleur") or d.get("couleur"),
                "image": m.get("image") or d.get("image"),
                "nom": m.get("nom") if m.get("nom") != c else d.get("nom") or c,
                "arme_choisie": 0, "artefact_choisi": 0, "adaptations": [],
            })
            membres.append(m)

        # 1) Même arme conseillée en premier pour deux persos : le second prend sa meilleure alternative libre
        prises = {}
        for m in membres:
            armes = m.get("armes") or []
            if not armes:
                continue
            premiere = armes[0]["nom"]
            if premiere in prises:
                libre = next((i for i, a in enumerate(armes) if a["nom"] not in prises), None)
                if libre is not None:
                    m["arme_choisie"] = libre
                    m["adaptations"].append(f"{premiere} est déjà conseillée à {prises[premiere]} : si tu n'en as qu'un "
                                            f"exemplaire, {armes[libre]['nom']} est la meilleure alternative ici.")
                    notes.append(f"{prises[premiere]} et {m['nom']} veulent tous les deux {premiere}.")
            prises.setdefault(armes[m["arme_choisie"]]["nom"], m["nom"])

        # 2) Sets de soutien dont le bonus d'équipe ne se cumule pas : un seul porteur suffit
        portes = {}
        for m in membres:
            options = m.get("artefacts") or []
            if not options:
                continue
            soutien = _set_soutien(options[0])
            if soutien and soutien in portes:
                libre = next((i for i, o in enumerate(options) if _set_soutien(o) not in portes), None)
                if libre is not None:
                    m["artefact_choisi"] = libre
                    m["adaptations"].append(f"{options[0]['ensembles'][0]} est déjà porté par {portes[soutien]} et son bonus "
                                            f"d'équipe ne se cumule pas : {' + '.join(options[libre]['ensembles'])} est plus utile ici.")
                    notes.append(f"Un seul {options[0]['ensembles'][0]} dans l'équipe : il est donné à {portes[soutien]}.")
            s = _set_soutien(options[m["artefact_choisi"]])
            if s:
                portes.setdefault(s, m["nom"])

        return {
            "membres": membres,
            "resonances": _resonances([m.get("element") for m in membres]),
            "notes": notes,
            "source": "Genshin-Builds",
        }

    # ------------------------------------------------------------------ pour le serveur

    def page_donnees(self, chemin, dossier):
        """GET /api/jeux/genshin_builds/page/persos, /page/build/<id> et /page/equipe/<id>,<id>,<id>"""
        if chemin == ["persos"]:
            return {"persos": self.persos(dossier)}
        if len(chemin) == 2 and chemin[0] == "builds_equipe":
            return self.builds_equipe([x for x in urllib.parse.unquote(chemin[1]).split(",") if x], dossier)
        if len(chemin) == 2 and chemin[0] == "equipe":
            return self.completer([x for x in urllib.parse.unquote(chemin[1]).split(",") if x], dossier)
        if len(chemin) == 2 and chemin[0] == "build":
            return self.build(urllib.parse.unquote(chemin[1]), dossier)
        raise ErreurJeu("Demande inconnue.")
