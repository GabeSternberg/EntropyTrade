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
      kv([["Trading mode", "paper (simulated fills)"], ["Exchange submission", h("span", { class: "num-neg" }, "Not available")], ["Global paper halt", realInfo ? "Available in the top bar. Halting preserves accounts and evidence." : "Engaged (demo)"], ["Readiness approval", "A data-only review. It never authorizes execution or live trading."]]),
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
    const current = () => ET.mode() === "real" && ctx.isCurrent();
    const known = new Map();
    let shown = null;
    let token = null;
    let governance = null;
    async function refresh() {
      try {
        const [list, catalog] = await Promise.all([
          ET.api("/api/monitors", { fresh: true }).catch((error) => ({ error })),
          ET.api("/api/catalog", { fresh: true }).catch((error) => ({ error })),
        ]);
        if (!current()) return;
        if (list.error) { shown = null; host.replaceChildren(errorState(list.error.message, () => ET.route())); return; }
        if (token !== catalog.csrf_token) { known.clear(); token = catalog.csrf_token; }
        if (!list.length) {
          shown = null;
          if (ctx.params?.[0]) { host.replaceChildren(unavailable("Selected paper deployment not found", "The requested monitor is not recorded in this workspace. No other deployment has been selected.")); return; }
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
        if (!current()) return;
        const stamp = JSON.stringify([monitors, token || null]);
        if (stamp === shown) return;
        shown = stamp;
        const expanded = new Set([...host.querySelectorAll("details")].filter((details) => details.open).map((details) => details.querySelector("summary")?.textContent));
        const simulated = monitors.filter((x) => x.ok && x.m.paper_summary?.status === "simulated");
        const accountsUnknown = monitors.some((entry) => !entry.ok);
        const synthetic = simulated.filter((x) => x.m.paper_summary.data_kind === "synthetic").length;
        const sum = (k) => simulated.reduce((a, x) => a + Number(x.m.paper_summary[k] || 0), 0);
        const parts = [callout("Simulated paper accounting on retained evidence. Eligibility can remain blocked by missing models, fees or depth; no fill here was observed on an exchange.", "info"),
          h("div", { class: "kpi-strip" },
            kpi({ label: "Paper accounts", value: accountsUnknown ? "—" : String(simulated.length), sub: accountsUnknown ? "Some monitor accounts unavailable" : `${monitors.length} monitors · ${monitors.length - simulated.length} without committed account activity`, iconName: "paper" }),
            kpi({ label: "Cash", value: !accountsUnknown && simulated.length ? fmt.usd(sum("cash")) : "—", iconName: "database" }),
            kpi({ label: "Realized simulated P&L", value: !accountsUnknown && simulated.length ? fmt.signedUsd(sum("realized_pnl")) : "—", iconName: "check" }),
            kpi({ label: "Fees", value: !accountsUnknown && simulated.length ? fmt.usd(sum("fees")) : "—", iconName: "file" }),
            kpi({ label: "Fills / settlements", value: !accountsUnknown && simulated.length ? `${sum("fill_count")} / ${sum("settlement_count")}` : "—", iconName: "activity" }))];
        if (synthetic) parts.splice(1, 0, callout(synthetic === simulated.length
          ? "CONTROLLED SYNTHETIC accounting totals verify software behavior. They do not establish empirical trading performance."
          : "Mixed accounting totals include CONTROLLED SYNTHETIC accounts. Inspect each account's Data field before interpreting these figures.", synthetic === simulated.length ? "demo" : "warn"));
        parts.push(card({ title: "Paper accounts by monitor", flush: true, source: "real" }, dataTable({ columns: [
          { key: "id", label: "Monitor", sort: (x) => x.m.id, render: (x) => h("div", { class: "cell-market" }, h("span", { class: "cell-title" }, `${x.m.family} · ${x.m.candidate_id}`), h("span", { class: "cell-sub mono" }, fmt.short(x.m.id, 12))) },
          { key: "status", label: "Deployment", sort: (x) => x.m.status, render: (x) => statusPill(x.m.status) },
          { key: "source", label: "Research lineage", sortable: false, render: (x) => x.m.source_kind === "autonomous_research"
            ? h("div", { class: "cell-title" }, h("a", { class: "link", href: `#/research/${encodeURIComponent(x.m.research_job_id)}?tab=experiments&experiment=${encodeURIComponent(x.m.experiment_id)}` }, `Research ${fmt.short(x.m.research_job_id, 12)}`), h("div", { class: "mono muted" }, `experiment ${fmt.short(x.m.experiment_id?.replace(/^sha256:/, ""), 12)}`))
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
          if (found?.ok) {
            governance ||= paperGovernance(found.m, ctx, paperDeployment(found.m, catalog.error ? null : catalog.csrf_token));
            governance.updateAccount(paperDeployment(found.m, catalog.error ? null : catalog.csrf_token));
            parts.push(governance);
          } else parts.push(unavailable("Selected paper deployment not found", found?.error?.message || "The requested monitor is not recorded in this workspace. No other deployment has been selected."));
        } else parts.push(callout("Select an account to inspect frozen research lineage, positions, execution decisions and deployment controls.", "info"));
        parts.push(executionPanel(true));
        host.replaceChildren(...parts);
        host.querySelectorAll("details").forEach((details) => {
          if (expanded.has(details.querySelector("summary")?.textContent)) details.setAttribute("open", "");
        });
      } finally {
        if (current()) setTimeout(() => {
          if (current()) refresh().catch((error) => {
            if (current()) { shown = null; host.replaceChildren(errorState(error.message, () => ET.route())); }
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
      ...(cycle.result?.paper?.settlements || []).map((row) => ({ cycle: cycle.sequence, kind: "Official settlement", ticker: row.settlement?.market_ticker || "—", status: "settled", reason: `Result: ${row.settlement?.result || "—"} · observed ${fmt.dateTime(row.observed_outcome?.retrieved_at || row.settlement?.settled_at)}`, quantity: null })),
    ]);
    const metadata = [
      ["Source", research ? "Autonomous research experiment" : "Legacy research run"],
      research ? ["Research job", h("a", { class: "link mono", href: `#/research/${encodeURIComponent(monitor.research_job_id)}?tab=experiments&experiment=${encodeURIComponent(monitor.experiment_id)}` }, monitor.research_job_id)] : null,
      research ? ["Experiment version", h("a", { class: "link mono", href: `#/research/${encodeURIComponent(monitor.research_job_id)}?tab=experiments&experiment=${encodeURIComponent(monitor.experiment_id)}` }, monitor.experiment_id)] : null,
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
      h("p", { class: "hint" }, "Deployment lifecycle controls are separate from the global paper halt. Resuming a deployment does not release a halt; releasing a halt does not resume a deployment."),
      [account.data_kind, binding.snapshot?.data_kind, source.eligibility?.data_kind].includes("synthetic") ? callout("CONTROLLED SYNTHETIC: this account verifies software behavior. Its simulated fills and P&L are not empirical trading evidence.", "demo") : null,
      kv(metadata),
      monitor.status === "suspended" || monitor.status === "cancelled" ? callout("This deployment is stopped permanently. Its account, evidence and event history remain available for inspection.", "info") : null,
      h("div", { class: "row-actions" },
        h("a", { class: "btn ghost sm", href: `/api/monitors/${encodeURIComponent(monitor.id)}/paper`, download: `paper-${monitor.id}.json` }, "Paper account JSON"),
        h("a", { class: "btn ghost sm", href: `/api/monitors/${encodeURIComponent(monitor.id)}/export`, download: `shadow-${monitor.id}.json` }, "Execution evidence JSON"),
        button("Open workbench execution log", { variant: "ghost sm", onclick: () => ET.selectMonitor(monitor.id).catch((error) => toast(error.message, "error")) }, "external")),
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
        { key: "mode", label: "Purpose", render: (cycle) => cycle.result?.cycle_mode === "reconcile_only" ? "Settlement-only reconciliation" : "Paper observations" },
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

  // ============================================================ OWNER & READINESS
  const replaceContent = (element, ...children) => element.replaceChildren(...children.filter((child) => child !== null && child !== undefined));
  const ownerSetup = () => h("div", { class: "stack" },
    callout("Owner access is not configured. Readiness approval, rollback and halt release require a locally configured owner. Halting paper activity and revoking a proposal remain available.", "warn"),
    h("p", { class: "hint" }, "On the server, run the interactive setup command and restart with --owner-file pointing to that private file. The website cannot create owner credentials."),
    h("code", { class: "owner-setup" }, 'python -m entropytrade.api.owner init --file "$HOME/.config/entropytrade/owner.json" --owner-id owner'));
  const evidenceValue = (value) => value === null || value === undefined ? "—" : typeof value === "object" ? JSON.stringify(value) : String(value);
  function checkList(checks) {
    return h("ul", { class: "readiness-checks" }, (Array.isArray(checks) ? checks : []).map((check) => h("li",
      icon(check.passed === true ? "check" : "alert", 14), h("div", h("strong", fmt.words(check.name || "Evidence check")), h("p", { class: "hint" }, check.reason || "No assessment reason supplied")),
      statusPill(check.passed === true ? "passed" : "blocked"))));
  }
  function readinessFacts(facts) {
    if (!facts || typeof facts !== "object") return emptyState({ title: "Evidence facts are not available" });
    const scores = facts.scores || {}, account = facts.account || {};
    const interval = scores.brier_skill_interval;
    return h("details", { class: "readiness-facts" }, h("summary", "Paper observations and prospective validation"),
      kv([
        ["Evidence as of", fmt.dateTime(facts.evidence_as_of)], ["Evidence hash", facts.evidence_hash || "—"],
        ["Data kind", account.data_kind || "Not assessed"], ["Verified cycle prefix", Array.isArray(facts.paper_prefix) ? String(facts.paper_prefix.length) : "—"],
        ["Prospective assessment", fmt.words(scores.status || "Not assessed")], ["Independent events", fmt.num(scores.independent_events)], ["Independent dates", fmt.num(scores.independent_dates)],
        ["Scored observations", fmt.num(scores.observations)], ["Quote coverage", typeof scores.quote_coverage === "number" ? fmt.pct(scores.quote_coverage) : "—"],
        ["Model Brier score", fmt.num(scores.model?.brier, 4)], ["Baseline Brier score", fmt.num(scores.baseline?.brier, 4)],
        ["Model log loss", fmt.num(scores.model?.log_loss, 4)], ["Baseline log loss", fmt.num(scores.baseline?.log_loss, 4)],
        ["Brier skill interval", interval ? `${fmt.num(interval.lower, 4)} to ${fmt.num(interval.upper, 4)}` : "Not estimated"],
        ["Realized simulated P&L", fmt.signedUsd(account.realized_pnl)], ["Simulated fees", fmt.usd(account.fees)], ["Current drawdown at cost", fmt.usd(account.drawdown_at_cost)],
      ]), h("p", { class: "hint" }, account.limitation || "Paper accounting and prospective diagnostics do not authorize execution or establish future profitability."));
  }
  function auditEvents(events) {
    return events?.length ? dataTable({ columns: [
      { key: "at", label: "Time (UTC)", render: (event) => fmt.dateTime(event.at) },
      { key: "action", label: "Action", render: (event) => fmt.words(event.action || event.kind || "Event") },
      { key: "actor", label: "Recorded actor", render: (event) => evidenceValue(event.actor || event.principal || event.payload?.actor) },
      { key: "reason", label: "Reason", render: (event) => event.reason || event.note || event.payload?.reason || "—" },
    ], rows: events, sortKey: "at", dense: true }) : emptyState({ title: "No recorded events" });
  }
  function incidentTable(incidents) {
    if (!incidents?.length) return emptyState({ title: "No recorded incidents" });
    return dataTable({ columns: [
      { key: "id", label: "Incident", render: (incident) => h("div", h("strong", fmt.words(incident.kind)), h("p", { class: "mono hint" }, incident.id)) },
      { key: "state", label: "State", render: (incident) => statusPill(incident.resolved_at ? "resolved" : incident.acknowledged_at ? "acknowledged" : "open") },
      { key: "opened_at", label: "Detected", render: (incident) => fmt.dateTime(incident.opened_at) },
      { key: "evidence", label: "Recorded observation", sortable: false, render: (incident) => {
        const signals = Array.isArray(incident.evidence?.signals) ? incident.evidence.signals : [];
        const relevant = signals.filter((signal) => signal.kind === incident.kind);
        const reasons = (relevant.length ? relevant : signals).map((signal) => signal.reason).filter(Boolean);
        return h("div", h("p", reasons.join("; ") || incident.detail || incident.reason || "No recorded reason"),
          h("details", h("summary", "Incident evidence and lifecycle"), kv([["Acknowledged", fmt.dateTime(incident.acknowledged_at)], ["Resolved", fmt.dateTime(incident.resolved_at)], ["Evidence", evidenceValue(incident.evidence)]]), auditEvents(incident.events)));
      } },
    ], rows: incidents, sortKey: "opened_at", dense: true });
  }
  ET.ownerAccess = async () => {
    if (ET.mode() !== "real") return;
    const body = h("div", { class: "stack" }, skeleton(3));
    const modal = dialog({ title: "Owner access", body });
    modal.setAttribute("data-owner-control", "");
    async function load() {
      try {
        const owner = await ET.api("/api/owner", { fresh: true });
        if (ET.mode() !== "real" || !modal.open) return;
        if (!owner.configured) { replaceContent(body, ownerSetup()); return; }
        const issue = h("div", { role: "status" });
        if (owner.authenticated) {
          const out = button("Sign out", { variant: "ghost", "data-owner-logout": true, onclick: async () => {
            try { await ET.mutate("/api/owner/logout", {}, owner.csrf_token); ET.refreshSafety?.(); await ET.refreshPaperReview?.(); await load(); }
            catch (error) { issue.replaceChildren(callout(error.message, "error")); }
          } });
          replaceContent(body, callout("Signed in for readiness review and halt release. This session cannot authorize trading.", "info"), kv([["Authenticated owner", evidenceValue(owner.principal)]]), issue, out);
          return;
        }
        const password = h("input", { class: "input", type: "password", autocomplete: "current-password", "aria-label": "Owner passphrase", "data-owner-password": true });
        const signIn = button("Sign in", { variant: "primary", "data-owner-login": true });
        const submit = async () => {
          const value = password.value || "";
          password.value = "";
          if (!value) { issue.replaceChildren(callout("Enter the locally configured owner passphrase.", "warn")); return; }
          signIn.disabled = true;
          try { await ET.mutate("/api/owner/login", { password: value }, owner.csrf_token); ET.refreshSafety?.(); await ET.refreshPaperReview?.(); await load(); }
          catch (error) { issue.replaceChildren(callout(error.message, "error")); signIn.disabled = false; }
        };
        signIn.addEventListener("click", submit);
        password.addEventListener("keydown", (event) => { if (event.key === "Enter") { event.preventDefault(); submit(); } });
        modal.addEventListener("close", () => { password.value = ""; });
        replaceContent(body, h("p", "Enter the owner passphrase configured locally on this server. The session uses a private same-origin cookie; the passphrase is not saved in browser preferences."), password, issue, signIn);
        password.focus();
      } catch (error) { if (ET.mode() === "real" && modal.open) replaceContent(body, errorState(error.message, load)); }
    }
    await load();
  };
  ET.controlAccess = async () => {
    if (ET.mode() !== "real") return;
    const body = h("div", { class: "stack" }, skeleton(3));
    const modal = dialog({ title: "Global paper halt", body });
    modal.setAttribute("data-owner-control", "");
    async function load(message) {
      try {
        const [owner, control] = await Promise.all([ET.api("/api/owner", { fresh: true }), ET.api("/api/controls", { fresh: true })]);
        if (ET.mode() !== "real" || !modal.open) return;
        const issue = h("div", { role: "status" }, typeof message === "string" && message ? callout(message, "error") : null);
        const reason = h("textarea", { class: "input", rows: 2, maxlength: 500, "aria-label": "Global halt reason" });
        const releaseBlocked = control.halted && (!owner.authenticated || control.halt_file_present === true);
        const act = button(control.halted ? "Release global halt" : "Halt new paper orders", { variant: control.halted ? "ghost" : "primary", disabled: releaseBlocked, "data-global-control": control.halted ? "release" : "halt" });
        act.addEventListener("click", async () => {
          if (!reason.value?.trim()) { issue.replaceChildren(callout("Enter a reason for the audit trail.", "warn")); return; }
          act.disabled = true;
          try {
            await ET.mutate(`/api/controls/${control.halted ? "release" : "halt"}`, { reason: reason.value.trim(), ...(control.halted ? { expected_epoch: control.epoch } : {}) }, owner.csrf_token);
            ET.refreshSafety?.(); await ET.refreshPaperReview?.(); await load();
          } catch (error) { await load(error.message); }
        });
        replaceContent(body, callout(control.halted ? "Global paper halt is engaged. New paper orders are blocked; official settlement polling continues for existing positions." : "Global paper halt is released. Each deployment still requires its own eligibility and lifecycle checks.", control.halted ? "warn" : "info"),
          kv([["Control epoch", evidenceValue(control.epoch)], ["Updated", fmt.dateTime(control.updated_at)], ["Recorded reason", control.reason || "—"]]),
          h("p", { class: "hint" }, "Halting blocks new paper orders while official settlement polling continues for existing positions. Releasing a halt does not resume paused, suspended or cancelled deployments and never enables live submission."),
          control.halt_file_present === true ? callout("The server's HALT file is present. Remove it locally after review, refresh this dialog, then release the persistent halt as the owner. The website cannot remove the file.", "warn") : null,
          control.halted && !owner.configured ? ownerSetup() : control.halted && !owner.authenticated ? callout("Sign in as the configured owner to release this halt.", "warn") : null,
          reason, issue, act, h("details", h("summary", "Global control audit"), auditEvents(control.events)));
      } catch (error) { if (ET.mode() === "real" && modal.open) replaceContent(body, errorState(error.message, load)); }
    }
    await load();
  };

  function paperGovernance(monitor, ctx, account) {
    const host = h("section", { class: "stack", id: "paper-governance" });
    const panel = h("div", { class: "stack" }, skeleton(3));
    const notice = h("div", { role: "status" });
    const state = { report: null, owner: null, record: null, selectedId: ctx.query?.get("proposal") || null, loadingProposal: false, monitoring: null, tab: ctx.query?.get("tab") || "account", selectionError: null };
    const current = () => ET.mode() === "real" && ctx.isCurrent();
    const uri = `/api/monitors/${encodeURIComponent(monitor.id)}`;
    const ownerButton = button("Owner access", { variant: "ghost sm", onclick: async () => { await ET.ownerAccess(); } }, "lock");
    const refresh = button("Refresh review", { variant: "ghost sm", onclick: () => load() }, "refresh");
    const tabBar = tabs([{ key: "account", label: "Account" }, { key: "monitoring", label: "Monitoring" }, { key: "readiness", label: "Readiness" }, { key: "evidence", label: "Evidence & audit" }], state.tab, (key) => { state.tab = key; ET.updateQuery?.({ tab: key }); draw(); });
    host.append(card({ title: "Readiness & oversight", subtitle: "Human review records only. Execution remains unauthorized.", actions: h("div", { class: "row-actions" }, ownerButton, refresh) },
      callout("Readiness approval is data only: execution_authorized=false and real-money submission stays disabled. No review, rollback or halt release changes a running model.", "lock"), notice, tabBar.el, panel));
    let generation = 0, monitoringGeneration = 0;
    async function load(id) {
      if (!current()) return;
      const request = ++generation;
      refresh.disabled = true;
      if (id && id !== state.record?.id) {
        state.selectedId = id; state.record = null; state.loadingProposal = true;
        replaceContent(panel, skeleton(3));
      }
      try {
        const [report, owner] = await Promise.all([ET.api(uri + "/readiness", { fresh: true }), ET.api("/api/owner", { fresh: true })]);
        if (!current() || request !== generation) return;
        const selected = id || state.selectedId || state.record?.id || report.proposals?.[0]?.id;
        state.report = report; state.owner = owner;
        if (selected && !(report.proposals || []).some((proposal) => proposal.id === selected)) {
          state.record = null; state.selectedId = selected; state.loadingProposal = false;
          state.selectionError = "Selected readiness proposal not found for this monitor. No other proposal has been selected.";
          notice.replaceChildren(); draw(); return;
        }
        const record = selected ? await ET.api(`/api/readiness/${encodeURIComponent(selected)}`, { fresh: true }) : null;
        if (!current() || request !== generation) return;
        if (record && (record.id !== selected || record.monitor_id !== monitor.id)) {
          state.record = null; state.selectedId = selected; state.loadingProposal = false;
          state.selectionError = "Selected readiness proposal does not match this monitor and proposal identifier. No other proposal has been selected.";
          notice.replaceChildren(); draw(); return;
        }
        state.record = record; state.selectedId = selected || null; state.loadingProposal = false; state.selectionError = null;
        // Defaulting a saved proposal enriches this history entry. Only an explicit
        // selection creates a new entry, so Back can leave the deployment page.
        if (selected) ET.updateQuery?.({ proposal: selected }, { replace: !id });
        notice.replaceChildren(); draw();
      } catch (error) { if (current() && request === generation) notice.replaceChildren(errorState(error.message, () => load(id))); }
      finally { if (request === generation) { state.loadingProposal = false; refresh.disabled = false; } }
    }
    ET.refreshPaperReview = () => current() ? load() : undefined;
    function proposalPicker() {
      const proposals = state.report.proposals || [];
      if (!proposals.length) return null;
      const select = h("select", { class: "input", "aria-label": "Frozen readiness proposal" }, proposals.map((proposal) => h("option", { value: proposal.id, selected: proposal.id === state.selectedId }, `${fmt.words(proposal.status)} · ${proposal.id}`)));
      select.addEventListener("change", () => { ET.updateQuery?.({ proposal: select.value }); return load(select.value); });
      return h("label", { class: "field" }, h("span", { class: "field-label" }, "Frozen readiness proposal"), select);
    }
    async function mutation(path, body, id) {
      try { const result = await ET.mutate(path, body, state.owner.csrf_token); await load(id || result.id || result.proposal?.id); }
      catch (error) {
        if (!current()) return;
        await load(id); notice.replaceChildren(callout(error.message, "error"));
      }
    }
    function draw() {
      if (!current()) return;
      if (state.selectionError) { replaceContent(panel, unavailable("Selected readiness proposal unavailable", state.selectionError)); return; }
      if (state.tab === "account") { replaceContent(panel, account); return; }
      if (state.tab === "monitoring") { drawMonitoring(); return; }
      if (!state.report) return;
      if (state.loadingProposal) { replaceContent(panel, skeleton(3)); return; }
      if (state.tab === "monitoring") { drawMonitoring(); return; }
      if (state.tab === "evidence") {
        replaceContent(panel, proposalPicker(), state.record ? h("div", { class: "stack" }, kv([["Proposal", state.record.id], ["Revision", evidenceValue(state.record.revision)], ["State", fmt.words(state.record.status)]]), auditEvents(state.record.events)) : emptyState({ title: "No frozen readiness proposal" }),
          h("details", h("summary", "Global control audit"), auditEvents(state.report.control?.events)));
        return;
      }
      const preview = state.report.preview || {};
      const capital = h("input", { class: "input", type: "number", min: "10", max: "1000", step: ".01", value: "100.00", "aria-label": "Proposed capital in dollars" });
      const loss = h("input", { class: "input", type: "number", min: ".01", max: "50", step: ".01", value: "10.00", "aria-label": "Proposed maximum loss in dollars" });
      const freeze = button("Save readiness proposal", { variant: "primary sm", disabled: !state.owner.csrf_token, "data-readiness-freeze": true });
      freeze.addEventListener("click", async () => {
        freeze.disabled = true;
        try {
          const result = await ET.mutate(uri + "/readiness", { capital_dollars: capital.value, max_loss_dollars: loss.value }, state.owner.csrf_token);
          await load(result.id || result.proposal?.id);
        } catch (error) { if (current()) { await load(); notice.replaceChildren(callout(error.message, "error")); } }
      });
      const overview = h("div", { class: "stack" },
        preview.facts?.account?.data_kind === "synthetic" ? callout("CONTROLLED SYNTHETIC readiness diagnostics verify software behavior only. They are not authentic prospective trading evidence.", "demo") : null,
        state.owner.configured ? callout(state.owner.authenticated ? "Owner signed in. Reviews record this server's authenticated principal." : "Owner sign-in is required to approve, reject, roll back or release a global halt.", "info") : ownerSetup(),
        h("div", { class: "chip-row" }, statusPill(preview.eligible === true ? "eligible" : "blocked"), statusPill(state.report.control?.halted === true ? "halted" : "execution disabled")),
        checkList(preview.checks), readinessFacts(preview.facts), (preview.reasons || []).length ? h("ul", { class: "hyp-reasons" }, preview.reasons.map((reason) => h("li", reason))) : null,
        h("details", h("summary", "Frozen source and evidence references"), kv([
          ["Monitor", monitor.id], ["Research job", monitor.research_job_id || "Legacy source"], ["Experiment", monitor.experiment_id || "—"], ["Strategy hash", monitor.spec_hash || "—"],
          ["Model hash", monitor.model_binding?.model_ref?.version || "—"], ["Source fingerprint", preview.source_fingerprint || "—"], ["Policy hash", preview.policy_hash || "—"],
          ["Data kind", preview.facts?.data_kind || monitor.paper_summary?.data_kind || "Not assessed"], ["Paper account as of", fmt.dateTime(monitor.paper_summary?.as_of)],
        ])),
        h("p", { class: "hint" }, "Capital and maximum loss describe a future proposal only. The server derives bounded risk limits; these fields do not fund an account or change this deployment."),
        h("div", { class: "readiness-envelope" }, h("label", { class: "field" }, h("span", { class: "field-label" }, "Proposed capital ($10–$1,000)"), capital), h("label", { class: "field" }, h("span", { class: "field-label" }, "Maximum loss (up to $50 and proposed capital)"), loss)), freeze,
        h("details", h("summary", "Default preview capital envelope and server risk limits"), kv([["Capital envelope", evidenceValue(preview.capital_envelope)], ["Server-derived risk limits", evidenceValue(preview.risk_limits)]])));
      replaceContent(panel, overview, proposalPicker(), state.record ? recordCard() : emptyState({ title: "No frozen readiness proposal", body: "A proposal records the server's evidence assessment and must receive a separate owner review." }));
    }
    function recordCard() {
      const record = state.record, payload = record.payload || {};
      const base = `/api/readiness/${encodeURIComponent(record.id)}`;
      const note = h("textarea", { class: "input", rows: 2, maxlength: 1000, required: true, placeholder: "Required: reason for approving or rejecting this frozen evidence", "aria-label": "Readiness review note" });
      const reason = h("textarea", { class: "input", rows: 2, maxlength: 500, "aria-label": "Readiness revocation reason" });
      const review = (decision) => {
        if (!note.value?.trim()) { notice.replaceChildren(callout("Enter a review reason before approving or rejecting the proposal.", "warn")); note.focus(); return; }
        return mutation(base + "/review", { decision, expected_revision: record.revision, note: note.value.trim() }, record.id);
      };
      const approval = state.owner.authenticated && record.status === "proposed";
      const currentChecks = record.current_checks;
      const checks = Array.isArray(currentChecks) ? currentChecks : currentChecks?.checks;
      const currentEligible = currentChecks?.eligible === true;
      const approve = button("Approve readiness review", { variant: "primary sm", disabled: !approval || !currentEligible, "data-readiness-review": "approve", onclick: () => review("approve") });
      const reject = button("Reject readiness review", { variant: "ghost sm", disabled: !approval, "data-readiness-review": "reject", onclick: () => review("reject") });
      const revoke = button("Revoke readiness proposal", { variant: "ghost sm", disabled: record.status === "revoked", "data-readiness-revoke": true, onclick: () => {
        if (!reason.value?.trim()) { notice.replaceChildren(callout("Enter a revocation reason for the audit trail.", "warn")); return; }
        return mutation(base + "/revoke", { reason: reason.value.trim() }, record.id);
      } });
      const prior = (state.report.proposals || []).filter((proposal) => proposal.id !== record.id);
      const target = h("select", { class: "input", "aria-label": "Prior readiness proposal" }, prior.map((proposal) => h("option", { value: proposal.id }, `${fmt.words(proposal.status)} · ${proposal.id}`)));
      const rollbackReason = h("textarea", { class: "input", rows: 2, maxlength: 500, "aria-label": "Rollback proposal reason" });
      const rollback = button("Create pending rollback proposal", { variant: "ghost sm", disabled: !state.owner.authenticated || !prior.length, "data-readiness-rollback": true, onclick: async () => {
        if (!rollbackReason.value?.trim()) { notice.replaceChildren(callout("Enter a rollback reason for the audit trail.", "warn")); return; }
        await mutation(base + "/rollback", { target_proposal_id: target.value, reason: rollbackReason.value.trim() });
      } });
      return card({ title: "Frozen proposal", subtitle: record.id, className: "readiness-record" },
        h("div", { class: "chip-row" }, statusPill(record.status), h("span", { class: "mono" }, `revision ${record.revision}`)),
        h("a", { class: "btn ghost sm", href: base, download: `readiness-${record.id.replace(/^sha256:/, "")}.json` }, "Readiness record JSON"),
        payload.facts?.account?.data_kind === "synthetic" ? callout("CONTROLLED SYNTHETIC review: software evidence only. Approval does not establish authentic prospective skill.", "demo") : null,
        kv([["Source fingerprint", payload.source_fingerprint || record.source_fingerprint], ["Policy hash", payload.policy_hash], ["Control epoch at proposal", evidenceValue(payload.control_epoch)], ["Capital envelope", evidenceValue(payload.capital_envelope)], ["Server-derived risk limits", evidenceValue(payload.risk_limits)], ["Execution authorized", "False"], ["Real-money submission", "Disabled"]]),
        currentChecks?.eligible === false ? callout("This frozen proposal does not pass the current checks. A recorded review cannot bypass changed evidence or controls.", "warn") : null,
        readinessFacts(payload.facts), checkList(checks || payload.checks), h("p", { class: "hint" }, "Review uses the current server revision and checks. A stale proposal or changed evidence requires a fresh review."), note,
        h("div", { class: "row-actions" }, approve, reject), reason, revoke,
        h("details", h("summary", "Rollback from a prior server proposal"), h("div", { class: "stack" }, h("p", { class: "hint" }, "Rollback creates a fresh pending proposal from prior server references. It does not reactivate a deployment, swap its model or approve trading."), target, rollbackReason, rollback)));
    }
    async function drawMonitoring() {
      const request = ++monitoringGeneration;
      replaceContent(panel, skeleton(3));
      try {
        const result = await ET.api(uri + "/monitoring", { fresh: true });
        if (!current() || state.tab !== "monitoring" || request !== monitoringGeneration) return;
        state.monitoring = result;
        const evaluation = result.evaluation || {};
        replaceContent(panel, kv([["Evidence as of", fmt.dateTime(evaluation.evidence_as_of)], ["Assessment", fmt.words(evaluation.status || "Not assessed")]]), checkList(evaluation.checks),
          h("h4", "Observed signals"), Array.isArray(evaluation.signals) && evaluation.signals.length ? h("ul", { class: "readiness-signals" }, evaluation.signals.map((signal) => h("li", statusPill(signal.severity || "info"), h("div", h("strong", fmt.words(signal.kind || "Observation")), h("p", signal.reason || "No assessment reason supplied"), h("p", { class: "hint" }, fmt.words(signal.recommended_action || "Inspect evidence")))))) : emptyState({ title: "Awaiting monitoring observations" }),
          h("h4", "Incidents"), incidentTable(result.incidents),
          h("h4", "Investigations"), (result.investigations || []).length ? h("ul", { class: "mini-list" }, result.investigations.map((investigation) => h("li", h("div", h("strong", investigation.objective || "Read-only investigation"), h("p", { class: "hint" }, fmt.words(investigation.status))), investigation.research_job_id ? h("a", { class: "link", href: `#/research/${encodeURIComponent(investigation.research_job_id)}` }, "Open investigation research") : h("span", "Research link pending")))) : emptyState({ title: "No investigation jobs", body: "Missing observations are not proof of model drift or profitability." }));
      } catch (error) { if (current() && state.tab === "monitoring" && request === monitoringGeneration) replaceContent(panel, errorState(error.message, drawMonitoring)); }
    }
    host.updateAccount = (next) => { account = next; if (state.tab === "account") draw(); };
    draw(); load();
    return host;
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
    const allAlerts = r.alerts.ok ? r.alerts.data.alerts || [] : [];
    const monitorFilter = ctx.query?.get("monitor");
    const selectedAlert = ctx.query?.get("alert");
    const alerts = monitorFilter ? allAlerts.filter((alert) => alert.monitor_id === monitorFilter) : allAlerts;
    const selected = selectedAlert ? alerts.find((alert) => alert.id === selectedAlert) : null;
    const schedules = r.schedules.ok ? r.schedules.data : [];
    const partitions = r.partitions.ok ? r.partitions.data : [];
    const fees = r.fees.ok ? r.fees.data.versions || [] : [];
    const parts = [h("div", { class: "kpi-strip" },
      kpi({ label: "Shadow monitors", value: r.monitors.ok ? String(r.monitors.data.length) : "—", sub: r.monitors.ok ? `${r.monitors.data.filter((m) => m.status === "active").length} active` : "unavailable", iconName: "eye" }),
      kpi({ label: "Open alerts", value: r.alerts.ok ? String(allAlerts.filter((a) => !a.resolved_at).length) : "—", kind: alerts.some((a) => !a.resolved_at) ? "warn" : "", iconName: "alert" }),
      kpi({ label: "Forward validation", value: r.schedules.ok ? `${schedules.filter((s) => s.status === "active").length} active` : "—", sub: "opt-in label collection", iconName: "clock" }),
      kpi({ label: "Weather datasets", value: r.datasets.ok ? String(r.datasets.data.length) : "—", sub: "immutable snapshots", iconName: "database" }),
      kpi({ label: "Label partitions", value: r.partitions.ok ? String(partitions.length) : "—", sub: `${partitions.filter((p) => p.status === "sealed").length} sealed`, iconName: "layers" }),
      kpi({ label: "Fee versions", value: r.fees.ok ? String(fees.length) : "—", sub: fees.length ? "reviewed documents" : "missing evidence", iconName: "file", kind: fees.length ? "" : "warn" }))];
    parts.push(card({ title: "Collector health", source: "real" }, unavailable("Collector status is not exposed to the website", "Automated market and forecast collection runs as a separate process so the website can never affect it. Check it from a terminal (for example `uv run entropytrade health`). Forward-collection history under data/cache/chain is not read by this page.")));
    const alertFilter = h("div", { class: "row-actions alerts-filter" },
      h("span", { class: "hint" }, monitorFilter ? `Monitor filter: ${monitorFilter}` : "All monitors"),
      monitorFilter || selectedAlert ? h("a", { class: "link", href: "#/ops?tab=alerts" }, "Clear alert selection") : null);
    const alertBody = selectedAlert && !selected && r.alerts.ok ? unavailable("Selected alert not found", "The requested alert is not recorded for this monitor filter. No other alert has been selected.") : alerts.length ? dataTable({ columns: [
      { key: "kind", label: "Alert", render: (a) => h("a", { class: "link", "data-alert": a.id, href: `#/ops?tab=alerts&monitor=${encodeURIComponent(a.monitor_id)}&alert=${encodeURIComponent(a.id)}` }, fmt.words(a.kind)) },
      { key: "monitor_id", label: "Monitor", render: (a) => h("a", { class: "link mono", href: `#/paper/${encodeURIComponent(a.monitor_id)}?tab=monitoring` }, fmt.short(a.monitor_id)) },
      { key: "state", label: "State", sort: (a) => (a.resolved_at ? 2 : a.acknowledged_at ? 1 : 0), render: (a) => statusPill(a.resolved_at ? "resolved" : a.acknowledged_at ? "acknowledged" : "open") },
      { key: "opened_at", label: "Detected", align: "num", render: (a) => fmt.dateTime(a.opened_at) },
    ], rows: alerts, sortKey: "opened_at", dense: true, rowClass: (alert) => alert.id === selectedAlert ? "selected-alert" : "", onRow: (a) => ET.go(`#/paper/${encodeURIComponent(a.monitor_id)}?tab=monitoring`) })
      : r.alerts.ok ? emptyState({ iconName: "check", title: "No operator alerts", body: "Stale collection, repeated failures and unresolved reconciliation alerts appear here. Acknowledge them in the workbench." }) : errorState(r.alerts.error.message);
    const schedBody = schedules.length ? dataTable({ columns: [
      { key: "id", label: "Schedule", render: (s) => h("span", { class: "mono" }, fmt.short(s.config?.id, 12)) },
      { key: "status", label: "Status", render: (s) => statusPill(s.status) },
      { key: "pending", label: "Pending", align: "num", render: (s) => fmt.num(s.counts?.pending || 0) },
      { key: "verified", label: "Verified", align: "num", render: (s) => fmt.num(s.counts?.verified || 0) },
      { key: "refused", label: "Refused", align: "num", render: (s) => fmt.num(s.counts?.refused || 0) },
    ], rows: schedules, sortKey: "status", dense: true }) : r.schedules.ok ? emptyState({ iconName: "clock", title: "Forward validation not enabled", body: "Label collection is opt-in. Enable it in the Research Workbench.", action: link("Workbench", "#/workbench") }) : errorState(r.schedules.error.message);
    parts.push(h("div", { class: "grid g-1-1" }, card({ title: "Operator alerts", flush: alerts.length > 0, source: "real" }, alertFilter, alertBody), card({ title: "Settlement label coverage", subtitle: "Continuous forward validation", flush: schedules.length > 0 }, schedBody)));
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
          "The Research Workbench is disabled in Demo Mode and sends no requests until opened in Real Mode.",
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
