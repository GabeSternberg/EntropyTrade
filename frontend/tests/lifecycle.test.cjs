"use strict";
// Exercise the shipped views and interface kit with recorded metadata and controllable
// navigation/read completion. Managed-browser acceptance covers native browser behavior.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const walk = (node) => [node, ...node.children.flatMap(walk)];
const content = (node) => [node.textContent, ...node.children.map(content)].join(" ").replace(/\s+/g, " ").trim();
function matches(node, selector) {
  const checked = selector.endsWith(":checked");
  if (checked) selector = selector.slice(0, -8);
  const attr = selector.match(/\[([^=\]]+)(?:=["']?([^\]"']*)["']?)?\]/);
  const name = selector.replace(/\[[^\]]*\]/g, "");
  const tag = name.match(/^[\w-]+/)?.[0];
  const id = name.match(/#([\w-]+)/)?.[1];
  const classes = [...name.matchAll(/\.([\w-]+)/g)].map((m) => m[1]);
  return (!tag || node.tag === tag) && (!id || node.attrs.id === id) && classes.every((c) => (node.attrs.class || "").split(/\s+/).includes(c)) && (!attr || (attr[2] === undefined ? node.attrs[attr[1]] !== undefined : node.attrs[attr[1]] === attr[2])) && (!checked || node.checked);
}
class Element {
  constructor(tag, value = "") {
    this.tag = tag; this.textContent = value; this.children = []; this.attrs = {}; this.style = {}; this.dataset = {}; this.handlers = {}; this.parentNode = null;
    this.classList = { add: (...names) => this.setAttribute("class", [...new Set((this.attrs.class || "").split(/\s+/).filter(Boolean).concat(names))].join(" ")), remove: (...names) => this.setAttribute("class", (this.attrs.class || "").split(/\s+/).filter((name) => !names.includes(name)).join(" ")), toggle: (name, force) => { const has = (this.attrs.class || "").split(/\s+/).includes(name); const next = force ?? !has; this.classList[next ? "add" : "remove"](name); return next; } };
  }
  set innerHTML(_) { throw new Error("Recorded evidence must remain text"); }
  setAttribute(name, value) { this.attrs[name] = String(value); if (["value", "id"].includes(name)) this[name] = String(value); if (["checked", "selected", "disabled"].includes(name)) this[name] = true; }
  getAttribute(name) { return this.attrs[name]; }
  append(...nodes) { for (const node of nodes) { node.parentNode = this; this.children.push(node); } }
  replaceChildren(...nodes) { this.children.forEach((node) => { node.parentNode = null; }); this.children = []; this.append(...nodes); }
  get lastChild() { return this.children.at(-1); }
  get value() { return this._value ?? (this.tag === "select" ? this.children.find((node) => node.selected)?.value ?? this.children[0]?.value ?? "" : ""); }
  set value(value) { this._value = String(value); }
  addEventListener(name, handler) { this.handlers[name] = handler; }
  querySelector(selector) { return this.querySelectorAll(selector)[0] || null; }
  querySelectorAll(selector) { return walk(this).slice(1).filter((node) => matches(node, selector)); }
  focus() { this.focused = true; }
  scrollIntoView() { this.scrolled = true; }
  showModal() { this.open = true; }
  close() { this.open = false; this.handlers.close?.(); }
  remove() { if (this.parentNode) this.parentNode.children = this.parentNode.children.filter((node) => node !== this); this.parentNode = null; }
}
const jobId = "11111111-1111-4111-8111-111111111111";
const monitorId = "22222222-2222-4222-8222-222222222222";
const otherMonitorId = "33333333-3333-4333-8333-333333333333";
const alertId = "44444444-4444-4444-8444-444444444444";
const hash = (character) => "sha256:" + character.repeat(64);
const experimentId = hash("a"), otherExperimentId = hash("b"), proposalId = hash("c"), otherProposalId = hash("d");
const researchLink = (id = experimentId, tab = "experiments") => `#/research/${jobId}?tab=${tab}&experiment=${encodeURIComponent(id)}`;
const paperLink = (tab, id = proposalId) => `#/paper/${monitorId}?tab=${tab}&proposal=${encodeURIComponent(id)}`;
const settle = async () => { for (let i = 0; i < 4; i++) await new Promise((resolve) => setImmediate(resolve)); };
const find = (root, selector) => root.querySelector(selector);
const tab = (root, key) => walk(root).find((node) => node.attrs.role === "tab" && node.dataset.key === key);
const kpiValue = (root, label) => {
  const entry = root.querySelectorAll(".kpi").find((node) => content(find(node, ".kpi-label")) === label);
  assert.ok(entry, `Expected KPI: ${label}`);
  return content(find(entry, ".kpi-value"));
};
const component = (counts, recent = [], initialized = true) => ({ available: true, initialized, counts, recent });
function summary() {
  const experiments = Array.from({ length: 10 }, (_, index) => {
    const id = index === 0 ? experimentId : index === 1 ? otherExperimentId : hash(String(index));
    return { job_id: jobId, experiment_id: id, status: index ? "failed" : "evaluated", result_status: index ? "invalid" : "backtested", validation_status: index ? "refused" : "evaluated", backtest_status: index ? "blocked" : "completed", data_kind: index ? "real" : "synthetic", updated_at: "2026-11-16T01:00:00Z", href: researchLink(id) };
  });
  return { schema: "workspace-summary-v1", recorded_metadata_only: true, recent_limit: 10, components: {
    research_jobs: component({ total: 67, by_status: { evaluated: 31, failed: 36 } }, [{ id: jobId, job_id: jobId, family: "weather", status: "evaluated", updated_at: "2026-11-16T01:00:00Z", href: `#/research/${jobId}` }]),
    experiments: component({ total: 83, by_status: { evaluated: 40, failed: 43 }, by_result_status: { backtested: 7, invalid: 76 }, by_validation_status: { evaluated: 5, refused: 78 }, by_backtest_status: { completed: 7, blocked: 74 }, by_data_kind: { real: 80, synthetic: 3 }, with_recorded_result: 81, with_recorded_validation: 80, with_recorded_model: 40, with_recorded_backtest: 81 }, experiments),
    legacy_jobs: component({ total: 59, by_status: { completed: 59 } }, [{ id: otherMonitorId, job_id: otherMonitorId, status: "completed", created_at: "2026-11-15T00:00:00Z", href: "#/workbench" }]),
    course_jobs: component({ total: 61, by_status: { completed: 61 } }, [{ id: otherMonitorId, job_id: otherMonitorId, status: "completed", href: `#/cis1990/${otherMonitorId}` }]),
    monitors: component({ total: 9, by_status: { active: 5, cancelled: 4 }, by_source_kind: { autonomous_research: 6, legacy: 3 } }, [{ id: monitorId, monitor_id: monitorId, source_kind: "autonomous_research", status: "active", href: `#/paper/${monitorId}` }]),
    paper_accounts: component({ total: 3, by_data_kind: { real: 2, synthetic: 1 }, monitors_without_account: 6 }),
    alerts: component({ total: 6, unresolved: 4, unacknowledged: 3, unresolved_unacknowledged: 2 }, [{ id: alertId, alert_id: alertId, monitor_id: monitorId, kind: "stale_collection", href: `#/ops?tab=alerts&monitor=${monitorId}&alert=${alertId}` }]),
    readiness: component({ total: 2, by_status: { proposed: 1, rejected: 1 } }, [{ id: proposalId, proposal_id: proposalId, monitor_id: monitorId, status: "rejected", href: paperLink("readiness") }]),
  } };
}
function experiment(id, score, reason) { return { id, hypothesis_id: "h-recorded", status: "evaluated", updated_at: "2026-11-16T01:00:00Z", config: {}, result: { data_kind: "synthetic", models: { ridge: { metrics: { brier: score, log_loss: .45 }, artifact_hash: hash("e") } }, eligibility: { eligible: false, reasons: [reason] }, validation: { status: "refused", holdout_evaluated: false }, backtest: { status: "blocked", reasons: [reason] } } }; }
function job() { return { id: jobId, family: "weather", universe: ["KXHIGHPHIL"], status: "evaluated", detail: "Recorded experiment history", created_at: "2026-11-15T00:00:00Z", updated_at: "2026-11-16T01:00:00Z", request: { objective: "Retained point-in-time weather research", provider: { provider: "local_templates" } }, events: [], hypotheses: [], experiments: [experiment(experimentId, .1234, "FIRST_EXPERIMENT_REFUSAL"), experiment(otherExperimentId, .2468, "SELECTED_EXPERIMENT_REFUSAL")], usage: {}, scope: "Research only" }; }
function monitor() { return { id: monitorId, family: "weather", candidate_id: "h-recorded", source_kind: "autonomous_research", research_job_id: jobId, experiment_id: experimentId, source_ref: { source_hash: hash("e") }, spec_hash: hash("f"), model_binding: { kind: "research_weather_v1", model_ref: { family: "ridge", version: hash("e") }, snapshot: {} }, status: "cancelled", interval_seconds: 300, next_at: "2026-11-16T01:00:00Z", cycle_count: 0, failures: 0, spec: {}, cycles: [], events: [], paper_summary: { status: "not_started", reason: "No committed paper cycle" } }; }
function readiness(id, marker) { return { id, monitor_id: monitorId, revision: 2, status: "rejected", source_fingerprint: hash("e"), payload: { eligible: false, execution_authorized: false, submission_enabled: false, checks: [{ name: "source", passed: false, reason: marker }] }, current_checks: { eligible: false, checks: [{ name: "source", passed: false, reason: marker }] }, events: [{ action: "rejected", at: "2026-11-16T01:00:00Z", reason: marker, actor: { kind: "human", actor_id: "recorded-owner" } }] }; }
function researchCatalog() {
  return { csrf_token: "test-csrf", families: [{ family: "weather", readiness: "research_ready", readiness_note: "Recorded weather inputs only", series: [{ series: "KXHIGHPHIL", name: "Philadelphia daily maximum" }] }], providers: [{ provider: "local_templates", configured: true, label: "Local templates", note: "Local deterministic templates", suggested_models: [] }, { provider: "openai", configured: true, label: "Configured research provider", note: "Research credentials only", suggested_models: ["test-research-model"] }], features: [], defaults: { budget: { ai_usd: "0.50", http_requests: 10 }, lookback_days: 30, validation_depth: "quick", acquisition: "none", paper_preference: "never" }, scope: "Research only; real-money submission disabled" };
}
function responses() {
  return {
    "/api/workspace/summary": summary(),
    "/api/catalog": { csrf_token: "test-csrf" },
    "/api/research": researchCatalog(),
    "/api/research/jobs": { jobs: [job()] },
    [`/api/research/jobs/${jobId}`]: job(),
    [`/api/research/jobs/${jobId}/paper`]: { proposals: [experimentId, otherExperimentId].map((id) => ({ experiment_id: id, hypothesis_id: "h-recorded", model_family: "ridge", model_hash: hash("e"), strategy_hash: hash("f"), proposal_hash: hash("e"), eligible: false, reasons: [id === experimentId ? "FIRST_PAPER_REFUSAL" : "SELECTED_PAPER_REFUSAL"], checks: [], validation_summary: {}, binding_summary: {} })) },
    "/api/monitors": [{ id: monitorId, status: "cancelled" }],
    [`/api/monitors/${monitorId}`]: monitor(),
    [`/api/monitors/${monitorId}/readiness`]: { preview: { eligible: false, checks: [] }, proposals: [{ id: proposalId, status: "rejected" }, { id: otherProposalId, status: "rejected" }], control: { events: [] } },
    [`/api/readiness/${encodeURIComponent(proposalId)}`]: readiness(proposalId, "FIRST_READINESS_RECORD"),
    [`/api/readiness/${encodeURIComponent(otherProposalId)}`]: readiness(otherProposalId, "SELECTED_READINESS_RECORD"),
    [`/api/monitors/${monitorId}/monitoring`]: { evaluation: { status: "pending", checks: [{ name: "dates", passed: false, reason: "Awaiting independent prospective dates" }] }, incidents: [], investigations: [] },
    "/api/owner": { configured: true, authenticated: false, csrf_token: "owner-csrf", submission_enabled: false },
    "/api/controls": { halted: false, epoch: 1, events: [], submission_enabled: false },
    "/api/alerts": { alerts: [{ id: alertId, monitor_id: monitorId, kind: "stale_collection", opened_at: "2026-11-16T01:00:00Z" }, { id: "55555555-5555-4555-8555-555555555555", monitor_id: otherMonitorId, kind: "other_monitor_only", opened_at: "2026-11-15T01:00:00Z" }] },
    "/api/weather/schedules": [], "/api/weather/datasets": [], "/api/weather/label-partitions": [], "/api/fees": { versions: [] },
  };
}
function application({ hash: initialHash = "#/overview", overrides = {} } = {}) {
  const requests = [], timers = [], nodes = new Map(), body = new Element("body"), history = [initialHash];
  let historyIndex = 0, currentHash = initialHash;
  // Native hash navigation appends an entry; pushState/replaceState and traversal
  // update the current URL directly so they cannot accidentally append twice.
  const location = { get hash() { return currentHash; }, set hash(next) {
    if (String(next) === currentHash) return;
    currentHash = String(next); history.splice(++historyIndex); history.push(currentHash);
  } };
  const window = { ET: {}, location, scrollTo() {}, localStorage: { getItem: () => "real", setItem() {} }, addEventListener() {}, history: {
    pushState: (_, __, url) => { currentHash = String(url).slice(String(url).indexOf("#")); history.splice(++historyIndex); history.push(currentHash); },
    replaceState: (_, __, url) => { currentHash = String(url).slice(String(url).indexOf("#")); history[historyIndex] = currentHash; },
  } };
  const document = { readyState: "loading", body, addEventListener() {}, createElement: (tag) => new Element(tag), createElementNS: (_, tag) => new Element(tag), createTextNode: (value) => new Element("#text", value), getElementById: (id) => { const existing = walk(body).find((node) => node.attrs.id === id); if (existing) return existing; if (!nodes.has(id)) { const node = new Element("div"); node.setAttribute("id", id); nodes.set(id, node); body.append(node); } return nodes.get(id); }, querySelector: (selector) => body.querySelector(selector), querySelectorAll: (selector) => body.querySelectorAll(selector) };
  const values = { ...responses(), ...overrides };
  const context = vm.createContext({ window, document, Node: Element, URLSearchParams, console, navigator: { platform: "Linux" }, setTimeout: (callback) => { timers.push(callback); return timers.length; }, clearTimeout() {}, fetch: async (url, options) => {
    requests.push({ url, options });
    const value = values[url];
    if (value === undefined) throw new Error("Unexpected API request: " + url);
    const result = typeof value === "function" ? await value({ url, options }) : await value;
    if (result instanceof Error) throw result;
    return { ok: true, json: async () => result };
  } });
  for (const file of ["ui.js", "shell.js", "views-markets.js", "views-lab.js", "views-research.js", "views-ops.js", "views-cis1990.js"]) vm.runInContext(fs.readFileSync(path.join(__dirname, "../src", file), "utf8"), context, { filename: file });
  const app = { ET: window.ET, window, document, requests, timers, body, root: document.getElementById("view"), historySnapshot: () => ({ entries: [...history], index: historyIndex }), async route(next) { if (next) location.hash = next; window.ET.route(); await settle(); }, async back() { if (historyIndex) currentHash = history[--historyIndex]; window.ET.route(); await settle(); }, async forward() { if (historyIndex < history.length - 1) currentHash = history[++historyIndex]; window.ET.route(); await settle(); } };
  return app;
}

