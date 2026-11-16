"use strict";
// Dependency-free presentation regressions. This DOM double does not replace browser QA.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

class Element {
  constructor(tag) {
    this.tag = tag;
    this.children = [];
    this.textContent = "";
    this.className = "";
    this.dataset = {};
    this.options = [{}, {}];
    this.classList = { add: (...names) => { this.className += " " + names.join(" "); } };
  }
  set innerHTML(_) { throw new Error("Dynamic evidence must use text nodes"); }
  append(...children) { this.children.push(...children); }
  replaceChildren(...children) { this.children = children; }
  addEventListener() {}
  setAttribute(name, value) { (this.attributes ||= {})[name] = String(value); }
}

function application(alerts = []) {
  const elements = new Map();
  const document = {
    getElementById: (id) => {
      if (!elements.has(id)) elements.set(id, new Element("div"));
      return elements.get(id);
    },
    createElement: (tag) => new Element(tag),
    querySelectorAll: () => [],
  };
  document.getElementById("mode").value = "recorded";
  const context = vm.createContext({
    document, setInterval: () => 0,
    fetch: async (url) => ({ ok: true, json: async () =>
      url === "/api/alerts" ? { alerts } :
      ["/api/jobs", "/api/monitors", "/api/weather/datasets"].includes(url) ? [] : { csrf_token: "test" } }),
  });
  vm.runInContext(fs.readFileSync(path.join(__dirname, "../src/app.js"), "utf8") +
    "\nglobalThis.show = (result, tab) => { state.job = { result }; state.tab = tab; renderResult(); }; globalThis.showAlerts = shadowAlerts; globalThis.showProspective = prospectiveEvaluation; globalThis.showGates = v1Gates;", context);
  return { context, content: document.getElementById("result-content"), alerts: document.getElementById("shadow-alerts") };
}
test("label partitions: an older overlapping refresh cannot overwrite the selected partition", async () => {
  const { context } = application();
  await new Promise((resolve) => setTimeout(resolve, 10)); // let initialize() settle
  const select = context.document.getElementById("weather-label-partition");
  const content = context.document.getElementById("weather-labels");
  const partitions = [
    { partition_id: "00000000", status: "sealed", requests: 128, request_limit: 128 },
    { partition_id: "00000001", status: "active", requests: 1, request_limit: 128 },
  ];
  const pending = new Map();
  context.fetch = (url) => {
    const respond = (value) => ({ ok: true, json: async () => value });
    if (url === "/api/weather/label-partitions") return Promise.resolve(respond(partitions));
    return new Promise((resolve) => pending.set(url, () => resolve(respond([
      { id: "request-" + url.slice(-1), status: "completed", detail: "rows for " + url.slice(-8) },
    ]))));
  };
  const tick = () => new Promise((resolve) => setTimeout(resolve, 0));
  select.value = "00000001";
  const older = context.weatherLabels(); await tick();       // refresh click, rows still pending
  assert.equal(content.attributes["aria-busy"], "true");
  select.value = "00000000";
  const newer = context.weatherLabels(); await tick();       // later partition change
  pending.get("/api/weather/label-partitions/00000000")(); await newer;
  assert.equal(content.attributes["aria-busy"], "false");
  pending.get("/api/weather/label-partitions/00000001")(); await older;
  assert.equal(content.dataset.partition, "00000000");
  assert.equal(select.value, "00000000");
  assert.match(text(content), /rows for 00000000/);
  assert.doesNotMatch(text(content), /rows for 00000001/);
  assert.equal(content.attributes["aria-busy"], "false");
});
function text(element) { return [element.textContent, ...element.children.map(text)].join("\n"); }
function descendants(element) { return [element, ...element.children.flatMap(descendants)]; }

