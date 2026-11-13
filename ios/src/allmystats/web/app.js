// ================= AllMyStats — interface =================

const etat = {
  jeux: [],
  jeuActif: null,
  donnees: null,
  statChoisie: null,
  appli: null,
  carteCollee: null,
};

const $ = (sel) => document.querySelector(sel);
// Ouvert depuis le téléphone (appli Android reliée au PC) : on cache ce qui ne marche que sur le PC
const DISTANT = !["localhost", "127.0.0.1", "[::1]"].includes(location.hostname);
// Les applis du téléphone (AllMyStats tourne dans le téléphone, sans le PC) : Android et iPhone
const ANDROID = /AllMyStatsAndroid/.test(navigator.userAgent) && !DISTANT;
const IOS = !DISTANT && (/AllMyStatsIOS/.test(navigator.userAgent) || (() => {
  try {
    if (new URLSearchParams(location.search).get("app") === "ios") localStorage.setItem("ams_app", "ios");
    return localStorage.getItem("ams_app") === "ios";
  } catch (e) { return new URLSearchParams(location.search).get("app") === "ios"; }
})());
const APPLI_MOBILE = ANDROID || IOS;
const HORS_PC = DISTANT || APPLI_MOBILE;
if (HORS_PC) document.documentElement.classList.add("distant");
const esc = (t) => String(t ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const emblemeJeu = (j) => icone(j.icone || "jeu_" + j.id, ICONES.jeu);
const mouvementReduit = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;

// ---------- API ----------
async function api(chemin, options = {}) {
  const rep = await fetch(chemin, {
    headers: { "Content-Type": "application/json" },
    ...options,
    body: options.body ? JSON.stringify(options.body) : undefined,
  });
  const data = await rep.json().catch(() => ({}));
  if (!rep.ok) throw new Error(data.erreur || `Erreur ${rep.status}`);
  return data;
}

// type : "ok" | "erreur" | "info"
function toast(message, type = "ok") {
  const t = $("#toast");
  const ic = { ok: "ok", erreur: "erreur", info: "astuce", connexion: "connexion" }[type] || "ok";
  t.innerHTML = `${icone(ic)}<span>${texteRiche(message)}</span>`;
  t.className = "visible" + (type === "erreur" ? " erreur" : "");
  son({ ok: "succes", erreur: "erreur", info: "info", connexion: "succes" }[type] || "info");
  clearTimeout(t._timer);
  t._timer = setTimeout(() => (t.className = ""), type === "erreur" ? 6500 : 4000);
}

// ---------- Formatage ----------
function nombre(v, stat) {
  if (v === null || v === undefined) return "—";
  const d = stat?.decimales ?? 0;
  const txt = Number(v).toLocaleString("fr-FR", { minimumFractionDigits: d, maximumFractionDigits: d });
  return stat?.unite ? `${txt} ${stat.unite}` : txt;
}
const dateCourte = (iso) => new Date(iso).toLocaleDateString("fr-FR", { day: "2-digit", month: "short" });
function dateLongue(iso) {
  const d = new Date(iso);
  return d.toLocaleDateString("fr-FR", { day: "numeric", month: "long" }) +
    " à " + d.toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" });
}

// ---------- Fond animé ----------
function fondAnime() { try { return localStorage.getItem("fond_anime") !== "0"; } catch (e) { return true; } }
function appliquerFond() { document.documentElement.classList.toggle("fond-fixe", !fondAnime()); }
appliquerFond();

// ---------- Démarrage ----------
async function demarrer() {
  $("#logo").innerHTML = ICONES.ams;
  $("#ic-parametres").innerHTML = ICONES.reglages;
  $("#ic-amis").innerHTML = ICONES.amis;
  $("#btn-amis").addEventListener("click", () => { son("onglet"); afficherPageAmis(); });
  try {
    etat.jeux = await api("/api/jeux");
  } catch (e) {
    $("#contenu").innerHTML = `<div class="vide">${ICONES.erreur}AllMyStats ne répond pas. Relance l'application.</div>`;
    return;
  }
  afficherListeJeux();
  await chargerAppli();
  // Page rechargée (mise à jour…) : une carte restée posée dans la fenêtre est d'abord retirée
  if (etat.appli?.fenetre_native) api("/api/carte-collee", { method: "POST", body: { action: "cacher" } }).catch(() => {});
  setInterval(chargerAppli, 60 * 1000);
  if (IOS && !etat.appli?.lie) return afficherLiaison();   // première ouverture sur iPhone : on relie au PC
  let memo = null;
  try { memo = localStorage.getItem("jeuActif"); } catch (e) {}
  ouvrirPremierJeuVisible(memo);
}

function ouvrirPremierJeuVisible(prefere) {
  const visibles = etat.jeux.filter((j) => !j.cache);
  if (visibles.length) {
    choisirJeu(visibles.some((j) => j.id === prefere) ? prefere : visibles[0].id);
  } else {
    etat.jeuActif = null;
    etat.donnees = null;
    $("#contenu").innerHTML = etat.jeux.length
      ? `<div class="vide">${ICONES.vide}Tous les jeux sont masqués.
           <button class="principal" id="vide-parametres">${ICONES.reglages}Choisir les jeux affichés</button></div>`
      : `<div class="vide">${ICONES.vide}Aucun jeu trouvé dans le dossier <code>jeux</code>.</div>`;
    $("#vide-parametres")?.addEventListener("click", ouvrirParametres);
  }
}

// Le nom affiché sous un jeu : le pseudo du compte connecté (sans « UID » ni #1234567)
const pseudoCourt = (compte) => (compte || "").replace(/^UID /, "").replace(/#\d+$/, "");

function cartouche(j, petit = false) {
  // Dans un dossier (ex : Call of Duty), le compte est affiché une seule fois, sur le dossier
  const sous = petit ? "" : j.connecte ? `${ICONES.connecte}${esc(pseudoCourt(j.compte) || "Connecté")}`
    : j.connexion ? "Pas connecté" : j.compte ? esc(pseudoCourt(j.compte)) : "";
  return `<button class="cartouche ${petit ? "petit" : ""} ${j.id === etat.jeuActif ? "actif" : ""}" data-id="${esc(j.id)}"
      style="--c:${esc(j.couleur)}" ${j.id === etat.jeuActif ? 'aria-current="page"' : ""}>
    <span class="cartouche-emblem">${emblemeJeu(j)}</span>
    <span class="cartouche-texte"><b>${esc(j.nom)}</b>${sous ? `<small>${sous}</small>` : ""}</span>
  </button>`;
}

const slug = (t) => t.toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/[^a-z0-9]+/g, "_");
function familleOuverte(nom) {
  try { return localStorage.getItem("famille_" + nom) !== "fermee"; } catch (e) { return true; }
}

function afficherListeJeux() {
  // Les jeux d'une même famille (ex : Call of Duty) sont rangés dans un dossier qu'on ouvre et ferme
  const blocs = [];
  for (const j of etat.jeux.filter((x) => !x.cache)) {
    if (!j.famille) { blocs.push({ jeu: j }); continue; }
    let f = blocs.find((b) => b.famille === j.famille);
    if (!f) blocs.push((f = { famille: j.famille, jeux: [] }));
    f.jeux.push(j);
  }
  $("#btn-amis").classList.toggle("actif", etat.jeuActif === "_amis");
  if (etat.jeuActif === "_amis") $("#btn-amis").setAttribute("aria-current", "page"); else $("#btn-amis").removeAttribute("aria-current");
  $("#liste-jeux").innerHTML = blocs.map((b) => {
    if (b.jeu) return cartouche(b.jeu);
    const actif = b.jeux.some((j) => j.id === etat.jeuActif);
    const ouverte = actif || familleOuverte(b.famille);
    const connecte = b.jeux.find((j) => j.connecte);
    const sousFamille = connecte ? `${ICONES.connecte}${esc(pseudoCourt(connecte.compte) || "Connecté")}`
      : `${b.jeux.length} jeux`;
    return `<div class="famille ${actif ? "contient-actif" : ""}">
      <button class="cartouche cartouche-famille" data-famille="${esc(b.famille)}" aria-expanded="${ouverte}">
        <span class="cartouche-emblem">${icone("famille_" + slug(b.famille), ICONES.jeu)}</span>
        <span class="cartouche-texte"><b>${esc(b.famille)}</b><small>${sousFamille}</small></span>
        <span class="chev">${ICONES.chevron}</span>
      </button>
      <div class="sous-jeux" ${ouverte ? "" : "hidden"}>${b.jeux.map((j) => cartouche(j, true)).join("")}</div>
    </div>`;
  }).join("");
  document.querySelectorAll("#liste-jeux .cartouche[data-id]").forEach((b) => (b.onclick = () => choisirJeu(b.dataset.id)));
  document.querySelectorAll("#liste-jeux .cartouche-famille").forEach((b) => (b.onclick = () => {
    const liste = b.nextElementSibling;
    liste.hidden = !liste.hidden;
    b.setAttribute("aria-expanded", String(!liste.hidden));
    try { localStorage.setItem("famille_" + b.dataset.famille, liste.hidden ? "fermee" : "ouverte"); } catch (e) {}
  }));
}

async function choisirJeu(id) {
  const autreJeu = etat.jeuActif !== id;
  etat.jeuActif = id;
  if (autreJeu) { etat.statChoisie = null; builds.choisi = null; builds.defilement = 0; }
  try { localStorage.setItem("jeuActif", id); } catch (e) {}
  try {
    etat.donnees = await api(`/api/jeux/${id}`);
    afficherListeJeux();
    afficherJeu(autreJeu);
    actualiserSiBesoin();
  } catch (e) {
    toast(e.message, "erreur");
  }
}

// ---------- Actualisation automatique ----------
const ACTUALISER_APRES = 10 * 60 * 1000;
const ACTUALISER_TOUTES = 20 * 60 * 1000;

function reglagesComplets() {
  const { jeu, reglages } = etat.donnees;
  return jeu.reglages.every((r) => r.optionnel || reglages[r.cle]);
}
function actualiserSiBesoin() {
  const d = etat.donnees;
  if (!d?.jeu.auto || !reglagesComplets()) return;
  const age = d.derniere_maj ? Date.now() - new Date(d.derniere_maj).getTime() : Infinity;
  if (age > ACTUALISER_APRES) actualiser(true);
}
setInterval(() => {
  if (document.visibilityState === "visible" && etat.donnees?.jeu.auto && reglagesComplets()) actualiser(true);
}, ACTUALISER_TOUTES);

// ---------- Page d'un jeu ----------
// Garde la barre de gauche à jour quand tu te connectes ou te déconnectes
// (les jeux d'une même famille partagent la même connexion)
function synchroniserConnexion() {
  if (!etat.donnees) return;
  const { jeu, connecte, compte } = etat.donnees;
  let change = false;
  for (const j of etat.jeux) {
    const meme = j.id === jeu.id || (jeu.famille && j.famille === jeu.famille && j.connexion === jeu.connexion);
    if (meme && (j.connecte !== connecte || j.compte !== compte)) {
      Object.assign(j, { connecte, compte });
      change = true;
    }
  }
  if (change) afficherListeJeux();
}

function afficherJeu(animer = false) {
  synchroniserConnexion();
  const { jeu, stats, details, derniere_maj } = etat.donnees;
  $("#titre-mobile").textContent = jeu.famille && jeu.famille !== jeu.nom ? `${jeu.nom}` : jeu.nom;
  fermerMenu();
  document.documentElement.style.setProperty("--accent", jeu.couleur);
  cacherCarteCollee();
  if (jeu.page === "carte") return afficherPageCarte(jeu);
  if (jeu.page === "builds") return afficherPageBuilds(jeu);

  // Range les stats par groupe ; on cache les stats auto jamais récupérées
  const visible = (s) => s.source === "manuel" || s.modifiable || stats[s.cle].actuelle !== null;
  const groupes = [];
  for (const s of jeu.stats.filter(visible)) {
    const nomGroupe = s.groupe || (s.source === "auto" ? "Stats automatiques" : "Stats que tu notes");
    let g = groupes.find((x) => x.nom === nomGroupe);
    if (!g) groupes.push((g = { nom: nomGroupe, icone: s.icone, stats: [] }));
    g.stats.push(s);
  }
  if (!jeu.stats.some((s) => s.cle === etat.statChoisie && visible(s))) {
    const avecHistorique = jeu.stats.find((s) => visible(s) && stats[s.cle].historique.length > 1);
    etat.statChoisie = (avecHistorique || groupes[0]?.stats[0] || jeu.stats[0])?.cle;
  }
  const statsModifiables = jeu.stats.filter((s) => s.source === "manuel" || s.modifiable);

  $("#contenu").innerHTML = `
    ${carteJoueur()}
    ${!reglagesComplets() && !jeu.connexion ? `<div class="bandeau">${ICONES.astuce}
        <span class="texte">Pour récupérer tes stats, renseigne d'abord : <b>${jeu.reglages.filter((r) => !r.optionnel).map((r) => esc(r.nom)).join(", ")}</b></span>
        <button class="principal" data-action="reglages">${ICONES.reglages}Ouvrir les réglages</button></div>` : ""}
    ${!etat.donnees.connecte && jeu.connexion ? `<div class="bandeau">${ICONES.connexion}
        <span class="texte">${esc(jeu.connexion_aide)}</span></div>` : ""}

    ${jeu.import_donnees ? blocImportDonnees(jeu.import_donnees, !Object.values(stats).some((x) => x.actuelle !== null)) : ""}

    ${groupes.map((g) => `<h2 class="titre">${icone(g.icone)}${esc(g.nom)}</h2>
      <div class="grille-stats">${g.stats.map(tuileStat).join("")}</div>`).join("")}

    ${jeu.lit_ecran && !HORS_PC ? `<div class="bandeau test-ecran">${ICONES.ecran}
        <span class="texte"><b>Lecture d'écran</b>Les stats marquées « écran » sont lues sur ton écran pendant que tu joues.
          Si elles ne bougent pas, lance le test : AllMyStats te dit exactement ce qui bloque.</span>
        <button class="secondaire" data-action="test-ecran">${ICONES.ecran}Tester la lecture d'écran</button></div>` : ""}

    ${jeu.import_images ? `
    <label class="depot-captures" id="depot-captures">
      <input type="file" id="fichiers-captures" accept="image/png,image/jpeg,image/bmp" multiple>
      <span class="depot-icone">${ICONES.pogo_capture || ICONES.ajouter}</span>
      <span class="texte"><b>Importer des captures</b>${esc(jeu.consigne_import)}
        <small>Glisse tes captures ici, ou clique pour les choisir. Les images ne sont pas gardées : seuls les chiffres le sont.</small></span>
    </label>` : ""}

    <h2 class="titre">${ICONES.graphique}Progression</h2>
    <div class="zone-graph">
      <div class="panneau" id="panneau-graph"></div>
      <div class="panneau historique" id="panneau-historique"></div>
    </div>

    ${statsModifiables.length ? `
    <h2 class="titre">${ICONES.ajouter}Noter ou corriger une stat</h2>
    <div class="panneau">
      <form class="ajout" id="form-ajout">
        <label>Stat
          <select name="cle">${statsModifiables.map((s) => `<option value="${esc(s.cle)}">${esc(s.nom)}${s.unite ? " (" + esc(s.unite) + ")" : ""}</option>`).join("")}</select>
        </label>
        <label>Valeur <input name="valeur" inputmode="decimal" required placeholder="ex : 4520" style="width:130px"></label>
        <label>Date <input name="date" type="date" value="${new Date().toLocaleDateString("en-CA")}"></label>
        <label class="note">Note (facultatif) <input name="note" placeholder="ex : après une grosse session de farm"></label>
        <button class="principal">${ICONES.ajouter}Ajouter</button>
      </form>
    </div>` : ""}

    <div id="details">${afficherDetails(details)}</div>`;

  // Événements
  document.querySelectorAll(".stat").forEach((c) => (c.onclick = () => {
    etat.statChoisie = c.dataset.cle;
    document.querySelectorAll(".stat").forEach((x) => x.classList.toggle("choisie", x === c));
    afficherGraphique();
    const sel = $("#form-ajout select");
    if (sel && [...sel.options].some((o) => o.value === c.dataset.cle)) sel.value = c.dataset.cle;
  }));
  document.querySelectorAll('[data-action="actualiser"]').forEach((b) => b.addEventListener("click", () => actualiser()));
  document.querySelectorAll('[data-action="reglages"]').forEach((b) => b.addEventListener("click", ouvrirReglages));
  document.querySelectorAll('[data-action="connecter"]').forEach((b) => b.addEventListener("click", connecter));
  document.querySelectorAll('[data-action="test-ecran"]').forEach((b) => b.addEventListener("click", testerEcran));
  brancherDepotCaptures();
  brancherImportDonnees();
  brancherInventaire();
  brancherMenuConnexion();
  $("#form-ajout")?.addEventListener("submit", ajouterMesure);
  const sel = $("#form-ajout select");
  if (sel && statsModifiables.some((s) => s.cle === etat.statChoisie)) sel.value = etat.statChoisie;

  afficherGraphique();
  if (animer) animerVedette();
}

// Une adresse d'image sûre à mettre dans la page (https, caractères simples seulement)
const urlImage = (u) => typeof u === "string" && /^https:\/\/[\w.\-\/%?=&~+]+$/.test(u) && u.length < 500 ? u : "";

// La carte de joueur : l'emblème, ton pseudo, et la stat la plus importante en très grand
function carteJoueur() {
  const { jeu, stats, connecte, compte, derniere_maj, details } = etat.donnees;
  const vedette = jeu.stats.find((s) => s.cle === jeu.vedette) || jeu.stats.find((s) => stats[s.cle].actuelle !== null);
  const valeur = vedette ? stats[vedette.cle].actuelle : null;
  const pseudo = pseudoCourt(compte) || jeu.nom;
  // La photo du compte (Genshin, Steam, carte Valorant) et la bannière du jeu, quand on les connaît
  const avatar = urlImage(details?.avatar), banniere = urlImage(details?.banniere);
  return `
  <section class="carte-joueur ${banniere ? "avec-banniere" : ""}" aria-label="Carte de joueur ${esc(jeu.nom)}"
      ${banniere ? `style="--banniere:url('${banniere}')"` : ""}>
    <div class="deco" aria-hidden="true">${banniere ? `<div class="cj-banniere"></div>` : ""}<div class="filigrane">${emblemeJeu(jeu)}</div></div>
    <div class="cj-emblem ${avatar ? "a-photo" : ""}">${avatar
      ? `<img class="cj-photo" src="${avatar}" alt="Photo du compte" onerror="this.parentNode.classList.remove('a-photo');this.remove()"><span class="cj-mini">${emblemeJeu(jeu)}</span>`
      : emblemeJeu(jeu)}</div>
    <div class="cj-identite">
      <div class="cj-jeu">${jeu.famille && jeu.famille !== jeu.nom ? esc(jeu.famille) + " · " : ""}${esc(jeu.nom)}</div>
      <div class="cj-pseudo">${esc(pseudo)}</div>
      ${details?.badge?.texte ? `<div class="cj-badge">${details.badge.image ? `<img src="${esc(details.badge.image)}" alt="">` : icone(details.badge.icone)}${esc(details.badge.texte)}</div>` : ""}
      <div class="cj-maj">${derniere_maj ? "Actualisé le " + esc(dateLongue(derniere_maj)) : "Pas encore actualisé"}</div>
    </div>
    ${vedette ? `<div class="cj-vedette">
      <div class="chiffre" data-cible="${valeur ?? ""}" data-decimales="${vedette.decimales || 0}">${esc(nombre(valeur, { decimales: vedette.decimales }))}</div>
      <div class="libelle">${icone(vedette.icone)}${texteRiche(vedette.nom)}</div>
    </div>` : "<div></div>"}
    <div class="cj-actions">
      ${jeu.connexion ? (connecte ? (HORS_PC ? `<span class="pill-connecte">${ICONES.connecte}Connecté</span>` : menuConnexion()) :
        HORS_PC ? `<span class="note-pc">${ICONES.connexion}Connexion ${esc(jeu.connexion)} : sur le PC seulement</span>` :
        `<button class="principal" data-action="connecter">${ICONES.connexion}Se connecter avec ${esc(jeu.connexion)}</button>`) : ""}
      ${jeu.reglages.length ? `<button class="secondaire" data-action="reglages">${ICONES.reglages}Réglages</button>` : ""}
      ${jeu.auto ? `<button class="secondaire" data-action="actualiser" id="btn-actualiser">${ICONES.actualiser}Actualiser</button>` : ""}
    </div>
    ${afficherEtatSources(details?.etat)}
  </section>`;
}

function menuConnexion() {
  const { jeu, compte } = etat.donnees;
  return `<div class="menu-connexion">
    <button class="pill-connecte" aria-haspopup="true" aria-expanded="false" title="Compte ${esc(jeu.connexion)}">
      ${ICONES.connecte}Connecté${compte ? `<small>${esc(compte)}</small>` : ""}<span class="chev">${ICONES.chevron}</span>
    </button>
    <div class="menu" hidden>
      <button class="discret" data-action="connecter">${ICONES.actualiser}Reconnecter</button>
      <button class="discret" data-action="deconnecter">${ICONES.deconnexion}Se déconnecter de ${esc(jeu.connexion)}</button>
    </div>
  </div>`;
}

function brancherMenuConnexion() {
  const pill = $(".pill-connecte");
  if (!pill) return;
  const menu = pill.nextElementSibling;
  pill.onclick = (e) => {
    e.stopPropagation();
    menu.hidden = !menu.hidden;
    pill.setAttribute("aria-expanded", String(!menu.hidden));
  };
  document.addEventListener("click", () => { menu.hidden = true; pill.setAttribute("aria-expanded", "false"); }, { once: true });
  menu.querySelector('[data-action="deconnecter"]').onclick = deconnecter;
}

function animerVedette() {
  // Le vrai chiffre est affiché tout de suite ; il « monte » juste à l'écran (une seule animation)
  const el = $(".cj-vedette .chiffre");
  if (!el || mouvementReduit()) return;
  el.classList.remove("apparait");
  void el.offsetWidth;
  el.classList.add("apparait");
}

function tuileStat(stat) {
  const s = etat.donnees.stats[stat.cle];
  let delta = "Pas encore de données";
  if (s.actuelle !== null) {
    delta = "";
    if (s.precedente !== null) {
      const diff = s.actuelle - s.precedente;
      delta = diff === 0 ? `${ICONES.egal}Pas de changement`
        : diff > 0 ? `${ICONES.hausse}<span class="plus">+${nombre(diff, stat)}</span> depuis la dernière fois`
        : `${ICONES.baisse}<span class="moins">${nombre(diff, stat)}</span> depuis la dernière fois`;
    }
  }
  const etiquette = stat.etiquette || (stat.source === "manuel" ? "à noter" : "");
  const perso = etat.donnees.details?.tuiles?.[stat.cle];   // ex : rang Valorant affiché en toutes lettres avec son logo
  return `<button class="stat ${stat.cle === etat.statChoisie ? "choisie" : ""} ${perso ? "tuile-perso" : ""}" data-cle="${esc(stat.cle)}" title="${esc(stat.aide || "")}">
      <span class="sticker">${perso?.image ? `<img src="${esc(perso.image)}" alt="" loading="lazy">` : icone(stat.icone, ICONES.graphique)}</span>
      ${etiquette ? `<span class="etiquette">${esc(etiquette)}</span>` : ""}
      <div class="nom">${texteRiche(stat.nom)}</div>
      ${perso ? `<div class="val">${esc(perso.texte)}${perso.sous ? `<small>${esc(perso.sous)}</small>` : ""}</div>`
              : `<div class="val ${s.actuelle === null ? "rien" : ""}">${nombre(s.actuelle, stat)}</div>`}
      <div class="delta">${delta}</div>
    </button>`;
}

function afficherEtatSources(liste) {
  if (!liste?.length) return "";
  return `<div class="sources">${liste.map((s) => {
    const classe = s.ok === true ? "ok" : s.ok === false ? "ko" : "neutre";
    return `<div class="source ${classe}" title="${esc(s.texte)}">
      ${icone(s.icone)}<b>${esc(s.nom)}</b><span class="etat">${ICONES[classe === "ko" ? "erreur" : classe]}</span>
      <span class="txt">${esc(s.texte)}</span></div>`;
  }).join("")}</div>`;
}

// ---------- Graphique (SVG fait maison, marche sans internet) ----------
function afficherGraphique() {
  const stat = etat.donnees.jeu.stats.find((s) => s.cle === etat.statChoisie);
  const panneau = $("#panneau-graph");
  if (!stat) { panneau.innerHTML = ""; return; }
  const points = etat.donnees.stats[stat.cle].historique;
  let gain = "";
  if (points.length > 1) {
    const diff = points[points.length - 1].valeur - points[0].valeur;
    gain = `<small>${diff >= 0 ? "+" : ""}${nombre(diff, stat)} depuis le ${dateCourte(points[0].date)}</small>`;
  }
  panneau.innerHTML = `<h3>${icone(stat.icone)}${texteRiche(stat.nom)} ${gain}</h3>` + (points.length < 2
    ? `<div class="graph-vide">${ICONES.graphique}
         <span>${points.length ? "La courbe apparaîtra dès que cette stat aura bougé." : "Aucune valeur pour l'instant."}</span>
         <span>${stat.source === "auto" ? "AllMyStats s'actualise tout seul." : "Ajoute une valeur plus bas."}</span></div>`
    : svgCourbe(points, stat));
  afficherHistorique(stat, points);
}

function svgCourbe(points, stat) {
  const L = 700, H = 260, g = 54, d = 16, h = 16, b = 30;
  const t = points.map((p) => new Date(p.date).getTime());
  const v = points.map((p) => p.valeur);
  let tMin = Math.min(...t), tMax = Math.max(...t);
  if (tMax === tMin) { tMin -= 3600e3; tMax += 3600e3; }
  let vMin = Math.min(...v), vMax = Math.max(...v);
  if (vMax === vMin) { vMin -= 1; vMax += 1; }
  const marge = (vMax - vMin) * 0.12; vMin -= marge; vMax += marge;
  const X = (x) => g + ((x - tMin) / (tMax - tMin)) * (L - g - d);
  const Y = (y) => h + (1 - (y - vMin) / (vMax - vMin)) * (H - h - b);

  let grille = "";
  for (let i = 0; i <= 4; i++) {
    const val = vMin + ((vMax - vMin) * i) / 4, y = Y(val);
    grille += `<line class="grille" x1="${g}" x2="${L - d}" y1="${y}" y2="${y}"/>
      <text x="${g - 10}" y="${y + 4}" text-anchor="end">${esc(nombre(val, { decimales: stat.decimales || (vMax - vMin < 5 ? 1 : 0) }))}</text>`;
  }
  const nbDates = Math.min(5, points.length);
  for (let i = 0; i < nbDates; i++) {
    const tt = tMin + ((tMax - tMin) * i) / Math.max(1, nbDates - 1);
    grille += `<text x="${X(tt)}" y="${H - 6}" text-anchor="middle">${esc(dateCourte(tt))}</text>`;
  }
  // Courbe en escalier : une stat garde sa valeur jusqu'au changement suivant
  let chemin = "";
  points.forEach((p, i) => {
    const x = X(t[i]).toFixed(1), y = Y(p.valeur).toFixed(1);
    chemin += i ? ` H${x} V${y}` : `M${x},${y}`;
  });
  const aire = `${chemin} V${H - b} H${X(t[0])} Z`;
  const ronds = points.map((p, i) => `<circle cx="${X(t[i])}" cy="${Y(p.valeur)}" r="5" fill="var(--encre)" stroke="var(--accent)" stroke-width="2.5">
      <title>${esc(nombre(p.valeur, stat))} le ${esc(dateLongue(p.date))}${p.note ? "\n" + esc(p.note) : ""}</title></circle>`).join("");
  return `<svg class="graph" viewBox="0 0 ${L} ${H}" role="img" aria-label="Évolution de ${esc(stat.nom)}">
    <defs><linearGradient id="deg" x1="0" x2="0" y1="0" y2="1">
      <stop offset="0" stop-color="var(--accent)" stop-opacity=".32"/><stop offset="1" stop-color="var(--accent)" stop-opacity="0"/>
    </linearGradient></defs>
    ${grille}
    <path d="${aire}" fill="url(#deg)"/>
    <path d="${chemin}" fill="none" stroke="var(--accent)" stroke-width="3" stroke-linejoin="round"/>
    ${ronds}
  </svg>`;
}

function afficherHistorique(stat, points) {
  const panneau = $("#panneau-historique");
  if (!points.length) {
    panneau.innerHTML = `<h3>${ICONES.historique}Historique</h3><p class="gris">Rien pour l'instant.</p>`;
    return;
  }
  panneau.innerHTML = `<h3>${ICONES.historique}Historique <small>${points.length} valeur${points.length > 1 ? "s" : ""}</small></h3>
    <table>${[...points].reverse().map((p) => `
      <tr>
        <td>${esc(dateCourte(p.date))}<div class="note">${esc(p.note || (p.source === "auto" ? "automatique" : "noté à la main"))}</div></td>
        <td class="v">${esc(nombre(p.valeur, stat))}</td>
        <td style="width:30px"><button title="Supprimer cette valeur" aria-label="Supprimer cette valeur" data-id="${p.id}">${ICONES.supprimer}</button></td>
      </tr>`).join("")}</table>`;
  panneau.querySelectorAll("button[data-id]").forEach((b) => (b.onclick = () => supprimerMesure(b.dataset.id)));
}

