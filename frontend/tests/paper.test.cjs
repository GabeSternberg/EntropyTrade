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
  focus() {}
  showModal() { this.open = true; }
  close() { this.open = false; this.handlers.close?.(); }
  remove() {}
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
  return { root, ET: window.ET, calls, routes, timers, reads, body: context.document.body };
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
  assert.doesNotMatch(text(app.root), /Paper deployment saved/);
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


const readinessId = "sha256:" + "e".repeat(64);
const priorId = "sha256:" + "f".repeat(64);
const ownerState = (authenticated = false) => ({ configured: true, authenticated, principal: authenticated ? "owner" : null, csrf_token: "owner-csrf", submission_enabled: false });
const controlState = (halted = false) => ({ halted, epoch: 4, reason: "Recorded reason", updated_at: "2026-11-15T23:00:00Z", events: [], submission_enabled: false });
const readinessRecord = (overrides = {}) => ({ id: readinessId, monitor_id: monitorId, revision: 2, status: "proposed", source_fingerprint: "sha256:source", payload: { policy_hash: "sha256:policy", control_epoch: 4, source_fingerprint: "sha256:source", eligible: true, checks: [{ name: "evidence", passed: true, reason: "Bound evidence verified" }], capital_envelope: { max_dollars: "100.00", max_contracts: 10 }, risk_limits: { max_loss_dollars: "10.00" }, execution_authorized: false, submission_enabled: false }, current_checks: { eligible: true, checks: [{ name: "current_evidence", passed: true, reason: "Still current" }] }, events: [], ...overrides });
function readinessApp({ owner = ownerState(), report, record = readinessRecord(), submit } = {}) {
  const value = report || { preview: { ...record.payload, proposal_hash: readinessId }, proposals: [{ id: readinessId, status: record.status }, { id: priorId, status: "rejected" }], control: controlState() };
  return application({ responses: { "/api/owner": owner, "/api/controls": controlState(), "/api/monitors": [{ id: monitorId }], [`/api/monitors/${monitorId}`]: monitor(), [`/api/monitors/${monitorId}/readiness`]: value, [`/api/readiness/${encodeURIComponent(readinessId)}`]: record, [`/api/readiness/${encodeURIComponent(priorId)}`]: { ...record, id: priorId } }, submit });
}
async function oversight(app) { await app.ET.views.paper(app.root, { params: [monitorId], query: new URLSearchParams("tab=readiness"), isCurrent: () => true }); await new Promise((resolve) => setImmediate(resolve)); }
const find = (root, key, value) => descendants(root).find((node) => node.attrs[key] === value);

test("readiness: changing proposal hides the previous export and review controls until matching evidence arrives", async () => {
  const app = readinessApp({ owner: ownerState(true) }), original = app.ET.api;
  let finish;
  app.ET.api = (url, options) => url === `/api/readiness/${encodeURIComponent(priorId)}` ? new Promise((resolve) => { finish = resolve; }) : original(url, options);
  await oversight(app);
  assert.ok(find(app.root, "href", `/api/readiness/${encodeURIComponent(readinessId)}`));
  assert.ok(find(app.root, "data-readiness-review", "approve"));
  const picker = find(app.root, "aria-label", "Frozen readiness proposal");
  picker.value = priorId;
  const loading = picker.handlers.change();
  assert.equal(find(app.root, "href", `/api/readiness/${encodeURIComponent(readinessId)}`), undefined);
  assert.equal(find(app.root, "data-readiness-review", "approve"), undefined);
  assert.equal(find(app.root, "data-readiness-review", "reject"), undefined);
  assert.equal(find(app.root, "data-readiness-revoke", ""), undefined);
  assert.equal(find(app.root, "data-readiness-rollback", ""), undefined);
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(find(app.root, "href", `/api/readiness/${encodeURIComponent(priorId)}`), undefined);
  finish(readinessRecord({ id: priorId }));
  await loading;
  assert.ok(find(app.root, "href", `/api/readiness/${encodeURIComponent(priorId)}`));
  assert.equal(find(app.root, "href", `/api/readiness/${encodeURIComponent(readinessId)}`), undefined);
  assert.ok(find(app.root, "data-readiness-review", "approve"));
  assert.equal(app.calls.length, 0);
});

test("owner access: unconfigured state gives local CLI guidance and no credential setup form", async () => {
  const app = readinessApp({ owner: { configured: false, authenticated: false, csrf_token: "owner-csrf" } });
  await app.ET.ownerAccess();
  assert.match(text(app.body), /Owner access is not configured/);
  assert.match(text(app.body), /entropytrade.api.owner init/);
  assert.equal(descendants(app.body).filter((node) => node.attrs.type === "password").length, 0);
  assert.equal(app.calls.length, 0);
});