for (const synthetic of [false, true]) {
  test(`prospective evaluation: ${synthetic ? "synthetic diagnostics are labeled" : "authentic insufficiency has no invented metrics"}`, async () => {
    const { context } = application();
    const panel = new Element("section");
    const value = {
      status: synthetic ? "diagnostics_available" : "insufficient", as_of: "2026-10-31T00:00:00Z",
      counts: { pending: 1, refused: 1, matched: synthetic ? 11 : 0, independent_events: 12, independent_dates: 12, matched_events: synthetic ? 10 : 0, matched_dates: synthetic ? 10 : 0, poll_observations: 39 },
      diagnostics: synthetic ? [{ data_kind: "synthetic", model_hash: "frozen-model", calibration: "none", independent_events: 10, independent_dates: 10, metrics: { event_weighted_brier: .0875, event_weighted_log_loss: .3, reliability_bins: [] } }] : [],
      observations: [{ ticker: "<script>source</script>", event_id: "event", target_date: "2026-10-31", status: "refused", reason: "missing_prediction", outcome_revisions: 0 }],
      cycle_statuses: { interrupted: 1 }, cycle_failures: [], limitations: ["No profitability claim"], report_hash: "hash",
    };
    context.fetch = async () => ({ ok: true, json: async () => value });
    await context.showProspective("monitor", panel);
    assert.match(text(panel), /separate from historical validation and simulated paper accounting/);
    assert.match(text(panel), /Forecast evaluation JSON/); assert.match(text(panel), /Forecast observations CSV/);
    if (synthetic) { assert.match(text(panel), /CONTROLLED SYNTHETIC/); assert.match(text(panel), /Event-weighted Brier score/); }
    else { assert.match(text(panel), /Insufficient evidence: no forecast metrics/); assert.doesNotMatch(text(panel), /Event-weighted Brier score/); }
    assert.match(text(panel), /<script>source<\/script>/);
    assert.equal(descendants(panel).filter(e => e.tag === "script").length, 0);
  });
}

test("operator alerts keep acknowledged incidents open and resolved history inspectable", async () => {
  const { context, alerts } = application([
    { id: "a", monitor_id: "monitor-a", kind: "stale_collection", opened_at: "2026-10-31T00:00:00Z", acknowledged_at: "2026-10-31T00:01:00Z", resolved_at: null, evidence: { source: "<img src=x onerror=bad()>" }, events: [] },
    { id: "b", monitor_id: "monitor-a", kind: "repeated_failures", opened_at: "2026-10-31T00:00:00Z", acknowledged_at: null, resolved_at: null, evidence: {}, events: [] },
    { id: "c", monitor_id: "monitor-b", kind: "unresolved_reconciliation", opened_at: "2026-10-30T00:00:00Z", acknowledged_at: null, resolved_at: "2026-10-31T00:00:00Z", evidence: {}, events: [] },
  ]);
  await context.showAlerts();
  assert.match(text(alerts), /2 open · 1 need acknowledgement/);
  assert.match(text(alerts), /Stale collection · Acknowledged \/ still open/);
  assert.match(text(alerts), /Repeated failures · Needs acknowledgement/);
  assert.match(text(alerts), /Unresolved reconciliation · Resolved/);
  assert.equal(descendants(alerts).filter(e => e.tag === "button" && e.textContent === "Acknowledge alert").length, 1);
  assert.match(text(alerts), /<img src=x onerror=bad\(\)>/);
  assert.equal(descendants(alerts).filter(e => e.tag === "img").length, 0);
});
function fixture(partial) {
  return {
    data_kind: "real", reasoning_limit: "Local templates; no LLM.",
    coverage: {}, candidates: [], proposals: [], hypotheses: [], decisions: [], warnings: [],
    probabilities: [], probability_count: 0, probability_limit: 100, lineage: {}, artifacts: [],
    final_holdout_evaluated: false,
    acquisition: {
      headline: "Public acquisition INCOMPLETE · bitcoin", status: "incomplete",
      counts: `HTTP receipts: ${partial ? 3 : 0} (${partial ? 2 : 0} successful); listed contracts: ${partial ? 2 : 0}; observations: 0; acquisition failures: 1.`,
      failure_summaries: ["coinbase: ConnectError <script>alert('source')</script> (failed at 2026-10-25T15:00:00+00:00)"],
      started_at: "2026-10-25T15:00:00+00:00", decision_time: "2026-10-25T15:00:01+00:00",
      universe_complete: false, history_complete: false,
      evaluation_limit: "Forward ingestion only. No historical evaluation, fitted probabilities or empirical returns.",
      limitations: ["Bitcoin rules_known is false; settlement sources remain unresolved."],
    },
  };
}

