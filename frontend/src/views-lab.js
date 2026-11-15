"use strict";
// Strategy Lab and Backtesting & Analytics views.
(function () {
  const ET = window.ET;
  const { h, icon, fmt, pill, statusPill, button, card, kpi, emptyState, unavailable, errorState, callout, kv, segmented, dataTable, lineChart, barChart, calibrationChart, heatGrid, tabs, skeleton, dialog, toast } = ET;
  const STAGES = ["draft", "research", "backtested", "validated", "shadow", "paper"];
  function link(text, href) { return h("a", { class: "link", href }, text, icon("chevronRight", 13)); }
  function verdictPill(v) { return v ? statusPill(v === "PROMISING" ? "promising" : v === "REJECTED" ? "rejected" : "insufficient") : h("span", { class: "muted" }, "—"); }

  // Session-only demo drafts: kept in memory, never persisted or sent anywhere.
  const demoDrafts = [];

  // ============================================================ STRATEGY LAB
  ET.views.lab = async (root, ctx) => {
    if (ctx.params[0]) return strategyDetail(root, ctx.params[0], ctx);
    const newBtn = button("New hypothesis", { variant: "primary" }, "plus");
    newBtn.addEventListener("click", () => newHypothesis());
    root.append(ET.pageHeader("Strategy Lab", "Formulate hypotheses, review typed specifications and track every experiment's evidence.", newBtn));
    if (ET.mode() === "demo") return labDemo(root, ctx);
    return labReal(root, ctx);
  };

  function newHypothesis() {
    const idea = h("textarea", { class: "input", rows: 5, maxlength: 6000, "aria-label": "Hypothesis", placeholder: "e.g. Upward forecast revisions in the final 12 hours are under-priced in high-temperature contracts" });
    const family = h("select", { class: "input", "aria-label": "Market family" }, h("option", { value: "weather" }, "Weather · daily high temperature"), h("option", { value: "bitcoin" }, "Bitcoin · KXBTC contracts"));
    const examples = h("div", { class: "chip-row" }, [
      "Do upward forecast revisions improve weather contract probabilities?",
      "revision_f >= 1.25 and hours_to_close < 8",
      "Test Bitcoin spot distance to strike",
    ].map((text) => h("button", { type: "button", class: "pill chip clickable", onclick: () => { idea.value = text; } }, text)));
    const demo = ET.mode() === "demo";
    const body = h("div", { class: "form-stack" },
      demo ? callout("Demo Mode: this creates a simulated draft in your browser session only. It is not formulated, saved or evaluated.", "demo") : callout("Real Mode: you'll continue in the Research Workbench with this idea prefilled. Choose a data source there, review the evidence gates, then start the run.", "info"),
      h("label", { class: "field-label" }, "Hypothesis (natural language or exact comparisons joined by AND)"), idea, examples,
      h("label", { class: "field-label" }, "Market family"), family);
    const go = button(demo ? "Create simulated draft" : "Continue in workbench", { variant: "primary" }, demo ? "sparkles" : "workbench");
    const dlg = dialog({ title: "New hypothesis", body, footer: [button("Cancel", { variant: "ghost", onclick: () => dlg.close() }), go] });
    idea.focus();
    go.addEventListener("click", () => {
      const text = idea.value.trim();
      if (!text) { idea.focus(); idea.classList.add("invalid"); return; }
      dlg.close();
      if (demo) {
        const comparisons = text.split(/\s+and\s+/i).filter((part) => /(>=|<=|==|>|<)/.test(part));
        demoDrafts.unshift({ id: `draft-${Date.now().toString(36)}`, name: text.length > 48 ? `${text.slice(0, 46)}…` : text, family: family.value === "weather" ? "Weather · daily high" : "Crypto · BTC hourly", status: "draft", approval: "Not requested", hypothesis: text, signal: comparisons.length ? comparisons.join(" AND ") : "Signal selected from prose (no numeric threshold invented)", sizing: "Not specified", metrics: null, data_kind: "demo", session: true });
        toast("Simulated draft created for this session", "ok");
        ET.route();
      } else {
        ET.go("#/workbench");
        const target = document.getElementById("idea"); const fam = document.getElementById("family");
        if (target) { target.value = text; target.focus(); }
        if (fam) { fam.value = family.value; fam.dispatchEvent(new Event("change")); }
      }
    });
  }

  function labDemo(root, ctx) {
    const d = ET.demo();
    const strategies = [...demoDrafts, ...d.strategies];
    const expByStrategy = (id) => d.experiments.filter((e) => e.strategy_id === id);
    const completed = d.experiments.filter((e) => e.status === "completed");
    root.append(h("div", { class: "kpi-strip" },
      kpi({ label: "Strategies", value: String(strategies.length), sub: `${strategies.filter((s) => ["paper", "shadow"].includes(s.status)).length} in paper/shadow`, iconName: "lab" }),
      kpi({ label: "Experiments", value: String(d.experiments.length), sub: `${d.experiments.filter((e) => e.status === "running").length} running`, iconName: "beaker" }),
      kpi({ label: "Promising", value: String(completed.filter((e) => e.verdict === "PROMISING").length), sub: `of ${completed.length} completed`, iconName: "star", kind: "pos" }),
      kpi({ label: "Best Brier", value: fmt.num(Math.min(...completed.map((e) => e.brier)), 3), sub: "lower is better", iconName: "target" }),
      kpi({ label: "Pending review", value: String(strategies.filter((s) => s.approval === "Pending review").length), sub: "awaiting human approval", iconName: "flag", kind: "warn" })));

    const series = d.experiments.filter((e) => e.brier !== null).slice().reverse();
    const trend = card({ title: "Forecast quality across experiments", subtitle: "Brier score and log loss per completed experiment (lower is better)", source: "demo" },
      lineChart([
        { name: "Brier score", values: series.map((e) => ({ x: e.created_at, y: e.brier })), color: "var(--c1)" },
        { name: "Log loss ÷ 3", values: series.map((e) => ({ x: e.created_at, y: e.log_loss / 3 })), color: "var(--c3)" },
      ], { height: 220, yFormat: (v) => v.toFixed(3), xFormat: (v) => fmt.date(v).replace(/, \d{4}/, ""), watermark: "SIMULATED" }));
    root.append(trend);

    const panel = h("div");
    const key = ctx.query.get("tab") || "strategies";
    const tabBar = tabs([{ key: "strategies", label: "Strategies", count: strategies.length }, { key: "experiments", label: "Experiments", count: d.experiments.length }, { key: "models", label: "Model comparison", count: d.models.length }], key, render);
    function render(k) {
      if (k === "strategies") {
        const filter = { stage: "all" };
        const board = h("div");
        const drawBoard = () => board.replaceChildren(dataTable({
          columns: [
            { key: "name", label: "Strategy", render: (s) => h("div", { class: "cell-market" }, h("span", { class: "cell-title" }, s.name, s.session ? pill("session draft", "demo-tag") : null), h("span", { class: "cell-sub" }, s.family)) },
            { key: "status", label: "Stage", sort: (s) => STAGES.indexOf(s.status), render: (s) => stageTrack(s.status) },
            { key: "approval", label: "Approval", render: (s) => approvalPill(s.approval) },
            { key: "sharpe", label: "Sharpe", align: "num", sort: (s) => s.metrics?.sharpe ?? -99, render: (s) => (s.metrics ? fmt.num(s.metrics.sharpe, 2) : "—") },
            { key: "ret", label: "Backtest return", align: "num", sort: (s) => s.metrics?.total_return ?? -99, render: (s) => (s.metrics ? h("span", { class: `num-${ET.tone(s.metrics.total_return)}` }, fmt.pct(s.metrics.total_return, 1, true)) : "—") },
            { key: "brier", label: "Brier", align: "num", sort: (s) => s.metrics?.brier ?? 99, render: (s) => (s.metrics ? fmt.num(s.metrics.brier, 3) : "—") },
            { key: "exps", label: "Experiments", align: "num", sort: (s) => expByStrategy(s.id).length, render: (s) => String(expByStrategy(s.id).length) },
          ], rows: strategies.filter((s) => filter.stage === "all" || s.status === filter.stage), sortKey: "status", onRow: (s) => (s.session ? toast("Session drafts have no detail page", "info") : ET.go(`#/lab/${s.id}`)), caption: "Strategies",
        }));
        const stageSel = segmented([{ key: "all", label: "All" }, ...STAGES.map((st) => ({ key: st, label: fmt.words(st) }))], "all", (k2) => { filter.stage = k2; drawBoard(); }, { "aria-label": "Stage filter", class: "segmented scroll" });
        drawBoard();
        panel.replaceChildren(card({ title: "Strategies", actions: stageSel, flush: true }, board));
      } else if (k === "experiments") {
        panel.replaceChildren(card({ title: "Experiments", subtitle: "Every run keeps its dataset identity, fold boundaries and evidence links", flush: true }, dataTable({
          columns: [
            { key: "kind", label: "Experiment", render: (e) => h("div", { class: "cell-market" }, h("span", { class: "cell-title" }, e.kind), h("span", { class: "cell-sub" }, e.strategy)) },
            { key: "id", label: "Run ID", render: (e) => h("span", { class: "mono muted" }, e.id) },
            { key: "status", label: "Status", render: (e) => statusPill(e.status) },
            { key: "verdict", label: "Verdict", render: (e) => verdictPill(e.verdict) },
            { key: "created_at", label: "Created", align: "num", render: (e) => fmt.dateTime(e.created_at) },
            { key: "dataset", label: "Dataset", render: (e) => h("span", { class: "mono muted" }, e.dataset) },
            { key: "events", label: "Events", align: "num", render: (e) => fmt.num(e.events) },
            { key: "brier", label: "Brier", align: "num", sort: (e) => e.brier ?? 99, render: (e) => (e.brier === null ? "—" : fmt.num(e.brier, 4)) },
            { key: "log_loss", label: "Log loss", align: "num", sort: (e) => e.log_loss ?? 99, render: (e) => (e.log_loss === null ? "—" : fmt.num(e.log_loss, 4)) },
          ], rows: d.experiments, sortKey: "created_at", pageSize: 12, onRow: (e) => experimentDialog(e), caption: "Experiments",
        })));
      } else {
        panel.replaceChildren(h("div", { class: "grid g-1-1" },
          card({ title: "Calibration", subtitle: "Reliability diagram · 10 bins · validation folds only", source: "demo" }, calibrationChart(d.models.map((m) => ({ name: m.name, bins: m.bins })), { watermark: "SIMULATED" })),
          card({ title: "Predictive metrics", subtitle: `${d.models[0].events.toLocaleString()} validation events · protected holdout excluded`, flush: true }, dataTable({
            columns: [
              { key: "name", label: "Model", render: (m) => h("strong", m.name) },
              { key: "brier", label: "Brier", align: "num", render: (m) => fmt.num(m.brier, 3) },
              { key: "log_loss", label: "Log loss", align: "num", render: (m) => fmt.num(m.log_loss, 3) },
              { key: "ece", label: "ECE", align: "num", render: (m) => fmt.num(m.ece, 3) },
              { key: "auc", label: "AUC", align: "num", render: (m) => fmt.num(m.auc, 2) },
            ], rows: d.models, sortKey: "brier", sortDir: "asc",
          }), h("div", { class: "pad" }, barChart(d.models.map((m) => ({ label: m.name.split(" ")[0], value: d.models[0].brier - m.brier, series: "Brier improvement vs market", tone: m.name.startsWith("Market") ? "muted" : "accent" })), { height: 160, signed: false, yFormat: (v) => v.toFixed(3), watermark: "SIMULATED" })))));
      }
    }
    render(key);
    root.append(tabBar.el, panel);
  }

  function stageTrack(status) {
    const idx = STAGES.indexOf(status);
    return h("div", { class: "stage-track", title: fmt.words(status) }, STAGES.map((st, i) => h("span", { class: `seg ${i <= idx ? "on" : ""} ${i === idx ? "cur" : ""}` })), h("span", { class: "stage-name" }, fmt.words(status)));
  }
  function approvalPill(text) {
    const kind = /^Approved/.test(text) ? "pos" : /Pending/.test(text) ? "warn" : "";
    return pill(text, `status nocap ${kind}`);
  }
  function experimentDialog(e) {
    dialog({ title: e.kind, drawer: true, body: h("div", { class: "stack" },
      h("div", { class: "chip-row" }, statusPill(e.status), verdictPill(e.verdict), pill("Simulated", "demo-tag")),
      kv([["Strategy", h("a", { class: "link", href: `#/lab/${e.strategy_id}` }, e.strategy)], ["Run ID", h("span", { class: "mono" }, e.id)], ["Dataset", h("span", { class: "mono" }, e.dataset)], ["Created", fmt.dateTime(e.created_at)], ["Duration", fmt.duration(e.duration_s)], ["Independent events", fmt.num(e.events)], ["Walk-forward folds", String(e.folds)], ["Brier score", e.brier === null ? "—" : fmt.num(e.brier, 4)], ["Log loss", e.log_loss === null ? "—" : fmt.num(e.log_loss, 4)]]),
      h("h4", { class: "section-label" }, "Evidence"),
      h("ul", { class: "evidence-list" }, ["Typed specification (JSON)", "Dataset manifest + receipt hashes", "Fold boundaries & holdout exclusion", "Validation predictions", "Simulated execution scenarios"].map((t) => h("li", icon("file", 14), h("span", t), h("span", { class: "muted mono" }, "demo · not downloadable")))),
      e.status === "failed" ? callout("Worker exited before review: feature build refused a forecast vintage received after the decision time.", "error") : null) });
  }

  function strategyDetail(root, id, ctx) {
    if (ET.mode() !== "demo") return strategyReal(root, id, ctx);
    const d = ET.demo();
    const st = d.strategies.find((s) => s.id === id);
    if (!st) { root.append(ET.pageHeader("Strategy not found"), card({}, emptyState({ title: `No strategy ${id}`, action: link("Back to Strategy Lab", "#/lab") }))); return; }
    const exps = d.experiments.filter((e) => e.strategy_id === id);
    const promote = button("Request promotion", { variant: "ghost", disabled: true, title: "Promotion requires a recorded human approval outside the website" }, "flag");
    const analytics = h("a", { class: "btn primary", href: `#/analytics?strategy=${st.id}` }, icon("analytics", 15), h("span", "Open analytics"));
    root.append(h("a", { class: "back", href: "#/lab" }, icon("chevronLeft", 14), "Strategy Lab"));
    root.append(h("header", { class: "page-head" }, h("div", { class: "page-titles" }, h("div", { class: "eyebrow-row" }, pill(st.family, "chip"), approvalPill(st.approval)), h("h1", st.name), h("p", { class: "page-sub" }, st.hypothesis)), h("div", { class: "page-actions" }, ET.sourceChip(), promote, analytics)));
    root.append(card({ title: "Lifecycle" }, h("ol", { class: "lifecycle" }, STAGES.map((stage, i) => h("li", { class: `life ${i < STAGES.indexOf(st.status) ? "done" : i === STAGES.indexOf(st.status) ? "current" : ""}` }, h("span", { class: "life-dot" }, i < STAGES.indexOf(st.status) ? icon("check", 12) : String(i + 1)), h("span", { class: "life-label" }, fmt.words(stage))))), h("p", { class: "hint" }, "Advancing beyond paper (live_small, live) requires a human approval recorded before the transition. The website cannot grant it.")));
    if (st.metrics) {
      const m = st.metrics;
      root.append(h("div", { class: "kpi-strip" },
        kpi({ label: "Total return", value: fmt.pct(m.total_return, 1, true), kind: m.total_return >= 0 ? "pos" : "neg", sub: "240-day backtest", iconName: "up" }),
        kpi({ label: "Sharpe", value: fmt.num(m.sharpe, 2), sub: "annualized", iconName: "analytics" }),
        kpi({ label: "Max drawdown", value: fmt.pct(m.max_drawdown, 1), kind: "neg", iconName: "down" }),
        kpi({ label: "Win rate", value: fmt.pct(m.win_rate), sub: `${fmt.num(m.trades)} trades`, iconName: "check" }),
        kpi({ label: "Brier", value: fmt.num(m.brier, 3), sub: `log loss ${fmt.num(m.log_loss, 3)}`, iconName: "target" })));
    }
    root.append(h("div", { class: "grid g-2-1" },
      h("div", { class: "stack" },
        st.equity.length ? card({ title: "Backtest equity", subtitle: "Walk-forward out-of-sample, after modeled fees", source: "demo", actions: link("Full analytics", `#/analytics?strategy=${st.id}`) }, lineChart([{ name: "Equity", values: st.equity, color: "var(--accent)", area: true }], { height: 220, yFormat: (v) => fmt.compactUsd(v), baseline: 10000, watermark: "SIMULATED" })) : card({ title: "Backtest" }, emptyState({ iconName: "analytics", title: "Not backtested yet", body: "This strategy has no completed walk-forward backtest." })),
        card({ title: "Experiments", flush: true }, exps.length ? dataTable({ columns: [
          { key: "kind", label: "Experiment" }, { key: "status", label: "Status", render: (e) => statusPill(e.status) }, { key: "verdict", label: "Verdict", render: (e) => verdictPill(e.verdict) },
          { key: "created_at", label: "Created", align: "num", render: (e) => fmt.dateTime(e.created_at) }, { key: "brier", label: "Brier", align: "num", render: (e) => (e.brier === null ? "—" : fmt.num(e.brier, 4)) },
        ], rows: exps, sortKey: "created_at", onRow: experimentDialog }) : emptyState({ iconName: "beaker", title: "No experiments yet" }))),
      h("div", { class: "stack" },
        card({ title: "Specification" }, kv([["Signal", h("code", st.signal)], ["Universe", st.universe], ["Position sizing", st.sizing], ["Exit", "Hold to settlement"], ["Risk overrides", "none (enforced by type)"], ["Created", fmt.date(st.created_at)]])),
        card({ title: "Assumptions" }, h("ul", { class: "check-list" }, st.assumptions.map((a) => h("li", icon("check", 13), h("span", a))))),
        card({ title: "Evidence links" }, h("ul", { class: "evidence-list" }, ["Specification hash", "Dataset manifest", "Model artifacts", "Fee evidence version"].map((t, i) => h("li", icon("file", 14), h("span", t), h("span", { class: "mono muted" }, `sha256:${(st.id.length * 7919 * (i + 3)).toString(16).padStart(8, "0")}…`))))))));
  }

  async function labReal(root, ctx) {
    const host = h("div", { class: "stack" }, skeleton(5));
    root.append(host);
    const jobs = await ET.api("/api/jobs").catch((error) => ({ error }));
    if (!ctx.isCurrent()) return;
    if (jobs.error) { host.replaceChildren(errorState(jobs.error.message, () => ET.route())); return; }
    const completed = jobs.filter((j) => j.status === "completed").slice(0, 12);
    const details = await Promise.all(completed.map((j) => ET.api(`/api/jobs/${j.id}`).catch(() => null)));
    if (!ctx.isCurrent()) return;
    const proposals = details.filter(Boolean).flatMap((job) => (job.result?.proposals || []).map((p) => ({ job, p })));
    const parts = [h("div", { class: "kpi-strip" },
      kpi({ label: "Research runs", value: String(jobs.length), sub: `${completed.length} completed`, iconName: "beaker" }),
      kpi({ label: "Typed candidates", value: String(proposals.filter((x) => x.p.spec).length), sub: "from recent completed runs", iconName: "lab" }),
      kpi({ label: "Non-executable", value: String(proposals.filter((x) => !x.p.spec).length), sub: "proposals with reasons", iconName: "alert" }),
      kpi({ label: "Failed / cancelled", value: String(jobs.filter((j) => ["failed", "cancelled", "interrupted"].includes(j.status)).length), iconName: "x" }))];
    const key = ctx.query.get("tab") || "experiments";
    const panel = h("div");
    const tabBar = tabs([{ key: "experiments", label: "Research runs", count: jobs.length }, { key: "strategies", label: "Candidates", count: proposals.length }, { key: "models", label: "Model comparison" }], key, render);
    function render(k) {
      if (k === "experiments") {
        panel.replaceChildren(card({ title: "Research runs", subtitle: "Durable queue · open a run to inspect its review, probabilities and lineage", flush: jobs.length > 0, source: "real" }, jobs.length ? dataTable({
          columns: [
            { key: "idea", label: "Idea", sort: (j) => j.request.idea, render: (j) => h("div", { class: "cell-market" }, h("span", { class: "cell-title" }, j.request.idea), h("span", { class: "cell-sub" }, `${j.request.family} · ${fmt.words(j.request.mode)}`)) },
            { key: "id", label: "Run ID", render: (j) => h("span", { class: "mono muted" }, fmt.short(j.id, 12)) },
            { key: "status", label: "Status", render: (j) => statusPill(j.status) },
            { key: "detail", label: "Detail", render: (j) => h("span", { class: "muted clamp" }, j.detail || "—") },
            { key: "created_at", label: "Created", align: "num", render: (j) => fmt.dateTime(j.created_at) },
          ], rows: jobs, sortKey: "created_at", pageSize: 15, onRow: (j) => ET.openRun(j.id),
        }) : emptyState({ iconName: "beaker", title: "No research runs yet", body: "Use “New hypothesis” or the Research Workbench to start a run. Results and their evidence appear here.", action: h("a", { class: "btn primary sm", href: "#/workbench" }, "Open workbench") })));
      } else if (k === "strategies") {
        panel.replaceChildren(card({ title: "Candidates from completed runs", subtitle: "Typed specifications are executable in shadow; others list why they were refused", flush: proposals.length > 0, source: "real" }, proposals.length ? dataTable({
          columns: [
            { key: "name", label: "Candidate", sort: (x) => x.p.spec?.name || x.p.candidate_id, render: (x) => h("div", { class: "cell-market" }, h("span", { class: "cell-title" }, x.p.spec?.name || x.p.title || x.p.candidate_id || "Proposal"), h("span", { class: "cell-sub" }, x.job.request.idea)) },
            { key: "typed", label: "Specification", sort: (x) => (x.p.spec ? 1 : 0), render: (x) => (x.p.spec ? statusPill("typed") : statusPill("refused")) },
            { key: "kind", label: "Data", render: (x) => statusPill(x.job.result?.data_kind || "—") },
            { key: "created", label: "Run created", align: "num", sort: (x) => x.job.created_at, render: (x) => fmt.dateTime(x.job.created_at) },
          ], rows: proposals, sortKey: "created", onRow: (x) => ET.openRun(x.job.id),
        }) : emptyState({ iconName: "lab", title: "No candidates yet", body: "Completed research runs list their typed hypotheses and refusals here." })));
      } else {
        panel.replaceChildren(card({ title: "Model comparison" }, unavailable("No authentic model comparison is available", "Model metrics require enough independent real events to pass the evidence gates. Current authentic evidence is insufficient; synthetic runs prove software behavior only. Per-run forecast metrics are in each run's review.")));
      }
    }
    render(key);
    parts.push(tabBar.el, panel);
    host.replaceChildren(...parts);
  }
  function strategyReal(root, id, ctx) {
    void ctx;
    root.append(ET.pageHeader("Strategy detail"), card({}, unavailable("Strategy pages are part of Demo Mode", `Real candidates are reviewed inside their research run. Open the run in the Research Workbench to inspect “${id}”.`, link("Back to Strategy Lab", "#/lab"))));
  }

  // ========================================================= ANALYTICS
  ET.views.analytics = async (root, ctx) => {
    if (ET.mode() !== "demo") return analyticsReal(root, ctx);
    const d = ET.demo();
    const tested = d.strategies.filter((s) => s.metrics);
    let st = tested.find((s) => s.id === ctx.query.get("strategy")) || tested[0];
    const select = h("select", { class: "input select-inline", "aria-label": "Strategy" }, tested.map((s) => h("option", { value: s.id, selected: s.id === st.id }, s.name)));
    select.addEventListener("change", () => ET.go(`#/analytics?strategy=${select.value}`));
    const exportBtn = button("Export", { variant: "ghost", title: "Downloads are available for real runs in the workbench" }, "download");
    exportBtn.addEventListener("click", () => toast("Demo data is not exportable. Real run reports download from the workbench.", "info"));
    root.append(ET.pageHeader("Backtesting & Analytics", "Walk-forward performance, risk, calibration, cost sensitivity and data sufficiency.", [select, exportBtn]));
    const m = st.metrics;
    root.append(h("div", { class: "kpi-grid" },
      kpi({ label: "Total return", value: fmt.pct(m.total_return, 1, true), kind: m.total_return >= 0 ? "pos" : "neg", iconName: "up", sub: "out-of-sample" }),
      kpi({ label: "Sharpe ratio", value: fmt.num(m.sharpe, 2), iconName: "analytics", sub: "annualized, daily" }),
      kpi({ label: "Max drawdown", value: fmt.pct(m.max_drawdown, 1), kind: "neg", iconName: "down", sub: "peak to trough" }),
      kpi({ label: "Win rate", value: fmt.pct(m.win_rate, 1), iconName: "target", sub: `profit factor ${fmt.num(m.profit_factor, 2)}` })));
    const panel = h("div");
    const tabBar = tabs([{ key: "performance", label: "Performance" }, { key: "risk", label: "Risk & drawdown" }, { key: "calibration", label: "Calibration" }, { key: "costs", label: "Fees & slippage" }, { key: "walkforward", label: "Walk-forward & data" }], ctx.query.get("tab") || "performance", render, "pills");
    function render(k) {
      if (k === "performance") {
        let span = "ALL";
        const host = h("div");
        const draw = () => { const n = { "30D": 30, "90D": 90, ALL: st.equity.length }[span]; host.replaceChildren(lineChart([{ name: st.name, values: st.equity.slice(-n), color: "var(--accent)", area: true }, { name: "Market-implied baseline", values: st.equity.slice(-n).map((p, i, arr) => ({ x: p.x, y: arr[0].y * (1 + (i / arr.length) * 0.012) })), color: "var(--muted-line)", dash: true }], { height: 280, yFormat: (v) => fmt.compactUsd(v), watermark: "SIMULATED" })); };
        draw();
        const pnls = st.trade_pnls;
        const wins = pnls.filter((x) => x > 0); const losses = pnls.filter((x) => x <= 0);
        panel.replaceChildren(h("div", { class: "grid g-2-1" },
          card({ title: "Equity curve", subtitle: "$10,000 simulated bankroll · fees modeled at each decision", source: "demo", actions: segmented(["30D", "90D", "ALL"].map((x) => ({ key: x, label: x })), span, (x) => { span = x; draw(); }) }, host),
          card({ title: "Trade statistics" }, h("div", { class: "stat-pair" }, h("div", h("span", { class: "stat-label" }, "Total trades"), h("strong", { class: "stat-big" }, fmt.num(m.trades))), h("div", h("span", { class: "stat-label" }, "Profit factor"), h("strong", { class: "stat-big" }, fmt.num(m.profit_factor, 2)))),
            kv([["Average win", h("span", { class: "num-pos" }, fmt.signedUsd(wins.reduce((a, b) => a + b, 0) / wins.length))], ["Average loss", h("span", { class: "num-neg" }, fmt.signedUsd(losses.reduce((a, b) => a + b, 0) / losses.length))], ["Win/loss ratio", `${fmt.num(Math.abs((wins.reduce((a, b) => a + b, 0) / wins.length) / (losses.reduce((a, b) => a + b, 0) / losses.length)), 2)} : 1`], ["Average gross edge", fmt.pct(m.avg_edge, 1)], ["Hold period", "to settlement"]]))),
          card({ title: "Monthly returns", source: "demo" }, barChart(monthly(st.equity), { height: 200, yFormat: (v) => fmt.pct(v, 1, true), watermark: "SIMULATED" })));
      } else if (k === "risk") {
        const dd = ET.demoTools.drawdown(st.equity);
        panel.replaceChildren(h("div", { class: "stack" },
          card({ title: "Drawdown", subtitle: "Percent below running equity peak", source: "demo" }, lineChart([{ name: "Drawdown", values: dd, color: "var(--neg)", area: true, areaBase: 0 }], { height: 220, yFormat: (v) => fmt.pct(v, 1), watermark: "SIMULATED", yMax: 0 })),
          h("div", { class: "grid g-1-1" },
            card({ title: "Daily return distribution" }, barChart(histogram(st.returns, 21, (v) => fmt.pct(v, 1)), { height: 220, yFormat: (v) => fmt.num(v), signed: false, xLabelEvery: 4, watermark: "SIMULATED" })),
            card({ title: "Trade P&L distribution" }, barChart(histogram(st.trade_pnls, 21, (v) => `$${Math.round(v)}`, true), { height: 220, yFormat: (v) => fmt.num(v), signed: false, xLabelEvery: 4, watermark: "SIMULATED" })))));
      } else if (k === "calibration") {
        const model = d.models[3];
        panel.replaceChildren(h("div", { class: "grid g-1-1" },
          card({ title: "Reliability", subtitle: "Calibrated model vs market-implied baseline", source: "demo" }, calibrationChart([{ name: "Calibrated ensemble", bins: model.bins }, { name: "Market-implied", bins: d.models[0].bins, color: "var(--muted-line)" }], { watermark: "SIMULATED" })),
          card({ title: "Predictive metrics", subtitle: "Validation folds only; final holdout remains closed" }, kv([["Brier score", fmt.num(m.brier, 4)], ["Market Brier", fmt.num(d.models[0].brier, 4)], ["Log loss", fmt.num(m.log_loss, 4)], ["Expected calibration error", fmt.num(model.ece, 3)], ["AUC", fmt.num(model.auc, 2)], ["Validation events", fmt.num(model.events)]]),
            barChart(model.bins.map((b) => ({ label: `${Math.round(b.p * 100)}%`, value: b.n, series: "Events" })), { height: 140, signed: false, yFormat: (v) => fmt.num(v) }), h("p", { class: "hint" }, "Prediction count per probability bin."))));
      } else if (k === "costs") {
        const g = ET.demoTools.feeGrid(st);
        panel.replaceChildren(h("div", { class: "grid g-2-1" },
          card({ title: "Fee & slippage sensitivity", subtitle: "Total return under fee multipliers (rows) and extra slippage per contract (columns)", source: "demo" }, heatGrid({ rows: g.rows, cols: g.cols, values: g.values, rowTitle: "Fees", colTitle: "Slippage" })),
          card({ title: "Break-even" }, kv([["Base-case return", fmt.pct(g.values[2][0], 1, true)], ["Return at 2× fees + 4¢", h("span", { class: `num-${ET.tone(g.values[4][4])}` }, fmt.pct(g.values[4][4], 1, true))], ["Break-even slippage at 1× fees", `${Math.max(0, (g.values[2][0] / 0.028)).toFixed(1)}¢`]]), callout("Fee coefficients come from reviewed, point-in-time fee documents. A decision without applicable certified fee evidence is refused, not costed at zero.", "info"))));
      } else {
        const folds = ET.demoTools.walkForward(st);
        const suff = ET.demoTools.sufficiency(st);
        panel.replaceChildren(h("div", { class: "stack" },
          h("div", { class: "grid g-1-1" },
            card({ title: "Walk-forward folds", subtitle: "Expanding window · 1-month test periods", flush: true }, dataTable({ columns: [
              { key: "fold", label: "Fold", align: "num" }, { key: "train", label: "Train" }, { key: "test", label: "Test" }, { key: "events", label: "Events", align: "num" },
              { key: "brier", label: "Brier", align: "num", render: (f) => fmt.num(f.brier, 3) }, { key: "market_brier", label: "Market", align: "num", render: (f) => fmt.num(f.market_brier, 3) },
              { key: "return", label: "Return", align: "num", render: (f) => h("span", { class: `num-${ET.tone(f.return)}` }, fmt.pct(f.return, 1, true)) },
            ], rows: folds, sortKey: "fold", sortDir: "asc", dense: true })),
            card({ title: "Out-of-sample return by fold", source: "demo" }, barChart(folds.map((f) => ({ label: f.test, value: f.return })), { height: 230, yFormat: (v) => fmt.pct(v, 1, true), watermark: "SIMULATED" }))),
          card({ title: "Data sufficiency", subtitle: "Independent settled events per month vs. the 100-event modeling threshold", source: "demo" }, barChart(suff.map((x) => ({ label: x.label, value: x.value, tone: x.value >= x.required ? "pos" : "warn", note: x.value >= x.required ? "Meets threshold" : `${x.required - x.value} events short` })), { height: 200, signed: false, yFormat: (v) => fmt.num(v), watermark: "SIMULATED" }),
            h("div", { class: "legend" }, h("span", { class: "legend-item" }, h("span", { class: "swatch pos" }), "Meets threshold"), h("span", { class: "legend-item" }, h("span", { class: "swatch warn" }), "Insufficient")))));
      }
    }
    render(ctx.query.get("tab") || "performance");
    root.append(tabBar.el, panel);
  };
  function monthly(series) {
    const out = []; let start = series[0];
    series.forEach((p, i) => {
      const next = series[i + 1];
      if (!next || new Date(next.x).getUTCMonth() !== new Date(p.x).getUTCMonth()) { out.push({ label: new Date(p.x).toLocaleDateString("en-US", { month: "short", timeZone: "UTC" }), value: p.y / start.y - 1 }); start = p; }
    });
    return out;
  }
  function histogram(values, bins, label, signed = false) {
    const min = Math.min(...values); const max = Math.max(...values); const w = (max - min) / bins || 1;
    const counts = Array.from({ length: bins }, (_, i) => ({ lo: min + i * w, n: 0 }));
    values.forEach((v) => { counts[Math.min(bins - 1, Math.floor((v - min) / w))].n += 1; });
    return counts.map((c) => ({ label: label(c.lo + w / 2), value: c.n, tone: signed || true ? (c.lo + w / 2 >= 0 ? "pos" : "neg") : "accent", series: "Count" }));
  }

  async function analyticsReal(root, ctx) {
    root.append(ET.pageHeader("Backtesting & Analytics", "Walk-forward performance, risk, calibration, cost sensitivity and data sufficiency."));
    const host = h("div", { class: "stack" }, skeleton(5));
    root.append(host);
    const r = await ET.apiAll({ jobs: "/api/jobs", datasets: "/api/weather/datasets" });
    if (!ctx.isCurrent()) return;
    const jobs = r.jobs.ok ? r.jobs.data : [];
    const datasets = r.datasets.ok ? r.datasets.data : [];
    const parts = [card({ title: "Backtest performance", source: "real" }, unavailable("No authentic backtest has passed the evidence gates", "Equity curves, drawdowns, trade distributions and fee sensitivity are shown only for real runs with sufficient independent events, certified fees and executable depth. This workspace has none yet, so no performance figures are displayed. Synthetic runs verify software only and are not shown as results.", h("div", { class: "row-actions" }, h("a", { class: "btn primary sm", href: "#/workbench" }, "Open workbench"), button("Preview in Demo Mode", { variant: "ghost sm", onclick: () => ET.setMode("demo") }, "eye"))))];
    parts.push(card({ title: "Data sufficiency", subtitle: "Frozen weather datasets and their modeling readiness", flush: datasets.length > 0, source: "real" }, datasets.length ? dataTable({ columns: [
      { key: "dataset_id", label: "Dataset", render: (x) => h("span", { class: "mono" }, fmt.short(x.dataset_id?.replace("sha256:", ""), 16)) },
      { key: "status", label: "Readiness", sort: (x) => x.readiness?.status, render: (x) => statusPill(x.readiness?.status || "unknown") },
      { key: "events", label: "Independent events", align: "num", sort: (x) => x.readiness?.independent_events ?? 0, render: (x) => fmt.num(x.readiness?.independent_events) },
      { key: "captures", label: "Captures", align: "num", sort: (x) => x.capture_count ?? 0, render: (x) => fmt.num(x.capture_count) },
      { key: "observations", label: "Observations", align: "num", sort: (x) => x.observation_count ?? 0, render: (x) => fmt.num(x.observation_count) },
    ], rows: datasets, sortKey: "events" }) : r.datasets.ok ? emptyState({ iconName: "database", title: "No frozen datasets", body: "Freeze retained weather inputs in the Research Workbench to see evidence shortages here." }) : errorState(r.datasets.error.message)));
    const completed = jobs.filter((j) => j.status === "completed");
    parts.push(card({ title: "Completed research reviews", subtitle: "Each review carries its own forecast metrics, refusals and simulated execution scenarios", flush: completed.length > 0 }, completed.length ? dataTable({ columns: [
      { key: "idea", label: "Idea", sort: (j) => j.request.idea, render: (j) => h("span", { class: "cell-title" }, j.request.idea) },
      { key: "mode", label: "Data", sort: (j) => j.request.mode, render: (j) => statusPill(j.request.mode === "synthetic" ? "synthetic" : j.request.mode) },
      { key: "created_at", label: "Created", align: "num", render: (j) => fmt.dateTime(j.created_at) },
    ], rows: completed, sortKey: "created_at", onRow: (j) => ET.openRun(j.id), pageSize: 10 }) : emptyState({ iconName: "beaker", title: "No completed reviews" })));
    host.replaceChildren(...parts);
  }
})();
