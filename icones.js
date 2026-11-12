// ================= Emojis personnalisés de AllMyStats =================
// Chaque emoji est un petit dessin SVG (32 × 32). Pour en ajouter un :
//   emoji("mon_nom", `...dessin svg...`);
// puis utilise "mon_nom" comme icone dans un fichier de jeu (Stat(..., icone="mon_nom")).

const ICONES = {};
function emoji(nom, dessin) {
  ICONES[nom] = `<svg class="emoji" viewBox="0 0 32 32" aria-hidden="true">${dessin}</svg>`;
}
const deg = (id, a, b, vertical = true) =>
  `<defs><linearGradient id="${id}" x1="0" y1="0" x2="${vertical ? 0 : 1}" y2="${vertical ? 1 : 0}">
     <stop offset="0" stop-color="${a}"/><stop offset="1" stop-color="${b}"/></linearGradient></defs>`;
const rad = (id, a, b) =>
  `<defs><radialGradient id="${id}" cx=".4" cy=".35" r=".7"><stop offset="0" stop-color="${a}"/><stop offset="1" stop-color="${b}"/></radialGradient></defs>`;
const ETOILE4 = "M16 2 L19.6 12.4 L30 16 L19.6 19.6 L16 30 L12.4 19.6 L2 16 L12.4 12.4 Z";
const etoile5 = (cx, cy, r) => {
  let p = "";
  for (let i = 0; i < 10; i++) {
    const a = -Math.PI / 2 + (i * Math.PI) / 5, rr = i % 2 ? r * 0.45 : r;
    p += `${i ? "L" : "M"}${(cx + rr * Math.cos(a)).toFixed(1)} ${(cy + rr * Math.sin(a)).toFixed(1)} `;
  }
  return p + "Z";
};

// ---------- Le jeu ----------
emoji("jeu_genshin", `${rad("gj", "#3b5b9a", "#14213f")}
  <circle cx="16" cy="16" r="15" fill="url(#gj)"/>
  <ellipse cx="16" cy="16" rx="13" ry="5" fill="none" stroke="#e8c36a" stroke-width="1" opacity=".55" transform="rotate(-25 16 16)"/>
  <path d="${ETOILE4}" transform="translate(5.5 5.5) scale(.66)" fill="#ffe9a8" stroke="#e8b04a" stroke-width="1.2"/>
  <circle cx="24.5" cy="8" r="1.4" fill="#fff"/>`);

// ---------- Monnaies ----------
emoji("primogemme", `${deg("gp", "#ffffff", "#9fd8ff")}
  <path d="${ETOILE4}" fill="url(#gp)" stroke="#e2b552" stroke-width="1.6" stroke-linejoin="round"/>
  <path d="M16 7 L18 14 L25 16 L18 18 L16 25 L14 18 L7 16 L14 14 Z" fill="#d7f0ff" opacity=".9"/>
  <path d="M16 2 L16 30 M2 16 L30 16" stroke="#7fbfe8" stroke-width=".6" opacity=".6"/>`);
emoji("primo_jour", `${deg("gpj", "#ffffff", "#9fd8ff")}
  <path d="${ETOILE4}" transform="translate(0 3) scale(.85)" fill="url(#gpj)" stroke="#e2b552" stroke-width="1.6" stroke-linejoin="round"/>
  <circle cx="25" cy="7" r="4.2" fill="#ffc54d"/>
  <g stroke="#ffc54d" stroke-width="1.4" stroke-linecap="round"><path d="M25 .8v1.6M31.2 7h-1.6M29.4 2.6l-1.1 1.1M20.6 2.6l1.1 1.1M29.4 11.4l-1.1-1.1"/></g>`);
emoji("primos_depensees", `${deg("gpd", "#ffffff", "#9fd8ff")}
  <path d="${ETOILE4}" transform="scale(.85)" fill="url(#gpd)" stroke="#e2b552" stroke-width="1.6" stroke-linejoin="round"/>
  <circle cx="24" cy="24" r="7" fill="#c86bd8"/>
  <path d="M24 20v7M21 24.5l3 3 3-3" stroke="#fff" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"/>`);
emoji("mora", `${rad("gm", "#ffe7a0", "#c98a1c")}
  <circle cx="16" cy="16" r="13.5" fill="url(#gm)" stroke="#8a5a10" stroke-width="1.2"/>
  <circle cx="16" cy="16" r="9.5" fill="none" stroke="#a8701a" stroke-width="1.2"/>
  <path d="M16 9.5 L20.5 16 L16 22.5 L11.5 16 Z" fill="#fff4cc" stroke="#a8701a"/>`);

// ---------- Vœux ----------
emoji("voeu", `${deg("gv", "#5f7cff", "#d07bff", false)}
  <path d="M3 29 L18 14" stroke="url(#gv)" stroke-width="3.5" stroke-linecap="round" opacity=".55"/>
  <path d="M7 29 L19 17" stroke="#9ecbff" stroke-width="1.6" stroke-linecap="round" opacity=".7"/>
  <path d="M3 25 L15 13" stroke="#e7b8ff" stroke-width="1.6" stroke-linecap="round" opacity=".7"/>
  <path d="${etoile5(22, 10, 8.5)}" fill="#fff3c4" stroke="#f2c14e" stroke-width="1.4" stroke-linejoin="round"/>`);
emoji("cinq_etoiles", `${deg("g5", "#ffe28a", "#e09a2a")}
  <path d="${etoile5(16, 17, 14.5)}" fill="url(#g5)" stroke="#a8661a" stroke-width="1.2" stroke-linejoin="round"/>
  <text x="16" y="21.5" text-anchor="middle" font-size="11" font-weight="800" fill="#7a3f00" font-family="Segoe UI, sans-serif">5</text>`);
emoji("quatre_etoiles", `${deg("g4", "#e6c8ff", "#9b62d6")}
  <path d="${etoile5(16, 17, 14.5)}" fill="url(#g4)" stroke="#5e2f94" stroke-width="1.2" stroke-linejoin="round"/>
  <text x="16" y="21.5" text-anchor="middle" font-size="11" font-weight="800" fill="#3f1670" font-family="Segoe UI, sans-serif">4</text>`);
emoji("pity", `${deg("gpi", "#ffe28a", "#e09a2a")}
  <circle cx="16" cy="16" r="13" fill="#2a2f45" stroke="#4a5070" stroke-width="1.5"/>
  <path d="M16 3 A13 13 0 1 1 4.7 22.5" fill="none" stroke="url(#gpi)" stroke-width="4" stroke-linecap="round"/>
  <path d="${etoile5(16, 16.5, 6.5)}" fill="#ffe28a"/>`);
emoji("sablier", `${deg("gs", "#9fd8ff", "#5f7cff")}
  <path d="M8 3h16M8 29h16" stroke="#c9a15a" stroke-width="2.6" stroke-linecap="round"/>
  <path d="M10 4c0 7 6 8 6 12s-6 5-6 12h12c0-7-6-8-6-12s6-5 6-12z" fill="#e9f5ff" stroke="#c9a15a" stroke-width="1.4"/>
  <path d="M12.5 26c1-3 3-4 3.5-6 .5 2 2.5 3 3.5 6z M13 8h6c-.5 2-2 3-3 4-1-1-2.5-2-3-4z" fill="url(#gs)"/>`);
emoji("arme", `${deg("ga", "#ffffff", "#9fb4d0")}
  <path d="M27 3 L29 5 L13 21 L11 19 Z" fill="url(#ga)" stroke="#6b7a92" stroke-width="1"/>
  <path d="M7 17 L15 25 M9 23 L4 28" stroke="#e2b552" stroke-width="3" stroke-linecap="round"/>
  <circle cx="4" cy="28" r="2" fill="#c86bd8"/>`);

// ---------- Profil ----------
emoji("aventure", `${rad("gav", "#fff6dd", "#e2c78f")}
  <circle cx="16" cy="16" r="13.5" fill="url(#gav)" stroke="#9a6a24" stroke-width="1.6"/>
  <path d="M16 5 L19 16 L16 27 L13 16 Z" fill="#c2453b"/>
  <path d="M16 16 L19 16 L16 27 L13 16 Z" fill="#e8eef7"/>
  <circle cx="16" cy="16" r="2" fill="#9a6a24"/>
  <path d="M16 3.5v2M16 26.5v2M3.5 16h2M26.5 16h2" stroke="#9a6a24" stroke-width="1.6"/>`);
emoji("monde", `${rad("gmo", "#7fd0ff", "#1f6fb5")}
  <circle cx="16" cy="16" r="13.5" fill="url(#gmo)"/>
  <path d="M9 9c3-1 5 1 4 3s-4 1-5 4 2 4 1 7c-3-2-5-6-4-10z M19 6c3 0 7 3 8 7-2 1-4-1-6 1s1 5-2 7c-1-3-3-4-2-7s3-3 2-8z" fill="#7bd389"/>
  <ellipse cx="16" cy="16" rx="13.5" ry="5" fill="none" stroke="#fff" stroke-width=".8" opacity=".5"/>
  <path d="M16 2.5 C10 8 10 24 16 29.5 C22 24 22 8 16 2.5" fill="none" stroke="#fff" stroke-width=".8" opacity=".5"/>`);
emoji("succes", `${deg("gsu", "#ffe28a", "#d08a1a")}
  <path d="M9 4h14v7a7 7 0 0 1-14 0z" fill="url(#gsu)" stroke="#8a5a10" stroke-width="1.2"/>
  <path d="M9 7H5c0 4 2 6 5 6M23 7h4c0 4-2 6-5 6" fill="none" stroke="#d08a1a" stroke-width="2"/>
  <path d="M14 18h4v4h-4z" fill="#d08a1a"/><rect x="9" y="22" width="14" height="5" rx="1.5" fill="#7a4b12"/>
  <path d="${etoile5(16, 10.5, 4)}" fill="#fff6d0"/>`);
