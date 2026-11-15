"use strict";
// Dependency-free checks of the Demo/Real data boundary and the deterministic demo dataset.
// Rendering and interaction are covered by frontend/browser/redesign.spec.cjs.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const source = (name) => fs.readFileSync(path.join(__dirname, "../src", name), "utf8");

function load({ stored = null } = {}) {
  const storage = new Map(stored ? [["entropytrade.data-mode", stored]] : []);
  const requests = [];
  const window = {
    localStorage: { getItem: (k) => storage.get(k) ?? null, setItem: (k, v) => storage.set(k, String(v)) },
  };
  const context = vm.createContext({
    window, console, setTimeout, URLSearchParams,
    // The shell boots on DOMContentLoaded; keeping readyState "loading" tests the data layer alone.
    document: { readyState: "loading", addEventListener() {} },
    fetch: async (url, options) => { requests.push({ url, options }); return { ok: true, json: async () => ({ url }) }; },
  });
  for (const name of ["ui.js", "demo-data.js", "shell.js"]) vm.runInContext(source(name), context, { filename: name });
  return { ET: window.ET, requests, storage };
}

test("real mode is the default and demo data is refused outside Demo Mode", () => {
  const { ET } = load();
  assert.equal(ET.mode(), "real");
  assert.throws(() => ET.demo(), /only available in Demo Mode/);
});

test("demo mode serves frozen data and disables every API read", async () => {
  const { ET, requests } = load({ stored: "demo" });
  assert.equal(ET.mode(), "demo");
  const data = ET.demo();
  assert.equal(data.data_kind, "demo");
  assert.ok(Object.isFrozen(data) && Object.isFrozen(data.markets) && Object.isFrozen(data.markets[0]));
  assert.throws(() => { data.markets[0].last = 0.5; }, TypeError);
  await assert.rejects(ET.api("/api/jobs"), /disabled in Demo Mode/);
  assert.equal(requests.length, 0);
});

test("real API reads are same-origin GETs under /api/ only", async () => {
  const { ET, requests } = load();
  await ET.api("/api/v1-gates");
  assert.equal(requests.length, 1);
  assert.equal(requests[0].url, "/api/v1-gates");
  assert.equal(requests[0].options.method, "GET");
  assert.equal(requests[0].options.body, undefined);
  assert.equal(requests[0].options.credentials, "same-origin");
  for (const bad of ["https://example.invalid/api/jobs", "/style.css", "//evil/api/x", 42]) {
    await assert.rejects(ET.api(bad), /same-origin \/api\//);
  }
  assert.equal(requests.length, 1);
});

test("an unreachable resource does not blank the others", async () => {
  const { ET } = load();
  const result = await ET.apiAll({ ok: "/api/catalog", bad: "/not-api" });
  assert.equal(result.ok.ok, true);
  assert.equal(result.bad.ok, false);
});

test("demo data is deterministic across loads and internally consistent", () => {
  const a = load({ stored: "demo" }).ET.demo();
  const b = load({ stored: "demo" }).ET.demo();
  assert.equal(JSON.stringify(a), JSON.stringify(b));
  for (const m of a.markets) {
    assert.equal(m.data_kind, "demo");
    if (m.status === "open") {
      assert.ok(m.yes_bid > 0 && m.yes_bid < m.yes_ask && m.yes_ask < 1, m.ticker);
    }
  }
  const p = a.paper;
  const deployed = p.positions.reduce((sum, x) => sum + x.cost, 0);
  assert.ok(Math.abs(deployed - p.deployed) < 0.01);
  const byCategory = p.by_category.reduce((sum, c) => sum + c.exposure, 0);
  assert.ok(Math.abs(byCategory - deployed) < 0.05);
  for (const x of p.positions) assert.ok(x.cost <= 250, "per-event cap respected");
  const tools = load({ stored: "demo" }).ET.demoTools;
  for (const st of a.strategies.filter((s) => s.metrics)) {
    assert.ok(Math.abs(st.metrics.sharpe) < 3, `${st.name} has a plausible Sharpe ratio`);
    // The 1× fees / 0¢ slippage cell is the reported backtest return.
    assert.equal(tools.feeGrid(st).values[2][0], st.metrics.total_return);
  }
});
