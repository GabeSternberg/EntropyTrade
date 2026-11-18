"use strict";
// Run the shipped legacy workbench with explicit shell lifecycle and controlled transport.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

class Element {
  constructor(tag) {
    this.tag = tag; this.children = []; this.textContent = ""; this.dataset = {}; this.attributes = {};
    this.handlers = new Map(); this.options = [{ value: "recorded" }, { value: "provider" }];
    this.selectedOptions = []; this.value = ""; this.hidden = false; this.disabled = false;
    this.classList = { add: (...names) => { this.className = [this.className, ...names].join(" "); } };
  }
  set innerHTML(_) { throw new Error("Evidence must remain text"); }
  append(...children) { this.children.push(...children); }
  replaceChildren(...children) { this.children = children; this.textContent = ""; }
  setAttribute(name, value) { this.attributes[name] = String(value); }
  addEventListener(type, handler) { const handlers = this.handlers.get(type) || []; handlers.push(handler); this.handlers.set(type, handlers); }
  removeEventListener(type, handler) { this.handlers.set(type, (this.handlers.get(type) || []).filter((entry) => entry !== handler)); }
  async emit(type) { const event = { prevented: false, preventDefault() { this.prevented = true; }, stopImmediatePropagation() {} }; for (const handler of this.handlers.get(type) || []) await handler(event); return event; }
}
const text = (element) => [element.textContent, ...element.children.map(text)].join(" ");
const walk = (element) => [element, ...element.children.flatMap(walk)];
const tick = async () => { for (let i = 0; i < 3; i++) await new Promise((resolve) => setImmediate(resolve)); };
const job = (marker = "CURRENT_JOB", status = "running") => ({ id: "same-job", status, updated_at: marker, created_at: "2026-11-17T00:00:00Z", request: { idea: marker, family: "weather", mode: "recorded" }, detail: marker, events: [], result: null });
const monitor = (marker = "CURRENT_MONITOR") => ({ id: "same-monitor", family: "weather", status: "active", source_kind: "legacy", interval_seconds: 300, cycle_count: 0, next_at: marker, failures: 0, events: [], alerts: [], contracts: [], cycles: [] });
const evaluation = { status: "insufficient", counts: {}, diagnostics: [], observations: [], cycle_statuses: {}, cycle_failures: [], limitations: [] };
function application({ initiallyVisible = false, initialMode = "real" } = {}) {
  const nodes = new Map(), requests = [], timers = new Map(), documentHandlers = new Map(), overrides = new Map();
  let mode = initialMode, workbench = initiallyVisible, timerId = 0;
  const get = (id) => { if (!nodes.has(id)) nodes.set(id, new Element("div")); return nodes.get(id); };
  get("workbench-view").hidden = !initiallyVisible; get("mode").value = "recorded"; get("family").value = "weather";
  const document = { visibilityState: "visible", getElementById: get, createElement: (tag) => new Element(tag), querySelectorAll: () => [], addEventListener: (type, handler) => documentHandlers.set(type, handler) };
  const window = { ET: { mode: () => mode, workbenchActive: () => workbench && !get("workbench-view").hidden, fmt: { decisionPoint: () => "retained decision" } } };
  const defaults = {
    "/api/catalog": { csrf_token: "real-csrf" }, "/api/jobs": [], "/api/monitors": [], "/api/alerts": { alerts: [] },
    "/api/weather/datasets": [], "/api/weather/schedules": [], "/api/weather/label-partitions": [],
    "/api/weather/partitions": { partitions: [], total_inputs: 0, partition_size: 128 }, "/api/fees": { versions: [] },
    "/api/v1-gates": { open: [], gates: [], v1_complete: false },
    "/api/jobs/same-job": job(), "/api/monitors/same-monitor": monitor(), "/api/monitors/same-monitor/evaluation": evaluation,
  };
  const context = vm.createContext({ document, window, AbortController, crypto: { randomUUID: () => "fixture-id" },
    setInterval: (callback) => { timers.set(++timerId, callback); return timerId; }, clearInterval: (id) => timers.delete(id),
    fetch: async (url, options) => {
      requests.push({ url, options });
      const value = overrides.has(url) ? overrides.get(url) : defaults[url];
      if (value === undefined) throw new Error("Unexpected request: " + url);
      const result = typeof value === "function" ? await value(options) : await value;
      return { ok: true, json: async () => result };
    },
  });
  vm.runInContext(fs.readFileSync(path.join(__dirname, "../src/app.js"), "utf8") +
    "\nglobalThis.workbenchTest = { api, poll: () => poll(legacy.epoch), snapshot: () => ({ ready: legacy.ready, token: state.token, job: state.job, monitor: state.monitor }) };", context);
  const hooks = window.ET.legacyWorkbench;
  return { get, requests, timers, overrides, hooks, document, access: context.workbenchTest,
    enter() { mode = "real"; workbench = true; get("workbench-view").hidden = false; return hooks.activate(); },
    leave() { workbench = false; get("workbench-view").hidden = true; hooks.deactivate(); },
    demo() { mode = "demo"; hooks.deactivate(); },
    setMode(value) { mode = value; },
    async visibility(value) { document.visibilityState = value; documentHandlers.get("visibilitychange")(); await tick(); },
  };
}
const cancelled = (error) => error.cancelled === true;