emoji("abysse", `${rad("gab", "#b07cff", "#2a1450")}
  <circle cx="16" cy="16" r="14" fill="url(#gab)"/>
  <path d="M16 16 m0 -1.5 a1.5 1.5 0 1 1 -1.5 1.5 a3.5 3.5 0 0 1 3.5 -3.5 a5.5 5.5 0 0 1 5.5 5.5 a7.5 7.5 0 0 1 -7.5 7.5 a9.5 9.5 0 0 1 -9.5 -9.5 a11 11 0 0 1 11 -11" fill="none" stroke="#e4d2ff" stroke-width="1.8" stroke-linecap="round"/>`);
emoji("etoiles_abysse", `${rad("gea", "#8a5cd8", "#2a1450")}
  <circle cx="16" cy="16" r="14" fill="url(#gea)"/>
  <path d="${etoile5(16, 11, 6)}" fill="#ffe28a"/>
  <path d="${etoile5(9.5, 20, 4.6)}" fill="#ffe28a"/>
  <path d="${etoile5(22.5, 20, 4.6)}" fill="#ffe28a"/>`);
emoji("theatre", `${deg("gth", "#ffffff", "#d9d2f2")}
  <path d="M5 6c6 2 12 2 18 0v9c0 7-5 11-9 11s-9-4-9-11z" fill="url(#gth)" stroke="#c9a15a" stroke-width="1.5"/>
  <path d="M9 12c1.5-1 3-1 4 0M15 12c1.5-1 3-1 4 0" stroke="#3a2a5a" stroke-width="1.6" fill="none" stroke-linecap="round"/>
  <path d="M10 18c2 3 6 3 8 0" stroke="#c2453b" stroke-width="1.8" fill="none" stroke-linecap="round"/>
  <path d="${etoile5(26, 6, 4)}" fill="#e2b552"/>`);
emoji("amitie", `${deg("gam", "#ff9fc4", "#e2457a")}
  <path d="M16 28 C6 21 3 15.5 3 11 a6.5 6.5 0 0 1 13 -1.5 a6.5 6.5 0 0 1 13 1.5 c0 4.5 -3 10 -13 17z" fill="url(#gam)" stroke="#a82c5a" stroke-width="1.2"/>
  <path d="M8 9.5c1-1.5 2.5-2 4-1.6" stroke="#fff" stroke-width="1.6" fill="none" stroke-linecap="round" opacity=".7"/>`);
emoji("vitrine", `${deg("gvi", "#3b5b9a", "#1d2a4a")}
  <rect x="5" y="3" width="22" height="26" rx="3" fill="url(#gvi)" stroke="#e2b552" stroke-width="1.6"/>
  <circle cx="16" cy="13" r="4.5" fill="#cfe3ff"/><path d="M8.5 25c1-5 4-7 7.5-7s6.5 2 7.5 7z" fill="#cfe3ff"/>`);
emoji("profil", `${deg("gpr", "#5fb3e6", "#3b5b9a")}
  <rect x="3" y="6" width="26" height="20" rx="3" fill="url(#gpr)"/>
  <circle cx="11" cy="14" r="3.5" fill="#fff"/><path d="M5.5 22.5c.8-3.5 3-5 5.5-5s4.7 1.5 5.5 5z" fill="#fff"/>
  <path d="M19 12h7M19 16h7M19 20h5" stroke="#dcefff" stroke-width="1.8" stroke-linecap="round"/>`);
emoji("signature", `<path d="M5 25c4-1 6-9 8-9s-1 8 2 8 4-6 6-6 1 4 4 4" fill="none" stroke="#cfe3ff" stroke-width="2" stroke-linecap="round"/>
  <path d="M20 4l6 6-11 11-7 1 1-7z" fill="#e2b552" stroke="#8a5a10" stroke-width="1"/>`);

// ---------- Exploration (HoYoLAB) ----------
emoji("jours", `<rect x="4" y="6" width="24" height="22" rx="3.5" fill="#f4f1ea" stroke="#9a6a24" stroke-width="1.4"/>
  <path d="M4 9.5a3.5 3.5 0 0 1 3.5-3.5h17a3.5 3.5 0 0 1 3.5 3.5V13H4z" fill="#d65b4f"/>
  <path d="M10 3.5v5M22 3.5v5" stroke="#5a3a10" stroke-width="2" stroke-linecap="round"/>
  <path d="M11 20l3.5 3.5L21 17" stroke="#3f9d5a" stroke-width="2.6" fill="none" stroke-linecap="round" stroke-linejoin="round"/>`);
emoji("persos", `<circle cx="11" cy="11" r="5" fill="#9fd8ff"/><path d="M2.5 27c1-6 4.5-9 8.5-9s7.5 3 8.5 9z" fill="#9fd8ff"/>
  <circle cx="22" cy="10" r="4.5" fill="#e2b552"/><path d="M15.5 25c.8-5 3.5-7.8 6.5-7.8s6.3 2.8 7.3 7.8z" fill="#e2b552"/>`);
emoji("exploration", `<path d="M3 7l8-3 10 3 8-3v21l-8 3-10-3-8 3z" fill="#f1e2bd" stroke="#9a6a24" stroke-width="1.3" stroke-linejoin="round"/>
  <path d="M11 4v21M21 7v21" stroke="#c9a15a" stroke-width="1"/>
  <path d="M6 20c3-1 4-5 7-5s4 4 8 2" stroke="#6fc4a8" stroke-width="1.6" fill="none" stroke-dasharray="2 2"/>
  <path d="M23 6a4 4 0 0 1 4 4c0 3-4 7-4 7s-4-4-4-7a4 4 0 0 1 4-4z" fill="#d65b4f"/><circle cx="23" cy="10" r="1.5" fill="#fff"/>`);
emoji("coffre", `${deg("gc", "#c9873e", "#7a4b1e")}
  <path d="M4 14h24v12a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2z" fill="url(#gc)" stroke="#4a2a0e" stroke-width="1.2"/>
  <path d="M4 14a12 8 0 0 1 24 0z" fill="#b57634" stroke="#4a2a0e" stroke-width="1.2"/>
  <path d="M4 14h24M10 7.5v20.5M22 7.5v20.5" stroke="#e2b552" stroke-width="2"/>
  <rect x="13.5" y="12" width="5" height="6" rx="1" fill="#ffe28a" stroke="#8a5a10"/>`);
emoji("oculus", `${rad("go", "#eaffff", "#3fb8b0")}
  <circle cx="16" cy="16" r="12" fill="#3fb8b0" opacity=".25"/>
  <circle cx="16" cy="16" r="8.5" fill="url(#go)"/>
  <path d="M16 9 L20 16 L16 23 L12 16 Z" fill="#fff" opacity=".85"/>
  <path d="M16 1v4M16 27v4M1 16h4M27 16h4M5.5 5.5l2.8 2.8M23.7 23.7l2.8 2.8M26.5 5.5l-2.8 2.8M8.3 23.7l-2.8 2.8" stroke="#7fe0d8" stroke-width="1.4" stroke-linecap="round"/>`);
emoji("teleporteur", `${deg("gt", "#bff4ff", "#3f8fd8")}
  <ellipse cx="16" cy="27" rx="11" ry="3" fill="#6b5a46"/>
  <path d="M16 2 L22 12 L16 24 L10 12 Z" fill="url(#gt)" stroke="#e2b552" stroke-width="1.4" stroke-linejoin="round"/>
  <path d="M16 2v22M10 12h12" stroke="#fff" stroke-width=".8" opacity=".6"/>
  <ellipse cx="16" cy="25" rx="7" ry="1.6" fill="#9fe6ff" opacity=".6"/>`);
emoji("domaine", `<path d="M4 28V12L16 4l12 8v16z" fill="#8d8aa8" stroke="#4a4766" stroke-width="1.3" stroke-linejoin="round"/>
  <path d="M10 28V18a6 6 0 0 1 12 0v10z" fill="#2a1f4a"/>
  <path d="M12 28V19a4 4 0 0 1 8 0v9z" fill="#8a5cd8" opacity=".75"/>
  <path d="${etoile5(16, 11, 2.6)}" fill="#ffe28a"/>`);

// ---------- En ce moment (notes en temps réel) ----------
emoji("resine", `${deg("gr", "#9ff0e6", "#4a7fd8")}
  <path d="M16 2 C11 9 6 14 6 19.5 a10 10 0 0 0 20 0 C26 14 21 9 16 2z" fill="url(#gr)" stroke="#2a4a8a" stroke-width="1.2"/>
  <path d="M19 13a7 7 0 1 0 2 11 5.5 5.5 0 1 1-2-11z" fill="#fff6c8"/>`);
emoji("commission", `<path d="M7 5h16a3 3 0 0 1 3 3v18H10a3 3 0 0 1-3-3z" fill="#f1e2bd" stroke="#9a6a24" stroke-width="1.3"/>
  <path d="M7 23a3 3 0 0 0 3 3 3 3 0 0 0 3-3V8a3 3 0 0 0-3-3" fill="none" stroke="#9a6a24" stroke-width="1.3"/>
  <path d="M15 11h7M15 15h7M15 19h5" stroke="#9a6a24" stroke-width="1.6" stroke-linecap="round"/>
  <circle cx="24" cy="24" r="5" fill="#d65b4f"/><path d="M21.8 24l1.6 1.6 3-3" stroke="#fff" stroke-width="1.6" fill="none"/>`);
emoji("royaume", `${rad("gro", "#d7fff0", "#3f9d8a")}
  <path d="M6 15 L16 6 L26 15 V27 H6 Z" fill="#c9873e" stroke="#5a3a10" stroke-width="1.2" stroke-linejoin="round"/>
  <path d="M3.5 16 L16 4.5 L28.5 16" fill="none" stroke="#b5453b" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/>
  <circle cx="16" cy="20" r="5" fill="url(#gro)" stroke="#2a6a5a"/><path d="M16 17.5v5M13.5 20h5" stroke="#2a6a5a" stroke-width="1.2"/>`);
emoji("expedition", `<path d="M8 4v25" stroke="#7a4b12" stroke-width="2.4" stroke-linecap="round"/>
  <path d="M9 5h16l-4 5 4 5H9z" fill="#5fb3e6" stroke="#2a5a8a" stroke-width="1.2" stroke-linejoin="round"/>
  <path d="${etoile5(15, 10, 3)}" fill="#ffe28a"/>`);