// ---------- Détails (profil, persos…) ----------
function portrait(c, secours) {
  const em = `<span class="portrait" ${c.image ? 'style="display:none"' : ""}>${icone(c.icone || secours, ICONES.persos)}</span>`;
  if (!c.image) return em;
  return `<img class="portrait" src="${esc(c.image)}" alt="" loading="lazy"
    onerror="this.style.display='none';this.nextElementSibling.style.display='grid'">${em}`;
}
const badgeHtml = (b) => `<span class="badge">${icone(b)}${texteRiche(b)}</span>`;

function afficherDetails(details) {
  if (!details?.sections?.length) return "";
  return details.sections.map((section) => {
    let html = `<h2 class="titre">${icone(section.icone)}${texteRiche(section.titre)}${section.cartes ? `<span class="compte">${section.cartes.length}</span>` : section.compte_total !== undefined ? `<span class="compte">${section.compte_total}</span>` : ""}</h2>`;
    if (section.note) html += `<p class="note-details">${ICONES.astuce}<span>${esc(section.note)}</span></p>`;
    if (section.conseils?.length) {
      html += `<div class="panneau conseils">${section.conseils.map(([ic, t]) =>
        `<p>${icone(ic)}<span>${texteRiche(t)}</span></p>`).join("")}</div>`;
    }
    if (section.build?.length) {
      html += `<div class="panneau bf-build">${section.build.map((b) => `
        <div class="bf-stat"><span class="bf-stat-nom">${icone(b.icone)}${esc(b.nom)}</span>
          <span class="bf-barre"><span style="width:${Math.min(100, (b.points / 2800) * 100)}%"></span></span>
          <b>${esc(nombre(b.points))}</b></div>`).join("")}</div>`;
    }
    if (section.inventaire) html += inventaireHtml(section.inventaire);
    if (section.lignes?.length) {
      const ico = (ic) => /^https?:/.test(ic || "") ? `<img class="mini" src="${esc(ic)}" alt="" loading="lazy">` : icone(ic);
      html += `<div class="panneau lignes">${section.lignes.map(([k, v, ic]) =>
        `<div><span class="cle">${ico(ic)}${texteRiche(k)}</span><span class="valeur">${texteRiche(v)}</span></div>`).join("")}</div>`;
    }
    if (section.cartes?.length && section.compact) {
      html += `<div class="grille-vignettes">${section.cartes.map((c) => `
        <div class="vignette" style="--c:${esc(c.couleur || "var(--accent)")}" title="${esc(c.titre)}">
          ${portrait(c, "persos")}
          <div class="t">${esc(c.titre)}</div>
          <div class="st">${(c.badges || []).map((b) => icone(b)).join("")}${texteRiche(c.sous_titre || "")}</div>
        </div>`).join("")}</div>`;
    } else if (section.cartes?.length) {
      html += `<div class="grille-fiches">${section.cartes.map((c) => `
        <div class="fiche ${c.banniere ? "avec-banniere" : ""}" style="--c:${esc(c.couleur || "var(--accent)")}${c.banniere ? `;--banniere:url('${esc(c.banniere)}')` : ""}">
          <div class="haut">
            ${c.image || c.icone ? portrait(c, c.icone || "persos") : ""}
            <div><div class="t">${texteRiche(c.titre)}</div><div class="st">${texteRiche(c.sous_titre || "")}</div></div>
          </div>
          ${c.progression !== undefined ? `<div class="barre-prog"><div style="width:${Math.min(100, c.progression * 100)}%"></div></div>` : ""}
          ${c.badges?.length ? `<div class="badges">${c.badges.map(badgeHtml).join("")}</div>` : ""}
          ${c.lignes?.length ? `<div class="lignes-fiche">${c.lignes.map(([k, v]) => `<div><span>${texteRiche(k)}</span><span>${texteRiche(v)}</span></div>`).join("")}</div>` : ""}
        </div>`).join("")}</div>`;
    }
    return html;
  }).join("");
}

// ---------- Actions ----------
let actualisationEnCours = false;
async function actualiser(silencieux = false) {
  if (actualisationEnCours) return;
  actualisationEnCours = true;
  const jeuId = etat.jeuActif;
  const btn = $("#btn-actualiser");
  if (btn) { btn.disabled = true; btn.innerHTML = `${ICONES.sablier}Récupération…`; }
  try {
    const rep = await api(`/api/jeux/${jeuId}/actualiser`, { method: "POST" });
    if (etat.jeuActif === jeuId) {
      etat.donnees = rep;
      afficherListeJeux();
      afficherJeu();
    }
    const alerte = rep.details?.etat?.some((s) => s.ok === false);
    if (!silencieux || alerte) toast(rep.message, alerte ? "erreur" : "ok");
  } catch (e) {
    toast(e.message, "erreur");
    const b = $("#btn-actualiser");
    if (b) { b.disabled = false; b.innerHTML = `${ICONES.actualiser}Actualiser`; }
  } finally {
    actualisationEnCours = false;
  }
}

async function ajouterMesure(ev) {
  ev.preventDefault();
  const f = new FormData(ev.target);
  const cle = f.get("cle");
  try {
    const rep = await api(`/api/jeux/${etat.jeuActif}/mesure`, {
      method: "POST",
      body: { cle, valeur: f.get("valeur"), date: f.get("date"), note: f.get("note") },
    });
    etat.donnees = rep;
    etat.statChoisie = cle;
    afficherJeu();
    toast(rep.message);
  } catch (e) {
    toast(e.message, "erreur");
  }
}

async function supprimerMesure(id) {
  if (!confirm("Supprimer cette valeur ?")) return;
  try {
    await api(`/api/mesures/${id}`, { method: "DELETE" });
    etat.donnees = await api(`/api/jeux/${etat.jeuActif}`);
    afficherJeu();
    toast("Valeur supprimée");
  } catch (e) {
    toast(e.message, "erreur");
  }
}

// ---------- Connexion avec le compte du jeu ----------
async function connecter() {
  const jeuId = etat.jeuActif;
  const nom = etat.donnees.jeu.connexion;
  if ($("#fenetre-reglages").open) $("#fenetre-reglages").close();
  document.querySelectorAll('[data-action="connecter"]').forEach((b) => { b.disabled = true; b.innerHTML = `${ICONES.sablier}Connexion…`; });
  try {
    let rep = await api(`/api/jeux/${jeuId}/connexion`, { method: "POST" });
    if (rep.etat === "attente")
      toast(etat.donnees.jeu.connexion_consigne
        || `Une fenêtre ${nom} s'est ouverte : connecte-toi, AllMyStats s'occupe du reste.`, "connexion");
    while (rep.etat === "attente") {
      await new Promise((r) => setTimeout(r, 1500));
      rep = await api(`/api/jeux/${jeuId}/connexion`);
    }
    if (rep.etat !== "ok") throw new Error(rep.message);
    toast(rep.message);
    if (etat.jeuActif === jeuId) {
      etat.donnees = await api(`/api/jeux/${jeuId}`);
      afficherListeJeux();
      afficherJeu();
      actualiser();
    }
  } catch (e) {
    toast(e.message, "erreur");
    if (etat.jeuActif === jeuId) afficherJeu();
  }
}

