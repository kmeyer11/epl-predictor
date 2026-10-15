// Chart helpers for the site: colours per model, number formats, a tooltip,
// and an SVG line chart with a crosshair. No dependencies.
(function () {
  if (!window.EPL) return;
  const D = window.EPL;
  const byName = Object.fromEntries(D.models.map((m) => [m.name, m]));

  // Colour follows the model, never its rank: real models take series slots in
  // registry order, benchmarks get greys and a dash so they read as yardsticks.
  const slot = {};
  let next = 1;
  let bench = 1;
  for (const m of D.models) {
    if (!m.benchmark) slot[m.name] = { color: `var(--series-${next++})`, dash: "" };
  }
  for (const name of ["market", "baseline"].concat(D.models.map((m) => m.name))) {
    if (byName[name] && !slot[name]) {
      // The second benchmark also gets a hollow dot, since a dash can't show on a dot.
      slot[name] = { color: `var(--bench-${bench})`, dash: bench === 1 ? "6 4" : "2 4", hollow: bench > 1 };
      bench++;
    }
  }

  const fmt = {
    pts: (v) => v.toFixed(2),
    pts3: (v) => v.toFixed(3),
    signed: (v) => (v > 0 ? "+" : v < 0 ? "−" : "±") + Math.abs(v).toFixed(2),
    pct: (v) => Math.round(v * 100) + "%",
    season: (y) => `${String(y % 100).padStart(2, "0")}/${String((y + 1) % 100).padStart(2, "0")}`,
    date: (iso) => new Date(iso).toLocaleDateString("en-GB", { day: "numeric", month: "short" }),
    kickoff: (iso) =>
      new Date(iso).toLocaleString("en-GB", { weekday: "short", hour: "2-digit", minute: "2-digit", timeZone: "UTC" }),
  };

  function points(pick, actual) {
    const pd = pick[0] - pick[1];
    const ad = actual[0] - actual[1];
    if (Math.sign(pd) !== Math.sign(ad)) return 0;
    if (pd !== ad) return 3;
    return pick[0] === actual[0] ? 9 : 4;
  }

  let tip;
  function tooltip(html, x, y) {
    if (!tip) {
      tip = document.createElement("div");
      tip.className = "tip";
      document.body.appendChild(tip);
    }
    if (html == null) {
      tip.style.opacity = 0;
      return;
    }
    tip.innerHTML = html;
    tip.style.opacity = 1;
    const r = tip.getBoundingClientRect();
    const left = Math.min(x + 14, window.innerWidth - r.width - 8);
    tip.style.left = left + "px";
    tip.style.top = Math.max(8, y - r.height - 12) + "px";
  }

  // Attributes for a dot marker: filled with the model colour, or hollow.
  function dot(model) {
    const s = slot[model];
    return s.hollow
      ? `fill="var(--surface)" stroke="${s.color}" stroke-width="2"`
      : `fill="${s.color}" class="ring"`;
  }

  function swatch(model) {
    const s = slot[model];
    const ring = s.hollow ? `<circle cx="9" cy="5" r="3.5" fill="var(--surface)" stroke="${s.color}" stroke-width="1.5"/>` : "";
    return `<svg class="key" width="18" height="10" aria-hidden="true"><line x1="1" y1="5" x2="17" y2="5" stroke="${s.color}" stroke-width="2.5" stroke-dasharray="${s.dash}" stroke-linecap="round"/>${ring}</svg>`;
  }

  function legend(models) {
    return `<div class="legend">${models
      .map((m) => `<span>${swatch(m)}${m}</span>`)
      .join("")}</div>`;
  }

  // series: [{model, values: [number]}], all the same length; labels: x labels.
  function lineChart(el, { series, labels, height = 280, zeroLine = false, yFormat = (v) => v, tipValue = yFormat }) {
    const width = el.clientWidth || 640;
    const pad = { top: 12, right: 92, bottom: 26, left: 44 };
    const all = series.flatMap((s) => s.values);
    let lo = Math.min(...all, zeroLine ? 0 : Infinity);
    let hi = Math.max(...all, zeroLine ? 0 : -Infinity);
    const span = hi - lo || 1;
    lo -= span * 0.05;
    hi += span * 0.05;
    const n = labels.length;
    const x = (i) => pad.left + (i / Math.max(1, n - 1)) * (width - pad.left - pad.right);
    const y = (v) => pad.top + (1 - (v - lo) / (hi - lo)) * (height - pad.top - pad.bottom);
    const ticks = niceTicks(lo, hi, 4);

    const grid = ticks
      .map((t) => `<line class="grid" x1="${pad.left}" x2="${width - pad.right}" y1="${y(t)}" y2="${y(t)}"/>
        <text class="axis" x="${pad.left - 8}" y="${y(t) + 4}" text-anchor="end">${yFormat(t)}</text>`)
      .join("");
    const zero = zeroLine ? `<line class="baseline" x1="${pad.left}" x2="${width - pad.right}" y1="${y(0)}" y2="${y(0)}"/>` : "";
    const xTicks = [0, Math.floor((n - 1) / 2), n - 1]
      .map((i) => `<text class="axis" x="${x(i)}" y="${height - 6}" text-anchor="middle">${labels[i]}</text>`)
      .join("");

    // End labels only when they don't collide; otherwise the legend carries identity.
    const ends = series.map((s) => ({ model: s.model, v: s.values[n - 1], y: y(s.values[n - 1]) })).sort((a, b) => a.y - b.y);
    const roomy = ends.every((e, i) => i === 0 || e.y - ends[i - 1].y >= 13);
    const lines = series
      .map((s) => {
        const d = s.values.map((v, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join("");
        const st = slot[s.model];
        return `<path d="${d}" fill="none" stroke="${st.color}" stroke-width="2" stroke-dasharray="${st.dash}" stroke-linejoin="round" stroke-linecap="round"/>
          <circle cx="${x(n - 1)}" cy="${y(s.values[n - 1])}" r="4" ${dot(s.model)}/>`;
      })
      .join("");
    const endLabels = roomy
      ? ends.map((e) => `<text class="end" x="${width - pad.right + 10}" y="${e.y + 4}">${e.model}</text>`).join("")
      : "";

    el.innerHTML = `<svg width="${width}" height="${height}" role="img">
      ${grid}${zero}${xTicks}${lines}${endLabels}
      <line class="cross" y1="${pad.top}" y2="${height - pad.bottom}" style="opacity:0"/>
      <rect x="${pad.left}" y="0" width="${width - pad.left - pad.right}" height="${height}" fill="transparent"/>
    </svg>`;

    const svg = el.querySelector("svg");
    const cross = svg.querySelector(".cross");
    svg.addEventListener("pointermove", (ev) => {
      const box = svg.getBoundingClientRect();
      const px = ev.clientX - box.left;
      if (px < pad.left - 6 || px > width - pad.right + 6) return;
      const i = Math.max(0, Math.min(n - 1, Math.round(((px - pad.left) / (width - pad.left - pad.right)) * (n - 1))));
      cross.setAttribute("x1", x(i));
      cross.setAttribute("x2", x(i));
      cross.style.opacity = 1;
      const rows = series
        .map((s) => ({ model: s.model, v: s.values[i] }))
        .sort((a, b) => b.v - a.v)
        .map((r) => `<div class="row">${swatch(r.model)}<span>${r.model}</span><b>${tipValue(r.v)}</b></div>`)
        .join("");
      tooltip(`<div class="tip-title">${labels[i]}</div>${rows}`, ev.clientX, ev.clientY);
    });
    svg.addEventListener("pointerleave", () => {
      cross.style.opacity = 0;
      tooltip(null);
    });
  }

  function niceTicks(lo, hi, count) {
    const raw = (hi - lo) / count;
    const mag = Math.pow(10, Math.floor(Math.log10(raw)));
    const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => s >= raw);
    const out = [];
    for (let t = Math.ceil(lo / step) * step; t <= hi + 1e-9; t += step) out.push(+t.toFixed(10));
    return out;
  }

  // Race data for one season: cumulative points per refit block, one series per model.
  function race(season, relativeTo) {
    const blocks = D.backtest.races[season];
    // Models without a backtest (live only) have no key in the blocks.
    const models = D.models.map((m) => m.name).filter((m) => blocks.length && m in blocks[0]);
    const series = models.map((m) => ({
      model: m,
      values: blocks.map((b) => b[m] - (relativeTo ? b[relativeTo] : 0)),
    }));
    return { series, labels: blocks.map((b) => fmt.date(b.date)) };
  }

  window.EPLCharts = { D, slot, fmt, points, tooltip, dot, swatch, legend, lineChart, race, byName };
})();