emoji("transformateur", `${deg("gtr", "#ffe28a", "#c98a1c")}
  <circle cx="16" cy="16" r="9" fill="url(#gtr)" stroke="#7a4b12" stroke-width="1.2"/>
  <g stroke="#7a4b12" stroke-width="3.4" stroke-linecap="round"><path d="M16 3v4M16 25v4M3 16h4M25 16h4M6.8 6.8l2.8 2.8M22.4 22.4l2.8 2.8M25.2 6.8l-2.8 2.8M9.6 22.4l-2.8 2.8"/></g>
  <circle cx="16" cy="16" r="4" fill="#5fb3e6" stroke="#2a5a8a"/>`);

// ---------- Éléments ----------
emoji("pyro", `${deg("gpy", "#ffd27a", "#e8452f")}
  <path d="M16 2c1 5 7 7 7 15a7 7 0 0 1-14 0c0-4 2-6 3-8 0 3 1 4 2 4 0-5 1-8 2-11z" fill="url(#gpy)"/>
  <path d="M16 15c1 2 3 3 3 6a3 3 0 0 1-6 0c0-2 2-3 3-6z" fill="#fff1c4"/>`);
emoji("hydro", `${deg("ghy", "#a8ecff", "#2f8fe0")}
  <path d="M16 3 C11 10 7 14 7 19.5 a9 9 0 0 0 18 0 C25 14 21 10 16 3z" fill="url(#ghy)"/>
  <path d="M11.5 19a4.5 4.5 0 0 0 4.5 4.5" stroke="#fff" stroke-width="1.8" fill="none" stroke-linecap="round"/>`);
emoji("anemo", `<g fill="none" stroke="#6fd8b8" stroke-width="2.6" stroke-linecap="round">
  <path d="M4 12h15a4 4 0 1 0-4-4"/><path d="M4 18h20a4 4 0 1 1-4 4"/><path d="M6 24h7"/></g>`);
emoji("electro", `${deg("gel", "#f0c8ff", "#9b5ce0")}
  <path d="M18 2 L7 18 h7 l-2 12 L25 13 h-8 z" fill="url(#gel)" stroke="#5e2f94" stroke-width="1" stroke-linejoin="round"/>`);
emoji("dendro", `${deg("gde", "#d6f58a", "#5aa62f")}
  <path d="M5 27 C5 14 13 5 27 5 C27 19 18 27 5 27z" fill="url(#gde)" stroke="#3a6e1a" stroke-width="1.2"/>
  <path d="M5 27 L21 11" stroke="#3a6e1a" stroke-width="1.6" stroke-linecap="round"/>`);
emoji("cryo", `<g stroke="#a8e8f5" stroke-width="2.2" stroke-linecap="round">
  <path d="M16 3v26M4.7 9.5l22.6 13M4.7 22.5l22.6-13"/>
  <path d="M12.5 5.5L16 8.5l3.5-3M12.5 26.5L16 23.5l3.5 3M5.5 14l4.2-1-1-4.2M26.5 18l-4.2 1 1 4.2M5.5 18l4.2 1-1 4.2M26.5 14l-4.2-1 1-4.2"/></g>`);
emoji("geo", `${deg("gge", "#ffe28a", "#c9871c")}
  <path d="M16 2 L28 10 L24 26 H8 L4 10 Z" fill="url(#gge)" stroke="#7a4b12" stroke-width="1.2" stroke-linejoin="round"/>
  <path d="M16 2 L16 15 L4 10 M16 15 L28 10 M16 15 L8 26 M16 15 L24 26" stroke="#7a4b12" stroke-width=".9" fill="none" opacity=".6"/>`);

// ================= Blox Fruits =================
emoji("jeu_bloxfruits", `${rad("gbf", "#c58cff", "#5a1f9a")}
  <circle cx="16" cy="18" r="12" fill="url(#gbf)" stroke="#3a0f6a" stroke-width="1.2"/>
  <g fill="none" stroke="#f3dcff" stroke-width="1.6" stroke-linecap="round">
    <path d="M9 15c2-3 5-3 6 0s-3 4-1 6 5 0 5-3"/><path d="M18 11c2 0 4 1 4 3"/><path d="M8 22c1 2 3 3 5 3"/></g>
  <path d="M16 6c0-2 1-3 3-4" stroke="#3f7a2a" stroke-width="2.2" stroke-linecap="round" fill="none"/>
  <path d="M17 5c3-3 7-2 8 0-3 2-6 2-8 0z" fill="#6fc44a" stroke="#3f7a2a"/>`);
emoji("beli", `${rad("gbe", "#fff2b0", "#d6a12a")}
  <ellipse cx="16" cy="24" rx="12" ry="4.5" fill="#b07a12"/>
  <ellipse cx="16" cy="21" rx="12" ry="4.5" fill="#d6a12a"/>
  <circle cx="16" cy="13" r="10" fill="url(#gbe)" stroke="#8a5a10" stroke-width="1.3"/>
  <text x="16" y="18" text-anchor="middle" font-size="13" font-weight="900" fill="#8a5a10" font-family="Georgia, serif">B</text>
  <path d="M12 6.5v13M20 6.5v13" stroke="#8a5a10" stroke-width="1" opacity=".5"/>`);
emoji("fragment", `${deg("gfr", "#f2c9ff", "#8a3fd8")}
  <path d="M16 2 L24 11 L21 29 L11 29 L8 11 Z" fill="url(#gfr)" stroke="#4a1a7a" stroke-width="1.2" stroke-linejoin="round"/>
  <path d="M16 2 L14 13 L11 29 M14 13 L24 11 M14 13 L21 29 M14 13 L8 11" stroke="#fff" stroke-width=".8" fill="none" opacity=".55"/>`);
emoji("prime", `<rect x="5" y="2.5" width="22" height="27" rx="2" fill="#f1e2bd" stroke="#9a6a24" stroke-width="1.3"/>
  <text x="16" y="9" text-anchor="middle" font-size="5.5" font-weight="900" fill="#5a3a10" font-family="Georgia, serif">WANTED</text>
  <rect x="9" y="10.5" width="14" height="11" rx="1" fill="#d9c49a"/>
  <circle cx="16" cy="14.5" r="2.8" fill="#7a5a30"/><path d="M11 21.5c.8-3 2.8-4 5-4s4.2 1 5 4z" fill="#7a5a30"/>
  <text x="16" y="27.5" text-anchor="middle" font-size="5" font-weight="800" fill="#b5453b" font-family="Segoe UI, sans-serif">$ ★★★</text>`);
emoji("bf_niveau", `${deg("gni", "#9ff0b8", "#2f9d5a")}
  <path d="M16 2 L28 9 V23 L16 30 L4 23 V9 Z" fill="url(#gni)" stroke="#1a5a32" stroke-width="1.3" stroke-linejoin="round"/>
  <path d="M16 9 L22 16 H18.5 V23 H13.5 V16 H10 Z" fill="#fff"/>`);
emoji("maitrise", `${deg("gma", "#ffd27a", "#e8452f")}
  <circle cx="16" cy="16" r="13" fill="#2a1f3a" stroke="url(#gma)" stroke-width="2.4"/>
  <path d="M10 19v-6a2 2 0 0 1 4 0v-1a2 2 0 0 1 4 0v1a2 2 0 0 1 4 0v6c0 4-3 6-6 6s-6-2-6-6z" fill="#ffd9b0" stroke="#7a4b12" stroke-width="1"/>
  <path d="M7 8l2 2M25 8l-2 2M16 4v2.5" stroke="#ffd27a" stroke-width="1.8" stroke-linecap="round"/>`);
emoji("badge", `${deg("gba", "#ffd27a", "#f0904a")}
  <path d="M16 2 L27 6 V15 C27 22 22 27 16 30 C10 27 5 22 5 15 V6 Z" fill="url(#gba)" stroke="#8a4a10" stroke-width="1.3" stroke-linejoin="round"/>
  <path d="M10.5 16l4 4 7.5-8" stroke="#fff" stroke-width="3" fill="none" stroke-linecap="round" stroke-linejoin="round"/>`);
emoji("badge_etoile", `${deg("gbs", "#ffe28a", "#e09a2a")}
  <path d="M16 2 L27 6 V15 C27 22 22 27 16 30 C10 27 5 22 5 15 V6 Z" fill="#2a2f45" stroke="url(#gbs)" stroke-width="2"/>
  <path d="${etoile5(16, 15.5, 8)}" fill="url(#gbs)"/>`);
emoji("badge_verrou", `<path d="M16 2 L27 6 V15 C27 22 22 27 16 30 C10 27 5 22 5 15 V6 Z" fill="#3a3f55" stroke="#6b7090" stroke-width="1.3" stroke-linejoin="round"/>
  <rect x="11" y="14" width="10" height="8" rx="1.5" fill="#9aa0bd"/>
  <path d="M13 14v-2.5a3 3 0 0 1 6 0V14" stroke="#9aa0bd" stroke-width="2" fill="none"/>`);
emoji("horloge", `${rad("gho", "#ffffff", "#cfe3ff")}
  <circle cx="16" cy="16" r="13" fill="url(#gho)" stroke="#3b5b9a" stroke-width="2"/>
  <path d="M16 8v8l5 3" stroke="#3b5b9a" stroke-width="2.4" fill="none" stroke-linecap="round" stroke-linejoin="round"/>
  <circle cx="16" cy="16" r="1.6" fill="#f0904a"/>`);
emoji("calendrier_semaine", `<rect x="4" y="6" width="24" height="22" rx="3.5" fill="#f4f1ea" stroke="#3b5b9a" stroke-width="1.4"/>
  <path d="M4 9.5a3.5 3.5 0 0 1 3.5-3.5h17a3.5 3.5 0 0 1 3.5 3.5V13H4z" fill="#5fb3e6"/>
  <path d="M10 3.5v5M22 3.5v5" stroke="#2a4a7a" stroke-width="2" stroke-linecap="round"/>
  <g fill="#f0904a"><rect x="7" y="16" width="3" height="3" rx=".6"/><rect x="11.5" y="16" width="3" height="3" rx=".6"/><rect x="16" y="16" width="3" height="3" rx=".6"/><rect x="20.5" y="16" width="3" height="3" rx=".6"/><rect x="7" y="21" width="3" height="3" rx=".6"/><rect x="11.5" y="21" width="3" height="3" rx=".6"/><rect x="16" y="21" width="3" height="3" rx=".6" opacity=".35"/></g>`);