const links = (root) => root.querySelectorAll("a").map((node) => node.attrs.href);
const selectedTab = (root, key) => assert.equal(tab(root, key)?.attrs["aria-selected"], "true", `Expected selected tab ${key}`);
const unavailable = (root) => assert.match(content(root), /(?:selected|requested|proposal|experiment|deployment|alert|record).{0,80}(?:not found|not recorded|unavailable|cannot|missing|does not belong|not available|mismatch)|(?:no|missing|unknown|invalid).{0,30}(?:selected|requested|proposal|experiment|deployment|alert|record)|cannot select/i);
const defer = () => { let resolve; const promise = new Promise((done) => { resolve = done; }); return { promise, resolve }; };
async function clickTab(app, key) {
  const control = tab(app.root, key);
  assert.ok(control, `Missing actual tab ${key}`);
  await control.handlers.click();
  await settle();
}

test("overview uses full stored counts above fifty while recent references stay bounded", async () => {
  const app = application();
  await app.route();
  for (const [label, value] of [["Autonomous research jobs", "67"], ["Persistent experiments", "83"], ["Legacy research runs", "59"], ["CIS course runs", "61"], ["Paper accounts", "3"], ["Open alerts", "4"]]) assert.equal(kpiValue(app.root, label), value);
  const experiments = find(app.root, '[data-summary-records="experiments"]');
  assert.equal(experiments.querySelectorAll(".summary-ref").length, 10);
  assert.match(content(experiments), /at most 10 recent references.*all stored records/i);
  assert.equal(new Set(links(experiments)).size, 10);
  assert.deepEqual(app.requests.map(({ url }) => url), ["/api/workspace/summary"]);
  assert.ok(app.requests.every(({ options }) => options.method === "GET"));
});

