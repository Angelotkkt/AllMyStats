"""Genshin Impact — stats récupérées via Enka.Network (avec ton UID, sans connexion).

Enka lit ta vitrine de profil en jeu. Pour voir les détails des persos
(armes, stats, aptitudes), active dans le jeu :
  Profil > Modifier la vitrine > « Afficher les détails des personnages ».
"""

import json
import os
import subprocess
import time
import urllib.error
import urllib.request

from core import chemins
from core.fenetre import _navigateurs_possibles
from core import connexion_navigateur as navigateur
from core.temps_de_jeu import SuiviJeu

from . import _genshin_hoyolab as hoyolab
from . import _genshin_voeux as voeux
from ._pages import PageEnLigne
from .base import ErreurJeu, Jeu, Stat

URL_API = "https://enka.network/api/uid/{uid}/"
URL_STORE = "https://raw.githubusercontent.com/EnkaNetwork/API-docs/master/store/{fichier}"
URL_ENKA = "https://enka.network"
URL_ICONES = "https://enka.network/ui/{nom}.png"
USER_AGENT = "AllMyStats/1.0 (appli de stats perso)"
DUREE_CACHE_STORE = 7 * 24 * 3600  # on retélécharge les noms des persos chaque semaine

ELEMENTS = {
    "Fire": ("Pyro", "#ef7a35"),
    "Water": ("Hydro", "#4cc2f1"),
    "Wind": ("Anemo", "#74c2a8"),
    "Electric": ("Electro", "#b08fc2"),
    "Grass": ("Dendro", "#a5c83b"),
    "Ice": ("Cryo", "#9fd6e3"),
    "Rock": ("Geo", "#fab632"),
}


def _telecharger_json(url, timeout=20):
    requete = urllib.request.Request(
        url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"}
    )
    with urllib.request.urlopen(requete, timeout=timeout) as reponse:
        return json.loads(reponse.read().decode("utf-8"))