test("owner access: manual sign-in clears passphrase before dispatch and sends no principal", async () => {
  let entered;
  const app = readinessApp({ submit: async (_, options) => { entered = JSON.parse(options.body); return { ok: false, status: 429, json: async () => ({ error: "Try again later" }) }; } });
  await app.ET.ownerAccess();
  const password = find(app.body, "data-owner-password", "");
  password.value = "manual-owner-passphrase";
  await find(app.body, "data-owner-login", "").handlers.click();
  assert.equal(password.value, "");
  assert.deepEqual(entered, { password: "manual-owner-passphrase" });
  assert.equal(app.calls[0].url, "/api/owner/login");
  assert.equal(app.calls[0].options.headers["X-EntropyTrade-CSRF"], "owner-csrf");
  assert.match(text(app.body), /Try again later/);
});

test("global halt: local risk reduction does not need an owner and cannot resume deployments", async () => {
  const app = readinessApp({ owner: { configured: false, authenticated: false, csrf_token: "owner-csrf" } });
  await app.ET.controlAccess();
  const act = find(app.body, "data-global-control", "halt");
  assert.equal(disabled(act), false);
  find(app.body, "aria-label", "Global halt reason").value = "Stop new activity for investigation";
  await act.handlers.click();
  assert.equal(app.calls[0].url, "/api/controls/halt");
  assert.deepEqual(JSON.parse(app.calls[0].options.body), { reason: "Stop new activity for investigation" });
  assert.match(text(app.body), /does not resume paused, suspended or cancelled/);
  assert.equal(app.calls.filter((call) => /resume|orders/.test(call.url)).length, 0);
});

test("global halt: release is owner-only and binds the observed epoch", async () => {
  const denied = application({ responses: { "/api/owner": ownerState(), "/api/controls": controlState(true) } });
  await denied.ET.controlAccess();
  assert.equal(disabled(find(denied.body, "data-global-control", "release")), true);
  const app = application({ responses: { "/api/owner": ownerState(true), "/api/controls": controlState(true) } });
  await app.ET.controlAccess();
  find(app.body, "aria-label", "Global halt reason").value = "Evidence reviewed";
  await find(app.body, "data-global-control", "release").handlers.click();
  assert.deepEqual(JSON.parse(app.calls[0].options.body), { reason: "Evidence reviewed", expected_epoch: 4 });
  assert.equal(app.calls[0].url, "/api/controls/release");
});

test("global halt: a local HALT file keeps owner release disabled with local recovery guidance", async () => {
  const app = application({ responses: { "/api/owner": ownerState(true), "/api/controls": { ...controlState(true), halt_file_present: true } } });
  await app.ET.controlAccess();
  assert.equal(disabled(find(app.body, "data-global-control", "release")), true);
  assert.match(text(app.body), /Remove it locally after review/);
  assert.match(text(app.body), /website cannot remove the file/);
  assert.equal(app.calls.length, 0);
});

test("global halt: a refused stale release refreshes the barrier without retrying the mutation", async () => {
  let sentinel = false;
  const app = application({ responses: { "/api/owner": ownerState(true), "/api/controls": () => ({ ...controlState(true), halt_file_present: sentinel }) }, submit: async () => {
    sentinel = true;
    return { ok: false, status: 409, json: async () => ({ error: "HALT sentinel was observed before release" }) };
  } });
  await app.ET.controlAccess();
  find(app.body, "aria-label", "Global halt reason").value = "Review the current barrier";
  await find(app.body, "data-global-control", "release").handlers.click();
  assert.equal(app.calls.length, 1);
  assert.equal(disabled(find(app.body, "data-global-control", "release")), true);
  assert.match(text(app.body), /HALT sentinel was observed before release/);
  assert.match(text(app.body), /Remove it locally after review/);
});

test("readiness: precise missing evidence and unconfigured owner remain blocked without fake metrics", async () => {
  const report = { preview: { eligible: false, checks: [{ name: "prospective_events", passed: false, reason: "Only 3 independent prospective dates; 20 required" }], reasons: ["Authentic history is missing"] }, proposals: [], control: controlState() };
  const app = readinessApp({ owner: { configured: false, csrf_token: "owner-csrf" }, report });
  await oversight(app);
  assert.match(text(app.root), /Only 3 independent prospective dates/);
  assert.match(text(app.root), /Authentic history is missing/);
  assert.match(text(app.root), /Owner access is not configured/);
  assert.equal(disabled(find(app.root, "data-readiness-freeze", "")), false);
  assert.match(text(app.root), /execution_authorized=false/);
  assert.equal(app.calls.length, 0);
});