test("overview separates legacy and course sources, real and synthetic data, and actual accounts", async () => {
  const app = application();
  await app.route();
  assert.match(content(find(app.root, '[data-summary-records="experiments"]')), /real: 80.*synthetic: 3/);
  assert.match(content(find(app.root, '[data-summary-records="paper_accounts"]')), /real: 2.*synthetic: 1/);
  assert.match(content(app.root), /6 monitors have no stored account/);
  assert.match(content(find(app.root, '[data-summary-records="monitors"]')), /autonomous_research: 6.*legacy: 3/);
  assert.ok(links(app.root).includes("#/workbench"));
  assert.ok(links(app.root).includes("#/cis1990"));
  assert.match(content(app.root), /stored metadata.*does not prove current scientific validity.*paper eligibility.*profitability/i);
});

test("unavailable components show an unknown dash while initialized-empty components show zero", async () => {
  const data = summary();
  data.components.research_jobs = { available: false, initialized: null, counts: null, recent: [] };
  data.components.experiments = component({ total: 0, by_status: {} }, [], false);
  const app = application({ overrides: { "/api/workspace/summary": data } });
  await app.route();
  assert.equal(kpiValue(app.root, "Autonomous research jobs"), "—");
  assert.equal(kpiValue(app.root, "Persistent experiments"), "0");
  assert.equal(kpiValue(app.root, "Paper accounts"), "3");
  assert.match(content(app.root), /Recorded metadata unavailable/);
  assert.match(content(app.root), /Not started/);
});

