// ================= Animation d'ouverture =================
// Le logo d'AllMyStats se charge… puis explose en objets de tous les jeux qui partent dans tous les sens.
// Dessins maison (web/icones.js). Un clic ou une touche la passe. Coupée si « réduire les animations »
// est demandé par le système, ou dans Paramètres > Sons et animation.

const INTRO = (() => {
  const OBJETS = ["primogemme", "fusil", "couteau", "jeton_or", "relique", "pioche", "bf_fruit", "valo_viseur",
    "fn_victoire", "apex_rang", "cs_premier", "beli", "mora", "voeu", "fragment", "artefact", "cod_parachute",
    "cod_victoire"];
  const lire = () => { try { return localStorage.getItem("intro_active") !== "0"; } catch (e) { return true; } };
  const reglages = {
    get active() { return lire(); },
    set active(v) { try { localStorage.setItem("intro_active", v ? "1" : "0"); } catch (e) {} },
  };
  const hasard = (a, b) => a + Math.random() * (b - a);

  function jouer() {
    if (!reglages.active || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    if (typeof ICONES === "undefined" || !document.body) return;
    const scene = document.createElement("div");
    scene.className = "intro";
    scene.setAttribute("aria-hidden", "true");
    scene.innerHTML = `
      <div class="intro-lueur"></div>
      <div class="intro-onde"></div>
      <div class="intro-logo">${ICONES.ams}</div>
      <div class="intro-nom">AllMyStats</div>`;
    document.body.appendChild(scene);
    const logo = scene.querySelector(".intro-logo");
    let fini = false;
    const minuteurs = [];

    const terminer = (vite) => {
      if (fini) return;
      fini = true;
      minuteurs.forEach(clearTimeout);
      scene.animate([{ opacity: 1 }, { opacity: 0 }], { duration: vite ? 180 : 450, easing: "ease-out", fill: "forwards" })
        .onfinish = () => scene.remove();
      ["pointerdown", "keydown"].forEach((t) => window.removeEventListener(t, passer, true));
    };
    const passer = () => terminer(true);
    ["pointerdown", "keydown"].forEach((t) => window.addEventListener(t, passer, true));

    // 1) Le logo arrive et se charge (il tremble de plus en plus)
    logo.animate([
      { transform: "scale(.3) rotate(-25deg)", opacity: 0 },
      { transform: "scale(1.08) rotate(4deg)", opacity: 1, offset: .55 },
      { transform: "scale(1) rotate(0)", opacity: 1 },
    ], { duration: 420, easing: "cubic-bezier(.2,.9,.3,1.2)", fill: "forwards" });
    minuteurs.push(setTimeout(() => {
      logo.animate([
        { transform: "scale(1) translate(0,0)" }, { transform: "scale(.94) translate(-3px,2px)" },
        { transform: "scale(.9) translate(3px,-2px)" }, { transform: "scale(.88) translate(-4px,-3px)" },
        { transform: "scale(.86) translate(4px,3px)" }, { transform: "scale(.85) translate(0,0)" },
      ], { duration: 380, easing: "linear", fill: "forwards" });
      scene.querySelector(".intro-lueur").animate([{ opacity: .35, transform: "scale(.6)" }, { opacity: 1, transform: "scale(1)" }],
        { duration: 380, easing: "ease-in", fill: "forwards" });
    }, 430));

    // 2) BOUM : le logo éclate, une onde part, les objets des jeux volent dans tous les sens
    minuteurs.push(setTimeout(() => {
      if (typeof son === "function") son("explosion");
      logo.animate([{ transform: "scale(.85)", opacity: 1, filter: "brightness(1)" },
        { transform: "scale(2.2)", opacity: 0, filter: "brightness(2.5)" }],
        { duration: 300, easing: "ease-out", fill: "forwards" });
      scene.querySelector(".intro-onde").animate([
        { transform: "translate(-50%,-50%) scale(0)", opacity: .9 },
        { transform: "translate(-50%,-50%) scale(1)", opacity: 0 }],
        { duration: 700, easing: "cubic-bezier(.1,.7,.3,1)", fill: "forwards" });
      scene.querySelector(".intro-lueur").animate([{ opacity: 1 }, { opacity: 0 }], { duration: 900, fill: "forwards" });

      const portee = Math.hypot(window.innerWidth, window.innerHeight) * .62;
      const nombre = window.innerWidth < 600 ? 26 : 38;
      for (let i = 0; i < nombre; i++) {
        const el = document.createElement("div");
        el.className = "intro-objet";
        el.innerHTML = ICONES[OBJETS[i % OBJETS.length]] || "";
        const taille = window.innerWidth < 600 ? hasard(44, 78) : hasard(60, 120);
        el.style.width = el.style.height = `${taille}px`;
        scene.appendChild(el);
        const angle = (i / nombre) * Math.PI * 2 + hasard(-.25, .25);
        const loin = portee * hasard(.5, 1.05);
        const x = Math.cos(angle) * loin, y = Math.sin(angle) * loin;
        const tour = hasard(-600, 600);
        el.animate([
          { transform: "translate(-50%,-50%) translate(0,0) rotate(0) scale(.2)", opacity: 1 },
          { transform: `translate(-50%,-50%) translate(${x * .42}px,${y * .42}px) rotate(${tour * .45}deg) scale(1.15)`, opacity: 1, offset: .28 },
          { transform: `translate(-50%,-50%) translate(${x * .7}px,${y * .7 + 20}px) rotate(${tour * .75}deg) scale(1)`, opacity: 1, offset: .65 },
          { transform: `translate(-50%,-50%) translate(${x}px,${y + 60}px) rotate(${tour}deg) scale(.9)`, opacity: 0 },
        ], { duration: hasard(1500, 2000), delay: hasard(0, 80), easing: "cubic-bezier(.2,.6,.35,1)", fill: "forwards" });
      }
      // Étincelles
      for (let i = 0; i < 26; i++) {
        const e = document.createElement("div");
        e.className = "intro-etincelle";
        e.style.background = ["#FF6B5E", "#FFC44D", "#33D1C1", "#ffffff"][i % 4];
        scene.appendChild(e);
        const a = Math.random() * Math.PI * 2, d = hasard(120, portee * .55);
        e.animate([
          { transform: "translate(-50%,-50%) translate(0,0) scale(1)", opacity: 1 },
          { transform: `translate(-50%,-50%) translate(${Math.cos(a) * d}px,${Math.sin(a) * d}px) scale(0)`, opacity: 0 },
        ], { duration: hasard(500, 900), easing: "cubic-bezier(.1,.8,.3,1)", fill: "forwards" });
      }
    }, 820));

    // 3) Le nom apparaît au milieu de l'explosion, puis tout s'efface
    minuteurs.push(setTimeout(() => {
      scene.querySelector(".intro-nom").animate([
        { transform: "translate(-50%,-50%) scale(.6)", opacity: 0, letterSpacing: "12px" },
        { transform: "translate(-50%,-50%) scale(1)", opacity: 1, letterSpacing: "-1px" }],
        { duration: 450, easing: "cubic-bezier(.2,.9,.3,1.1)", fill: "forwards" });
    }, 1100));
    minuteurs.push(setTimeout(() => terminer(false), 2550));
  }

  return { jouer, reglages };
})();

if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", INTRO.jouer);
else INTRO.jouer();
