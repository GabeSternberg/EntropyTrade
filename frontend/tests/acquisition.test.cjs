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
    this.options = [{}];
    this.classList = { add: (...names) => { this.className += " " + names.join(" "); } };
  }
  set innerHTML(_) { throw new Error("Dynamic evidence must use text nodes"); }
  append(...children) { this.children.push(...children); }
  replaceChildren(...children) { this.children = children; }
  addEventListener() {}
  setAttribute() {}
}

function application() {
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
    fetch: async (url) => ({ ok: true, json: async () => url === "/api/jobs" ? [] : { csrf_token: "test" } }),
  });
  vm.runInContext(fs.readFileSync(path.join(__dirname, "../src/app.js"), "utf8") +
    "\nglobalThis.show = (result, tab) => { state.job = { result }; state.tab = tab; renderResult(); };", context);
  return { context, content: document.getElementById("result-content") };
}
function text(element) { return [element.textContent, ...element.children.map(text)].join("\n"); }
function descendants(element) { return [element, ...element.children.flatMap(descendants)]; }
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