test("a summary request failure displays an error without fabricated zero counts", async () => {
  const app = application({ overrides: { "/api/workspace/summary": new Error("SUMMARY_READ_UNAVAILABLE") } });
  await app.route();
  assert.match(content(app.root), /SUMMARY_READ_UNAVAILABLE/);
  assert.equal(app.root.querySelectorAll(".kpi").length, 0);
});

for (const route of ["#/lab", "#/analytics"]) test(`${route} uses autonomous metadata and preserves exact experiment evidence links`, async () => {
  const app = application({ hash: route });
  await app.route();
  assert.equal(kpiValue(app.root, "Persistent experiments"), "83");
  assert.ok(links(app.root).includes(researchLink()));
  assert.match(content(app.root), /evaluated/);
  assert.match(content(app.root), /backtested/);
  assert.match(content(app.root), /refused/);
  assert.match(content(app.root), /81 recorded backtests/);
  assert.match(content(app.root), /blocked: 74.*completed: 7/);
  assert.match(content(app.root), /stored metadata|recorded metadata/i);
  assert.doesNotMatch(content(app.root), /No authentic backtest has passed|This workspace has none yet/);
  assert.deepEqual(app.requests.map(({ url }) => url), ["/api/workspace/summary"]);
});

test("overview keeps canonical experiment, readiness proposal and alert references", async () => {
  const app = application();
  await app.route();
  for (const href of [researchLink(), paperLink("readiness"), `#/ops?tab=alerts&monitor=${monitorId}&alert=${alertId}`, `#/cis1990/${otherMonitorId}`]) assert.ok(links(app.root).includes(href), `Missing exact ${href}`);
});

test("route parsing retains allowed selections and drops unrelated query keys", () => {
  const app = application();
  const parsed = app.ET.parseRoute(researchLink(otherExperimentId, "paper") + "&token=secret&redirect=https%3A%2F%2Fexample.invalid");
  assert.equal(parsed.name, "research");
  assert.deepEqual([...parsed.params], [jobId]);
  assert.equal(parsed.query.get("tab"), "paper");
  assert.equal(parsed.query.get("experiment"), otherExperimentId);
  assert.equal(parsed.query.has("token"), false);
  assert.equal(parsed.query.has("redirect"), false);
  assert.equal(parsed.routeError, null);
  const create = app.ET.parseRoute("#/research?new=1");
  assert.equal(create.query.get("new"), "1");
});

