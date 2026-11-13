"""Call of Duty : BO6, BO7, Cold War, MW4, Warzone, Warzone MW4, MW3 (2023), MW2 (2022).

Les 8 jeux sont rangés ensemble dans la barre de gauche (famille « Call of Duty ») et partagent
les mêmes réglages et la même connexion Activision. Voir _cod_commun.py pour le fonctionnement.
"""

import os
import time

from core import connexion_navigateur as navigateur
from core import diagnostic_ecran as diag
from core import windows

from . import _cod_commun as cod
from . import _cod_donnees as donnees_activision
from .base import ErreurJeu, Jeu, Stat

FAMILLE = "Call of Duty"


def stats_multijoueur(zombies=False):
    M, Z, T = "Multijoueur", "Zombies", "Temps de jeu"
    liste = [
        Stat("kd", "Ratio É/M (K/D)", "auto", decimales=2, groupe=M, icone="cod_kd", modifiable=True),
        Stat("niveau", "Niveau", "auto", groupe=M, icone="cod_niveau", modifiable=True),
        Stat("prestige", "Prestige", "auto", groupe=M, icone="cod_prestige", modifiable=True),
        Stat("eliminations", "Éliminations", "auto", groupe=M, icone="cod_elimination", modifiable=True),
        Stat("morts", "Morts", "auto", groupe=M, icone="cod_mort", modifiable=True),
        Stat("victoires", "Victoires", "auto", groupe=M, icone="cod_victoire", modifiable=True),
        Stat("defaites", "Défaites", "auto", groupe=M, icone="cod_defaite", modifiable=True),
        Stat("ratio_victoires", "Victoires (%)", "auto", unite="%", decimales=1, groupe=M, icone="cod_ratio"),
        Stat("parties", "Parties jouées", "auto", groupe=M, icone="manette", modifiable=True),
        Stat("precision", "Précision", "auto", unite="%", decimales=1, groupe=M, icone="cod_precision", modifiable=True),
        Stat("score_min", "Score / minute", "auto", groupe=M, icone="cod_score", modifiable=True),
    ]
    if zombies:
        liste += [
            Stat("zm_manche_max", "Manche la plus haute", "auto", groupe=Z, icone="cod_manche", modifiable=True),
            Stat("zm_zombies", "Zombies éliminés", "auto", groupe=Z, icone="cod_zombie", modifiable=True),
            Stat("zm_parties", "Parties Zombies", "auto", groupe=Z, icone="manette", modifiable=True),
        ]
    return liste + stats_temps(T)


def stats_warzone():
    W, T = "Battle royale", "Temps de jeu"
    return [
        Stat("victoires", "Victoires", "auto", groupe=W, icone="cod_victoire", modifiable=True),
        Stat("top5", "Top 5", "auto", groupe=W, icone="cod_podium", modifiable=True),
        Stat("top10", "Top 10", "auto", groupe=W, icone="cod_podium", modifiable=True),
        Stat("kd", "Ratio É/M (K/D)", "auto", decimales=2, groupe=W, icone="cod_kd", modifiable=True),
        Stat("eliminations", "Éliminations", "auto", groupe=W, icone="cod_elimination", modifiable=True),
        Stat("morts", "Morts", "auto", groupe=W, icone="cod_mort", modifiable=True),
        Stat("parties", "Parties jouées", "auto", groupe=W, icone="cod_parachute", modifiable=True),
        Stat("niveau", "Niveau", "auto", groupe=W, icone="cod_niveau", modifiable=True),
    ] + stats_temps(T)


def stats_temps(T):
    return [
        Stat("temps_jeu", "Temps de jeu (en jeu)", "auto", unite="h", decimales=1, groupe=T, icone="horloge",
             modifiable=True, aide="Lu dans ton Combat Record"),
        Stat("temps_suivi", "Temps suivi par AMS", "auto", unite="h", decimales=1, groupe=T, icone="historique",
             aide="Mesuré sur ce PC quand le jeu est lancé"),
        Stat("temps_7j", "Ces 7 derniers jours", "auto", unite="h", decimales=1, groupe=T, icone="calendrier_semaine"),
        Stat("sessions", "Sessions", "auto", groupe=T, icone="cod_session"),
    ]


