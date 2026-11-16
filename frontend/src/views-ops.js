"use strict";
// Paper Trading, Data & Operations and Settings views.
(function () {
  const ET = window.ET;
  const { h, icon, fmt, pill, statusPill, button, card, kpi, emptyState, unavailable, errorState, callout, meter, kv, segmented, dataTable, lineChart, barChart, donut, tabs, skeleton, dialog, dot, toast } = ET;
  function link(text, href) { return h("a", { class: "link", href }, text, icon("chevronRight", 13)); }
  function limitValue(l, v) { return l.unit === "usd" ? fmt.usd(v, 0) : l.unit === "pct" ? `${v}%` : String(v); }

  function executionPanel(realInfo) {
    const toggle = h("button", { type: "button", class: "switch", role: "switch", "aria-checked": "false", disabled: true, "aria-label": "Live trading (disabled)" }, h("span", { class: "switch-knob" }));
    return card({ title: "Execution controls", subtitle: "Real-money submission" },
      h("div", { class: "exec-row" }, h("div", h("strong", "Live trading"), h("p", { class: "hint" }, "Disabled. This server has no order-submission endpoint, and the browser never receives exchange credentials.")), toggle),
      kv([["Trading mode", "paper (simulated fills)"], ["Exchange submission", h("span", { class: "num-neg" }, "Not available")], ["Kill switch", realInfo ? "Enforced by the risk engine; not controllable here" : "Engaged (demo)"], ["Promotion to live", "Requires a recorded human approval outside the website"]]),
      h("div", { class: "row-actions" }, button("Place order", { variant: "primary", disabled: true, title: "Order entry is intentionally absent" }, "lock"), button("Flatten all", { variant: "ghost", disabled: true, title: "No live positions exist" }, "x")));
  }

  // ============================================================ PAPER
  ET.views.paper = async (root, ctx) => {
    root.append(ET.pageHeader("Paper Trading", "Simulated portfolio, orders and fills from approved strategies. No real orders are ever sent."));
    if (ET.mode() !== "demo") return paperReal(root, ctx);
    const p = ET.demo().paper;
    const now = ET.demo().now;
    root.append(h("div", { class: "kpi-strip" },
      kpi({ label: "Equity", value: fmt.usd(p.equity), deltaValue: p.equity / p.starting_balance - 1, sub: `start ${fmt.usd(p.starting_balance, 0)}`, iconName: "paper" }),
      kpi({ label: "Cash", value: fmt.usd(p.cash), sub: `${fmt.pct(p.cash / p.equity, 0)} of equity`, iconName: "database" }),
      kpi({ label: "Deployed", value: fmt.usd(p.deployed), sub: `${p.positions.length} positions`, iconName: "layers" }),
      kpi({ label: "Realized P&L", value: fmt.signedUsd(p.realized_pnl), kind: "pos", sub: "settled + closed", iconName: "check" }),
      kpi({ label: "Unrealized P&L", value: fmt.signedUsd(p.unrealized_pnl), kind: p.unrealized_pnl >= 0 ? "pos" : "neg", sub: "marked to mid", iconName: "activity" }),
      kpi({ label: "Fees paid", value: fmt.usd(p.fees_paid), sub: "certified schedule", iconName: "file" })));

    let range = "1M";
    const chartHost = h("div");
    const draw = () => { const n = { "1D": 24, "1W": 168, "1M": p.curve.length }[range]; chartHost.replaceChildren(lineChart([{ name: "Equity", values: p.curve.slice(-n), color: "var(--accent)", area: true }], { height: 260, yFormat: (v) => fmt.compactUsd(v), xFormat: range === "1D" ? (v) => fmt.time(v) : (v) => fmt.date(v).replace(/, \d{4}/, ""), baseline: p.starting_balance, watermark: "SIMULATED" })); };
    draw();
    const riskCard = card({ title: "Risk limits", subtitle: "Enforced on every simulated intent" }, h("div", { class: "limit-list" }, p.limits.map((l) => {
      const ratio = l.used / l.limit;
      return h("div", { class: "limit-row" }, h("div", { class: "limit-head" }, h("span", l.name), h("span", { class: "mono" }, `${limitValue(l, l.used)} / ${limitValue(l, l.limit)}`)), meter(l.used, l.limit, ratio > 0.8 ? "neg" : ratio > 0.6 ? "warn" : ""));
    })), h("p", { class: "hint" }, "Limits are read-only here. Strategies cannot raise their own limits."));
    root.append(h("div", { class: "grid g-2-1" }, card({ title: "Equity curve", subtitle: p.name, source: "demo", actions: segmented(["1D", "1W", "1M"].map((k) => ({ key: k, label: k })), range, (k) => { range = k; draw(); }) }, chartHost), riskCard));

    const posTable = dataTable({ columns: [
      { key: "ticker", label: "Contract", render: (x) => h("div", { class: "cell-market" }, h("a", { class: "cell-title link-plain", href: `#/markets/${encodeURIComponent(x.ticker)}` }, x.title), h("span", { class: "cell-sub mono" }, x.ticker)) },
      { key: "side", label: "Side", render: (x) => pill(x.side, x.side === "YES" ? "side-yes" : "side-no") },
      { key: "qty", label: "Qty", align: "num" },
      { key: "entry", label: "Entry", align: "num", render: (x) => fmt.cents(x.entry) },
      { key: "mark", label: "Mark", align: "num", render: (x) => fmt.cents(x.mark) },
      { key: "value", label: "Value", align: "num", render: (x) => fmt.usd(x.value) },
      { key: "pnl", label: "P&L", align: "num", render: (x) => h("span", { class: `num-${ET.tone(x.pnl)}` }, fmt.signedUsd(x.pnl)) },
      { key: "pnl_pct", label: "P&L %", align: "num", render: (x) => h("span", { class: `num-${ET.tone(x.pnl_pct)}` }, fmt.pct(x.pnl_pct, 1, true)) },
      { key: "strategy", label: "Strategy", render: (x) => h("a", { class: "link-plain muted", href: `#/lab/${x.strategy_id}` }, x.strategy) },
      { key: "close", label: "Settles", align: "num", render: (x) => h("span", { class: "muted" }, `in ${fmt.duration((x.close - now) / 1000)}`) },
    ], rows: p.positions, sortKey: "value", caption: "Open positions" });

    const panel = h("div");
    const tabBar = tabs([{ key: "orders", label: "Orders", count: p.orders.length }, { key: "fills", label: "Fills", count: p.fills.length }], "orders", (k) => {
      panel.replaceChildren(k === "orders" ? dataTable({ columns: [
        { key: "at", label: "Time (UTC)", render: (o) => h("span", { class: "mono" }, fmt.stamp(o.at)) },
        { key: "ticker", label: "Contract", render: (o) => h("span", { class: "mono" }, o.ticker) },
        { key: "side", label: "Side", render: (o) => pill(o.side, o.side === "YES" ? "side-yes" : "side-no") },
        { key: "limit", label: "Limit", align: "num", render: (o) => fmt.cents(o.limit) },
        { key: "filled", label: "Filled", align: "num", render: (o) => `${o.filled} / ${o.qty}` },
        { key: "status", label: "Status", render: (o) => statusPill(o.status) },
        { key: "reason", label: "Risk / reason", render: (o) => h("span", { class: "muted clamp" }, o.reason || "—") },
      ], rows: p.orders, sortKey: "at", dense: true, pageSize: 8, onRow: orderDialog }) : dataTable({ columns: [
        { key: "at", label: "Time (UTC)", render: (f) => h("span", { class: "mono" }, fmt.stamp(f.at)) },
        { key: "ticker", label: "Contract", render: (f) => h("span", { class: "mono" }, f.ticker) },
        { key: "action", label: "Action" }, { key: "side", label: "Side", render: (f) => pill(f.side, f.side === "YES" ? "side-yes" : "side-no") },
        { key: "qty", label: "Qty", align: "num" }, { key: "price", label: "Price", align: "num", render: (f) => fmt.cents(f.price) },
        { key: "fee", label: "Fee", align: "num", render: (f) => fmt.usd(f.fee) },
        { key: "realized", label: "Realized", align: "num", sort: (f) => f.realized ?? -1e9, render: (f) => (f.realized === null ? "—" : h("span", { class: `num-${ET.tone(f.realized)}` }, fmt.signedUsd(f.realized))) },
      ], rows: p.fills, sortKey: "at", dense: true, pageSize: 10 }));
    });
    tabBar.set("orders");
    root.append(card({ title: "Open positions", subtitle: `${p.positions.length} simulated positions`, flush: true, source: "demo" }, posTable));
    root.append(h("div", { class: "grid g-2-1" }, card({ title: "Order & fill history", actions: tabBar.el, flush: true }, panel), executionPanel(false)));
    root.append(h("div", { class: "grid g-1-1-1" },
      card({ title: "Daily P&L", subtitle: "Last 30 days", source: "demo" }, barChart(p.daily_pnl, { height: 200, yFormat: (v) => fmt.signedUsd(v, 0), xLabelEvery: 5, watermark: "SIMULATED" })),
      card({ title: "P&L by strategy", flush: true }, dataTable({ columns: [
        { key: "name", label: "Strategy", render: (s) => h("a", { class: "link-plain", href: `#/lab/${s.id}` }, s.name) },
        { key: "pnl", label: "P&L", align: "num", render: (s) => h("span", { class: `num-${ET.tone(s.pnl)}` }, fmt.signedUsd(s.pnl)) },
        { key: "trades", label: "Trades", align: "num" }, { key: "win_rate", label: "Win", align: "num", render: (s) => fmt.pct(s.win_rate, 0) },
      ], rows: p.by_strategy, sortKey: "pnl", dense: true })),
      card({ title: "Exposure by category" }, h("div", { class: "donut-row" }, donut(p.by_category.map((c) => ({ label: c.name, value: c.exposure })), { size: 120, center: h("div", h("strong", fmt.compactUsd(p.by_category.reduce((a, c) => a + c.exposure, 0))), h("span", "at cost")) }),
        h("ul", { class: "legend-list" }, p.by_category.map((c, i) => { const sw = h("span", { class: "swatch" }); sw.style.background = ET.PALETTE[i]; return h("li", sw, h("span", c.name), h("span", { class: `mono num-${ET.tone(c.pnl)}` }, fmt.signedUsd(c.pnl, 0))); }))))));
  };
  function orderDialog(o) {
    dialog({ title: `Order ${o.id}`, drawer: true, body: h("div", { class: "stack" }, h("div", { class: "chip-row" }, statusPill(o.status), pill("Simulated", "demo-tag")),
      kv([["Contract", h("span", { class: "mono" }, o.ticker)], ["Side", o.side], ["Type", o.type], ["Limit", fmt.cents(o.limit)], ["Filled", `${o.filled} / ${o.qty}`], ["Strategy", o.strategy], ["Created", fmt.dateTime(o.at)]]),
      o.reason ? callout(o.reason, o.status === "rejected" ? "error" : "warn") : null,
      h("h4", { class: "section-label" }, "Risk checks"),
      h("ul", { class: "check-list" }, ["per_trade_notional", "max_event_exposure", "total_deployed", "book_age", "spread", "min_displayed_liquidity", "fee_evidence"].map((c) => {
        const failed = o.status === "rejected" && c === "max_event_exposure" || o.status === "cancelled" && c === "book_age";
        return h("li", { class: failed ? "fail" : "" }, icon(failed ? "x" : "check", 13), h("span", { class: "mono" }, c), h("span", { class: "muted" }, failed ? "failed" : "passed"));
      }))) });
  }

  async function paperReal(root, ctx) {
    const host = h("div", { class: "stack" }, skeleton(5));
    root.append(host);
    const known = new Map();
    let shown = null;
    let token = null;
    async function refresh() {
      try {
        const [list, catalog] = await Promise.all([
          ET.api("/api/monitors", { fresh: true }).catch((error) => ({ error })),
          ET.api("/api/catalog", { fresh: true }).catch((error) => ({ error })),
        ]);
        if (!ctx.isCurrent()) return;
        if (list.error) { shown = null; host.replaceChildren(errorState(list.error.message, () => ET.route())); return; }
        if (token !== catalog.csrf_token) { known.clear(); token = catalog.csrf_token; }
        if (!list.length) {
          shown = null;
          host.replaceChildren(card({ title: "Paper accounts", source: "real" }, unavailable("No simulated paper accounts in this workspace", "A paper deployment keeps its own simulated account, fills and settlements. None exist yet. Review a research experiment for deterministic paper eligibility or inspect existing research runs.", h("div", { class: "row-actions" }, h("a", { class: "btn primary sm", href: "#/research" }, "Review autonomous research"), h("a", { class: "btn ghost sm", href: "#/workbench" }, "Research workbench"), button("Preview in Demo Mode", { variant: "ghost sm", onclick: () => ET.setMode("demo") }, "eye")))), executionPanel(true));
          return;
        }
        const monitors = await Promise.all(list.map(async (m) => {
          const prior = known.get(m.id);
          if (prior?.ok && m.status !== "active" && m.id !== ctx.params?.[0] && prior.m.status === m.status && prior.m.failures === m.failures) return prior;
          const next = await ET.api(`/api/monitors/${m.id}`, { fresh: true }).then((value) => ({ ok: true, m: value })).catch((error) => ({ ok: false, m, error }));
          known.set(m.id, next);
          return next;
        }));
        if (!ctx.isCurrent()) return;
        const stamp = JSON.stringify([monitors, token || null]);
        if (stamp === shown) return;
        shown = stamp;
        const expanded = new Set([...host.querySelectorAll("details")].filter((details) => details.open).map((details) => details.querySelector("summary")?.textContent));
        const simulated = monitors.filter((x) => x.ok && x.m.paper_summary?.status === "simulated");
        const synthetic = simulated.filter((x) => x.m.paper_summary.data_kind === "synthetic").length;
        const sum = (k) => simulated.reduce((a, x) => a + Number(x.m.paper_summary[k] || 0), 0);
        const parts = [callout("Simulated paper accounting on retained evidence. Eligibility can remain blocked by missing models, fees or depth; no fill here was observed on an exchange.", "info"),
          h("div", { class: "kpi-strip" },
            kpi({ label: "Accounts", value: String(monitors.length), sub: `${simulated.length} with simulated activity`, iconName: "paper" }),
            kpi({ label: "Cash", value: simulated.length ? fmt.usd(sum("cash")) : "—", iconName: "database" }),
            kpi({ label: "Realized simulated P&L", value: simulated.length ? fmt.signedUsd(sum("realized_pnl")) : "—", iconName: "check" }),
            kpi({ label: "Fees", value: simulated.length ? fmt.usd(sum("fees")) : "—", iconName: "file" }),
            kpi({ label: "Fills / settlements", value: simulated.length ? `${sum("fill_count")} / ${sum("settlement_count")}` : "—", iconName: "activity" }))];
        if (synthetic) parts.splice(1, 0, callout(synthetic === simulated.length
          ? "CONTROLLED SYNTHETIC accounting totals verify software behavior. They do not establish empirical trading performance."
          : "Mixed accounting totals include CONTROLLED SYNTHETIC accounts. Inspect each account's Data field before interpreting these figures.", synthetic === simulated.length ? "demo" : "warn"));
        parts.push(card({ title: "Paper accounts by monitor", flush: true, source: "real" }, dataTable({ columns: [
          { key: "id", label: "Monitor", sort: (x) => x.m.id, render: (x) => h("div", { class: "cell-market" }, h("span", { class: "cell-title" }, `${x.m.family} · ${x.m.candidate_id}`), h("span", { class: "cell-sub mono" }, fmt.short(x.m.id, 12))) },
          { key: "status", label: "Deployment", sort: (x) => x.m.status, render: (x) => statusPill(x.m.status) },
          { key: "source", label: "Research lineage", sortable: false, render: (x) => x.m.source_kind === "autonomous_research"
            ? h("div", { class: "cell-title" }, h("a", { class: "link", href: `#/research/${encodeURIComponent(x.m.research_job_id)}` }, `Research ${fmt.short(x.m.research_job_id, 12)}`), h("div", { class: "mono muted" }, `experiment ${fmt.short(x.m.experiment_id?.replace(/^sha256:/, ""), 12)}`))
            : h("span", { class: "muted" }, "Legacy research run") },
          { key: "account", label: "Account", sort: (x) => x.m.paper_summary?.status, render: (x) => (x.ok ? statusPill(x.m.paper_summary?.status || "none") : statusPill("refused")) },
          { key: "kind", label: "Data", render: (x) => (x.m.paper_summary?.data_kind ? statusPill(x.m.paper_summary.data_kind) : "—") },
          { key: "cash", label: "Cash", align: "num", sort: (x) => Number(x.m.paper_summary?.cash ?? 0), render: (x) => fmt.usd(x.m.paper_summary?.cash) },
          { key: "pnl", label: "Realized", align: "num", sort: (x) => Number(x.m.paper_summary?.realized_pnl ?? 0), render: (x) => fmt.signedUsd(x.m.paper_summary?.realized_pnl) },
          { key: "fills", label: "Fills", align: "num", sort: (x) => x.m.paper_summary?.fill_count ?? 0, render: (x) => fmt.num(x.m.paper_summary?.fill_count) },
          { key: "drawdown", label: "Current drawdown at cost", align: "num", sort: (x) => Number(x.m.paper_summary?.drawdown_at_cost ?? -1), render: (x) => fmt.usd(x.m.paper_summary?.drawdown_at_cost) },
          { key: "note", label: "Note", sortable: false, render: (x) => h("span", { class: "muted clamp" }, x.ok ? (x.m.paper_summary?.reason || x.m.paper_summary?.limitation || "—") : x.error.message) },
        ], rows: monitors, sortKey: "id", onRow: (x) => ET.go(`#/paper/${encodeURIComponent(x.m.id)}`) })));
        const selected = ctx.params?.[0];
        if (selected) {
          const found = monitors.find((x) => x.m.id === selected);
          parts.push(found?.ok ? paperDeployment(found.m, catalog.error ? null : catalog.csrf_token) : errorState(found?.error?.message || "Paper deployment not found", () => ET.go("#/paper")));
        } else parts.push(callout("Select an account to inspect frozen research lineage, positions, execution decisions and deployment controls.", "info"));
        parts.push(executionPanel(true));
        host.replaceChildren(...parts);
        host.querySelectorAll("details").forEach((details) => {
          if (expanded.has(details.querySelector("summary")?.textContent)) details.setAttribute("open", "");
        });
      } finally {
        if (ctx.isCurrent()) setTimeout(() => {
          if (ctx.isCurrent()) refresh().catch((error) => {
            if (ctx.isCurrent()) { shown = null; host.replaceChildren(errorState(error.message, () => ET.route())); }
          });
        }, 5000);
      }
    }
    await refresh();
  }

  function paperDeployment(monitor, csrf) {
    const research = monitor.source_kind === "autonomous_research";
    const source = monitor.source_ref || {};
    const binding = monitor.model_binding || {};
    const model = binding.model_ref || monitor.spec?.model_ref || {};
    const account = monitor.paper_summary || {};
    const issue = h("div", { class: "research-issue" });
    const controls = h("div", { class: "row-actions" });
    const actions = monitor.status === "active" ? ["pause"] : monitor.status === "paused" ? ["resume"] : [];
    if (research && ["active", "paused"].includes(monitor.status)) actions.push("suspend");
    if (research && monitor.status !== "cancelled") actions.push("cancel");
    const names = { pause: "Pause deployment", resume: "Resume deployment", suspend: "Suspend deployment", cancel: "Cancel deployment" };
    const run = async (action) => {
      issue.replaceChildren();
      const buttons = [...controls.querySelectorAll("button")];
      buttons.forEach((b) => { b.disabled = true; });
      try {
        await ET.mutate(`/api/monitors/${encodeURIComponent(monitor.id)}/${action}`, {}, csrf);
        ET.route();
      } catch (error) {
        issue.append(callout(error.message, "error"));
        buttons.forEach((b) => { b.disabled = !csrf; });
      }
    };
    controls.append(...actions.map((action) => button(names[action], { variant: "ghost sm", disabled: !csrf, "data-paper-action": action, onclick: () => run(action) }, action === "resume" ? "play" : action === "pause" ? "pause" : "x")));
    const cycles = monitor.cycles || [];
    const executions = cycles.flatMap((cycle) => [
      ...(cycle.result?.paper?.decisions || []).map((decision) => ({ cycle: cycle.sequence, kind: "Decision / risk", ticker: decision.ticker, status: decision.status, reason: (decision.reasons || []).join(" · "), quantity: null })),
      ...(cycle.result?.paper?.executions || []).map((execution) => ({ cycle: cycle.sequence, kind: "Execution", ticker: execution.ticker, status: execution.status, reason: execution.reason || "—", quantity: execution.order?.filled_quantity })),
    ]);
    const metadata = [
      ["Source", research ? "Autonomous research experiment" : "Legacy research run"],
      research ? ["Research job", h("a", { class: "link mono", href: `#/research/${encodeURIComponent(monitor.research_job_id)}` }, monitor.research_job_id)] : null,
      research ? ["Experiment version", h("span", { class: "mono" }, monitor.experiment_id)] : null,
      ["Strategy version", h("span", { class: "mono" }, monitor.spec_hash)],
      ["Model version", h("span", { class: "mono" }, model.version || binding.model_hash || "No frozen model binding")],
      source.source_hash ? ["Deployment source version", h("span", { class: "mono" }, source.source_hash)] : null,
      research ? ["Trained decision time", fmt.decisionPoint(binding.snapshot?.selected_schedule)] : ["Poll interval", `${monitor.interval_seconds} seconds`],
      research && binding.snapshot?.series_locations ? ["Decision timezone", [...new Set(Object.values(binding.snapshot.series_locations).map((location) => location.timezone).filter(Boolean))].join(", ") || "No recorded timezone"] : null,
      research ? ["Next scheduled decision", `${fmt.dateTime(monitor.next_at)}${monitor.status === "active" ? "" : " (stopped)"}`] : ["Next eligible poll", monitor.status === "active" ? fmt.dateTime(monitor.next_at) : "Collection is stopped"],
      ["Durable cycles", fmt.num(monitor.cycle_count)],
      ["Consecutive failures", fmt.num(monitor.failures)],
    ];
    return card({ title: "Paper deployment", subtitle: monitor.id, className: "paper-deployment", id: "paper-deployment", actions: controls },
      h("div", { "data-paper-monitor": monitor.id, "data-paper-status": monitor.status }, statusPill(monitor.status)), issue,
      [account.data_kind, binding.snapshot?.data_kind, source.eligibility?.data_kind].includes("synthetic") ? callout("CONTROLLED SYNTHETIC: this account verifies software behavior. Its simulated fills and P&L are not empirical trading evidence.", "demo") : null,
      kv(metadata),
      monitor.status === "suspended" || monitor.status === "cancelled" ? callout("This deployment is stopped permanently. Its account, evidence and event history remain available for inspection.", "info") : null,
      h("div", { class: "row-actions" },
        h("a", { class: "btn ghost sm", href: `/api/monitors/${encodeURIComponent(monitor.id)}/paper`, download: `paper-${monitor.id}.json` }, "Paper account JSON"),
        h("a", { class: "btn ghost sm", href: `/api/monitors/${encodeURIComponent(monitor.id)}/export`, download: `shadow-${monitor.id}.json` }, "Execution evidence JSON"),
        button("Open workbench execution log", { variant: "ghost sm", onclick: () => { ET.go("#/workbench"); if (typeof window.selectMonitor === "function") window.selectMonitor(monitor.id, true).catch(() => {}); } }, "external")),
      account.status === "simulated" ? h("div", { class: "stack" },
        kv([
          ["Account as of", fmt.dateTime(account.as_of)],
          ["Cash", fmt.usd(account.cash)], ["Available cash", fmt.usd(account.available_cash)],
          ["Equity at cost", fmt.usd(account.equity_at_cost)], ["Realized simulated P&L", fmt.signedUsd(account.realized_pnl)],
          ["Fees paid", fmt.usd(account.fees)], ["Fills / settlements", `${account.fill_count} / ${account.settlement_count}`],
          account.drawdown_at_cost !== undefined ? ["Current drawdown at cost", fmt.usd(account.drawdown_at_cost)] : null,
          account.peak_equity_at_cost !== undefined ? ["Peak equity at cost", fmt.usd(account.peak_equity_at_cost)] : null,
        ]),
        h("p", { class: "hint" }, account.limitation),
        h("h4", { class: "section-label" }, "Open simulated positions"),
        dataTable({ columns: [
          { key: "ticker", label: "Contract", render: (position) => h("span", { class: "mono" }, position.contract?.market_ticker || "—") },
          { key: "side", label: "Side", render: (position) => statusPill(position.contract?.side || "—") },
          { key: "quantity", label: "Quantity", align: "num", render: (position) => fmt.num(position.quantity, 2) },
          { key: "total_cost", label: "Cost", align: "num", render: (position) => fmt.usd(position.total_cost) },
          { key: "fees_paid", label: "Fees", align: "num", render: (position) => fmt.usd(position.fees_paid) },
        ], rows: account.positions || [], sortKey: "total_cost", dense: true, empty: emptyState({ title: "No open simulated positions" }) })) : callout(account.reason || "No committed paper cycle; no retrospective fills have been added.", "info"),
      h("h4", { class: "section-label" }, "Execution and risk events"),
      dataTable({ columns: [
        { key: "cycle", label: "Cycle", align: "num" }, { key: "kind", label: "Kind" },
        { key: "ticker", label: "Contract", render: (event) => h("span", { class: "mono" }, event.ticker) },
        { key: "status", label: "Status", render: (event) => statusPill(event.status) },
        { key: "quantity", label: "Filled", align: "num", render: (event) => fmt.num(event.quantity, 2) },
        { key: "reason", label: "Reason", sortable: false, render: (event) => h("span", { class: "research-reasons" }, event.reason) },
      ], rows: executions, sortKey: "cycle", dense: true, pageSize: 20, empty: emptyState({ title: "No execution or risk events yet", body: "Only committed incoming-data cycles produce decisions and simulated fills." }) }),
      h("details", { class: "hyp-more" }, h("summary", `Collection cycles (${cycles.length} shown)`), dataTable({ columns: [
        { key: "sequence", label: "Cycle", align: "num" },
        { key: "status", label: "Status", render: (cycle) => statusPill(cycle.status) },
        { key: "finished_at", label: "Finished", render: (cycle) => fmt.dateTime(cycle.finished_at) },
        { key: "detail", label: "Detail", sortable: false },
      ], rows: cycles, sortKey: "sequence", dense: true })),
      h("details", { class: "hyp-more" }, h("summary", "Deployment event history"), dataTable({ columns: [
        { key: "at", label: "Time", render: (event) => fmt.dateTime(event.at) },
        { key: "action", label: "Event", sortable: false },
      ], rows: monitor.events || [], sortKey: "at", dense: true })),
      h("details", { class: "hyp-more" }, h("summary", "Frozen strategy, risk and model references"), kv([
        ["Feature binding", binding.kind || "—"],
        ["Binding version", binding.binding_hash || "—"],
        ["Position sizing", JSON.stringify(monitor.spec?.position_sizing || monitor.spec?.sizing || {})],
        ["Risk limits", JSON.stringify(source.eligibility?.risk_limits || cycles[0]?.result?.risk_limits || "No recorded risk policy")],
        ["Risk overrides", monitor.spec?.risk_overrides_allowed || "Not available"],
      ])));
  }

  // ============================================================ OPERATIONS
  ET.views.ops = async (root, ctx) => {
    root.append(ET.pageHeader("Data & Operations", "Collector health, coverage, data quality, evidence snapshots and storage runway."));
    if (ET.mode() !== "demo") return opsReal(root, ctx);
    const d = ET.demo();
    const ok = d.collectors.filter((c) => c.status === "ok").length;
    const runwayDays = (d.storage.capacity - d.storage.used) / d.storage.growth_per_day;
    root.append(h("div", { class: "kpi-strip" },
      kpi({ label: "Collectors healthy", value: `${ok} / ${d.collectors.length}`, kind: ok === d.collectors.length ? "pos" : "warn", sub: "1 degraded · 1 stale", iconName: "server" }),
      kpi({ label: "Receipts (24h)", value: fmt.compact(d.collectors.reduce((a, c) => a + c.receipts_24h, 0)), sub: "append-only", iconName: "database" }),
      kpi({ label: "Forecast coverage", value: fmt.pct(d.coverage.reduce((a, c) => a + c.forecast, 0) / d.coverage.length, 0), sub: "7 cities · 60 days", iconName: "globe" }),
      kpi({ label: "Settlement labels", value: fmt.pct(d.coverage.reduce((a, c) => a + c.settlement, 0) / d.coverage.length, 0), sub: `${d.coverage.reduce((a, c) => a + c.pending_labels, 0)} pending`, iconName: "flag" }),
      kpi({ label: "Open DQ alerts", value: String(d.quality_alerts.filter((a) => !a.resolved).length), kind: "warn", iconName: "alert" }),
      kpi({ label: "Storage runway", value: `${Math.round(runwayDays)} days`, sub: `${fmt.bytes(d.storage.growth_per_day)}/day`, iconName: "hardDrive", kind: runwayDays < 90 ? "warn" : "" })));
    root.append(card({ title: "Collectors", subtitle: "Read-only acquisition processes · last 24 hourly checks", flush: true, source: "demo" }, dataTable({ columns: [
      { key: "name", label: "Source", render: (c) => h("div", { class: "cell-market" }, h("span", { class: "cell-title" }, dot(c.status === "ok" ? "pos" : c.status === "degraded" ? "warn" : "neg"), c.name), h("span", { class: "cell-sub" }, c.cadence)) },
      { key: "status", label: "Status", render: (c) => statusPill(c.status === "ok" ? "healthy" : c.status) },
      { key: "last_success", label: "Last success", align: "num", render: (c) => fmt.ago(c.last_success, d.now) },
      { key: "uptime", label: "24h", sortable: false, render: (c) => h("div", { class: "uptime" }, c.history.map((x) => h("span", { class: `up ${x ? "ok" : "miss"}` }))) },
      { key: "receipts_24h", label: "Receipts", align: "num", render: (c) => fmt.num(c.receipts_24h) },
      { key: "error_rate", label: "Errors", align: "num", render: (c) => h("span", { class: c.error_rate > 0.05 ? "num-neg" : "" }, fmt.pct(c.error_rate, 1)) },
      { key: "latency_ms", label: "p95 latency", align: "num", render: (c) => (c.latency_ms === null ? "—" : `${c.latency_ms} ms`) },
    ], rows: d.collectors, sortKey: "name", sortDir: "asc" })));
    root.append(h("div", { class: "grid g-2-1" },
      card({ title: "Collection history", subtitle: "Receipts per day · all sources", source: "demo" }, barChart(d.collection_history.map((x) => ({ ...x, tone: x.note ? "warn" : "accent", series: "Receipts" })), { height: 220, signed: false, yFormat: (v) => fmt.compact(v), xLabelEvery: 2, watermark: "SIMULATED" })),
      card({ title: "Data-quality alerts" }, h("ol", { class: "feed" }, d.quality_alerts.map((a) => h("li", { class: `feed-item ${a.resolved ? "resolved" : ""}` }, h("span", { class: `feed-icon ${a.severity}` }, icon(a.severity === "info" ? "info" : "alert", 14)), h("div", { class: "feed-body" }, h("span", { class: "feed-title" }, a.title, a.resolved ? pill("resolved", "status pos") : null), h("span", { class: "feed-detail" }, a.detail)), h("time", { class: "feed-time" }, fmt.ago(a.at, d.now))))))));
    root.append(h("div", { class: "grid g-1-1-1" },
      card({ title: "Forecast & settlement coverage", flush: true }, dataTable({ columns: [
        { key: "city", label: "City" },
        { key: "forecast", label: "Forecasts", align: "num", render: (c) => h("div", { class: "prob" }, h("span", { class: "mono" }, fmt.pct(c.forecast, 0)), meter(c.forecast, 1, "accent")) },
        { key: "settlement", label: "Labels", align: "num", render: (c) => h("div", { class: "prob" }, h("span", { class: "mono" }, fmt.pct(c.settlement, 0)), meter(c.settlement, 1, c.settlement < 0.8 ? "warn" : "")) },
        { key: "pending_labels", label: "Pending", align: "num" },
      ], rows: d.coverage, sortKey: "city", sortDir: "asc", dense: true })),
      card({ title: "Snapshots & evidence", flush: true }, h("ul", { class: "mini-list pad" }, d.snapshots.map((x) => h("li", h("div", { class: "mini-main" }, h("span", { class: "mini-title" }, x.kind), h("span", { class: "mini-sub mono" }, `sha256:${x.sha256.slice(0, 16)}… · ${fmt.num(x.records)} records · ${fmt.bytes(x.size)}`)), statusPill(x.status))))),
      card({ title: "Storage runway", subtitle: `${fmt.bytes(d.storage.used)} of ${fmt.bytes(d.storage.capacity)}` },
        h("div", { class: "runway" }, h("strong", { class: "stat-big" }, `${Math.round(runwayDays)} days`), h("span", { class: "muted" }, "until capacity at current growth")),
        meter(d.storage.used, d.storage.capacity, d.storage.used / d.storage.capacity > 0.8 ? "neg" : "accent"),
        h("ul", { class: "legend-list" }, d.storage.breakdown.map(([name, bytes], i) => { const sw = h("span", { class: "swatch" }); sw.style.background = ET.PALETTE[i]; return h("li", sw, h("span", name), h("span", { class: "mono" }, fmt.bytes(bytes))); })),
        callout("Storage runway is a V1 gate: a human decision on retention is required.", "warn"))));
  };

  async function opsReal(root, ctx) {
    const host = h("div", { class: "stack" }, skeleton(6));
    root.append(host);
    const r = await ET.apiAll({ alerts: "/api/alerts", schedules: "/api/weather/schedules", datasets: "/api/weather/datasets", partitions: "/api/weather/label-partitions", fees: "/api/fees", monitors: "/api/monitors" });
    if (!ctx.isCurrent()) return;
    const alerts = r.alerts.ok ? r.alerts.data.alerts : [];
    const schedules = r.schedules.ok ? r.schedules.data : [];
    const partitions = r.partitions.ok ? r.partitions.data : [];
    const fees = r.fees.ok ? r.fees.data.versions || [] : [];
    const parts = [h("div", { class: "kpi-strip" },
      kpi({ label: "Shadow monitors", value: r.monitors.ok ? String(r.monitors.data.length) : "—", sub: r.monitors.ok ? `${r.monitors.data.filter((m) => m.status === "active").length} active` : "unavailable", iconName: "eye" }),
      kpi({ label: "Open alerts", value: String(alerts.filter((a) => !a.resolved_at).length), kind: alerts.some((a) => !a.resolved_at) ? "warn" : "", iconName: "alert" }),
      kpi({ label: "Forward validation", value: schedules.length ? `${schedules.filter((s) => s.status === "active").length} active` : "Off", sub: "opt-in label collection", iconName: "clock" }),
      kpi({ label: "Weather datasets", value: r.datasets.ok ? String(r.datasets.data.length) : "—", sub: "immutable snapshots", iconName: "database" }),
      kpi({ label: "Label partitions", value: String(partitions.length), sub: `${partitions.filter((p) => p.status === "sealed").length} sealed`, iconName: "layers" }),
      kpi({ label: "Fee versions", value: String(fees.length), sub: fees.length ? "reviewed documents" : "missing evidence", iconName: "file", kind: fees.length ? "" : "warn" }))];
    parts.push(card({ title: "Collector health", source: "real" }, unavailable("Collector status is not exposed to the website", "Automated market and forecast collection runs as a separate process so the website can never affect it. Check it from a terminal (for example `uv run entropytrade health`). Forward-collection history under data/cache/chain is not read by this page.")));
    const alertBody = alerts.length ? dataTable({ columns: [
      { key: "kind", label: "Alert", render: (a) => fmt.words(a.kind) },
      { key: "monitor_id", label: "Monitor", render: (a) => h("span", { class: "mono" }, fmt.short(a.monitor_id)) },
      { key: "state", label: "State", sort: (a) => (a.resolved_at ? 2 : a.acknowledged_at ? 1 : 0), render: (a) => statusPill(a.resolved_at ? "resolved" : a.acknowledged_at ? "acknowledged" : "open") },
      { key: "opened_at", label: "Detected", align: "num", render: (a) => fmt.dateTime(a.opened_at) },
    ], rows: alerts, sortKey: "opened_at", dense: true, onRow: (a) => { ET.go("#/workbench"); if (typeof window.selectMonitor === "function") window.selectMonitor(a.monitor_id, true).catch(() => {}); } })
      : r.alerts.ok ? emptyState({ iconName: "check", title: "No operator alerts", body: "Stale collection, repeated failures and unresolved reconciliation alerts appear here. Acknowledge them in the workbench." }) : errorState(r.alerts.error.message);
    const schedBody = schedules.length ? dataTable({ columns: [
      { key: "id", label: "Schedule", render: (s) => h("span", { class: "mono" }, fmt.short(s.config?.id, 12)) },
      { key: "status", label: "Status", render: (s) => statusPill(s.status) },
      { key: "pending", label: "Pending", align: "num", render: (s) => fmt.num(s.counts?.pending || 0) },
      { key: "verified", label: "Verified", align: "num", render: (s) => fmt.num(s.counts?.verified || 0) },
      { key: "refused", label: "Refused", align: "num", render: (s) => fmt.num(s.counts?.refused || 0) },
    ], rows: schedules, sortKey: "status", dense: true }) : r.schedules.ok ? emptyState({ iconName: "clock", title: "Forward validation not enabled", body: "Label collection is opt-in. Enable it in the Research Workbench.", action: link("Workbench", "#/workbench") }) : errorState(r.schedules.error.message);
    parts.push(h("div", { class: "grid g-1-1" }, card({ title: "Operator alerts", flush: alerts.length > 0, source: "real" }, alertBody), card({ title: "Settlement label coverage", subtitle: "Continuous forward validation", flush: schedules.length > 0 }, schedBody)));
    const partBody = partitions.length ? dataTable({ columns: [
      { key: "partition_id", label: "Partition", render: (p) => h("span", { class: "mono" }, p.partition_id) },
      { key: "status", label: "Status", render: (p) => statusPill(p.status) },
      { key: "requests", label: "Requests", align: "num", render: (p) => `${fmt.num(p.requests)} / ${fmt.num(p.request_limit)}` },
    ], rows: partitions, sortKey: "partition_id", dense: true }) : emptyState({ iconName: "layers", title: "No label partitions", body: "Sealed label-evidence partitions appear after settlement labels are acquired." });
    const feeBody = fees.length ? h("ul", { class: "mini-list" }, fees.map((v) => h("li", h("div", { class: "mini-main" }, h("span", { class: "mini-title" }, v.evidence_kind === "controlled" ? "CONTROLLED fixture · software evidence only" : "Authentic reviewed source"), h("span", { class: "mini-sub mono" }, `${fmt.short(v.version?.replace("sha256:", ""), 16)} · available ${fmt.dateTime(v.available_at)}`)), statusPill(v.policy ? "reviewed" : "refused"))))
      : r.fees.ok ? emptyState({ iconName: "file", title: "Missing fee evidence", body: "Costed shadow intentions and real backtests refuse without applicable reviewed fee documents." }) : errorState(r.fees.error.message);
    parts.push(h("div", { class: "grid g-1-1-1" }, card({ title: "Label evidence partitions", flush: partitions.length > 0 }, partBody), card({ title: "Fee evidence snapshots" }, feeBody),
      card({ title: "Storage runway" }, unavailable("Storage runway is not measured here", "The evidence storage runway decision is an open V1 gate that requires a human attestation. Disk usage of collector archives is not read by the website."))));
    host.replaceChildren(...parts);
  }

  // ============================================================ SETTINGS
  const SECTIONS = [["general", "General", "sliders"], ["data", "Data mode", "eye"], ["providers", "Research providers", "sparkles"], ["sources", "Data sources", "database"], ["risk", "Risk & approvals", "shield"], ["safety", "Safety boundaries", "lock"]];
  ET.views.settings = async (root, ctx) => {
    root.append(ET.pageHeader("Settings", "Preferences and read-only configuration status. Risk limits, fees and gates cannot be changed from the browser."));
    const current = SECTIONS.some(([k]) => k === ctx.params[0]) ? ctx.params[0] : "general";
    const nav = h("nav", { class: "settings-nav", "aria-label": "Settings sections" }, SECTIONS.map(([k, label, ic]) => h("a", { href: `#/settings/${k}`, class: "settings-link", "aria-current": k === current ? "page" : "false" }, icon(ic, 15), label)));
    const body = h("div", { class: "settings-body stack" });
    root.append(h("div", { class: "settings" }, nav, body));
    const demo = ET.mode() === "demo";
    if (current === "general") {
      const density = segmented([{ key: "comfortable", label: "Comfortable" }, { key: "compact", label: "Compact" }], ET.prefs.get("density", "comfortable"), (k) => { ET.prefs.set("density", k); toast("Density updated", "ok"); });
      const collapsed = h("input", { type: "checkbox", checked: !!ET.prefs.get("collapsed", false) });
      collapsed.addEventListener("change", () => ET.prefs.set("collapsed", collapsed.checked));
      body.append(card({ title: "Appearance", subtitle: "Stored in this browser only" },
        settingRow("Table density", "Compact reduces row height across tables.", density),
        settingRow("Collapse sidebar", "Show navigation icons only.", h("label", { class: "check toggle" }, collapsed, h("span", "Collapsed"))),
        settingRow("Time zone", "All clocks are displayed in UTC to match receipt and settlement times.", pill("UTC", "chip"))));
    } else if (current === "data") {
      body.append(card({ title: "Data source mode" },
        settingRow("Current mode", demo ? "Fictional sample data generated in the browser." : "Authentic data from this workspace's local API.", segmented([{ key: "real", label: "Real" }, { key: "demo", label: "Demo" }], ET.mode(), (k) => ET.setMode(k))),
        h("ul", { class: "check-list" }, [
          "Demo data is generated in the browser from a fixed seed and is labeled “Simulated” throughout.",
          "Demo data never leaves the browser: Demo Mode views make no API requests and offer no write actions.",
          "The Research Workbench always uses the real workspace, regardless of this setting.",
          "Real Mode shows honest empty, unavailable and error states when data is missing.",
        ].map((t) => h("li", icon("check", 13), h("span", t))))));
    } else if (current === "providers") {
      if (demo) body.append(card({ title: "Research providers", source: "demo" }, ET.demo().providers.map((p) => settingRow(p.name, p.detail, statusPill(p.status === "ready" || p.status === "configured" ? "ok" : "not configured")))));
      else {
        const c = await ET.api("/api/catalog").catch((error) => ({ error }));
        if (!ctx.isCurrent()) return;
        body.append(card({ title: "Research providers", source: "real" }, c.error ? errorState(c.error.message) : [
          settingRow("Local templates", "Deterministic formulation. No provider credentials.", statusPill("ok")),
          settingRow("Provider research", c.provider_enabled ? `Configured on the server: ${c.research_provider?.provider} / ${c.research_provider?.model_name}. Each run needs fresh consent in the workbench.` : "Not configured. Start the server with --research-provider and --research-model to enable it.", statusPill(c.provider_enabled ? "configured" : "not configured")),
          callout("Research credentials are separate from exchange credentials and are never accepted by the browser.", "lock")]));
      }
    } else if (current === "sources") {
      const rows = [["Kalshi public market data", "Read-only listings and order books", "collector"], ["Open-Meteo", "Forecast vintages", "public"], ["National Weather Service", "Gridpoint forecasts & climate reports", "public"], ["The Weather Company", "Official scalar highs for settlement labels", "labels"], ["Coinbase", "BTC-USD spot covariate (never a settlement label)", "public"]];
      body.append(card({ title: "Data sources", source: demo ? "demo" : "real" }, rows.map(([name, detail, kind]) => settingRow(name, detail, demo ? statusPill(name.startsWith("National") ? "degraded" : "ok") : pill(kind === "collector" ? "Separate collector" : kind === "labels" ? "Opt-in in workbench" : "Fetched by research runs", "chip")))));
    } else if (current === "risk") {
      if (demo) {
        const p = ET.demo().paper;
        body.append(card({ title: "Risk limits", subtitle: "Paper account · read-only", source: "demo" }, p.limits.map((l) => settingRow(l.name, `${limitValue(l, l.used)} used`, h("span", { class: "mono" }, limitValue(l, l.limit))))));
        body.append(gatesCard(ET.demo().gates));
      } else {
        const g = await ET.api("/api/v1-gates").catch((error) => ({ error }));
        if (!ctx.isCurrent()) return;
        body.append(card({ title: "Risk limits" }, unavailable("Limits are enforced by the risk engine, not edited here", "Per-trade, per-event, deployed, bankroll, loss, drawdown, book-age, spread and liquidity caps are applied to every intent. Strategies cannot raise their own limits, and the website exposes no limit editor.")));
        body.append(g.error ? card({ title: "V1 acceptance gates" }, errorState(g.error.message)) : gatesCard(g.gates, g));
      }
    } else {
      body.append(card({ title: "Safety boundaries", subtitle: "Properties of this server, not preferences" }, h("ul", { class: "check-list" }, [
        "Binds 127.0.0.1 only; requests must be same-origin localhost.",
        "Writes require a per-process CSRF token; this redesign adds no new write endpoints.",
        "No order-submission endpoint exists; submission_enabled is always false.",
        "Exchange credentials are never accepted by the browser; research credentials are server-side and opt-in per run.",
        "Strict Content-Security-Policy: same-origin scripts and styles only, no CDN or external fonts.",
        "Protected holdout data stays closed; point-in-time clocks are preserved.",
      ].map((t) => h("li", icon("shield", 13), h("span", t))))));
    }
  };
  function settingRow(title, detail, control) { return h("div", { class: "setting-row" }, h("div", h("strong", title), detail ? h("p", { class: "hint" }, detail) : null), h("div", { class: "setting-control" }, control)); }
  function gatesCard(gates, report) {
    const attested = gates.filter((g) => g.status === "attested").length;
    return card({ title: "V1 acceptance gates", subtitle: `${attested} of ${gates.length} attested · read-only`, source: report ? "real" : "demo" },
      h("ul", { class: "gate-list wide" }, gates.map((g) => h("li", { class: `gate ${g.status}` }, icon(g.status === "attested" ? "check" : g.status === "invalid" ? "alert" : "clock", 14), h("span", g.title), h("span", { class: "gate-ref" }, g.detail)))),
      h("p", { class: "hint" }, "A gate is attested only by a human-written file with matching evidence hashes under data/acceptance. This page never attests gates, certifies fees or enables trading."));
  }
})();