test("new research reload focuses the real objective form and submits the chosen provider", async () => {
  const app = application({ hash: "#/research?new=1", overrides: { "/api/research/jobs": ({ options }) => options.method === "POST" ? { id: jobId, created: true } : { jobs: [] } } });
  await app.route();
  const objective = find(app.root, "#research-objective");
  assert.ok(objective?.focused);
  assert.equal(app.requests.filter(({ options }) => options.method === "POST").length, 0);
  objective.value = "Inspect retained synthetic weather evidence";
  const provider = find(app.root, "#research-provider");
  provider.value = "openai"; provider.handlers.change();
  find(app.root, "#research-model").value = "test-research-model";
  const series = find(app.root, 'input[type="checkbox"]');
  series.checked = true;
  await find(app.root, "#research-submit").handlers.click();
  const submitted = app.requests.filter(({ options }) => options.method === "POST");
  assert.equal(submitted.length, 1);
  assert.equal(submitted[0].url, "/api/research/jobs");
  assert.equal(submitted[0].options.headers["X-EntropyTrade-CSRF"], "test-csrf");
  const body = JSON.parse(submitted[0].options.body);
  assert.equal(body.objective, objective.value);
  assert.deepEqual(body.provider, { provider: "openai", model_name: "test-research-model" });
  assert.deepEqual(body.universe, ["KXHIGHPHIL"]);
  assert.equal(app.window.location.hash, `#/research/${jobId}`);
  await app.route();
  assert.match(content(app.root), /Recorded experiment history/);
  assert.match(content(app.root), /evaluated/);
  const reloaded = application({ hash: "#/research?new=1" });
  await reloaded.route();
  assert.ok(find(reloaded.root, "#research-objective")?.focused);
});

for (const route of [`#/research/${jobId}?tab=bogus`, `#/research/${jobId}?tab=experiments&experiment=not-a-hash`, `#/paper/${monitorId}?tab=readiness&proposal=bad`, `#/paper/not-a-uuid?tab=account`, `#/ops?tab=alerts&monitor=bad`, `#/research/${jobId}?tab=paper&tab=experiments`]) test(`invalid selection is visibly refused before reads: ${route}`, async () => {
  const app = application({ hash: route });
  await app.route();
  unavailable(app.root);
  assert.match(content(app.root), /Invalid/);
  assert.equal(app.requests.length, 0);
});

test("research reload restores the exact experiment and its recorded refusal", async () => {
  const app = application({ hash: researchLink(otherExperimentId) });
  await app.route();
  selectedTab(app.root, "experiments");
  assert.equal(app.root.querySelectorAll(".research-experiment").length, 1);
  assert.equal(find(app.root, ".research-experiment").attrs["data-experiment"], otherExperimentId);
  assert.match(content(app.root), /SELECTED_EXPERIMENT_REFUSAL/);
  assert.match(content(app.root), /0\.2468/);
  assert.doesNotMatch(content(app.root), /FIRST_EXPERIMENT_REFUSAL|0\.1234/);
});

test("research tab changes persist the selected experiment and restore on back and forward", async () => {
  const app = application({ hash: researchLink(otherExperimentId) });
  await app.route();
  await clickTab(app, "paper");
  assert.equal(app.ET.parseRoute().query.get("tab"), "paper");
  assert.equal(app.ET.parseRoute().query.get("experiment"), otherExperimentId);
  assert.match(content(app.root), /SELECTED_PAPER_REFUSAL/);
  assert.doesNotMatch(content(app.root), /FIRST_PAPER_REFUSAL/);
  await app.back();
  selectedTab(app.root, "experiments");
  assert.match(content(app.root), /SELECTED_EXPERIMENT_REFUSAL/);
  await app.forward();
  selectedTab(app.root, "paper");
  assert.match(content(app.root), /SELECTED_PAPER_REFUSAL/);
  const reloaded = application({ hash: app.window.location.hash });
  await reloaded.route();
  selectedTab(reloaded.root, "paper");
  assert.match(content(reloaded.root), /SELECTED_PAPER_REFUSAL/);
});

test("recorded experiment picker persists its exact choice and restores the earlier choice on back", async () => {
  const app = application({ hash: researchLink() });
  await app.route();
  const picker = find(app.root, '[aria-label="Recorded experiment"]');
  assert.ok(picker);
  picker.value = otherExperimentId;
  await picker.handlers.change(); await settle();
  assert.equal(app.ET.parseRoute().query.get("experiment"), otherExperimentId);
  assert.match(content(app.root), /SELECTED_EXPERIMENT_REFUSAL/);
  assert.doesNotMatch(content(app.root), /FIRST_EXPERIMENT_REFUSAL/);
  await app.back();
  assert.equal(app.ET.parseRoute().query.get("experiment"), experimentId);
  assert.match(content(app.root), /FIRST_EXPERIMENT_REFUSAL/);
  assert.doesNotMatch(content(app.root), /SELECTED_EXPERIMENT_REFUSAL/);
  await app.forward();
  assert.match(content(app.root), /SELECTED_EXPERIMENT_REFUSAL/);
});

