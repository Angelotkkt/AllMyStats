// ================= Petits sons d'AllMyStats =================
// Tous synthétisés ici (Web Audio) : aucun fichier son, rien de copié. Courts et discrets.
// Réglages dans Paramètres > Sons (gardés dans cette fenêtre).

const SONS = (() => {
  let ctx = null, dernier = 0;
  const lire = (cle, defaut) => { try { const v = localStorage.getItem(cle); return v === null ? defaut : v; } catch (e) { return defaut; } };
  const ecrire = (cle, v) => { try { localStorage.setItem(cle, v); } catch (e) {} };
  const reglages = {
    get actifs() { return lire("sons_actifs", "1") === "1"; },
    set actifs(v) { ecrire("sons_actifs", v ? "1" : "0"); },
    get volume() { return Math.min(1, Math.max(0, Number(lire("sons_volume", "0.5")) || 0)); },
    set volume(v) { ecrire("sons_volume", String(v)); },
  };

  function audio() {
    if (!ctx) {
      const C = window.AudioContext || window.webkitAudioContext;
      if (!C) return null;
      ctx = new C();
    }
    if (ctx.state === "suspended") ctx.resume().catch(() => {});
    return ctx;
  }

  // Une note : forme d'onde, fréquence de départ -> d'arrivée, durée, volume relatif, décalage
  function note(a, sortie, { type = "sine", f1, f2 = f1, duree = 0.08, vol = 1, debut = 0 }) {
    const t = a.currentTime + debut;
    const o = a.createOscillator(), g = a.createGain();
    o.type = type;
    o.frequency.setValueAtTime(f1, t);
    if (f2 !== f1) o.frequency.exponentialRampToValueAtTime(f2, t + duree);
    g.gain.setValueAtTime(0.0001, t);
    g.gain.exponentialRampToValueAtTime(vol, t + 0.008);
    g.gain.exponentialRampToValueAtTime(0.0001, t + duree);
    o.connect(g).connect(sortie);
    o.start(t);
    o.stop(t + duree + 0.02);
  }

  function souffle(a, sortie, { duree = 0.14, vol = 0.5, de = 500, a_ = 2400, debut = 0 }) {
    const t = a.currentTime + debut;
    const n = Math.floor(a.sampleRate * duree);
    const tampon = a.createBuffer(1, n, a.sampleRate);
    const d = tampon.getChannelData(0);
    for (let i = 0; i < n; i++) d[i] = (Math.random() * 2 - 1) * (1 - i / n);
    const src = a.createBufferSource(), filtre = a.createBiquadFilter(), g = a.createGain();
    src.buffer = tampon;
    filtre.type = "bandpass"; filtre.Q.value = 1.4;
    filtre.frequency.setValueAtTime(de, t);
    filtre.frequency.exponentialRampToValueAtTime(a_, t + duree);
    g.gain.setValueAtTime(vol, t);
    src.connect(filtre).connect(g).connect(sortie);
    src.start(t);
  }

  const RECETTES = {
    clic: (a, s) => note(a, s, { type: "sine", f1: 1250, f2: 820, duree: 0.045, vol: 0.35 }),
    onglet: (a, s) => { note(a, s, { type: "triangle", f1: 520, duree: 0.06, vol: 0.4 });
      note(a, s, { type: "triangle", f1: 780, duree: 0.08, vol: 0.35, debut: 0.05 }); },
    succes: (a, s) => [523, 659, 784, 1047].forEach((f, i) =>
      note(a, s, { type: "triangle", f1: f, duree: 0.16, vol: 0.32, debut: i * 0.06 })),
    erreur: (a, s) => { note(a, s, { type: "sawtooth", f1: 240, f2: 200, duree: 0.12, vol: 0.12 });
      note(a, s, { type: "sawtooth", f1: 180, f2: 140, duree: 0.18, vol: 0.12, debut: 0.11 }); },
    info: (a, s) => { note(a, s, { type: "sine", f1: 1320, duree: 0.35, vol: 0.22 });
      note(a, s, { type: "sine", f1: 1980, duree: 0.25, vol: 0.08 }); },
    ouvrir: (a, s) => souffle(a, s, { duree: 0.13, vol: 0.35, de: 400, a_: 2600 }),
    fermer: (a, s) => souffle(a, s, { duree: 0.11, vol: 0.3, de: 2400, a_: 450 }),
    bascule: (a, s) => note(a, s, { type: "square", f1: 660, f2: 990, duree: 0.05, vol: 0.08 }),
    explosion: (a, s) => {
      souffle(a, s, { duree: .55, vol: .9, de: 1800, a_: 120 });
      note(a, s, { type: "sine", f1: 140, f2: 38, duree: .6, vol: .7 });
      [1568, 2093, 2637].forEach((f, i) => note(a, s, { type: "triangle", f1: f, duree: .5, vol: .12, debut: .08 + i * .07 }));
    },
    maj: (a, s) => [784, 988, 1175].forEach((f, i) =>
      note(a, s, { type: "sine", f1: f, duree: 0.3, vol: 0.25, debut: i * 0.09 })),
  };

  function jouer(nom, forcer = false) {
    if (!forcer && !reglages.actifs) return;
    const recette = RECETTES[nom];
    if (!recette) return;
    const maintenant = performance.now();
    if (!forcer && maintenant - dernier < 45) return;   // jamais deux sons collés
    dernier = maintenant;
    const a = audio();
    if (!a) return;
    const sortie = a.createGain();
    sortie.gain.value = reglages.volume * 0.9;
    sortie.connect(a.destination);
    try { recette(a, sortie); } catch (e) { /* pas de son, pas grave */ }
  }

  return { jouer, reglages, noms: Object.keys(RECETTES) };
})();