class CallOfDuty(Jeu):
    """Base commune : chaque jeu ne change que son nom, ses couleurs et ses stats."""
    famille = FAMILLE
    id_reglages = "callofduty"
    connexion_nom = "Activision"
    connexion_aide = ("Pour tous les Call of Duty, sans lecture d'écran : importe ton fichier « Mes données » "
                      "d'Activision (juste en dessous). En plus, la connexion Activision donne les stats officielles "
                      "à jour de Cold War et MW2.")
    connexion_consigne = "Clique sur CONNEXION en haut à droite du site, puis connecte-toi avec ton compte Activision."
    cles_connexion = ("activision_connecte",)
    dossier_connexion = cod.DOSSIER_CONNEXION
    stat_vedette = "kd"
    code_activision = None   # "cw" ou "mw2" si Activision partage encore les stats de ce jeu
    zombies = False

    reglages = [
        {
            "cle": "pseudo_activision",
            "nom": "Pseudo Activision",
            "optionnel": True,
            "aide": "Rempli tout seul quand tu te connectes (ex : Pseudo#1234567).",
        },
    ]

    def nom_du_compte(self, reglages):
        return reglages.get("pseudo_activision", "")

    def est_connecte(self, reglages):
        return bool(reglages.get("activision_connecte"))

    # ------------------------------------------------------------------ connexion

    def connexion(self, reglages, dossier):
        try:
            cookies = navigateur.recuperer_cookies(
                cod.URL_CONNEXION,
                os.path.join(dossier, cod.DOSSIER_CONNEXION),
                domaine=cod.DOMAINES,
                est_connecte=lambda c: bool(c.get("ACT_SSO_COOKIE")),
            )
        except navigateur.ErreurConnexion as e:
            raise ErreurJeu(str(e))
        trouves = {"activision_connecte": "oui"}
        try:  # le pseudo est un bonus : la connexion compte même si Activision ne le donne pas
            ids = cod.identites(cookies)
            if ids:
                trouves["pseudo_activision"] = ids[0].get("username", "")
        except Exception:
            pass
        nom = trouves.get("pseudo_activision") or "ton compte"
        return trouves, f"Connecté à Activision : {nom}"

    # ------------------------------------------------------------------ surveillance (chaque minute)

    import_donnees = {
        "titre": "Importer mes données Activision",
        "texte": "Toutes tes parties depuis Vanguard (2021), sans lecture d'écran : K/D, victoires, précision… "
                 "pour chaque Call of Duty d'un coup.",
        "accept": ".html,.htm,.zip",
        "lien": "https://support.activision.com/privacy",
        "etapes": [
            "Ouvre la page Confidentialité d'Activision (bouton ci-dessous) et choisis « Soumettre une demande ».",
            "Va sur le portail de confidentialité, puis « Accéder à mes données personnelles ».",
            "Connecte ton compte Activision et ton compte de jeu (Steam, Battle.net, Xbox…), puis envoie la demande.",
            "Activision t'envoie un e-mail en général sous 1 à 2 jours, avec un fichier HTML : glisse-le ici.",
        ],
        "prive": "Ce fichier contient aussi tes adresses IP : ne le partage avec personne. AllMyStats le lit sans "
                 "l'enregistrer et ne garde que tes totaux.",
    }

    def importer_donnees(self, contenu, nom, dossier):
        resultats, rapport = donnees_activision.lire(contenu, nom)
        if resultats:
            cod.garder_import(resultats, dossier)
        return {t: {k: v for k, v in r.items() if not k.startswith("_")} for t, r in resultats.items()}, rapport

    lit_ecran = True
    consigne_ecran = "Va sur Call of Duty et ouvre ton Combat Record (Carrière > Stats > Combat Record)."

    def tester_ecran(self, reglages, dossier):
        resultat = {"etapes": [], "lignes": [], "valeurs": {}, "cible": self.id,
                    "dernier_essai": diag.resume_essai(cod.DERNIER_ESSAI or None)}
        etapes = resultat["etapes"]
        lances = cod.programmes_cod()
        if os.name == "nt" and not lances:
            etapes.append(diag.etape("erreur", "Call of Duty lancé",
                                     "AllMyStats ne trouve aucun Call of Duty ouvert. Lance le jeu, puis refais le test. "
                                     "Si le jeu est bien ouvert, son programme porte un nom que AllMyStats ne connaît "
                                     "pas encore (regarde-le dans le Gestionnaire des tâches > Détails)."))
            return resultat
        if lances:
            etapes.append(diag.etape("ok", "Call of Duty lancé", "Programme : " + ", ".join(sorted(lances))))
        r = windows.lire_ecran_complet(cod.noms_sans_exe(lances), garder_essai=False)
        etapes_capture, lu = diag.etapes_capture(r, "Call of Duty")
        etapes += etapes_capture
        resultat["lignes"] = r["lignes"][:40]
        if lu:
            titre, mode, valeurs = cod.ranger_lecture(r, r["lignes"], reglages, dossier)
            if valeurs:
                resultat["cible"] = titre
                resultat["valeurs"] = cod.valeurs_ecran(titre, dossier)[0]
                etapes.append(diag.etape("ok", "Stats reconnues", ""))
            else:
                etapes.append(diag.etape("alerte", "Stats reconnues",
                                         "Le texte a bien été lu, mais ce n'est pas un Combat Record. Ouvre "
                                         "Carrière > Stats > Combat Record (ou Barracks > Combat Record selon le jeu), "
                                         "laisse-le affiché, puis refais le test."))
        return resultat

    def surveiller(self, reglages, dossier):
        cod.surveiller_famille(reglages, dossier)
        valeurs, _ = cod.valeurs_ecran(self.id, dossier)
        return {**valeurs, **cod.valeurs_temps(self.id, dossier)}

    # ------------------------------------------------------------------ actualisation

    def recuperer(self, reglages, dossier):
        valeurs, etat, sections = {}, [], []

        # 0) Fichier « Mes données » d'Activision  /  1) Combat Record lu sur l'écran
        #    (les deux sont des photos à un instant : la plus récente passe devant)
        importe, quand_import, brut_import = cod.valeurs_import(self.id, dossier)
        ecran, quand = cod.valeurs_ecran(self.id, dossier)
        sources = sorted([(quand_import or 0, importe), (quand or 0, ecran)], key=lambda x: x[0])
        for _, v in sources:
            valeurs.update(v)
        if importe:
            derniere = time.strftime("%d/%m/%Y", time.localtime(quand_import)) if quand_import else ""
            etat.append({"nom": "Données Activision", "icone": "telecharger", "ok": True,
                         "texte": f"{brut_import.get('_parties', 0)} partie(s), jusqu'au {derniere}"})
        else:
            etat.append({"nom": "Données Activision", "icone": "telecharger", "ok": None,
                         "texte": "importe le fichier « Mes données » d'Activision (sans lecture d'écran)"})
        if ecran:
            depuis = time.strftime("%d/%m à %H:%M", time.localtime(quand)) if quand else ""
            etat.append({"nom": "Combat Record", "icone": "cod_dossier", "ok": True, "texte": f"lu à l'écran le {depuis}"})

        # 2) Compte Activision (seulement pour les jeux qu'Activision partage encore)
        if self.code_activision:
            if reglages.get("activision_connecte"):
                try:
                    cookies = cod.lire_session(dossier)
                    v, ident = cod.stats_activision(self.code_activision, "mp", cookies)
                    if self.zombies:
                        try:
                            v.update(cod.stats_activision(self.code_activision, "zm", cookies)[0])
                        except cod.ErreurActivision:
                            pass
                    valeurs.update(v)  # les stats officielles passent avant celles lues à l'écran
                    etat.append({"nom": "Activision", "icone": "connecte", "ok": True,
                                 "texte": f"{ident.get('username', '')} ({ident.get('platform', '')})"})
                except (cod.ErreurActivision, navigateur.ErreurConnexion) as e:
                    etat.append({"nom": "Activision", "icone": "connexion", "ok": False, "texte": str(e)})
            else:
                etat.append({"nom": "Activision", "icone": "connexion", "ok": None,
                             "texte": "pas connecté : connecte-toi pour les stats officielles"})

        # 3) Temps de jeu mesuré sur ce PC
        temps = cod.valeurs_temps(self.id, dossier)
        if temps:
            valeurs.update(temps)
            etat.append({"nom": "Temps de jeu", "icone": "horloge", "ok": True,
                         "texte": f"{temps['sessions']} session(s) · {temps['temps_suivi']} h".replace(".", ",")})
        else:
            etat.append({"nom": "Temps de jeu", "icone": "horloge", "ok": None,
                         "texte": "lance le jeu sur ce PC avec AllMyStats allumé"})

        # Conseils
        conseils = [
            ["telecharger", "Sans lecture d'écran : demande ton fichier « Mes données » à Activision (le bandeau "
                            "plus bas explique comment) puis importe-le. Refais-le de temps en temps pour mettre à jour."],
            ["horloge", "Le temps de jeu se mesure tout seul quand un Call of Duty est lancé sur ce PC."],
            ["cod_dossier", "En option : ouvre ton Combat Record en jeu, AllMyStats le lit aussi à l'écran."],
        ]
        if self.code_activision:
            conseils.insert(1, ["connexion", "Connecte ton compte Activision pour les stats officielles de ce jeu."])
        sections.append({"titre": "Comment remplir tes stats", "icone": "astuce", "conseils": conseils})

        if not valeurs and not any(e["ok"] for e in etat):
            return {}, {"etat": etat, "sections": sections}, "Importe tes données Activision pour remplir tes stats"
        return valeurs, {"etat": etat, "sections": sections}, "Stats Call of Duty à jour"


