(function () {
  if (!window.EPL) {
    document.getElementById("app").innerHTML =
      '<p class="empty span-12">No data yet. From the repo root run: <code>python -m epl_predictor.cli export</code></p>';
    return;
  }
  const { D, slot, fmt, swatch, legend, lineChart, race, tooltip, byName } = EPLCharts;
  const B = D.backtest;
  const seasons = B.seasons;
  const $ = (id) => document.getElementById(id);
  const realModels = D.models.filter((m) => !m.benchmark).map((m) => m.name);
  const tag = (m) => (byName[m].benchmark ? '<span class="tag">benchmark</span>' : "");

  $("sub").textContent =
    `Backtest ${fmt.season(seasons[0])} – ${fmt.season(seasons.at(-1))} · ${B.matches.toLocaleString()} matches`;
  $("generated").textContent = `Updated ${new Date(D.generatedAt).toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "short" })}`;

  // Tiles
  const board = B.leaderboard;
  const leader = board[0];
  const bestReal = board.find((r) => !byName[r.model].benchmark);
  const tile = (id, label, value, delta) =>
    ($(id).innerHTML = `<div class="label">${label}</div><div class="value">${value}</div><div class="delta">${delta}</div>`);
  tile("t1", "Leader", leader.model, `${fmt.pts3(leader.ptsPerMatch)} pts/match · ${Math.round(leader.ptsPerMatch * 380)} per season`);
  if (bestReal && bestReal !== leader) {
    tile("t2", "Best real model", bestReal.model, `${fmt.signed(bestReal.diffToBest)} vs ${leader.model} (± ${bestReal.ci95.toFixed(2)})`);
  } else if (bestReal) {
    tile("t2", "Best real model", bestReal.model, "leads every benchmark");
  }
  if (bestReal) {
    const gain = bestReal.ptsPerMatch - bestReal.ptsPerMatchLikeliest;
    tile("t3", "Betting for points, not the likeliest score", `${gain >= 0 ? "+" : "−"}${Math.abs(gain).toFixed(2)}`,
      `pts/match for ${bestReal.model} · <b>${gain >= 0 ? "+" : "−"}${Math.abs(Math.round(gain * 380))}</b> per season`);
  }
  const U = D.upcoming;
  if (U.length) {
    const first = fmt.date(U[0].kickoff), last = fmt.date(U.at(-1).kickoff);
    tile("t4", "Next matches", `${U.length} bets`, `${first === last ? first : `${first} – ${last}`} · saved for live tracking`);
  } else {
    tile("t4", "Next matches", "none saved", "run predict, then export");
  }

  // Leaderboard: backtest or live, with an inline bar and a whisker for the gap to #1.
  let kind = "backtest";
  function drawBoard() {
    const src = kind === "live" ? D.live : B;
    $("board-kind").innerHTML = ["backtest", "live"]
      .map((k) => `<button data-k="${k}" aria-pressed="${k === kind}">${k === "live" ? `Live (${D.live.matches})` : "Backtest"}</button>`)
      .join("");
    $("board-hint").textContent = kind === "live"
      ? "Bets saved by predict before kickoff, scored once the result is in."
      : "Average plshowet points per match, replaying past seasons. Every model bet on the same matches.";
    const rows = src.leaderboard;
    if (!src.matches) {
      $("board").innerHTML = `<tr><td class="empty">No scored ${kind} bets yet.</td></tr>`;
      return;
    }
    const top = rows[0];
    const maxPts = Math.max(...rows.map((r) => r.ptsPerMatch));
    const minGap = Math.min(...rows.map((r) => r.diffToBest - r.ci95), -0.01);
    const whisker = (r) => {
      if (r === top) return `<span style="color:var(--muted)">leader</span>`;
      const w = 120, s = (v) => w - (v / minGap) * (w - 8) - 4;
      return `<svg width="${w}" height="14" aria-label="${fmt.signed(r.diffToBest)} ± ${r.ci95.toFixed(2)}">
        <line x1="${s(0)}" x2="${s(0)}" y1="0" y2="14" stroke="var(--axis)"/>
        <line x1="${s(r.diffToBest - r.ci95)}" x2="${Math.min(s(r.diffToBest + r.ci95), w)}" y1="7" y2="7" stroke="${slot[r.model].color}" stroke-width="2" stroke-linecap="round"/>
        <circle cx="${s(r.diffToBest)}" cy="7" r="4" fill="${slot[r.model].color}" class="ring"/></svg>
        <span style="color:var(--ink-2);font-size:12px">${fmt.signed(r.diffToBest)}</span>`;
    };
    $("board").innerHTML = `
      <thead><tr><th>#</th><th>Model</th><th>Pts/match</th><th>Gap to #1 (95%)</th><th class="num">Pts/season</th>
      <th class="num">Exact</th><th class="num">Outcome</th><th class="num">Margin</th><th class="num">RPS</th></tr></thead>
      <tbody>${rows.map((r, i) => `<tr title="${byName[r.model].description}">
        <td>${i + 1}</td>
        <td><span class="model">${swatch(r.model)}${r.model}${tag(r.model)}</span></td>
        <td class="barcell"><div class="bar"><i style="width:${(r.ptsPerMatch / maxPts) * 70}%;background:${slot[r.model].color}"></i>${fmt.pts3(r.ptsPerMatch)}</div></td>
        <td>${whisker(r)}</td>
        <td class="num">${Math.round(r.ptsPerMatch * 380)}</td>
        <td class="num">${r.exactPct.toFixed(1)}%</td><td class="num">${r.outcomePct.toFixed(1)}%</td>
        <td class="num">${r.marginPct.toFixed(1)}%</td><td class="num">${r.rps.toFixed(3)}</td></tr>`).join("")}</tbody>`;
  }
  $("board-kind").addEventListener("click", (e) => { if (e.target.dataset.k) { kind = e.target.dataset.k; drawBoard(); } });

  // Season race. Opens on the latest season once it has a few rounds, else the one before.
  const reference = byName.market ? "market" : leader.model;
  const recent = seasons.slice(-5);
  let current = B.races[seasons.at(-1)].length >= 15 ? seasons.at(-1) : seasons.at(-2) ?? seasons.at(-1);
  let mode = "gap";
  function drawRace() {
    $("seasons").innerHTML = recent.map((y) => `<button aria-pressed="${y === current}" data-y="${y}">${fmt.season(y)}</button>`).join("");
    $("mode").innerHTML = [["gap", `Gap to ${reference}`], ["total", "Total points"]]
      .map(([m, label]) => `<button data-m="${m}" aria-pressed="${m === mode}">${label}</button>`).join("");
    const gap = mode === "gap";
    $("race-hint").textContent = gap
      ? `Points ahead of (or behind) ${reference === "market" ? "the bookmakers" : reference}, as the season goes.`
      : "Running points total through the season.";
    const { series, labels } = race(current, gap ? reference : null);
    $("legend-race").innerHTML = legend(series.map((s) => s.model));
    lineChart($("race"), {
      series, labels, height: 300, zeroLine: gap,
      yFormat: (v) => Math.round(v),
      tipValue: (v) => (gap && v > 0 ? `+${v} pts` : `${v} pts`),
    });
  }
  $("seasons").addEventListener("click", (e) => { if (e.target.dataset.y) { current = +e.target.dataset.y; drawRace(); } });
  $("mode").addEventListener("click", (e) => { if (e.target.dataset.m) { mode = e.target.dataset.m; drawRace(); } });

  // Heatmap: one sequential hue; cells are labelled because the numbers fit.
  $("scale").innerHTML = [1, 2, 3, 4, 5].map((i) => `<i style="width:14px;height:10px;border-radius:2px;background:var(--seq-${i})"></i>`).join("");
  const order = board.map((r) => r.model);
  const vals = seasons.flatMap((y) => order.map((m) => B.bySeason[y][m]).filter((v) => v != null));
  const lo = Math.min(...vals), hi = Math.max(...vals);
  const step = (v) => Math.min(5, 1 + Math.floor(((v - lo) / (hi - lo || 1)) * 5));
  $("heat").innerHTML = `
    <tr><th></th>${seasons.map((y) => `<th>${fmt.season(y)}</th>`).join("")}</tr>
    ${order.map((m) => `<tr><td class="name"><span class="model">${swatch(m)}${m}</span></td>${seasons.map((y) => {
      const v = B.bySeason[y][m];
      if (v == null) return `<td class="cell">–</td>`;
      const s = step(v);
      return `<td class="cell ${s >= 3 ? "strong" : ""}" data-tip="${m} · ${fmt.season(y)}: ${fmt.pts(v)} pts/match" style="background:var(--seq-${s})">${fmt.pts(v)}</td>`;
    }).join("")}</tr>`).join("")}`;
  $("heat").addEventListener("pointermove", (e) => {
    const t = e.target.closest("[data-tip]");
    tooltip(t ? t.dataset.tip : null, e.clientX, e.clientY);
  });
  $("heat").addEventListener("pointerleave", () => tooltip(null));

  // Next matches: one row per match, one column per real model.
  const ref = realModels[0];
  $("bets").innerHTML = U.length ? `
    <thead><tr><th>Match</th><th>Kickoff (UTC)</th>${realModels.map((m) => `<th style="text-align:center"><span class="model">${swatch(m)}${m}</span></th>`).join("")}
    <th></th><th>${ref}: home / draw / away</th></tr></thead>
    <tbody>${U.map((f) => {
      const picks = realModels.map((m) => (f.bets[m] ? f.bets[m].pick.join("-") : "–"));
      const p = f.bets[ref];
      return `<tr><td>${f.home} – ${f.away}</td><td class="when">${fmt.kickoff(f.kickoff)}</td>
        ${picks.map((x) => `<td class="pick">${x}</td>`).join("")}
        <td class="when">${new Set(picks).size > 1 ? "models split" : "same bet"}</td>
        <td style="color:var(--ink-2)">${p ? `${fmt.pct(p.pH)} / ${fmt.pct(p.pD)} / ${fmt.pct(p.pA)}` : "–"}</td></tr>`;
    }).join("")}</tbody>` : `<tr><td class="empty">No upcoming bets saved. Run predict, then export.</td></tr>`;

  // The same bets as one block per match, for phones (the table needs a wide screen).
  $("bets-list").innerHTML = U.length ? U.map((f) => {
    const picks = realModels.map((m) => (f.bets[m] ? f.bets[m].pick.join("-") : "–"));
    const p = f.bets[ref];
    return `<div class="bet">
      <div class="bet-head"><b>${f.home} – ${f.away}</b><span class="when">${fmt.kickoff(f.kickoff)} UTC</span></div>
      <div class="bet-picks">${realModels.map((m, i) => `<span class="model">${swatch(m)}${m} <b>${picks[i]}</b></span>`).join("")}</div>
      <div class="when">${p ? `${ref}: H ${fmt.pct(p.pH)} D ${fmt.pct(p.pD)} A ${fmt.pct(p.pA)} · ` : ""}${new Set(picks).size > 1 ? "models split" : "same bet"}</div>
    </div>`;
  }).join("") : `<p class="empty">No upcoming bets saved. Run predict, then export.</p>`;

  $("theme").addEventListener("click", () => {
    const root = document.documentElement;
    const dark = root.dataset.theme === "dark" || (!root.dataset.theme && matchMedia("(prefers-color-scheme: dark)").matches);
    root.dataset.theme = dark ? "light" : "dark";
    localStorage.setItem("theme", root.dataset.theme);
  });

  drawBoard();
  drawRace();
  window.addEventListener("resize", drawRace);
})();