async function deconnecter() {
  const { jeu } = etat.donnees;
  if (!confirm(`Se déconnecter de ${jeu.connexion} ? Tes stats déjà enregistrées sont gardées.`)) return;
  try {
    const rep = await api(`/api/jeux/${etat.jeuActif}/deconnexion`, { method: "POST" });
    etat.donnees = rep;
    afficherListeJeux();
    afficherJeu();
    toast(rep.message, "info");
  } catch (e) {
    toast(e.message, "erreur");
  }
}

function ouvrirReglages() {
  const { jeu, reglages, connecte, compte } = etat.donnees;
  $("#titre-reglages").innerHTML = `${emblemeJeu(jeu)}Réglages · ${esc(jeu.nom)}`;
  $("#btn-enregistrer").innerHTML = `${ICONES.enregistrer}Enregistrer`;
  const champ = (r) => `
    ${r.section ? `<h3 class="section-reglages">${icone(r.secret ? "cle" : "reglages")}${esc(r.section)}</h3>` : ""}
    <label>${esc(r.nom)}${r.optionnel ? ` <small>(facultatif)</small>` : ""}
      <input name="${esc(r.cle)}" value="${esc(reglages[r.cle] || "")}" autocomplete="off" spellcheck="false" ${r.secret ? `type="password"` : ""}>
      ${r.aide ? `<small class="aide">${esc(r.aide).replace(/\n/g, "<br>")}</small>` : ""}
      ${r.lien ? `<a href="${esc(r.lien)}" target="_blank" rel="noopener">Ouvrir ${esc(r.lien.replace(/^https?:\/\//, ""))}</a>` : ""}
    </label>`;
  const simples = jeu.reglages.filter((r) => !r.avance);
  const avances = jeu.reglages.filter((r) => r.avance);
  $("#champs-reglages").innerHTML = `
    ${jeu.connexion ? `<div class="bloc-connexion">
        ${connecte
          ? `<span class="pill-connecte" style="align-self:flex-start;cursor:default">${ICONES.connecte}Connecté${compte ? `<small>${esc(compte)}</small>` : ""}</span>
             <div style="display:flex;gap:8px;flex-wrap:wrap">
               <button type="button" class="secondaire" data-action="connecter">${ICONES.actualiser}Reconnecter</button>
               <button type="button" class="secondaire" data-action="deconnecter">${ICONES.deconnexion}Se déconnecter</button></div>`
          : `<button type="button" class="principal" data-action="connecter">${ICONES.connexion}Se connecter avec ${esc(jeu.connexion)}</button>
             <small>${esc(jeu.connexion_aide)}</small>`}
      </div>` : ""}
    ${simples.map(champ).join("")}
    ${avances.length ? `<details class="avances"><summary>${ICONES.cle}Réglages avancés (à la main)<span class="chev">${ICONES.chevron}</span></summary>${avances.map(champ).join("")}</details>` : ""}`;
  $("#champs-reglages").querySelectorAll('[data-action="connecter"]').forEach((b) => b.addEventListener("click", connecter));
  $("#champs-reglages").querySelectorAll('[data-action="deconnecter"]').forEach((b) => b.addEventListener("click", () => {
    $("#fenetre-reglages").close(); deconnecter();
  }));
  const fenetre = $("#fenetre-reglages");
  fenetre.showModal();
  fenetre.onclose = async () => {
    if (fenetre.returnValue !== "ok") return;
    const valeurs = Object.fromEntries(new FormData($("#form-reglages")));
    try {
      const rep = await api(`/api/jeux/${etat.jeuActif}/reglages`, { method: "POST", body: valeurs });
      etat.donnees = rep;
      afficherJeu();
      toast(rep.message);
      if (jeu.auto && reglagesComplets()) actualiser();
    } catch (e) {
      toast(e.message, "erreur");
    }
  };
}

// ---------- Blox Fruits : inventaire comme en jeu (onglets + cases de couleur selon la rareté) ----------
function ongletInventaire() {
  try { return localStorage.getItem("bf_onglet") || "tout"; } catch (e) { return "tout"; }
}

function inventaireHtml(inv) {
  const choisi = ongletInventaire();
  const tous = inv.onglets.flatMap((o) => o.objets);
  const liste = choisi === "tout" ? tous : (inv.onglets.find((o) => o.cle === choisi)?.objets || []);
  return `<div class="bf-inventaire">
    <div class="bf-onglets" role="tablist">
      <button role="tab" class="bf-onglet ${choisi === "tout" ? "actif" : ""}" data-bf-onglet="tout">Tout <small>${tous.length}</small></button>
      ${inv.onglets.map((o) => `<button role="tab" class="bf-onglet ${choisi === o.cle ? "actif" : ""}" data-bf-onglet="${esc(o.cle)}">
        ${esc(o.nom)} <small>${o.objets.length}</small></button>`).join("")}
      ${tous.length ? `<button class="discret bf-vider" data-bf-vider>${ICONES.supprimer}Vider</button>` : ""}
    </div>
    <div class="bf-grille">${liste.length ? liste.map((o) => `
      <div class="bf-case r-${esc(o.rarete)}" title="${esc(o.nom)} · ${esc(o.rarete_nom || "")}">
        ${o.image ? `<img src="${esc(o.image)}" alt="" loading="lazy">` : `<span class="bf-sans-image">${ICONES.bf_inventaire}</span>`}
        ${o.qte ? `<span class="bf-qte">x${esc(o.qte)}</span>` : ""}
        <span class="bf-nom">${esc(o.nom)}</span>
        <button class="bf-retirer" data-bf-retirer="${esc(o.id)}" title="Retirer de l'inventaire" aria-label="Retirer ${esc(o.nom)}">${ICONES.fermer}</button>
      </div>`).join("") : `<p class="bf-vide">Rien dans cet onglet pour l'instant. Ouvre-le dans ton inventaire en jeu.</p>`}
    </div>
    ${inv.catalogue ? "" : `<p class="note-details">${ICONES.alerte}<span>Le catalogue du wiki Blox Fruits n'a pas pu être téléchargé : les objets seront reconnus dès qu'il sera disponible.</span></p>`}
  </div>`;
}

function brancherInventaire() {
  document.querySelectorAll("[data-bf-onglet]").forEach((b) => (b.onclick = () => {
    try { localStorage.setItem("bf_onglet", b.dataset.bfOnglet); } catch (e) {}
    $("#details").innerHTML = afficherDetails(etat.donnees.details);
    brancherInventaire();
  }));
  const retirer = async (nom) => {
    try {
      etat.donnees = await api(`/api/jeux/${etat.jeuActif}/inventaire`, { method: "POST", body: { nom } });
      $("#details").innerHTML = afficherDetails(etat.donnees.details);
      brancherInventaire();
    } catch (e) { toast(e.message, "erreur"); }
  };
  document.querySelectorAll("[data-bf-retirer]").forEach((b) => (b.onclick = () => retirer(b.dataset.bfRetirer)));
  document.querySelector("[data-bf-vider]")?.addEventListener("click", () => {
    if (confirmerVider()) retirer(null);
  });
}

function confirmerVider() {
  const b = document.querySelector("[data-bf-vider]");
  if (b.dataset.confirme) return true;
  b.dataset.confirme = "1";
  b.innerHTML = `${ICONES.supprimer}Sûr ? Clique encore`;
  setTimeout(() => { if (b.isConnected) { delete b.dataset.confirme; b.innerHTML = `${ICONES.supprimer}Vider`; } }, 3000);
  return false;
}

// ---------- Page « carte interactive » : la carte s'affiche ici, onglets en haut ----------
function carteChoisie(jeu) {
  let id = null;
  try { id = localStorage.getItem("carte_" + jeu.id); } catch (e) {}
  return (jeu.cartes_en_ligne || []).find((c) => c.id === id) || jeu.cartes_en_ligne?.[0];
}

function afficherPageCarte(jeu) {
  const carte = carteChoisie(jeu);
  $("#contenu").innerHTML = `
    <div class="barre-carte">
      <div class="bc-titre">${emblemeJeu(jeu)}<div><b>${esc(jeu.nom)}</b><small>${esc(jeu.famille || "")}</small></div></div>
      ${(jeu.cartes_en_ligne || []).length > 1 ? `<div class="onglets-carte" role="tablist" aria-label="Choisir la carte">
        ${jeu.cartes_en_ligne.map((c) => `
          <button role="tab" class="onglet ${c.id === carte?.id ? "actif" : ""}" aria-selected="${c.id === carte?.id}"
                  data-onglet="${esc(c.id)}" title="${esc(c.aide)}">${icone(c.icone || "carte_teyvat")}${esc(c.nom)}</button>`).join("")}
      </div>` : ""}
      <div class="actions-carte">
        ${carte?.connexion ? `<button class="principal" id="carte-connexion" title="Ouvre la carte dans sa fenêtre, connectée à ton compte HoYoLAB (pour cocher tes trouvailles)">${ICONES.connexion}${esc(carte.connexion)}</button>` : ""}
        <button class="secondaire" id="carte-navigateur" title="Ouvrir dans ton navigateur habituel (avec tes comptes, Google compris)">${ICONES.jeu}Dans mon navigateur</button>
        <button class="secondaire" id="carte-fenetre" title="Ouvrir dans sa propre fenêtre, en plein écran">${ICONES.ecran}Plein écran</button>
      </div>
    </div>
    <div class="cadre-carte" id="cadre-carte">
      <div class="carte-attente"><div class="rond"></div><p>${esc(jeu.texte_attente || "Chargement de la carte…")}</p></div>
    </div>
    <p class="note-carte">${ICONES.astuce}<span>${carte?.collee
      ? esc(jeu.note_page || "Connecte-toi directement dans la carte (en haut à droite), comme sur le site : ta connexion et tes repères sont gardés.")
      : "Pour te connecter avec Google : « Dans mon navigateur » ouvre cette carte là où tes comptes sont déjà connectés."}</span></p>`;
  document.querySelectorAll("[data-onglet]").forEach((b) => b.addEventListener("click", () => {
    try { localStorage.setItem("carte_" + jeu.id, b.dataset.onglet); } catch (e) {}
    cacherCarteCollee();
    afficherPageCarte(jeu);
  }));
  $("#carte-fenetre").addEventListener("click", () => ouvrirCarteFenetre(jeu, carteChoisie(jeu).id));
  $("#carte-navigateur").addEventListener("click", () => ouvrirCarteFenetre(jeu, carteChoisie(jeu).id, "navigateur"));
  $("#carte-connexion")?.addEventListener("click", () => ouvrirCarteFenetre(jeu, carteChoisie(jeu).id, "connexion"));
  if (carte) chargerCarte(jeu, carte);
}

// ---------- Builds & Teams (Genshin) ----------
// Deux vues plein écran : la grille de tous les persos, puis la fiche du perso choisi.
const ELEMENTS_BUILDS = [["Pyro", "#ef7a35"], ["Hydro", "#4cc2f1"], ["Anemo", "#74c2a8"], ["Electro", "#b08fc2"],
  ["Dendro", "#a5c83b"], ["Cryo", "#9fd6e3"], ["Geo", "#fab632"]];
const ARMES_BUILDS = ["Épée", "Espadon", "Arme d'hast", "Arc", "Catalyseur"];
const builds = { persos: null, filtre: "", element: "", arme: "", rarete: 0, choisi: null, cache: {}, defilement: 0,
  modeEquipe: false, equipe: [], filtreEquipe: "", elementEquipe: "", resultatEquipe: null, demandeEquipe: 0 };
const sansAccents = (t) => String(t || "").toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "");

function persosFiltres() {
  const f = sansAccents(builds.filtre.trim());
  return (builds.persos || []).filter((p) => (!builds.element || p.element === builds.element) &&
    (!builds.arme || p.arme === builds.arme) && (!builds.rarete || p.rarete === builds.rarete) &&
    (!f || sansAccents(p.nom).includes(f)));
}

async function afficherPageBuilds(jeu) {
  if (builds.choisi) return afficherFicheBuild(jeu, builds.choisi);
  if (builds.modeEquipe) return afficherCompleterEquipe(jeu);
  const puce = (attr, valeur, actif, contenu, style = "") =>
    `<button class="puce ${actif ? "actif" : ""}" data-${attr}="${esc(valeur)}" aria-pressed="${actif}" ${style}>${contenu}</button>`;
  $("#contenu").innerHTML = `
    <div class="bt-grille-page">
      <header class="bt-entete">
        <div class="bc-titre">${emblemeJeu(jeu)}<div><b>${esc(jeu.nom)}</b><small>${esc(jeu.famille || "")}</small></div></div>
        <span class="bt-compte" id="bt-compte"></span>
        <button class="bt-bouton-equipe" id="bt-mode-equipe">${ICONES.equipe}<span><b>Composer une équipe</b>
          <small>AMS complète ton équipe et build chaque perso</small></span></button>
      </header>
      <label class="bt-recherche">${ICONES.loupe}<input type="search" id="builds-cherche"
        placeholder="Chercher un perso (Furina, Kazuha…)" autocomplete="off" value="${esc(builds.filtre)}"></label>
      <div class="bt-filtres">
        <div class="bt-groupe" role="group" aria-label="Élément">
          ${puce("element", "", !builds.element, "Tous")}
          ${ELEMENTS_BUILDS.map(([e, c]) => puce("element", e, builds.element === e, `${icone(e.toLowerCase())}${e}`, `style="--el:${c}"`)).join("")}
        </div>
        <div class="bt-groupe" role="group" aria-label="Arme">
          ${ARMES_BUILDS.map((a) => puce("arme", a, builds.arme === a, esc(a))).join("")}
        </div>
        <div class="bt-groupe" role="group" aria-label="Rareté">
          ${[5, 4].map((r) => puce("rarete", r, builds.rarete === r, `<span class="etoiles-puce r${r}">${"★".repeat(r)}</span>`)).join("")}
        </div>
      </div>
      <div class="bt-grille" id="builds-grille"><div class="carte-attente"><div class="rond"></div></div></div>
    </div>`;
  $("#builds-cherche").addEventListener("input", (e) => { builds.filtre = e.target.value; dessinerGrilleBuilds(); });
  $("#bt-mode-equipe").addEventListener("click", () => {
    builds.modeEquipe = true; builds.defilement = document.querySelector("main").scrollTop;
    son("ouvrir"); afficherCompleterEquipe(jeu); document.querySelector("main").scrollTop = 0;
  });
  document.querySelectorAll(".bt-filtres [data-element], .bt-filtres [data-arme], .bt-filtres [data-rarete]").forEach((b) =>
    b.addEventListener("click", () => {
      if (b.dataset.element !== undefined) builds.element = b.dataset.element;
      if (b.dataset.arme !== undefined) builds.arme = builds.arme === b.dataset.arme ? "" : b.dataset.arme;
      if (b.dataset.rarete !== undefined) builds.rarete = builds.rarete === Number(b.dataset.rarete) ? 0 : Number(b.dataset.rarete);
      document.querySelectorAll(".bt-filtres .puce").forEach((x) => {
        const actif = x.dataset.element !== undefined ? x.dataset.element === builds.element
          : x.dataset.arme !== undefined ? x.dataset.arme === builds.arme : Number(x.dataset.rarete) === builds.rarete;
        x.classList.toggle("actif", actif); x.setAttribute("aria-pressed", actif);
      });
      dessinerGrilleBuilds();
    }));
  try {
    if (!builds.persos) builds.persos = (await api(`/api/jeux/${jeu.id}/page/persos`)).persos;
  } catch (e) {
    $("#builds-grille").innerHTML = `<div class="vide">${ICONES.erreur}${esc(e.message)}</div>`;
    return;
  }
  dessinerGrilleBuilds();
  document.querySelector("main").scrollTop = builds.defilement;
}

function dessinerGrilleBuilds() {
  const grille = $("#builds-grille");
  if (!grille || !builds.persos) return;
  const liste = persosFiltres();
  $("#bt-compte").textContent = `${liste.length} perso${liste.length > 1 ? "s" : ""}`;
  grille.innerHTML = liste.length ? liste.map((p) => `
    <button class="bt-perso r${p.rarete}" data-perso="${esc(p.id)}" style="--el:${p.couleur}"
            title="${esc(p.nom)}${p.arme ? " · " + esc(p.arme) : ""}">
      <span class="bt-visuel">${p.image ? `<img src="${esc(p.image)}" alt="" loading="lazy" onerror="this.remove()">` : ""}
        <span class="bt-elem">${icone((p.element || "").toLowerCase())}</span></span>
      <span class="bt-nom">${esc(p.nom)}</span></button>`).join("")
    : `<p class="gris bt-rien">Aucun perso ne correspond à ta recherche.</p>`;
  grille.querySelectorAll("[data-perso]").forEach((b) => b.addEventListener("click", () => {
    builds.defilement = document.querySelector("main").scrollTop;
    afficherFicheBuild(etat.donnees.jeu, b.dataset.perso);
  }));
}

// ================= Amis : code ami et classement =================
const amis = { data: null, jeu: null, edition: false };
const PALETTE_AMIS = ["#FFC44D", "#FF6B5E", "#33D1C1", "#7C8CFF", "#B98CFF", "#5BD67A", "#FF8FC7", "#4CC2F1"];

function depuis(secondes) {
  const s = Math.max(0, Date.now() / 1000 - secondes);
  if (s < 90) return "à l'instant";
  if (s < 3600) return `il y a ${Math.round(s / 60)} min`;
  if (s < 86400) return `il y a ${Math.round(s / 3600)} h`;
  return `il y a ${Math.round(s / 86400)} j`;
}
// Photo de profil : petite image en base64, ou adresse d'une photo de compte de jeu
const photoSure = (v) => typeof v === "string" && /^data:image\/(jpeg|png|webp);base64,[A-Za-z0-9+\/]+={0,2}$/.test(v) && v.length <= 2800
  ? v : urlImage(v);
function pastille(p) {
  const photo = photoSure(p.photo);
  return `<span class="am-pastille ${photo ? "photo" : ""}" style="--c:${esc(p.couleur || "#8a8fa8")}">${photo
    ? `<img src="${photo}" alt="" loading="lazy">` : esc((p.pseudo || "?").trim().charAt(0).toUpperCase())}</span>`;
}

// Une photo choisie sur le PC ou le téléphone -> petite image carrée JPEG (elle doit tenir dans un message)
async function reduirePhoto(fichier) {
  const adresse = URL.createObjectURL(fichier);
  try {
    const img = await new Promise((ok, ko) => { const i = new Image(); i.onload = () => ok(i); i.onerror = ko; i.src = adresse; });
    const cote = Math.min(img.naturalWidth, img.naturalHeight);
    for (const taille of [72, 64, 56, 48, 40]) {
      for (const qualite of [0.85, 0.72, 0.6, 0.5, 0.4]) {
        const c = document.createElement("canvas");
        c.width = c.height = taille;
        const ctx = c.getContext("2d");
        ctx.fillStyle = "#1C2146";
        ctx.fillRect(0, 0, taille, taille);
        ctx.imageSmoothingQuality = "high";
        ctx.drawImage(img, (img.naturalWidth - cote) / 2, (img.naturalHeight - cote) / 2, cote, cote, 0, 0, taille, taille);
        const donnees = c.toDataURL("image/jpeg", qualite);
        if (donnees.length <= 2700) return donnees;
      }
    }
    throw new Error("Cette photo est trop détaillée : essaie-en une autre.");
  } catch (e) {
    throw new Error(e?.message || "Cette image ne s'ouvre pas : choisis une photo JPEG ou PNG.");
  } finally {
    URL.revokeObjectURL(adresse);
  }
}

async function afficherPageAmis(frais = false) {
  etat.jeuActif = "_amis";
  etat.donnees = null;
  fermerMenu();
  cacherCarteCollee();
  $("#titre-mobile").textContent = "Amis";
  document.documentElement.style.setProperty("--accent", "#FFC44D");
  afficherListeJeux();
  if (!amis.data) $("#contenu").innerHTML = `<div class="bt-attente"><div class="rond"></div><p>Chargement de tes amis…</p></div>`;
  try {
    amis.data = await api("/api/amis" + (frais ? "?frais=1" : ""));
  } catch (e) {
    $("#contenu").innerHTML = `<div class="vide">${ICONES.erreur}${esc(e.message)}</div>`;
    return;
  }
  if (etat.jeuActif === "_amis") dessinerPageAmis();
}

async function actionAmis(route, corps, bouton) {
  if (bouton) bouton.disabled = true;
  try {
    const d = await api(`/api/amis/${route}`, { method: "POST", body: corps || {} });
    amis.data = d;
    if (d.message) toast(d.message);
    return true;
  } catch (e) {
    toast(e.message, "erreur");
    return false;
  } finally {
    if (bouton) bouton.disabled = false;
    if (etat.jeuActif === "_amis") dessinerPageAmis();
  }
}

function blocMoiAmis(moi) {
  const partages = moi.jeux_partages;
  const formulaire = (titre, bouton) => `
    <div class="am-form">
      <label class="am-champ"><span>Ton pseudo (ce que tes amis verront)</span>
        <input id="am-pseudo" maxlength="24" value="${esc(moi.pseudo)}" placeholder="Ex. Angelo" autocomplete="off"></label>
      <div class="am-champ"><span>Ta photo de profil</span>
        <div class="am-photo-choix">
          <span id="am-apercu">${pastille(moi)}</span>
          <label class="secondaire am-fichier" tabindex="0">Choisir une photo<input type="file" accept="image/*" id="am-fichier" hidden></label>
          ${(moi.photos_jeux || []).map((p) => `<button type="button" class="discret am-photo-jeu" data-photo-jeu="${esc(p.photo)}"
            title="Prendre ta photo ${esc(p.jeu)}"><img src="${urlImage(p.photo)}" alt="">${esc(p.jeu)}</button>`).join("")}
          <button type="button" class="discret" id="am-sans-photo">Sans photo</button>
        </div></div>
      <div class="am-champ"><span>Ta couleur</span>
        <div class="am-couleurs" role="radiogroup" aria-label="Couleur">${PALETTE_AMIS.map((c) => `<button type="button" role="radio"
          aria-checked="${c === moi.couleur}" aria-label="${c}" data-couleur="${c}" style="--c:${c}"></button>`).join("")}</div></div>
      <details class="am-jeux" ${partages ? "open" : ""}><summary>Jeux partagés : ${partages ? `${partages.length} sur ${moi.jeux_disponibles.length}` : "tous"}</summary>
        <div>${moi.jeux_disponibles.map((j) => `<label class="interrupteur"><input type="checkbox" data-jeu-partage="${esc(j.id)}"
          ${!partages || partages.includes(j.id) ? "checked" : ""}><span>${icone(j.icone || "jeu_" + j.id, ICONES.jeu)}${esc(j.nom)}</span></label>`).join("")}</div>
      </details>
      <p class="am-prive">${ICONES.astuce}<span>Seuls ton pseudo, ta photo et la dernière valeur de tes stats sont partagés, chiffrés :
        seuls tes amis acceptés peuvent les lire. Jamais tes connexions, tes UID ou ton historique.</span></p>
      <div class="am-boutons"><button class="principal" id="am-valider">${bouton}</button>
        ${titre ? `<button class="discret" id="am-annuler">Annuler</button>` : ""}</div>
    </div>`;
  if (moi.mobile && !moi.code) return `<section class="bt-bloc am-moi"><h3>${ICONES.amis}Ton profil</h3>
    <p class="gris">Ton profil d'amis se règle et se publie depuis AllMyStats sur ton PC. Ici, tu peux ajouter des amis et voir le classement.</p></section>`;
  if (!moi.actif || amis.edition) return `<section class="bt-bloc am-moi">
    <h3>${ICONES.amis}${moi.actif ? "Modifier ton profil" : "Partage tes stats avec tes amis"}</h3>
    ${moi.actif ? "" : `<p class="am-intro">Choisis un pseudo : AllMyStats te donne un code ami. Échange vos codes avec tes amis qui ont
      AllMyStats, envoyez-vous une demande, et une fois acceptée vous êtes dans le même classement.</p>`}
    ${formulaire(moi.actif, moi.actif ? "Enregistrer" : "Partager mes stats")}
  </section>`;
  return `<section class="bt-bloc am-moi">
    <div class="am-moi-tete">${pastille(moi)}<div><b>${esc(moi.pseudo)}</b>
      <small>${moi.mobile ? "Publié depuis ton PC" : moi.erreur ? `<span class="rouge">${esc(moi.erreur)}</span>` : moi.publie_le ? `Profil publié ${depuis(moi.publie_le)}` : "Pas encore publié"}</small></div></div>
    <div class="am-code"><span>Ton code ami</span><b id="am-mon-code">${esc(moi.code || "…")}</b>
      <button class="secondaire" id="am-copier" ${moi.code ? "" : "disabled"}>Copier</button></div>
    <p class="am-note">Donne ce code à tes amis : ils t'envoient une demande, tu l'acceptes, et vous voyez vos stats des deux côtés.
      Seuls tes amis acceptés peuvent les lire.</p>
    ${moi.mobile ? "" : `<div class="am-boutons">
      <button class="secondaire" id="am-publier">Publier maintenant</button>
      <button class="discret" id="am-modifier">Modifier le profil</button>
      <button class="discret" id="am-arreter">Arrêter de partager</button></div>`}
  </section>`;
}

// La barre de gauche : nombre d'amis, ou les demandes reçues en évidence
function majBadgeAmis(demandes, nbAmis) {
  const sous = $("#amis-sous");
  if (!sous) return;
  sous.textContent = demandes ? `${demandes} demande${demandes > 1 ? "s" : ""} d'ami${demandes > 1 ? "s" : ""}`
    : nbAmis ? `${nbAmis} ami${nbAmis > 1 ? "s" : ""}` : "Classement entre amis";
  $("#btn-amis").classList.toggle("a-demandes", demandes > 0);
}

function dessinerPageAmis() {
  const d = amis.data;
  const moi = d.moi;
  const moiProfil = { ...d.mon_profil, pseudo: moi.pseudo || "Toi", couleur: moi.couleur, moi: true };
  const amisOk = d.amis.filter((a) => !a.erreur && !a.ferme);
  const listeAmis = d.amis.map((a) => `
    <li class="${a.erreur || a.ferme ? "souci" : ""}">${pastille(a)}<div><b>${esc(a.pseudo)}</b>
      <small ${a.avertissement ? `title="${esc(a.avertissement)}"` : ""}>${a.erreur ? esc(a.erreur) : a.ferme ? "N'est plus en partage"
        : a.maj ? `Stats du ${esc(dateLongue(a.maj))}${a.avertissement ? " (dernières connues)" : ""}` : ""}</small></div>
      ${moi.mobile ? "" : `<button class="am-retirer" data-retirer="${esc(a.id)}" title="Retirer ${esc(a.pseudo)}" aria-label="Retirer ${esc(a.pseudo)}">×</button>`}</li>`).join("");
  const recues = (d.recues || []).map((a) => `
    <li>${pastille(a)}<div><b>${esc(a.pseudo)}</b><small>veut être ton ami${a.le ? ` · ${esc(depuis(a.le))}` : ""}</small></div>
      ${moi.mobile ? "" : `<button class="principal" data-accepter="${esc(a.id)}">Accepter</button>
      <button class="discret" data-refuser="${esc(a.id)}">Refuser</button>`}</li>`).join("");
  const envoyees = (d.envoyees || []).map((a) => `
    <li class="am-attente"><span class="am-pastille am-sablier" style="--c:#3a4383">…</span><div><b>${esc(a.code)}</b>
      <small>En attente de sa réponse${a.le ? ` · demande ${esc(depuis(a.le))}` : ""}</small></div>
      ${moi.mobile ? "" : `<button class="discret" data-annuler="${esc(a.id)}">Annuler</button>`}</li>`).join("");
  majBadgeAmis(d.recues?.length || 0, d.amis.length);
  (d.notifs || []).forEach((n, i) => setTimeout(() => toast(n, "info"), 400 + i * 2200));

  // Les jeux du classement : ceux où au moins un ami a des stats
  const joueurs = [moiProfil, ...amisOk];
  const jeuxClasses = [];
  for (const p of amisOk) for (const j of p.jeux) if (!jeuxClasses.some((x) => x.id === j.id)) jeuxClasses.push(j);
  if (!jeuxClasses.some((j) => j.id === amis.jeu)) amis.jeu = jeuxClasses[0]?.id || null;

  $("#contenu").innerHTML = `
    <div class="am-page">
      <header class="am-entete">
        <h2>Amis</h2>
        <p>Compare tes stats avec tes amis qui ont AllMyStats, jeu par jeu.</p>
        <button class="discret" id="am-rafraichir">${ICONES.actualiser || ""}Rafraîchir</button>
      </header>
      ${recues ? `<section class="bt-bloc am-demandes">
        <h3>${ICONES.amis}Demandes d'amis <span class="am-nb">${d.recues.length}</span></h3>
        <ul class="am-liste">${recues}</ul>
        <p class="am-note">En acceptant, vous devenez amis des deux côtés : chacun voit les stats de l'autre.</p>
      </section>` : ""}
      <div class="am-haut">
        ${blocMoiAmis(moi)}
        <section class="bt-bloc am-ajout">
          <h3>${ICONES.ajouter || ICONES.amis}Ajouter un ami</h3>
          ${moi.mobile ? `<p class="gris am-vide">Les demandes d'amis s'envoient et s'acceptent depuis AllMyStats sur ton PC.</p>`
          : !moi.actif ? `<p class="gris am-vide">Choisis d'abord ton pseudo à gauche : il te faut un profil pour envoyer des demandes.</p>`
          : `<form id="am-form-ajout" class="am-ajout-ligne">
              <input id="am-code-ami" placeholder="Colle son code ami (AMS-…)" autocomplete="off" spellcheck="false">
              <button class="principal">Envoyer la demande</button>
            </form>`}
          ${envoyees ? `<ul class="am-liste am-envoyees">${envoyees}</ul>` : ""}
          ${listeAmis ? `<h4 class="am-sous-titre">Tes amis</h4><ul class="am-liste">${listeAmis}</ul>`
            : `<p class="gris am-vide">Pas encore d'ami. Envoie une demande avec son code ami : il l'accepte dans la page Amis de son AllMyStats.</p>`}
        </section>
      </div>
      <section class="am-classement">
        <h3>${ICONES.podium}Classement</h3>
        ${jeuxClasses.length ? `
          <div class="bt-groupe am-jeux-choix" role="group" aria-label="Jeu">${jeuxClasses.map((j) => `<button class="puce ${j.id === amis.jeu ? "actif" : ""}"
            data-jeu-classement="${esc(j.id)}" aria-pressed="${j.id === amis.jeu}" style="--el:${esc(j.couleur)}">${icone(j.icone || "jeu_" + j.id, ICONES.jeu)}${esc(j.nom)}</button>`).join("")}</div>
          <div id="am-podium"></div>`
        : `<div class="vide am-vide-classement">${ICONES.podium}<span>${d.amis.length ? "Tes amis n'ont pas encore de stats partagées." : "Ajoute un ami avec son code pour voir le classement."}</span></div>`}
      </section>
    </div>`;
  if (amis.jeu) dessinerClassement(joueurs, d.moins_c_est_mieux || []);

  // Événements
  $("#am-rafraichir").onclick = () => { son("clic"); afficherPageAmis(true); };
  const formAjout = $("#am-form-ajout");
  if (formAjout) formAjout.onsubmit = async (e) => {
    e.preventDefault();
    const code = $("#am-code-ami").value.trim();
    if (!code) return toast("Colle d'abord le code ami (il commence par AMS-).", "info");
    await actionAmis("ajouter", { code }, e.submitter);
  };
  document.querySelectorAll("[data-retirer]").forEach((b) => b.onclick = () => {
    const a = d.amis.find((x) => x.id === b.dataset.retirer);
    if (confirm(`Retirer ${a?.pseudo || "cet ami"} ? Vous ne serez plus amis des deux côtés, et il ne verra plus tes stats.`))
      actionAmis("retirer", { id: b.dataset.retirer });
  });
  document.querySelectorAll("[data-accepter]").forEach((b) => b.onclick = () => { son("succes"); actionAmis("accepter", { id: b.dataset.accepter }, b); });
  document.querySelectorAll("[data-refuser]").forEach((b) => b.onclick = () => actionAmis("refuser", { id: b.dataset.refuser }, b));
  document.querySelectorAll("[data-annuler]").forEach((b) => b.onclick = () => actionAmis("annuler", { id: b.dataset.annuler }, b));
  document.querySelectorAll("[data-jeu-classement]").forEach((b) => b.onclick = () => {
    amis.jeu = b.dataset.jeuClassement; son("onglet"); dessinerPageAmis();
  });
  $("#am-copier")?.addEventListener("click", async () => {
    try { await navigator.clipboard.writeText(moi.code); toast("Code ami copié : envoie-le à tes amis !"); }
    catch (e) { const r = document.createRange(); r.selectNodeContents($("#am-mon-code")); getSelection().removeAllRanges(); getSelection().addRange(r);
      toast("Sélectionné : fais Ctrl+C pour le copier.", "info"); }
  });
  $("#am-publier")?.addEventListener("click", (e) => actionAmis("publier", {}, e.currentTarget));
  $("#am-modifier")?.addEventListener("click", () => { amis.edition = true; dessinerPageAmis(); });
  $("#am-arreter")?.addEventListener("click", (e) => {
    if (confirm("Arrêter de partager ? Tes amis seront retirés des deux côtés, et tu auras un nouveau code si tu reviens.")) actionAmis("arreter", {}, e.currentTarget);
  });
  let couleur = moi.couleur, photo = moi.photo || "";
  const apercu = () => { const a = $("#am-apercu"); if (a) a.innerHTML = pastille({ pseudo: $("#am-pseudo")?.value || moi.pseudo, couleur, photo }); };
  document.querySelectorAll(".am-couleurs [data-couleur]").forEach((b) => b.onclick = () => {
    couleur = b.dataset.couleur;
    document.querySelectorAll(".am-couleurs [data-couleur]").forEach((x) => x.setAttribute("aria-checked", String(x === b)));
    apercu();
  });
  $("#am-pseudo")?.addEventListener("input", apercu);
  $("#am-fichier")?.addEventListener("change", async (e) => {
    const f = e.target.files?.[0];
    if (!f) return;
    try { photo = await reduirePhoto(f); apercu(); son("clic"); }
    catch (err) { toast(err.message, "erreur"); }
    e.target.value = "";
  });
  document.querySelector(".am-fichier")?.addEventListener("keydown", (e) => {
    if (e.key === "Enter" || e.key === " ") { e.preventDefault(); $("#am-fichier").click(); }
  });
  document.querySelectorAll("[data-photo-jeu]").forEach((b) => b.onclick = () => { photo = b.dataset.photoJeu; apercu(); son("clic"); });
  $("#am-sans-photo")?.addEventListener("click", () => { photo = ""; apercu(); });
  $("#am-annuler")?.addEventListener("click", () => { amis.edition = false; dessinerPageAmis(); });
  $("#am-valider")?.addEventListener("click", async (e) => {
    const cases = [...document.querySelectorAll("[data-jeu-partage]")];
    const coches = cases.filter((c) => c.checked).map((c) => c.dataset.jeuPartage);
    const ok = await actionAmis("reglages", {
      pseudo: $("#am-pseudo").value, couleur, photo, actif: true,
      ...(coches.length === cases.length ? { tous_les_jeux: true } : { jeux_partages: coches }),
    }, e.currentTarget);
    if (ok) { amis.edition = false; dessinerPageAmis(); }
  });
}

function dessinerClassement(joueurs, moinsMieux) {
  const zone = $("#am-podium");
  // Toutes les stats de ce jeu qu'au moins 2 joueurs ont
  const stats = [];
  for (const p of joueurs) {
    const j = p.jeux.find((x) => x.id === amis.jeu);
    for (const s of j?.stats || []) if (!stats.some((x) => x.cle === s.cle)) stats.push(s);
  }
  const cartes = [];
  const premiers = new Map();
  for (const s of stats) {
    const moins = moinsMieux.includes(s.cle);
    const lignes = joueurs.map((p) => ({ p, v: p.jeux.find((x) => x.id === amis.jeu)?.stats.find((x) => x.cle === s.cle)?.valeur }))
      .filter((l) => typeof l.v === "number");
    if (lignes.length < 2) continue;
    lignes.sort((a, b) => moins ? a.v - b.v : b.v - a.v);
    let rang = 0;
    lignes.forEach((l, i) => { if (i === 0 || l.v !== lignes[i - 1].v) rang = i + 1; l.rang = rang; });
    lignes.filter((l) => l.rang === 1).forEach((l) => premiers.set(l.p, (premiers.get(l.p) || 0) + 1));
    const max = Math.max(...lignes.map((l) => Math.abs(l.v))) || 1;
    const min = Math.min(...lignes.map((l) => Math.abs(l.v)));
    cartes.push(`<article class="am-stat">
      <h4>${s.icone ? icone(s.icone) : ""}<span>${esc(s.nom)}</span>${moins ? `<small>moins, c'est mieux</small>` : ""}</h4>
      <ol>${lignes.map((l) => {
        const part = moins ? (min || 0.0001) / (Math.abs(l.v) || 0.0001) : Math.abs(l.v) / max;
        return `<li class="${l.p.moi ? "moi" : ""} r${Math.min(l.rang, 4)}">
          <span class="am-rang">${l.rang}</span>${pastille(l.p)}
          <span class="am-nom">${esc(l.p.moi ? `${l.p.pseudo} (toi)` : l.p.pseudo)}</span>
          <b>${esc(nombre(l.v, s))}</b>
          <span class="am-barre"><i style="width:${Math.max(4, Math.round(part * 100))}%;--c:${esc(l.p.couleur)}"></i></span></li>`;
      }).join("")}</ol></article>`);
  }
  if (!cartes.length) {
    zone.innerHTML = `<div class="vide">${ICONES.astuce}<span>Pas encore de stat en commun sur ce jeu : il faut qu'au moins deux d'entre vous aient la même stat.</span></div>`;
    return;
  }
  const champion = [...premiers.entries()].sort((a, b) => b[1] - a[1]);
  const [chef, nb] = champion[0] || [];
  const egalite = champion.length > 1 && champion[1][1] === nb;
  zone.innerHTML = `
    ${chef ? `<div class="am-champion" style="--c:${esc(chef.couleur)}">${ICONES.podium}<div>
      <b>${egalite ? "Égalité en tête !" : `${esc(chef.moi ? "Tu es" : chef.pseudo + " est")} en tête`}</b>
      <span>${egalite ? champion.filter((c) => c[1] === nb).map((c) => esc(c[0].moi ? "toi" : c[0].pseudo)).join(", ") + ` : ${nb} première${nb > 1 ? "s" : ""} place${nb > 1 ? "s" : ""} chacun`
        : `${nb} première${nb > 1 ? "s" : ""} place${nb > 1 ? "s" : ""} sur ${cartes.length} stat${cartes.length > 1 ? "s" : ""}`}</span></div></div>` : ""}
    <div class="am-stats">${cartes.join("")}</div>`;
}

// ---------- Compléter une équipe : jusqu'à 3 persos choisis, AMS propose les meilleurs coéquipiers ----------
const persoBuild = (id) => builds.persos?.find((p) => p.id === id);

async function afficherCompleterEquipe(jeu) {
  $("#contenu").innerHTML = `
    <div class="bt-grille-page bt-eq-page">
      <div class="bt-nav" role="navigation" aria-label="Navigation">
        <button class="secondaire" id="bt-eq-retour">${ICONES.retour}Tous les persos</button>
        <button class="discret" id="bt-eq-vider" ${builds.equipe.length ? "" : "hidden"}>Tout retirer</button>
      </div>
      <header class="bt-eq-entete">
        <h2>Composer une équipe</h2>
        <p>Choisis de 1 à 3 persos : AllMyStats te propose ceux qui vont le mieux avec eux, d'après les équipes
          conseillées par Genshin-Builds. Choisis-en 4 : tu obtiens le build de chacun, avec des alternatives et
          les ajustements pour que l'équipe marche ensemble.</p>
      </header>
      <div class="bt-eq-slots" id="bt-eq-slots"></div>
      <div id="bt-eq-resultats"></div>
      <section class="bt-eq-choix">
        <h3>${ICONES.loupe}Choisir un perso <small id="bt-eq-reste"></small></h3>
        <label class="bt-recherche">${ICONES.loupe}<input type="search" id="eq-cherche"
          placeholder="Chercher un perso…" autocomplete="off" value="${esc(builds.filtreEquipe)}"></label>
        <div class="bt-groupe bt-eq-elements" role="group" aria-label="Élément">
          <button class="puce ${builds.elementEquipe ? "" : "actif"}" data-el="">Tous</button>
          ${ELEMENTS_BUILDS.map(([e, c]) => `<button class="puce ${builds.elementEquipe === e ? "actif" : ""}" data-el="${esc(e)}"
            style="--el:${c}">${icone(e.toLowerCase())}${e}</button>`).join("")}
        </div>
        <div class="bt-grille bt-grille-mini" id="eq-grille"><div class="carte-attente"><div class="rond"></div></div></div>
      </section>
      <button class="bt-eq-voir" id="bt-eq-voir" hidden></button>
    </div>`;
  // Quand on choisit des persos tout en bas, un bouton flottant remonte vers l'équipe proposée
  const voir = $("#bt-eq-voir");
  voir.addEventListener("click", () => $("#bt-eq-slots").scrollIntoView({ behavior: mouvementReduit() ? "auto" : "smooth", block: "start" }));
  if ("IntersectionObserver" in window) {
    new IntersectionObserver(([e]) => { voir.dataset.horsVue = e.isIntersecting ? "" : "1"; majBoutonVoir(); })
      .observe($("#bt-eq-slots"));
  }
  $("#bt-eq-retour").addEventListener("click", () => { builds.modeEquipe = false; son("fermer"); afficherPageBuilds(jeu); });
  $("#bt-eq-vider").addEventListener("click", () => { builds.equipe = []; builds.resultatEquipe = null; majEquipe(); });
  $("#eq-cherche").addEventListener("input", (e) => { builds.filtreEquipe = e.target.value; dessinerChoixEquipe(); });
  document.querySelectorAll(".bt-eq-elements [data-el]").forEach((b) => b.addEventListener("click", () => {
    builds.elementEquipe = b.dataset.el;
    document.querySelectorAll(".bt-eq-elements .puce").forEach((x) => x.classList.toggle("actif", x === b));
    dessinerChoixEquipe();
  }));
  try {
    if (!builds.persos) builds.persos = (await api(`/api/jeux/${jeu.id}/page/persos`)).persos;
  } catch (e) {
    $("#eq-grille").innerHTML = `<div class="vide">${ICONES.erreur}${esc(e.message)}</div>`;
    return;
  }
  majEquipe(true);
}

function basculerEquipe(id) {
  const i = builds.equipe.indexOf(id);
  if (i >= 0) builds.equipe.splice(i, 1);
  else if (builds.equipe.length >= 4) return toast("Ton équipe a déjà 4 persos : retire-en un pour en changer.", "info");
  else builds.equipe.push(id);
  son(i >= 0 ? "fermer" : "clic");
  majEquipe();
}

function majEquipe(garder) {
  if (!$("#bt-eq-slots")) return;
  const r = builds.resultatEquipe;
  const encoreValable = r && r.cle === builds.equipe.join(",");
  if (!garder || !encoreValable) builds.resultatEquipe = encoreValable ? r : null;
  $("#bt-eq-vider").hidden = !builds.equipe.length;
  const reste = 4 - builds.equipe.length;
  $("#bt-eq-reste").textContent = reste ? `encore ${reste} place${reste > 1 ? "s" : ""}` : "équipe complète";
  dessinerSlotsEquipe();
  dessinerChoixEquipe();
  dessinerResultatsEquipe();
  majBoutonVoir();
  if (builds.equipe.length && !builds.resultatEquipe) chercherEquipe();
}

async function chercherEquipe() {
  const cle = builds.equipe.join(",");
  const numero = ++builds.demandeEquipe;
  try {
    const quoi = builds.equipe.length === 4 ? "builds_equipe" : "equipe";
    const d = await api(`/api/jeux/genshin_builds/page/${quoi}/${encodeURIComponent(cle)}`);
    if (numero !== builds.demandeEquipe) return;
    builds.resultatEquipe = { ...d, cle, complete: builds.equipe.length === 4 };
  } catch (e) {
    if (numero !== builds.demandeEquipe) return;
    builds.resultatEquipe = { cle, erreur: e.message };
  }
  dessinerSlotsEquipe();
  dessinerResultatsEquipe();
  majBoutonVoir();
}

function majBoutonVoir() {
  const voir = $("#bt-eq-voir");
  if (!voir) return;
  const n = builds.equipe.length, r = builds.resultatEquipe;
  voir.hidden = !n || !voir.dataset.horsVue;
  const noms = builds.equipe.map((id) => persoBuild(id)?.nom || id).join(" + ");
  voir.innerHTML = `${ICONES.equipe}<span><b>${esc(noms)}</b><small>${!r ? "Recherche en cours…"
    : r.erreur ? "Voir le problème" : n === 4 ? "Voir les builds de l'équipe" : "Voir les coéquipiers proposés"}</small></span><i>↑</i>`;
}

function dessinerSlotsEquipe() {
  const zone = $("#bt-eq-slots");
  if (!zone) return;
  const r = builds.resultatEquipe;
  const proposes = (r?.proposition || []).filter((p) => p.propose);
  const cases = [];
  for (let i = 0; i < 4; i++) {
    const id = builds.equipe[i];
    if (id) {
      const p = persoBuild(id) || { id, nom: id };
      cases.push(`<div class="bt-slot choisi r${p.rarete || 4}" style="--el:${p.couleur || "var(--accent)"}">
        <span class="bt-visuel">${p.image ? `<img src="${esc(p.image)}" alt="">` : ""}<span class="bt-elem">${icone((p.element || "").toLowerCase())}</span></span>
        <span class="bt-nom">${esc(p.nom)}</span>
        <button class="bt-slot-retirer" data-retirer="${esc(id)}" title="Retirer ${esc(p.nom)}" aria-label="Retirer ${esc(p.nom)}">×</button></div>`);
      continue;
    }
    const prop = proposes[i - builds.equipe.length];
    if (prop) {
      cases.push(`<button class="bt-slot propose r${prop.rarete || 4}" data-ajouter="${esc(prop.id)}" style="--el:${prop.couleur || "var(--or)"}"
          title="Ajouter ${esc(prop.nom)} à ton équipe">
        <span class="bt-visuel">${prop.image ? `<img src="${esc(prop.image)}" alt="">` : ""}<span class="bt-elem">${icone((prop.element || "").toLowerCase())}</span>
          <em class="bt-slot-tag">${ICONES.etincelle || ""}Proposé</em></span>
        <span class="bt-nom">${esc(prop.nom)}</span></button>`);
      continue;
    }
    const attente = builds.equipe.length && !r;
    cases.push(`<div class="bt-slot vide">${attente ? `<div class="rond"></div>` : `<b>+</b>`}
      <span>${attente ? "Recherche…" : i === builds.equipe.length ? "Choisis un perso plus bas" : "Libre"}</span></div>`);
  }
  const propositionComplete = proposes.length && builds.equipe.length + proposes.length === 4;
  zone.innerHTML = cases.join("") + (propositionComplete ? `
    <button class="bt-eq-prendre" id="bt-eq-prendre">${ICONES.ok}<span><b>Prendre cette équipe</b>
      <small>et voir le build de chaque perso</small></span></button>` : "");
  $("#bt-eq-prendre")?.addEventListener("click", () => {
    builds.equipe = r.proposition.map((p) => p.id);
    son("succes");
    majEquipe();
  });
  zone.querySelectorAll("[data-retirer]").forEach((b) => b.addEventListener("click", () => basculerEquipe(b.dataset.retirer)));
  zone.querySelectorAll("[data-ajouter]").forEach((b) => b.addEventListener("click", () => {
    basculerEquipe(b.dataset.ajouter);
  }));
}

function ouvrirBuildDepuisEquipe(id) {
  builds.defilement = 0;
  son("ouvrir");
  afficherFicheBuild(etat.donnees.jeu, id);
}

function dessinerResultatsEquipe() {
  const zone = $("#bt-eq-resultats");
  if (!zone) return;
  const r = builds.resultatEquipe;
  if (!builds.equipe.length) { zone.innerHTML = ""; return; }
  if (!r) { zone.innerHTML = `<div class="bt-attente"><div class="rond"></div><p>Recherche des meilleurs coéquipiers…</p></div>`; return; }
  if (r.erreur) { zone.innerHTML = `<div class="vide">${ICONES.erreur}${esc(r.erreur)}</div>`; return; }
  if (r.complete) return dessinerBuildsEquipe(zone, r);
  const plein = builds.equipe.length >= 4;
  const manque = r.manquants?.length
    ? `<p class="bt-eq-note">${ICONES.astuce}Genshin-Builds n'a pas encore d'équipes conseillées pour ${esc(r.manquants.join(", "))} : AllMyStats se base sur les autres persos choisis.</p>` : "";
  const sugg = (r.suggestions || []).map((p) => `
    <li style="--el:${p.couleur || "var(--accent)"}">
      ${vignetteBuild(p)}
      <div class="bt-eq-sugg-texte">
        <b>${p.element ? icone(p.element.toLowerCase()) : ""}${esc(p.nom)}</b>
        <span class="bt-eq-jauge" title="${p.score} %"><i style="width:${Math.max(6, p.score)}%"></i></span>
        <small>${esc(p.avis)} · dans ${p.nb_equipes} équipe${p.nb_equipes > 1 ? "s" : ""} conseillée${p.nb_equipes > 1 ? "s" : ""}${p.equipes_vues?.length ? ` (${esc(p.equipes_vues.join(", "))})` : ""}</small>
      </div>
      <div class="bt-eq-actions">
        <button class="secondaire" data-ajouter="${esc(p.id)}" ${plein ? "disabled title='Ton équipe est complète'" : ""}>+ Ajouter</button>
        <button class="discret" data-build="${esc(p.id)}">Build</button>
      </div>
    </li>`).join("");
  const equipes = (r.equipes || []).map((t) => `
    <li class="bt-equipe ${t.complete ? "complete" : ""}">
      <div class="bt-membres">${t.membres.map((m) => `<button class="bt-membre ${m.choisi ? "choisi" : ""}" data-build="${esc(m.id)}"
        title="Voir le build de ${esc(m.nom)}" style="--el:${m.couleur || "var(--accent)"}">${vignetteBuild(m)}<small>${esc(m.nom)}</small></button>`).join("")}</div>
      <p>${esc(t.nom)}${t.complete ? "" : ` · ${t.communs} de tes persos`}</p>
    </li>`).join("");
  zone.innerHTML = `${manque}
    ${sugg ? `<section class="bt-bloc bt-eq-sugg"><h3>${ICONES.equipe}Meilleurs coéquipiers <small>du plus conseillé au moins conseillé</small></h3><ol>${sugg}</ol></section>`
      : `<div class="vide">${ICONES.astuce}Pas assez d'équipes conseillées pour proposer des coéquipiers à cette sélection.</div>`}
    ${equipes ? `<section class="bt-equipes bt-eq-connues"><h3>${ICONES.equipe}Équipes conseillées avec ta sélection</h3><ul>${equipes}</ul></section>` : ""}
    <p class="bt-source">Équipes conseillées par <a href="https://genshin-builds.com/fr" target="_blank" rel="noopener">Genshin-Builds</a>, classées par AllMyStats.</p>`;
  zone.querySelectorAll("[data-ajouter]").forEach((b) => b.addEventListener("click", () => basculerEquipe(b.dataset.ajouter)));
  zone.querySelectorAll("[data-build]").forEach((b) => b.addEventListener("click", () => ouvrirBuildDepuisEquipe(b.dataset.build)));
}

function dessinerBuildsEquipe(zone, r) {
  const rang = (liste) => `<ol class="bt-rang">${liste.map((x) => `<li>${esc(x)}</li>`).join("")}</ol>`;
  const optionArtefacts = (o) => `<span class="bt-pieces">${esc(o.pieces)}</span>
    <span class="bt-sets">${o.ensembles.map((e) => `<b>${esc(e)}</b>`).join("")}</span>`;
  const resonances = (r.resonances || []).map((x) => `
    <li style="--el:${(ELEMENTS_BUILDS.find(([e]) => e === x.element) || [])[1] || "var(--or)"}">
      ${x.element ? icone(x.element.toLowerCase()) : ICONES.etoile || ""}<b>${esc(x.nom)}</b><span>${esc(x.effet)}</span></li>`).join("");
  const cartes = (r.membres || []).map((m) => {
    if (m.erreur) return `<article class="bt-eq-carte" style="--el:${m.couleur || "var(--accent)"}">
      <header>${vignetteBuild(m)}<div><h4>${esc(m.nom)}</h4></div></header>
      <p class="bt-eq-adapte">${ICONES.erreur}<span>${esc(m.erreur)}</span></p></article>`;
    const arme = m.armes?.[m.arme_choisie], autresArmes = (m.armes || []).filter((_, i) => i !== m.arme_choisie).slice(0, 4);
    const art = m.artefacts?.[m.artefact_choisi], autresArt = (m.artefacts || []).filter((_, i) => i !== m.artefact_choisi).slice(0, 3);
    const adapte = `<em class="bt-eq-tag">Adapté à l'équipe</em>`;
    return `<article class="bt-eq-carte" style="--el:${m.couleur || "var(--accent)"}">
      <header>
        ${vignetteBuild(m)}
        <div><h4>${m.element ? icone(m.element.toLowerCase()) : ""}${esc(m.nom)}</h4>${m.role ? `<small>${esc(m.role)}</small>` : ""}</div>
        <button class="discret" data-build="${esc(m.id)}">Fiche complète</button>
      </header>
      ${(m.adaptations || []).map((t) => `<p class="bt-eq-adapte">${ICONES.astuce}<span>${esc(t)}</span></p>`).join("")}
      ${arme ? `<section><h5>${ICONES.arme}Arme</h5>
        <div class="bt-eq-top">${vignetteBuild(arme)}<b>${esc(arme.nom)}</b>${m.arme_choisie ? adapte : ""}</div>
        ${autresArmes.length ? `<p class="bt-eq-alt"><span>Alternatives</span>${autresArmes.map((a) => esc(a.nom)).join(" · ")}</p>` : ""}
      </section>` : ""}
      ${art ? `<section><h5>${ICONES.artefact}Artefacts</h5>
        <div class="bt-eq-top bt-eq-art">${optionArtefacts(art)}${m.artefact_choisi ? adapte : ""}</div>
        ${autresArt.length ? `<p class="bt-eq-alt"><span>Alternatives</span>${autresArt.map((o) => `${esc(o.ensembles.join(" + "))} (${esc(o.pieces)})`).join(" · ")}</p>` : ""}
      </section>` : ""}
      ${m.stats?.length ? `<section><h5>${ICONES.graphique}Stats principales</h5>
        <dl class="bt-eq-stats">${m.stats.map((x) => `<dt>${esc(x.piece)}</dt><dd><b>${esc(x.valeurs[0] || "")}</b>${x.valeurs.length > 1
          ? `<small>ou ${esc(x.valeurs.slice(1).join(", "))}</small>` : ""}</dd>`).join("")}</dl>
      </section>` : ""}
      ${m.sous_stats?.length ? `<section><h5>Sous-stats à viser</h5>${rang(m.sous_stats)}</section>` : ""}
      ${m.aptitudes?.length ? `<section><h5>Aptitudes à monter</h5>${rang(m.aptitudes)}</section>` : ""}
      ${m.autres_roles?.length ? `<p class="bt-eq-roles">Autre${m.autres_roles.length > 1 ? "s" : ""} façon${m.autres_roles.length > 1 ? "s" : ""} de le jouer : ${esc(m.autres_roles.join(", "))} (dans la fiche complète)</p>` : ""}
    </article>`;
  }).join("");
  zone.innerHTML = `
    <section class="bt-bloc bt-eq-resume">
      <h3>${ICONES.equipe}Ce qui fait marcher ton équipe</h3>
      ${resonances ? `<ul class="bt-eq-reso">${resonances}</ul>` : `<p class="gris">Pas de résonance élémentaire avec ces 4 persos.</p>`}
      ${r.notes?.length ? `<ul class="bt-eq-notes">${r.notes.map((t) => `<li>${ICONES.astuce}<span>${esc(t)} Les builds plus bas en tiennent compte.</span></li>`).join("")}</ul>`
        : `<p class="bt-eq-ok">${ICONES.ok}<span>Aucun conflit : chaque perso peut garder son meilleur build.</span></p>`}
    </section>
    <div class="bt-eq-cartes">${cartes}</div>
    <p class="bt-source">Builds conseillés par <a href="https://genshin-builds.com/fr" target="_blank" rel="noopener">Genshin-Builds</a>, adaptés à ton équipe par AllMyStats.</p>`;
  zone.querySelectorAll("[data-build]").forEach((b) => b.addEventListener("click", () => ouvrirBuildDepuisEquipe(b.dataset.build)));
}

