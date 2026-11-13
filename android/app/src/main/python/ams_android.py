"""Lance AllMyStats DANS le téléphone : le même moteur que sur le PC (core + jeux), sans Windows.
L'interface (dossier web) est affichée par l'appli Android dans sa vue web."""

import os
import traceback


def demarrer(donnees, web, port):
    os.environ["MESSTATS_DONNEES"] = donnees
    os.environ["AMS_WEB"] = web
    os.environ["AMS_ANDROID"] = "1"
    # Certificats HTTPS : ceux d'Android
    if os.path.isdir("/system/etc/security/cacerts"):
        os.environ.setdefault("SSL_CERT_DIR", "/system/etc/security/cacerts")
    try:
        from core import serveur
        serveur.demarrer(int(port), ouvrir_navigateur=False)
    except BaseException:
        with open(os.path.join(donnees, "erreur_demarrage.txt"), "w", encoding="utf-8") as f:
            f.write(traceback.format_exc())
        raise
