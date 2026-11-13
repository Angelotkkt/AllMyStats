"""Le test « Tester la lecture d'écran » : explique, étape par étape, ce qui marche et ce qui bloque."""

import time


def etape(etat, titre, detail=""):
    """etat : "ok" | "erreur" | "alerte" | "neutre"."""
    return {"etat": etat, "titre": titre, "detail": detail}


def _devant(r):
    d = r.get("devant") or {}
    nom = d.get("titre") or d.get("processus") or ""
    if not nom:
        return "le bureau de Windows"
    if d.get("processus", "").lower() in ("msedge", "chrome", "allmystats", "messtats") and "AllMyStats" in nom:
        return "AllMyStats"
    return f"« {nom} »"


def etapes_capture(r, nom_jeu):
    """Étapes lisibles à partir du résultat de windows.lire_ecran_complet. Renvoie (etapes, texte_lu)."""
    e = r["etat"]
    if e == "PAS_WINDOWS":
        return [etape("erreur", "Windows", "La lecture d'écran ne marche que sur Windows 10 ou 11.")], False
    if e == "SANS_REPONSE":
        return [etape("erreur", "Lecture d'écran de Windows",
                      "PowerShell n'a rien répondu. Un antivirus bloque peut-être PowerShell pour AllMyStats."
                      + (f" Détail : {r['message']}" if r.get("message") else ""))], False

    etapes = []
    if e == "PAS_AU_PREMIER_PLAN":
        etapes.append(etape("erreur", f"{nom_jeu} au premier plan",
                            f"Au moment de la capture, c'est {_devant(r)} qui était devant. AllMyStats ne lit "
                            f"que la fenêtre du jeu : pendant le compte à rebours, clique dans la fenêtre de {nom_jeu}."))
        return etapes, False
    if e == "REDUIT":
        etapes.append(etape("erreur", f"{nom_jeu} au premier plan", "La fenêtre du jeu était réduite dans la barre des tâches."))
        return etapes, False
    titre = r.get("titre") or r.get("processus") or nom_jeu
    etapes.append(etape("ok", f"{nom_jeu} au premier plan", f"Fenêtre trouvée : « {titre} »."))

    taille = (r.get("fenetre") or "").replace("x", " × ")
    if e == "FENETRE_TROP_PETITE":
        etapes.append(etape("erreur", "Capture de la fenêtre", f"La fenêtre est trop petite ({taille}). Agrandis-la."))
        return etapes, False
    if e == "CAPTURE_NOIRE":
        etapes.append(etape("erreur", "Capture de la fenêtre",
                            "L'image capturée est toute noire : ton jeu est sûrement en plein écran exclusif, "
                            "que Windows ne laisse pas capturer. Dans les options d'affichage du jeu, choisis "
                            "« Plein écran fenêtré » (ou « Sans bordure »), puis refais le test."))
        return etapes, False
    if r.get("fenetre"):
        etapes.append(etape("ok", "Capture de la fenêtre", f"Image capturée ({taille}), puis effacée tout de suite."))

    if e == "PAS_DE_LANGUE_OCR":
        etapes.append(etape("erreur", "Lecture du texte par Windows",
                            "Windows n'a aucune langue de reconnaissance de texte installée. Dans Paramètres > "
                            "Heure et langue > Langue et région, ajoute « Français » ou « English (United States) », "
                            "puis redémarre le PC."))
        return etapes, False
    if e != "OK":
        etapes.append(etape("erreur", "Lecture du texte par Windows",
                            f"Windows a renvoyé une erreur : {r.get('message') or e}"))
        return etapes, False
    n = len(r["lignes"])
    if not n:
        etapes.append(etape("alerte", "Lecture du texte par Windows",
                            "Windows n'a lu aucun texte sur la capture. Vérifie que le jeu affiche bien ses chiffres "
                            "(pas d'écran de chargement)."))
        return etapes, False
    langue = f" (langue : {r['langue']})" if r.get("langue") else ""
    etapes.append(etape("ok", "Lecture du texte par Windows", f"{n} ligne(s) de texte lue(s){langue}."))
    return etapes, True


def resume_essai(essai):
    """Une phrase sur le dernier essai automatique, ou None."""
    if not essai:
        return None
    minutes = int((time.time() - essai.get("quand", time.time())) // 60)
    quand = "à l'instant" if minutes < 1 else f"il y a {minutes} min" if minutes < 120 else f"il y a {minutes // 60} h"
    textes = {
        "OK": f"texte lu ({essai.get('nb_lignes', 0)} lignes)",
        "PAS_AU_PREMIER_PLAN": "le jeu n'était pas au premier plan",
        "REDUIT": "la fenêtre du jeu était réduite",
        "FENETRE_TROP_PETITE": "la fenêtre du jeu était trop petite",
        "CAPTURE_NOIRE": "capture toute noire (plein écran exclusif ?)",
        "PAS_DE_LANGUE_OCR": "Windows n'a pas de langue de lecture",
        "SANS_REPONSE": "PowerShell n'a pas répondu",
        "PAS_EN_PARTIE": essai.get("message") or "pas en partie",
    }
    texte = textes.get(essai.get("etat"), f"erreur ({essai.get('message') or essai.get('etat')})")
    if essai.get("trouve") is not None:
        texte += f", {essai['trouve']} stat(s) reconnue(s)"
    return f"{quand} : {texte}"