for (const tab of ["review", "probabilities", "lineage"]) {
  for (const partial of [false, true]) {
    test(`${tab}: ${partial ? "partial" : "failed"} acquisition is visible without expanding details`, () => {
      const { context, content } = application();
      const result = fixture(partial);
      context.show(result, tab);
      const summary = content.children.find((child) => child.className.includes("acquisition"));
      assert.ok(summary);
      assert.ok(summary.className.includes("incomplete"));
      assert.ok(descendants(summary).every((child) => child.tag !== "details" && child.tag !== "script"));
      for (const value of [result.acquisition.headline, result.acquisition.counts,
        result.acquisition.failure_summaries[0], result.acquisition.evaluation_limit,
        result.acquisition.limitations[0], "History complete: false", "Final holdout is excluded."]) {
        assert.ok(text(content).includes(value), value);
      }
      if (tab === "probabilities") assert.ok(text(content).includes("No eligible fitted probability records"));
    });
  }
  test(`${tab}: synthetic banner stays visible`, () => {
    const { context, content } = application();
    const result = fixture(false);
    delete result.acquisition;
    result.data_kind = "synthetic";
    context.show(result, tab);
    assert.ok(text(content).includes("SYNTHETIC SOFTWARE DEMONSTRATION"));
    assert.ok(text(content).includes("Final holdout is excluded."));
  });
  test(`${tab}: retained Bitcoin gaps and reconciliation failures are visible`, () => {
    const { context, content } = application();
    const result = fixture(false);
    delete result.acquisition;
    result.bitcoin_history = {
      capture_count: 2, retained_events: 4, retained_dates: 2, protected_events: 0,
      limitations: ["No depth or certified fees; trading backtests and returns remain blocked."],
      reconciliation: { requested: 2, deferred: 0, receipts: [],
        failures: [{ ticker: "KXBTC-fixture", failure: "ConnectError", failed_at: "2026-10-28T23:00:00Z" }] },
      readiness: { summaries: ["Fitting: 4/40 events on 3/20 dates.", "Validation: 0/20 events on 0/10 dates."],
        limitation: "Minimum counts do not certify model quality or execution." },
    };
    context.show(result, tab);
    assert.ok(text(content).includes("2 retained captures"));
    assert.ok(text(content).includes("current failures: 1"));
    assert.ok(text(content).includes("KXBTC-fixture: ConnectError"));
    assert.ok(text(content).includes("trading backtests and returns remain blocked"));
    assert.ok(text(content).includes("Final holdout is excluded."));
    for (const summary of result.bitcoin_history.readiness.summaries) assert.ok(text(content).includes(summary));
  });
}

for (const tab of ["review", "probabilities", "lineage"]) {
  test(`${tab}: provider failure and limits are visible with zero experiment success`, () => {
    const { context, content } = application();
    const result = fixture(false);
    delete result.acquisition;
    result.status = "research_failed";
    result.reasoning = "provider";
    result.reasoning_limit = "Provider-backed bounded research; no fallback.";
    result.research = { status: "failed", provider: { provider: "openai", model_name: "configured-model" },
      failure: { type: "ResearchCredentialError", stage: "setup", reason: "Dedicated research credential is missing." },
      stages: [], limits: { requests: 16, tool_calls: 24 }, usage: { requests: 0 } };
    context.show(result, tab);
    for (const value of ["Provider-backed bounded research", "openai / configured-model", "ResearchCredentialError at setup",
      "Dedicated research credential is missing", "No candidates validated and no deterministic experiments ran", "Final holdout is excluded."]) {
      assert.ok(text(content).includes(value), value);
    }
    assert.ok(!text(content).includes("Predeclared mock proposals"));
    assert.ok(descendants(content).every(child => child.tag !== "script"));
  });
}

for (const tab of ["review", "probabilities", "lineage"]) {
  test(`${tab}: retained weather counts and shortages stay visible`, () => {
    const { context, content } = application();
    const result = fixture(false);
    delete result.acquisition;
    result.weather_history = {
      dataset_id: "sha256:" + "a".repeat(64), capture_count: 2, observation_count: 648,
      readiness: { status: "insufficient_data", independent_events: 4, date_blocks: 2,
        protected_events: 1, eligible_events: 3, scalar_label_events: 0, binary_label_events: 0,
        partitions: { fit: { events: 3, dates: 2, timely_source_matched_events: 0,
          minimum_events: 60, shortage: 60, label_cutoff: "2026-12-16T00:00:00+00:00" } },
        blockers: ["fit: 0/60 independent source-matched events", "No source-matched integer settlement highs"],
        limitations: ["Original receipt clocks are preserved", "Protected final holdout is excluded"] },
    };
    context.show(result, tab);
    const summary = content.children.find(child => child.className.includes("weather-history"));
    assert.ok(summary);
    for (const value of ["4 events on 2 dates", "1 protected events", "0 source-matched scalar labels",
      "fit: 0/60", "No source-matched integer settlement highs", "Original receipt clocks", "Final holdout is excluded."]) {
      assert.ok(text(summary).includes(value) || text(content).includes(value), value);
    }
    assert.ok(!descendants(summary).some(child => child.tag === "details"));
  });
}