test("readiness: freeze sends only future capital and loss fields", async () => {
  const app = readinessApp({ submit: async () => ({ ok: true, json: async () => ({ id: readinessId }) }) });
  await oversight(app);
  find(app.root, "aria-label", "Proposed capital in dollars").value = "200.00";
  find(app.root, "aria-label", "Proposed maximum loss in dollars").value = "15.00";
  await find(app.root, "data-readiness-freeze", "").handlers.click();
  assert.equal(app.calls[0].url, `/api/monitors/${monitorId}/readiness`);
  assert.deepEqual(JSON.parse(app.calls[0].options.body), { capital_dollars: "200.00", max_loss_dollars: "15.00" });
});

test("readiness: approval requires owner and current checks and sends revision, never actor or execution", async () => {
  const unsigned = readinessApp(); await oversight(unsigned);
  assert.equal(disabled(find(unsigned.root, "data-readiness-review", "approve")), true);
  const stale = readinessApp({ owner: ownerState(true), record: readinessRecord({ current_checks: { eligible: false, checks: [{ name: "freshness", passed: false, reason: "Evidence changed" }] } }) });
  await oversight(stale);
  assert.equal(disabled(find(stale.root, "data-readiness-review", "approve")), true);
  const app = readinessApp({ owner: ownerState(true) }); await oversight(app);
  find(app.root, "aria-label", "Readiness review note").value = "Reviewed frozen source and limits";
  find(app.root, "aria-label", "Readiness review note").value ||= "Reviewed current evidence";
  await find(app.root, "data-readiness-review", "approve").handlers.click();
  assert.equal(app.calls[0].url, `/api/readiness/${encodeURIComponent(readinessId)}/review`);
  assert.deepEqual(JSON.parse(app.calls[0].options.body), { decision: "approve", expected_revision: 2, note: "Reviewed frozen source and limits" });
});

test("readiness: server stale revision remains authoritative and does not retry approval", async () => {
  const app = readinessApp({ owner: ownerState(true), submit: async () => ({ ok: false, status: 409, json: async () => ({ error: "Proposal revision changed" }) }) });
  await oversight(app);
  find(app.root, "aria-label", "Readiness review note").value ||= "Reviewed current evidence";
  await find(app.root, "data-readiness-review", "approve").handlers.click();
  assert.equal(app.calls.length, 1);
  assert.match(text(app.root), /Proposal revision changed/);
});

test("readiness: unauthenticated revocation and owner rollback use bounded references only", async () => {
  const app = readinessApp(); await oversight(app);
  find(app.root, "aria-label", "Readiness revocation reason").value = "Withdraw this review";
  await find(app.root, "data-readiness-revoke", "").handlers.click();
  assert.deepEqual(JSON.parse(app.calls[0].options.body), { reason: "Withdraw this review" });
  const rollbackId = "sha256:" + "a".repeat(64);
  const owner = readinessApp({ owner: ownerState(true), submit: async () => ({ ok: true, json: async () => ({ id: rollbackId }) }) });
  const original = owner.ET.api;
  owner.ET.api = (url, options) => url === `/api/readiness/${encodeURIComponent(rollbackId)}` ? Promise.resolve(readinessRecord({ id: rollbackId })) : url === `/api/monitors/${monitorId}/readiness` ? original(url, options).then((report) => owner.calls.length ? { ...report, proposals: [...report.proposals, { id: rollbackId, status: "proposed" }] } : report) : original(url, options);
  await oversight(owner);
  find(owner.root, "aria-label", "Prior readiness proposal").value = priorId;
  find(owner.root, "aria-label", "Rollback proposal reason").value = "Compare prior bounded configuration";
  await find(owner.root, "data-readiness-rollback", "").handlers.click();
  assert.deepEqual(JSON.parse(owner.calls[0].options.body), { target_proposal_id: priorId, reason: "Compare prior bounded configuration" });
  assert.ok(find(owner.root, "href", `/api/readiness/${encodeURIComponent(rollbackId)}`));
  assert.match(text(owner.root), /does not reactivate a deployment/);
});