for (const panel of ["experiments", "paper"]) test(`unknown selected research experiment is refused in ${panel}`, async () => {
  const app = application({ hash: researchLink(hash("9"), panel) });
  await app.route();
  unavailable(app.root);
  assert.doesNotMatch(content(app.root), /FIRST_EXPERIMENT_REFUSAL|SELECTED_EXPERIMENT_REFUSAL|FIRST_PAPER_REFUSAL|SELECTED_PAPER_REFUSAL/);
});

test("paper readiness reload selects the exact frozen proposal and exact research lineage", async () => {
  const app = application({ hash: paperLink("readiness", otherProposalId) });
  await app.route();
  selectedTab(app.root, "readiness");
  assert.match(content(app.root), /SELECTED_READINESS_RECORD/);
  assert.doesNotMatch(content(app.root), /FIRST_READINESS_RECORD/);
  assert.ok(links(app.root).includes(researchLink()), "Lineage must preserve the originating experiment");
  assert.ok(app.requests.some(({ url }) => url === `/api/readiness/${encodeURIComponent(otherProposalId)}`));
  assert.ok(!app.requests.some(({ url }) => url === `/api/readiness/${encodeURIComponent(proposalId)}`));
});

test("paper tabs retain proposal selection through monitoring, evidence, back and reload", async () => {
  const app = application({ hash: paperLink("readiness", otherProposalId) });
  await app.route();
  await clickTab(app, "monitoring");
  assert.equal(app.ET.parseRoute().query.get("tab"), "monitoring");
  assert.equal(app.ET.parseRoute().query.get("proposal"), otherProposalId);
  assert.match(content(app.root), /Awaiting independent prospective dates/);
  await clickTab(app, "evidence");
  assert.equal(app.ET.parseRoute().query.get("tab"), "evidence");
  assert.match(content(app.root), /SELECTED_READINESS_RECORD/);
  await app.back();
  selectedTab(app.root, "monitoring");
  await app.back();
  selectedTab(app.root, "readiness");
  assert.match(content(app.root), /SELECTED_READINESS_RECORD/);
  await app.forward();
  const reloaded = application({ hash: app.window.location.hash });
  await reloaded.route();
  selectedTab(reloaded.root, "monitoring");
  assert.equal(reloaded.ET.parseRoute().query.get("proposal"), otherProposalId);
});

test("an unknown readiness proposal never silently selects the first frozen record", async () => {
  const app = application({ hash: paperLink("readiness", hash("9")) });
  await app.route();
  unavailable(app.root);
  assert.doesNotMatch(content(app.root), /FIRST_READINESS_RECORD|SELECTED_READINESS_RECORD/);
  assert.ok(!app.requests.some(({ url }) => url === `/api/readiness/${encodeURIComponent(proposalId)}`));
});

for (const list of [[{ id: monitorId }], []]) test(`a selected missing paper deployment is explicit with ${list.length} stored monitors`, async () => {
  const app = application({ hash: `#/paper/${otherMonitorId}?tab=account`, overrides: { "/api/monitors": list } });
  await app.route();
  unavailable(app.root);
  assert.match(content(app.root), /deployment.*not found|selected.*(?:missing|not found|unavailable)/i);
});

test("a returned readiness record must match both requested proposal and selected monitor", async () => {
  for (const value of [readiness(proposalId, "WRONG_RECORD_MUST_NOT_PAINT"), { ...readiness(otherProposalId, "WRONG_RECORD_MUST_NOT_PAINT"), monitor_id: otherMonitorId }]) {
    const app = application({ hash: paperLink("readiness", otherProposalId), overrides: { [`/api/readiness/${encodeURIComponent(otherProposalId)}`]: value } });
    await app.route();
    unavailable(app.root);
    assert.doesNotMatch(content(app.root), /WRONG_RECORD_MUST_NOT_PAINT/);
  }
});

test("readiness proposal changes persist immediately and discard an older async completion", async () => {
  const first = defer(), second = defer();
  let deferLoads = false;
  const app = application({ hash: paperLink("readiness"), overrides: {
    [`/api/readiness/${encodeURIComponent(proposalId)}`]: () => deferLoads ? first.promise : readiness(proposalId, "FIRST_READINESS_RECORD"),
    [`/api/readiness/${encodeURIComponent(otherProposalId)}`]: () => second.promise,
  } });
  await app.route();
  assert.match(content(app.root), /FIRST_READINESS_RECORD/);
  deferLoads = true;
  const picker = find(app.root, '[aria-label="Frozen readiness proposal"]');
  assert.ok(picker);
  const refresh = walk(app.root).find((node) => node.tag === "button" && content(node) === "Refresh review");
  assert.ok(refresh);
  const refreshed = refresh.handlers.click();
  await settle();
  // A newer explicit selection must win even if the earlier refresh resolves last.
  picker.value = otherProposalId;
  const selectSecond = picker.handlers.change();
  await settle();
  assert.equal(app.ET.parseRoute().query.get("proposal"), otherProposalId);
  assert.doesNotMatch(content(app.root), /FIRST_READINESS_RECORD/);
  second.resolve(readiness(otherProposalId, "SELECTED_READINESS_RECORD"));
  await selectSecond;
  await settle();
  first.resolve(readiness(proposalId, "STALE_READINESS_MUST_NOT_PAINT"));
  await refreshed;
  await settle();
  assert.match(content(app.root), /SELECTED_READINESS_RECORD/);
  assert.doesNotMatch(content(app.root), /FIRST_READINESS_RECORD|STALE_READINESS_MUST_NOT_PAINT/);
});

