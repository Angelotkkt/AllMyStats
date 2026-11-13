"""MODÈLE pour ajouter un nouveau jeu.

1. Copie ce fichier dans le dossier « jeux » et renomme la copie SANS le « _ »
   au début, par exemple : fortnite.py
2. Change l'id, le nom, l'icône et la liste des stats.
3. Relance AllMyStats : le jeu apparaît tout seul dans la liste.

Si le jeu n'a pas de moyen de récupérer les stats automatiquement,
mets seulement des Stat(..., "manuel") et supprime la fonction recuperer :
tu noteras tes stats à la main depuis l'appli.
"""

from .base import ErreurJeu, Jeu, Stat


class MonJeu(Jeu):
    id = "mon_jeu"            # unique, sans espace ni accent
    nom = "Mon jeu"
    icone = ""
    couleur = "#e0679b"

    # Réglages demandés dans l'appli (pseudo, identifiant...). Laisse [] si rien.
    reglages = [
        {"cle": "pseudo", "nom": "Pseudo", "aide": "Ton pseudo dans le jeu"},
    ]

    # groupe = titre du bloc ; icone = un emoji de web/icones.js (ou ajoutes-en un)
    stats = [
        Stat("victoires", "Victoires", "manuel", groupe="Parties", icone="succes"),
        Stat("eliminations", "Éliminations", "manuel", groupe="Parties", icone="arme"),
        Stat("temps_jeu", "Temps de jeu", "manuel", unite="h", groupe="Compte", icone="sablier"),
    ]

    # À garder seulement si tu as des Stat(..., "auto")
    def recuperer(self, reglages, dossier_donnees):
        pseudo = reglages.get("pseudo")
        if not pseudo:
            raise ErreurJeu("Mets ton pseudo dans les Réglages.")
        # Ici : appeler l'API du jeu et renvoyer les valeurs
        valeurs = {"victoires": 0}
        details = None
        return valeurs, details, f"Stats de {pseudo} récupérées"
