"""Honkai: Star Rail — stats récupérées via Enka.Network (avec ton UID, sans connexion).

Enka lit ton profil public en jeu (Menu > Profil). Pour voir le détail des persos (cônes de lumière, reliques),
mets-les dans ta vitrine : Profil > Modifier la vitrine.
"""

import json
import os
import time
import urllib.error
import urllib.request

from core.temps_de_jeu import SuiviJeu

from .base import ErreurJeu, Jeu, Stat

URL_API = "https://enka.network/api/hsr/uid/{uid}/"
URL_STORE = "https://raw.githubusercontent.com/EnkaNetwork/API-docs/master/store/hsr/{fichier}"
URL_ENKA = "https://enka.network"
USER_AGENT = "AllMyStats/1.0 (appli de stats perso)"
DUREE_CACHE_STORE = 7 * 24 * 3600

ELEMENTS = {
    "Physical": ("Physique", "#c9c9d6"),
    "Fire": ("Feu", "#ef7a35"),
    "Ice": ("Glace", "#9fd6e3"),
    "Thunder": ("Foudre", "#b08fc2"),
    "Wind": ("Vent", "#74c2a8"),
    "Quantum": ("Quantique", "#8a7cf0"),
    "Imaginary": ("Imaginaire", "#f4d35e"),
}
VOIES = {
    "Warrior": "Destruction", "Rogue": "Chasse", "Mage": "Érudition", "Shaman": "Harmonie",
    "Warlock": "Nihilité", "Knight": "Préservation", "Priest": "Abondance", "Memory": "Souvenir",
}