emoji("manette", `${deg("gmn", "#5a6078", "#2a2f45")}
  <path d="M8 9h16c4 0 6 4 6 10 0 4-2 6-4 6-3 0-4-4-6-4h-8c-2 0-3 4-6 4-2 0-4-2-4-6 0-6 2-10 6-10z" fill="url(#gmn)" stroke="#9aa0bd" stroke-width="1.2"/>
  <path d="M9 13v6M6 16h6" stroke="#fff" stroke-width="2" stroke-linecap="round"/>
  <circle cx="22" cy="14" r="1.6" fill="#ef6b6b"/><circle cx="25" cy="17" r="1.6" fill="#4ed39a"/><circle cx="19" cy="17" r="1.6" fill="#5fb3e6"/><circle cx="22" cy="20" r="1.6" fill="#f2c14e"/>`);
emoji("mer", `${deg("gme", "#7fd0ff", "#1f5fa5")}
  <circle cx="16" cy="16" r="14" fill="url(#gme)"/>
  <path d="M10 17h12l-2 4h-8z" fill="#7a4b12"/><path d="M16 6v11" stroke="#5a3a10" stroke-width="1.4"/>
  <path d="M16.5 7l6 8h-6z" fill="#fff"/><path d="M15.5 9l-4.5 6h4.5z" fill="#f4f1ea"/>
  <path d="M4 23c2-1.5 4-1.5 6 0s4 1.5 6 0 4-1.5 6 0 4 1.5 6 0" stroke="#fff" stroke-width="1.6" fill="none" stroke-linecap="round"/>`);
emoji("joueurs", `<circle cx="9" cy="12" r="3.6" fill="#f0904a"/><path d="M3 24c.6-4 3-6 6-6s5.4 2 6 6z" fill="#f0904a"/>
  <circle cx="23" cy="12" r="3.6" fill="#5fb3e6"/><path d="M17 24c.6-4 3-6 6-6s5.4 2 6 6z" fill="#5fb3e6"/>
  <circle cx="16" cy="10" r="4.4" fill="#ffe28a"/><path d="M8.5 27c.8-5 3.8-7.5 7.5-7.5s6.7 2.5 7.5 7.5z" fill="#ffe28a"/>
  <circle cx="27" cy="5" r="3" fill="#4ed39a" stroke="#0f1117" stroke-width="1.2"/>`);
emoji("visites", `<path d="M2 16c4-7 9-10 14-10s10 3 14 10c-4 7-9 10-14 10S6 23 2 16z" fill="#f4f1ea" stroke="#3b5b9a" stroke-width="1.4"/>
  <circle cx="16" cy="16" r="6" fill="#5fb3e6"/><circle cx="16" cy="16" r="2.8" fill="#1d2a4a"/><circle cx="17.5" cy="14.5" r="1" fill="#fff"/>`);

emoji("ticket", `${deg("gti", "#ffd27a", "#f0904a", false)}
  <path d="M3 9a2 2 0 0 1 2-2h22a2 2 0 0 1 2 2v3a3.5 3.5 0 0 0 0 7v3a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-3a3.5 3.5 0 0 0 0-7z" fill="url(#gti)" stroke="#8a4a10" stroke-width="1.2"/>
  <path d="M21 8v16" stroke="#8a4a10" stroke-width="1.2" stroke-dasharray="2 2"/>
  <path d="${etoile5(12, 16, 5)}" fill="#fff6d0"/>`);
emoji("amis", `<circle cx="11" cy="11" r="4.5" fill="#4ed39a"/><path d="M3 26c.8-5 4-8 8-8s7.2 3 8 8z" fill="#4ed39a"/>
  <circle cx="22" cy="11" r="4.5" fill="#5fb3e6"/><path d="M14 26c.8-5 4-8 8-8s7.2 3 8 8z" fill="#5fb3e6"/>
  <path d="M16 6.5c1.4-1.6 4-1 4 1.2 0 1.8-2.6 3.3-4 4.3-1.4-1-4-2.5-4-4.3 0-2.2 2.6-2.8 4-1.2z" fill="#ef6b8a"/>`);

// ================= AllMyStats : logo et interface =================
const AMS_CORAIL = "#FF6B5E", AMS_OR = "#FFC44D", AMS_TURQUOISE = "#33D1C1";
const HEXAGONE = "M16 1.5 L28.6 8.75 V23.25 L16 30.5 L3.4 23.25 V8.75 Z";

emoji("ams", `${deg("gams", "#2B3270", "#151936")}
  <path d="${HEXAGONE}" fill="url(#gams)" stroke="#3E4796" stroke-width="1.2" stroke-linejoin="round"/>
  <rect x="8.6" y="17" width="4.2" height="7.5" rx="1.4" fill="${AMS_CORAIL}"/>
  <rect x="13.9" y="13" width="4.2" height="11.5" rx="1.4" fill="${AMS_OR}"/>
  <rect x="19.2" y="9.5" width="4.2" height="15" rx="1.4" fill="${AMS_TURQUOISE}"/>
  <path d="M24.6 4.2 L25.4 6.4 L27.6 7.2 L25.4 8 L24.6 10.2 L23.8 8 L21.6 7.2 L23.8 6.4 Z" fill="#fff"/>`);

emoji("reglages", `${deg("grg", "#C9D0F2", "#7C86C2")}
  <path d="M13.6 2.5h4.8l.8 3.4 2.3 1 3-1.8 3.4 3.4-1.8 3 1 2.3 3.4.8v4.8l-3.4.8-1 2.3 1.8 3-3.4 3.4-3-1.8-2.3 1-.8 3.4h-4.8l-.8-3.4-2.3-1-3 1.8-3.4-3.4 1.8-3-1-2.3-3.4-.8v-4.8l3.4-.8 1-2.3-1.8-3 3.4-3.4 3 1.8 2.3-1z"
    fill="url(#grg)" stroke="#4A5290" stroke-width="1" stroke-linejoin="round"/>
  <circle cx="16" cy="16" r="5" fill="#1C2146" stroke="#4A5290"/><circle cx="16" cy="16" r="2" fill="${AMS_OR}"/>`);
emoji("actualiser", `<g fill="none" stroke-width="3.2" stroke-linecap="round">
  <path d="M25.5 12.5A10 10 0 0 0 7 10" stroke="${AMS_TURQUOISE}"/><path d="M6.5 19.5A10 10 0 0 0 25 22" stroke="${AMS_OR}"/></g>
  <path d="M27.5 5v8.5H19z" fill="${AMS_TURQUOISE}"/><path d="M4.5 27v-8.5H13z" fill="${AMS_OR}"/>`);
emoji("connexion", `<g fill="none" stroke-width="3.6" stroke-linecap="round">
  <path d="M13.5 18.5l5-5" stroke="#fff"/>
  <path d="M15 9.5l2.6-2.6a5.3 5.3 0 0 1 7.5 7.5L22.5 17" stroke="${AMS_TURQUOISE}"/>
  <path d="M17 22.5l-2.6 2.6a5.3 5.3 0 0 1-7.5-7.5L9.5 15" stroke="${AMS_OR}"/></g>`);
emoji("connecte", `${deg("gcx", "#6FF0C8", "#1FAE86")}
  <circle cx="16" cy="16" r="13.5" fill="url(#gcx)"/>
  <path d="M9.5 16.5l4.4 4.4 8.6-9.4" stroke="#0D3B2E" stroke-width="3.4" fill="none" stroke-linecap="round" stroke-linejoin="round"/>`);
emoji("deconnexion", `<path d="M13 5H8a3 3 0 0 0-3 3v16a3 3 0 0 0 3 3h5" stroke="#9AA3C7" stroke-width="3" fill="none" stroke-linecap="round"/>
  <path d="M14 16h13M21.5 10l6 6-6 6" stroke="${AMS_CORAIL}" stroke-width="3.2" fill="none" stroke-linecap="round" stroke-linejoin="round"/>`);
emoji("ok", `<circle cx="16" cy="16" r="13" fill="#33D19A"/>
  <path d="M10 16.5l4 4 8-8.5" stroke="#0D3B2E" stroke-width="3.4" fill="none" stroke-linecap="round" stroke-linejoin="round"/>`);
emoji("erreur", `<circle cx="16" cy="16" r="13" fill="${AMS_CORAIL}"/>
  <path d="M16 8.5v9" stroke="#3B0D0A" stroke-width="3.6" stroke-linecap="round"/><circle cx="16" cy="22.8" r="2.1" fill="#3B0D0A"/>`);
emoji("neutre", `<circle cx="16" cy="16" r="13" fill="#4A5290"/>
  <path d="M10 16h12" stroke="#C9D0F2" stroke-width="3.4" stroke-linecap="round"/>`);
emoji("alerte", `${deg("gal", "#FFE08A", "#FFB020")}
  <path d="M16 3.5 L29.5 27 H2.5 Z" fill="url(#gal)" stroke="#8A5A10" stroke-width="1.4" stroke-linejoin="round"/>
  <path d="M16 11.5v7.5" stroke="#4A2E05" stroke-width="3.2" stroke-linecap="round"/><circle cx="16" cy="23" r="1.9" fill="#4A2E05"/>`);
emoji("astuce", `${rad("gas", "#FFF6C8", "#FFC44D")}
  <path d="M16 3a9 9 0 0 0-5.2 16.4c.8.6 1.2 1.4 1.2 2.4V23h8v-1.2c0-1 .4-1.8 1.2-2.4A9 9 0 0 0 16 3z" fill="url(#gas)" stroke="#8A5A10" stroke-width="1.2"/>
  <rect x="12" y="24" width="8" height="2.6" rx="1" fill="#9AA3C7"/><rect x="13" y="27.4" width="6" height="2.2" rx="1" fill="#7C86C2"/>
  <path d="M14 15l2 2 2-2M16 17v5" stroke="#8A5A10" stroke-width="1.4" fill="none" stroke-linecap="round"/>`);
