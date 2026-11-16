"use strict";
// Actual interface-kit and view rendering. Real-browser acceptance separately exercises
// the durable server, promotion gates and execution accounting.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

class Element {
  constructor(tag, text = "") { this.tag = tag; this.textContent = text; this.children = []; this.attrs = {}; this.style = {}; this.dataset = {}; this.handlers = {}; this.classList = { add() {}, remove() {}, toggle() {} }; }
  set innerHTML(_) { throw new Error("Research evidence must use text nodes"); }
  append(...children) { this.children.push(...children); }
  replaceChildren(...children) { this.children = children; }
  setAttribute(name, value) { this.attrs[name] = String(value); if (name === "value") this.value = String(value); }
  getAttribute(name) { return this.attrs[name]; }
  addEventListener(name, handler) { this.handlers[name] = handler; }
  querySelector(tag) { return descendants(this).slice(1).find((e) => e.tag === tag); }
  querySelectorAll(tag) { return descendants(this).slice(1).filter((e) => e.tag === tag); }
}
const descendants = (node) => [node, ...node.children.flatMap(descendants)];
const text = (node) => [node.textContent, ...node.children.map(text)].join("\n");
const disabled = (node) => node.disabled === true || node.attrs.disabled !== undefined;
const jobId = "11111111-1111-4111-8111-111111111111";
const monitorId = "22222222-2222-4222-8222-222222222222";
const experimentId = "sha256:" + "a".repeat(64);

function job() {
  return { id: jobId, family: "weather", universe: ["KXHIGHPHIL"], status: "awaiting_observations", detail: "Missing evidence", created_at: "2026-11-15T00:00:00Z", updated_at: "2026-11-15T00:00:00Z", request: { objective: "Study point-in-time weather evidence", provider: { provider: "local_templates" } }, events: [], hypotheses: [], experiments: [], usage: {}, scope: "Research results only" };
}
function proposal(overrides = {}) {
  return { experiment_id: experimentId, hypothesis_id: "h-example", model_family: "ridge", model_hash: "sha256:" + "b".repeat(64), strategy_hash: "sha256:" + "c".repeat(64), proposal_hash: "sha256:" + "d".repeat(64), eligible: false,
    reasons: ["Authentic history is required", "Prospective evidence is missing", "Certified fees are unavailable", "Forward source binding is incomplete"],
    checks: [{ name: "authentic_data", passed: false, reason: "Synthetic experiments cannot be promoted" }],
    validation_summary: { status: "evaluated", holdout_evaluated: false }, binding_summary: { kind: "research_weather_v1", feature_names: ["nws_pfm_max_f"], selected_schedule: { day_offset: -1, local_time: "18:00:00" } }, ...overrides };
}
function monitor(status = "active", account = null) {
  return { id: monitorId, family: "weather", candidate_id: "h-example", source_kind: "autonomous_research", research_job_id: jobId, experiment_id: experimentId, source_ref: { source_hash: "sha256:source" }, spec_hash: "sha256:strategy", model_binding: { kind: "research_weather_v1", model_ref: { family: "ridge", version: "sha256:model" }, binding_hash: "sha256:binding", snapshot: { selected_schedule: { day_offset: -1, local_time: "18:00:00" }, series_locations: { KXHIGHPHIL: { timezone: "America/New_York" } } } },
    status, interval_seconds: 300, next_at: "2026-11-15T01:00:00Z", cycle_count: 0, failures: 0, spec: {}, cycles: [], events: [],
    paper_summary: account || { status: "not_started", reason: "No committed paper cycle; no retrospective fills" } };
}
function application({ mode = "real", responses = {}, submit } = {}) {
  const root = new Element("main"), calls = [], routes = [], timers = [], reads = [];
  const currentJob = job();
  const chrome = new Map();
  const window = { ET: {}, location: { hash: "#/workbench" }, scrollTo() {}, localStorage: { getItem: () => mode, setItem() {} } };
  const context = vm.createContext({ window, Node: Element, URLSearchParams, setTimeout: (callback) => { timers.push(callback); return 0; }, document: { readyState: "loading", addEventListener() {}, body: new Element("body"), querySelectorAll: () => [], getElementById: (id) => { if (!chrome.has(id)) chrome.set(id, new Element("div")); return chrome.get(id); }, createElement: (tag) => new Element(tag), createElementNS: (_, tag) => new Element(tag), createTextNode: (value) => new Element("#text", value) },
    fetch: async (url, options) => { calls.push({ url, options }); return submit ? submit(url, options) : { ok: true, json: async () => ({ id: monitorId, created: true }) }; },
  });
  for (const file of ["ui.js", "shell.js", "views-research.js", "views-ops.js"]) {
    if (file === "shell.js") Object.assign(window.ET, { toast() {}, demoData: { quality_alerts: [], research: { jobs: [currentJob] } } });
    vm.runInContext(fs.readFileSync(path.join(__dirname, "../src", file), "utf8"), context);
  }
  Object.assign(window.ET, {
    pageHeader: (value) => window.ET.h("h1", value), toast() {},
    go: (route) => routes.push(route), route: () => routes.push("refresh"),
    api: async (url) => {
      if (window.ET.mode() !== "real") throw new Error("Demo Mode must not call the API");
      reads.push(url);
      const value = responses[url] ?? (url === "/api/research" || url === "/api/catalog" ? { csrf_token: "csrf-test" } : url === `/api/research/jobs/${jobId}` ? currentJob : undefined);
      if (value === undefined) throw new Error("Unexpected read: " + url);
      return typeof value === "function" ? value() : value;
    },
  });
  return { root, ET: window.ET, calls, routes, timers, reads };
}
async function paperProposals(app) {
  await app.ET.views.research(app.root, { params: [jobId], isCurrent: () => true });
  const tab = descendants(app.root).find((node) => node.attrs.role === "tab" && text(node).includes("Paper eligibility"));
  assert.ok(tab);
  tab.handlers.click();
  await new Promise((resolve) => setImmediate(resolve));
}

