"use strict";
// Autonomous research jobs. Real Mode reads /api/research only; Demo Mode shows labeled
// sample jobs from demo-data.js. Nothing on this page can place an order.
(function () {
  const ET = window.ET;
  const { h, fmt, pill, statusPill, button, card, callout, kv, dataTable, kpi, tabs, meter, icon } = ET;

  const STEPS = [
    ["queued", "Saved"],
    ["generating_hypotheses", "Hypotheses"],
    ["planning_data", "Requirements & inventory"],
    ["acquiring_data", "Acquisition"],
    ["registering_features", "Features"],
    ["awaiting_observations", "Awaiting evidence"],
    ["evaluated", "Evaluated"],
  ];
  const ACTIVE = new Set(["queued", "generating_hypotheses", "planning_data", "acquiring_data", "registering_features", "recoverable_error"]);
  const RESUMABLE = new Set(["evaluated", "awaiting_observations", "awaiting_authorization", "recoverable_error"]);
  const TERMINAL = new Set(["failed", "cancelled"]);
  const HYP_TONE = {
    backtest_eligible: "pos", needs_more_data: "warn", awaiting_new_observations: "warn",
    awaiting_authorization: "warn", proposed: "", duplicate: "", rejected: "neg",
    permanently_unsupported: "neg", insufficient_evidence: "neg",
  };
  const REQ_TONE = { satisfied: "pos", partial: "warn", acquiring: "warn", awaiting_observations: "warn", awaiting_authorization: "warn", missing: "neg", unobtainable: "neg" };
  const words = (value) => fmt.words(String(value || "").replace(/_/g, " "));
  const tonePill = (value, tones) => pill(words(value), `status ${tones[value] || ""}`.trim(), { "data-status": value });

  async function post(csrf, path, body = {}) {
    const response = await fetch(path, {
      method: "POST", credentials: "same-origin",
      headers: { "Content-Type": "application/json", "X-EntropyTrade-CSRF": csrf },
      body: JSON.stringify(body),
    });
    const result = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(result.error || `Request failed (${response.status})`);
    return result;
  }

  ET.views.research = async (root, ctx) => {
    if (ctx.params[0]) return detailView(root, ctx, ctx.params[0]);
    return listView(root, ctx);
  };

  // ----------------------------------------------------------------- list
  async function listView(root, ctx) {
    root.append(ET.pageHeader("Autonomous Research",
      "Describe an objective. EntropyTrade formulates hypotheses, inventories evidence, records what is missing and keeps the job until it can continue."));
    if (ET.mode() === "demo") {
      const demo = ET.demo().research;
      root.append(callout("Demo Mode: these research jobs are fictional examples. Submitting is disabled; switch to Real Mode to run research on this workspace.", "demo"));
      root.append(jobsCard(demo.jobs, "demo"));
      return;
    }
    root.append(ET.skeleton(4));
    const loaded = await ET.apiAll({ catalog: "/api/research", jobs: "/api/research/jobs" });
    if (!ctx.isCurrent()) return;
    root.lastChild.remove();
    if (!loaded.catalog.ok) {
      root.append(ET.unavailable("Research service unavailable", "The local server did not answer /api/research. " + loaded.catalog.error.message));
      return;
    }
    const catalog = loaded.catalog.data;
    root.append(h("div", { class: "grid g-2-1 research-top" }, submitCard(catalog), scopeCard(catalog)));
    root.append(loaded.jobs.ok ? jobsCard(loaded.jobs.data.jobs, "real") : ET.errorState(loaded.jobs.error.message, ET.route));
  }

  function scopeCard(catalog) {
    const configured = catalog.providers.filter((p) => p.configured && p.provider !== "local_templates");
    return card({ title: "How this works", subtitle: "Deterministic gates decide every status" },
      h("ol", { class: "research-how" },
        h("li", "Hypotheses come from local templates or a configured AI provider. They are proposals, never established edges."),
        h("li", "Each hypothesis becomes machine-readable data requirements: kind, entity, clock, fidelity and minimum independent events."),
        h("li", "Existing datasets are inventoried first. Values without the required clocks do not count."),
        h("li", "Missing evidence is acquired from approved read-only sources or planned for forward collection, then reevaluated.")),
      kv([
        ["AI providers configured", configured.length ? configured.map((p) => p.label).join(", ") : "None (local templates only)"],
        ["Registered features", String(catalog.features.length)],
        ["Order submission", "Disabled"],
      ]),
      callout(catalog.scope, "lock"));
  }

  function field(label, control, hint) {
    return h("label", { class: "field" }, h("span", { class: "field-label" }, label), control, hint ? h("span", { class: "hint" }, hint) : null);
  }

  function submitCard(catalog) {
    const defaults = catalog.defaults;
    const objective = h("textarea", { class: "input", rows: 3, id: "research-objective", maxlength: 2000,
      placeholder: "Find profitable strategies for Kalshi daily temperature markets using weather forecasts." });
    const family = h("select", { class: "input", id: "research-family" },
      catalog.families.map((f) => h("option", { value: f.family }, `${words(f.family)}${f.readiness === "research_ready" ? "" : " (requirements only)"}`)));
    const familyNote = h("p", { class: "hint" });
    const universe = h("div", { class: "chip-row research-universe", role: "group", "aria-label": "Contract universe" });
    const provider = h("select", { class: "input", id: "research-provider" },
      catalog.providers.map((p) => h("option", { value: p.provider, disabled: !p.configured }, p.configured ? p.label : `${p.label} (not configured)`)));
    const listId = "research-model-suggestions";
    const models = h("datalist", { id: listId });
    const model = h("input", { class: "input", id: "research-model", list: listId, autocomplete: "off", placeholder: "Model name" });
    const providerNote = h("p", { class: "hint" });
    const budget = h("input", { class: "input", id: "research-budget", type: "number", min: "0", max: "5", step: "0.05", value: defaults.budget.ai_usd });
    const lookback = h("input", { class: "input", id: "research-lookback", type: "number", min: "7", max: "180", value: String(defaults.lookback_days) });
    const depth = h("select", { class: "input", id: "research-depth" },
      [["quick", "Quick (20 events)"], ["standard", "Standard (60 events)"], ["thorough", "Thorough (120 events)"]].map(([v, l]) => h("option", { value: v, selected: v === defaults.validation_depth }, l)));
    const acquisition = h("select", { class: "input", id: "research-acquisition" },
      [["approved_sources", "Acquire from approved sources"], ["ask", "Ask before each acquisition"], ["none", "Inventory only"]].map(([v, l]) => h("option", { value: v, selected: v === defaults.acquisition }, l)));
    const paper = h("select", { class: "input", id: "research-paper" },
      [["recommend", "Recommend only"], ["paper_when_authorized", "Paper-trade when authorized"], ["never", "Never"]].map(([v, l]) => h("option", { value: v, selected: v === defaults.paper_preference }, l)));
    const issue = h("div", { class: "research-issue" });
    const submit = button("Start research", { variant: "primary", id: "research-submit" }, "sparkles");

    function syncFamily() {
      const selected = catalog.families.find((f) => f.family === family.value);
      familyNote.textContent = selected.readiness_note;
      universe.replaceChildren(...selected.series.map((s) => h("label", { class: "check research-series" },
        h("input", { type: "checkbox", value: s.series, "aria-label": `${s.name} (${s.series})` }), h("span", `${s.name} `, h("span", { class: "mono muted" }, s.series)))));
    }
    function syncProvider() {
      const selected = catalog.providers.find((p) => p.provider === provider.value);
      const local = selected.provider === "local_templates";
      model.disabled = local; budget.disabled = local;
      model.value = local ? "" : (selected.suggested_models[0] || model.value);
      models.replaceChildren(...selected.suggested_models.map((m) => h("option", { value: m })));
      providerNote.textContent = selected.note;
    }
    family.addEventListener("change", syncFamily);
    provider.addEventListener("change", syncProvider);
    syncFamily(); syncProvider();

    submit.addEventListener("click", async () => {
      issue.replaceChildren();
      const text = objective.value.trim();
      if (text.length < 10) { issue.append(callout("Describe the research objective in at least 10 characters.", "error")); return; }
      const local = provider.value === "local_templates";
      const body = {
        objective: text, family: family.value,
        universe: [...universe.querySelectorAll("input:checked")].map((x) => x.value),
        provider: local ? { provider: "local_templates" } : { provider: provider.value, model_name: model.value.trim() },
        budget: { ...defaults.budget, ai_usd: local ? "0" : String(budget.value || "0") },
        acquisition: acquisition.value, lookback_days: Number(lookback.value), validation_depth: depth.value,
        paper_preference: paper.value,
      };
      submit.disabled = true;
      try {
        const result = await post(catalog.csrf_token, "/api/research/jobs", body);
        ET.toast(result.created ? "Research job saved" : "An equivalent job already exists", "info");
        ET.go(`#/research/${result.id}`);
      } catch (error) {
        issue.append(callout(error.message, "error"));
      } finally { submit.disabled = false; }
    });

    return card({ title: "New research objective", subtitle: "Persistent job. You can leave and return later." },
      field("Research objective", objective),
      h("div", { class: "grid g-1-1" }, field("Market family", family, null), field("Validation depth", depth)),
      familyNote,
      field("Contract universe", universe, "Leave empty to use the series named in the objective, or the first configured series."),
      h("div", { class: "grid g-1-1" }, field("AI provider", provider), field("Model", h("div", model, models))),
      providerNote,
      h("div", { class: "grid g-3" }, field("AI budget (USD)", budget), field("Lookback (days)", lookback), field("Paper trading", paper)),
      field("Data acquisition", acquisition, "Read-only public sources from the approved catalog. Nothing is ever fetched from a URL a model proposes."),
      issue,
      h("div", { class: "row-actions end" }, submit));
  }

  function jobsCard(jobs, source) {
    const columns = [
      { key: "request", label: "Objective", render: (j) => h("div", { class: "cell-title research-objective-cell" }, j.request.objective), sort: (j) => j.request.objective },
      { key: "family", label: "Universe", render: (j) => h("span", { class: "mono" }, j.universe.join(", ")) },
      { key: "provider", label: "Reasoning", render: (j) => j.request.provider.provider === "local_templates" ? "Local templates" : `${j.request.provider.provider} · ${j.request.provider.model_name}`, sortable: false },
      { key: "status", label: "Status", render: (j) => statusPill(j.status) },
      { key: "hypothesis_counts", label: "Hypotheses", sortable: false, render: (j) => h("div", { class: "chip-row" },
        Object.entries(j.hypothesis_counts || {}).map(([k, n]) => pill(`${n} ${words(k)}`, `status ${HYP_TONE[k] || ""}`.trim()))) },
      { key: "updated_at", label: "Updated", align: "num", render: (j) => fmt.ago(j.updated_at) },
    ];
    return card({ title: "Research jobs", subtitle: `${jobs.length} saved`, source, flush: true },
      dataTable({ columns, rows: jobs, sortKey: "updated_at", onRow: (j) => ET.go(`#/research/${j.id}`), dense: true,
        empty: ET.emptyState({ iconName: "sparkles", title: "No research jobs yet", body: "Describe an objective above to start one." }) }));
  }

  // --------------------------------------------------------------- detail
  async function detailView(root, ctx, id) {
    const demo = ET.mode() === "demo";
    let csrf = null;
    if (demo) {
      const job = ET.demo().research.jobs.find((j) => j.id === id);
      if (!job) { root.append(ET.emptyState({ title: "Demo job not found", body: "Return to the research list." })); return; }
      render(root, job, { demo: true });
      return;
    }
    root.append(ET.skeleton(5));
    let shown = null;
    const tab = { key: "hypotheses" };
    while (ctx.isCurrent()) {
      let job;
      try {
        if (!csrf) csrf = (await ET.api("/api/research")).csrf_token;
        job = await ET.api(`/api/research/jobs/${encodeURIComponent(id)}`, { fresh: true });
      } catch (error) {
        if (ctx.isCurrent()) root.replaceChildren(ET.errorState(error.message, ET.route));
        return;
      }
      if (!ctx.isCurrent()) return;
      const stamp = `${job.updated_at}|${job.events.length}|${job.status}`;
      if (stamp !== shown) {
        shown = stamp;
        root.replaceChildren();
        render(root, job, { csrf, tab, refresh: () => { shown = null; } });
      }
      if (!ACTIVE.has(job.status)) return;
      await new Promise((resolve) => setTimeout(resolve, 1200));
    }
  }

  function stepper(job) {
    // A step is done only if the job's own event log shows it ran; skipped steps say so.
    const visited = new Set(job.events.map((e) => e.stage));
    const current = job.status === "recoverable_error" ? job.checkpoint?.stage : job.status === "awaiting_authorization" ? "awaiting_observations" : job.status;
    const index = STEPS.findIndex(([key]) => key === current);
    const last = index >= 0 ? index : STEPS.length;
    return h("ol", { class: "lifecycle research-steps", "aria-label": "Research job progress" }, STEPS.map(([key, label], i) => {
      const ran = visited.has(key) || key === "queued";
      const state = i === index && job.status !== "evaluated" ? "current" : i <= last && ran ? "done" : i < last ? "skipped" : "";
      return h("li", { class: `life ${state}`.trim(), "data-step": key, "data-state": state || "pending" },
        h("span", { class: "life-dot" }, state === "done" ? icon("check", 12) : state === "skipped" ? "–" : String(i + 1)),
        h("span", { class: "life-label" }, label, state === "skipped" ? h("span", { class: "life-note" }, "Skipped") : null));
    }));
  }

  function render(root, job, options) {
    const usage = job.usage || {};
    const requirements = job.requirements || [];
    const satisfied = requirements.filter((r) => r.assessment?.status === "satisfied").length;
    const live = job.hypotheses.filter((x) => x.status !== "duplicate");
    const actions = [];
    if (!options.demo) {
      const run = async (action) => {
        try { await post(options.csrf, `/api/research/jobs/${job.id}/${action}`); options.refresh(); ET.route(); }
        catch (error) { ET.toast(error.message, "error"); }
      };
      if (RESUMABLE.has(job.status)) actions.push(button(job.status === "recoverable_error" ? "Retry now" : "Reevaluate", { variant: "ghost sm", id: "research-resume", onclick: () => run("resume") }, "refresh"));
      if (!TERMINAL.has(job.status)) actions.push(button("Cancel job", { variant: "ghost sm", id: "research-cancel", onclick: () => run("cancel") }, "x"));
      actions.push(h("a", { class: "btn ghost sm", href: `/api/research/jobs/${job.id}/report`, download: `research-${job.id}.json`, id: "research-export" }, icon("download", 15), h("span", "Export report")));
    }
    root.append(ET.pageHeader(job.request.objective, `${words(job.family)} · ${job.universe.join(", ")} · created ${fmt.dateTime(job.created_at)}`, h("div", { class: "row-actions" }, ...actions)));
    if (options.demo) root.append(callout("Demo Mode: this research job is a fictional example and never reached the local server.", "demo"));
    root.append(h("div", { class: "research-status-row" }, statusPill(job.status), h("span", { class: "research-detail", id: "research-detail" }, job.detail)));
    if (job.error) root.append(callout(`${job.error.type} during ${words(job.error.stage)}: ${job.error.reason}`, job.status === "failed" ? "error" : "warn"));
    root.append(card({ title: "Lifecycle" }, stepper(job)));
    root.append(h("div", { class: "kpi-strip" },
      kpi({ label: "Hypotheses", value: String(live.length), sub: `${job.hypotheses.length - live.length} duplicates`, iconName: "sparkles" }),
      kpi({ label: "Requirements satisfied", value: `${satisfied} / ${requirements.length}`, iconName: "check" }),
      kpi({ label: "AI spend", value: fmt.usd(Number(usage.ai_usd || 0), 4), sub: `${usage.ai_requests || 0} requests · ${fmt.compact((usage.input_tokens || 0) + (usage.output_tokens || 0))} tokens`, iconName: "zap" }),
      kpi({ label: "Source requests", value: String(usage.http_requests || 0), sub: fmt.bytes(usage.bytes || 0), iconName: "globe" }),
      kpi({ label: "Runtime", value: (usage.runtime_seconds || 0) < 1 ? "<1s" : fmt.duration(usage.runtime_seconds), iconName: "clock" })));

    const panels = [
      { key: "hypotheses", label: "Hypotheses", count: live.length, render: () => hypothesesPanel(job) },
      { key: "requirements", label: "Data requirements", count: requirements.length, render: () => requirementsPanel(job) },
    ];
    if (job.sources) panels.push({ key: "sources", label: "Sources", count: job.sources.length, render: () => sourcesPanel(job) });
    if (job.acquisitions) panels.push({ key: "acquisitions", label: "Acquisitions", count: job.acquisitions.length, render: () => acquisitionsPanel(job, options) });
    if (job.features) panels.push({ key: "features", label: "Features", count: job.features.length, render: () => featuresPanel(job) });
    if (job.forward_requests) panels.push({ key: "forward", label: "Forward collection", count: job.forward_requests.length, render: () => forwardPanel(job) });
    panels.push({ key: "events", label: "Activity", count: job.events.length, render: () => eventsPanel(job) });
    const body = h("div", { class: "research-panel" });
    const selected = options.tab && panels.some((p) => p.key === options.tab.key) ? options.tab.key : "hypotheses";
    const bar = tabs(panels.map(({ key, label, count }) => ({ key, label, count })), selected, (key) => {
      if (options.tab) options.tab.key = key;
      body.replaceChildren(panels.find((p) => p.key === key).render());
    });
    root.append(card({ flush: false, className: "research-tabs" }, bar.el, body));
    body.append(panels.find((p) => p.key === selected).render());
    root.append(callout(job.scope, "lock"));
  }

  function facet(name, value) {
    if (!value) return null;
    const kind = value.ready ? "" : value.satisfied ? "warn" : "neg";
    return h("div", { class: "facet" }, h("span", { class: "facet-label" }, `${name} evidence`), meter(value.satisfied, Math.max(1, value.total), kind), h("span", { class: "mono" }, `${value.satisfied}/${value.total}`));
  }

  function hypothesesPanel(job) {
    const resolutions = job.resolutions || {};
    return h("div", { class: "stack" }, job.hypotheses.map((row) => {
      const spec = row.spec;
      const resolved = Object.fromEntries((resolutions[row.hypothesis_id] || []).map((r) => [r.requested, r]));
      const chip = (need) => {
        const r = resolved[need.name];
        const via = r ? r.via : "pending";
        return pill(need.name, `chip mono ${via === "unregistered" ? "neg" : via === "alias" ? "warn" : ""}`.trim(), { title: r ? `${via}${r.feature_id && r.feature_id !== need.name ? " → " + r.feature_id : ""}` : "not yet resolved" });
      };
      return h("article", { class: "hyp-card", "data-hypothesis": row.hypothesis_id },
        h("header", { class: "hyp-head" },
          h("div", { class: "hyp-titles" }, h("h4", spec.title), h("p", { class: "muted mono" }, `${row.hypothesis_id} · v${spec.version} · ${spec.provenance.generator === "provider" ? `${spec.provenance.provider} · ${spec.provenance.model_name}` : "local template " + spec.provenance.template_id}`)),
          tonePill(row.status, HYP_TONE)),
        h("p", { class: "hyp-rationale" }, spec.rationale),
        h("div", { class: "chip-row" }, h("span", { class: "section-label" }, "Features"), spec.features.map(chip), h("span", { class: "section-label" }, "Label"), chip(spec.label)),
        h("div", { class: "facets" }, facet("Predictive", row.facets.predictive), facet("Execution", row.facets.execution)),
        row.reasons.length ? h("ul", { class: "hyp-reasons" }, row.reasons.slice(0, 8).map((r) => h("li", r))) : null,
        row.searches > 1 ? h("p", { class: "hint" }, `This mechanism has been searched ${row.searches} times across jobs; later validation must account for repeated searches.`) : null,
        h("details", { class: "hyp-more" }, h("summary", "Specification"),
          kv([
            ["Universe", spec.universe.join(", ")],
            ["Decision times", spec.decision_schedule.map((d) => `${d.day_offset === 0 ? "target day" : `${-d.day_offset} day before`} ${d.local_time.slice(0, 5)} local`).join("; ")],
            ["Candidate models", spec.candidate_models.join(", ")],
            ["Rules", spec.rules.length ? spec.rules.map((r) => `${r.feature} ${r.op} ${r.threshold ?? "(fit)"} → ${r.side}`).join("; ") : "None proposed"],
            ["Timestamp semantics", spec.timestamp_semantics],
            ["Validation plan", spec.validation_plan],
          ]),
          h("p", { class: "section-label" }, "Leakage risks"), h("ul", { class: "hyp-reasons" }, spec.leakage_risks.map((x) => h("li", x))),
          h("p", { class: "section-label" }, "Invalidation criteria"), h("ul", { class: "hyp-reasons" }, spec.invalidation.map((x) => h("li", x)))));
    }));
  }

  function requirementsPanel(job) {
    const columns = [
      { key: "kind", label: "Evidence", render: (r) => h("div", { class: "cell-title" }, words(r.kind), h("div", { class: "muted mono" }, r.variable)) },
      { key: "entity", label: "Entity", render: (r) => h("span", { class: "mono" }, r.entity) },
      { key: "clock", label: "Clock", render: (r) => words(r.clock) },
      { key: "blocking", label: "Needed for", render: (r) => `${r.predictive_for.length} predictive / ${r.hypotheses.length} total` , sortable: false },
      { key: "status", label: "Status", sort: (r) => r.assessment?.status, render: (r) => r.assessment ? tonePill(r.assessment.status, REQ_TONE) : pill("Pending") },
      { key: "events", label: "Events", align: "num", sort: (r) => r.assessment?.events_available ?? -1, render: (r) => r.assessment ? `${r.assessment.events_available} / ${r.assessment.events_required}` : "—" },
      { key: "reasons", label: "Assessment", sortable: false, render: (r) => h("div", { class: "cell-title research-reasons" }, (r.assessment?.reasons || []).slice(0, 3).join(" · ")) },
    ];
    return dataTable({ columns, rows: job.requirements, sortKey: "status", sortDir: "asc", dense: true,
      empty: ET.emptyState({ iconName: "database", title: "No requirements yet", body: "Requirements are derived after hypotheses are recorded." }) });
  }

  function sourcesPanel(job) {
    const columns = [
      { key: "source_id", label: "Source", render: (s) => h("div", { class: "cell-title" }, s.name, h("div", { class: "muted mono" }, s.source_id)) },
      { key: "requirement", label: "Requirement", render: (s) => h("span", { class: "mono" }, `${s.kind} · ${s.entity}`) },
      { key: "decision", label: "Decision", render: (s) => tonePill(s.decision, { acquire: "pos", forward_collect: "warn", reject: "neg", authorization_required: "warn" }) },
      { key: "reasons", label: "Checks", sortable: false, render: (s) => h("div", { class: "cell-title research-reasons" }, s.reasons.join(" · ")) },
    ];
    return dataTable({ columns, rows: job.sources, sortKey: "decision", sortDir: "asc", dense: true });
  }

  function acquisitionsPanel(job) {
    const columns = [
      { key: "source_id", label: "Source", render: (a) => h("span", { class: "mono" }, a.source_id) },
      { key: "params", label: "Scope", sortable: false, render: (a) => h("span", { class: "mono" }, `${a.params.entity} · ${a.params.start} → ${a.params.end}`) },
      { key: "status", label: "Status", render: (a) => statusPill(a.status) },
      { key: "requests", label: "Requests", align: "num", render: (a) => String(a.requests) },
      { key: "bytes", label: "Bytes", align: "num", render: (a) => fmt.bytes(a.bytes) },
      { key: "dataset_id", label: "Dataset", sortable: false, render: (a) => a.dataset_id ? h("span", { class: "mono", title: a.dataset_id }, fmt.short(a.dataset_id)) : "—" },
      { key: "detail", label: "Detail", sortable: false, render: (a) => h("div", { class: "cell-title research-reasons" }, a.detail) },
    ];
    return dataTable({ columns, rows: job.acquisitions, sortKey: "status", dense: true,
      empty: ET.emptyState({ iconName: "globe", title: "No acquisitions", body: "Nothing needed acquiring, or acquisition is disabled for this job." }) });
  }

  function featuresPanel(job) {
    const columns = [
      { key: "feature_id", label: "Feature", render: (f) => h("div", { class: "cell-title" }, h("span", { class: "mono" }, f.feature_id), h("div", { class: "muted" }, `v${f.version} · ${f.unit}`)) },
      { key: "entity", label: "Entity", render: (f) => h("span", { class: "mono" }, f.entity) },
      { key: "rows", label: "Rows", align: "num", render: (f) => `${f.non_null} / ${f.rows}` },
      { key: "events", label: "Events", align: "num", render: (f) => String(f.events) },
      { key: "artifact_id", label: "Artifact", sortable: false, render: (f) => h("span", { class: "mono", title: f.artifact_id }, fmt.short(f.artifact_id)) },
      { key: "inputs", label: "Lineage", sortable: false, render: (f) => h("div", { class: "cell-title research-reasons" }, f.inputs.map((x) => fmt.short(x)).join(", ")) },
    ];
    return dataTable({ columns, rows: job.features, sortKey: "feature_id", sortDir: "asc", dense: true,
      empty: ET.emptyState({ iconName: "layers", title: "No features registered", body: "Features are materialized once their input evidence exists." }) });
  }

  function forwardPanel(job) {
    const columns = [
      { key: "kind", label: "Evidence", render: (f) => h("div", { class: "cell-title" }, words(f.kind), h("div", { class: "muted mono" }, `${f.variable} · ${f.entity}`)) },
      { key: "collector", label: "Collector", render: (f) => words(f.collector) },
      { key: "status", label: "Status", render: (f) => statusPill(f.status) },
      { key: "progress", label: "Observed", align: "num", sort: (f) => f.events_observed, render: (f) => `${f.events_observed} / ${f.events_required}` },
      { key: "next_check_at", label: "Next check", align: "num", render: (f) => f.next_check_at ? fmt.dateTime(f.next_check_at) : "—" },
      { key: "detail", label: "Detail", sortable: false, render: (f) => h("div", { class: "cell-title research-reasons" }, f.detail) },
    ];
    return dataTable({ columns, rows: job.forward_requests, sortKey: "status", dense: true,
      empty: ET.emptyState({ iconName: "clock", title: "No forward collection needed", body: "Every requirement was historical or unobtainable." }) });
  }

  function eventsPanel(job) {
    return dataTable({ columns: [
      { key: "at", label: "Time", render: (e) => h("span", { class: "mono" }, fmt.stamp(e.at)) },
      { key: "stage", label: "Stage", render: (e) => words(e.stage) },
      { key: "detail", label: "Detail", sortable: false, render: (e) => h("div", { class: "cell-title" }, e.detail) },
    ], rows: job.events, sortKey: "at", dense: true, pageSize: 25 });
  }
})();