emoji("maj", `${deg("gmj", "#C9A8FF", "#7B4DE0")}
  <rect x="4" y="12" width="24" height="17" rx="3" fill="url(#gmj)"/>
  <rect x="2.5" y="8" width="27" height="6" rx="2" fill="#9B6BFF"/>
  <path d="M16 8v21" stroke="${AMS_OR}" stroke-width="3.2"/>
  <path d="M16 8c-2-4-7-5-7-2s5 2 7 2c2 0 7 1 7-2s-5-2-7 2z" fill="none" stroke="${AMS_OR}" stroke-width="2.2" stroke-linejoin="round"/>
  <path d="M25.5 2.5l.7 1.9 1.9.7-1.9.7-.7 1.9-.7-1.9-1.9-.7 1.9-.7z" fill="#fff"/>`);
emoji("supprimer", `<path d="M8 8l16 16M24 8L8 24" stroke="${AMS_CORAIL}" stroke-width="3.6" stroke-linecap="round"/>`);
emoji("fermer", `<path d="M9 9l14 14M23 9L9 23" stroke="#C9D0F2" stroke-width="3.2" stroke-linecap="round"/>`);
emoji("hausse", `<path d="M16 6 L27 22 H5 Z" fill="#33D19A" stroke="#0D6B4A" stroke-width="1.4" stroke-linejoin="round"/>`);
emoji("baisse", `<path d="M16 26 L27 10 H5 Z" fill="${AMS_CORAIL}" stroke="#8A2A20" stroke-width="1.4" stroke-linejoin="round"/>`);
emoji("egal", `<path d="M7 12h18M7 20h18" stroke="#9AA3C7" stroke-width="3.4" stroke-linecap="round"/>`);
emoji("etoile", `${deg("get", "#FFE28A", "#F2A92A")}
  <path d="${etoile5(16, 17, 14)}" fill="url(#get)" stroke="#A8661A" stroke-width="1.2" stroke-linejoin="round"/>`);
emoji("ajouter", `<circle cx="16" cy="16" r="13" fill="${AMS_TURQUOISE}"/>
  <path d="M16 9.5v13M9.5 16h13" stroke="#0B3B36" stroke-width="3.4" stroke-linecap="round"/>`);
emoji("fichier_zip", `<path d="M7 3h12l7 7v19H7z" fill="#E9ECFA" stroke="#4A5290" stroke-width="1.3" stroke-linejoin="round"/>
  <path d="M19 3v7h7" fill="#C9D0F2" stroke="#4A5290" stroke-width="1.3" stroke-linejoin="round"/>
  <path d="M13 6h2v2h-2zM15 8h2v2h-2zM13 10h2v2h-2zM15 12h2v2h-2z" fill="#7C86C2"/>
  <rect x="12" y="15" width="6" height="7" rx="1.5" fill="${AMS_OR}" stroke="#8A5A10"/>`);
emoji("quitter", `<path d="M10 8.5a10 10 0 1 0 12 0" stroke="${AMS_CORAIL}" stroke-width="3.4" fill="none" stroke-linecap="round"/>
  <path d="M16 4v11" stroke="${AMS_CORAIL}" stroke-width="3.4" stroke-linecap="round"/>`);
emoji("graphique", `<rect x="3" y="4" width="26" height="24" rx="4" fill="#1C2146" stroke="#4A5290" stroke-width="1.3"/>
  <path d="M7 22l6-7 5 4 7-9" stroke="${AMS_TURQUOISE}" stroke-width="2.8" fill="none" stroke-linecap="round" stroke-linejoin="round"/>
  <circle cx="25" cy="10" r="2.4" fill="${AMS_OR}"/>`);
emoji("historique", `<circle cx="17" cy="16" r="11" fill="#1C2146" stroke="#9AA3C7" stroke-width="2.4"/>
  <path d="M17 10v6.5l4 2.5" stroke="${AMS_OR}" stroke-width="2.6" fill="none" stroke-linecap="round"/>
  <path d="M3 12.5l3 4 4-3" stroke="#9AA3C7" stroke-width="2.4" fill="none" stroke-linecap="round" stroke-linejoin="round"/>`);
emoji("ecran", `<rect x="2.5" y="4" width="27" height="18.5" rx="3" fill="#1C2146" stroke="#9AA3C7" stroke-width="1.8"/>
  <path d="M11 29h10M16 22.5V29" stroke="#9AA3C7" stroke-width="2.4" stroke-linecap="round"/>
  <path d="M6.5 11V8h3M25.5 11V8h-3M6.5 15.5v3h3M25.5 15.5v3h-3" stroke="${AMS_OR}" stroke-width="1.8" fill="none" stroke-linecap="round" stroke-linejoin="round"/>
  <path d="M8 13.2h16" stroke="${AMS_TURQUOISE}" stroke-width="2.2" stroke-linecap="round"/>
  <rect x="11" y="9.6" width="6" height="1.6" rx=".8" fill="#4A5290"/><rect x="11" y="15.3" width="9" height="1.6" rx=".8" fill="#4A5290"/>`);
emoji("chrono", `<circle cx="16" cy="18" r="11.5" fill="#1C2146" stroke="${AMS_OR}" stroke-width="2.4"/>
  <rect x="13" y="2.5" width="6" height="3.4" rx="1.2" fill="${AMS_OR}"/><path d="M25 8.5l2-2" stroke="${AMS_OR}" stroke-width="2.4" stroke-linecap="round"/>
  <path d="M16 18V11.5" stroke="${AMS_TURQUOISE}" stroke-width="2.6" stroke-linecap="round"/><circle cx="16" cy="18" r="2" fill="#EEF0FA"/>`);
emoji("vide", `<path d="M4 13l12-6 12 6v12l-12 6-12-6z" fill="#2C3360" stroke="#4A5290" stroke-width="1.3" stroke-linejoin="round"/>
  <path d="M4 13l12 6 12-6M16 19v12" stroke="#4A5290" stroke-width="1.3" fill="none"/>
  <path d="M10 5c1-2 3-2 4 0M19 3c1-1.5 3-1.5 3.6 0" stroke="#9AA3C7" stroke-width="1.4" fill="none" stroke-linecap="round"/>`);
emoji("cle", `<circle cx="10" cy="16" r="6.5" fill="none" stroke="${AMS_OR}" stroke-width="3.2"/>
  <path d="M16 16h13M24.5 16v5M28.5 16v3.5" stroke="${AMS_OR}" stroke-width="3.2" stroke-linecap="round"/>`);
emoji("chevron", `<path d="M9 12l7 7 7-7" stroke="#C9D0F2" stroke-width="3.2" fill="none" stroke-linecap="round" stroke-linejoin="round"/>`);
emoji("enregistrer", `<rect x="4" y="4" width="24" height="24" rx="4" fill="${AMS_TURQUOISE}"/>
  <rect x="9" y="4" width="14" height="8" fill="#0B3B36" opacity=".55"/><rect x="9" y="17" width="14" height="11" rx="1.5" fill="#E9FFFB"/>`);
emoji("jeu", `${deg("gje", "#5A6078", "#2A2F45")}
  <path d="M8 9h16c4 0 6 4 6 10 0 4-2 6-4 6-3 0-4-4-6-4h-8c-2 0-3 4-6 4-2 0-4-2-4-6 0-6 2-10 6-10z" fill="url(#gje)" stroke="#9AA3C7" stroke-width="1.2"/>
  <path d="M9 13v6M6 16h6" stroke="#fff" stroke-width="2" stroke-linecap="round"/>
  <circle cx="22" cy="14" r="1.6" fill="${AMS_CORAIL}"/><circle cx="25" cy="17" r="1.6" fill="${AMS_TURQUOISE}"/>
  <circle cx="19" cy="17" r="1.6" fill="#5FB3E6"/><circle cx="22" cy="20" r="1.6" fill="${AMS_OR}"/>`);

// ================= Call of Duty (insignes originaux, pas les logos officiels) =================
const POCHOIR = `font-family="Bahnschrift, 'DejaVu Sans Condensed', Impact, sans-serif" font-weight="900" text-anchor="middle"`;
function insigne(nom, forme, fond, bord, texte, couleurTexte, extra = "", taille = 10) {
  emoji(nom, `${deg("g" + nom, fond[0], fond[1])}
    <path d="${forme}" fill="url(#g${nom})" stroke="${bord}" stroke-width="1.5" stroke-linejoin="round"/>
    ${extra}
    <text x="16" y="${19.5 + (taille - 10) * 0.35}" ${POCHOIR} font-size="${taille}" fill="${couleurTexte}" letter-spacing="-.3">${texte}</text>`);
}
const BOUCLIER = "M16 2 L28 6.5 V15 C28 22.5 22.6 27.6 16 30 C9.4 27.6 4 22.5 4 15 V6.5 Z";
const CARRE = "M5 4 H27 A2 2 0 0 1 29 6 V26 A2 2 0 0 1 27 28 H5 A2 2 0 0 1 3 26 V6 A2 2 0 0 1 5 4 Z";
const LOSANGE = "M16 2 L30 16 L16 30 L2 16 Z";
const ROND = "M16 2.5 A13.5 13.5 0 1 1 15.99 2.5 Z";

emoji("famille_call_of_duty", `${deg("gfcod", "#C9CED8", "#7E8796")}
  <path d="M9 7 C9 4.5 11 3.5 12.5 3.5 H19.5 C21 3.5 23 4.5 23 7 V22 C23 24.5 21 26 19 26 H13 C11 26 9 24.5 9 22 Z" fill="url(#gfcod)" stroke="#4A5160" stroke-width="1.3" transform="rotate(-12 16 15)"/>
  <path d="M11 9 C11 6.5 13 5.5 14.5 5.5 H21.5 C23 5.5 25 6.5 25 9 V24 C25 26.5 23 28 21 28 H15 C13 28 11 26.5 11 24 Z" fill="#DDE2EA" stroke="#4A5160" stroke-width="1.3"/>
  <circle cx="18" cy="9" r="1.4" fill="#4A5160"/>
  <path d="M14 14h8M14 17.5h8M14 21h5" stroke="#5A6275" stroke-width="1.6" stroke-linecap="round"/>
  <path d="M18 9 C14 4 8 3 5 5" stroke="#9AA3B5" stroke-width="1.2" fill="none" stroke-dasharray="1.2 1.2"/>`);
