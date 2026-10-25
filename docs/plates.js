// Draws a top-down plate for a list of dish names as an inline SVG. No images needed.
(() => {
  // Keyword → [fill, highlight]. First match wins; order matters ("butter naan" before "butter").
  const PALETTE = [
    [/paratha|naan|roti|chapati|bhature|bread|baati/i, ["#E9B45C", "#F6D592"]],
    [/rajma|chole|gatte/i,                             ["#8A2E1C", "#B5482B"]],
    [/paneer|butter masala/i,                          ["#F07A2C", "#FFB067"]],
    [/dal|churma|tadka/i,                              ["#F2B705", "#FFD84D"]],
    [/rice|pulao|poha/i,                               ["#FFF6DD", "#FFFFFF"]],
    [/curd|raita|lassi|kheer|egg/i,                    ["#FFFDF4", "#FFFFFF"]],
    [/chai|coffee|tea/i,                               ["#9A5B2E", "#C88A55"]],
    [/samosa|sandwich|bhel/i,                          ["#D99A3A", "#F1C26C"]],
    [/salad|chutney|sabzi/i,                           ["#3E9B4F", "#7CCB72"]],
    [/jamun|jam/i,                                     ["#5A1A12", "#8E3123"]],
    [/banana/i,                                        ["#FFD93B", "#FFF08A"]],
  ];
  const FALLBACK = ["#E07A3F", "#F4A86C"];

  const colorFor = dish => (PALETTE.find(([re]) => re.test(dish)) || [null, FALLBACK])[1];

  // Small deterministic PRNG so a plate looks the same every render.
  function rng(seed) {
    let h = 2166136261;
    for (const c of seed) h = Math.imul(h ^ c.charCodeAt(0), 16777619);
    return () => ((h = Math.imul(h ^ (h >>> 15), 2246822507) ^ Math.imul(h ^ (h >>> 13), 3266489909)) >>> 0) / 4294967296;
  }

  // Wobbly closed blob around (cx, cy).
  function blob(cx, cy, r, rand, points = 9) {
    const pts = Array.from({ length: points }, (_, i) => {
      const a = (i / points) * Math.PI * 2;
      const rr = r * (0.82 + rand() * 0.3);
      return [cx + Math.cos(a) * rr, cy + Math.sin(a) * rr];
    });
    // Smooth closed curve: each point is a control point, midpoints are the anchors.
    const p = i => pts[i % points];
    const mid = i => [(p(i)[0] + p(i + 1)[0]) / 2, (p(i)[1] + p(i + 1)[1]) / 2].map(v => v.toFixed(1)).join(",");
    let d = `M${mid(0)}`;
    for (let i = 1; i <= points; i++) d += `Q${p(i).map(v => v.toFixed(1)).join(",")} ${mid(i)}`;
    return d + "Z";
  }

  window.plateSVG = function plateSVG(dishes, { rim = "#FFFFFF", seed = dishes.join("|") } = {}) {
    const rand = rng(seed);
    const n = dishes.length;
    const parts = dishes.map((dish, i) => {
      const [fill, hi] = colorFor(dish);
      // First dish sits near the middle, the rest orbit it.
      const ring = i === 0 ? 0 : 58;
      const a = ((i - 1) / Math.max(1, n - 1)) * Math.PI * 2 + rand() * 0.4;
      const cx = 150 + Math.cos(a) * ring, cy = 150 + Math.sin(a) * ring;
      const r = i === 0 ? 46 : 30 + rand() * 6;
      // Specks give texture (spices, grains).
      const specks = Array.from({ length: 5 }, () => {
        const sa = rand() * Math.PI * 2, sr = rand() * r * 0.6;
        return `<circle cx="${(cx + Math.cos(sa) * sr).toFixed(1)}" cy="${(cy + Math.sin(sa) * sr).toFixed(1)}" r="${(1.5 + rand() * 2).toFixed(1)}" fill="${hi}" opacity=".9"/>`;
      }).join("");
      return `<path d="${blob(cx, cy, r, rand)}" fill="${fill}"/>${specks}`;
    }).join("");

    const label = dishes.join(", ").replace(/[&<>"']/g, c => `&#${c.charCodeAt(0)};`);
    return `<svg viewBox="0 0 300 300" role="img" aria-label="${label}">
      <circle cx="150" cy="156" r="140" fill="rgba(0,0,0,.14)"/>
      <circle cx="150" cy="150" r="140" fill="${rim}"/>
      <circle cx="150" cy="150" r="112" fill="none" stroke="rgba(0,0,0,.07)" stroke-width="2"/>
      ${parts}
    </svg>`;
  };
})();