test("direct initial Real workbench route activates after deferred controller registration", async () => {
  const app = application({ initiallyVisible: true }); await tick();
  assert.equal(app.requests.filter((request) => request.url === "/api/catalog").length, 1);
  assert.equal(app.access.snapshot().ready, true);
  assert.equal(app.get("submit").disabled, false);
  assert.equal(app.timers.size, 1);
  await app.hooks.activate();
  assert.equal(app.requests.filter((request) => request.url === "/api/catalog").length, 1);
  const demo = application({ initiallyVisible: true, initialMode: "demo" }); await tick();
  assert.equal(demo.requests.length, 0); assert.equal(demo.timers.size, 0);
});

test("provider selection during initialization reconciles consent before submission", async () => {
  const app = application(); let releaseHistory;
  app.overrides.set("/api/catalog", { csrf_token: "real-csrf", provider_enabled: true,
    research_provider: { provider: "openai", model_name: "controlled" } });
  app.overrides.set("/api/jobs", new Promise((resolve) => { releaseHistory = resolve; }));
  const pending = app.enter(); await tick();
  app.get("reasoning").value = "provider";
  await app.get("reasoning").emit("change");
  assert.equal(app.get("provider-options").hidden, true);
  assert.equal(app.get("submit").disabled, true);
  releaseHistory([]); await pending;
  assert.equal(app.get("provider-options").hidden, false);
  assert.equal(app.get("enable-provider").required, true);
  assert.equal(app.get("enable-provider").checked, false);
  assert.equal(app.get("submit").disabled, false);
});

test("rendered history stays inert until all panels and handlers are ready", async () => {
  const app = application(); let releaseDatasets;
  app.overrides.set("/api/monitors", [monitor()]);
  app.overrides.set("/api/weather/datasets", new Promise((resolve) => { releaseDatasets = resolve; }));
  const pending = app.enter(); await tick();
  const button = walk(app.get("shadow-history")).find((element) => element.tag === "button");
  assert.ok(button, "history renders before later panels finish");
  assert.equal(app.get("workbench-view").inert, true);
  assert.equal(app.get("workbench-view").attributes["aria-busy"], "true");
  releaseDatasets([]); await pending;
  assert.equal(app.get("workbench-view").inert, false);
  assert.equal(app.get("workbench-view").attributes["aria-busy"], "false");
  await button.emit("click");
  assert.match(text(app.get("shadow-evidence")), /CURRENT_MONITOR/);
  app.leave();
  assert.equal(app.get("workbench-view").inert, true);
});

