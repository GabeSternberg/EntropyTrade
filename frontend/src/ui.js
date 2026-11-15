"use strict";
// EntropyTrade interface kit: DOM builders, icons, formatting, components and SVG charts.
// Dependency-free and CSP-compatible: DOM text nodes only, no string evaluation and no inline
// style attributes (element.style via CSSOM only). Everything is exposed on window.ET.
(function () {
  const ET = (window.ET = window.ET || {});
  ET.views = ET.views || {}; // view modules register here before shell.js boots
  const SVG_NS = "http://www.w3.org/2000/svg";

  // ------------------------------------------------------------------ DOM
  function apply(el, attrs) {
    if (!attrs) return el;
    for (const [key, value] of Object.entries(attrs)) {
      if (value === undefined || value === null || value === false) continue;
      if (key === "class") el.setAttribute("class", value);
      else if (key === "style") Object.assign(el.style, value);
      else if (key === "dataset") Object.assign(el.dataset, value);
      else if (key.startsWith("on") && typeof value === "function") el.addEventListener(key.slice(2), value);
      else if (key === "text") el.textContent = String(value);
      else if (value === true) el.setAttribute(key, "");
      else el.setAttribute(key, String(value));
    }
    return el;
  }
  function add(el, children) {
    for (const child of children.flat(Infinity)) {
      if (child === undefined || child === null || child === false) continue;
      el.append(child instanceof Node ? child : document.createTextNode(String(child)));
    }
    return el;
  }
  function isAttrs(value) {
    return value && typeof value === "object" && !(value instanceof Node) && !Array.isArray(value);
  }
  function h(tag, attrs, ...children) {
    const el = document.createElement(tag);
    if (isAttrs(attrs)) apply(el, attrs); else children.unshift(attrs);
    return add(el, children);
  }
  function s(tag, attrs, ...children) {
    const el = document.createElementNS(SVG_NS, tag);
    if (isAttrs(attrs)) {
      for (const [key, value] of Object.entries(attrs)) {
        if (value === undefined || value === null || value === false) continue;
        if (key === "text") el.textContent = String(value);
        else if (key.startsWith("on") && typeof value === "function") el.addEventListener(key.slice(2), value);
        else el.setAttribute(key, String(value));
      }
    } else children.unshift(attrs);
    return add(el, children);
  }

  // ---------------------------------------------------------------- icons
  // Stroke icons on a 24px grid (Lucide-style geometry, drawn locally).
  const ICONS = {
    overview: ["M3 13h8V3H3z", "M13 21h8V11h-8z", "M3 21h8v-6H3z", "M13 9h8V3h-8z"],
    markets: ["M3 3v18h18", "M7 15l4-4 3 3 6-7"],
    lab: ["M9 3h6", "M10 3v6L4.5 18.5A1.7 1.7 0 0 0 6 21h12a1.7 1.7 0 0 0 1.5-2.5L14 9V3", "M7 15h10"],
    analytics: ["M3 3v18h18", "M8 17V11", "M13 17V7", "M18 17v-4"],
    paper: ["M3 7h18v13H3z", "M16 13h2", "M3 7l3-4h12l3 4"],
    ops: ["M4 6c0-1.7 3.6-3 8-3s8 1.3 8 3-3.6 3-8 3-8-1.3-8-3z", "M4 6v6c0 1.7 3.6 3 8 3s8-1.3 8-3V6", "M4 12v6c0 1.7 3.6 3 8 3s8-1.3 8-3v-6"],
    settings: ["M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6z", "M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"],
    workbench: ["M4 17l6-6-6-6", "M12 19h8"],
    search: ["M11 19a8 8 0 1 0 0-16 8 8 0 0 0 0 16z", "M21 21l-4.3-4.3"],
    bell: ["M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9", "M13.7 21a2 2 0 0 1-3.4 0"],
    lock: ["M5 11h14v10H5z", "M8 11V7a4 4 0 0 1 8 0v4"],
    up: ["M7 17L17 7", "M8 7h9v9"],
    down: ["M7 7l10 10", "M17 8v9H8"],
    chevronRight: ["M9 18l6-6-6-6"],
    chevronDown: ["M6 9l6 6 6-6"],
    chevronLeft: ["M15 18l-6-6 6-6"],
    x: ["M18 6L6 18", "M6 6l12 12"],
    check: ["M20 6L9 17l-5-5"],
    alert: ["M10.3 3.9L1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z", "M12 9v4", "M12 17h.01"],
    info: ["M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20z", "M12 16v-4", "M12 8h.01"],
    download: ["M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4", "M7 10l5 5 5-5", "M12 15V3"],
    external: ["M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6", "M15 3h6v6", "M10 14L21 3"],
    filter: ["M22 3H2l8 9.5V19l4 2v-8.5z"],
    plus: ["M12 5v14", "M5 12h14"],
    refresh: ["M23 4v6h-6", "M1 20v-6h6", "M3.5 9a9 9 0 0 1 14.9-3.4L23 10", "M1 14l4.6 4.4A9 9 0 0 0 20.5 15"],
    play: ["M6 4l14 8-14 8z"],
    pause: ["M7 4h3v16H7z", "M14 4h3v16h-3z"],
    clock: ["M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20z", "M12 6v6l4 2"],
    activity: ["M22 12h-4l-3 9L9 3l-3 9H2"],
    shield: ["M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"],
    layers: ["M12 2L2 7l10 5 10-5z", "M2 17l10 5 10-5", "M2 12l10 5 10-5"],
    sparkles: ["M12 3l1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9z", "M19 15l.8 2.2L22 18l-2.2.8L19 21l-.8-2.2L16 18l2.2-.8z"],
    menu: ["M3 6h18", "M3 12h18", "M3 18h18"],
    sidebar: ["M3 3h18v18H3z", "M9 3v18"],
    star: ["M12 2l3.1 6.3 6.9 1-5 4.9 1.2 6.8L12 17.8 5.8 21l1.2-6.8-5-4.9 6.9-1z"],
    zap: ["M13 2L3 14h9l-1 8 10-12h-9z"],
    target: ["M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20z", "M12 18a6 6 0 1 0 0-12 6 6 0 0 0 0 12z", "M12 14a2 2 0 1 0 0-4 2 2 0 0 0 0 4z"],
    database: ["M12 8c4.4 0 8-1.3 8-3s-3.6-3-8-3-8 1.3-8 3 3.6 3 8 3z", "M4 5v14c0 1.7 3.6 3 8 3s8-1.3 8-3V5"],
    server: ["M2 3h20v7H2z", "M2 14h20v7H2z", "M6 6.5h.01", "M6 17.5h.01"],
    file: ["M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z", "M14 2v6h6", "M8 13h8", "M8 17h6"],
    beaker: ["M4.5 3h15", "M6 3v16a2 2 0 0 0 2 2h8a2 2 0 0 0 2-2V3", "M6 14h12"],
    flag: ["M4 15s1-1 4-1 5 2 8 2 4-1 4-1V3s-1 1-4 1-5-2-8-2-4 1-4 1z", "M4 22v-7"],
    command: ["M18 3a3 3 0 0 0-3 3v12a3 3 0 1 0 3-3H6a3 3 0 1 0 3 3V6a3 3 0 1 0-3 3h12a3 3 0 0 0 0-6z"],
    eye: ["M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z", "M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6z"],
    globe: ["M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20z", "M2 12h20", "M12 2a15 15 0 0 1 4 10 15 15 0 0 1-4 10 15 15 0 0 1-4-10 15 15 0 0 1 4-10z"],
    sliders: ["M4 21v-7", "M4 10V3", "M12 21v-9", "M12 8V3", "M20 21v-5", "M20 12V3", "M1 14h6", "M9 8h6", "M17 16h6"],
    hardDrive: ["M22 12H2", "M5.5 5.1L2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.5-6.9A2 2 0 0 0 16.8 4H7.2a2 2 0 0 0-1.7 1.1z", "M6 16h.01", "M10 16h.01"],
  };
  function icon(name, size = 16, extraClass = "") {
    const paths = ICONS[name] || ICONS.info;
    return s("svg", { class: `icon ${extraClass}`.trim(), width: size, height: size, viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", "stroke-width": 1.8, "stroke-linecap": "round", "stroke-linejoin": "round", "aria-hidden": "true", focusable: "false" },
      paths.map((d) => s("path", { d })));
  }
  function logo(size = 22) {
    return s("svg", { class: "logo-mark", width: size, height: size, viewBox: "0 0 24 24", "aria-hidden": "true" },
      s("rect", { x: 1, y: 1, width: 22, height: 22, rx: 6, fill: "var(--accent)" }),
      s("path", { d: "M7 7h10M7 12h7M7 17h10M7 7v10", stroke: "var(--accent-ink)", "stroke-width": 2.2, "stroke-linecap": "round", fill: "none" }));
  }

  // ----------------------------------------------------------- formatting
  const fmt = {
    num(value, digits = 0) {
      if (value === null || value === undefined || Number.isNaN(Number(value))) return "—";
      return Number(value).toLocaleString("en-US", { minimumFractionDigits: digits, maximumFractionDigits: digits });
    },
    usd(value, digits = 2) {
      if (value === null || value === undefined || Number.isNaN(Number(value))) return "—";
      const n = Number(value);
      return `${n < 0 ? "−" : ""}$${Math.abs(n).toLocaleString("en-US", { minimumFractionDigits: digits, maximumFractionDigits: digits })}`;
    },
    signedUsd(value, digits = 2) {
      if (value === null || value === undefined) return "—";
      return `${Number(value) > 0 ? "+" : ""}${fmt.usd(value, digits)}`;
    },
    compactUsd(value) {
      if (value === null || value === undefined) return "—";
      const n = Math.abs(Number(value));
      const sign = Number(value) < 0 ? "−" : "";
      if (n >= 1e6) return `${sign}$${(n / 1e6).toFixed(2)}M`;
      if (n >= 1e3) return `${sign}$${(n / 1e3).toFixed(1)}K`;
      return `${sign}$${n.toFixed(0)}`;
    },
    compact(value) {
      if (value === null || value === undefined) return "—";
      const n = Number(value);
      if (Math.abs(n) >= 1e6) return `${(n / 1e6).toFixed(1)}M`;
      if (Math.abs(n) >= 1e3) return `${(n / 1e3).toFixed(1)}K`;
      return String(Math.round(n));
    },
    pct(value, digits = 1, signed = false) {
      if (value === null || value === undefined || Number.isNaN(Number(value))) return "—";
      const n = Number(value) * 100;
      return `${signed && n > 0 ? "+" : ""}${n < 0 ? "−" : ""}${Math.abs(n).toFixed(digits)}%`;
    },
    cents(value) {
      if (value === null || value === undefined) return "—";
      return `${Math.round(Number(value) * 100)}¢`;
    },
    date(value) {
      if (!value) return "—";
      const d = new Date(value);
      return Number.isNaN(d.getTime()) ? String(value) : d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric", timeZone: "UTC" });
    },
    dateTime(value) {
      if (!value) return "—";
      const d = new Date(value);
      if (Number.isNaN(d.getTime())) return String(value);
      return d.toLocaleString("en-US", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit", hour12: false, timeZone: "UTC" }) + " UTC";
    },
    stamp(value) {
      const d = new Date(value);
      if (Number.isNaN(d.getTime())) return "—";
      return `${d.toLocaleDateString("en-US", { month: "short", day: "numeric", timeZone: "UTC" })} ${d.toISOString().slice(11, 16)}`;
    },
    time(value) {
      const d = new Date(value);
      return Number.isNaN(d.getTime()) ? "—" : d.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit", hour12: false, timeZone: "UTC" });
    },
    ago(value, now = Date.now()) {
      if (!value) return "—";
      const seconds = Math.max(0, Math.round((now - new Date(value).getTime()) / 1000));
      if (Number.isNaN(seconds)) return "—";
      if (seconds < 60) return `${seconds}s ago`;
      if (seconds < 3600) return `${Math.round(seconds / 60)}m ago`;
      if (seconds < 86400) return `${Math.round(seconds / 3600)}h ago`;
      return `${Math.round(seconds / 86400)}d ago`;
    },
    duration(seconds) {
      if (seconds === null || seconds === undefined) return "—";
      if (seconds < 60) return `${Math.round(seconds)}s`;
      if (seconds < 3600) return `${Math.round(seconds / 60)}m`;
      if (seconds < 86400) return `${(seconds / 3600).toFixed(1)}h`;
      return `${(seconds / 86400).toFixed(1)}d`;
    },
    bytes(value) {
      if (value === null || value === undefined) return "—";
      const units = ["B", "KB", "MB", "GB", "TB"];
      let n = Number(value); let i = 0;
      while (n >= 1024 && i < units.length - 1) { n /= 1024; i += 1; }
      return `${n.toFixed(i ? 1 : 0)} ${units[i]}`;
    },
    short(value, n = 8) { return value ? String(value).slice(0, n) : "—"; },
    words(value) { return value ? String(value).replaceAll("_", " ") : "—"; },
  };
  function tone(value) { return value > 0 ? "pos" : value < 0 ? "neg" : "flat"; }

  // ----------------------------------------------------------- components
  function pill(text, kind = "", attrs = {}) {
    return h("span", { ...attrs, class: `pill ${kind}`.trim() }, text);
  }
  const STATUS_TONES = {
    pos: /^(completed|active|ok|healthy|operational|attested|filled|settled|passed|promising|approved|backtested|validated|fresh|yes|win|live|sealed|paper|shadow)$/i,
    warn: /^(pending|queued|running|starting|paused|insufficient|degraded|stale|partial|delayed|review|draft|research|open|acknowledged|warning|resting|partially filled|lagging)$/i,
    neg: /^(failed|rejected|error|invalid|cancelled|interrupted|down|refused|blocked|no|loss|critical|halted|expired|incomplete)$/i,
  };
  function statusPill(value) {
    const text = fmt.words(value);
    const kind = STATUS_TONES.pos.test(text) ? "pos" : STATUS_TONES.neg.test(text) ? "neg" : STATUS_TONES.warn.test(text) ? "warn" : "";
    return pill(text, `status ${kind}`, { "data-status": String(value) });
  }
  function dot(kind) { return h("span", { class: `dot ${kind}`, "aria-hidden": "true" }); }
  function delta(value, formatter = (v) => fmt.pct(v, 1, true)) {
    if (value === null || value === undefined) return h("span", { class: "delta flat" }, "—");
    return h("span", { class: `delta ${tone(value)}` }, icon(value >= 0 ? "up" : "down", 12), formatter(value));
  }
  function button(label, attrs = {}, iconName) {
    const { variant = "", ...rest } = attrs;
    return h("button", { type: "button", ...rest, class: `btn ${variant} ${rest.class || ""}`.trim() }, iconName ? icon(iconName, 15) : null, label ? h("span", label) : null);
  }
  function card(attrs, ...children) {
    const { title, subtitle, actions, flush, className, id, source } = attrs || {};
    const head = title || actions ? h("header", { class: "card-head" },
      h("div", { class: "card-titles" }, title ? h("h3", { class: "card-title" }, title) : null, subtitle ? h("p", { class: "card-sub" }, subtitle) : null),
      h("div", { class: "card-actions" }, source ? sourceTag(source) : null, actions)) : null;
    return h("section", { class: `card ${flush ? "flush" : ""} ${className || ""}`.trim(), id }, head, h("div", { class: "card-body" }, children));
  }
  function sourceTag(source) {
    return source === "demo" ? pill("Simulated", "demo-tag", { title: "Demo Mode · fictional sample data" }) : pill("Local API", "real-tag", { title: "Authentic data from this workspace" });
  }
  function kpi({ label, value, sub, deltaValue, deltaFormat, iconName, kind = "", spark, sparkTone, help }) {
    return h("div", { class: `kpi ${kind}`.trim() },
      h("div", { class: "kpi-top" },
        iconName ? h("span", { class: `kpi-icon ${kind}` }, icon(iconName, 16)) : null,
        h("span", { class: "kpi-label" }, label),
        help ? h("span", { class: "kpi-help", title: help }, icon("info", 13)) : null),
      h("div", { class: "kpi-value" }, value),
      h("div", { class: "kpi-foot" }, deltaValue !== undefined ? delta(deltaValue, deltaFormat) : null, sub ? h("span", { class: "kpi-sub" }, sub) : null),
      spark ? h("div", { class: "kpi-spark" }, sparkline(spark, { width: 120, height: 32, tone: sparkTone })) : null);
  }
  function emptyState({ iconName = "info", title, body, action, kind = "" }) {
    return h("div", { class: `empty-state ${kind}`.trim() },
      h("span", { class: "empty-icon" }, icon(iconName, 20)),
      h("h4", title), body ? h("p", body) : null, action || null);
  }
  function unavailable(title, body, action) {
    return emptyState({ iconName: "lock", title, body, action, kind: "unavailable" });
  }
  function errorState(message, retry) {
    return emptyState({ iconName: "alert", title: "Could not load this data", body: message, kind: "error", action: retry ? button("Retry", { onclick: retry, variant: "ghost sm" }, "refresh") : null });
  }
  function skeleton(lines = 3, kind = "") {
    return h("div", { class: `skeleton-block ${kind}`.trim(), "aria-busy": "true", "aria-label": "Loading" },
      Array.from({ length: lines }, (_, i) => h("span", { class: `skeleton-line w${(i % 3) + 1}` })));
  }
  function callout(text, kind = "info", iconName) {
    return h("div", { class: `callout ${kind}`, role: kind === "error" ? "alert" : "note" }, icon(iconName || (kind === "warn" || kind === "error" ? "alert" : kind === "lock" ? "lock" : "info"), 15), h("div", text));
  }
  function meter(value, max = 1, kind = "") {
    const bar = h("span", { class: `meter-fill ${kind}`.trim() });
    bar.style.width = `${Math.max(0, Math.min(100, (value / max) * 100))}%`;
    return h("span", { class: "meter", role: "meter", "aria-valuenow": value, "aria-valuemin": 0, "aria-valuemax": max }, bar);
  }
  function kv(rows) {
    return h("dl", { class: "kv" }, rows.filter(Boolean).map(([k, v]) => h("div", { class: "kv-row" }, h("dt", k), h("dd", v))));
  }

  // Tabs: returns { el, set }; onchange(key) renders the panel.
  function tabs(items, active, onchange, variant = "") {
    const bar = h("div", { class: `tabbar ${variant}`.trim(), role: "tablist" });
    const buttons = items.map(({ key, label, count }) => {
      const b = h("button", { type: "button", role: "tab", class: "tab", "aria-selected": String(key === active), dataset: { key } },
        label, count !== undefined ? h("span", { class: "tab-count" }, String(count)) : null);
      b.addEventListener("click", () => set(key));
      return b;
    });
    add(bar, buttons);
    function set(key) {
      buttons.forEach((b) => b.setAttribute("aria-selected", String(b.dataset.key === key)));
      onchange(key);
    }
    bar.addEventListener("keydown", (event) => {
      if (!["ArrowLeft", "ArrowRight"].includes(event.key)) return;
      const index = buttons.findIndex((b) => b.getAttribute("aria-selected") === "true");
      const next = buttons[(index + (event.key === "ArrowRight" ? 1 : -1) + buttons.length) % buttons.length];
      next.focus(); set(next.dataset.key);
    });
    return { el: bar, set };
  }
  function segmented(items, active, onchange, attrs = {}) {
    const wrap = h("div", { class: "segmented", role: "group", ...attrs });
    const buttons = items.map(({ key, label }) => {
      const b = h("button", { type: "button", "aria-pressed": String(key === active), dataset: { key } }, label);
      b.addEventListener("click", () => {
        buttons.forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
        onchange(key);
      });
      return b;
    });
    return add(wrap, buttons);
  }

  // Sortable data table. columns: {key, label, align, render(row), sort(row), width}
  function dataTable({ columns, rows, sortKey, sortDir = "desc", onRow, empty, pageSize = 0, rowClass, dense = false, caption }) {
    let key = sortKey; let dir = sortDir; let page = 0;
    const wrap = h("div", { class: "table-shell" });
    function sorted() {
      const column = columns.find((c) => c.key === key);
      if (!column) return rows.slice();
      const get = column.sort || ((row) => row[column.key]);
      return rows.slice().sort((a, b) => {
        const x = get(a); const y = get(b);
        const cmp = typeof x === "number" && typeof y === "number" ? x - y : String(x ?? "").localeCompare(String(y ?? ""));
        return dir === "asc" ? cmp : -cmp;
      });
    }
    function render() {
      const all = sorted();
      const pages = pageSize ? Math.max(1, Math.ceil(all.length / pageSize)) : 1;
      page = Math.min(page, pages - 1);
      const view = pageSize ? all.slice(page * pageSize, (page + 1) * pageSize) : all;
      const head = h("thead", h("tr", columns.map((c) => {
        const sortable = c.sortable !== false;
        const th = h("th", { class: `${c.align || ""} ${sortable ? "sortable" : ""}`.trim(), scope: "col", "aria-sort": c.key === key ? (dir === "asc" ? "ascending" : "descending") : null },
          sortable ? h("button", { type: "button", class: "th-btn" }, c.label, h("span", { class: "sort-ind" }, c.key === key ? (dir === "asc" ? "▲" : "▼") : "")) : c.label);
        if (c.width) th.style.width = c.width;
        if (sortable) th.querySelector("button").addEventListener("click", () => {
          if (key === c.key) dir = dir === "asc" ? "desc" : "asc"; else { key = c.key; dir = c.align === "num" ? "desc" : "asc"; }
          render();
        });
        return th;
      })));
      const body = h("tbody", view.map((row) => {
        const tr = h("tr", { class: `${onRow ? "clickable" : ""} ${rowClass ? rowClass(row) : ""}`.trim(), tabindex: onRow ? 0 : null },
          columns.map((c) => h("td", { class: c.align || "" }, c.render ? c.render(row) : (row[c.key] ?? "—"))));
        if (onRow) {
          tr.addEventListener("click", () => onRow(row));
          tr.addEventListener("keydown", (event) => { if (event.key === "Enter") onRow(row); });
        }
        return tr;
      }));
      const table = h("table", { class: `data-table ${dense ? "dense" : ""}`.trim() }, caption ? h("caption", { class: "sr-only" }, caption) : null, head, body);
      const parts = [h("div", { class: "table-scroll" }, table)];
      if (!view.length) parts.push(empty || emptyState({ iconName: "search", title: "No matching rows", body: "Adjust the filters to see results." }));
      if (pageSize && all.length > pageSize) {
        const prev = button("", { variant: "ghost icon sm", "aria-label": "Previous page", disabled: page === 0, onclick: () => { page -= 1; render(); } }, "chevronLeft");
        const next = button("", { variant: "ghost icon sm", "aria-label": "Next page", disabled: page >= pages - 1, onclick: () => { page += 1; render(); } }, "chevronRight");
        parts.push(h("div", { class: "table-foot" }, h("span", `Showing ${page * pageSize + 1}–${Math.min(all.length, (page + 1) * pageSize)} of ${all.length}`), h("div", { class: "pager" }, prev, h("span", `${page + 1} / ${pages}`), next)));
      }
      wrap.replaceChildren(...parts);
    }
    render();
    wrap.update = (nextRows) => { rows = nextRows; page = 0; render(); };
    return wrap;
  }

  // Dialogs and drawers: native <dialog> for focus management and Escape handling.
  function dialog({ title, body, footer, wide = false, drawer = false, onclose }) {
    const close = button("", { variant: "ghost icon", "aria-label": "Close" }, "x");
    const el = h("dialog", { class: `modal ${wide ? "wide" : ""} ${drawer ? "drawer" : ""}`.trim(), "aria-label": typeof title === "string" ? title : "Details" },
      h("header", { class: "modal-head" }, h("h2", title), close),
      h("div", { class: "modal-body" }, body),
      footer ? h("footer", { class: "modal-foot" }, footer) : null);
    close.addEventListener("click", () => el.close());
    el.addEventListener("click", (event) => { if (event.target === el) el.close(); });
    el.addEventListener("close", () => { el.remove(); if (onclose) onclose(); });
    document.body.append(el);
    el.showModal();
    return el;
  }
  function toast(message, kind = "info") {
    let host = document.getElementById("toasts");
    if (!host) { host = h("div", { id: "toasts", class: "toasts", role: "status", "aria-live": "polite" }); document.body.append(host); }
    const item = h("div", { class: `toast ${kind}` }, icon(kind === "error" ? "alert" : kind === "ok" ? "check" : "info", 15), h("span", message));
    host.append(item);
    setTimeout(() => { item.classList.add("leaving"); setTimeout(() => item.remove(), 250); }, 3600);
  }

  // ---------------------------------------------------------------- charts
  const PALETTE = ["var(--c1)", "var(--c2)", "var(--c3)", "var(--c4)", "var(--c5)", "var(--c6)"];
  function niceTicks(min, max, count = 5) {
    if (min === max) { min -= 1; max += 1; }
    const span = max - min;
    const step0 = span / count;
    const mag = 10 ** Math.floor(Math.log10(step0));
    const err = step0 / mag;
    const step = (err >= 7.5 ? 10 : err >= 3.5 ? 5 : err >= 1.5 ? 2 : 1) * mag;
    const lo = Math.floor(min / step) * step;
    const hi = Math.ceil(max / step) * step;
    const ticks = [];
    for (let v = lo; v <= hi + step / 2; v += step) ticks.push(Number(v.toFixed(10)));
    return ticks;
  }
  function chartFrame(width, height, label) {
    return s("svg", { class: "chart", viewBox: `0 0 ${width} ${height}`, width, height, role: "img", "aria-label": label || "Chart" });
  }
  function sparkline(values, { width = 120, height = 32, tone: t } = {}) {
    if (!values || values.length < 2) return h("span", { class: "spark-empty" }, "—");
    const min = Math.min(...values); const max = Math.max(...values);
    const k = t || (values[values.length - 1] >= values[0] ? "pos" : "neg");
    const xs = (i) => (i / (values.length - 1)) * width;
    const ys = (v) => height - 2 - ((v - min) / (max - min || 1)) * (height - 4);
    const d = values.map((v, i) => `${i ? "L" : "M"}${xs(i).toFixed(1)},${ys(v).toFixed(1)}`).join("");
    return s("svg", { class: `spark ${k}`, viewBox: `0 0 ${width} ${height}`, width, height, preserveAspectRatio: "none", "aria-hidden": "true" },
      s("path", { d: `${d}L${width},${height}L0,${height}Z`, class: "spark-area" }),
      s("path", { d, class: "spark-line" }));
  }

  // Interactive time-series chart with crosshair tooltip.
  // series: [{name, values:[{x(ms or index), y}], color, area, dash}]
  function lineChartAt(series, opts = {}) {
    const { height = 260, yFormat = (v) => fmt.num(v), xFormat = (v) => fmt.date(v), area = false, zero = false, label, baseline, watermark, yMin, yMax, legend = series.length > 1 } = opts;
    const W = Math.max(280, opts.width || 800); const H = height; const pad = { l: 56, r: 16, t: 14, b: 28 };
    const host = h("div", { class: "chart-host" });
    const all = series.flatMap((x) => x.values);
    if (!all.length) { host.append(emptyState({ iconName: "analytics", title: "No series to plot" })); return host; }
    const xsAll = all.map((p) => p.x); const ysAll = all.map((p) => p.y);
    if (baseline !== undefined) ysAll.push(baseline);
    if (zero) ysAll.push(0);
    const xmin = Math.min(...xsAll); const xmax = Math.max(...xsAll);
    const ticks = niceTicks(yMin ?? Math.min(...ysAll), yMax ?? Math.max(...ysAll), 4);
    const ymin = ticks[0]; const ymax = ticks[ticks.length - 1];
    const X = (x) => pad.l + ((x - xmin) / (xmax - xmin || 1)) * (W - pad.l - pad.r);
    const Y = (y) => pad.t + (1 - (y - ymin) / (ymax - ymin || 1)) * (H - pad.t - pad.b);
    const svg = chartFrame(W, H, label);
    const defs = s("defs");
    svg.append(defs);
    ticks.forEach((t) => svg.append(s("line", { x1: pad.l, x2: W - pad.r, y1: Y(t), y2: Y(t), class: `grid ${t === 0 ? "zero" : ""}` }), s("text", { x: pad.l - 8, y: Y(t) + 4, class: "axis-label", "text-anchor": "end", text: yFormat(t) })));
    const xticks = Math.max(2, Math.min(6, Math.floor(W / 130)));
    for (let i = 0; i <= xticks; i += 1) {
      const xv = xmin + ((xmax - xmin) * i) / xticks;
      svg.append(s("text", { x: X(xv), y: H - 8, class: "axis-label", "text-anchor": i === 0 ? "start" : i === xticks ? "end" : "middle", text: xFormat(xv) }));
    }
    if (baseline !== undefined) svg.append(s("line", { x1: pad.l, x2: W - pad.r, y1: Y(baseline), y2: Y(baseline), class: "baseline" }));
    series.forEach((ser, idx) => {
      const color = ser.color || PALETTE[idx % PALETTE.length];
      const pts = ser.values;
      if (!pts.length) return;
      const d = pts.map((p, i) => `${i ? "L" : "M"}${X(p.x).toFixed(1)},${Y(p.y).toFixed(1)}`).join("");
      if (ser.area ?? (area && idx === 0)) {
        const gid = `g${Math.random().toString(36).slice(2, 8)}`;
        defs.append(s("linearGradient", { id: gid, x1: 0, x2: 0, y1: 0, y2: 1 },
          s("stop", { offset: "0%", "stop-color": color, "stop-opacity": ser.areaOpacity ?? 0.28 }),
          s("stop", { offset: "100%", "stop-color": color, "stop-opacity": 0 })));
        const base = Y(ser.areaBase ?? Math.max(ymin, Math.min(0 > ymin ? 0 : ymin, ymax)));
        svg.append(s("path", { d: `${d}L${X(pts[pts.length - 1].x)},${base}L${X(pts[0].x)},${base}Z`, fill: `url(#${gid})`, class: "area" }));
      }
      svg.append(s("path", { d, class: `line ${ser.dash ? "dashed" : ""}`, stroke: color, "stroke-width": ser.width || 2 }));
    });
    const cross = s("line", { class: "crosshair", y1: pad.t, y2: H - pad.b, x1: -10, x2: -10 });
    const dots = series.map((ser, idx) => s("circle", { r: 4, class: "hover-dot", fill: ser.color || PALETTE[idx % PALETTE.length], cx: -10, cy: -10 }));
    svg.append(cross, ...dots);
    if (watermark) svg.append(s("text", { x: W - pad.r - 6, y: pad.t + 14, class: "watermark", "text-anchor": "end", text: watermark }));
    const tip = h("div", { class: "chart-tip", hidden: true });
    host.append(svg, tip);
    if (legend) host.prepend(h("div", { class: "legend" }, series.map((ser, idx) => {
      const sw = h("span", { class: "swatch" }); sw.style.background = ser.color || PALETTE[idx % PALETTE.length];
      return h("span", { class: "legend-item" }, sw, ser.name);
    })));
    const ref = series.reduce((a, b) => (b.values.length > a.values.length ? b : a));
    function move(event) {
      const rect = svg.getBoundingClientRect();
      const px = ((event.clientX - rect.left) / rect.width) * W;
      const xv = xmin + ((px - pad.l) / (W - pad.l - pad.r)) * (xmax - xmin);
      let best = 0; let bestDist = Infinity;
      ref.values.forEach((p, i) => { const dd = Math.abs(p.x - xv); if (dd < bestDist) { bestDist = dd; best = i; } });
      const point = ref.values[best];
      if (!point) return;
      cross.setAttribute("x1", X(point.x)); cross.setAttribute("x2", X(point.x));
      const rows = series.map((ser, idx) => {
        const p = ser.values.reduce((a, b) => (Math.abs(b.x - point.x) < Math.abs(a.x - point.x) ? b : a), ser.values[0]);
        if (p) { dots[idx].setAttribute("cx", X(p.x)); dots[idx].setAttribute("cy", Y(p.y)); }
        const sw = h("span", { class: "swatch" }); sw.style.background = ser.color || PALETTE[idx % PALETTE.length];
        return h("div", { class: "tip-row" }, sw, h("span", ser.name || "Value"), h("strong", p ? yFormat(p.y) : "—"));
      });
      tip.replaceChildren(h("div", { class: "tip-head" }, xFormat(point.x)), ...rows);
      tip.hidden = false;
      const left = (X(point.x) / W) * rect.width;
      tip.style.left = `${Math.min(rect.width - 180, Math.max(0, left + 12))}px`;
      tip.style.top = "8px";
    }
    svg.addEventListener("pointermove", (event) => { host.classList.add("hovering"); move(event); });
    svg.addEventListener("pointerleave", () => { host.classList.remove("hovering"); tip.hidden = true; cross.setAttribute("x1", -10); cross.setAttribute("x2", -10); dots.forEach((d) => { d.setAttribute("cx", -10); d.setAttribute("cy", -10); }); });
    return host;
  }

  // Vertical bars (histogram / P&L by period). items: [{label, value, tone?}]
  function barChartAt(items, opts = {}) {
    const { height = 220, yFormat = (v) => fmt.num(v), label, signed = true, highlight, watermark, xLabelEvery = 1 } = opts;
    const W = Math.max(280, opts.width || 800); const H = height; const pad = { l: 52, r: 12, t: 12, b: 30 };
    const host = h("div", { class: "chart-host" });
    if (!items.length) { host.append(emptyState({ iconName: "analytics", title: "No observations" })); return host; }
    const vals = items.map((i) => i.value);
    const ticks = niceTicks(Math.min(0, ...vals), Math.max(0, ...vals), 4);
    const ymin = ticks[0]; const ymax = ticks[ticks.length - 1];
    const Y = (y) => pad.t + (1 - (y - ymin) / (ymax - ymin || 1)) * (H - pad.t - pad.b);
    const bw = (W - pad.l - pad.r) / items.length;
    const every = Math.max(xLabelEvery, Math.ceil(46 / bw));
    const svg = chartFrame(W, H, label);
    ticks.forEach((t) => svg.append(s("line", { x1: pad.l, x2: W - pad.r, y1: Y(t), y2: Y(t), class: `grid ${t === 0 ? "zero" : ""}` }), s("text", { x: pad.l - 8, y: Y(t) + 4, class: "axis-label", "text-anchor": "end", text: yFormat(t) })));
    const tip = h("div", { class: "chart-tip", hidden: true });
    items.forEach((item, i) => {
      const x = pad.l + i * bw + bw * 0.14;
      const y0 = Y(0); const y1 = Y(item.value);
      const k = item.tone || (signed ? (item.value >= 0 ? "pos" : "neg") : "accent");
      const rect = s("rect", { x, y: Math.min(y0, y1), width: Math.max(1, bw * 0.72), height: Math.max(1, Math.abs(y1 - y0)), rx: Math.min(3, bw * 0.2), class: `bar ${k} ${highlight === i ? "hl" : ""}` });
      rect.addEventListener("pointerenter", (event) => {
        tip.replaceChildren(h("div", { class: "tip-head" }, item.label), h("div", { class: "tip-row" }, h("span", item.series || "Value"), h("strong", yFormat(item.value))), item.note ? h("div", { class: "tip-note" }, item.note) : null);
        tip.hidden = false;
        const r = svg.getBoundingClientRect();
        tip.style.left = `${Math.min(r.width - 170, Math.max(0, event.clientX - r.left + 10))}px`; tip.style.top = "8px";
      });
      rect.addEventListener("pointerleave", () => { tip.hidden = true; });
      svg.append(rect);
      if (i % every === 0) svg.append(s("text", { x: x + bw * 0.36, y: H - 10, class: "axis-label", "text-anchor": "middle", text: item.label }));
    });
    if (watermark) svg.append(s("text", { x: W - pad.r - 6, y: pad.t + 14, class: "watermark", "text-anchor": "end", text: watermark }));
    host.append(svg, tip);
    return host;
  }

  // Charts are drawn in real pixels: re-render at the container's width so text never scales.
  function responsive(build) {
    const frame = h("div", { class: "chart-frame" });
    let width = 0;
    frame.append(build(800));
    if (typeof ResizeObserver === "function") {
      const observer = new ResizeObserver((entries) => {
        const next = Math.round(entries[0].contentRect.width);
        if (next > 0 && Math.abs(next - width) > 3) { width = next; frame.replaceChildren(build(next)); }
      });
      observer.observe(frame);
    }
    return frame;
  }
  const lineChart = (series, opts = {}) => responsive((width) => lineChartAt(series, { ...opts, width }));
  const barChart = (items, opts = {}) => responsive((width) => barChartAt(items, { ...opts, width }));

  // Reliability diagram: bins [{p (mean predicted), o (observed freq), n}]
  function calibrationChart(groups, opts = {}) {
    const { height = 300, watermark } = opts;
    const W = 420; const H = height; const pad = { l: 44, r: 14, t: 14, b: 34 };
    const X = (v) => pad.l + v * (W - pad.l - pad.r);
    const Y = (v) => pad.t + (1 - v) * (H - pad.t - pad.b);
    const svg = s("svg", { class: "chart square", viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": "Calibration reliability diagram" });
    [0, 0.25, 0.5, 0.75, 1].forEach((t) => {
      svg.append(s("line", { x1: X(0), x2: X(1), y1: Y(t), y2: Y(t), class: "grid" }), s("line", { x1: X(t), x2: X(t), y1: Y(0), y2: Y(1), class: "grid" }),
        s("text", { x: pad.l - 8, y: Y(t) + 4, class: "axis-label", "text-anchor": "end", text: `${t * 100}%` }),
        s("text", { x: X(t), y: H - 14, class: "axis-label", "text-anchor": "middle", text: `${t * 100}%` }));
    });
    svg.append(s("line", { x1: X(0), y1: Y(0), x2: X(1), y2: Y(1), class: "diagonal" }));
    svg.append(s("text", { x: X(0.5), y: H - 1, class: "axis-title", "text-anchor": "middle", text: "Predicted probability" }));
    const host = h("div", { class: "chart-host" });
    const tip = h("div", { class: "chart-tip", hidden: true });
    groups.forEach((g, idx) => {
      const color = g.color || PALETTE[idx % PALETTE.length];
      const d = g.bins.map((b, i) => `${i ? "L" : "M"}${X(b.p).toFixed(1)},${Y(b.o).toFixed(1)}`).join("");
      svg.append(s("path", { d, class: "line", stroke: color, "stroke-width": 2 }));
      g.bins.forEach((b) => {
        const c = s("circle", { cx: X(b.p), cy: Y(b.o), r: Math.max(3, Math.min(9, Math.sqrt(b.n) / 2)), fill: color, class: "cal-dot" });
        c.addEventListener("pointerenter", (event) => {
          tip.replaceChildren(h("div", { class: "tip-head" }, g.name), h("div", { class: "tip-row" }, h("span", "Predicted"), h("strong", fmt.pct(b.p))), h("div", { class: "tip-row" }, h("span", "Observed"), h("strong", fmt.pct(b.o))), h("div", { class: "tip-row" }, h("span", "Events"), h("strong", String(b.n))));
          tip.hidden = false; const r = svg.getBoundingClientRect();
          tip.style.left = `${Math.min(r.width - 170, event.clientX - r.left + 10)}px`; tip.style.top = `${Math.max(0, event.clientY - r.top - 60)}px`;
        });
        c.addEventListener("pointerleave", () => { tip.hidden = true; });
        svg.append(c);
      });
    });
    if (watermark) svg.append(s("text", { x: W - pad.r - 6, y: pad.t + 14, class: "watermark", "text-anchor": "end", text: watermark }));
    host.append(h("div", { class: "legend" }, groups.map((g, idx) => { const sw = h("span", { class: "swatch" }); sw.style.background = g.color || PALETTE[idx % PALETTE.length]; return h("span", { class: "legend-item" }, sw, g.name); })), svg, tip);
    return host;
  }

  // Heat grid: rows x cols numeric matrix with diverging colors.
  function heatGrid({ rows, cols, values, format = (v) => fmt.pct(v, 1, true), rowTitle, colTitle, center = 0, scale }) {
    const flat = values.flat();
    const span = scale || Math.max(...flat.map((v) => Math.abs(v - center))) || 1;
    const grid = h("div", { class: "heat" });
    grid.style.gridTemplateColumns = `minmax(84px,auto) repeat(${cols.length}, minmax(52px,1fr))`;
    grid.append(h("div", { class: "heat-corner" }, h("span", rowTitle || ""), h("span", colTitle || "")));
    cols.forEach((c) => grid.append(h("div", { class: "heat-col" }, c)));
    rows.forEach((r, i) => {
      grid.append(h("div", { class: "heat-row" }, r));
      cols.forEach((c, j) => {
        const v = values[i][j];
        const t = Math.max(-1, Math.min(1, (v - center) / span));
        const cell = h("div", { class: "heat-cell", title: `${r} · ${c}: ${format(v)}`, tabindex: 0 }, format(v));
        cell.style.background = t >= 0 ? `rgba(52, 199, 140, ${0.08 + t * 0.55})` : `rgba(240, 97, 109, ${0.08 + -t * 0.55})`;
        grid.append(cell);
      });
    });
    return grid;
  }

  function donut(parts, { size = 132, thickness = 16, center } = {}) {
    const total = parts.reduce((a, p) => a + p.value, 0) || 1;
    const r = (size - thickness) / 2; const c = 2 * Math.PI * r;
    const svg = s("svg", { class: "donut", width: size, height: size, viewBox: `0 0 ${size} ${size}`, role: "img", "aria-label": "Allocation" });
    svg.append(s("circle", { cx: size / 2, cy: size / 2, r, class: "donut-track", "stroke-width": thickness, fill: "none" }));
    let offset = 0;
    parts.forEach((p, idx) => {
      const len = (p.value / total) * c;
      svg.append(s("circle", { cx: size / 2, cy: size / 2, r, fill: "none", stroke: p.color || PALETTE[idx % PALETTE.length], "stroke-width": thickness, "stroke-dasharray": `${Math.max(0, len - 2)} ${c}`, "stroke-dashoffset": -offset, transform: `rotate(-90 ${size / 2} ${size / 2})` }, s("title", { text: `${p.label}: ${fmt.pct(p.value / total)}` })));
      offset += len;
    });
    const wrap = h("div", { class: "donut-wrap" }, svg);
    if (center) wrap.append(h("div", { class: "donut-center" }, center));
    return wrap;
  }

  // Probability price chart for a binary market: yes price (0-1) over time + volume bars.
  function priceChart(points, opts = {}) {
    return lineChart([{ name: "YES price", values: points.map((p) => ({ x: p.t, y: p.p })), color: "var(--accent)", area: true }],
      { height: opts.height || 240, yFormat: (v) => `${Math.round(v * 100)}¢`, xFormat: opts.xFormat || ((v) => fmt.dateTime(v).replace(" UTC", "")), yMin: 0, yMax: 1, label: "YES price history", watermark: opts.watermark, legend: false });
  }

  Object.assign(ET, { h, s, icon, logo, fmt, tone, pill, statusPill, dot, delta, button, card, sourceTag, kpi, emptyState, unavailable, errorState, skeleton, callout, meter, kv, tabs, segmented, dataTable, dialog, toast, sparkline, lineChart, barChart, calibrationChart, heatGrid, donut, priceChart, PALETTE, ICONS });
})();
