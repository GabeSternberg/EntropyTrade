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

  function parse() {
    const raw = (window.location.hash || "#/overview").replace(/^#\/?/, "");
    const [pathPart, query = ""] = raw.split("?");
    const parts = pathPart.split("/").filter(Boolean).map(decodeURIComponent);
    return { name: parts[0] || "overview", params: parts.slice(1), query: new URLSearchParams(query) };
  }
  ET.go = (hash) => { if (window.location.hash === hash) route(); else window.location.hash = hash; };

  let renderToken = 0;
  function route() {
    const { name, params, query } = parse();
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
    if (isWorkbench) { renderToken += 1; view.replaceChildren(); window.scrollTo(0, 0); return; }
    const token = ++renderToken;
    const target = h("div", { class: "view-inner", "data-view": key });
    view.replaceChildren(target);
    window.scrollTo(0, 0);
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
    : h("span", { class: "source-chip real", title: "Authentic data from this local workspace" }, h("span", { class: "dot pos" }), "Real data · local workspace");

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
    const bell = h("a", { class: "btn ghost icon bell", href: "#/ops", "aria-label": "Alerts", title: "Alerts" }, icon("bell", 17), h("span", { class: "bell-dot", id: "bell-dot", hidden: true }));
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
    let count = 0;
    if (mode === "demo") count = ET.demoData.quality_alerts.filter((a) => !a.resolved).length;
    else {
      try { const { alerts } = await ET.api("/api/alerts"); count = alerts.filter((a) => !a.resolved_at).length; } catch { count = 0; }
    }
    if (badge) { badge.hidden = !count; badge.textContent = String(count); }
    if (dotEl) dotEl.hidden = !count;
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
    const entries = NAV.flatMap((g) => g.items.map((i) => ({ label: i.label, hint: "Page", icon: i.icon, href: `#/${i.key}` })));
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