for (const tab of ["review", "probabilities", "lineage"]) {
  test(`${tab}: shadow history clocks, depth and fee blockers stay visible`, () => {
    const { context, content } = application();
    const result = fixture(false);
    delete result.acquisition;
    result.weather_history = {
      dataset_id: "sha256:" + "b".repeat(64), capture_count: 128, observation_count: 128,
      readiness: { status: "insufficient_data", independent_events: 1, date_blocks: 1,
        protected_events: 0, eligible_events: 1, scalar_label_events: 0, binary_label_events: 1,
        partitions: {}, blockers: ["No source-matched integer settlement highs"], limitations: [],
        shadow_audit: { verified_cycles: 128, decision_samples: 128, sized_books: 127, stale_books: 1,
          limitation: "Forward predictions retain their partition; never promoted to validation.",
          execution_blockers: ["Missing later labels refuse historical evaluation", "Stale or missing depth refuses executable backtesting", "Certified effective historical fees are unavailable"] } },
    };
    context.show(result, tab);
    const summary = content.children.find(child => child.className.includes("weather-history"));
    assert.ok(summary);
    const visible = summary.children.filter(child => child.tag !== "details").map(text).join("\n");
    for (const value of ["128 verified shadow cycles", "128 exact decision samples", "127 sized books", "1 stale books", "never promoted to validation", "Missing later labels", "Stale or missing depth", "Certified effective historical fees"]) {
      assert.ok(visible.includes(value), value);
    }
  });
}

test("V1 gates panel shows open and invalid gates as text and never claims completion", async () => {
  const { context } = application();
  await new Promise((resolve) => setTimeout(resolve, 10));
  const panel = context.document.getElementById("v1-gates");
  const report = { v1_complete: false, open: ["a", "b"], submission_enabled: false, gates: [
    { gate_id: "a", title: "Certified effective fees", reference: "issue #6", status: "open", detail: "no attestation file" },
    { gate_id: "b", title: "<img src=x onerror=bad()>", reference: "", status: "invalid", detail: "evidence hash mismatch: ev.txt" },
    { gate_id: "c", title: "Done gate", reference: "", status: "attested", detail: "attested by operator at 2026-11-07T00:00:00Z" },
  ] };
  context.fetch = async () => ({ ok: true, json: async () => report });
  await context.showGates();
  assert.match(text(panel), /V1 incomplete: 2 of 3 gates are not attested/);
  assert.match(text(panel), /Certified effective fees · open/);
  assert.match(text(panel), /issue #6 · no attestation file/);
  assert.match(text(panel), /<img src=x onerror=bad\(\)> · invalid/);
  assert.equal(descendants(panel).filter(e => e.tag === "img").length, 0);
  context.fetch = async () => ({ ok: false, status: 500, json: async () => ({ error: "boom" }) });
  await context.showGates();
  assert.match(text(panel), /V1 gate report unavailable/);
  assert.doesNotMatch(text(panel), /attested\./);
});

test("workbench settlement-only cycles render without prediction or execution fields", async () => {
  const { context } = application();
  await new Promise((resolve) => setImmediate(resolve));
  const monitor = { id: "monitor", status: "cancelled", source_kind: "legacy", interval_seconds: 300, next_at: "2026-11-15T23:00:00Z", failures: 0, cycle_count: 1, events: [], contracts: [], cycles: [{ sequence: 1, status: "completed", finished_at: "2026-11-15T23:01:00Z", detail: "Official settlement drained", result: { cycle_mode: "reconcile_only", schema: "shadow-reconciliation-cycle-v1", capture: null, model_binding: null, execution: null, paper_execution: null, decisions: [], quotes: [], outcomes: [], paper: { settlements: [] } } }] };
  context.fetch = async (url) => ({ ok: true, json: async () => url.endsWith("/evaluation") ? { status: "insufficient", counts: {}, diagnostics: [], observations: [], cycle_statuses: {}, cycle_failures: [], limitations: [] } : monitor });
  await context.selectMonitor("monitor", true);
  const result = context.document.getElementById("shadow-evidence");
  assert.match(text(result), /Settlement-only reconciliation/);
  assert.match(text(result), /no new predictions, quotes or paper orders/);
  assert.match(text(result), /Decisions: 0; quotes: 0/);
});