test("paper proposals: precise evidence refusals keep deployment disabled and make no POST", async () => {
  const app = application({ responses: { [`/api/research/jobs/${jobId}/paper`]: { proposals: [proposal({ reasons: ["<script>source</script>", ...proposal().reasons] })] } } });
  await paperProposals(app);
  for (const reason of proposal().reasons) assert.ok(text(app.root).includes(reason));
  assert.match(text(app.root), /<script>source<\/script>/);
  assert.equal(descendants(app.root).filter((node) => node.tag === "script").length, 0);
  assert.ok(disabled(descendants(app.root).find((node) => node.attrs["data-paper-start"] === "ridge")));
  assert.equal(app.calls.length, 0);
});

test("paper proposals: explicit eligible action sends references and interval only with CSRF", async () => {
  const app = application({ responses: { [`/api/research/jobs/${jobId}/paper`]: { proposals: [proposal({ eligible: true, reasons: [], checks: [], strategy: { forbidden_browser_spec: true }, risk_limits: { forbidden_browser_cap: 999999 } })] } } });
  await paperProposals(app);
  const start = descendants(app.root).find((node) => node.attrs["data-paper-start"] === "ridge");
  assert.ok(!disabled(start));
  assert.match(text(app.root), /1 day before target at 18:00:00 local/);
  assert.equal(descendants(app.root).filter((node) => node.attrs["aria-label"] === "Paper poll interval in seconds").length, 0);
  await start.handlers.click();
  assert.equal(app.calls.length, 1);
  assert.equal(app.calls[0].url, `/api/research/jobs/${jobId}/paper`);
  assert.equal(app.calls[0].options.headers["X-EntropyTrade-CSRF"], "csrf-test");
  assert.deepEqual(JSON.parse(app.calls[0].options.body), { experiment_id: experimentId, model_family: "ridge", interval_seconds: 300 });
  assert.deepEqual(app.routes, [`#/paper/${monitorId}`]);
});

test("paper proposals: server rejection refreshes authoritative refusal without retrying create", async () => {
  let changed = false;
  const app = application({ responses: { [`/api/research/jobs/${jobId}/paper`]: () => ({ proposals: [proposal({ eligible: !changed, reasons: changed ? ["Frozen source evidence failed verification"] : [] })] }) },
    submit: async () => { changed = true; return { ok: false, status: 409, json: async () => ({ error: "Eligibility changed" }) }; } });
  await paperProposals(app);
  await descendants(app.root).find((node) => node.attrs["data-paper-start"] === "ridge").handlers.click();
  assert.equal(app.calls.length, 1);
  assert.deepEqual(app.routes, []);
  assert.match(text(app.root), /Eligibility changed/);
  assert.match(text(app.root), /Frozen source evidence failed verification/);
  assert.ok(disabled(descendants(app.root).find((node) => node.attrs["data-paper-start"] === "ridge")));
});