function dessinerChoixEquipe() {
  const grille = $("#eq-grille");
  if (!grille || !builds.persos) return;
  const f = sansAccents(builds.filtreEquipe.trim());
  const liste = builds.persos.filter((p) => (!builds.elementEquipe || p.element === builds.elementEquipe) && (!f || sansAccents(p.nom).includes(f)));
  grille.innerHTML = liste.length ? liste.map((p) => {
    const choisi = builds.equipe.includes(p.id);
    return `<button class="bt-perso r${p.rarete} ${choisi ? "choisi" : ""}" data-perso="${esc(p.id)}" style="--el:${p.couleur}"
        aria-pressed="${choisi}" title="${choisi ? "Retirer" : "Choisir"} ${esc(p.nom)}">
      <span class="bt-visuel">${p.image ? `<img src="${esc(p.image)}" alt="" loading="lazy" onerror="this.remove()">` : ""}
        <span class="bt-elem">${icone((p.element || "").toLowerCase())}</span>${choisi ? `<span class="bt-coche">${ICONES.ok}</span>` : ""}</span>
      <span class="bt-nom">${esc(p.nom)}</span></button>`;
  }).join("") : `<p class="gris bt-rien">Aucun perso ne correspond à ta recherche.</p>`;
  grille.querySelectorAll("[data-perso]").forEach((b) => b.addEventListener("click", () => basculerEquipe(b.dataset.perso)));
}