insigne("jeu_cod_bo6", BOUCLIER, ["#3A3F4C", "#14161C"], "#E8A33D", "BO6", "#F2B24E");
insigne("jeu_cod_bo7", HEXAGONE, ["#3D2B2B", "#140F0F"], "#F25C3C", "BO7", "#FF7A55");
insigne("jeu_cod_coldwar", ROND, ["#20324F", "#0C1626"], "#4FA3E0", "CW", "#CFE6FF",
  `<path d="${etoile5(16, 9, 3.2)}" fill="#E5484D"/>`, 11);
insigne("jeu_cod_mw4", CARRE, ["#2E3A27", "#11160E"], "#7FC25B", "MW4", "#A6E07F");
insigne("jeu_cod_mw3", LOSANGE, ["#2E2A4A", "#121024"], "#9C8CF0", "MW3", "#C9BEFF", "", 8.5);
insigne("jeu_cod_mw2", LOSANGE, ["#1F3A40", "#0C1A1D"], "#5BB7C9", "MW2", "#A8E8F4", "", 8.5);
emoji("jeu_cod_warzone", `${deg("gwz", "#5B5236", "#221E12")}
  <path d="${ROND}" fill="url(#gwz)" stroke="#C9B458" stroke-width="1.5"/>
  <path d="M8 13 C8 7.5 24 7.5 24 13 C21.5 11.6 19 11.6 16 13 C13 11.6 10.5 11.6 8 13 Z" fill="#E9DDA0"/>
  <path d="M8.5 13 L15 21 M23.5 13 L17 21 M16 13 V21" stroke="#E9DDA0" stroke-width=".9"/>
  <text x="16" y="27" ${POCHOIR} font-size="7.5" fill="#E9DDA0">WZ</text>`);
emoji("jeu_cod_warzone_mw4", `${deg("gwz4", "#24493E", "#0C1C17")}
  <path d="${ROND}" fill="url(#gwz4)" stroke="#5CC9A7" stroke-width="1.5"/>
  <path d="M8 13 C8 7.5 24 7.5 24 13 C21.5 11.6 19 11.6 16 13 C13 11.6 10.5 11.6 8 13 Z" fill="#B4F0DA"/>
  <path d="M8.5 13 L15 21 M23.5 13 L17 21 M16 13 V21" stroke="#B4F0DA" stroke-width=".9"/>
  <text x="16" y="27" ${POCHOIR} font-size="7" fill="#B4F0DA">WZ4</text>`);

emoji("cod_kd", `<circle cx="16" cy="16" r="11" fill="none" stroke="#E5E9F2" stroke-width="2.4"/>
  <path d="M16 2.5v7M16 22.5v7M2.5 16h7M22.5 16h7" stroke="#E5E9F2" stroke-width="2.4" stroke-linecap="round"/>
  <path d="M11 21 L21 11" stroke="${AMS_OR}" stroke-width="3" stroke-linecap="round"/>
  <circle cx="16" cy="16" r="2" fill="${AMS_CORAIL}"/>`);
emoji("cod_elimination", `<circle cx="16" cy="16" r="11" fill="#2A1A1A" stroke="${AMS_CORAIL}" stroke-width="2.2"/>
  <path d="M16 3v6M16 23v6M3 16h6M23 16h6" stroke="${AMS_CORAIL}" stroke-width="2.2" stroke-linecap="round"/>
  <path d="M12.5 12.5l7 7M19.5 12.5l-7 7" stroke="#fff" stroke-width="2.6" stroke-linecap="round"/>`);
emoji("cod_mort", `${deg("gcm", "#C7CCD8", "#7E8596")}
  <path d="M8 29V13a8 8 0 0 1 16 0v16z" fill="url(#gcm)" stroke="#4A5160" stroke-width="1.3"/>
  <path d="M16 11v10M12 14.5h8" stroke="#4A5160" stroke-width="2.4" stroke-linecap="round"/>
  <path d="M4 29h24" stroke="#5A8A3E" stroke-width="2.6" stroke-linecap="round"/>`);
emoji("cod_victoire", `${deg("gcv", "#FFE28A", "#E09A2A")}
  <path d="M10 4v24" stroke="#C9CED8" stroke-width="2.4" stroke-linecap="round"/>
  <path d="M11 5h15l-3.5 5 3.5 5H11z" fill="url(#gcv)" stroke="#8A5A10" stroke-width="1.1" stroke-linejoin="round"/>
  <path d="${etoile5(17.5, 10, 2.6)}" fill="#fff"/>
  <path d="M5 28h10" stroke="#9AA3C7" stroke-width="2.4" stroke-linecap="round"/>`);
emoji("cod_defaite", `<path d="M10 4v24" stroke="#9AA3C7" stroke-width="2.4" stroke-linecap="round"/>
  <path d="M11 5h13l-2 4 3 3-3 4H11z" fill="#5A6078" stroke="#3A3F55" stroke-width="1.1" stroke-linejoin="round"/>
  <path d="M17 5l-2 4 3 3-2 4" stroke="#1C2146" stroke-width="1.6" fill="none"/>
  <path d="M5 28h10" stroke="#9AA3C7" stroke-width="2.4" stroke-linecap="round"/>`);
emoji("cod_ratio", `<circle cx="16" cy="16" r="12" fill="#5A6078"/>
  <path d="M16 16V4a12 12 0 0 1 10.4 18z" fill="${AMS_OR}"/>
  <circle cx="16" cy="16" r="5" fill="#1C2146"/>`);
emoji("cod_precision", `<circle cx="16" cy="16" r="13" fill="#F4F1EA"/><circle cx="16" cy="16" r="9.5" fill="${AMS_CORAIL}"/>
  <circle cx="16" cy="16" r="6" fill="#F4F1EA"/><circle cx="16" cy="16" r="2.8" fill="${AMS_CORAIL}"/>
  <path d="M29 3l-11 11" stroke="#4A5160" stroke-width="2" stroke-linecap="round"/><path d="M29 3l-4.5.6 3.9 3.9z" fill="#4A5160"/>`);
emoji("cod_score", `<path d="M4 22a12 12 0 0 1 24 0" fill="none" stroke="#3A3F55" stroke-width="5" stroke-linecap="round"/>
  <path d="M4 22a12 12 0 0 1 20.5-8.5" fill="none" stroke="${AMS_TURQUOISE}" stroke-width="5" stroke-linecap="round"/>
  <path d="M16 22l7-9" stroke="#fff" stroke-width="2.6" stroke-linecap="round"/><circle cx="16" cy="22" r="2.6" fill="${AMS_OR}"/>`);
emoji("cod_niveau", `${deg("gcn", "#FFE28A", "#E09A2A")}
  <path d="M6 13l10-6 10 6v4l-10-6-10 6z" fill="url(#gcn)" stroke="#8A5A10" stroke-width="1"/>
  <path d="M6 20l10-6 10 6v4l-10-6-10 6z" fill="url(#gcn)" stroke="#8A5A10" stroke-width="1"/>
  <path d="M6 27l10-6 10 6v3l-10-6-10 6z" fill="#C9CED8" stroke="#4A5160" stroke-width="1"/>`);
emoji("cod_prestige", `${deg("gcp", "#D9C2FF", "#8B5CF6")}
  <path d="M16 2 L28 9 V23 L16 30 L4 23 V9 Z" fill="url(#gcp)" stroke="#4A2A8A" stroke-width="1.3" stroke-linejoin="round"/>
  <path d="${etoile5(16, 16.5, 8)}" fill="#FFE28A" stroke="#8A5A10" stroke-width=".8"/>`);
emoji("cod_manche", `<rect x="3" y="5" width="26" height="22" rx="3" fill="#2A1414" stroke="#B5353B" stroke-width="1.4"/>
  <path d="M8 10v12M12 10v12M16 10v12M20 10v12M6 19l17-7" stroke="#E5484D" stroke-width="2.4" stroke-linecap="round"/>
  <path d="M25 9v14" stroke="#E5484D" stroke-width="2.4" stroke-linecap="round"/>`);
emoji("cod_zombie", `${rad("gcz", "#B5E07A", "#5E9A3A")}
  <path d="M6 14a10 10 0 0 1 20 0v6c0 5-4 9-10 9S6 25 6 20z" fill="url(#gcz)" stroke="#2F5A1A" stroke-width="1.3"/>
  <circle cx="12" cy="15.5" r="2.6" fill="#F4F1EA"/><circle cx="12.6" cy="16" r="1.1" fill="#B5353B"/>
  <circle cx="20.5" cy="15" r="2" fill="#F4F1EA"/><circle cx="20.8" cy="15.4" r=".9" fill="#B5353B"/>
  <path d="M11 23c2-1.5 8-1.5 10 0" stroke="#2F5A1A" stroke-width="1.6" fill="none" stroke-linecap="round"/>
  <path d="M13 22.6v1.8M16 22.2v1.8M19 22.6v1.8" stroke="#F4F1EA" stroke-width="1.2"/>
  <path d="M9 7l3 2M23 6l-2 3" stroke="#2F5A1A" stroke-width="1.4" stroke-linecap="round"/>`);
emoji("cod_podium", `<rect x="11.5" y="11" width="9" height="18" rx="1" fill="${AMS_OR}"/>
  <rect x="3" y="17" width="9" height="12" rx="1" fill="#C9CED8"/><rect x="20" y="20" width="9" height="9" rx="1" fill="#D08A4A"/>
  <text x="16" y="21" ${POCHOIR} font-size="7" fill="#5A3A05">1</text>
  <path d="${etoile5(16, 6, 3.6)}" fill="#FFE28A"/>`);