test("a late summary or research response cannot paint after navigation", async () => {
  const lateSummary = defer(), lateJob = defer();
  const app = application({ overrides: { "/api/workspace/summary": lateSummary.promise, [`/api/research/jobs/${jobId}`]: lateJob.promise } });
  await app.route();
  await app.route(researchLink(otherExperimentId));
  await app.route(`#/ops?tab=alerts&monitor=${monitorId}&alert=${alertId}`);
  lateSummary.resolve(summary());
  const staleJob = job(); staleJob.request.objective = "STALE_JOB_MUST_NOT_PAINT";
  lateJob.resolve(staleJob);
  await settle();
  assert.equal(app.ET.parseRoute().name, "ops");
  assert.doesNotMatch(content(app.root), /STALE_JOB_MUST_NOT_PAINT|SELECTED_EXPERIMENT_REFUSAL/);
  assert.equal(app.root.querySelectorAll('[data-summary-component="research_jobs"]').length, 0);
});

test("late monitoring evidence cannot replace the currently selected readiness tab", async () => {
  const pending = defer();
  const app = application({ hash: paperLink("readiness", otherProposalId), overrides: { [`/api/monitors/${monitorId}/monitoring`]: pending.promise } });
  await app.route();
  await clickTab(app, "monitoring");
  await clickTab(app, "readiness");
  pending.resolve({ evaluation: { status: "pending", checks: [{ name: "source", passed: false, reason: "STALE_MONITORING_MUST_NOT_PAINT" }] }, incidents: [], investigations: [] });
  await settle();
  selectedTab(app.root, "readiness");
  assert.match(content(app.root), /SELECTED_READINESS_RECORD/);
  assert.doesNotMatch(content(app.root), /STALE_MONITORING_MUST_NOT_PAINT/);
});

test("alert routes retain monitor and alert filters and link directly to monitoring evidence", async () => {
  const href = `#/ops?tab=alerts&monitor=${monitorId}&alert=${alertId}`;
  const app = application({ hash: href });
  await app.route();
  assert.match(content(app.root), /stale collection/);
  assert.doesNotMatch(content(app.root), /other monitor only/);
  assert.ok(links(app.root).some((value) => value === `#/paper/${monitorId}?tab=monitoring`));
  assert.equal(app.ET.parseRoute().query.get("monitor"), monitorId);
  assert.equal(app.ET.parseRoute().query.get("alert"), alertId);
  const reloaded = application({ hash: href });
  await reloaded.route();
  assert.doesNotMatch(content(reloaded.root), /other monitor only/);
});

test("automatic saved proposal restoration preserves one-step Back from paper monitoring to the exact alert", async () => {
  const alertsHref = `#/ops?tab=alerts&monitor=${monitorId}&alert=${alertId}`;
  const pendingReview = defer();
  const app = application({ hash: alertsHref, overrides: { [`/api/monitors/${monitorId}/readiness`]: pendingReview.promise } });
  await app.route();
  const monitorHref = links(app.root).find((href) => href === `#/paper/${monitorId}?tab=monitoring`);
  assert.ok(monitorHref, "Use the monitoring link rendered by the selected alert");
  await app.route(monitorHref);
  assert.deepEqual(app.historySnapshot(), { entries: [alertsHref, monitorHref], index: 1 });
  pendingReview.resolve({ preview: { eligible: false, checks: [] }, proposals: [{ id: proposalId, status: "rejected" }, { id: otherProposalId, status: "rejected" }], control: { events: [] } });
  await settle();
  selectedTab(app.root, "monitoring");
  assert.equal(app.ET.parseRoute().query.get("proposal"), proposalId);
  assert.match(content(app.root), /Awaiting independent prospective dates/);
  const restoredHref = app.window.location.hash;
  assert.deepEqual(app.historySnapshot(), { entries: [alertsHref, restoredHref], index: 1 }, "Automatic default selection must replace the paper entry instead of appending another one");
  await app.back();
  assert.equal(app.window.location.hash, alertsHref, "One Back must restore the exact monitor and alert filters");
  assert.equal(app.ET.parseRoute().name, "ops");
  assert.match(content(app.root), /stale collection/);
  assert.doesNotMatch(content(app.root), /other monitor only/);
  assert.deepEqual(app.historySnapshot(), { entries: [alertsHref, restoredHref], index: 0 }, "Returning to Alerts must not create another paper entry");
  await app.forward();
  selectedTab(app.root, "monitoring");
  assert.deepEqual(app.historySnapshot(), { entries: [alertsHref, restoredHref], index: 1 });
  // Explicit user choices still create navigable entries.
  await clickTab(app, "readiness");
  const readinessHref = app.window.location.hash;
  assert.equal(app.historySnapshot().entries.length, 3);
  const picker = find(app.root, '[aria-label="Frozen readiness proposal"]');
  picker.value = otherProposalId;
  await picker.handlers.change(); await settle();
  assert.equal(app.ET.parseRoute().query.get("proposal"), otherProposalId);
  assert.equal(app.historySnapshot().entries.length, 4);
  await app.back();
  assert.equal(app.window.location.hash, readinessHref);
  assert.equal(app.ET.parseRoute().query.get("proposal"), proposalId);
});