function retourGrilleBuilds() {
  builds.choisi = null;
  afficherPageBuilds(etat.donnees.jeu);
}

async function afficherFicheBuild(jeu, id) {
  builds.choisi = id;
  const perso = builds.persos?.find((p) => p.id === id) || { id, nom: id };
  const liste = persosFiltres();
  const pos = liste.findIndex((p) => p.id === id);
  const voisin = (d) => liste.length > 1 && pos >= 0 ? liste[(pos + d + liste.length) % liste.length] : null;
  const avant = voisin(-1), apres = voisin(1);
  $("#contenu").innerHTML = `
    <div class="bt-fiche-page" style="--el:${perso.couleur || "var(--accent)"}">
      <div class="bt-nav" role="navigation" aria-label="Navigation entre les persos">
        <button class="secondaire" id="bt-retour">${ICONES.retour}Tous les persos</button>
        <span class="bt-nav-voisins">
          ${avant ? `<button class="discret" data-voisin="${esc(avant.id)}" title="${esc(avant.nom)}">${ICONES.retour}${esc(avant.nom)}</button>` : ""}
          ${apres ? `<button class="discret suivant" data-voisin="${esc(apres.id)}" title="${esc(apres.nom)}">${esc(apres.nom)}${ICONES.retour}</button>` : ""}
        </span>
      </div>
      <div id="bt-fiche">${heroBuild(perso, null)}
        <div class="bt-attente"><div class="rond"></div><p>Recherche des meilleurs builds de ${esc(perso.nom)}…</p></div></div>
    </div>`;
  document.querySelector("main").scrollTop = 0;
  $("#bt-retour").addEventListener("click", retourGrilleBuilds);
  document.querySelectorAll("[data-voisin]").forEach((b) => b.addEventListener("click", () => afficherFicheBuild(jeu, b.dataset.voisin)));
  try {
    const data = builds.cache[id] || await api(`/api/jeux/${jeu.id}/page/build/${encodeURIComponent(id)}`);
    builds.cache[id] = data;
    if (builds.choisi !== id || !$("#bt-fiche")) return;
    $("#bt-fiche").innerHTML = heroBuild(perso, data) + corpsBuild(data);
  } catch (e) {
    if (builds.choisi !== id || !$("#bt-fiche")) return;
    $("#bt-fiche").innerHTML = heroBuild(perso, null) + `<div class="bt-attente"><p>${esc(e.message)}</p>
      <a class="bouton-lien" href="https://genshin-builds.com/fr/character/${encodeURIComponent(id)}" target="_blank" rel="noopener">${ICONES.jeu}Voir sur Genshin-Builds</a></div>`;
  }
}
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && builds.choisi && $("#bt-retour") && !document.querySelector("dialog[open]")) retourGrilleBuilds();
});