emoji("cod_parachute", `<path d="M3 14 C3 5 29 5 29 14 C25 12 20.5 12 16 14 C11.5 12 7 12 3 14 Z" fill="#C9B458" stroke="#6B5E25" stroke-width="1.2"/>
  <path d="M3.5 14 L14 25 M28.5 14 L18 25 M16 14 V25" stroke="#9AA3C7" stroke-width="1.1"/>
  <rect x="13" y="24" width="6" height="6" rx="1.5" fill="#5A6078"/>`);
emoji("cod_session", `<circle cx="16" cy="18" r="11" fill="#1C2146" stroke="#C9CED8" stroke-width="2.4"/>
  <path d="M13 3h6M16 3v4M25 8l2 2" stroke="#C9CED8" stroke-width="2.4" stroke-linecap="round"/>
  <path d="M16 18V11" stroke="${AMS_CORAIL}" stroke-width="2.6" stroke-linecap="round"/>
  <path d="M16 18a7 7 0 0 0 7-7" fill="none" stroke="${AMS_TURQUOISE}" stroke-width="2.6" stroke-linecap="round"/>`);
emoji("cod_dossier", `${deg("gcd", "#8A7A52", "#5A4E30")}
  <path d="M3 8a2 2 0 0 1 2-2h7l3 3h12a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" fill="url(#gcd)" stroke="#3A3220" stroke-width="1.2"/>
  <rect x="7" y="12" width="18" height="11" rx="1" fill="#E9E2CC"/>
  <path d="M10 15.5h8M10 19h12" stroke="#8A7A52" stroke-width="1.5" stroke-linecap="round"/>
  <path d="${etoile5(23, 14.8, 2.4)}" fill="#E5484D"/>`);

// Utilitaire : renvoie l'emoji (ou le texte de secours, ex. un vrai emoji)
function icone(nom, secours = "") {
  return (nom && ICONES[String(nom).toLowerCase()]) || secours;
}

// Texte avec les symboles remplacés par nos emojis (★ -> étoile dessinée)
function texteRiche(t) {
  return esc(t).replace(/★/g, `<span class="mini-emoji">${ICONES.etoile}</span>`);
}

// ---------- Pokémon GO (dessins originaux) ----------
emoji("jeu_pokemongo", `${rad("gpg", "#8EE3FF", "#1E7FC2")}
  <path d="M16 2.5c-6 0-10.5 4.5-10.5 10.3 0 7.4 8.4 14.6 9.6 15.6.5.4 1.3.4 1.8 0 1.2-1 9.6-8.2 9.6-15.6C26.5 7 22 2.5 16 2.5z" fill="url(#gpg)" stroke="#0E4A78" stroke-width="1.3"/>
  <circle cx="16" cy="12.8" r="5.6" fill="#EEF7FF" stroke="#0E4A78" stroke-width="1.2"/>
  <path d="M16 8.6l1.2 2.9 3 .3-2.3 2 .7 3-2.6-1.6-2.6 1.6.7-3-2.3-2 3-.3z" fill="#FFC44D"/>
  <ellipse cx="16" cy="29.4" rx="6" ry="1.4" fill="#0E4A78" opacity=".35"/>`);
emoji("pogo_niveau", `${deg("gpn", "#7FD6FF", "#2C86D9")}
  <path d="M16 2.5l11 4v9c0 6.8-4.6 11.6-11 14-6.4-2.4-11-7.2-11-14v-9z" fill="url(#gpn)" stroke="#0E4A78" stroke-width="1.3" stroke-linejoin="round"/>
  <path d="M10.5 18.5l5.5-5 5.5 5M10.5 13.5l5.5-5 5.5 5" stroke="#EEF7FF" stroke-width="2.6" fill="none" stroke-linecap="round" stroke-linejoin="round"/>`);
emoji("pogo_xp", `${rad("gpx", "#FFF3B8", "#FFB020")}
  <path d="M16 2l3.2 8.6 9 .6-7 5.7 2.4 8.8L16 20.8l-7.6 4.9 2.4-8.8-7-5.7 9-.6z" fill="url(#gpx)" stroke="#8A5A10" stroke-width="1.2" stroke-linejoin="round"/>
  <path d="M27 24l1.2 2.6 2.6 1.2-2.6 1.2L27 31.6l-1.2-2.6-2.6-1.2 2.6-1.2z" fill="#FFE08A"/>`);
emoji("pogo_distance", `<path d="M9.5 3.5c3 0 4.6 3 4.4 7-.2 3.4-1.6 5.6-4.4 5.6S5.3 13.9 5.1 10.5c-.2-4 1.4-7 4.4-7z" fill="#33D1C1" stroke="#0E5E57" stroke-width="1.2"/>
  <rect x="6.6" y="17.6" width="6" height="4.2" rx="2.1" fill="#33D1C1" stroke="#0E5E57" stroke-width="1.2"/>
  <path d="M22.5 9.5c3 0 4.6 3 4.4 7-.2 3.4-1.6 5.6-4.4 5.6s-4.2-2.2-4.4-5.6c-.2-4 1.4-7 4.4-7z" fill="#7FE6DB" stroke="#0E5E57" stroke-width="1.2"/>
  <rect x="19.6" y="23.6" width="6" height="4.2" rx="2.1" fill="#7FE6DB" stroke="#0E5E57" stroke-width="1.2"/>`);
emoji("pogo_attrapes", `<path d="M5 27L15.5 16.5" stroke="#B07A3A" stroke-width="3" stroke-linecap="round"/>
  <circle cx="20.5" cy="11.5" r="8.5" fill="#E8F6FF" fill-opacity=".25" stroke="#9AA3C7" stroke-width="2"/>
  <path d="M13.5 6.5c3 3 9 9 13 11M12.5 12c3.5 1.5 8 6 9.5 9.5M17 3.5c.5 4 3.5 8.5 11.5 9.5" stroke="#9AA3C7" stroke-width="1" fill="none"/>
  <path d="M21 9.5l1 2.2 2.4.2-1.8 1.6.6 2.3-2.2-1.3-2 1.3.5-2.3-1.8-1.6 2.4-.2z" fill="#FFC44D"/>`);
emoji("pogo_pokestop", `<path d="M16 29V14" stroke="#9AA3C7" stroke-width="2.4" stroke-linecap="round"/>
  <ellipse cx="16" cy="29" rx="6" ry="1.6" fill="#4A5290"/>
  <circle cx="16" cy="10" r="7.5" fill="#3FB6E8" stroke="#0E4A78" stroke-width="1.4"/>
  <circle cx="16" cy="10" r="3.4" fill="#EEF7FF"/>
  <path d="M8.5 10h4M19.5 10h4" stroke="#0E4A78" stroke-width="1.4"/>`);
emoji("pogo_capture", `<rect x="8" y="2.5" width="16" height="27" rx="3.5" fill="#1C2146" stroke="#9AA3C7" stroke-width="1.8"/>
  <rect x="10.5" y="6" width="11" height="17" rx="1.5" fill="#3FB6E8"/>
  <path d="M10.5 19.5l3.5-4 3 3 2-2 2.5 3v3.5h-11z" fill="#EEF7FF" opacity=".9"/>
  <circle cx="18.6" cy="10" r="1.8" fill="#FFC44D"/>
  <path d="M4 7V4h3M28 7V4h-3M4 25v3h3M28 25v3h-3" stroke="#FFC44D" stroke-width="1.8" fill="none" stroke-linecap="round"/>`);
emoji("dossier_photos", `<path d="M3 8.5a2.5 2.5 0 0 1 2.5-2.5H12l3 3h11.5A2.5 2.5 0 0 1 29 11.5V25a2.5 2.5 0 0 1-2.5 2.5h-21A2.5 2.5 0 0 1 3 25z" fill="#FFC44D" stroke="#8A5A10" stroke-width="1.2"/>
  <rect x="9" y="13" width="14" height="10.5" rx="1.5" fill="#EEF7FF" stroke="#8A5A10" stroke-width="1"/>
  <path d="M9.5 22l4-4.5 3 3 2-2 4 3.5" stroke="#3FB6E8" stroke-width="1.6" fill="none" stroke-linejoin="round"/>
  <circle cx="19.5" cy="16" r="1.4" fill="#FF6B5E"/>`);

// ---------- Valorant (dessins originaux) ----------
emoji("jeu_valorant", `${deg("gva", "#FF7A85", "#C9202F")}
  <path d="M16 2.5l12 6.5v14L16 29.5 4 23V9z" fill="url(#gva)" stroke="#5A0E16" stroke-width="1.3" stroke-linejoin="round"/>
  <circle cx="16" cy="16" r="7" fill="none" stroke="#FFF1EE" stroke-width="2"/>
  <path d="M16 6.5v5M16 20.5v5M6.5 16h5M20.5 16h5" stroke="#FFF1EE" stroke-width="2" stroke-linecap="round"/>
  <circle cx="16" cy="16" r="1.8" fill="#FFF1EE"/>`);
emoji("valo_rang", `${deg("gvr", "#FFE7A0", "#E0A21E")}
  <path d="M16 2.5l10 5.5v9.5c0 6-4.5 10.4-10 12.5-5.5-2.1-10-6.5-10-12.5V8z" fill="url(#gvr)" stroke="#6E4A08" stroke-width="1.3" stroke-linejoin="round"/>
  <path d="M10 15.5l6-4.5 6 4.5M10 20.5l6-4.5 6 4.5" stroke="#6E4A08" stroke-width="2.4" fill="none" stroke-linecap="round" stroke-linejoin="round"/>`);
emoji("valo_rr", `<rect x="3" y="12" width="26" height="9" rx="4.5" fill="#1C2146" stroke="#9AA3C7" stroke-width="1.4"/>
  <rect x="5" y="14" width="15" height="5" rx="2.5" fill="#33D1C1"/>
  <path d="M22 8l3-4 3 4M25 4v6" stroke="#33D19A" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"/>
  <path d="M7 26h18" stroke="#4A5290" stroke-width="2" stroke-linecap="round"/>`);