test("legacy script load, hidden workbench and Demo dispatch no reads or writes", async () => {
  const app = application(); await tick();
  assert.equal(app.requests.length, 0); assert.equal(app.timers.size, 0); assert.equal(app.get("submit").disabled, true);
  for (const body of [undefined, {}]) await assert.rejects(app.access.api("/api/jobs", body), cancelled);
  await assert.rejects(app.hooks.activate(), cancelled);
  await app.enter(); const before = app.requests.length;
  // Dispatch checks the actual shell/DOM boundary even before a lifecycle callback runs.
  app.setMode("demo");
  for (const body of [undefined, {}]) await assert.rejects(app.access.api("/api/jobs", body), cancelled);
  app.setMode("real"); app.get("workbench-view").hidden = true;
  for (const body of [undefined, {}]) await assert.rejects(app.access.api("/api/jobs", body), cancelled);
  assert.equal(app.requests.length, before);
});

test("activation is lazy, concurrent readiness is shared, and writes use Real CSRF", async () => {
  const app = application(); let resolveCatalog;
  app.overrides.set("/api/catalog", new Promise((resolve) => { resolveCatalog = resolve; }));
  const first = app.enter(), second = app.hooks.activate();
  assert.equal(app.requests.length, 1); assert.equal(app.get("submit").disabled, true);
  await app.get("research-form").emit("submit");
  assert.equal(app.requests.length, 1, "user controls refuse before readiness");
  resolveCatalog({ csrf_token: "activation-csrf" }); await Promise.all([first, second]);
  assert.equal(app.requests.filter((request) => request.url === "/api/catalog").length, 1);
  assert.equal(app.timers.size, 1); assert.equal(app.get("submit").disabled, false);
  app.overrides.set("/api/jobs", (options) => options.method === "POST" ? { id: "same-job" } : []);
  await app.get("research-form").emit("submit");
  const write = app.requests.find((request) => request.options.method === "POST");
  assert.equal(write.options.headers["X-EntropyTrade-CSRF"], "activation-csrf");
  assert.equal(write.options.credentials, "same-origin");
  assert.match(text(app.get("form-message")), /Request saved/);
});

test("hidden and Demo navigation stop timers and saved static handlers stay stale after reactivation", async () => {
  const app = application(); await app.enter();
  const savedSubmit = app.get("research-form").handlers.get("submit")[0], savedRefresh = app.get("refresh").handlers.get("click")[0];
  const savedPoll = [...app.timers.values()][0];
  app.leave(); const before = app.requests.length;
  await savedSubmit({ preventDefault() {}, stopImmediatePropagation() {} }); await savedRefresh({ preventDefault() {}, stopImmediatePropagation() {} }); await savedPoll();
  assert.equal(app.requests.length, before); assert.equal(app.timers.size, 0); assert.equal(app.get("submit").disabled, true);
  await app.enter(); const reentered = app.requests.length;
  await savedSubmit({ preventDefault() {}, stopImmediatePropagation() {} }); await savedRefresh({ preventDefault() {}, stopImmediatePropagation() {} }); await savedPoll();
  assert.equal(app.requests.length, reentered, "old wrappers cannot act in a newer activation");
  await app.get("refresh").emit("click"); assert.equal(app.requests.length, reentered + 1);
  app.demo(); const demoBefore = app.requests.length;
  await app.get("research-form").emit("submit"); await app.get("refresh").emit("click");
  assert.equal(app.requests.length, demoBefore); assert.equal(app.timers.size, 0);
});

test("background visibility aborts work and resumes only a visible Real workbench", async () => {
  const app = application(); await app.enter();
  const oldSignal = app.requests[0].options.signal;
  await app.visibility("hidden"); const before = app.requests.length;
  assert.equal(oldSignal.aborted, true); assert.equal(app.timers.size, 0);
  await assert.rejects(app.access.api("/api/jobs"), cancelled);
  await app.visibility("visible");
  assert.equal(app.requests.filter((request) => request.url === "/api/catalog").length, 2); assert.equal(app.timers.size, 1);
  app.demo(); const demoBefore = app.requests.length; await app.visibility("hidden"); await app.visibility("visible");
  assert.equal(app.requests.length, demoBefore); assert.ok(before < app.requests.length);
});