function heroBuild(perso, d) {
  const rarete = d?.rarete || perso.rarete;
  const element = d?.element || perso.element;
  const infos = [element && `${icone(element.toLowerCase())}${esc(element)}`, esc(d?.arme || perso.arme || ""),
    d?.stat_bonus && `Bonus : ${esc(d.stat_bonus)}`].filter(Boolean);
  return `
    <header class="bt-hero r${rarete || 4}">
      ${perso.splash ? `<img class="bt-splash" src="${esc(perso.splash)}" alt="" onerror="this.remove()">` : ""}
      ${perso.image ? `<img class="bt-avatar" src="${esc(perso.image)}" alt="">` : ""}
      <div class="bt-hero-texte">
        ${rarete ? `<span class="bt-etoiles r${rarete}" aria-label="${rarete} étoiles">${"★".repeat(rarete)}</span>` : ""}
        <h2>${esc(d?.nom || perso.nom)}</h2>
        ${d?.titre ? `<p class="bt-titre">${esc(d.titre)}</p>` : ""}
        <p class="bt-infos">${infos.map((x) => `<span>${x}</span>`).join("")}</p>
      </div>
    </header>`;
}

function vignetteBuild(o) {
  return `<span class="bt-vig">${o.image ? `<img src="${esc(o.image)}" alt="" loading="lazy" onerror="this.remove()">` : ""}</span>`;
}

function corpsBuild(d) {
  const rang = (liste) => `<ol class="bt-rang">${liste.map((x) => `<li>${esc(x)}</li>`).join("")}</ol>`;
  const blocs = (d.builds || []).map((b, i) => {
    const principales = (b.stats || []).filter((s) => !["Fleur", "Plume"].includes(s.piece));
    const fixes = (b.stats || []).filter((s) => ["Fleur", "Plume"].includes(s.piece));
    return `
    ${d.builds.length > 1 || b.nom ? `<h3 class="bt-build-nom">${esc(b.nom || "Build " + (i + 1))}</h3>` : ""}
    <div class="bt-sections">
      ${b.armes?.length ? `<section class="bt-bloc bt-armes">
        <h3>${ICONES.arme}Armes <small>de la meilleure à la plus accessible</small></h3>
        <ol>${b.armes.map((a, n) => `<li class="${n === 0 ? "top" : ""}">${vignetteBuild(a)}<span>${esc(a.nom)}</span>
          ${n === 0 ? `<em>Meilleure</em>` : ""}</li>`).join("")}</ol>
      </section>` : ""}
      ${b.artefacts?.length ? `<section class="bt-bloc bt-artefacts">
        <h3>${ICONES.artefact}Artefacts</h3>
        <ul>${b.artefacts.map((a, n) => `<li class="${n === 0 ? "top" : ""}">
          <span class="bt-pieces">${esc(a.pieces)}</span>
          <span class="bt-sets">${a.ensembles.map((e) => `<b>${esc(e)}</b>`).join("")}</span></li>`).join("")}</ul>
      </section>` : ""}
      ${principales.length ? `<section class="bt-bloc bt-stats">
        <h3>${ICONES.graphique}Stats principales</h3>
        <div class="bt-pieces-grille">${principales.map((s) => `
          <div class="bt-piece"><small>${esc(s.piece)}</small>${s.valeurs.map((v, n) => `<b class="${n ? "alt" : ""}">${esc(v)}</b>`).join("")}</div>`).join("")}
        </div>
        ${fixes.length ? `<p class="bt-fixes">${fixes.map((s) => `${esc(s.piece)} : ${s.valeurs.map(esc).join(" / ")}`).join(" · ")}</p>` : ""}
      </section>` : ""}
      ${b.sous_stats?.length || b.aptitudes?.length ? `<section class="bt-bloc bt-priorites">
        ${b.sous_stats?.length ? `<h3>Sous-stats à viser</h3>${rang(b.sous_stats)}` : ""}
        ${b.aptitudes?.length ? `<h3>Aptitudes à monter</h3>${rang(b.aptitudes)}` : ""}
      </section>` : ""}
    </div>
    ${b.note ? `<p class="note-details">${ICONES.astuce}<span>${esc(b.note)}</span></p>` : ""}`;
  }).join("");
  const equipes = (d.equipes || []).map((t) => `
    <li class="bt-equipe">
      <div class="bt-membres">${t.membres.map((m) => `<span class="bt-membre" title="${esc(m.nom)}">${vignetteBuild(m)}<small>${esc(m.nom)}</small></span>`).join("")}</div>
      ${t.nom ? `<p>${esc(t.nom)}</p>` : ""}
    </li>`).join("");
  const age = d.age > 3600 ? `mis à jour il y a ${Math.round(d.age / 3600)} h` : "à jour";
  return `${blocs || `<p class="gris">Pas encore de build pour ce perso.</p>`}
    ${equipes ? `<section class="bt-equipes"><h3>${ICONES.equipe}Meilleures équipes</h3><ul>${equipes}</ul></section>` : ""}
    <p class="bt-source">Conseils de <a href="${esc(d.lien)}" target="_blank" rel="noopener">Genshin-Builds</a>, ${age}.</p>`;
}

// ----- Carte « collée » : la vraie carte (connectée à ton compte) posée sur le cadre, dans sa propre fenêtre
function zoneCadre() {
  const cadre = $("#cadre-carte");
  if (!cadre) return null;
  const r = cadre.getBoundingClientRect();
  return { x: r.left, y: r.top, l: r.width, h: r.height, lv: window.innerWidth, hv: window.innerHeight,
           dpr: window.devicePixelRatio || 1 };
}

async function montrerCarteCollee(jeu, carte) {
  etat.carteCollee = { jeu: jeu.id, carte: carte.id };
  try {
    const rep = await api("/api/carte-collee", { method: "POST",
      body: { action: "montrer", jeu: jeu.id, carte: carte.id, zone: zoneCadre() } });
    if (etat.carteCollee?.carte !== carte.id) return api("/api/carte-collee", { method: "POST", body: { action: "cacher" } });
    if (rep.ok) {
      $("#cadre-carte").innerHTML = `<div class="carte-attente"><p>${icone(carte.icone || "carte_teyvat")}${esc(jeu.texte_affiche || "La carte connectée est affichée ici.")}</p></div>`;
      if (rep.mode && rep.mode !== "OK") toast(`Placement de la carte : ${rep.mode === "ESTIME" ? "estimé (mesure exacte impossible)" : rep.mode}`, "info");
      return;
    }
    etat.carteCollee = null;
    // Nouvelle application : si la carte ne peut pas être posée ici, elle s'ouvre dans sa propre fenêtre
    if (etat.appli?.fenetre_native) return montrerCarteFenetreNative(jeu, carte);
    afficherCarteDansCadre(carte, rep.raison);
  } catch (e) {
    etat.carteCollee = null;
    afficherCarteDansCadre(carte, e.message);
  }
}

function cacherCarteCollee() {
  if (!etat.carteCollee) return;
  etat.carteCollee = null;
  api("/api/carte-collee", { method: "POST", body: { action: "cacher" } }).catch(() => {});
}

let attentePlacement = null;
function replacerCarteCollee() {
  if (!etat.carteCollee) return;
  clearTimeout(attentePlacement);
  attentePlacement = setTimeout(() => {
    const zone = zoneCadre();
    if (etat.carteCollee && zone) api("/api/carte-collee", { method: "POST", body: { action: "placer", zone } }).catch(() => {});
  }, 60);
}
window.addEventListener("resize", replacerCarteCollee);
document.addEventListener("scroll", replacerCarteCollee, true);

// Une fenêtre d'AllMyStats (Paramètres, Réglages…) passe devant : la carte se cache le temps qu'elle est ouverte
const _ouvrirModale = HTMLDialogElement.prototype.showModal;
HTMLDialogElement.prototype.showModal = function () {
  const enCours = etat.carteCollee;
  cacherCarteCollee();
  if (enCours) this.addEventListener("close", () => {
    const jeu = etat.jeux.find((j) => j.id === enCours.jeu);
    const carte = jeu?.cartes_en_ligne?.find((c) => c.id === enCours.carte);
    if (jeu && carte && etat.jeuActif === jeu.id && carteChoisie(jeu)?.id === carte.id) montrerCarteCollee(jeu, carte);
  }, { once: true });
  return _ouvrirModale.call(this);
};

function afficherCarteDansCadre(carte, raison) {
  const cadre = $("#cadre-carte");
  if (!cadre) return;
  cadre.innerHTML = `<iframe src="${esc(carte.url)}" title="${esc(carte.nom)}" allow="fullscreen; clipboard-write"></iframe>`;
  if (raison) toast(`Affichage connecté impossible ici (${raison}) : page affichée sans ton compte.`, "info");
}

async function chargerCarte(jeu, carte) {
  if (HORS_PC) {
    $("#cadre-carte").innerHTML = `<div class="carte-refus">${icone(carte.icone || "carte_teyvat")}
      <p><b>${esc(carte.nom)}</b> s'ouvre dans ton navigateur sur le téléphone, avec ton compte.</p>
      <a class="bouton-lien" href="${esc(carte.url)}" target="_blank" rel="noopener">${ICONES.jeu}Ouvrir ${esc(carte.nom)}</a></div>`;
    return;
  }
  if (carte.collee) return montrerCarteCollee(jeu, carte);
  let integrable = null;
  try {
    integrable = (await api(`/api/jeux/${jeu.id}/integrable/${encodeURIComponent(carte.id)}`)).integrable;
  } catch (e) { /* on essaie quand même */ }
  const cadre = $("#cadre-carte");
  if (!cadre || carteChoisie(jeu)?.id !== carte.id) return;   // l'utilisateur a changé d'onglet entre-temps
  if (integrable === false) {
    cadre.innerHTML = `<div class="carte-refus">${ICONES.alerte}
      <p><b>${esc(carte.nom)}</b> n'accepte pas d'être affichée à l'intérieur d'une autre appli : c'est le site qui le décide.
        Ouvre-la dans sa propre fenêtre, ou choisis l'autre carte en haut.</p>
      <button class="principal" id="carte-refus-ouvrir">${ICONES.ecran}Ouvrir ${esc(carte.nom)}</button></div>`;
    $("#carte-refus-ouvrir").addEventListener("click", () => ouvrirCarteFenetre(jeu, carte.id));
    return;
  }
  cadre.innerHTML = `<iframe src="${esc(carte.url)}" title="${esc(carte.nom)}" allow="fullscreen; clipboard-write"
    referrerpolicy="no-referrer-when-downgrade"></iframe>`;
}

// Nouvelle application : la vraie page HoYoLAB s'ouvre dans sa propre fenêtre AllMyStats (ouverte tout de suite)
function montrerCarteFenetreNative(jeu, carte) {
  const cadre = $("#cadre-carte");
  cadre.innerHTML = `<div class="carte-native">${icone(jeu.icone || "carte_teyvat")}
    <h3>${esc(carte.nom)}</h3>
    <p>La carte s'ouvre dans sa propre fenêtre AllMyStats : c'est la vraie page de HoYoverse.</p>
    <ul>
      <li>${ICONES.connexion}<span>Connecte-toi une fois en haut à droite de la carte (e-mail et mot de passe HoYoverse) :
        la connexion et tes repères sont gardés pour les fois suivantes.</span></li>
      <li>${ICONES.cle}<span>Tu te connectes directement chez HoYoverse : AllMyStats ne voit jamais ton mot de passe,
        et ta session reste dans la fenêtre de la carte, sur ton PC.</span></li>
      <li>${ICONES.astuce}<span>Connexion avec Google ou Apple : elle s'ouvre dans ton navigateur. Dans ce cas, utilise
        plutôt « Dans mon navigateur ».</span></li>
    </ul>
    <button class="principal" id="carte-native-ouvrir">${ICONES.ecran}Ouvrir la carte</button></div>`;
  $("#carte-native-ouvrir").addEventListener("click", () => ouvrirCarteFenetre(jeu, carte.id, "connexion"));
  if (!etat.carteOuverte?.[carte.id]) {   // ouverte toute seule la première fois qu'on vient ici
    etat.carteOuverte = { ...(etat.carteOuverte || {}), [carte.id]: true };
    ouvrirCarteFenetre(jeu, carte.id, "connexion");
  }
}

async function ouvrirCarteFenetre(jeu, idCarte, mode = "fenetre") {
  try {
    toast((await api(`/api/jeux/${jeu.id}/ouvrir`, { method: "POST", body: { carte: idCarte, mode } })).message, "info");
  } catch (e) { toast(e.message, "erreur"); }
}