test("an unknown selected alert is visibly refused without substituting another monitor", async () => {
  const app = application({ hash: `#/ops?tab=alerts&monitor=${monitorId}&alert=unknown-record` });
  await app.route();
  unavailable(app.root);
  assert.match(content(app.root), /(?:selected|requested|unknown).*alert.*(?:not found|missing|unavailable)|alert.*(?:not found|does not belong)/i);
  assert.doesNotMatch(content(app.root), /other monitor only/);
});

function courseRecord(id, marker) { return { id, status: "completed", detail: marker, updated_at: "2026-11-16T01:00:00Z", events: [], result: null, request: { mode: "cis1990_demo" } }; }
const courseConfig = () => ({ configured: true, csrf_token: "test-course-csrf", model_name: "test-course-model", latest: courseRecord(jobId, "LATEST_COURSE_MUST_NOT_REPLACE_SELECTED") });

test("saved course route opens the exact retained run instead of config.latest", async () => {
  const app = application({ hash: `#/cis1990/${otherMonitorId}`, overrides: { "/api/cis1990": courseConfig(), [`/api/cis1990/${otherMonitorId}`]: courseRecord(otherMonitorId, "SELECTED_COURSE_RECORD") } });
  await app.route();
  assert.match(content(app.root), /SELECTED_COURSE_RECORD/);
  assert.doesNotMatch(content(app.root), /LATEST_COURSE_MUST_NOT_REPLACE_SELECTED/);
  assert.deepEqual(app.requests.map(({ url }) => url), ["/api/cis1990", `/api/cis1990/${otherMonitorId}`]);
  assert.ok(app.requests.every(({ options }) => options.method === "GET"));
});

test("missing saved course run gives a selected-record refusal without falling back to latest", async () => {
  const app = application({ hash: `#/cis1990/${otherMonitorId}`, overrides: { "/api/cis1990": courseConfig(), [`/api/cis1990/${otherMonitorId}`]: new Error("Saved course run not found") } });
  await app.route();
  assert.match(content(app.root), /Selected course run unavailable/);
  assert.doesNotMatch(content(app.root), /LATEST_COURSE_MUST_NOT_REPLACE_SELECTED/);
});

test("a saved course response with another record id is visibly refused", async () => {
  const app = application({ hash: `#/cis1990/${otherMonitorId}`, overrides: { "/api/cis1990": courseConfig(), [`/api/cis1990/${otherMonitorId}`]: courseRecord(jobId, "WRONG_COURSE_MUST_NOT_PAINT") } });
  await app.route();
  assert.match(content(app.root), /Selected course run unavailable/);
  assert.doesNotMatch(content(app.root), /WRONG_COURSE_MUST_NOT_PAINT|LATEST_COURSE_MUST_NOT_REPLACE_SELECTED/);
});

test("command palette exposes persistent research, deployments, alerts and readiness routes", () => {
  const app = application();
  app.ET.palette();
  const palette = find(app.body, "dialog.palette");
  assert.ok(palette?.open);
  for (const [label, href] of [["New research", "#/research?new=1"], ["Paper deployments", "#/paper"], ["Alerts", "#/ops?tab=alerts"], ["Readiness review", "#/paper?tab=readiness"]]) {
    const row = palette.querySelectorAll("a").find((node) => content(node).startsWith(label));
    assert.equal(row?.attrs.href, href);
  }
  const search = find(palette, "input");
  search.value = "CIS"; search.handlers.input();
  assert.match(content(palette), /Legacy \/ course/);
  assert.ok(links(palette).includes("#/cis1990"));
  assert.equal(app.requests.length, 0);
});

test("owner login reloads a previously refused API view and logout removes its data", async () => {
  let authenticated = false;
  const app = application({ overrides: {
    "/api/workspace/summary": () => authenticated ? summary() : new Error("An authenticated owner session is required"),
    "/api/owner": () => ({ configured: true, authenticated, csrf_token: "owner-csrf" }),
    "/api/owner/login": () => { authenticated = true; return {}; },
    "/api/owner/logout": () => { authenticated = false; return {}; },
  } });
  await app.route();
  assert.match(content(app.root), /authenticated owner session/);
  await app.ET.ownerAccess();
  find(app.body, "[data-owner-password]").value = "CONTROLLED test passphrase";
  await find(app.body, "[data-owner-login]").handlers.click();
  await settle();
  assert.equal(kpiValue(app.root, "Autonomous research jobs"), "67");
  await find(app.body, "[data-owner-logout]").handlers.click();
  await settle();
  assert.match(content(app.root), /authenticated owner session/);
  assert.equal(find(app.root, ".kpi"), null);
});

test("owner authentication resets and awaits an active legacy connection", async () => {
  const app = application({ overrides: { "/api/owner/login": {} } });
  const transitions = [];
  const pending = defer();
  app.ET.workbenchActive = () => true;
  app.ET.legacyWorkbench = {
    deactivate: () => transitions.push("deactivate"),
    activate: async () => { transitions.push("activate"); await pending.promise; transitions.push("ready"); },
  };
  await app.ET.ownerAccess();
  find(app.body, "[data-owner-password]").value = "CONTROLLED test passphrase";
  const signingIn = find(app.body, "[data-owner-login]").handlers.click();
  await settle();
  assert.deepEqual(transitions, ["deactivate", "activate"]);
  pending.resolve();
  await signingIn;
  assert.deepEqual(transitions, ["deactivate", "activate", "ready"]);
});