test("owner and governance: saved Real handlers dispatch nothing after switching Demo", async () => {
  const app = readinessApp({ owner: ownerState(true) }); await oversight(app);
  find(app.root, "aria-label", "Readiness review note").value = "Reviewed current evidence";
  const approve = find(app.root, "data-readiness-review", "approve").handlers.click;
  const freeze = find(app.root, "data-readiness-freeze", "").handlers.click;
  await app.ET.controlAccess();
  find(app.body, "aria-label", "Global halt reason").value = "Stop";
  const halt = find(app.body, "data-global-control", "halt").handlers.click;
  app.ET.setMode("demo");
  const reads = app.reads.length;
  await approve(); await freeze(); await halt(); await app.ET.ownerAccess();
  assert.equal(app.calls.length, 0);
  assert.equal(app.reads.length, reads);
});

test("owner access: logout carries no actor and a saved login handler cannot send a secret in Demo", async () => {
  const owner = readinessApp({ owner: ownerState(true) });
  await owner.ET.ownerAccess();
  await find(owner.body, "data-owner-logout", "").handlers.click();
  assert.equal(owner.calls[0].url, "/api/owner/logout");
  assert.deepEqual(JSON.parse(owner.calls[0].options.body), {});
  const app = readinessApp();
  await app.ET.ownerAccess();
  const password = find(app.body, "data-owner-password", "");
  password.value = "manually-entered-secret";
  const login = find(app.body, "data-owner-login", "").handlers.click;
  app.ET.setMode("demo");
  const reads = app.reads.length;
  await login();
  assert.equal(password.value, "");
  assert.equal(app.calls.length, 0);
  assert.equal(app.reads.length, reads);
  assert.doesNotMatch(text(app.body), /manually-entered-secret/);
});

test("readiness audit: recorded owner and reason remain text, with no automatic approval", async () => {
  const record = readinessRecord({ events: [{ at: "2026-11-15T23:00:00Z", action: "approved", actor: { kind: "human", actor_id: "local-owner" }, reason: "<script>reviewed evidence</script>" }] });
  const app = readinessApp({ record }); await oversight(app);
  descendants(app.root).find((node) => node.attrs.role === "tab" && text(node).trim() === "Evidence & audit").handlers.click();
  assert.match(text(app.root), /local-owner/);
  assert.match(text(app.root), /<script>reviewed evidence<\/script>/);
  assert.equal(descendants(app.root).filter((node) => node.tag === "script").length, 0);
  assert.equal(app.calls.length, 0);
});

test("readiness monitoring: pending evidence is explicit and incident research links are canonical", async () => {
  const app = readinessApp();
  const original = app.ET.api;
  app.ET.api = (url, options) => url === `/api/monitors/${monitorId}/monitoring` ? Promise.resolve({ monitor_id: monitorId, evaluation: { evidence_as_of: "2026-11-15T23:00:00Z", status: "pending", checks: [{ name: "sample", passed: false, reason: "Awaiting enough independent prospective dates" }], signals: [{ kind: "pending_observations", severity: "info", recommended_action: "await_evidence", reason: "No drift conclusion from three dates" }] }, incidents: [], investigations: [{ id: "i1", status: "proposed", research_job_id: jobId, objective: "Investigate retained source coverage" }], submission_enabled: false }) : original(url, options);
  await oversight(app);
  descendants(app.root).find((node) => node.attrs.role === "tab" && text(node).trim() === "Monitoring").handlers.click();
  await new Promise((resolve) => setImmediate(resolve));
  assert.match(text(app.root), /Awaiting enough independent prospective dates/);
  assert.match(text(app.root), /No drift conclusion from three dates/);
  assert.ok(descendants(app.root).some((node) => node.attrs.href === `#/research/${jobId}`));
  assert.equal(app.calls.length, 0);
});

test("readiness monitoring: durable incidents show recorded reasons and open or resolved state", async () => {
  const app = readinessApp(), original = app.ET.api;
  app.ET.api = (url, options) => url.endsWith("/monitoring") ? Promise.resolve({ evaluation: {}, incidents: [
    { id: "incident-open", kind: "forecast_degradation", opened_at: "2026-11-15T23:00:00Z", acknowledged_at: "2026-11-15T23:01:00Z", resolved_at: null, evidence: { signals: [{ kind: "forecast_degradation", reason: "<script>proper score worsened</script>" }] }, events: [] },
    { id: "incident-resolved", kind: "readiness_integrity", opened_at: "2026-11-14T23:00:00Z", resolved_at: "2026-11-15T00:00:00Z", evidence: { signals: [{ kind: "readiness_integrity", reason: "Retained source was restored" }] }, events: [] },
  ] }) : original(url, options);
  await oversight(app);
  descendants(app.root).find((node) => node.attrs.role === "tab" && text(node).trim() === "Monitoring").handlers.click();
  await new Promise((resolve) => setImmediate(resolve));
  for (const expected of [/incident-open/, /acknowledged/, /incident-resolved/, /resolved/, /<script>proper score worsened<\/script>/, /Retained source was restored/]) assert.match(text(app.root), expected);
  assert.equal(descendants(app.root).filter((node) => node.tag === "script").length, 0);
});

