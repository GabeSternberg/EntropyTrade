"use strict";
// Overview and Market Explorer views.
(function () {
  const ET = window.ET;
  const { h, icon, fmt, pill, statusPill, button, card, kpi, emptyState, unavailable, errorState, callout, meter, kv, segmented, dataTable, sparkline, lineChart, priceChart, tabs, skeleton, dot } = ET;

  function grid(cls, ...children) { return h("div", { class: `grid ${cls}` }, children); }
  function link(text, href) { return h("a", { class: "link", href }, text, icon("chevronRight", 13)); }
  const statusOrder = ["draft", "research", "backtested", "validated", "shadow", "paper"];

  // =============================================================== OVERVIEW
  ET.views.overview = async (root, ctx) => {
    root.append(ET.pageHeader("Overview", ET.mode() === "demo" ? "Research, paper trading and data health at a glance." : "Your local workspace at a glance: research runs, shadow monitors, data and readiness."));
    if (ET.mode() === "demo") return overviewDemo(root);
    return overviewReal(root, ctx);
  };

  function overviewDemo(root) {
    const d = ET.demo();
    const p = d.paper;
    const attested = d.gates.filter((g) => g.status === "attested").length;
    const active = d.strategies.filter((s) => ["paper", "shadow"].includes(s.status)).length;
    const winRate = p.by_strategy.reduce((a, s) => a + s.win_rate * s.trades, 0) / p.by_strategy.reduce((a, s) => a + s.trades, 0);
    root.append(h("div", { class: "kpi-strip" },
      kpi({ label: "Paper equity", value: fmt.usd(p.equity), deltaValue: p.equity / p.starting_balance - 1, sub: `from ${fmt.usd(p.starting_balance, 0)}`, iconName: "paper" }),
      kpi({ label: "Today's P&L", value: fmt.signedUsd(p.today_pnl), kind: p.today_pnl >= 0 ? "pos" : "neg", sub: "simulated fills", iconName: "activity" }),
      kpi({ label: "Realized P&L", value: fmt.signedUsd(p.realized_pnl), kind: "pos", sub: `${fmt.usd(p.fees_paid)} fees`, iconName: "target" }),
      kpi({ label: "Win rate", value: fmt.pct(winRate), sub: `${p.by_strategy.reduce((a, s) => a + s.trades, 0)} settled trades`, iconName: "check" }),
      kpi({ label: "Live strategies", value: `${active} / ${d.strategies.length}`, sub: "paper + shadow", iconName: "lab" }),
      kpi({ label: "V1 readiness", value: `${attested} / ${d.gates.length}`, sub: "gates attested", iconName: "flag", kind: attested === d.gates.length ? "pos" : "warn" })));

    let range = "1M";
    const chartHost = h("div");
    function drawCurve() {
      const n = { "1D": 24, "1W": 168, "1M": p.curve.length }[range];
      const pts = p.curve.slice(-n);
      chartHost.replaceChildren(lineChart([{ name: "Equity", values: pts, color: "var(--accent)", area: true }], { height: 250, yFormat: (v) => fmt.compactUsd(v), xFormat: range === "1D" ? (v) => fmt.time(v) : (v) => fmt.date(v).replace(/, \d{4}/, ""), baseline: p.starting_balance, watermark: "SIMULATED", label: "Paper equity curve" }));
    }
    drawCurve();
    const rangeSel = segmented(["1D", "1W", "1M"].map((k) => ({ key: k, label: k })), range, (k) => { range = k; drawCurve(); }, { "aria-label": "Equity range" });

    const riskCard = card({ title: "Risk utilization", subtitle: "Against configured paper limits", actions: link("Details", "#/paper") },
      h("div", { class: "limit-list" }, p.limits.map((l) => {
        const ratio = l.used / l.limit;
        return h("div", { class: "limit-row" }, h("div", { class: "limit-head" }, h("span", l.name), h("span", { class: "mono" }, `${l.unit === "usd" ? fmt.usd(l.used, 0) : l.unit === "pct" ? `${l.used}%` : l.used} / ${l.unit === "usd" ? fmt.usd(l.limit, 0) : l.unit === "pct" ? `${l.limit}%` : l.limit}`)), meter(l.used, l.limit, ratio > 0.8 ? "neg" : ratio > 0.6 ? "warn" : ""));
      })));
    root.append(grid("g-2-1", card({ title: "Paper equity", subtitle: "Demo account · hourly marks", actions: rangeSel, source: "demo" }, chartHost), riskCard));

    const opps = d.markets.filter((m) => m.status === "open" && m.edge !== null).sort((a, b) => Math.abs(b.edge) - Math.abs(a.edge)).slice(0, 6);
    const oppTable = dataTable({
      columns: [
        { key: "title", label: "Market", render: (m) => h("div", { class: "cell-market" }, h("span", { class: "cell-title" }, m.title), h("span", { class: "cell-sub mono" }, m.ticker)) },
        { key: "mid", label: "Market", align: "num", sort: (m) => (m.yes_bid + m.yes_ask) / 2, render: (m) => fmt.pct((m.yes_bid + m.yes_ask) / 2, 0) },
        { key: "model_prob", label: "Model", align: "num", render: (m) => fmt.pct(m.model_prob, 0) },
        { key: "edge", label: "Edge", align: "num", sort: (m) => Math.abs(m.edge), render: (m) => h("span", { class: `num-${ET.tone(m.edge)}` }, fmt.pct(m.edge, 1, true)) },
        { key: "spark", label: "48h", sortable: false, render: (m) => sparkline(m.spark, { width: 90, height: 24 }) },
      ], rows: opps, sortKey: "edge", onRow: (m) => ET.go(`#/markets/${encodeURIComponent(m.ticker)}`), dense: true, caption: "Top model-vs-market gaps",
    });
    const feed = h("ol", { class: "feed" }, d.alerts.map((a) => h("li", { class: "feed-item" },
      h("span", { class: `feed-icon ${a.severity}` }, icon(a.severity === "warning" ? "alert" : a.severity === "ok" ? "check" : "info", 14)),
      h("a", { class: "feed-body", href: a.route }, h("span", { class: "feed-title" }, a.title), h("span", { class: "feed-detail" }, a.detail)),
      h("time", { class: "feed-time" }, fmt.ago(a.at, d.now)))));
    root.append(grid("g-2-1", card({ title: "Market opportunities", subtitle: "Largest gaps between calibrated model and market mid (before fees)", actions: link("Explorer", "#/markets"), flush: true }, oppTable),
      card({ title: "Recent activity", actions: link("All alerts", "#/ops") }, feed)));

    const counts = statusOrder.map((st) => ({ st, n: d.strategies.filter((x) => x.status === st).length }));
    const pipeline = h("div", { class: "pipeline" }, counts.map(({ st, n }) => h("a", { class: `stage ${n ? "has" : ""}`, href: "#/lab" }, h("span", { class: "stage-n" }, String(n)), h("span", { class: "stage-label" }, fmt.words(st)))));
    const exps = h("ul", { class: "mini-list" }, d.experiments.slice(0, 5).map((e) => h("li", h("div", { class: "mini-main" }, h("span", { class: "mini-title" }, e.kind), h("span", { class: "mini-sub" }, `${e.strategy} · ${fmt.ago(e.created_at, d.now)}`)), e.verdict ? statusPill(e.verdict === "PROMISING" ? "promising" : e.verdict === "REJECTED" ? "rejected" : "insufficient") : statusPill(e.status))));
    const health = h("ul", { class: "mini-list" }, d.collectors.slice(0, 6).map((c) => h("li", h("div", { class: "mini-main" }, h("span", { class: "mini-title" }, dot(c.status === "ok" ? "pos" : c.status === "degraded" ? "warn" : "neg"), c.name), h("span", { class: "mini-sub" }, `${c.cadence} · ${fmt.ago(c.last_success, d.now)}`)), h("span", { class: "mono muted" }, fmt.compact(c.receipts_24h)))));
    const gatesList = h("ul", { class: "gate-list" }, d.gates.map((g) => h("li", { class: `gate ${g.status}` }, icon(g.status === "attested" ? "check" : "clock", 14), h("span", g.title))));
    root.append(grid("g-4",
      card({ title: "Strategy pipeline", subtitle: `${d.strategies.length} strategies`, actions: link("Lab", "#/lab") }, pipeline, h("div", { class: "spacer" }), exps),
      card({ title: "Data health", subtitle: "Collectors · last 24h", actions: link("Operations", "#/ops") }, health),
      card({ title: "V1 readiness", subtitle: `${d.gates.filter((g) => g.status === "attested").length} of ${d.gates.length} gates attested`, actions: link("Gates", "#/settings/risk") }, gatesList),
      card({ title: "Exposure by category", subtitle: "Open paper positions" }, ET.donut(p.by_category.map((c) => ({ label: c.name, value: c.exposure })), { center: h("div", h("strong", fmt.compactUsd(p.by_category.reduce((a, c) => a + c.exposure, 0))), h("span", "deployed")) }),
        h("ul", { class: "legend-list" }, p.by_category.map((c, i) => { const sw = h("span", { class: "swatch" }); sw.style.background = ET.PALETTE[i]; return h("li", sw, h("span", c.name), h("span", { class: "mono" }, fmt.usd(c.exposure, 0))); })))));
  }

  async function overviewReal(root, ctx) {
    const kpiRow = h("div", { class: "kpi-strip" }, Array.from({ length: 6 }, () => h("div", { class: "kpi" }, skeleton(2))));
    root.append(kpiRow);
    const body = h("div", { class: "stack" }, skeleton(6, "tall"));
    root.append(body);
    const r = await ET.apiAll({ catalog: "/api/catalog", jobs: "/api/jobs", monitors: "/api/monitors", alerts: "/api/alerts", gates: "/api/v1-gates", datasets: "/api/weather/datasets", schedules: "/api/weather/schedules", fees: "/api/fees" });
    if (!ctx.isCurrent()) return;
    if (!r.catalog.ok) {
      kpiRow.replaceChildren();
      body.replaceChildren(errorState(`The local API is not reachable: ${r.catalog.error.message}. Start it with \`uv run entropytrade-web\` and reload.`, () => ET.route()));
      return;
    }
    const jobs = r.jobs.ok ? r.jobs.data : [];
    const monitors = r.monitors.ok ? r.monitors.data : [];
    const alerts = r.alerts.ok ? r.alerts.data.alerts : [];
    const gates = r.gates.ok ? r.gates.data : null;
    const datasets = r.datasets.ok ? r.datasets.data : [];
    const attested = gates ? gates.gates.filter((g) => g.status === "attested").length : null;
    const completed = jobs.filter((j) => j.status === "completed").length;
    const running = jobs.filter((j) => ["queued", "starting", "running"].includes(j.status)).length;
    const openAlerts = alerts.filter((a) => !a.resolved_at);
    kpiRow.replaceChildren(
      kpi({ label: "Research runs", value: fmt.num(jobs.length), sub: jobs.length ? `${completed} completed · ${running} in progress` : "none yet", iconName: "beaker" }),
      kpi({ label: "Monitors", value: fmt.num(monitors.length), sub: `${monitors.filter((m) => m.status === "active").length} active`, iconName: "eye" }),
      kpi({ label: "Paper accounts", value: fmt.num(monitors.length), sub: "1 per shadow monitor", iconName: "paper" }),
      kpi({ label: "Open alerts", value: fmt.num(openAlerts.length), sub: `${openAlerts.filter((a) => !a.acknowledged_at).length} need acknowledgement`, iconName: "bell", kind: openAlerts.length ? "warn" : "" }),
      kpi({ label: "Datasets", value: fmt.num(datasets.length), sub: datasets.length ? `${datasets[0].readiness?.status ? fmt.words(datasets[0].readiness.status) : "latest"}` : "none frozen", iconName: "database" }),
      kpi({ label: "V1 readiness", value: attested === null ? "—" : `${attested} / ${gates.gates.length}`, sub: "gates attested", iconName: "flag", kind: gates?.v1_complete ? "pos" : "warn" }));

    const runsTable = jobs.length ? dataTable({
      columns: [
        { key: "idea", label: "Research idea", sort: (j) => j.request.idea, render: (j) => h("div", { class: "cell-market" }, h("span", { class: "cell-title" }, j.request.idea), h("span", { class: "cell-sub" }, `${j.request.family} · ${fmt.words(j.request.mode)}`)) },
        { key: "status", label: "Status", render: (j) => statusPill(j.status) },
        { key: "created_at", label: "Created", align: "num", render: (j) => fmt.dateTime(j.created_at) },
      ], rows: jobs.slice(0, 8), sortKey: "created_at", dense: true, onRow: (j) => openRun(j.id),
    }) : emptyState({ iconName: "beaker", title: "No research runs yet", body: "Start a run in the Research Workbench. Completed runs, their evidence and typed candidates appear here.", action: h("a", { class: "btn primary sm", href: "#/workbench" }, "Open workbench") });

    const alertList = openAlerts.length ? h("ol", { class: "feed" }, openAlerts.slice(0, 6).map((a) => h("li", { class: "feed-item" },
      h("span", { class: "feed-icon warning" }, icon("alert", 14)),
      h("a", { class: "feed-body", href: "#/ops" }, h("span", { class: "feed-title" }, fmt.words(a.kind)), h("span", { class: "feed-detail" }, `Monitor ${fmt.short(a.monitor_id)} · ${a.acknowledged_at ? "acknowledged, still open" : "needs acknowledgement"}`)),
      h("time", { class: "feed-time" }, fmt.ago(a.opened_at)))))
      : r.alerts.ok ? emptyState({ iconName: "check", title: "No open operator alerts", body: "Stale collection, repeated failures and unresolved reconciliation alerts from shadow monitors appear here." }) : errorState(r.alerts.error.message);

    const gateList = gates ? h("ul", { class: "gate-list" }, gates.gates.map((g) => h("li", { class: `gate ${g.status}`, title: g.detail }, icon(g.status === "attested" ? "check" : g.status === "invalid" ? "alert" : "clock", 14), h("span", g.title), g.reference ? h("span", { class: "gate-ref" }, g.reference) : null))) : errorState(r.gates.error.message);

    const opp = unavailable("No live market feed in the website", "Kalshi listings are collected by the separate read-only collector and are not loaded into this page. Market data captured by research runs is under Workbench → Evidence & lineage.", link("Market Explorer", "#/markets"));
    const paperBody = monitors.length ? h("ul", { class: "mini-list" }, monitors.slice(0, 6).map((m) => h("li", h("div", { class: "mini-main" }, h("span", { class: "mini-title" }, `${m.family} · ${m.candidate_id}`), h("span", { class: "mini-sub mono" }, fmt.short(m.id))), statusPill(m.status))))
      : emptyState({ iconName: "paper", title: "No paper accounts", body: "A simulated paper account starts with each shadow monitor on a completed real research candidate.", action: link("Paper Trading", "#/paper") });
    const sched = r.schedules.ok ? r.schedules.data : [];
    const dataBody = h("div", kv([
      ["Frozen weather datasets", fmt.num(datasets.length)],
      ["Forward validation schedules", sched.length ? `${sched.length} (${sched.filter((x) => x.status === "active").length} active)` : "Not enabled (opt-in)"],
      ["Fee evidence versions", r.fees.ok ? fmt.num(r.fees.data.versions?.length || 0) : "Unavailable"],
      ["Collector process", h("span", { class: "muted" }, "Runs separately · not monitored here")],
    ]));
    body.replaceChildren(
      grid("g-2-1", card({ title: "Recent research runs", subtitle: "Durable queue in this workspace", actions: link("Strategy Lab", "#/lab"), flush: jobs.length > 0, source: "real" }, runsTable), card({ title: "Operator alerts", actions: link("Operations", "#/ops") }, alertList)),
      grid("g-3", card({ title: "Market opportunities" }, opp), card({ title: "Paper & shadow", actions: link("Paper Trading", "#/paper") }, paperBody), card({ title: "Data & evidence", actions: link("Operations", "#/ops") }, dataBody)),
      card({ title: "V1 readiness", subtitle: gates ? (gates.v1_complete ? "Every gate is attested." : `${gates.open.length} of ${gates.gates.length} gates are not attested. Gates are attested only by human-written files under data/acceptance.`) : "" }, gateList));
  }
  function openRun(id) {
    ET.go("#/workbench");
    if (typeof window.selectJob === "function") window.selectJob(id).catch(() => {});
  }
  ET.openRun = openRun;

  // ========================================================== MARKET EXPLORER
  ET.views.markets = async (root, ctx) => {
    if (ctx.params[0]) return marketDetail(root, ctx.params[0], ctx);
    root.append(ET.pageHeader("Market Explorer", "Search and filter Kalshi event contracts by category, price, spread and liquidity."));
    if (ET.mode() !== "demo") return marketsReal(root, ctx);
    const d = ET.demo();
    const categories = [...new Set(d.markets.map((m) => m.category))];
    const state = { q: "", cats: new Set(categories), status: "open", minP: 0, maxP: 100, maxSpread: 8, minLiq: 0, modelOnly: false, closing: "any" };
    const countEl = h("span", { class: "count" });
    const tableHost = h("div");
    const chips = h("div", { class: "chip-row" });

    const search = h("input", { type: "search", class: "input", placeholder: "Search ticker, title or series", "aria-label": "Search markets" });
    search.addEventListener("input", () => { state.q = search.value.trim().toLowerCase(); draw(); });
    const catBoxes = h("div", { class: "check-grid" }, categories.map((c) => {
      const box = h("input", { type: "checkbox", checked: true, value: c });
      box.addEventListener("change", () => { if (box.checked) state.cats.add(c); else state.cats.delete(c); draw(); });
      return h("label", { class: "check" }, box, h("span", c), h("span", { class: "check-count" }, String(d.markets.filter((m) => m.category === c).length)));
    }));
    const statusSel = segmented([{ key: "open", label: "Open" }, { key: "settled", label: "Settled" }, { key: "all", label: "All" }], state.status, (k) => { state.status = k; draw(); }, { "aria-label": "Market status" });
    function rangeInput(label, key, min, max, unit) {
      const out = h("output", { class: "range-out mono" });
      const input = h("input", { type: "range", min, max, value: state[key], "aria-label": label });
      const sync = () => { out.textContent = `${state[key]}${unit}`; };
      input.addEventListener("input", () => { state[key] = Number(input.value); sync(); draw(); });
      sync();
      return h("div", { class: "range-field" }, h("div", { class: "range-head" }, h("span", label), out), input);
    }
    const liqSel = h("select", { class: "input", "aria-label": "Minimum liquidity" }, [["0", "Any depth"], ["2000", "≥ $2K"], ["5000", "≥ $5K"], ["10000", "≥ $10K"]].map(([v, t]) => h("option", { value: v }, t)));
    liqSel.addEventListener("change", () => { state.minLiq = Number(liqSel.value); draw(); });
    const closeSel = h("select", { class: "input", "aria-label": "Closing window" }, [["any", "Any time"], ["day", "Within 24 hours"], ["week", "Within 7 days"], ["month", "Within 30 days"]].map(([v, t]) => h("option", { value: v }, t)));
    closeSel.addEventListener("change", () => { state.closing = closeSel.value; draw(); });
    const modelBox = h("input", { type: "checkbox" });
    modelBox.addEventListener("change", () => { state.modelOnly = modelBox.checked; draw(); });
    const reset = button("Reset filters", { variant: "ghost sm" }, "refresh");
    reset.addEventListener("click", () => ET.route());

    const filters = h("aside", { class: "filters card" },
      h("div", { class: "filter-head" }, h("h3", { class: "card-title" }, icon("filter", 14), "Filters"), reset),
      h("div", { class: "field" }, h("label", { class: "field-label" }, "Search"), search),
      h("div", { class: "field" }, h("span", { class: "field-label" }, "Status"), statusSel),
      h("div", { class: "field" }, h("span", { class: "field-label" }, "Category"), catBoxes),
      h("div", { class: "field" }, h("span", { class: "field-label" }, "Implied probability"), rangeInput("Minimum", "minP", 0, 100, "%"), rangeInput("Maximum", "maxP", 0, 100, "%")),
      h("div", { class: "field" }, rangeInput("Max spread", "maxSpread", 1, 8, "¢")),
      h("div", { class: "field" }, h("label", { class: "field-label" }, "Liquidity"), liqSel),
      h("div", { class: "field" }, h("label", { class: "field-label" }, "Closes"), closeSel),
      h("label", { class: "check toggle" }, modelBox, h("span", "Only markets with a model estimate")));

    const columns = [
      { key: "title", label: "Market", render: (m) => h("div", { class: "cell-market" }, h("span", { class: "cell-title" }, m.title), h("span", { class: "cell-sub" }, h("span", { class: `cat-chip cat-${m.category.toLowerCase()}` }, m.category), h("span", { class: "mono" }, m.ticker))) },
      { key: "spark", label: "48h", sortable: false, render: (m) => sparkline(m.spark, { width: 76, height: 26 }) },
      { key: "mid", label: "Implied", align: "num", sort: (m) => m.status === "open" ? (m.yes_bid + m.yes_ask) / 2 : m.last, render: (m) => m.status === "open" ? h("div", { class: "prob" }, h("strong", fmt.pct((m.yes_bid + m.yes_ask) / 2, 0)), meter((m.yes_bid + m.yes_ask) / 2, 1, "accent")) : statusPill(m.result === "yes" ? "Settled YES" : "Settled NO") },
      { key: "bidask", label: "Bid / Ask", align: "num", sort: (m) => m.spread ?? 99, render: (m) => m.status === "open" ? h("div", { class: "stack-cell" }, h("span", { class: "mono" }, `${fmt.cents(m.yes_bid)} / ${fmt.cents(m.yes_ask)}`), h("span", { class: "cell-sub" }, `${fmt.cents(m.spread)} spread`)) : "—" },
      { key: "change_24h", label: "24h", align: "num", render: (m) => h("span", { class: `num-${ET.tone(m.change_24h)}` }, `${m.change_24h > 0 ? "+" : ""}${Math.round(m.change_24h * 100)}¢`) },
      { key: "volume_24h", label: "Vol / Depth", align: "num", render: (m) => h("div", { class: "stack-cell" }, h("span", fmt.compact(m.volume_24h)), h("span", { class: "cell-sub" }, m.status === "open" ? fmt.compactUsd(m.liquidity) : "—")) },
      { key: "edge", label: "Model edge", align: "num", sort: (m) => m.edge ?? -9, render: (m) => (m.edge === null ? h("span", { class: "muted" }, "—") : h("span", { class: `num-${ET.tone(m.edge)}` }, fmt.pct(m.edge, 1, true))) },
      { key: "close", label: "Closes", align: "num", render: (m) => h("span", { class: "muted" }, m.status === "open" ? `in ${fmt.duration((m.close - d.now) / 1000)}` : fmt.date(m.close)) },
    ];
    const table = dataTable({ columns, rows: [], sortKey: "volume_24h", onRow: (m) => ET.go(`#/markets/${encodeURIComponent(m.ticker)}`), pageSize: 15, caption: "Markets" });
    tableHost.append(table);
    function draw() {
      const horizon = { any: Infinity, day: ET.demoTools.DAY, week: 7 * ET.demoTools.DAY, month: 30 * ET.demoTools.DAY }[state.closing];
      const rows = d.markets.filter((m) => {
        if (!state.cats.has(m.category)) return false;
        if (state.status !== "all" && m.status !== state.status) return false;
        if (state.q && !`${m.ticker} ${m.title} ${m.series}`.toLowerCase().includes(state.q)) return false;
        const mid = m.status === "open" ? ((m.yes_bid + m.yes_ask) / 2) * 100 : m.last * 100;
        if (mid < state.minP || mid > state.maxP) return false;
        if (m.spread !== null && m.spread * 100 > state.maxSpread) return false;
        if (m.liquidity < state.minLiq && m.status === "open") return false;
        if (state.modelOnly && m.model_prob === null) return false;
        if (m.status === "open" && m.close - d.now > horizon) return false;
        return true;
      });
      table.update(rows);
      countEl.textContent = `${rows.length} of ${d.markets.length} markets`;
      const active = [];
      if (state.q) active.push(`“${state.q}”`);
      if (state.cats.size !== categories.length) active.push(`${state.cats.size} categories`);
      if (state.minP > 0 || state.maxP < 100) active.push(`${state.minP}–${state.maxP}%`);
      if (state.maxSpread < 8) active.push(`spread ≤ ${state.maxSpread}¢`);
      if (state.minLiq) active.push(`depth ≥ ${fmt.compactUsd(state.minLiq)}`);
      if (state.closing !== "any") active.push(closeSel.selectedOptions[0].textContent.toLowerCase());
      if (state.modelOnly) active.push("model estimate");
      chips.replaceChildren(...active.map((t) => pill(t, "chip")));
    }
    draw();
    const cats = categories.map((c) => { const ms = d.markets.filter((m) => m.category === c && m.status === "open"); return { c, n: ms.length, vol: ms.reduce((a, m) => a + m.volume_24h, 0) }; });
    root.append(h("div", { class: "cat-strip" }, cats.map(({ c, n, vol }) => h("button", { type: "button", class: "cat-card", onclick: () => { state.cats = new Set([c]); catBoxes.querySelectorAll("input").forEach((b) => { b.checked = b.value === c; }); draw(); } }, h("span", { class: `cat-dot cat-${c.toLowerCase()}` }), h("span", { class: "cat-name" }, c), h("span", { class: "cat-meta" }, `${n} open · ${fmt.compact(vol)} vol`)))));
    root.append(h("div", { class: "explorer" }, filters, card({ title: h("span", { class: "results-title" }, countEl), actions: chips, flush: true, source: "demo" }, tableHost)));
  }

  async function marketsReal(root, ctx) {
    const host = h("div", { class: "stack" }, skeleton(4));
    root.append(host);
    const monitors = await ET.api("/api/monitors").catch((error) => ({ error }));
    if (!ctx.isCurrent()) return;
    const parts = [callout("Real Mode shows only market data retained in this workspace. Live Kalshi listings are collected by the separate read-only collector (`entropytrade collect`), which is deliberately kept outside the website; its history is not loaded here.", "info")];
    if (monitors.error) { host.replaceChildren(...parts, errorState(monitors.error.message, () => ET.route())); return; }
    const details = await Promise.all(monitors.slice(0, 10).map((m) => ET.api(`/api/monitors/${m.id}`).catch(() => null)));
    if (!ctx.isCurrent()) return;
    const rows = details.filter(Boolean).flatMap((m) => (m.contracts || []).map((c) => ({ ...c, monitor: m.id, family: m.family })));
    if (!rows.length) {
      parts.push(card({ title: "Tracked contracts", source: "real" }, unavailable("No market data retained in this workspace", "Contracts appear here once a shadow monitor captures public listings for a completed real research candidate. Use Demo Mode to preview the full explorer.", h("div", { class: "row-actions" }, h("a", { class: "btn primary sm", href: "#/workbench" }, "Open workbench"), button("Preview in Demo Mode", { variant: "ghost sm", onclick: () => ET.setMode("demo") }, "eye")))));
    } else {
      parts.push(card({ title: "Contracts tracked by shadow monitors", subtitle: `${rows.length} contracts · official outcomes recorded as they become available`, flush: true, source: "real" }, dataTable({
        columns: [
          { key: "ticker", label: "Contract", render: (c) => h("span", { class: "mono" }, c.ticker) },
          { key: "family", label: "Family" },
          { key: "title", label: "Title", sort: (c) => c.market?.title, render: (c) => c.market?.title || c.market?.subtitle || "—" },
          { key: "close", label: "Close time", render: (c) => fmt.dateTime(c.market?.close_time) },
          { key: "outcome", label: "Official outcome", sort: (c) => c.outcome?.result, render: (c) => (c.outcome?.result ? statusPill(c.outcome.result) : h("span", { class: "muted" }, "Pending")) },
          { key: "last_attempt", label: "Last check", align: "num", render: (c) => fmt.dateTime(c.last_attempt) },
        ], rows, sortKey: "ticker", sortDir: "asc", pageSize: 20,
      })));
    }
    host.replaceChildren(...parts);
  }

  function orderBook(m) {
    const r = (() => { let a = m.ticker.length * 7919; return () => { a = (a * 16807) % 2147483647; return a / 2147483647; }; })();
    const bids = Array.from({ length: 6 }, (_, i) => ({ p: Math.max(0.01, m.yes_bid - i * 0.01), q: Math.round(40 + r() * 600) }));
    const asks = Array.from({ length: 6 }, (_, i) => ({ p: Math.min(0.99, m.yes_ask + i * 0.01), q: Math.round(40 + r() * 600) }));
    const max = Math.max(...bids.map((b) => b.q), ...asks.map((a) => a.q));
    const row = (side, x) => { const bar = h("span", { class: `book-bar ${side}` }); bar.style.width = `${(x.q / max) * 100}%`; return h("div", { class: `book-row ${side}` }, bar, h("span", { class: "mono" }, fmt.cents(x.p)), h("span", { class: "mono muted" }, fmt.num(x.q))); };
    return h("div", { class: "book" }, h("div", { class: "book-head" }, h("span", "Price"), h("span", "Contracts")), asks.slice().reverse().map((a) => row("ask", a)), h("div", { class: "book-mid" }, `Spread ${fmt.cents(m.spread)}`), bids.map((b) => row("bid", b)));
  }

  function marketDetail(root, ticker, ctx) {
    if (ET.mode() !== "demo") {
      root.append(ET.pageHeader(ticker, "Market detail"), card({}, unavailable("Market detail is not available in Real Mode", "Live market data is not served to the website. Retained contract rules and receipts for research runs are in the Research Workbench.", link("Back to explorer", "#/markets"))));
      return;
    }
    const d = ET.demo();
    const m = d.markets.find((x) => x.ticker === ticker);
    if (!m) { root.append(ET.pageHeader("Market not found"), card({}, emptyState({ iconName: "search", title: `No market ${ticker}`, action: link("Back to explorer", "#/markets") }))); return; }
    const mid = m.status === "open" ? (m.yes_bid + m.yes_ask) / 2 : m.last;
    root.append(h("a", { class: "back", href: "#/markets" }, icon("chevronLeft", 14), "All markets"));
    root.append(h("header", { class: "page-head market-head" },
      h("div", { class: "page-titles" }, h("div", { class: "eyebrow-row" }, pill(m.category, `cat cat-${m.category.toLowerCase()}`), h("span", { class: "mono muted" }, m.ticker), statusPill(m.status)), h("h1", m.title), h("p", { class: "page-sub" }, `Series ${m.series} · Event ${m.event} · Settles on ${m.source}`)),
      h("div", { class: "page-actions" }, ET.sourceChip(), h("div", { class: "price-big" }, h("span", { class: "price-label" }, "YES"), h("strong", fmt.pct(mid, 0)), h("span", { class: `num-${ET.tone(m.change_24h)}` }, `${m.change_24h > 0 ? "+" : ""}${Math.round(m.change_24h * 100)}¢ 24h`)))));
    let span = "7D";
    const chartHost = h("div");
    const drawChart = () => {
      const hist = span === "24H" ? ET.demoTools.priceHistory(m.ticker, m.fair, 96, 15 * 60e3) : ET.demoTools.priceHistory(m.ticker, m.fair, span === "7D" ? 168 : 360, span === "7D" ? ET.demoTools.HOUR : 2 * ET.demoTools.HOUR);
      chartHost.replaceChildren(priceChart(hist, { watermark: "SIMULATED", xFormat: span === "24H" ? (v) => fmt.time(v) : (v) => fmt.date(v).replace(/, \d{4}/, "") }));
    };
    drawChart();
    const spanSel = segmented(["24H", "7D", "30D"].map((k) => ({ key: k, label: k })), span, (k) => { span = k; drawChart(); }, { "aria-label": "Chart range" });
    const modelCard = m.model_prob === null ? emptyState({ iconName: "lab", title: "No model coverage", body: "No registered model covers this series." })
      : h("div", { class: "model-compare" },
        h("div", { class: "mc-row" }, h("span", "Market mid"), h("strong", fmt.pct(mid, 1)), meter(mid, 1, "muted")),
        h("div", { class: "mc-row" }, h("span", "Calibrated model"), h("strong", fmt.pct(m.model_prob, 1)), meter(m.model_prob, 1, "accent")),
        h("div", { class: "mc-row" }, h("span", "Gross edge"), h("strong", { class: `num-${ET.tone(m.edge)}` }, fmt.pct(m.edge, 1, true))),
        h("p", { class: "hint" }, "Edge before fees and slippage. Decisions also require fresh book depth and certified fee evidence."));
    const related = d.markets.filter((x) => x.event === m.event && x.ticker !== m.ticker);
    root.append(h("div", { class: "grid g-2-1" },
      h("div", { class: "stack" },
        card({ title: "Price history", subtitle: "YES contract price", actions: spanSel, source: "demo" }, chartHost),
        card({ title: "Contract rules" }, h("p", { class: "rules" }, m.rules), kv([["Settlement source", m.source], ["Close", fmt.dateTime(m.close)], ["Series", m.series], ["Event", m.event]]))),
      h("div", { class: "stack" },
        m.status === "open" ? card({ title: "Order book", subtitle: "YES side · top 6 levels" }, orderBook(m)) : card({ title: "Settlement" }, kv([["Result", statusPill(m.result === "yes" ? "Settled YES" : "Settled NO")], ["Final price", fmt.cents(m.last)]])),
        card({ title: "Model vs market" }, modelCard),
        card({ title: "Statistics" }, kv([["Bid / Ask", m.status === "open" ? `${fmt.cents(m.yes_bid)} / ${fmt.cents(m.yes_ask)}` : "—"], ["Volume (24h)", fmt.num(m.volume_24h)], ["Open interest", fmt.num(m.open_interest)], ["Displayed depth", fmt.usd(m.liquidity, 0)]])),
        related.length ? card({ title: "Same event", flush: true }, h("ul", { class: "mini-list pad" }, related.map((x) => h("li", h("a", { class: "mini-main", href: `#/markets/${encodeURIComponent(x.ticker)}` }, h("span", { class: "mini-title" }, x.title), h("span", { class: "mini-sub mono" }, x.ticker)), h("strong", { class: "mono" }, fmt.pct((x.yes_bid + x.yes_ask) / 2, 0)))))) : null)));
    root.append(h("div", { class: "row-actions end" }, button("Trade (disabled)", { variant: "primary", disabled: true, title: "Order submission is not available from this website" }, "lock"), h("span", { class: "hint" }, "Order entry is intentionally absent. Paper fills come only from approved strategies' simulated execution.")));
    void ctx; void tabs;
  }
})();
