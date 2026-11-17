"use strict";
// Render the actual research view and interface kit; this DOM double complements the
// managed-Chromium acceptance and makes refused/missing metric behavior deterministic.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

class Element {
  constructor(tag, text = "") { this.tag = tag; this.textContent = text; this.children = []; this.attrs = {}; this.style = {}; this.dataset = {}; this.handlers = {}; }
  set innerHTML(_) { throw new Error("Evidence must be rendered as text"); }
  append(...nodes) { this.children.push(...nodes); }
  replaceChildren(...nodes) { this.children = nodes; }
  setAttribute(name, value) { this.attrs[name] = String(value); }
  getAttribute(name) { return this.attrs[name]; }
  addEventListener(name, fn) { this.handlers[name] = fn; }
  querySelector(tag) { return descendants(this).slice(1).find((e) => e.tag === tag); }
}
const descendants = (element) => [element, ...element.children.flatMap(descendants)];
const content = (element) => [element.textContent, ...element.children.map(content)].join("\n");

async function render(experiments) {
  const root = new Element("main");
  const job = {
    id: "demo", family: "weather", universe: ["KXHIGHPHIL"], status: "awaiting_observations", detail: "Awaiting evidence", created_at: "2026-11-15T00:00:00Z", updated_at: "2026-11-15T00:00:00Z",
    request: { objective: "Controlled research presentation", provider: { provider: "local_templates" } },
    events: [], scope: "No order path exists", hypotheses: [], experiments,
  };
  const window = { ET: {} };
  const context = vm.createContext({ window, Node: Element, document: {
    createElement: (tag) => new Element(tag), createElementNS: (_, tag) => new Element(tag), createTextNode: (text) => new Element("#text", text),
  } });
  for (const file of ["ui.js", "views-research.js"]) vm.runInContext(fs.readFileSync(path.join(__dirname, "../src", file), "utf8"), context);
  Object.assign(window.ET, { mode: () => "demo", demo: () => ({ research: { jobs: [job] } }), pageHeader: (text) => window.ET.h("h1", text) });
  await window.ET.views.research(root, { params: ["demo"] });
  const tab = descendants(root).find((e) => e.attrs.role === "tab" && content(e).includes("Modeling & validation"));
  assert.ok(tab, "Modeling history remains available even when no experiment succeeded");
  tab.handlers.click();
  return root;
}

function experiment(overrides = {}) {
  return { id: "sha256:" + "a".repeat(64), hypothesis_id: "h-123", status: "awaiting_data", updated_at: "2026-11-15T00:00:00Z", config: {}, result: {}, ...overrides };
}

test("research modeling: empty history has no invented metrics", async () => {
  const view = await render([]);
  assert.match(content(view), /No experiments recorded/);
  assert.doesNotMatch(content(view), /Brier score|Log loss|Recorded backtest performance/);
});

test("research modeling: precise refusals, no fabricated zero scores or returns", async () => {
  const view = await render([experiment({ result: {
    eligibility: { eligible: false, reasons: ["Only 7 independent events; at least 60 required.", "<script>source</script>"], independent_events: 7, independent_dates: 7, complete_events: 7 },
    backtest: { status: "blocked", execution_fidelity: "predictive_only", reasons: ["Missing decision-time sized books", "Fees are uncertified"] },
    validation: { status: "awaiting_data", holdout_evaluated: false, prospective: false },
  } })]);
  for (const expected of [/Only 7 independent events/, /<script>source<\/script>/, /Missing decision-time sized books/, /Fees are uncertified/, /No fitted validation metrics/, /Not evaluated/, /historical predictions are not prospective/, /Real-money submission/, /Disabled/]) assert.match(content(view), expected);
  assert.equal(descendants(view).filter((e) => e.tag === "script").length, 0);
  assert.doesNotMatch(content(view), /Brier score|Log loss|Recorded backtest performance/);
});

test("research modeling: frozen metrics and baselines retain synthetic label and provenance", async () => {
  const view = await render([experiment({ status: "evaluated", result: {
    data_kind: "synthetic", eligibility: { eligible: true, independent_events: 100, independent_dates: 100, complete_events: 90 },
    config: { seed: 17, min_train_events: 60 },
    models: { ridge: { artifact_hash: "sha256:fitted", training_events: 60, calibration: "platt", metrics: { brier: .125, log_loss: .42 } } },
    baselines: { raw_forecast: { metrics: { brier: .2, log_loss: .5 } } },
    validation: { status: "evaluated", partition_hash: "sha256:partition", holdout_evaluated: false, prospective: false, partitions: { fit: { events: 60, dates: 60 }, holdout: { events: 10, dates: 10, labels: "WITHHELD_LABELS_MUST_NOT_RENDER" } }, walk_forward: [{}, {}] },
    backtest: { status: "blocked", execution_fidelity: "predictive_only", reasons: ["No authentic execution evidence"] },
    provenance: { feature_artifacts: ["sha256:feature"], dataset_versions: ["sha256:dataset"] }, report: { hash: "sha256:report" },
  } })]);
  for (const expected of [/CONTROLLED SYNTHETIC/, /Brier score/, /Log loss/, /0.1250/, /0.2000/, /platt/, /sha256:feature/, /sha256:dataset/, /sha256:report/, /historical predictions are not prospective/]) assert.match(content(view), expected);
  assert.doesNotMatch(content(view), /Recorded backtest performance|WITHHELD_LABELS_MUST_NOT_RENDER/);
});

test("research modeling: interrupted training error stays visible with no results", async () => {
  const view = await render([experiment({ status: "failed", error: { type: "TrainingFailure", reason: "Bounded worker failed" } })]);
  assert.match(content(view), /TrainingFailure: Bounded worker failed/);
  assert.match(content(view), /No fitted validation metrics/);
  assert.doesNotMatch(content(view), /Brier score|Recorded backtest performance/);
});

test("research route: returning from a demo job cannot request a fictional real job", async () => {
  const root = new Element("main");
  const routes = [];
  const window = { ET: { views: {}, mode: () => "real", go: (route) => routes.push(route), unavailable: (title, body) => new Element("p", title + " " + body), api: () => { throw new Error("Fictional IDs must not reach the real API"); } } };
  const context = vm.createContext({ window });
  vm.runInContext(fs.readFileSync(path.join(__dirname, "../src/views-research.js"), "utf8"), context);
  await window.ET.views.research(root, { params: ["demo-weather-job"] });
  assert.deepEqual(routes, []);
  assert.match(content(root), /cannot be selected/);
});


test("research backtests: recorded scenarios display simulated accounting only", async () => {
  const view = await render([experiment({ status: "evaluated", result: {
    data_kind: "synthetic", eligibility: { eligible: true },
    backtest: { status: "backtested", execution_fidelity: "order_book_simulation", reasons: [], performance: { scenarios: [
      { scenario: "base", fill_count: 12, events_traded: 10, net_pnl: "12.50", fees_paid: "2.25", drawdown_at_cost: "4.00", unsettled_positions: 0 },
    ] } },
  } })]);
  for (const expected of [/Recorded backtest performance/, /Simulated fills/, /Net P&L/, /\$12.50/, /\$2.25/, /Drawdown at cost/, /\$4.00/, /modeled snapshot fills/, /do not authorize deployment/, /Real-money submission/, /Disabled/]) assert.match(content(view), expected);
});