test("readiness monitoring: an earlier request cannot overwrite the latest assessment", async () => {
  const app = readinessApp(), original = app.ET.api, pending = [];
  app.ET.api = (url, options) => url.endsWith("/monitoring") ? new Promise((resolve) => pending.push(resolve)) : original(url, options);
  await oversight(app);
  const tab = (label) => descendants(app.root).find((node) => node.attrs.role === "tab" && text(node).trim() === label).handlers.click();
  tab("Monitoring"); tab("Readiness"); tab("Monitoring");
  assert.equal(pending.length, 2);
  const assessment = (reason) => ({ evaluation: { signals: [{ reason }] }, incidents: [], investigations: [] });
  pending[1](assessment("Current degraded observation"));
  await new Promise((resolve) => setImmediate(resolve));
  pending[0](assessment("Outdated healthy observation"));
  await new Promise((resolve) => setImmediate(resolve));
  assert.match(text(app.root), /Current degraded observation/);
  assert.doesNotMatch(text(app.root), /Outdated healthy observation/);
});

test("readiness: expired owner session refreshes sign-in state without retrying approval", async () => {
  let authenticated = true;
  const app = readinessApp({ owner: () => ownerState(authenticated), submit: async () => { authenticated = false; return { ok: false, status: 401, json: async () => ({ error: "Owner session expired" }) }; } });
  await oversight(app);
  find(app.root, "aria-label", "Readiness review note").value ||= "Reviewed current evidence";
  await find(app.root, "data-readiness-review", "approve").handlers.click();
  assert.equal(app.calls.length, 1);
  assert.equal(disabled(find(app.root, "data-readiness-review", "approve")), true);
  assert.match(text(app.root), /Owner session expired/);
  assert.match(text(app.root), /Owner sign-in is required/);
});

test("readiness: an unknown current eligibility cannot become an approval", async () => {
  const app = readinessApp({ owner: ownerState(true), record: readinessRecord({ current_checks: { checks: [{ name: "source", passed: true, reason: "Partial source assessment only" }] } }) });
  await oversight(app);
  assert.equal(disabled(find(app.root, "data-readiness-review", "approve")), true);
  assert.equal(app.calls.length, 0);
});

test("paper timeline: settlement-only reconciliation is explicit and nullable prediction fields stay safe", async () => {
  const value = monitor("cancelled");
  value.cycles = [{ sequence: 2, status: "completed", finished_at: "2026-11-15T23:05:00Z", detail: "Official outcome reconciled", result: { schema: "shadow-reconciliation-cycle-v1", cycle_mode: "reconcile_only", capture: null, model_binding: null, execution: null, paper_execution: null, decisions: [], quotes: [], contracts: [], paper: { settlements: [{ settlement: { market_ticker: "KXHIGHPHIL-26NOV15-T55", result: "yes", settled_at: "2026-11-15T23:04:00Z" }, observed_outcome: { retrieved_at: "2026-11-15T23:05:00Z" } }] } } }];
  const app = application({ responses: { "/api/monitors": [{ id: monitorId }], [`/api/monitors/${monitorId}`]: value } });
  await app.ET.views.paper(app.root, { params: [monitorId], isCurrent: () => true });
  assert.match(text(app.root), /Settlement-only reconciliation/);
  assert.match(text(app.root), /Official settlement/);
  assert.match(text(app.root), /KXHIGHPHIL-26NOV15-T55/);
  assert.match(text(app.root), /Result: yes/);
  assert.equal(app.calls.length, 0);
});


test("readiness: approve and reject require an audit reason before dispatch", async () => {
  const app = readinessApp({ owner: ownerState(true) }); await oversight(app);
  await find(app.root, "data-readiness-review", "approve").handlers.click();
  await find(app.root, "data-readiness-review", "reject").handlers.click();
  assert.equal(app.calls.length, 0);
  assert.match(text(app.root), /Enter a review reason before approving or rejecting/);
});