test("paper proposals: existing cancelled deployment stays inspectable without creating another", async () => {
  const app = application({ responses: { [`/api/research/jobs/${jobId}/paper`]: { proposals: [proposal({ eligible: true, existing_deployment: { id: monitorId, status: "cancelled" } })] } } });
  await paperProposals(app);
  assert.match(text(app.root), /Open paper deployment/);
  assert.equal(descendants(app.root).filter((node) => node.attrs["data-paper-start"]).length, 0);
  assert.ok(descendants(app.root).some((node) => node.attrs.href === `#/paper/${monitorId}`));
  assert.equal(app.calls.length, 0);
});

test("paper proposals: Demo Mode has no eligibility reads or deployment writes", async () => {
  const app = application({ mode: "demo" });
  await paperProposals(app);
  assert.match(text(app.root), /paper proposals and deployment requests are disabled/);
  assert.equal(app.calls.length, 0);
});

for (const [status, actions] of [["active", ["pause", "suspend", "cancel"]], ["paused", ["resume", "suspend", "cancel"]], ["suspended", ["cancel"]], ["cancelled", []]]) {
  test(`paper dashboard: ${status} exposes only permitted lifecycle controls`, async () => {
    const value = monitor(status);
    const app = application({ responses: { "/api/monitors": [{ id: monitorId }], [`/api/monitors/${monitorId}`]: value } });
    await app.ET.views.paper(app.root, { params: [monitorId], isCurrent: () => true });
    assert.deepEqual(descendants(app.root).filter((node) => node.attrs["data-paper-action"]).map((node) => node.attrs["data-paper-action"]), actions);
    for (const version of [experimentId, "sha256:model", "sha256:strategy", "sha256:source"]) assert.ok(text(app.root).includes(version));
    assert.match(text(app.root), /No committed paper cycle/);
    assert.match(text(app.root), /1 day before target at 18:00:00 local/);
    assert.match(text(app.root), /America\/New_York/);
    assert.doesNotMatch(text(app.root), /Poll interval/);
    assert.ok(!text(app.root).includes("$1,000"), "no fabricated account balance before a committed cycle");
    assert.ok(disabled(descendants(app.root).find((node) => node.attrs["aria-label"] === "Live trading (disabled)")));
  });
}

test("paper dashboard: control requests carry CSRF and no risk or model overrides", async () => {
  const app = application({ responses: { "/api/monitors": [{ id: monitorId }], [`/api/monitors/${monitorId}`]: monitor() } });
  await app.ET.views.paper(app.root, { params: [monitorId], isCurrent: () => true });
  await descendants(app.root).find((node) => node.attrs["data-paper-action"] === "pause").handlers.click();
  assert.equal(app.calls.length, 1);
  assert.equal(app.calls[0].url, `/api/monitors/${monitorId}/pause`);
  assert.equal(app.calls[0].options.headers["X-EntropyTrade-CSRF"], "csrf-test");
  assert.deepEqual(JSON.parse(app.calls[0].options.body), {});
  assert.deepEqual(app.routes, ["refresh"]);
});

test("paper dashboard: cancellation preserves real recorded accounting and risk refusals", async () => {
  const account = { status: "simulated", data_kind: "synthetic", cash: "1001.42", available_cash: "1001.42", equity_at_cost: "1001.42", realized_pnl: "1.50", fees: ".08", fill_count: 2, settlement_count: 1, positions: [], as_of: "2026-11-15T23:00:00Z", drawdown_at_cost: ".07", peak_equity_at_cost: "1001.49", limitation: "Simulated accounting only" };
  const value = monitor("cancelled", account);
  value.cycles = [{ sequence: 1, status: "completed", detail: "CONTROLLED", result: { paper: { decisions: [{ ticker: "<img src=x>", status: "blocked", reasons: ["Certified fee evidence is missing"] }], executions: [{ ticker: "<img src=x>", status: "cancelled", reason: "liquidity_exhausted" }] } } }];
  const app = application({ responses: { "/api/monitors": [{ id: monitorId }], [`/api/monitors/${monitorId}`]: value } });
  await app.ET.views.paper(app.root, { params: [monitorId], isCurrent: () => true });
  for (const expected of [/CONTROLLED SYNTHETIC/, /\$1,001.42/, /liquidity_exhausted/, /Certified fee evidence is missing/, /No open simulated positions/, /Account as of/, /23:00 UTC/, /Current drawdown at cost/, /\$0.07/, /Peak equity at cost/]) assert.match(text(app.root), expected);
  assert.ok(descendants(app.root).every((node) => node.tag !== "img"));
  assert.equal(descendants(app.root).filter((node) => node.attrs["data-paper-action"]).length, 0);
});


