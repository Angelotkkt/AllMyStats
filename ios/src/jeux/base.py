"""Ce que chaque jeu doit fournir pour apparaître dans AllMyStats.

Pour ajouter un jeu : copie _modele_nouveau_jeu.py, renomme-le (ex: fortnite.py),
remplis-le, puis relance le programme. Il est détecté tout seul.
"""


class ErreurJeu(Exception):
    """Erreur avec un message clair à afficher à l'utilisateur."""


class Stat:
    def __init__(self, cle, nom, source="manuel", unite="", decimales=0, aide="", groupe="", icone="",
                 modifiable=False, etiquette=""):
        self.cle = cle            # identifiant interne, sans espace ni accent (ex: "primogemmes")
        self.nom = nom            # nom affiché (ex: "Primogemmes")
        self.source = source      # "auto" = récupéré tout seul, "manuel" = tu le notes toi-même
        self.unite = unite        # ex: "h", "%"
        self.decimales = decimales
        self.aide = aide
        self.groupe = groupe      # titre du bloc où la stat est rangée (ex: "Vœux")
        self.icone = icone        # nom d'un emoji perso de web/icones.js (ex: "primogemme")
        self.modifiable = modifiable  # stat auto qu'on peut aussi corriger à la main
        self.etiquette = etiquette    # petit mot affiché sur la carte (ex: "écran")

    def en_dict(self):
        return {
            "cle": self.cle,
            "nom": self.nom,
            "source": self.source,
            "unite": self.unite,
            "decimales": self.decimales,
            "aide": self.aide,
            "groupe": self.groupe,
            "icone": self.icone,
            "modifiable": self.modifiable,
            "etiquette": self.etiquette,
        }


class Jeu:
    id = ""          # identifiant unique (ex: "genshin")
    nom = ""         # nom affiché
    icone = ""       # nom d'un emoji de web/icones.js (sinon : jeu_<id>)
    couleur = "#7c8cff"
    stats = []       # liste de Stat
    reglages = []    # ex: [{"cle": "uid", "nom": "UID", "aide": "..."}]
    connexion_nom = None   # ex: "HoYoLAB" -> affiche un bouton « Se connecter avec HoYoLAB »
    connexion_aide = ""
    connexion_consigne = ""   # ce qu'il faut faire dans la fenêtre de connexion (affiché à son ouverture)

    @property
    def cle_reglages(self):
        return self.id_reglages or self.id

    def a_des_stats_auto(self):
        return any(s.source == "auto" for s in self.stats)

    def importer_donnees(self, contenu, nom, dossier_donnees):
        """Lit un fichier de données importé. Renvoie (stats par jeu {id: {clé: valeur}}, rapport [textes])."""
        raise ErreurJeu("Ce jeu n'importe pas de fichier.")

    def recuperer(self, reglages, dossier_donnees):
        """Récupère les stats automatiques.

        Doit renvoyer un tuple (valeurs, details, message) :
          - valeurs : {cle_stat: nombre}
          - details : fiche à afficher (voir format dans genshin.py) ou None
          - message : petit texte affiché après l'actualisation
        En cas de problème, lever ErreurJeu("explication").
        """
        raise ErreurJeu("Ce jeu n'a pas de récupération automatique.")

    def surveiller(self, reglages, dossier_donnees):
        """Appelé toutes les minutes tant que AllMyStats tourne. Peut renvoyer {cle_stat: nombre}."""
        return None

    page = None               # page spéciale à la place des stats (ex : "carte" pour une carte interactive)
    cartes_en_ligne = []      # pour page="carte" : [{"id", "nom", "url", "aide"}]
    import_images = False     # vrai si on peut glisser des captures d'écran dans l'appli (méthode lire_capture)
    consigne_import = ""
    import_donnees = None     # fichier de données à importer (ex : « Mes données » d'Activision) : {"titre", "accept", "aide", "etapes", "lien"}
    consigne_ecran = ""       # ce qu'il faut afficher en jeu pendant le test
    met_devant = False        # vrai si le test met lui-même la fenêtre du jeu au premier plan
    lit_ecran = False         # vrai si le jeu lit des stats sur l'écran (bouton « Tester la lecture d'écran »)

    def tester_ecran(self, reglages, dossier_donnees):
        """Test immédiat de la lecture d'écran. Renvoie un dictionnaire :
          etapes (voir core/diagnostic_ecran.etape), lignes (texte lu), valeurs ({cle: nombre} à enregistrer),
          cible (id du jeu où ranger les valeurs), dernier_essai (phrase ou None)."""
        return None

    famille = None            # ex: "Call of Duty" -> rangé avec ses frères dans la barre de gauche
    ordre = 0                 # ordre dans la famille
    id_reglages = None        # pour partager les réglages (et la connexion) entre plusieurs jeux d'une famille
    stat_vedette = None       # la stat affichée en grand sur la carte de joueur (ex: "niveau")
    cles_connexion = ()       # réglages effacés à la déconnexion (ex: cookies)
    dossier_connexion = None  # dossier de la fenêtre de connexion (effacé à la déconnexion)

    def est_connecte(self, reglages):
        return bool(self.cles_connexion) and all(reglages.get(c) for c in self.cles_connexion[:1])

    def nom_du_compte(self, reglages):
        """Texte court affiché sous « Connecté » (ex: pseudo ou UID)."""
        return ""

    def connexion(self, reglages, dossier_donnees):
        """Connecte le compte du joueur. Renvoie (reglages_trouves, message).
        Lever ErreurJeu en cas de problème."""
        raise ErreurJeu("Ce jeu n'a pas de connexion directe.")

    def en_dict(self):
        return {
            "famille": self.famille,
            "ordre": self.ordre,
            "connexion": self.connexion_nom,
            "vedette": self.stat_vedette,
            "connexion_aide": self.connexion_aide,
            "connexion_consigne": self.connexion_consigne,
            "id": self.id,
            "nom": self.nom,
            "icone": self.icone,
            "couleur": self.couleur,
            "stats": [s.en_dict() for s in self.stats],
            "reglages": self.reglages,
            "auto": self.a_des_stats_auto(),
            "lit_ecran": self.lit_ecran,
            "met_devant": self.met_devant,
            "consigne_ecran": self.consigne_ecran,
            "import_images": self.import_images,
            "page": self.page,
            "cartes_en_ligne": self.cartes_en_ligne,
            "consigne_import": self.consigne_import,
            "import_donnees": self.import_donnees,
        }