class BlackOps6(CallOfDuty):
    id, nom, ordre, couleur, icone = "cod_bo6", "Black Ops 6", 1, "#E8A33D", "jeu_cod_bo6"
    zombies = True
    stats = stats_multijoueur(zombies=True)


class BlackOps7(CallOfDuty):
    id, nom, ordre, couleur, icone = "cod_bo7", "Black Ops 7", 2, "#F25C3C", "jeu_cod_bo7"
    zombies = True
    stats = stats_multijoueur(zombies=True)


class ColdWar(CallOfDuty):
    id, nom, ordre, couleur, icone = "cod_coldwar", "Cold War", 3, "#4FA3E0", "jeu_cod_coldwar"
    zombies = True
    code_activision = "cw"
    stats = stats_multijoueur(zombies=True)


class ModernWarfare4(CallOfDuty):
    id, nom, ordre, couleur, icone = "cod_mw4", "MW4", 4, "#7FC25B", "jeu_cod_mw4"
    stats = stats_multijoueur()


class Warzone(CallOfDuty):
    id, nom, ordre, couleur, icone = "cod_warzone", "Warzone", 5, "#C9B458", "jeu_cod_warzone"
    stat_vedette = "victoires"
    stats = stats_warzone()


class WarzoneMW4(CallOfDuty):
    id, nom, ordre, couleur, icone = "cod_warzone_mw4", "Warzone MW4", 6, "#5CC9A7", "jeu_cod_warzone_mw4"
    stat_vedette = "victoires"
    stats = stats_warzone()


class ModernWarfare3(CallOfDuty):
    id, nom, ordre, couleur, icone = "cod_mw3", "MW3 (2023)", 7, "#9C8CF0", "jeu_cod_mw3"
    stats = stats_multijoueur()


class ModernWarfare2(CallOfDuty):
    id, nom, ordre, couleur, icone = "cod_mw2", "MW2 (2022)", 8, "#5BB7C9", "jeu_cod_mw2"
    code_activision = "mw2"
    stats = stats_multijoueur()
