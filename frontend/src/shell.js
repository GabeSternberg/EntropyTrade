"use strict";
// Application shell: data-source mode, guarded API access, routing, navigation and the
// command palette. Demo data is reachable only through ET.demo(), which refuses outside
// Demo Mode; API reads and explicit writes both refuse dispatch outside Real Mode.
(function () {
  const ET = window.ET;
  const { h, icon, logo, fmt, pill, button, segmented, dialog, toast } = ET;
  const MODE_KEY = "entropytrade.data-mode";
  const PREFS_KEY = "entropytrade.preferences";

  // ------------------------------------------------------------ data mode
  function readStorage(key) { try { return window.localStorage.getItem(key); } catch { return null; } }
  function writeStorage(key, value) { try { window.localStorage.setItem(key, value); } catch { /* private window */ } }
  let mode = readStorage(MODE_KEY) === "demo" ? "demo" : "real";
  ET.mode = () => mode;
  ET.setMode = (next) => {
    if (next !== "demo" && next !== "real") throw new Error("unknown data mode");
    if (next === mode) return;
    mode = next;
    writeStorage(MODE_KEY, mode);
    cache.clear();
    applyMode();
    toast(mode === "demo" ? "Demo Mode: showing fictional sample data" : "Real Mode: showing this workspace's data", mode === "demo" ? "info" : "ok");
    route();
  };
  ET.demo = () => {
    if (mode !== "demo") throw new Error("Demo data is only available in Demo Mode");
    return ET.demoData;
  };
  ET.prefs = (() => {
    let value = {};
    try { value = JSON.parse(readStorage(PREFS_KEY) || "{}") || {}; } catch { value = {}; }
    return {
      get: (key, fallback) => (key in value ? value[key] : fallback),
      set: (key, next) => { value = { ...value, [key]: next }; writeStorage(PREFS_KEY, JSON.stringify(value)); applyPrefs(); },
    };
  })();

  // Read-only API: GET only, same-origin /api/ paths only, short-lived cache.
  const cache = new Map();
  ET.api = async (path, { fresh = false } = {}) => {
    if (typeof path !== "string" || !path.startsWith("/api/")) throw new Error("ET.api reads same-origin /api/ resources only");
    if (mode !== "real") throw new Error("Real API reads are disabled in Demo Mode");
    const hit = cache.get(path);
    if (!fresh && hit && Date.now() - hit.at < 4000) return hit.promise;
    const promise = fetch(path, { method: "GET", credentials: "same-origin", headers: { Accept: "application/json" } }).then(async (response) => {
      const body = await response.json().catch(() => ({}));
      if (!response.ok) throw Object.assign(new Error(body.error || `Request failed (${response.status})`), { status: response.status });
      return body;
    });
    cache.set(path, { at: Date.now(), promise });
    promise.catch(() => cache.delete(path));
    return promise;
  };
  // One write boundary for modern views. Check the current mode at dispatch time so a
  // handler rendered earlier cannot write after navigation switches to Demo Mode.
  ET.mutate = async (path, body, csrf) => {
    if (typeof path !== "string" || !path.startsWith("/api/")) throw new Error("ET.mutate writes same-origin /api/ resources only");
    if (mode !== "real") throw new Error("Real API writes are disabled in Demo Mode");
    if (typeof csrf !== "string" || !csrf.trim()) throw new Error("A current CSRF token is required");
    const response = await fetch(path, {
      method: "POST", credentials: "same-origin",
      headers: { "Content-Type": "application/json", "X-EntropyTrade-CSRF": csrf },
      body: JSON.stringify(body ?? {}),
    });
    const result = await response.json().catch(() => ({}));
    if (!response.ok) throw Object.assign(new Error(result.error || `Request failed (${response.status})`), { status: response.status });
    cache.clear();
    return result;
  };
  // Settle several reads independently so one unavailable resource does not blank a page.
  ET.apiAll = async (paths) => {
    const entries = await Promise.all(Object.entries(paths).map(async ([key, path]) => {
      try { return [key, { ok: true, data: await ET.api(path) }]; } catch (error) { return [key, { ok: false, error }]; }
    }));
    return Object.fromEntries(entries);
  };

  // ------------------------------------------------------------ navigation
  const NAV = [
    { group: "Workspace", items: [
      { key: "overview", label: "Overview", icon: "overview" },
      { key: "markets", label: "Market Explorer", icon: "markets" },
      { key: "lab", label: "Strategy Lab", icon: "lab" },
      { key: "analytics", label: "Backtesting", icon: "analytics" },
      { key: "paper", label: "Paper Trading", icon: "paper" },
    ] },
    { group: "Research", items: [
      { key: "research", label: "Autonomous Research", icon: "sparkles" },
      { key: "workbench", label: "Research Workbench", icon: "workbench" },
      { key: "cis1990", label: "CIS 1990 Research Demo", icon: "beaker" },
    ] },
    { group: "System", items: [
      { key: "ops", label: "Data & Operations", icon: "ops" },
      { key: "settings", label: "Settings", icon: "settings" },
    ] },
  ];
  const TITLES = Object.fromEntries(NAV.flatMap((g) => g.items.map((i) => [i.key, i.label])));
  ET.views = ET.views || {};

  const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
  const HASH = /^sha256:[0-9a-f]{64}$/;
  const ROUTE_QUERIES = {
    research: { new: (v) => v === "1", tab: (v) => ["hypotheses", "requirements", "sources", "acquisitions", "features", "experiments", "forward", "paper", "events"].includes(v), experiment: (v) => HASH.test(v) },
    paper: { tab: (v) => ["account", "monitoring", "readiness", "evidence"].includes(v), proposal: (v) => HASH.test(v) },
    ops: { tab: (v) => v === "alerts", monitor: (v) => UUID.test(v), alert: (v) => /^[a-zA-Z0-9_:-]{1,128}$/.test(v) },
    workbench: { job: (v) => UUID.test(v) },
    lab: { tab: (v) => ["strategies", "experiments", "models"].includes(v) },
    analytics: { tab: (v) => ["performance", "risk", "calibration", "costs", "walkforward"].includes(v), strategy: (v) => /^[a-zA-Z0-9_-]{1,128}$/.test(v) },
  };
  function parse(hash = window.location.hash) {
    const raw = (hash || "#/overview").replace(/^#\/?/, "");
    const split = raw.indexOf("?");
    const pathPart = split < 0 ? raw : raw.slice(0, split);
    const supplied = new URLSearchParams(split < 0 ? "" : raw.slice(split + 1));
    let parts;
    try { parts = pathPart.split("/").filter(Boolean).map(decodeURIComponent); }
    catch { return { name: "overview", params: [], query: new URLSearchParams(), routeError: "Invalid route encoding" }; }
    const name = parts[0] || "overview", query = new URLSearchParams();
    let routeError = null;
    for (const [key, value] of supplied) {
      const validate = ROUTE_QUERIES[name]?.[key];
      if (!validate) continue;
      if (supplied.getAll(key).length !== 1 || !validate(value)) routeError = `Invalid ${key} selection in this link`;
      else query.set(key, value);
    }
    if (["research", "paper", "cis1990"].includes(name) && parts.length > 2) routeError = "Invalid persisted record path in this link";
    if (name === "research" && query.has("experiment") && !parts[1] || name === "paper" && query.has("proposal") && !parts[1]) routeError = "This evidence selection requires its parent record identifier";
    if (["research", "paper", "cis1990"].includes(name) && parts[1] && !UUID.test(parts[1]) && mode === "real") routeError = "Invalid persisted record identifier in this link";
    return { name, params: parts.slice(1), query, routeError };
  }
  ET.parseRoute = parse;
  ET.routeLink = (name, id, values = {}) => {
    const query = new URLSearchParams();
    Object.entries(values).forEach(([key, value]) => { if (value != null && value !== "") query.set(key, value); });
    return `#/${name}${id ? "/" + encodeURIComponent(id) : ""}${query.size ? "?" + query.toString() : ""}`;
  };
  // Tabs update the URL without tearing down their active selection/loading state.
  // Browser back/forward is rendered through popstate/hashchange below.
  ET.updateQuery = (values, { replace = false } = {}) => {
    const current = parse();
    Object.entries(values).forEach(([key, value]) => { if (value == null || value === "") current.query.delete(key); else current.query.set(key, value); });
    const href = ET.routeLink(current.name, current.params[0], Object.fromEntries(current.query));
    if (window.location.hash !== href) {
      const method = replace ? "replaceState" : "pushState";
      if (window.history?.[method]) window.history[method](null, "", href);
      else if (!replace) window.location.hash = href;
    }
  };
  ET.go = (hash) => { if (window.location.hash === hash) return route(); window.location.hash = hash; };
  ET.workbenchActive = () => mode === "real" && parse().name === "workbench" && document.getElementById("workbench-view")?.hidden === false;
  ET.activateWorkbench = async () => {
    if (mode !== "real") throw new Error("The research workbench is disabled in Demo Mode");
    if (parse().name !== "workbench") window.location.hash = "#/workbench";
    await route();
    if (!ET.workbenchActive()) throw new Error("The research workbench is no longer active");
    if (!ET.legacyWorkbench) throw new Error("The research workbench failed to load");
    return ET.legacyWorkbench;
  };
  ET.openRun = async (id) => { const legacy = await ET.activateWorkbench(); return legacy.selectJob(id); };
  ET.selectMonitor = async (id) => { const legacy = await ET.activateWorkbench(); return legacy.selectMonitor(id, true); };

  let renderToken = 0;
  let workbenchRoute = null;
  function route() {
    const selected = parse();
    const key = `${mode}|${window.location.hash}`;
    if (selected.name === "workbench") {
      if (workbenchRoute?.key === key) return workbenchRoute.promise;
      const promise = renderRoute();
      workbenchRoute = { key, promise };
      return promise;
    }
    workbenchRoute = null;
    return renderRoute();
  }
  async function renderRoute() {
    const { name, params, query, routeError } = parse();
    const known = name in TITLES;
    const key = known ? name : "overview";
    document.querySelectorAll(".nav-item").forEach((a) => a.setAttribute("aria-current", a.dataset.key === key ? "page" : "false"));
    document.title = `${TITLES[key]} · EntropyTrade`;
    const crumb = document.getElementById("crumb");
    if (crumb) crumb.replaceChildren(h("span", { class: "crumb-root" }, "EntropyTrade"), icon("chevronRight", 13), h("span", { class: "crumb-page" }, TITLES[key]));
    const view = document.getElementById("view");
    const workbench = document.getElementById("workbench-view");
    document.body.classList.remove("nav-open");
    const isWorkbench = key === "workbench";
    workbench.hidden = !isWorkbench;
    view.hidden = isWorkbench;
    if (!isWorkbench || mode !== "real") ET.legacyWorkbench?.deactivate();
    if (isWorkbench) {
      const token = ++renderToken; view.replaceChildren(); window.scrollTo(0, 0);
      if (mode !== "real") {
        workbench.hidden = true; view.hidden = false;
        view.replaceChildren(ET.unavailable("Research workbench disabled in Demo Mode", "Switch to Real Mode to inspect or run persisted research. Demo Mode never sends workbench requests."));
        return;
      }
      if (routeError) { workbench.hidden = true; view.hidden = false; view.replaceChildren(ET.errorState(routeError)); ET.legacyWorkbench?.deactivate(); return; }
      try {
        await ET.legacyWorkbench?.activate();
        if (token === renderToken && ET.workbenchActive() && query.get("job")) await ET.legacyWorkbench?.selectJob(query.get("job"));
      } catch (error) { if (ET.workbenchActive()) toast(error.message, "error"); }
      return;
    }
    const token = ++renderToken;
    const target = h("div", { class: "view-inner", "data-view": key });
    view.replaceChildren(target);
    window.scrollTo(0, 0);
    if (routeError) { target.append(ET.unavailable("This link cannot select a record", routeError)); return; }
    const renderer = ET.views[key];
    if (!renderer) { target.append(ET.emptyState({ title: "This section is unavailable", body: "The view module failed to load." })); return; }
    Promise.resolve(renderer(target, { params, query, isCurrent: () => token === renderToken })).catch((error) => {
      if (token !== renderToken) return;
      target.replaceChildren(ET.errorState(error.message, () => route()));
    });
  }
  ET.route = route;

  // Shared page header with an unmistakable data-source indicator.
  ET.pageHeader = (title, subtitle, actions) => h("header", { class: "page-head" },
    h("div", { class: "page-titles" }, h("h1", title), subtitle ? h("p", { class: "page-sub" }, subtitle) : null),
    h("div", { class: "page-actions" }, ET.sourceChip(), actions || null));
  ET.sourceChip = () => mode === "demo"
    ? h("span", { class: "source-chip demo", title: "Fictional sample data generated in this browser" }, h("span", { class: "dot demo" }), "Demo data · simulated")
    : h("span", { class: "source-chip real", title: "Persisted workspace records; inspect each record's provenance" }, h("span", { class: "dot pos" }), "Workspace data · persisted");

  const SUMMARY_LABELS = { research_jobs: "Autonomous research jobs", experiments: "Persistent experiments", legacy_jobs: "Legacy research runs", course_jobs: "CIS course runs", monitors: "Shadow monitors", paper_accounts: "Paper accounts", alerts: "Open alerts", readiness: "Readiness records" };
  ET.summaryKpis = (summary, keys) => h("div", { class: "kpi-strip" }, keys.map((key) => {
    const component = summary?.components?.[key];
    const counts = component?.available ? component.counts : null;
    const node = ET.kpi({ label: SUMMARY_LABELS[key], value: counts ? fmt.num(key === "alerts" ? counts.unresolved : counts.total) : "—", sub: !counts ? "unavailable" : component.initialized ? "stored metadata · full count" : "not started", iconName: key === "experiments" ? "analytics" : key === "paper_accounts" ? "paper" : "database" });
    node.setAttribute("data-summary-component", key);
    return node;
  }));
  ET.summaryRecords = (summary, key) => {
    const component = summary?.components?.[key];
    if (!component?.available || !component.counts) return ET.unavailable("Recorded metadata unavailable", "This component could not be read. Its count and recent references are unknown.");
    const counts = component.counts;
    const groups = ["by_status", "by_data_kind", "by_source_kind", "by_result_status", "by_validation_status", "by_backtest_status"].filter((field) => counts[field] && Object.keys(counts[field]).length);
    const breakdown = groups.length ? h("div", { class: "summary-breakdown" }, groups.map((field) => h("p", { class: "hint" }, `${fmt.words(field.replace(/^by_/, ""))}: `, Object.entries(counts[field]).sort(([a], [b]) => a.localeCompare(b)).map(([value, count]) => `${value}: ${count}`).join(" · ")))) : null;
    const recent = component.recent || [];
    const evidenceCounts = key === "experiments" ? h("p", { class: "hint" }, [
      ["with_recorded_result", "results"], ["with_recorded_validation", "validations"], ["with_recorded_model", "model artifacts"], ["with_recorded_backtest", "backtests"],
    ].filter(([field]) => counts[field] != null).map(([field, label]) => `${counts[field]} recorded ${label}`).join(" · ")) : null;
    return h("div", { class: "stack", "data-summary-records": key }, breakdown, evidenceCounts,
      key === "paper_accounts" && counts.monitors_without_account != null ? h("p", { class: "hint" }, `${counts.monitors_without_account} monitors have no stored account. An unstarted monitor is not an account.`) : null,
      recent.length ? h("ul", { class: "mini-list summary-record-list" }, recent.map((record) => {
        const id = record.experiment_id || record.proposal_id || record.alert_id || record.id || record.job_id || record.monitor_id;
        return h("li", h("div", { class: "mini-main" }, h("a", { class: "link mono summary-ref", href: record.href }, id),
          h("span", { class: "mini-sub" }, [record.status, record.kind, record.source_kind ? `source: ${record.source_kind}` : null, record.data_kind ? `data: ${record.data_kind}` : null, record.result_status ? `result: ${record.result_status}` : null, record.validation_status ? `validation: ${record.validation_status}` : null, record.backtest_status ? `backtest: ${record.backtest_status}` : null].filter(Boolean).join(" · "))),
          record.monitor_href ? h("a", { class: "link", href: record.monitor_href }, "Monitor evidence") : null);
      })) : ET.emptyState({ title: counts.total > 0 ? "No recent references available" : component.initialized ? "No records stored" : "Not started", body: counts.total > 0 ? "Stored records were counted, but no valid navigable references are available in this recent window." : "No recent references are recorded for this component." }),
      h("p", { class: "hint" }, `Showing at most ${summary?.recent_limit || 10} recent references. Counts include all stored records.`));
  };
  ET.summaryNotice = () => ET.callout("Counts and statuses describe stored metadata. A recorded result, validation, model or readiness review does not prove current scientific validity, paper eligibility or trading profitability. Open the exact evidence record to inspect its checks and refusals.", "info");

  // ------------------------------------------------------------ chrome
  function buildSidebar() {
    const side = document.getElementById("sidebar");
    const nav = h("nav", { class: "nav", "aria-label": "Primary" }, NAV.map((group) => h("div", { class: "nav-group" },
      h("p", { class: "nav-label" }, group.group),
      group.items.map((item) => h("a", { class: "nav-item", href: `#/${item.key}`, dataset: { key: item.key }, title: item.label },
        icon(item.icon, 17), h("span", { class: "nav-text" }, item.label), h("span", { class: "nav-badge", id: `nav-badge-${item.key}`, hidden: true }))))));
    const collapse = button("", { variant: "ghost icon sm collapse-btn", "aria-label": "Collapse sidebar", title: "Collapse sidebar" }, "sidebar");
    collapse.addEventListener("click", () => ET.prefs.set("collapsed", !ET.prefs.get("collapsed", false)));
    side.replaceChildren(
      h("div", { class: "brand-row" }, h("a", { class: "brand", href: "#/overview", "aria-label": "EntropyTrade overview" }, logo(24), h("span", { class: "brand-name" }, "EntropyTrade")), collapse),
      nav,
      h("div", { class: "side-foot" },
        h("div", { class: "env-card" },
          h("div", { class: "env-row" }, icon("lock", 14), h("span", "Execution disabled")),
          h("p", "Paper & shadow only. Real-money submission is not available from this website."),
          h("div", { class: "env-row muted" }, h("span", { class: "dot pos pulse" }), h("span", { id: "clock" }, "—"))))
    );
  }
  function buildTopbar() {
    const bar = document.getElementById("topbar");
    const menu = button("", { variant: "ghost icon menu-btn", "aria-label": "Open navigation" }, "menu");
    menu.addEventListener("click", () => document.body.classList.toggle("nav-open"));
    const search = h("button", { type: "button", class: "search-trigger", "aria-label": "Search (Command K)" }, icon("search", 15), h("span", "Search markets, strategies, pages…"), h("kbd", navigator.platform.includes("Mac") ? "⌘K" : "Ctrl K"));
    search.addEventListener("click", palette);
    const modeSwitch = segmented([{ key: "real", label: "Real" }, { key: "demo", label: "Demo" }], mode, (key) => ET.setMode(key), { class: "segmented mode-switch", "aria-label": "Data mode", id: "mode-switch" });
    const bell = h("a", { class: "btn ghost icon bell", href: "#/ops?tab=alerts", "aria-label": "Alerts", title: "Alerts" }, icon("bell", 17), h("span", { class: "bell-dot", id: "bell-dot", hidden: true }));
    const owner = button("Owner access", { variant: "ghost sm", id: "owner-access", onclick: () => ET.ownerAccess?.() }, "lock");
    const halt = button("Paper halt", { variant: "ghost sm", id: "global-halt", onclick: () => ET.controlAccess?.() }, "shield");
    bar.replaceChildren(menu, h("div", { class: "crumb", id: "crumb" }), search,
      h("div", { class: "top-actions" }, h("span", { class: "mode-label" }, "Data"), modeSwitch, owner, halt, bell,
        h("span", { class: "exec-pill", title: "No order endpoint exists on this server" }, icon("lock", 13), "Live trading off")));
  }
  function applyMode() {
    document.body.classList.toggle("mode-demo", mode === "demo");
    document.body.classList.toggle("mode-real", mode === "real");
    document.querySelectorAll("#mode-switch button").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.key === mode)));
    const banner = document.getElementById("mode-banner");
    if (mode === "demo") {
      document.querySelectorAll("dialog[data-owner-control]").forEach((modal) => modal.close());
      const exit = button("Switch to Real Mode", { variant: "sm banner-btn" });
      exit.addEventListener("click", () => ET.setMode("real"));
      banner.replaceChildren(h("div", { class: "banner-inner" }, icon("eye", 15), h("strong", "Demo Mode"),
        h("span", "Every figure shown is fictional sample data generated in your browser. It is not a market record or a research result, and it is never sent to research, evidence or trading systems."), exit));
      banner.hidden = false;
    } else banner.hidden = true;
    updateIndicators();
    updateSafety();
  }
  async function updateSafety() {
    const owner = document.getElementById("owner-access");
    const halt = document.getElementById("global-halt");
    if (!owner || !halt) return;
    owner.disabled = halt.disabled = mode !== "real";
    if (mode !== "real") { owner.textContent = "Owner access"; halt.textContent = "Paper halt · demo"; return; }
    const result = await ET.apiAll({ owner: "/api/owner", control: "/api/controls" });
    if (mode !== "real") return;
    owner.textContent = result.owner.ok && result.owner.data.authenticated ? "Owner signed in" : "Owner access";
    owner.title = result.owner.ok ? "Owner identity is required for readiness review and halt release" : "Owner status unavailable; open to retry";
    halt.textContent = result.control.ok ? (result.control.data.halted ? "Paper halt engaged" : "Paper halt") : "Paper halt · unavailable";
    halt.setAttribute("data-halted", result.control.ok ? String(result.control.data.halted) : "unknown");
  }
  ET.refreshSafety = updateSafety;
  function applyPrefs() {
    document.body.classList.toggle("collapsed", !!ET.prefs.get("collapsed", false));
    document.body.classList.toggle("density-compact", ET.prefs.get("density", "comfortable") === "compact");
  }
  async function updateIndicators() {
    const badge = document.getElementById("nav-badge-ops");
    const dotEl = document.getElementById("bell-dot");
    const requestedMode = mode;
    let count = null;
    if (mode === "demo") count = ET.demoData.quality_alerts.filter((a) => !a.resolved).length;
    else {
      try { const summary = await ET.api("/api/workspace/summary"); count = summary.components?.alerts?.counts?.unresolved ?? null; } catch { /* unavailable is not zero */ }
    }
    if (requestedMode !== mode) return;
    if (badge) { badge.hidden = count == null || count === 0; badge.textContent = count == null ? "—" : String(count); badge.title = count == null ? "Alert count unavailable" : "Recorded unresolved alerts"; }
    if (dotEl) dotEl.hidden = count == null || count === 0;
  }

  function tick() {
    const el = document.getElementById("clock");
    if (el) el.textContent = `${new Date().toISOString().slice(11, 19)} UTC · localhost`;
  }

  // ------------------------------------------------------------ command palette
  function palette() {
    if (document.querySelector("dialog.palette")) return;
    const input = h("input", { type: "search", class: "palette-input", placeholder: "Jump to a page, market or strategy…", "aria-label": "Search" });
    const results = h("div", { class: "palette-results", role: "listbox" });
    const entries = [
      { label: "New research", hint: "Persistent research objective", icon: "sparkles", href: "#/research?new=1" },
      { label: "Paper deployments", hint: "Accounts and evidence", icon: "paper", href: "#/paper" },
      { label: "Alerts", hint: "Operator review", icon: "bell", href: "#/ops?tab=alerts" },
      { label: "Readiness review", hint: "Select a paper deployment", icon: "shield", href: "#/paper?tab=readiness" },
      ...NAV.flatMap((g) => g.items.map((i) => ({ label: i.label, hint: ["workbench", "cis1990"].includes(i.key) ? "Legacy / course" : "Page", icon: i.icon, href: `#/${i.key}` }))),
    ];
    if (mode === "demo") {
      ET.demoData.markets.forEach((m) => entries.push({ label: m.title, hint: m.ticker, icon: "markets", href: `#/markets/${encodeURIComponent(m.ticker)}` }));
      ET.demoData.strategies.forEach((st) => entries.push({ label: st.name, hint: "Strategy", icon: "lab", href: `#/lab/${st.id}` }));
    }
    let active = 0; let shown = [];
    function draw() {
      const q = input.value.trim().toLowerCase();
      shown = entries.filter((e) => !q || e.label.toLowerCase().includes(q) || e.hint.toLowerCase().includes(q)).slice(0, 9);
      active = Math.min(active, Math.max(0, shown.length - 1));
      results.replaceChildren(...(shown.length ? shown.map((e, i) => {
        const row = h("a", { href: e.href, class: `palette-row ${i === active ? "active" : ""}`, role: "option", "aria-selected": String(i === active) }, icon(e.icon, 15), h("span", { class: "palette-label" }, e.label), h("span", { class: "palette-hint" }, e.hint));
        row.addEventListener("click", () => dlg.close());
        return row;
      }) : [h("p", { class: "palette-empty" }, "No matches")]));
    }
    const dlg = dialog({ title: "Search", body: h("div", input, results) });
    dlg.classList.add("palette");
    input.addEventListener("input", () => { active = 0; draw(); });
    input.addEventListener("keydown", (event) => {
      if (event.key === "ArrowDown") { active = Math.min(shown.length - 1, active + 1); draw(); event.preventDefault(); }
      if (event.key === "ArrowUp") { active = Math.max(0, active - 1); draw(); event.preventDefault(); }
      if (event.key === "Enter" && shown[active]) { dlg.close(); ET.go(shown[active].href); }
    });
    draw(); input.focus();
  }
  ET.palette = palette;

  function boot() {
    buildSidebar(); buildTopbar(); applyPrefs(); applyMode(); tick();
    setInterval(tick, 1000);
    setInterval(updateIndicators, 15000);
    setInterval(updateSafety, 15000);
    window.addEventListener("hashchange", route);
    window.addEventListener("popstate", route);
    document.addEventListener("keydown", (event) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") { event.preventDefault(); palette(); }
    });
    const scrim = document.getElementById("scrim");
    if (scrim) scrim.addEventListener("click", () => document.body.classList.remove("nav-open"));
    route();
  }
  ET.fmt = fmt; ET.pillOf = pill;
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot); else boot();
})();