emoji("valo_viseur", `<circle cx="16" cy="16" r="11" fill="none" stroke="#FF4655" stroke-width="2.4"/>
  <circle cx="16" cy="16" r="5" fill="none" stroke="#FF4655" stroke-width="2"/>
  <path d="M16 2v7M16 23v7M2 16h7M23 16h7" stroke="#EEF0FA" stroke-width="2.2" stroke-linecap="round"/>
  <circle cx="16" cy="16" r="1.6" fill="#EEF0FA"/>`);
emoji("valo_acs", `<rect x="3" y="3" width="26" height="26" rx="5" fill="#1C2146" stroke="#4A5290" stroke-width="1.3"/>
  <rect x="7.5" y="17" width="4" height="8" rx="1" fill="#9AA3C7"/><rect x="14" y="11" width="4" height="14" rx="1" fill="#FF4655"/>
  <rect x="20.5" y="7" width="4" height="18" rx="1" fill="#FFC44D"/>`);
emoji("valo_degats", `${rad("gvd", "#FFD0C8", "#FF4655")}
  <path d="M16 2l3 7.5 8-3-4.5 7 7.5 3-7.5 3 4.5 7-8-3-3 7.5-3-7.5-8 3 4.5-7-7.5-3 7.5-3-4.5-7 8 3z" fill="url(#gvd)" stroke="#5A0E16" stroke-width="1" stroke-linejoin="round"/>
  <circle cx="16" cy="16" r="3.5" fill="#FFF1EE"/>`);
emoji("valo_tete", `<path d="M16 4a8 8 0 0 0-8 8c0 3 1.4 5 3 6.5V22h10v-3.5c1.6-1.5 3-3.5 3-6.5a8 8 0 0 0-8-8z" fill="#2C3360" stroke="#9AA3C7" stroke-width="1.5"/>
  <path d="M11 26.5h10" stroke="#9AA3C7" stroke-width="2" stroke-linecap="round"/>
  <circle cx="16" cy="12" r="5" fill="none" stroke="#FF4655" stroke-width="1.8"/>
  <path d="M16 5.5v3M16 15.5v3M9.5 12h3M19.5 12h3" stroke="#FF4655" stroke-width="1.6" stroke-linecap="round"/>`);
emoji("valo_victoire", `${deg("gvv", "#9DF2D0", "#22A879")}
  <path d="M9 4h14v6a7 7 0 0 1-14 0z" fill="url(#gvv)" stroke="#0E5E42" stroke-width="1.3"/>
  <path d="M9 6H5v2a4 4 0 0 0 4 4M23 6h4v2a4 4 0 0 1-4 4" stroke="#0E5E42" stroke-width="1.5" fill="none"/>
  <path d="M16 17v5M11 28h10l-1.5-6h-7z" fill="#22A879" stroke="#0E5E42" stroke-width="1.3" stroke-linejoin="round"/>`);
emoji("valo_niveau", `<rect x="4" y="5" width="24" height="22" rx="4" fill="#1C2146" stroke="#FF4655" stroke-width="1.8"/>
  <path d="M10 20l6-7 6 7" stroke="#EEF0FA" stroke-width="2.6" fill="none" stroke-linecap="round" stroke-linejoin="round"/>
  <path d="M10 24h12" stroke="#FFC44D" stroke-width="2" stroke-linecap="round"/>`);
emoji("valo_agent", `<circle cx="16" cy="10.5" r="6" fill="#2C3360" stroke="#9AA3C7" stroke-width="1.5"/>
  <path d="M10.5 9h11" stroke="#FF4655" stroke-width="2.4" stroke-linecap="round"/>
  <path d="M5 29c.8-6.5 5.2-10 11-10s10.2 3.5 11 10z" fill="#2C3360" stroke="#9AA3C7" stroke-width="1.5" stroke-linejoin="round"/>
  <path d="M16 19v10" stroke="#FF4655" stroke-width="1.6"/>`);
emoji("valo_carte", `<path d="M3 7l8-3 10 3 8-3v21l-8 3-10-3-8 3z" fill="#2C3360" stroke="#9AA3C7" stroke-width="1.4" stroke-linejoin="round"/>
  <path d="M11 4v21M21 7v21" stroke="#4A5290" stroke-width="1.2"/>
  <path d="M14 13l2.5 2.5L19 13M14 18l5-5" stroke="#FF4655" stroke-width="2" fill="none" stroke-linecap="round"/>`);
emoji("valo_client", `<rect x="3" y="5" width="26" height="18" rx="3" fill="#1C2146" stroke="#9AA3C7" stroke-width="1.6"/>
  <path d="M11 28h10M16 23v5" stroke="#9AA3C7" stroke-width="2" stroke-linecap="round"/>
  <circle cx="16" cy="14" r="5" fill="none" stroke="#33D1C1" stroke-width="2"/>
  <path d="M13.6 14l1.7 1.7 3.2-3.4" stroke="#33D1C1" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"/>`);
emoji("telecharger", `<path d="M16 3.5v15" stroke="#EEF0FA" stroke-width="3.6" stroke-linecap="round"/>
  <path d="M9 12.5l7 7 7-7" stroke="#EEF0FA" stroke-width="3.6" fill="none" stroke-linecap="round" stroke-linejoin="round"/>
  <path d="M4.5 21v4.5a2 2 0 0 0 2 2h19a2 2 0 0 0 2-2V21" stroke="${AMS_OR}" stroke-width="3.2" fill="none" stroke-linecap="round" stroke-linejoin="round"/>`);
emoji("carte_teyvat", `${deg("gct", "#F4E2B0", "#D9B66A")}
  <path d="M3 7l8-3 10 3 8-3v21l-8 3-10-3-8 3z" fill="url(#gct)" stroke="#6E4E14" stroke-width="1.3" stroke-linejoin="round"/>
  <path d="M11 4v21M21 7v21" stroke="#B8924A" stroke-width="1"/>
  <path d="M6 18c3-1 4 2 7 1s3-5 6-5 4 2 6 1" stroke="#3F7FD9" stroke-width="1.6" fill="none" stroke-linecap="round"/>
  <path d="M22 6.5a4 4 0 0 0-4 4c0 3 4 6.5 4 6.5s4-3.5 4-6.5a4 4 0 0 0-4-4z" fill="#FF6B5E" stroke="#7A1F18" stroke-width="1"/>
  <circle cx="22" cy="10.5" r="1.5" fill="#FFF3E8"/>`);
ICONES.famille_genshin_impact = ICONES.jeu_genshin;

// ---------- Blox Fruits : build et inventaire (dessins originaux) ----------
emoji("bf_build", `<rect x="4" y="18" width="5" height="10" rx="1.5" fill="#f0904a"/><rect x="11.5" y="12" width="5" height="16" rx="1.5" fill="#FFC44D"/>
  <rect x="19" y="6" width="5" height="22" rx="1.5" fill="#33D1C1"/><path d="M26 6l2-2M26 10h3" stroke="#EEF0FA" stroke-width="1.6" stroke-linecap="round"/>`);
emoji("bf_inventaire", `${deg("gbi", "#C98B4A", "#8A5622")}
  <path d="M6 11c0-3 2-5 5-5h10c3 0 5 2 5 5v15H6z" fill="url(#gbi)" stroke="#4A2C10" stroke-width="1.4" stroke-linejoin="round"/>
  <path d="M6 14h20" stroke="#4A2C10" stroke-width="1.4"/><rect x="13" y="12" width="6" height="5" rx="1.2" fill="#FFC44D" stroke="#4A2C10" stroke-width="1.1"/>
  <path d="M12 6V4.5a4 4 0 0 1 8 0V6" stroke="#4A2C10" stroke-width="1.6" fill="none"/>`);
emoji("bf_melee", `<path d="M9 14V9a2 2 0 0 1 4 0v4-6a2 2 0 0 1 4 0v6-5a2 2 0 0 1 4 0v6-3a2 2 0 0 1 4 0v8c0 5-3 8-8 8h-1c-4 0-7-3-8-6l-2-5a2 2 0 0 1 3.5-2z"
  fill="#F3C9A0" stroke="#7A4A22" stroke-width="1.3" stroke-linejoin="round"/>`);
emoji("bf_defense", `${deg("gbd", "#9AD0FF", "#3C7DD9")}<path d="M16 3l11 4v8c0 7-5 12-11 14-6-2-11-7-11-14V7z" fill="url(#gbd)" stroke="#173A6E" stroke-width="1.4" stroke-linejoin="round"/>
  <path d="M16 8v16M9 14h14" stroke="#EEF7FF" stroke-width="2" opacity=".8"/>`);
emoji("bf_epee", `<path d="M26 4l-3 1-13 13 4 4 13-13z" fill="#DDE3EE" stroke="#5A6378" stroke-width="1.3" stroke-linejoin="round"/>
  <path d="M8 18l6 6M11 21l-5 5" stroke="#7A4A22" stroke-width="2.6" stroke-linecap="round"/><circle cx="5.5" cy="26.5" r="1.8" fill="#FFC44D"/>`);
emoji("bf_arme", `<path d="M4 12h20l3-2v6h-6l-2 3h-4l-1 4H9l1-6H4z" fill="#8C95A8" stroke="#3A4152" stroke-width="1.3" stroke-linejoin="round"/>
  <path d="M14 16h4" stroke="#3A4152" stroke-width="1.2"/><circle cx="27.5" cy="11" r="1.2" fill="#FFC44D"/>`);
emoji("bf_fruit", `${rad("gbf", "#C79BFF", "#6A2FC9")}<circle cx="16" cy="18" r="10.5" fill="url(#gbf)" stroke="#3A1477" stroke-width="1.3"/>
  <path d="M11 15c2-3 4 1 6-2s4 0 5 2M10 20c2-2 4 1 6-1s4 1 6 0" stroke="#EADBFF" stroke-width="1.4" fill="none" stroke-linecap="round"/>
  <path d="M16 7.5c0-2 1-3.5 3-4.5" stroke="#5B3A12" stroke-width="1.8" fill="none" stroke-linecap="round"/><path d="M17.5 5.5c2.5-1.5 5-.5 6 1-2 1.5-4.5 1-6-1z" fill="#3FC46B"/>`);