test("aborted initialization and pending writes reject without undefined results or stale UI", async () => {
  const app = application(); let resolveCatalog;
  app.overrides.set("/api/catalog", new Promise((resolve) => { resolveCatalog = resolve; }));
  const pending = app.enter(); app.leave();
  resolveCatalog({ csrf_token: "stale-csrf" }); await assert.rejects(pending, cancelled);
  assert.equal(app.access.snapshot().token, null); assert.equal(text(app.get("connection")), "");
  app.overrides.delete("/api/catalog"); await app.enter();
  let resolveWrite; app.overrides.set("/api/jobs", new Promise((resolve) => { resolveWrite = resolve; }));
  const submitted = app.get("research-form").emit("submit"); await tick();
  app.leave(); resolveWrite({ id: "same-job" }); await submitted;
  assert.equal(app.get("submit").disabled, true);
  assert.doesNotMatch(text(app.get("form-message")), /Request saved/);
  assert.equal(app.requests.filter((request) => request.url === "/api/jobs/same-job").length, 0);
  assert.equal(text(app.get("connection")), "");
});

test("awaited selection survives lazy initialization and reentry rebuilds dynamic controls", async () => {
  const app = application();
  const ready = app.enter(), selected = app.hooks.selectJob("same-job");
  await Promise.all([ready, selected]); assert.match(text(app.get("run-header")), /CURRENT_JOB/);
  const oldCancel = walk(app.get("run-header")).find((element) => element.textContent === "Cancel run");
  app.leave(); await app.enter();
  const newCancel = walk(app.get("run-header")).find((element) => element.textContent === "Cancel run");
  assert.notEqual(newCancel, oldCancel);
  const before = app.requests.length; await oldCancel.emit("click"); assert.equal(app.requests.length, before);
  app.overrides.set("/api/jobs/same-job/cancel", {}); await newCancel.emit("click");
  assert.ok(app.requests.some((request) => request.url === "/api/jobs/same-job/cancel" && request.options.method === "POST"));
});

test("late same-ID job responses from selection, polling and older activation never repaint", async () => {
  const app = application(); await app.enter(); await app.hooks.selectJob("same-job");
  let resolveOld; app.overrides.set("/api/jobs/same-job", new Promise((resolve) => { resolveOld = resolve; }));
  const oldPoll = app.access.poll(); await tick();
  app.overrides.set("/api/jobs/same-job", job("NEWER_SAME_ID")); await app.hooks.selectJob("same-job");
  resolveOld(job("STALE_POLL")); await oldPoll;
  assert.match(text(app.get("run-header")), /NEWER_SAME_ID/); assert.doesNotMatch(text(app.get("run-header")), /STALE_POLL/);
  let resolveSelection; app.overrides.set("/api/jobs/same-job", new Promise((resolve) => { resolveSelection = resolve; }));
  const oldSelection = app.hooks.selectJob("same-job"); await tick(); app.leave();
  app.overrides.set("/api/jobs/same-job", job("NEW_ACTIVATION")); await app.enter();
  resolveSelection(job("STALE_ACTIVATION")); await assert.rejects(oldSelection, cancelled);
  assert.match(text(app.get("run-header")), /NEW_ACTIVATION/); assert.doesNotMatch(text(app.get("run-header")), /STALE_ACTIVATION/);
});

test("same-ID monitor selection discards older responses and old monitor actions", async () => {
  const app = application(); await app.enter(); await app.hooks.selectMonitor("same-monitor");
  const oldPause = walk(app.get("shadow-evidence")).find((element) => element.textContent === "Pause monitor");
  let resolveOld; app.overrides.set("/api/monitors/same-monitor", new Promise((resolve) => { resolveOld = resolve; }));
  const older = app.hooks.selectMonitor("same-monitor"); await tick();
  app.overrides.set("/api/monitors/same-monitor", monitor("NEWER_MONITOR")); await app.hooks.selectMonitor("same-monitor");
  resolveOld(monitor("STALE_MONITOR")); await older;
  assert.match(text(app.get("shadow-evidence")), /NEWER_MONITOR/); assert.doesNotMatch(text(app.get("shadow-evidence")), /STALE_MONITOR/);
  app.leave(); await app.enter(); const before = app.requests.length; await oldPause.emit("click");
  assert.equal(app.requests.length, before);
});