test("paper dashboard: polling shows committed changes and recovers after an API outage", async () => {
  let unavailable = false;
  let value = monitor();
  const app = application({ responses: { "/api/monitors": () => { if (unavailable) throw new Error("Listener unavailable"); return [{ id: monitorId }]; }, [`/api/monitors/${monitorId}`]: () => value } });
  await app.ET.views.paper(app.root, { params: [monitorId], isCurrent: () => true });
  const poll = async () => { app.timers.shift()(); await new Promise((resolve) => setImmediate(resolve)); };
  assert.match(text(app.root), /No committed paper cycle/);
  value = monitor("active", { status: "simulated", data_kind: "real", cash: "999.75", realized_pnl: "-.25", fees: ".25", fill_count: 1, settlement_count: 0, positions: [] });
  await poll();
  assert.match(text(app.root), /\$999.75/);
  unavailable = true;
  await poll();
  assert.match(text(app.root), /Listener unavailable/);
  unavailable = false;
  await poll();
  assert.match(text(app.root), /\$999.75/);
  assert.doesNotMatch(text(app.root), /Listener unavailable/);
});

test("paper dashboard: leaving the page stops subsequent polling", async () => {
  let current = true;
  const app = application({ responses: { "/api/monitors": [], } });
  await app.ET.views.paper(app.root, { params: [], isCurrent: () => current });
  const before = app.reads.length;
  current = false;
  app.timers.shift()();
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(app.reads.length, before);
});


test("paper dashboard: mixed evidence headline totals disclose synthetic accounts", async () => {
  const account = { status: "simulated", data_kind: "synthetic", cash: "999.75", fees: ".25", realized_pnl: "-.25", fill_count: 1, settlement_count: 0, positions: [] };
  const first = monitor("cancelled", account);
  const second = { ...monitor("paused", { ...account, data_kind: "real" }), id: "33333333-3333-4333-8333-333333333333", source_kind: "legacy" };
  const app = application({ responses: { "/api/monitors": [first, second], [`/api/monitors/${first.id}`]: first, [`/api/monitors/${second.id}`]: second } });
  await app.ET.views.paper(app.root, { params: [], isCurrent: () => true });
  assert.match(text(app.root), /Mixed accounting totals include CONTROLLED SYNTHETIC accounts/);
});


test("paper proposals: saved Real action cannot write after a switch to Demo Mode", async () => {
  const app = application({ responses: { [`/api/research/jobs/${jobId}/paper`]: { proposals: [proposal({ eligible: true, reasons: [] })] } } });
  await paperProposals(app);
  const saved = descendants(app.root).find((node) => node.attrs["data-paper-start"] === "ridge").handlers.click;
  app.ET.setMode("demo");
  const reads = app.reads.length;
  await saved();
  assert.equal(app.calls.length, 0);
  assert.equal(app.reads.length, reads);
  assert.match(text(app.root), /Real API writes are disabled in Demo Mode/);
});

test("paper dashboard: saved Real control cannot write after a switch to Demo Mode", async () => {
  const app = application({ responses: { "/api/monitors": [{ id: monitorId }], [`/api/monitors/${monitorId}`]: monitor() } });
  await app.ET.views.paper(app.root, { params: [monitorId], isCurrent: () => true });
  const saved = descendants(app.root).find((node) => node.attrs["data-paper-action"] === "cancel").handlers.click;
  app.ET.setMode("demo");
  await saved();
  assert.equal(app.calls.length, 0);
  assert.match(text(app.root), /Real API writes are disabled in Demo Mode/);
});

test("paper dashboard: switching Demo while a CSRF read is pending cannot expose a writer", async () => {
  let finish;
  const pending = new Promise((resolve) => { finish = resolve; });
  const app = application({ responses: { "/api/catalog": () => pending, "/api/monitors": [{ id: monitorId }], [`/api/monitors/${monitorId}`]: monitor() } });
  const rendered = app.ET.views.paper(app.root, { params: [monitorId], isCurrent: () => true });
  app.ET.setMode("demo");
  finish({ csrf_token: "csrf-from-real-request" });
  await rendered;
  assert.equal(app.calls.length, 0);
  assert.equal(descendants(app.root).filter((node) => node.attrs["data-paper-action"]).length, 0);
  await assert.rejects(app.ET.mutate(`/api/monitors/${monitorId}/cancel`, {}, "csrf-from-real-request"), /disabled in Demo Mode/);
  assert.equal(app.calls.length, 0);
});