def _lire_json(chemin):
    try:
        with open(chemin, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def _ecrire_json(chemin, data):
    with open(chemin, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)


class GenshinImpact(Jeu):
    id = "genshin"
    nom = "Genshin Impact"
    icone = ""
    couleur = "#5fb3e6"
    stat_vedette = "niveau_aventure"
    connexion_nom = "HoYoLAB"
    cles_connexion = ("ltoken_v2", "ltuid_v2", "ltmid_v2")
    dossier_connexion = "connexion_hoyolab"
    famille = "Genshin Impact"
    ordre = 0
    connexion_aide = ("Connecte-toi avec ton compte HoYoverse (le même que dans Genshin) : AllMyStats récupère "
                      "ton UID, tes stats, ta résine et tes primos tout seul.")

    reglages = [
        {
            "cle": "uid",
            "nom": "UID",
            "aide": "Rempli tout seul quand tu te connectes. Sinon : ton UID (9 ou 10 chiffres), "
                    "en bas à droite de l'écran en jeu.",
        },
        {
            "section": "Cookies HoYoLAB (remplis tout seuls par « Se connecter »)",
            "avance": True,
            "cle": "ltoken_v2",
            "nom": "ltoken_v2",
            "secret": True,
            "optionnel": True,
            "aide": "1. Connecte-toi sur hoyolab.com dans Edge ou Chrome.\n"
                    "2. Appuie sur F12, onglet « Application », puis Cookies > https://www.hoyolab.com.\n"
                    "3. Copie la valeur de ltoken_v2, ltuid_v2 et ltmid_v2 dans les 3 cases.\n"
                    "Garde-les secrets : c'est comme un mot de passe.",
            "lien": "https://www.hoyolab.com",
        },
        {"cle": "ltuid_v2", "nom": "ltuid_v2", "secret": True, "optionnel": True, "avance": True},
        {"cle": "ltmid_v2", "nom": "ltmid_v2", "secret": True, "optionnel": True, "avance": True},
        {
            "section": "Historique des vœux",
            "avance": True,
            "cle": "lien_voeux",
            "nom": "Lien des vœux (seulement si tu ne joues pas sur ce PC)",
            "optionnel": True,
            "aide": "Sur PC, rien à faire : ouvre l'historique des vœux en jeu, AllMyStats le trouve tout seul. "
                    "Sur téléphone ou console, colle ici le lien de l'historique (il expire au bout de 24 h).",
        },
    ]

    P, H, J, V, T = "Profil", "Exploration", "Primogemmes & Mora", "Vœux", "Temps de jeu"
    stats = [
        # --- Profil (Enka.Network, juste avec l'UID) ---
        Stat("niveau_aventure", "Niveau d'aventure", "auto", groupe=P, icone="aventure"),
        Stat("niveau_monde", "Niveau du monde", "auto", groupe=P, icone="monde"),
        Stat("succes", "Succès", "auto", groupe=P, icone="succes"),
        Stat("abysse", "Abysse", "auto", decimales=1, groupe=P, icone="abysse",
             aide="12,3 = étage 12, salle 3"),
        Stat("etoiles_abysse", "Étoiles d'Abysse", "auto", groupe=P, icone="etoiles_abysse", aide="Sur 36"),
        Stat("theatre", "Théâtre Imaginarium", "auto", groupe=P, icone="theatre", aide="Acte atteint"),
        Stat("amities_max", "Amitié max", "auto", groupe=P, icone="amitie", aide="Persos en amitié niveau 10"),
        # --- HoYoLAB ---
        Stat("jours_actifs", "Jours actifs", "auto", groupe=H, icone="jours"),
        Stat("persos_total", "Personnages", "auto", groupe=H, icone="persos"),
        Stat("persos_5", "Persos 5★", "auto", groupe=H, icone="cinq_etoiles"),
        Stat("exploration", "Exploration moyenne", "auto", unite="%", decimales=1, groupe=H, icone="exploration"),
        Stat("coffres", "Coffres ouverts", "auto", groupe=H, icone="coffre"),
        Stat("oculi", "Oculi trouvés", "auto", groupe=H, icone="oculus"),
        Stat("teleporteurs", "Points de téléportation", "auto", groupe=H, icone="teleporteur"),
        Stat("domaines", "Domaines", "auto", groupe=H, icone="domaine"),
        # --- Journal du voyageur ---
        Stat("primos_jour", "Primos gagnées aujourd'hui", "auto", groupe=J, icone="primo_jour"),
        Stat("primos_mois", "Primos gagnées ce mois", "auto", groupe=J, icone="primogemme"),
        Stat("mora_mois", "Mora gagnés ce mois", "auto", groupe=J, icone="mora"),
        # --- Vœux ---
        Stat("voeux_total", "Vœux effectués", "auto", groupe=V, icone="voeu"),
        Stat("primos_depensees", "Primos dépensées en vœux", "auto", groupe=V, icone="primos_depensees",
             aide="Vœux × 160"),
        Stat("cinq_etoiles", "5★ obtenus", "auto", groupe=V, icone="cinq_etoiles"),
        Stat("quatre_etoiles", "4★ obtenus", "auto", groupe=V, icone="quatre_etoiles"),
        Stat("pity_perso", "Pity bannière perso", "auto", groupe=V, icone="pity",
             aide="Vœux depuis ton dernier 5★ (garanti à 90)"),
        Stat("pity_arme", "Pity bannière arme", "auto", groupe=V, icone="arme",
             aide="Vœux depuis ton dernier 5★ (garanti à 80)"),
        Stat("pity_moyen", "Pity moyen d'un 5★", "auto", decimales=1, groupe=V, icone="sablier"),
        # --- Temps de jeu (mesuré sur ce PC tant que AllMyStats tourne) ---
        Stat("temps_total", "Temps de jeu suivi", "auto", unite="h", decimales=1, groupe=T, icone="horloge",
             aide="Mesuré sur ce PC depuis que AllMyStats tourne (mode arrière-plan conseillé)"),
        Stat("temps_7j", "Ces 7 derniers jours", "auto", unite="h", decimales=1, groupe=T, icone="calendrier_semaine"),
        Stat("sessions", "Parties lancées", "auto", groupe=T, icone="manette"),
    ]

    def _suivi(self, dossier):
        return SuiviJeu(os.path.join(dossier, "genshin_temps.json"), ("GenshinImpact.exe", "YuanShen.exe"))

    def surveiller(self, reglages, dossier_donnees):
        suivi = self._suivi(dossier_donnees)
        suivi.verifier()
        return suivi.resume()[0]

    # ------------------------------------------------------------------

    def nom_du_compte(self, reglages):
        """Ton pseudo Genshin (lu sur ton profil), sinon celui de HoYoLAB, et l'UID seulement en dernier."""
        pseudo = (_lire_json(os.path.join(chemins.DONNEES, "genshin_compte.json")) or {}).get("pseudo")
        hoyolab = reglages.get("pseudo_compte") or ""
        if hoyolab.isdigit():   # anciennes versions : l'UID était rangé à la place du pseudo
            hoyolab = ""
        return pseudo or hoyolab or (f"UID {reglages['uid']}" if reglages.get("uid") else "")

    def connexion(self, reglages, dossier_donnees):
        try:
            cookies = navigateur.recuperer_cookies(
                "https://www.hoyolab.com/home",
                os.path.join(dossier_donnees, "connexion_hoyolab"),
                domaine="hoyolab.com",
                est_connecte=lambda c: bool(c.get("ltoken_v2") and c.get("ltuid_v2")),
            )
        except navigateur.ErreurConnexion as e:
            raise ErreurJeu(str(e))
        trouves = {k: cookies[k] for k in hoyolab.NOMS_COOKIES if cookies.get(k)}

        try:
            comptes = hoyolab.comptes_genshin(trouves)
        except hoyolab.ErreurHoyolab as e:
            raise ErreurJeu(f"Connecté, mais impossible de trouver ton compte Genshin : {e}")
        if not comptes:
            raise ErreurJeu("Connecté, mais aucun compte Genshin n'est lié à ce compte HoYoLAB.")
        actuel = (reglages.get("uid") or "").strip()
        compte = next((c for c in comptes if str(c.get("game_role_id")) == actuel), None) \
            or max(comptes, key=lambda c: c.get("level") or 0)
        trouves["uid"] = str(compte.get("game_role_id"))
        hoyolab.tout_rendre_visible(trouves, compte)

        nom = compte.get("nickname") or trouves["uid"]
        trouves["pseudo_compte"] = nom
        return trouves, f"Connecté en tant que {nom} (UID {trouves['uid']})"

    def recuperer(self, reglages, dossier_donnees):
        uid = (reglages.get("uid") or "").strip()
        if not uid.isdigit() or not (9 <= len(uid) <= 10):
            raise ErreurJeu("Mets ton UID Genshin (9 ou 10 chiffres) dans les Réglages.")

        valeurs, sections, etat = {}, [], []
        noms = _Noms(dossier_donnees)

        # 1) Profil public via Enka.Network
        try:
            data, depuis_cache = self._donnees_profil(uid, dossier_donnees)
            info = data.get("playerInfo") or {}

            def garder(cle, valeur):
                if isinstance(valeur, (int, float)):
                    valeurs[cle] = valeur

            garder("niveau_aventure", info.get("level"))
            garder("niveau_monde", info.get("worldLevel"))
            garder("succes", info.get("finishAchievementNum"))
            if info.get("towerFloorIndex"):
                valeurs["abysse"] = info["towerFloorIndex"] + (info.get("towerLevelIndex") or 0) / 10
            garder("etoiles_abysse", info.get("towerStarIndex"))
            garder("theatre", info.get("theaterActIndex"))
            garder("amities_max", info.get("fetterCount"))
            sections += self._construire_details(info, data.get("avatarInfoList"), noms)
            nom_joueur = info.get("nickname") or uid
            if info.get("nickname"):
                _ecrire_json(os.path.join(dossier_donnees, "genshin_compte.json"), {"pseudo": info["nickname"], "uid": uid})
            etat.append({"nom": "Profil", "icone": "aventure", "ok": True,
                         "texte": f"{nom_joueur}" + (" · à jour" if depuis_cache else "")})
        except ErreurJeu as e:
            etat.append({"nom": "Profil", "icone": "aventure", "ok": False, "texte": str(e)})

        # 2) HoYoLAB (si les cookies sont renseignés)
        cookies = hoyolab.lire_cookies(reglages)
        if cookies.get("ltoken_v2") and cookies.get("ltuid_v2"):
            try:
                v, s, avertissements = hoyolab.recuperer(uid, cookies)
                valeurs.update(v)
                sections = s[:1] + sections + s[1:] if s and s[0]["titre"] == "En ce moment" else sections + s
                texte = "connecté" if not avertissements else " · ".join(avertissements)
                etat.append({"nom": "HoYoLAB", "icone": "jours", "ok": not avertissements, "texte": texte})
            except hoyolab.ErreurHoyolab as e:
                etat.append({"nom": "HoYoLAB", "icone": "jours", "ok": False, "texte": str(e)})
        else:
            etat.append({"nom": "HoYoLAB", "icone": "jours", "ok": None,
                         "texte": "pas connecté : clique sur « Se connecter avec HoYoLAB » pour l'exploration, "
                                  "tous tes persos, la résine et les primos"})

        # 3) Historique des vœux
        chemin_voeux = os.path.join(dossier_donnees, "genshin_voeux.json")
        lien = (reglages.get("lien_voeux") or "").strip() or voeux.chercher_lien_dans_le_jeu()
        texte_voeux, ok_voeux = None, True
        if lien:
            try:
                stock, nouveaux = voeux.mettre_a_jour(lien, chemin_voeux)
                texte_voeux = f"{nouveaux} nouveau(x) vœu(x)" if nouveaux else "à jour"
            except voeux.ErreurVoeux as e:
                texte_voeux, ok_voeux = str(e), False
        stock = voeux.charger_stock(chemin_voeux)
        if stock:
            v, s = voeux.analyser(stock, uid, noms.image_par_nom)
            valeurs.update(v)
            if s:
                sections += s
            texte_voeux = texte_voeux or "ouvre l'historique des vœux en jeu pour avoir les nouveaux"
        elif not lien:
            ok_voeux = None
            texte_voeux = "ouvre l'historique des vœux en jeu (sur ce PC), puis actualise"
        etat.append({"nom": "Vœux", "icone": "voeu", "ok": ok_voeux, "texte": texte_voeux})

        # 4) Temps de jeu
        v, s = self._suivi(dossier_donnees).resume()
        if v:
            valeurs.update(v)
            sections += s
            etat.append({"nom": "Temps de jeu", "icone": "horloge", "ok": True,
                         "texte": f"{v['sessions']} partie(s) · {v['temps_total']} h".replace(".", ",")})
        else:
            etat.append({"nom": "Temps de jeu", "icone": "horloge", "ok": None,
                         "texte": "lance Genshin sur ce PC avec AllMyStats allumé (mode arrière-plan conseillé)"})

        if not valeurs:
            raise ErreurJeu(" / ".join(f"{e['nom']} : {e['texte']}" for e in etat if e["ok"] is False)
                            or "Aucune donnée récupérée.")

        reussies = [e["nom"] for e in etat if e["ok"]]
        message = "Récupéré : " + ", ".join(reussies) if reussies else "Rien de nouveau"
        return valeurs, {"etat": etat, "sections": sections}, message

    # ------------------------------------------------------------------

    def _donnees_profil(self, uid, dossier):
        """Appelle Enka en respectant son cache (champ ttl)."""
        chemin_cache = os.path.join(dossier, "genshin_cache_profil.json")
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
        except (urllib.error.URLError, TimeoutError, OSError):
            raise ErreurJeu("Impossible de joindre Enka.Network. Vérifie ta connexion internet.")

        ttl = data.get("ttl") or 60
        _ecrire_json(chemin_cache, {"uid": uid, "expire": time.time() + ttl, "data": data})
        return data, False

    def _construire_details(self, info, avatars, noms):
        sections = []

        profil = [
            ["Pseudo", info.get("nickname", "?"), "profil"],
            ["Signature", info.get("signature") or "—", "signature"],
        ]
        if info.get("towerFloorIndex"):
            texte = f"Étage {info['towerFloorIndex']} – salle {info.get('towerLevelIndex', '?')}"
            if info.get("towerStarIndex") is not None:
                texte += f" · {info['towerStarIndex']}★"
            profil.append(["Abysse", texte, "abysse"])
        if info.get("theaterActIndex"):
            profil.append(["Théâtre Imaginarium", f"Acte {info['theaterActIndex']}", "theatre"])
        sections.append({"titre": "Profil", "icone": "profil", "lignes": profil})

        cartes = []
        if avatars:
            for av in avatars:
                cartes.append(self._carte_perso(av, noms))
            note = None
        else:
            for av in info.get("showAvatarInfoList") or []:
                perso = noms.perso(av.get("avatarId"))
                cartes.append(
                    {
                        "titre": perso["nom"],
                        "sous_titre": f"Niv. {av.get('level', '?')}",
                        "image": perso["icone"],
                        "couleur": perso["couleur"],
                        "badges": [perso["element"]] if perso["element"] else [],
                        "lignes": [],
                    }
                )
            note = ("Pour voir armes, stats et aptitudes : en jeu, Profil > Modifier la vitrine > "
                    "active « Afficher les détails des personnages ».")

        sections.append({"titre": "Personnages de la vitrine", "icone": "vitrine", "cartes": cartes, "note": note})
        return sections

    def _carte_perso(self, av, noms):
        perso = noms.perso(av.get("avatarId"), av.get("skillDepotId"))
        props = {str(p.get("type")): p.get("val") for p in av.get("propMap", {}).values()}
        niveau = props.get("4001", "?")
        constellation = len(av.get("talentIdList") or [])
        combat = {str(k): v for k, v in (av.get("fightPropMap") or {}).items()}
        amitie = (av.get("fetterInfo") or {}).get("expLevel")

        def nombre(cle):
            return round(combat.get(cle, 0))

        def pourcent(cle):
            return f"{combat.get(cle, 0) * 100:.1f} %".replace(".", ",")

        lignes = [
            ["PV max", f"{nombre('2000'):,}".replace(",", " ")],
            ["ATQ", f"{nombre('2001'):,}".replace(",", " ")],
            ["DÉF", f"{nombre('2002'):,}".replace(",", " ")],
            ["Maîtrise élém.", nombre("28")],
            ["Taux CRIT", pourcent("20")],
            ["DGT CRIT", pourcent("22")],
            ["Recharge", pourcent("23")],
        ]

        # Aptitudes (attaque normale / compétence / déchaînement)
        niveaux = av.get("skillLevelMap") or {}
        niveaux = {str(k): v for k, v in niveaux.items()}
        ordre = perso.get("ordre_aptitudes") or list(niveaux.keys())
        apt = [str(niveaux[str(i)]) for i in ordre if str(i) in niveaux]
        if apt:
            lignes.insert(0, ["Aptitudes", " / ".join(apt)])

        # Arme et artefacts
        nb_artefacts = 0
        for equip in av.get("equipList") or []:
            if "weapon" in equip:
                flat = equip.get("flat") or {}
                nom_arme = noms.texte(flat.get("nameTextMapHash")) or "Arme"
                arme = equip["weapon"]
                affixes = list((arme.get("affixMap") or {}).values())
                raffinement = 1 + (affixes[0] if affixes else 0)
                etoiles = flat.get("rankLevel")
                texte = f"{nom_arme} · Niv. {arme.get('level', '?')} · R{raffinement}"
                if etoiles:
                    texte += f" · {etoiles}★"
                lignes.insert(0, ["Arme", texte])
            elif "reliquary" in equip:
                nb_artefacts += 1
        lignes.append(["Artefacts équipés", f"{nb_artefacts}/5"])

        badges = []
        if perso["element"]:
            badges.append(perso["element"])
        badges.append(f"C{constellation}")
        if amitie:
            badges.append(f"Amitié {amitie}")

        return {
            "titre": perso["nom"],
            "sous_titre": f"Niv. {niveau} · C{constellation}",
            "image": perso["icone"],
            "couleur": perso["couleur"],
            "badges": badges,
            "lignes": lignes,
        }


class _Noms:
    """Traduit les identifiants d'Enka en noms (FR si possible), avec un cache local."""

    def __init__(self, dossier):
        self._dossier, self._rafraichi = dossier, False
        self._charger(dossier)

    def _charger(self, dossier, age_max=None):
        self._age_max = age_max
        # Les fichiers « gi/ » d'Enka sont ceux qui suivent les nouveaux persos (les anciens ne bougent plus)
        self.persos = (self._store(dossier, "gi/avatars.json", "genshin_persos_v2.json")
                       or self._store(dossier, "characters.json", "genshin_persos.json") or {})
        self.armes = self._store(dossier, "gi/weapons.json", "genshin_armes.json") or {}
        loc = (self._store(dossier, "gi/locs.json", "genshin_textes_v2.json", garder_langues=("fr", "en"))
               or self._store(dossier, "loc.json", "genshin_textes.json", garder_langues=("fr", "en")) or {})
        self.textes_fr = loc.get("fr") or {}
        self.textes_en = loc.get("en") or {}

    @staticmethod
    def _url(chemin_icone):
        """« /ui/UI_X.png » (nouveau format) ou « UI_X » (ancien) -> adresse complète de l'image."""
        if not chemin_icone:
            return None
        if chemin_icone.startswith("/"):
            return URL_ENKA + chemin_icone
        return URL_ICONES.format(nom=chemin_icone)

    def _store(self, dossier, fichier, nom_local, garder_langues=None):
        chemin = os.path.join(dossier, nom_local)
        existe = os.path.exists(chemin)
        age_max = DUREE_CACHE_STORE if getattr(self, "_age_max", None) is None else self._age_max
        recent = existe and time.time() - os.path.getmtime(chemin) < age_max
        if recent:
            return _lire_json(chemin)
        try:
            data = _telecharger_json(URL_STORE.format(fichier=fichier), timeout=60)
            if garder_langues:
                data = {k: v for k, v in data.items() if k in garder_langues}
            _ecrire_json(chemin, data)
            return data
        except Exception:
            # Pas grave : on garde l'ancienne version si on l'a
            return _lire_json(chemin) if existe else None

    def image_par_nom(self, nom):
        """Retrouve l'icône d'un perso OU d'une arme à partir de son nom (pour l'historique des vœux)."""
        if not hasattr(self, "_par_nom"):
            self._par_nom = {}
            for infos in self.persos.values():
                n = self.texte(infos.get("NameTextMapHash"))
                if n and infos.get("SideIconName"):
                    self._par_nom.setdefault(n.lower(), self._url(infos["SideIconName"].replace("_Side", "")))
            for infos in self.armes.values():
                n = self.texte(infos.get("NameTextMapHash"))
                if n and infos.get("Icon"):
                    self._par_nom.setdefault(n.lower(), self._url(infos["Icon"]))
        return self._par_nom.get((nom or "").lower())

    def texte(self, hash_texte):
        if hash_texte is None:
            return None
        cle = str(hash_texte)
        return self.textes_fr.get(cle) or self.textes_en.get(cle)

    def perso(self, avatar_id, skill_depot_id=None):
        infos = None
        if skill_depot_id is not None:
            infos = self.persos.get(f"{avatar_id}-{skill_depot_id}")
        infos = infos or self.persos.get(str(avatar_id)) or {}
        if not infos and not self._rafraichi:
            # Perso tout nouveau : on reprend tout de suite la dernière liste d'Enka (au plus une fois par heure)
            self._rafraichi = True
            self._charger(self._dossier, age_max=3600)
            if hasattr(self, "_par_nom"):
                del self._par_nom
            return self.perso(avatar_id, skill_depot_id)

        nom = self.texte(infos.get("NameTextMapHash")) or f"Perso #{avatar_id}"
        element, couleur = ELEMENTS.get(infos.get("Element"), (None, "#8a8fa8"))
        icone_side = infos.get("SideIconName")
        icone = self._url(icone_side.replace("_Side", "")) if icone_side else None
        return {
            "nom": nom,
            "element": element,
            "couleur": couleur,
            "icone": icone,
            "ordre_aptitudes": infos.get("SkillOrder"),
        }


class CarteGenshin(PageEnLigne):
    """Sous-catégorie « Interactive Map » : la carte officielle de Teyvat (HoYoLAB), toujours à jour,
    ouverte dans sa propre fenêtre. Ses repères restent dans cette fenêtre (connexion HoYoLAB comprise)."""
    id = "genshin_carte"
    nom = "Interactive Map"
    icone = "carte_teyvat"
    couleur = "#5B8DEF"
    famille = "Genshin Impact"
    ordre = 1
    page = "carte"
    stats = []
    texte_connexion = "Carte ouverte avec ton compte : connecte-toi une fois, tes repères y seront gardés"
    cartes_en_ligne = [
        {"id": "hoyolab", "nom": "Carte officielle (HoYoLAB)",
         "url": "https://act.hoyolab.com/ys/app/interactive-map/index.html?lang=fr-fr",
         "aide": "La carte de HoYoverse : coffres, oculi, matériaux, ennemis, quêtes, toutes les régions. "
                 "Connecte-toi directement dedans pour cocher ce que tu as trouvé, comme sur le site.",
         "collee": True},
        {"id": "appsample", "nom": "Carte Appsample",
         "url": "https://genshin-impact-map.appsample.com/",
         "aide": "Une autre carte très complète, faite par la communauté."},
    ]

