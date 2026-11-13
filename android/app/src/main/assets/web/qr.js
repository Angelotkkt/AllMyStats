// ================= QR code (fait maison, sans bibliothèque) =================
// Mode « octets », correction d'erreurs M, versions 1 à 10. QR.svg(texte) renvoie un dessin SVG.
const QR = (() => {
  // [total de mots, mots de correction par bloc, [nb blocs, mots de données par bloc], ...]
  const TABLE = [null,
    [26, 10, [1, 16]], [44, 16, [1, 28]], [70, 26, [1, 44]], [100, 18, [2, 32]], [134, 24, [2, 43]],
    [172, 16, [4, 27]], [196, 18, [4, 31]], [242, 22, [2, 38], [2, 39]], [292, 22, [3, 36], [2, 37]],
    [346, 26, [4, 43], [1, 44]]];
  const ALIGNEMENTS = [null, [], [6, 18], [6, 22], [6, 26], [6, 30], [6, 34], [6, 22, 38], [6, 24, 42], [6, 26, 46], [6, 28, 50]];

  // Corps de Galois GF(256), polynôme 0x11D
  const EXP = new Array(512), LOG = new Array(256);
  for (let i = 0, x = 1; i < 255; i++) { EXP[i] = x; LOG[x] = i; x <<= 1; if (x & 0x100) x ^= 0x11d; }
  for (let i = 255; i < 512; i++) EXP[i] = EXP[i - 255];
  const mul = (a, b) => (a && b ? EXP[LOG[a] + LOG[b]] : 0);

  function generateur(n) {
    let g = [1];
    for (let i = 0; i < n; i++) {
      const suivant = new Array(g.length + 1).fill(0);
      for (let j = 0; j < g.length; j++) { suivant[j] ^= g[j]; suivant[j + 1] ^= mul(g[j], EXP[i]); }
      g = suivant;
    }
    return g;
  }
  function correction(donnees, n) {
    const g = generateur(n), reste = donnees.concat(new Array(n).fill(0));
    for (let i = 0; i < donnees.length; i++) {
      const c = reste[i];
      if (c) for (let j = 0; j < g.length; j++) reste[i + j] ^= mul(g[j], c);
    }
    return reste.slice(donnees.length);
  }

  function capacite(v) { const t = TABLE[v]; return t.slice(2).reduce((s, [n, d]) => s + n * d, 0); }

  function mots(octets, v) {
    const bits = [];
    const ajouter = (val, n) => { for (let i = n - 1; i >= 0; i--) bits.push((val >> i) & 1); };
    ajouter(0b0100, 4);
    ajouter(octets.length, v < 10 ? 8 : 16);
    octets.forEach((o) => ajouter(o, 8));
    const cap = capacite(v) * 8;
    ajouter(0, Math.min(4, cap - bits.length));
    while (bits.length % 8) bits.push(0);
    const donnees = [];
    for (let i = 0; i < bits.length; i += 8) donnees.push(parseInt(bits.slice(i, i + 8).join(""), 2));
    for (let p = 0; donnees.length < capacite(v); p++) donnees.push(p % 2 ? 0x11 : 0xec);
    // Blocs, correction, puis entrelacement
    const t = TABLE[v], blocs = [], corrections = [];
    let pos = 0;
    for (const [nb, taille] of t.slice(2)) for (let b = 0; b < nb; b++) {
      const bloc = donnees.slice(pos, pos + taille); pos += taille;
      blocs.push(bloc); corrections.push(correction(bloc, t[1]));
    }
    const sortie = [];
    const max = Math.max(...blocs.map((b) => b.length));
    for (let i = 0; i < max; i++) blocs.forEach((b) => { if (i < b.length) sortie.push(b[i]); });
    for (let i = 0; i < t[1]; i++) corrections.forEach((c) => sortie.push(c[i]));
    return sortie;
  }

  function bch(valeur, poly, decalage) {
    let v = valeur << decalage;
    const degre = (x) => 31 - Math.clz32(x);
    while (v && degre(v) >= degre(poly)) v ^= poly << (degre(v) - degre(poly));
    return (valeur << decalage) | v;
  }

  const MASQUES = [(r, c) => (r + c) % 2 === 0, (r) => r % 2 === 0, (r, c) => c % 3 === 0, (r, c) => (r + c) % 3 === 0,
    (r, c) => (Math.floor(r / 2) + Math.floor(c / 3)) % 2 === 0, (r, c) => ((r * c) % 2) + ((r * c) % 3) === 0,
    (r, c) => (((r * c) % 2) + ((r * c) % 3)) % 2 === 0, (r, c) => (((r + c) % 2) + ((r * c) % 3)) % 2 === 0];

  function matrice(texte) {
    const octets = Array.from(new TextEncoder().encode(texte));
    let v = 1;
    while (v <= 10 && capacite(v) < octets.length + (v < 10 ? 2 : 3)) v++;
    if (v > 10) throw new Error("Texte trop long pour le QR code");
    const n = 17 + 4 * v;
    const m = Array.from({ length: n }, () => new Array(n).fill(null));   // null = libre
    const fixe = Array.from({ length: n }, () => new Array(n).fill(false));
    const poser = (r, c, val) => { m[r][c] = val; fixe[r][c] = true; };

    const reperes = (r0, c0) => {
      for (let r = -1; r <= 7; r++) for (let c = -1; c <= 7; c++) {
        const rr = r0 + r, cc = c0 + c;
        if (rr < 0 || cc < 0 || rr >= n || cc >= n) continue;
        const dedans = r >= 0 && r <= 6 && c >= 0 && c <= 6;
        poser(rr, cc, dedans && (r === 0 || r === 6 || c === 0 || c === 6 || (r >= 2 && r <= 4 && c >= 2 && c <= 4)));
      }
    };
    reperes(0, 0); reperes(0, n - 7); reperes(n - 7, 0);
    for (let i = 8; i < n - 8; i++) { poser(6, i, i % 2 === 0); poser(i, 6, i % 2 === 0); }
    const al = ALIGNEMENTS[v];
    al.forEach((r, i) => al.forEach((c, j) => {
      const dernier = al.length - 1;
      if ((i === 0 && j === 0) || (i === 0 && j === dernier) || (i === dernier && j === 0)) return;   // coins des repères
      for (let dr = -2; dr <= 2; dr++) for (let dc = -2; dc <= 2; dc++)
        poser(r + dr, c + dc, Math.max(Math.abs(dr), Math.abs(dc)) !== 1);
    }));
    // Zones réservées (format, version), remplies plus tard
    for (let i = 0; i < 9; i++) { if (!fixe[8][i]) poser(8, i, false); if (!fixe[i][8]) poser(i, 8, false); }
    for (let i = 0; i < 8; i++) { poser(8, n - 1 - i, false); poser(n - 1 - i, 8, false); }
    poser(n - 8, 8, true);   // module toujours noir
    if (v >= 7) for (let i = 0; i < 6; i++) for (let j = 0; j < 3; j++) { poser(i, n - 11 + j, false); poser(n - 11 + j, i, false); }

    // Données en zigzag
    const bits = [];
    mots(octets, v).forEach((o) => { for (let i = 7; i >= 0; i--) bits.push((o >> i) & 1); });
    let k = 0, haut = true;
    for (let c = n - 1; c > 0; c -= 2) {
      if (c === 6) c--;
      for (let i = 0; i < n; i++) {
        const r = haut ? n - 1 - i : i;
        for (const cc of [c, c - 1]) if (!fixe[r][cc]) m[r][cc] = k < bits.length ? bits[k++] === 1 : false;
      }
      haut = !haut;
    }

    // Choix du masque (le moins de « pénalités »)
    const essayer = (masque) => {
      const x = m.map((ligne, r) => ligne.map((val, c) => (fixe[r][c] ? val : val !== MASQUES[masque](r, c))));
      const format = bch((0b00 << 3) | masque, 0x537, 10) ^ 0x5412;   // 00 = correction M
      const bit = (i) => ((format >> i) & 1) === 1;
      for (let i = 0; i <= 5; i++) x[i][8] = bit(i);
      x[7][8] = bit(6); x[8][8] = bit(7); x[8][7] = bit(8);
      for (let i = 9; i < 15; i++) x[8][14 - i] = bit(i);
      for (let i = 0; i < 8; i++) x[8][n - 1 - i] = bit(i);
      for (let i = 8; i < 15; i++) x[n - 15 + i][8] = bit(i);
      x[n - 8][8] = true;
      if (v >= 7) {
        const info = bch(v, 0x1f25, 12);
        for (let i = 0; i < 18; i++) {
          const b = ((info >> i) & 1) === 1;
          x[Math.floor(i / 3)][n - 11 + (i % 3)] = b; x[n - 11 + (i % 3)][Math.floor(i / 3)] = b;
        }
      }
      return x;
    };
    const penalite = (x) => {
      let p = 0;
      for (let pass = 0; pass < 2; pass++) for (let i = 0; i < n; i++) {
        let suite = 1;
        for (let j = 1; j < n; j++) {
          const a = pass ? x[j][i] : x[i][j], b = pass ? x[j - 1][i] : x[i][j - 1];
          if (a === b) { suite++; if (suite === 5) p += 3; else if (suite > 5) p++; } else suite = 1;
        }
      }
      for (let i = 0; i < n - 1; i++) for (let j = 0; j < n - 1; j++)
        if (x[i][j] === x[i + 1][j] && x[i][j] === x[i][j + 1] && x[i][j] === x[i + 1][j + 1]) p += 3;
      const noirs = x.flat().filter(Boolean).length;
      p += Math.floor(Math.abs(noirs * 100 / (n * n) - 50) / 5) * 10;
      return p;
    };
    let meilleur = null, score = Infinity;
    for (let masque = 0; masque < 8; masque++) {
      const x = essayer(masque), s = penalite(x);
      if (s < score) { score = s; meilleur = x; }
    }
    return meilleur;
  }

  function svg(texte, { taille = 220, encre = "#141832", fond = "#ffffff" } = {}) {
    const x = matrice(texte), n = x.length, marge = 4, total = n + 2 * marge;
    let d = "";
    x.forEach((ligne, r) => ligne.forEach((val, c) => { if (val) d += `M${c + marge} ${r + marge}h1v1h-1z`; }));
    return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${total} ${total}" width="${taille}" height="${taille}"
      shape-rendering="crispEdges" role="img" aria-label="QR code"><rect width="${total}" height="${total}" fill="${fond}"/>
      <path d="${d}" fill="${encre}"/></svg>`;
  }

  return { matrice, svg };
})();
if (typeof module !== "undefined") module.exports = QR;