// ---------- Importer un fichier de données (« Mes données » d'Activision…) ----------
function blocImportDonnees(d, ouvert) {
  return `
    <section class="import-donnees">
      <label class="depot-captures depot-donnees" id="depot-donnees">
        <input type="file" id="fichier-donnees" accept="${esc(d.accept || "")}">
        <span class="depot-icone">${ICONES.telecharger}</span>
        <span class="texte"><b>${esc(d.titre)}</b>${esc(d.texte || "")}
          <small>Glisse le fichier ici, ou clique pour le choisir.</small></span>
      </label>
      <details class="etapes-donnees" ${ouvert ? "open" : ""}>
        <summary>${ICONES.astuce}Comment obtenir ce fichier ?<span class="chev">${ICONES.chevron}</span></summary>
        <ol>${(d.etapes || []).map((e) => `<li>${esc(e)}</li>`).join("")}</ol>
        ${d.lien ? `<a class="bouton-lien" href="${esc(d.lien)}" target="_blank" rel="noopener">${ICONES.jeu}Ouvrir la page d'Activision</a>` : ""}
        ${d.prive ? `<p class="prive-donnees">${ICONES.cle}<span>${esc(d.prive)}</span></p>` : ""}
      </details>
      <div id="rapport-donnees"></div>
    </section>`;
}

function brancherImportDonnees() {
  const zone = $("#depot-donnees");
  if (!zone) return;
  $("#fichier-donnees").addEventListener("change", (e) => { const f = e.target.files[0]; if (f) importerDonnees(f); e.target.value = ""; });
  ["dragenter", "dragover"].forEach((t) => zone.addEventListener(t, (e) => { e.preventDefault(); zone.classList.add("survol"); }));
  ["dragleave", "drop"].forEach((t) => zone.addEventListener(t, () => zone.classList.remove("survol")));
  zone.addEventListener("drop", (e) => { e.preventDefault(); const f = e.dataTransfer.files[0]; if (f) importerDonnees(f); });
}

async function importerDonnees(fichier) {
  const zone = $("#depot-donnees"), jeuId = etat.jeuActif;
  zone.classList.add("en-cours");
  zone.querySelector(".texte small").textContent = `Lecture de ${fichier.name}…`;
  try {
    const rep = await fetch(`/api/jeux/${jeuId}/donnees`, { method: "POST", body: fichier,
      headers: { "Content-Type": "application/octet-stream", "X-Nom-Fichier": encodeURIComponent(fichier.name) } });
    const data = await rep.json().catch(() => ({}));
    if (!rep.ok) throw new Error(data.erreur || `Erreur ${rep.status}`);
    toast(data.message, data.ok ? "ok" : "erreur");
    if (data.ok && etat.jeuActif === jeuId) await choisirJeu(jeuId);
    const r = $("#rapport-donnees");
    if (r) r.innerHTML = `<div class="rapport-donnees ${data.ok ? "" : "rate"}">
      ${data.jeux?.length ? `<p><b>Rempli :</b> ${data.jeux.map((j) => `${esc(j.nom)} (${j.stats} stats)`).join(", ")}</p>` : ""}
      ${data.rapport?.length ? `<details ${data.ok ? "" : "open"}><summary>Ce qui a été lu dans le fichier</summary>
        <ul>${data.rapport.map((l) => `<li>${esc(l)}</li>`).join("")}</ul></details>` : ""}</div>`;
  } catch (e) {
    toast(e.message, "erreur");
  } finally {
    $("#depot-donnees")?.classList.remove("en-cours");
    const s = $("#depot-donnees .texte small");
    if (s) s.textContent = "Glisse le fichier ici, ou clique pour le choisir.";
  }
}

// ---------- Importer des captures d'écran (jeux sur téléphone) ----------
function brancherDepotCaptures() {
  const zone = $("#depot-captures");
  if (!zone) return;
  $("#fichiers-captures").addEventListener("change", (e) => { importerCaptures([...e.target.files]); e.target.value = ""; });
  ["dragenter", "dragover"].forEach((t) => zone.addEventListener(t, (e) => { e.preventDefault(); zone.classList.add("survol"); }));
  ["dragleave", "drop"].forEach((t) => zone.addEventListener(t, () => zone.classList.remove("survol")));
  zone.addEventListener("drop", (e) => { e.preventDefault(); importerCaptures([...e.dataTransfer.files]); });
}

async function importerCaptures(fichiers) {
  const images = fichiers.filter((f) => /^image\/(png|jpe?g|bmp)$/i.test(f.type));
  if (fichiers.length && !images.length) { toast("Envoie des captures en PNG ou JPG.", "erreur"); return; }
  const zone = $("#depot-captures");
  const jeuId = etat.jeuActif;
  let total = 0, derniereErreur = null;
  for (const [i, f] of images.entries()) {
    zone?.classList.add("en-cours");
    zone?.querySelector("small") && (zone.querySelector("small").textContent = `Lecture de ${f.name} (${i + 1}/${images.length})…`);
    try {
      const rep = await fetch(`/api/jeux/${jeuId}/image`, {
        method: "POST", body: f,
        headers: { "Content-Type": f.type, "X-Nom-Fichier": encodeURIComponent(f.name) },
      }).then(async (r) => { const d = await r.json(); if (!r.ok) throw new Error(d.erreur); return d; });
      total += rep.trouve.length;
      const { message, trouve, nouvelles, lignes, ...donnees } = rep;
      if (etat.jeuActif === jeuId) etat.donnees = donnees;
      if (images.length === 1) toast(message, trouve.length ? "ok" : "info");
    } catch (e) {
      derniereErreur = e.message;
    }
  }
  if (etat.jeuActif === jeuId) afficherJeu();
  if (derniereErreur && !total) toast(derniereErreur, "erreur");
  else if (images.length > 1) toast(`${images.length} captures lues · ${total} stat(s) trouvée(s)`, total ? "ok" : "info");
}

// ---------- Tester la lecture d'écran ----------
const DELAI_TEST = 8;

async function testerEcran() {
  const { jeu } = etat.donnees;
  const fen = $("#fenetre-test");
  const zone = $("#contenu-test");
  const arret = new AbortController();
  let reste = DELAI_TEST;
  zone.innerHTML = `
    <h2 class="titre-fenetre" id="titre-test">${ICONES.ecran}Tester la lecture d'écran</h2>
    <div class="compte-a-rebours">
      <div class="compte" id="compte" aria-live="off">${reste}</div>
      <div>
        <p>${esc(jeu.consigne_ecran)}</p>
        ${jeu.met_devant
          ? `<p>À la fin du compte à rebours, <b>AllMyStats met lui-même la fenêtre du jeu devant</b> et la capture.
          Un petit son te dira que c'est fait : reviens alors ici.</p>`
          : `<p><b>Clique dans la fenêtre du jeu</b> (ou Alt + Tab) avant la fin du compte à rebours.
          Un petit son te dira que la capture est faite : reviens alors ici.</p>`}
      </div>
    </div>
    <div class="boutons"><button type="button" class="secondaire" id="test-annuler">Annuler</button></div>`;
  fen.showModal();
  const minuteur = setInterval(() => {
    reste -= 1;
    const c = $("#compte");
    if (!c) return;
    if (reste > 0) c.textContent = reste;
    else {
      clearInterval(minuteur);
      $(".compte-a-rebours").outerHTML = `<div class="attente"><div class="rond"></div><p>Capture et lecture du texte…</p></div>`;
    }
  }, 1000);
  $("#test-annuler").onclick = () => { arret.abort(); clearInterval(minuteur); fen.close(); };
  fen.onclose = () => { arret.abort(); clearInterval(minuteur); };

  try {
    const rep = await api(`/api/jeux/${jeu.id}/test-ecran`, { method: "POST", body: { delai: DELAI_TEST }, signal: arret.signal });
    clearInterval(minuteur);
    const { reussi, etapes, lignes, trouve, cible, cible_nom, ...donnees } = rep;
    if (donnees.jeu?.id === etat.jeuActif) { etat.donnees = donnees; afficherJeu(); }
    if (fen.open) afficherResultatTest(rep);
  } catch (e) {
    clearInterval(minuteur);
    if (arret.signal.aborted) return;
    fen.close();
    toast(e.message, "erreur");
  }
}

function afficherResultatTest(rep) {
  const ic = { ok: "ok", erreur: "erreur", alerte: "alerte", neutre: "neutre" };
  const zone = $("#contenu-test");
  zone.innerHTML = `
    <h2 class="titre-fenetre" id="titre-test">${rep.reussi ? ICONES.ok + "La lecture d'écran marche" : ICONES.alerte + "La lecture d'écran bloque"}</h2>
    <ol class="etapes-test">${rep.etapes.map((e) => `
      <li class="${esc(e.etat)}">${ICONES[ic[e.etat] || "neutre"]}
        <div><b>${esc(e.titre)}</b>${e.detail ? `<span>${esc(e.detail)}</span>` : ""}</div></li>`).join("")}
    </ol>
    ${rep.trouve?.length ? `<div class="trouve">${rep.trouve.map((t) =>
      `<span class="puce">${esc(t.nom)}<b>${esc(nombre(t.valeur, t))}</b></span>`).join("")}</div>` : ""}
    ${rep.lignes?.length ? `<details class="texte-lu"><summary>Ce que Windows a lu (${rep.lignes.length} lignes)<span class="chev">${ICONES.chevron}</span></summary>
      <pre>${esc(rep.lignes.join("\n"))}</pre></details>` : ""}
    <div class="boutons">
      <button type="button" class="secondaire" id="test-refaire">${ICONES.actualiser}Refaire le test</button>
      <button type="button" class="principal" id="test-fermer">Fermer</button>
    </div>`;
  $("#test-fermer").onclick = () => $("#fenetre-test").close();
  $("#test-refaire").onclick = () => { $("#fenetre-test").close(); testerEcran(); };
}

// ---------- AllMyStats lui-même : version, mises à jour, arrière-plan ----------
async function chargerAppli() {
  try {
    etat.appli = await api("/api/appli");
  } catch (e) { return; }
  $("#version").textContent = "version " + etat.appli.version;
  if (typeof etat.appli.demandes_amis === "number") {
    const avant = etat.demandesAmis ?? etat.appli.demandes_amis;
    etat.demandesAmis = etat.appli.demandes_amis;
    majBadgeAmis(etat.appli.demandes_amis, amis.data?.amis?.length || 0);
    if (etat.appli.demandes_amis > avant) {
      toast("Nouvelle demande d'ami : va voir dans Amis !", "info");
      if (etat.jeuActif === "_amis" && !amis.edition) afficherPageAmis();
    }
  }
  const b = $("#bandeau-maj");
  const maj = etat.appli.maj;
  if (maj && b.hidden && etat.appliVue) son("maj");   // une nouvelle version vient d'arriver
  etat.appliVue = true;
  b.hidden = !maj || HORS_PC;   // depuis le téléphone, l'installation se fait sur le PC
  if (maj) {
    b.innerHTML = `${ICONES.maj}
      <span class="texte"><b>AllMyStats ${esc(maj.version)}</b> ${maj.en_ligne ? "a été téléchargé tout seul et" : ""} est prêt à être installé
        ${maj.nouveautes?.length ? `<span class="nouveautes">${maj.nouveautes.slice(0, 3).map(esc).join(", ")}</span>` : ""}</span>
      <button class="principal" id="btn-installer-maj">${ICONES.maj}Installer la mise à jour</button>`;
    $("#btn-installer-maj").onclick = () => installerMaj();
  } else if (!HORS_PC && etat.appli.programme_a_jour === false && !etat.programmeRefuse) {
    // Ancien AllMyStats.exe (fenêtre Edge) : on propose la nouvelle application, avec sa vraie fenêtre
    b.hidden = false;
    b.innerHTML = `${ICONES.ams}
      <span class="texte"><b>Nouvelle application AllMyStats</b> une vraie fenêtre Windows, sans navigateur. Tes stats et tes
        réglages sont gardés.</span>
      <button class="principal" id="btn-programme">${ICONES.maj}Installer</button>
      <button class="discret" id="btn-programme-plus-tard">Plus tard</button>`;
    $("#btn-programme").onclick = async (e) => {
      e.currentTarget.disabled = true;
      e.currentTarget.innerHTML = `${ICONES.maj}Téléchargement…`;
      try {
        const r = await api("/api/appli/programme", { method: "POST", body: {} });
        toast(r.message, "info");
      } catch (err) {
        toast(err.message, "erreur");
        e.currentTarget.disabled = false;
        e.currentTarget.innerHTML = `${ICONES.maj}Installer`;
      }
    };
    $("#btn-programme-plus-tard").onclick = () => { etat.programmeRefuse = true; b.hidden = true; };
  }
}

async function installerMaj(fichier) {
  const fen = $("#fenetre-attente");
  $("#texte-attente").textContent = "Installation de la mise à jour…";
  fen.showModal();
  try {
    const rep = fichier
      ? await fetch("/api/maj/fichier", { method: "POST", headers: { "Content-Type": "application/zip" }, body: fichier })
          .then(async (r) => { const d = await r.json(); if (!r.ok) throw new Error(d.erreur); return d; })
      : await api("/api/maj/installer", { method: "POST" });
    $("#texte-attente").textContent = rep.message;
    await attendreRedemarrage(rep.version);
  } catch (e) {
    fen.close();
    toast(e.message, "erreur");
  }
}

async function attendreRedemarrage(version) {
  for (let i = 0; i < 90; i++) {
    await new Promise((r) => setTimeout(r, 1000));
    try {
      const a = await fetch("/api/appli").then((r) => r.json());
      if (a.version === version) { location.reload(); return; }
    } catch (e) { /* l'application redémarre */ }
  }
  $("#texte-attente").textContent = "AllMyStats met du temps à redémarrer. Ferme cette fenêtre et relance AllMyStats.";
}

// ---------- Jeux affichés / masqués ----------
function blocsVisibilite() {
  const blocs = [];
  for (const j of etat.jeux) {
    if (!j.famille) { blocs.push({ jeu: j }); continue; }
    let f = blocs.find((b) => b.famille === j.famille);
    if (!f) blocs.push((f = { famille: j.famille, jeux: [] }));
    f.jeux.push(j);
  }
  const ligne = (cle, emblem, nom, coche, sous = false, desactive = false) => `
    <label class="interrupteur jeu-visible ${sous ? "sous" : ""}">
      <input type="checkbox" data-cle="${esc(cle)}" ${coche ? "checked" : ""} ${desactive ? "disabled" : ""}>
      <span class="mini-emblem">${emblem}</span><span>${esc(nom)}</span>
    </label>`;
  return blocs.map((b) => {
    if (b.jeu) return ligne(b.jeu.id, emblemeJeu(b.jeu), b.jeu.nom, !b.jeu.cache);
    const familleVisible = !b.jeux[0].famille_cachee;
    return `<div class="famille-visible">
      ${ligne(`famille:${b.famille}`, icone("famille_" + slug(b.famille), ICONES.jeu), b.famille, familleVisible)}
      ${b.jeux.map((j) => ligne(j.id, emblemeJeu(j), j.nom, !j.masque_seul, true, !familleVisible)).join("")}
    </div>`;
  }).join("");
}

async function changerVisibilite() {
  const cases = [...document.querySelectorAll(".jeux-affiches input[data-cle]")];
  const caches = cases.filter((c) => !c.checked).map((c) => c.dataset.cle);
  try {
    await api("/api/appli/jeux-caches", { method: "POST", body: { caches } });
    etat.jeux = await api("/api/jeux");
    afficherListeJeux();
    const actif = etat.jeux.find((j) => j.id === etat.jeuActif);
    if (!actif || actif.cache) ouvrirPremierJeuVisible(null);
    ouvrirParametres();
  } catch (e) {
    toast(e.message, "erreur");
  }
}

function depuis(ts) {
  const min = Math.round((Date.now() / 1000 - ts) / 60);
  return min < 1 ? "à l'instant" : min < 120 ? `il y a ${min} min` : `il y a ${Math.round(min / 60)} h`;
}

function ouvrirParametres() {
  const a = etat.appli || {};
  const el = a.en_ligne || {};
  $("#titre-parametres").innerHTML = `${ICONES.reglages}Paramètres d'AllMyStats`;
  $("#contenu-parametres").innerHTML = `
    <div class="version-grande">${ICONES.ams}<div><b>AllMyStats ${esc(a.version || "")}</b><small>AMS · nouveautés de cette version :</small></div></div>
    ${a.nouveautes?.length ? `<ul class="liste-nouveautes">${a.nouveautes.slice(0, 6).map((n) => `<li>${esc(n)}</li>`).join("")}</ul>` : ""}

    <h3 class="section-reglages">${ICONES.jeu}Jeux affichés</h3>
    <p class="gris petit">Décoche les jeux auxquels tu ne joues pas : ils disparaissent de la barre de gauche
      et AllMyStats arrête de les surveiller. Leurs stats sont gardées si tu les réaffiches.</p>
    <div class="jeux-affiches">${blocsVisibilite()}</div>

    ${APPLI_MOBILE ? `<h3 class="section-reglages">${ICONES.telephone}Synchronisation avec le PC</h3>
      <p class="gris petit">Ton téléphone a récupéré tes comptes et tes stats du PC, puis il se débrouille tout seul.
        Pour reprendre les nouveautés du PC (nouvelle clé, import Call of Duty, connexion…), scanne de nouveau son QR code.</p>
      <button type="button" class="secondaire" id="p-resynchro">${ICONES.actualiser}Synchroniser avec mon PC</button>`
    : DISTANT ? `<p class="note-pc">${ICONES.telephone}Ouvert depuis ton téléphone : les mises à jour, « Toujours actif » et « Quitter » se règlent sur le PC.</p>
      ${window.Android ? `<button type="button" class="secondaire" id="p-delier">${ICONES.deconnexion}Relier un autre PC</button>` : ""}` : `
    <h3 class="section-reglages">${ICONES.telephone}Téléphone</h3>
    <div id="bloc-telephone"><p class="gris">Chargement…</p></div>

    <h3 class="section-reglages">${ICONES.maj}Mises à jour</h3>
    ${a.maj ? `<p>La version <b>${esc(a.maj.version)}</b> ${a.maj.en_ligne ? "a été téléchargée toute seule" : "est dans ton dossier de téléchargements"}.</p>
               <button type="button" class="principal" id="p-installer">${ICONES.maj}Installer AllMyStats ${esc(a.maj.version)}</button>`
      : el.depot ? `<p class="gris">${el.erreur || !el.quand ? "" : "Tu as la dernière version. "}AllMyStats vérifie tout seul sur Internet toutes les 10 minutes${el.quand ? ` (dernière vérification ${depuis(el.quand)})` : ""}.</p>`
      : `<p class="gris">Les mises à jour par Internet ne sont pas encore branchées : il manque leur source (en bas de cette section).</p>`}
    ${el.erreur ? `<p class="erreur-maj">${ICONES.alerte}<span>${esc(el.erreur)}</span></p>` : ""}
    <div class="ligne-boutons">
      <button type="button" class="secondaire" id="p-verifier" ${el.depot ? "" : "disabled"}>${ICONES.actualiser}Vérifier maintenant</button>
    </div>
    <label class="interrupteur">
      <input type="checkbox" id="p-maj-auto" ${el.auto !== false ? "checked" : ""}>
      <span>Installer les mises à jour toutes seules</span>
    </label>
    <p class="gris petit">Elles s'installent quand la fenêtre d'AllMyStats est fermée, ou au prochain démarrage.
      Sinon, un bandeau te propose de les installer en un clic.</p>
    <details class="avances" ${el.depot ? "" : "open"}>
      <summary>${ICONES.cle}Source des mises à jour<span class="chev">${ICONES.chevron}</span></summary>
      <label>Dépôt GitHub
        <input id="p-depot" value="${esc(el.depot || "")}" placeholder="pseudo/AllMyStats" spellcheck="false" autocomplete="off">
        <small class="aide">L'endroit public où les nouvelles versions sont publiées.</small>
      </label>
      <button type="button" class="secondaire" id="p-depot-ok">${ICONES.enregistrer}Enregistrer la source</button>
      <label class="fichier"><span class="avec">${ICONES.fichier_zip}Ou installe un fichier AllMyStats.zip toi-même</span>
        <input type="file" id="p-fichier" accept=".zip"></label>
    </details>

    <h3 class="section-reglages">${ICONES.actualiser}Toujours actif</h3>
    <label class="interrupteur">
      <input type="checkbox" id="p-arriere" ${a.arriere_plan ? "checked" : ""} ${a.windows ? "" : "disabled"}>
      <span>Démarrer avec Windows et tourner en arrière-plan</span>
    </label>
    <p class="gris petit">Conseillé : le temps de jeu, la lecture d'écran (Blox Fruits, Call of Duty) et les actualisations
      continuent même fenêtre fermée. AllMyStats reste léger (une petite vérification par minute).</p>`}

    ${HORS_PC || !a.discord ? "" : sectionDiscord(a.discord)}

    <h3 class="section-reglages">${ICONES.son}Sons</h3>
    <label class="interrupteur">
      <input type="checkbox" id="p-sons" ${SONS.reglages.actifs ? "checked" : ""}>
      <span>Petits sons (clics, onglets, réussites, erreurs)</span>
    </label>
    <div class="volume-sons" ${SONS.reglages.actifs ? "" : "hidden"}>${ICONES.son_coupe}
      <input type="range" id="p-volume" min="0" max="1" step="0.05" value="${SONS.reglages.volume}" aria-label="Volume des sons">
      ${ICONES.son}</div>
    <label class="interrupteur">
      <input type="checkbox" id="p-fond" ${fondAnime() ? "checked" : ""}>
      <span>Fond animé (des lueurs qui bougent doucement, à la couleur du jeu)</span>
    </label>
    <label class="interrupteur">
      <input type="checkbox" id="p-intro" ${INTRO.reglages.active ? "checked" : ""}>
      <span>Animation d'ouverture (le logo qui explose)</span>
    </label>
    <label class="interrupteur">
      <input type="checkbox" id="p-ambiance" ${AMBIANCE.reglages.active ? "checked" : ""}>
      <span>Ambiance sonore (une musique douce quand AllMyStats est au premier plan)</span>
    </label>
    <div class="volume-sons" id="volume-ambiance" ${AMBIANCE.reglages.active ? "" : "hidden"}>${ICONES.son_coupe}
      <input type="range" id="p-volume-ambiance" min="0" max="1" step="0.05" value="${AMBIANCE.reglages.volume}" aria-label="Volume de l'ambiance">
      ${ICONES.musique}</div>

    ${HORS_PC ? "" : `<h3 class="section-reglages">${ICONES.quitter}Quitter</h3>
    <button type="button" class="secondaire" id="p-quitter">${ICONES.quitter}Arrêter complètement AllMyStats</button>`}`;
  if (!HORS_PC) chargerTelephone();
  $("#p-resynchro")?.addEventListener("click", () => {
    if (window.Android) return window.Android.synchroniser();
    $("#fenetre-parametres").close();
    afficherLiaison(true);
  });
  $("#p-delier")?.addEventListener("click", () => window.Android?.oublierPc());
  const fen = $("#fenetre-parametres");
  if (!fen.open) fen.showModal();
  const rafraichir = (rep) => { etat.appli = rep; chargerAppli(); ouvrirParametres(); };
  $("#contenu-parametres").querySelectorAll(".jeux-affiches input").forEach((c) => c.addEventListener("change", changerVisibilite));
  $("#p-verifier")?.addEventListener("click", async (e) => {
    e.target.disabled = true;
    e.target.innerHTML = `${ICONES.actualiser}Vérification…`;
    try {
      const rep = await api("/api/maj/verifier", { method: "POST" });
      toast(rep.message, "info");
      rafraichir(rep);
    } catch (err) {
      toast(err.message, "erreur");
      chargerAppli().then(() => ouvrirParametres());
    }
  });
  $("#p-maj-auto")?.addEventListener("change", async (e) => {
    try {
      rafraichir(await api("/api/appli/mises-a-jour", { method: "POST", body: { auto: e.target.checked } }));
    } catch (err) { e.target.checked = !e.target.checked; toast(err.message, "erreur"); }
  });
  $("#p-depot-ok")?.addEventListener("click", async () => {
    try {
      const rep = await api("/api/appli/mises-a-jour", { method: "POST", body: { depot: $("#p-depot").value } });
      toast("Source enregistrée. Vérification…", "info");
      rafraichir(rep);
      if (rep.en_ligne.depot) $("#p-verifier").click();
    } catch (err) { toast(err.message, "erreur"); }
  });
  $("#p-installer")?.addEventListener("click", () => { fen.close(); installerMaj(); });
  $("#p-fichier")?.addEventListener("change", (e) => {
    const f = e.target.files[0];
    if (f) { fen.close(); installerMaj(f); }
  });
  $("#p-sons").addEventListener("change", (e) => {
    SONS.reglages.actifs = e.target.checked;
    $(".volume-sons").hidden = !e.target.checked;
    if (e.target.checked) SONS.jouer("succes");
  });
  $("#p-fond").addEventListener("change", (e) => {
    try { localStorage.setItem("fond_anime", e.target.checked ? "1" : "0"); } catch (err) {}
    appliquerFond();
  });
  $("#p-intro").addEventListener("change", (e) => {
    INTRO.reglages.active = e.target.checked;
    if (e.target.checked) { $("#fenetre-parametres").close(); setTimeout(INTRO.jouer, 150); }
  });
  $("#p-ambiance").addEventListener("change", (e) => {
    AMBIANCE.activer(e.target.checked);
    $("#volume-ambiance").hidden = !e.target.checked;
    dessinerBoutonAmbiance();
  });
  $("#p-volume-ambiance").addEventListener("input", (e) => AMBIANCE.volume(Number(e.target.value)));
  $("#p-volume").addEventListener("change", (e) => { SONS.reglages.volume = Number(e.target.value); SONS.jouer("clic", true); });
  brancherDiscord();
  $("#p-arriere")?.addEventListener("change", async (e) => {
    try {
      etat.appli = await api("/api/appli/arriere-plan", { method: "POST", body: { actif: e.target.checked } });
      toast(e.target.checked ? "AllMyStats démarrera avec Windows et restera actif en arrière-plan"
                             : "AllMyStats ne démarrera plus avec Windows", "info");
    } catch (err) {
      e.target.checked = !e.target.checked;
      toast(err.message, "erreur");
    }
  });
  $("#p-quitter")?.addEventListener("click", async () => {
    await api("/api/appli/quitter", { method: "POST" }).catch(() => {});
    document.body.innerHTML = `<div class="vide" style="margin:auto">${ICONES.quitter}AllMyStats est arrêté. Tu peux fermer cette fenêtre.</div>`;
  });
}