def _telecharger_json(url, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def _lire_json(chemin):
    try:
        with open(chemin, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def _ecrire_json(chemin, data):
    with open(chemin, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)


class _Noms:
    """Noms français, images et éléments des persos et cônes, d'après les fichiers publics d'Enka
    (retéléchargés une fois par semaine, et gardés si Internet est coupé)."""

    def __init__(self, dossier):
        self.dossier = dossier
        self._donnees = {}

    def _store(self, fichier, nom_local, filtre=None):
        if fichier in self._donnees:
            return self._donnees[fichier]
        chemin = os.path.join(self.dossier, nom_local)
        existe = os.path.exists(chemin)
        data = None
        if existe and time.time() - os.path.getmtime(chemin) < DUREE_CACHE_STORE:
            data = _lire_json(chemin)
        if data is None:
            try:
                data = _telecharger_json(URL_STORE.format(fichier=fichier), timeout=60)
                if filtre:
                    data = filtre(data)
                _ecrire_json(chemin, data)
            except Exception:
                data = _lire_json(chemin) if existe else None
        self._donnees[fichier] = data or {}
        return self._donnees[fichier]

    def _textes(self):
        # Seulement le français et l'anglais (le fichier complet a 10 langues)
        return self._store("hsr.json", "starrail_textes.json",
                           lambda d: {k: v for k, v in d.items() if k in ("fr", "en")})

    def texte(self, hachage):
        t = self._textes()
        return (t.get("fr") or {}).get(str(hachage)) or (t.get("en") or {}).get(str(hachage))

    @staticmethod
    def _url(chemin):
        return URL_ENKA + chemin if chemin and chemin.startswith("/") else None

    def perso(self, id_perso):
        avatars = self._store("avatars.json", "starrail_persos.json", lambda d: {
            k: {c: v.get(c) for c in ("AvatarName", "Rarity", "Element", "AvatarBaseType", "AvatarSideIconPath")}
            for k, v in d.items()})
        p = avatars.get(str(id_perso)) or {}
        element = ELEMENTS.get(p.get("Element") or "")
        nom = self.texte((p.get("AvatarName") or {}).get("Hash")) or f"Perso {id_perso}"
        if str(id_perso).startswith("80"):   # le Pionnier / la Pionnière : nom choisi par le joueur
            nom = "Pionnier·ère"
        return {"nom": nom, "image": self._url(p.get("AvatarSideIconPath")), "rarete": p.get("Rarity"),
                "element": element[0] if element else None, "couleur": element[1] if element else None,
                "voie": VOIES.get(p.get("AvatarBaseType") or "")}

    def cone(self, id_cone):
        cones = self._store("weapons.json", "starrail_cones.json", lambda d: {
            k: {c: v.get(c) for c in ("EquipmentName", "Rarity", "ImagePath")} for k, v in d.items()})
        c = cones.get(str(id_cone)) or {}
        return {"nom": self.texte((c.get("EquipmentName") or {}).get("Hash")) or "Cône de lumière",
                "rarete": c.get("Rarity"), "image": self._url(c.get("ImagePath"))}

    def photo(self, id_icone):
        pfps = self._store("pfps.json", "starrail_photos.json")
        e = pfps.get(str(id_icone)) or {}
        return self._url(e.get("Icon") if isinstance(e, dict) else None)


class HonkaiStarRail(Jeu):
    id = "starrail"
    nom = "Honkai: Star Rail"
    icone = "jeu_starrail"
    couleur = "#8C7CF0"
    stat_vedette = "niveau_pionnier"
    connexion_aide = ("Mets ton UID (en bas à gauche de l'écran en jeu) dans les Réglages : AllMyStats lit ton "
                      "profil public, sans connexion.")

    reglages = [
        {"cle": "uid", "nom": "UID",
         "aide": "Ton UID Honkai: Star Rail (9 ou 10 chiffres), en bas à gauche de l'écran en jeu, ou dans Menu > Profil."},
    ]

    P, C, T = "Profil", "Collection", "Temps de jeu"
    stats = [
        Stat("niveau_pionnier", "Niveau de Pionnier", "auto", groupe=P, icone="aventure"),
        Stat("equilibre", "Niveau d'équilibre", "auto", groupe=P, icone="monde"),
        Stat("succes", "Succès", "auto", groupe=P, icone="succes"),
        Stat("univers_simule", "Univers simulé", "auto", groupe=P, icone="exploration",
             aide="Le monde le plus haut terminé"),
        Stat("memoire_chaos", "Mémoire du Chaos", "auto", groupe=P, icone="abysse", aide="Étape la plus haute"),
        Stat("persos_total", "Personnages", "auto", groupe=C, icone="persos"),
        Stat("cones", "Cônes de lumière", "auto", groupe=C, icone="arme"),
        Stat("reliques", "Reliques", "auto", groupe=C, icone="artefact"),
        Stat("temps_total", "Temps de jeu suivi", "auto", unite="h", decimales=1, groupe=T, icone="horloge",
             aide="Mesuré sur ce PC depuis que AllMyStats tourne (mode arrière-plan conseillé)"),
        Stat("temps_7j", "Ces 7 derniers jours", "auto", unite="h", decimales=1, groupe=T, icone="calendrier_semaine"),
        Stat("sessions", "Parties lancées", "auto", groupe=T, icone="manette"),
    ]

    def _suivi(self, dossier):
        return SuiviJeu(os.path.join(dossier, "starrail_temps.json"), ("StarRail.exe",))

    def surveiller(self, reglages, dossier_donnees):
        suivi = self._suivi(dossier_donnees)
        suivi.verifier()
        return suivi.resume()[0]

    def nom_du_compte(self, reglages):
        pseudo = (_lire_json(os.path.join(self._dossier_compte(), "starrail_compte.json")) or {}).get("pseudo")
        return pseudo or (f"UID {reglages['uid']}" if reglages.get("uid") else "")

    @staticmethod
    def _dossier_compte():
        from core import chemins
        return chemins.DONNEES

    def recuperer(self, reglages, dossier_donnees):
        uid = (reglages.get("uid") or "").strip()
        if not uid.isdigit() or not (9 <= len(uid) <= 10):
            raise ErreurJeu("Mets ton UID Honkai: Star Rail (9 ou 10 chiffres) dans les Réglages.")
        valeurs, sections, etat, images = {}, [], [], {}
        noms = _Noms(dossier_donnees)

        # 1) Profil public via Enka.Network
        try:
            data, depuis_cache = self._donnees_profil(uid, dossier_donnees)
            info = data.get("detailInfo") or {}
            record = info.get("recordInfo") or {}
            defi = record.get("challengeInfo") or {}

            def garder(cle, valeur):
                if isinstance(valeur, (int, float)) and not isinstance(valeur, bool):
                    valeurs[cle] = valeur

            garder("niveau_pionnier", info.get("level"))
            garder("equilibre", info.get("worldLevel"))
            garder("succes", record.get("achievementCount"))
            garder("persos_total", record.get("avatarCount"))
            garder("cones", record.get("equipmentCount"))
            garder("reliques", record.get("relicCount"))
            if record.get("maxRogueChallengeScore"):
                garder("univers_simule", record.get("maxRogueChallengeScore"))
            if defi.get("scheduleMaxLevel"):
                garder("memoire_chaos", defi.get("scheduleMaxLevel"))
            sections += self._details(info, record, noms)
            try:
                photo = noms.photo(info.get("headIcon"))
                if photo:
                    images["avatar"] = photo
            except Exception:
                pass
            if info.get("nickname"):
                _ecrire_json(os.path.join(dossier_donnees, "starrail_compte.json"), {"pseudo": info["nickname"], "uid": uid})
            etat.append({"nom": "Profil", "icone": "aventure", "ok": True,
                         "texte": f"{info.get('nickname') or uid}" + (" · à jour" if depuis_cache else "")})
        except ErreurJeu as e:
            etat.append({"nom": "Profil", "icone": "aventure", "ok": False, "texte": str(e)})

        # 2) Temps de jeu
        v, s = self._suivi(dossier_donnees).resume()
        if v:
            valeurs.update(v)
            sections += s
            etat.append({"nom": "Temps de jeu", "icone": "horloge", "ok": True,
                         "texte": f"{v['sessions']} partie(s) · {v['temps_total']} h".replace(".", ",")})
        else:
            etat.append({"nom": "Temps de jeu", "icone": "horloge", "ok": None,
                         "texte": "lance Star Rail sur ce PC avec AllMyStats allumé (mode arrière-plan conseillé)"})

        if not valeurs:
            raise ErreurJeu(" / ".join(f"{e['nom']} : {e['texte']}" for e in etat if e["ok"] is False)
                            or "Aucune donnée récupérée.")
        reussies = [e["nom"] for e in etat if e["ok"]]
        message = "Récupéré : " + ", ".join(reussies) if reussies else "Rien de nouveau"
        return valeurs, {"etat": etat, "sections": sections, **images}, message

    def _donnees_profil(self, uid, dossier):
        """Appelle Enka en respectant son cache (champ ttl)."""
        chemin_cache = os.path.join(dossier, "starrail_cache_profil.json")
        cache = _lire_json(chemin_cache) or {}
        if cache.get("uid") == uid and cache.get("expire", 0) > time.time():
            return cache["data"], True
        try:
            data = _telecharger_json(URL_API.format(uid=uid))
        except urllib.error.HTTPError as e:
            messages = {
                400: "UID au mauvais format.",
                404: "Aucun joueur trouvé avec cet UID.",
                424: "Le jeu est en maintenance ou vient d'être mis à jour. Réessaie plus tard.",
                429: "Trop de demandes d'un coup. Attends un peu puis réessaie.",
                500: "Le serveur d'Enka a un souci. Réessaie plus tard.",
                503: "Enka est indisponible pour le moment. Réessaie plus tard.",
            }
            raise ErreurJeu(messages.get(e.code, f"Erreur Enka (code {e.code})."))
        except (urllib.error.URLError, TimeoutError, OSError, ValueError):
            raise ErreurJeu("Impossible de joindre Enka.Network. Vérifie ta connexion internet.")
        ttl = data.get("ttl") or 60
        _ecrire_json(chemin_cache, {"uid": uid, "expire": time.time() + ttl, "data": data})
        return data, False

    def _details(self, info, record, noms):
        profil = [["Pseudo", info.get("nickname") or "?", "profil"],
                  ["Signature", info.get("signature") or "—", "signature"]]
        if info.get("friendCount") is not None:
            profil.append(["Amis en jeu", info["friendCount"], "amis"])
        if record.get("musicCount"):
            profil.append(["Musiques collectionnées", record["musicCount"], "son"])
        if record.get("bookCount"):
            profil.append(["Livres collectionnés", record["bookCount"], "signature"])
        sections = [{"titre": "Profil", "icone": "profil", "lignes": profil}]

        cartes = []
        for av in info.get("avatarDetailList") or []:
            p = noms.perso(av.get("avatarId"))
            lignes = []
            eq = av.get("equipment") or {}
            if eq.get("tid"):
                c = noms.cone(eq["tid"])
                lignes.append(["Cône de lumière", f"{c['nom']} · niv. {eq.get('level', '?')} · S{eq.get('rank') or 1}"])
            if av.get("relicList"):
                lignes.append(["Reliques", f"{len(av['relicList'])} équipée(s)"])
            if p["voie"]:
                lignes.append(["Voie", p["voie"]])
            badges = [x for x in (p["element"], f"E{av.get('rank') or 0}") if x]
            cartes.append({"titre": p["nom"], "sous_titre": f"Niv. {av.get('level', '?')}", "image": p["image"],
                           "couleur": p["couleur"], "badges": badges, "lignes": lignes})
        note = None if cartes else ("Pour voir tes persos ici : en jeu, Menu > Profil > Modifier la vitrine, "
                                    "et ajoutes-y des personnages.")
        sections.append({"titre": "Personnages de la vitrine", "icone": "vitrine", "cartes": cartes, "note": note})
        return sections