const son = (nom) => SONS.jouer(nom);

// Clics : un petit « tic » sur les boutons, un son d'onglet sur la barre de gauche et les onglets
document.addEventListener("click", (e) => {
  const cible = e.target.closest("button, [role=tab], summary, .interrupteur input, a.bouton-lien");
  if (!cible || cible.disabled || cible.dataset.son === "aucun") return;
  if (cible.matches(".interrupteur input")) return son("bascule");
  if (cible.closest("nav") || cible.matches("[role=tab], .onglet")) return son("onglet");
  son("clic");
}, true);

// Fenêtres (Paramètres, tests…) : un petit souffle à l'ouverture et à la fermeture
(() => {
  const ouvrir = HTMLDialogElement.prototype.showModal;
  HTMLDialogElement.prototype.showModal = function () {
    son("ouvrir");
    if (!this._sonFermer) {
      this._sonFermer = true;
      this.addEventListener("close", () => son("fermer"));
    }
    return ouvrir.call(this);
  };
})();

// ================= Ambiance sonore =================
// Une nappe douce (accords lents) et quelques notes de cristal de temps en temps, synthétisées ici.
// Elle ne joue que quand la fenêtre d'AllMyStats est active (elle se tait pendant que tu joues).
// Bouton en bas à gauche, ou Paramètres > Sons, pour la couper ou régler son volume.
const AMBIANCE = (() => {
  const lire = (cle, defaut) => { try { const v = localStorage.getItem(cle); return v === null ? defaut : v; } catch (e) { return defaut; } };
  const ecrire = (cle, v) => { try { localStorage.setItem(cle, v); } catch (e) {} };
  const reglages = {
    get active() { return lire("ambiance_active", "1") === "1"; },
    set active(v) { ecrire("ambiance_active", v ? "1" : "0"); },
    get volume() { return Math.min(1, Math.max(0, Number(lire("ambiance_volume", "0.4")) || 0)); },
    set volume(v) { ecrire("ambiance_volume", String(v)); },
  };
  const hz = (midi) => 440 * Math.pow(2, (midi - 69) / 12);
  // Fa majeur, tout en douceur : Fa7M, Rém9, Si♭7M, Do6/9
  const ACCORDS = [[53, 57, 60, 64], [50, 53, 57, 64], [46, 50, 53, 57], [48, 55, 57, 62]];
  const CRISTAL = [77, 79, 81, 84, 86, 89, 91, 93];   // pentatonique de Fa, en haut
  const DUREE_ACCORD = 11, FONDU = 4;

  let ctx = null, sortie = null, echo = null, minuteurs = [], enCours = false, demarree = false, accord = 0;

  function preparer() {
    if (ctx) return true;
    const C = window.AudioContext || window.webkitAudioContext;
    if (!C) return false;
    ctx = new C();
    sortie = ctx.createGain();
    sortie.gain.value = 0.0001;
    sortie.connect(ctx.destination);
    // Écho doux pour les notes de cristal
    echo = ctx.createDelay(1.5);
    echo.delayTime.value = 0.42;
    const retour = ctx.createGain(), filtre = ctx.createBiquadFilter();
    retour.gain.value = 0.38; filtre.type = "lowpass"; filtre.frequency.value = 2600;
    echo.connect(filtre).connect(retour).connect(echo);
    filtre.connect(sortie);
    return true;
  }

  function niveau() { return reglages.volume * 0.16; }

  function jouerAccord() {
    if (!enCours) return;
    const t = ctx.currentTime, notes = ACCORDS[accord % ACCORDS.length];
    accord++;
    const filtre = ctx.createBiquadFilter(), g = ctx.createGain();
    filtre.type = "lowpass"; filtre.frequency.value = 700; filtre.Q.value = 0.4;
    const lfo = ctx.createOscillator(), prof = ctx.createGain();
    lfo.frequency.value = 0.07; prof.gain.value = 260;
    lfo.connect(prof).connect(filtre.frequency);
    g.gain.setValueAtTime(0.0001, t);
    g.gain.exponentialRampToValueAtTime(0.11, t + FONDU);
    g.gain.setValueAtTime(0.11, t + DUREE_ACCORD);
    g.gain.exponentialRampToValueAtTime(0.0001, t + DUREE_ACCORD + FONDU);
    filtre.connect(g).connect(sortie);
    const fin = t + DUREE_ACCORD + FONDU + 0.1;
    notes.forEach((n, i) => [-6, 5].forEach((desaccord) => {
      const o = ctx.createOscillator();
      o.type = i === 0 ? "sine" : "triangle";
      o.frequency.value = hz(n);
      o.detune.value = desaccord;
      o.connect(filtre);
      o.start(t); o.stop(fin);
    }));
    lfo.start(t); lfo.stop(fin);
    minuteurs.push(setTimeout(jouerAccord, DUREE_ACCORD * 1000));
  }

  function jouerCristal() {
    if (!enCours) return;
    const t = ctx.currentTime, f = hz(CRISTAL[Math.floor(Math.random() * CRISTAL.length)]);
    const o = ctx.createOscillator(), g = ctx.createGain();
    o.type = "sine"; o.frequency.value = f;
    g.gain.setValueAtTime(0.0001, t);
    g.gain.exponentialRampToValueAtTime(0.05, t + 0.02);
    g.gain.exponentialRampToValueAtTime(0.0001, t + 2.6);
    o.connect(g); g.connect(sortie); g.connect(echo);
    o.start(t); o.stop(t + 2.7);
    minuteurs.push(setTimeout(jouerCristal, 2500 + Math.random() * 4500));
  }

  function fondu(cible, duree) {
    const t = ctx.currentTime;
    sortie.gain.cancelScheduledValues(t);
    sortie.gain.setValueAtTime(Math.max(0.0001, sortie.gain.value), t);
    sortie.gain.exponentialRampToValueAtTime(Math.max(0.0001, cible), t + duree);
  }

  function lancer() {
    if (!reglages.active || !demarree || enCours || !preparer()) return;
    if (document.visibilityState === "hidden" || !document.hasFocus()) return;
    if (ctx.state === "suspended") ctx.resume().catch(() => {});
    enCours = true;
    fondu(niveau(), 3);
    jouerAccord();
    minuteurs.push(setTimeout(jouerCristal, 1800));
  }

  function arreter(duree = 1.5) {
    if (!enCours) return;
    enCours = false;
    minuteurs.forEach(clearTimeout); minuteurs = [];
    fondu(0.0001, duree);
  }

  // Les navigateurs n'autorisent le son qu'après un premier clic ou une touche
  const premierGeste = () => { demarree = true; lancer(); };
  ["pointerdown", "keydown"].forEach((t) => document.addEventListener(t, premierGeste, { once: true, capture: true }));
  window.addEventListener("focus", lancer);
  window.addEventListener("blur", () => arreter(1.2));
  document.addEventListener("visibilitychange", () => (document.visibilityState === "hidden" ? arreter(0.6) : lancer()));

  return {
    reglages,
    activer(oui) { reglages.active = oui; demarree = true; oui ? lancer() : arreter(0.8); },
    volume(v) { reglages.volume = v; if (enCours) fondu(niveau(), 0.4); },
  };
})();

// Bouton en bas de la barre de gauche
function dessinerBoutonAmbiance() {
  const b = document.getElementById("btn-ambiance");
  if (!b || typeof ICONES === "undefined") return;
  const actif = AMBIANCE.reglages.active;
  b.innerHTML = actif ? ICONES.musique : ICONES.son_coupe;
  b.setAttribute("aria-pressed", actif);
  b.title = actif ? "Couper l'ambiance sonore" : "Remettre l'ambiance sonore";
  b.classList.toggle("coupe", !actif);
}
document.addEventListener("DOMContentLoaded", () => {
  dessinerBoutonAmbiance();
  document.getElementById("btn-ambiance")?.addEventListener("click", () => {
    AMBIANCE.activer(!AMBIANCE.reglages.active);
    dessinerBoutonAmbiance();
  });
});