// ---------- Signe de vie : l'application se ferme toute seule quand la fenêtre est fermée ----------
function signeDeVie() { fetch("/api/ping").catch(() => {}); }
signeDeVie();
setInterval(signeDeVie, 20000);
window.addEventListener("pagehide", () => navigator.sendBeacon("/api/au-revoir", "1"));

$("#btn-parametres").addEventListener("click", ouvrirParametres);
demarrer();

// ---------- Téléphone : la liste des jeux dans un tiroir ----------
function ouvrirMenu() {
  document.body.classList.add("menu-ouvert");
  $("#voile").hidden = false;
  $("#btn-menu").setAttribute("aria-expanded", "true");
}
// ---------- Discord : « Joue à AllMyStats » avec le logo, une description et un bouton ----------
function sectionDiscord(d) {
  const etatTexte = !d.actif ? "" : !d.id ? "Il manque l'identifiant de l'application Discord (voir plus bas)."
    : d.connecte ? "Affiché sur ton statut Discord." : d.erreur ? d.erreur : "Ouvre Discord sur ce PC : le statut s'affichera tout seul.";
  return `
    <h3 class="section-reglages">${ICONES.discord_statut}Discord</h3>
    <label class="interrupteur">
      <input type="checkbox" id="p-discord" ${d.actif ? "checked" : ""}>
      <span>Montrer AllMyStats sur mon statut Discord (logo et description)</span>
    </label>
    ${etatTexte ? `<p class="gris petit ${d.connecte ? "" : "discord-attente"}">${esc(etatTexte)}</p>` : ""}
    ${d.id_integre ? "" : `<details class="discord-id" ${d.id ? "" : "open"}>
      <summary>Identifiant de l'application Discord${d.id ? " : réglé" : ""}</summary>
      <ol class="petit">
        <li>Va sur <b>discord.com/developers/applications</b> et connecte-toi avec ton compte Discord.</li>
        <li><b>New Application</b>, nomme-la <b>AllMyStats</b> (c'est le nom affiché après « Joue à »), accepte et crée.</li>
        <li>Dans <b>General Information</b>, mets le logo d'AllMyStats en <b>App Icon</b>, puis copie l'<b>Application ID</b>.</li>
        <li>Colle-le ici. Ce n'est pas un mot de passe : c'est un numéro public.</li>
      </ol>
      <label>Application ID
        <input id="p-discord-id" value="${esc(d.id || "")}" inputmode="numeric" placeholder="Ex. 1234567890123456789" autocomplete="off" spellcheck="false">
      </label>
      <button type="button" class="secondaire" id="p-discord-ok">${ICONES.enregistrer}Enregistrer</button>
    </details>`}`;
}

function brancherDiscord() {
  const envoyer = async (corps, message) => {
    try {
      etat.appli = await api("/api/appli/discord", { method: "POST", body: corps });
      if (message) toast(message, "info");
    } catch (err) { toast(err.message, "erreur"); }
  };
  $("#p-discord")?.addEventListener("change", (e) => envoyer({ actif: e.target.checked },
    e.target.checked ? "AllMyStats s'affichera sur ton statut Discord" : "AllMyStats ne s'affichera plus sur Discord"));
  $("#p-discord-ok")?.addEventListener("click", () => envoyer({ id: $("#p-discord-id").value }, "Identifiant Discord enregistré"));
}

function fermerMenu() {
  if (!document.body.classList.contains("menu-ouvert")) return;
  document.body.classList.remove("menu-ouvert");
  $("#voile").hidden = true;
  $("#btn-menu").setAttribute("aria-expanded", "false");
}
$("#btn-menu").innerHTML = ICONES.menu;
$("#logo-mobile").innerHTML = ICONES.ams;
$("#btn-menu").addEventListener("click", () => (document.body.classList.contains("menu-ouvert") ? fermerMenu() : ouvrirMenu()));
$("#voile").addEventListener("click", fermerMenu);
$("#btn-parametres").addEventListener("click", fermerMenu);
document.addEventListener("keydown", (e) => { if (e.key === "Escape") fermerMenu(); });

// ---------- Paramètres > Téléphone (sur le PC) ----------
async function chargerTelephone(action) {
  const bloc = $("#bloc-telephone");
  if (!bloc) return;
  let t;
  try {
    t = action ? await api("/api/appli/telephone", { method: "POST", body: action }) : await api("/api/appli/telephone");
  } catch (e) { bloc.innerHTML = `<p class="erreur-maj">${ICONES.alerte}<span>${esc(e.message)}</span></p>`; return; }
  const code = (t.code || "").replace(/^(.{4})/, "$1-");
  bloc.innerHTML = `
    <label class="interrupteur"><input type="checkbox" id="p-telephone" ${t.actif ? "checked" : ""}>
      <span>Relier mon téléphone (même Wi-Fi que ce PC, juste le temps de la liaison)</span></label>
    ${t.actif && t.lien ? `
      <div class="telephone-bloc">
        <div class="telephone-qr">${QR.svg(t.lien, { taille: 170 })}</div>
        <div class="telephone-infos">
          <span class="gris petit">Dans l'appli AllMyStats du téléphone : <b>Scanner le QR code</b>, ou tape :</span>
          <span class="telephone-adresse">${esc(t.adresses[0])}:${t.port}</span>
          <span class="telephone-code">${esc(code)}</span>
          <button type="button" class="discret" id="p-nouveau-code">${ICONES.actualiser}Nouveau code (délie les téléphones)</button>
        </div>
      </div>
      <p class="gris petit">Le téléphone copie une fois tes comptes, tes clés et tes stats, puis <b>marche sans le PC</b>
        (il récupère ses stats tout seul sur Internet). Les connexions HoYoLAB, Riot, Roblox et Activision restent sur le PC.
        Rescanne quand tu veux reprendre les nouveautés du PC.</p>
      <p class="gris petit">Sur iPhone : dans l'appli AllMyStats pour iPhone (sur le site), tape l'adresse et le code ci-dessus.</p>
      <p class="gris petit">Si Windows demande d'autoriser AllMyStats sur le réseau, coche <b>Réseaux privés</b> et accepte.
        Le téléphone ne voit AllMyStats que quand ce PC est allumé (« Toujours actif » conseillé).</p>` : ""}
    ${t.erreur ? `<p class="erreur-maj">${ICONES.alerte}<span>${esc(t.erreur)}</span></p>` : ""}
    <p class="gris petit">L'appli Android se télécharge sur le site d'AllMyStats :
      <a href="https://angelotkkt.github.io/AllMyStats/#telephone" target="_blank" rel="noopener">angelotkkt.github.io/AllMyStats</a></p>`;
  $("#p-telephone").addEventListener("change", (e) => chargerTelephone({ actif: e.target.checked }));
  $("#p-nouveau-code")?.addEventListener("click", () => chargerTelephone({ nouveau_code: true }));
}

// ---------- iPhone : relier l'appli au PC (une fois), sans quitter l'interface ----------
function afficherLiaison(resynchro = false) {
  cacherCarteCollee();
  $("#titre-mobile").textContent = "Relier au PC";
  $("#contenu").innerHTML = `
    <section class="liaison">
      ${resynchro ? `<button class="discret" id="liaison-retour">${ICONES.retour}Revenir à mes stats</button>` : ""}
      <div class="liaison-tete">${ICONES.ams}<div><h2>${resynchro ? "Synchroniser avec ton PC" : "Relie ton iPhone une fois"}</h2>
        <p class="gris">${resynchro
          ? "Reprends les nouveautés du PC (nouvelle clé, import Call of Duty…). Les stats du PC remplacent celles du téléphone."
          : "Ton iPhone copie tes comptes, tes clés et tes stats depuis AllMyStats sur ton PC. Ensuite il marche <b>tout seul, sans le PC</b>."}</p></div></div>
      <ol class="liaison-etapes">
        <li>Sur ton PC : AllMyStats &gt; <b>Paramètres</b> &gt; <b>Téléphone</b>, coche « Relier mon téléphone ».</li>
        <li>Mets l'iPhone sur le <b>même Wi-Fi</b> que le PC (juste le temps de la liaison). Si l'iPhone demande
          l'accès au réseau local, accepte.</li>
        <li>Tape l'adresse et le code affichés sous le QR code du PC :</li>
      </ol>
      <form id="form-liaison" class="liaison-form">
        <label>Adresse du PC<input id="liaison-hote" inputmode="decimal" autocomplete="off" placeholder="192.168.1.20:8790"
          value="${esc((() => { try { return localStorage.getItem("ams_pc") || ""; } catch (e) { return ""; } })())}"></label>
        <label>Code<input id="liaison-code" autocomplete="off" autocapitalize="characters" maxlength="9" placeholder="ABCD-2345"></label>
        <button class="principal" type="submit" id="liaison-ok">${ICONES.telephone}Relier</button>
      </form>
      <p class="gris petit">Les connexions HoYoLAB, Riot, Roblox et Activision restent sur ton PC : le téléphone utilise
        tes clés d'API et les infos publiques de tes comptes.</p>
    </section>`;
  $("#liaison-retour")?.addEventListener("click", () => choisirJeu(etat.jeuActif || etat.jeux[0]?.id));
  $("#form-liaison").addEventListener("submit", async (e) => {
    e.preventDefault();
    const hote = $("#liaison-hote").value.trim(), code = $("#liaison-code").value.trim();
    if (!hote || !code) return toast("Tape l'adresse et le code affichés sur ton PC.", "erreur");
    const bouton = $("#liaison-ok");
    bouton.disabled = true;
    bouton.innerHTML = `${ICONES.actualiser}Copie de tes comptes et de tes stats…`;
    try {
      await api("/api/mobile/relier", { method: "POST", body: { hote, code } });
      try { localStorage.setItem("ams_pc", hote); } catch (err) {}
      toast("Relié ! Ton téléphone marche maintenant sans le PC.", "ok");
      setTimeout(() => location.reload(), 800);
    } catch (err) {
      toast(err.message, "erreur");
      bouton.disabled = false;
      bouton.innerHTML = `${ICONES.telephone}Relier`;
    }
  });
}
