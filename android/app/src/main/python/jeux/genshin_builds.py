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

    # ------------------------------------------------------------------ pour le serveur

    def page_donnees(self, chemin, dossier):
        """GET /api/jeux/genshin_builds/page/persos  et  /page/build/<id>"""
        if chemin == ["persos"]:
            return {"persos": self.persos(dossier)}
        if len(chemin) == 2 and chemin[0] == "build":
            return self.build(urllib.parse.unquote(chemin[1]), dossier)
        raise ErreurJeu("Demande inconnue.")
