"use strict";
// Real managed Chromium + localhost. Controlled source/clock injection is explicitly isolated.
const { test, expect, chromium } = require("@playwright/test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { spawn, spawnSync } = require("node:child_process");
const { createHash } = require("node:crypto");
const pause = ms => new Promise(resolve => setTimeout(resolve, ms));
const sha = bytes => createHash("sha256").update(bytes).digest("hex");

async function procedure(page, browser, controlled) {
  const repo = path.resolve(__dirname, "../..");
  const kind = controlled ? "controlled" : "authentic";
  const evidence = path.join(process.env.ENTROPYTRADE_BROWSER_EVIDENCE, kind);
  let workspace = process.env.ENTROPYTRADE_BROWSER_WORKSPACE + "-forward-" + kind;
  const python = process.env.ENTROPYTRADE_BROWSER_PYTHON || path.join(repo, ".venv/bin/python");
  const port = Number(process.env.ENTROPYTRADE_BROWSER_PORT || 43151);
  const origin = `http://127.0.0.1:${port}`;
  assert(path.isAbsolute(workspace) && workspace.startsWith(path.join(repo, "data/cache/")));
  assert(!fs.existsSync(workspace), "Fresh workspace required");
  assert(chromium.executablePath().startsWith(path.join(__dirname, ".browsers/")));
  fs.mkdirSync(evidence, { recursive: true });
  const receiptFile = path.join(evidence, "browser-receipt.json");
  assert(!fs.existsSync(receiptFile));
  const receipt = { status: "running", kind, started_at: new Date().toISOString(),
    executable: chromium.executablePath(), browser: browser.version(), origin, workspace,
    operations: [], screenshots: [], downloads: [], page_errors: [],
    evidence_scope: controlled ? "CONTROLLED source reports and scheduling clock; no empirical data/performance" :
      "Authentic original whole shadow receipt replay plus new authentic read-only label acquisition. No clock override.",
    limitations: ["V1 incomplete. Sparse history, missing empirical models and uncertified fees still refuse trading; submissions disabled."] };
  const save = () => fs.writeFileSync(receiptFile, JSON.stringify(receipt, null, 2) + "\n");
  const env = { PATH: "/usr/bin:/bin", PYTHONNOUSERSITE: "1", PYTHONDONTWRITEBYTECODE: "1",
    OMP_NUM_THREADS: "1", OPENBLAS_NUM_THREADS: "1", TZ: "UTC",
    PYTHONPATH: path.join(repo, "backend") + ":" + path.join(repo, "backend/src") };
  const phaseFile = workspace + "-phase.json";
  let phaseEpoch = 0;
  function phase(value, seconds = 0) {
    phaseEpoch += seconds;
    fs.writeFileSync(phaseFile + ".pending", JSON.stringify({ phase: value, now: new Date(Date.UTC(2026, 9, 31, 12) + phaseEpoch * 1000).toISOString() }));
    fs.renameSync(phaseFile + ".pending", phaseFile);
    receipt.operations.push({ action: "CONTROLLED-source", phase: value, seconds: phaseEpoch }); save();
  }
  function command(args, name) {
    const result = spawnSync(python, args, { cwd: repo, env, encoding: "utf8", timeout: 120_000 });
    fs.writeFileSync(path.join(evidence, name + ".log"), result.stdout + result.stderr);
    assert.equal(result.status, 0, result.stdout + result.stderr);
  }
  let server, epoch = 0;
  async function start() {
    assert(!await fetch(origin + "/api/catalog").catch(() => null), "Port occupied");
    const log = fs.openSync(path.join(evidence, `server-${++epoch}.log`), "a");
    const args = controlled ? ["-m", "tests.integration.forward_validation_fixture", workspace, "--phase", phaseFile, "--port", String(port)] :
      ["-m", "entropytrade.api.server", "--workspace", workspace, "--port", String(port)];
    server = spawn(python, args, { cwd: repo, env, stdio: ["ignore", log, log] }); fs.closeSync(log);
    for (let i = 0; i < 150; i++) {
      if (server.exitCode !== null) throw new Error(`Listener exited ${server.exitCode}`);
      const response = await fetch(origin + "/api/catalog").catch(() => null);
      if (response?.ok) {
        const catalog = await response.json();
        assert.equal(catalog.submission_enabled, false); assert.equal(catalog.provider_enabled, false);
        receipt.operations.push({ action: "start", epoch, workspace }); save(); return;
      }
      await pause(100);
    }
    throw new Error("Listener startup timeout");
  }
  async function stop() {
    if (!server || server.exitCode !== null || server.signalCode !== null) return;
    server.kill("SIGINT");
    for (let i = 0; i < 200 && server.exitCode === null && server.signalCode === null; i++) await pause(100);
    if (server.exitCode === null && server.signalCode === null) { server.kill("SIGKILL"); throw new Error("Graceful shutdown timeout"); }
    receipt.operations.push({ action: "stop", epoch }); save();
  }
  async function shot(name) {
    const file = name + ".png";
    await page.locator(name === "frozen-insufficient-data" ? "#weather-readiness" : "section[aria-labelledby=forward-validation-title]").screenshot({ path: path.join(evidence, file) });
    receipt.screenshots.push({ file, sha256: sha(fs.readFileSync(path.join(evidence, file))) }); save();
  }
  async function download(name) {
    const pending = page.waitForEvent("download");
    await page.getByRole("link", { name: "Download forward validation state", exact: true }).click();
    await (await pending).saveAs(path.join(evidence, name));
    const bytes = fs.readFileSync(path.join(evidence, name));
    receipt.downloads.push({ file: name, sha256: sha(bytes) }); save(); return bytes;
  }
  let scheduleId, cancelledRequest;
  async function waitFor(predicate) {
    let value;
    for (let i = 0; i < 400; i++) {
      const response = await fetch(origin + "/api/weather/schedules/" + scheduleId);
      value = await response.json();
      if (response.ok && predicate(value)) { await page.getByRole("button", { name: "Refresh forward validation", exact: true }).click(); return value; }
      await pause(100);
    }
    throw new Error("Backlog did not reach expected state: " + JSON.stringify(value));
  }
  async function paused() {
    await page.getByRole("button", { name: "Pause forward validation", exact: true }).click();
    return waitFor(s => s.status === "paused" && !s.inflight);
  }
  async function resumed() {
    await page.getByRole("button", { name: "Resume forward validation", exact: true }).click();
  }
  page.on("pageerror", error => { receipt.page_errors.push(error.message); save(); });
  save();
  try {
    if (controlled) { phase("preliminary"); command(["-m", "tests.integration.forward_validation_fixture", workspace], "seed-controlled"); }
    else {
      const metadata = workspace + "-import.json";
      command(["-m", "tests.integration.shadow_history_fixture", workspace, metadata, "--authentic"], "seed-authentic");
      fs.copyFileSync(metadata, path.join(evidence, "authentic-inputs.json"));
    }
    await start(); await page.goto(origin);
    await expect(page.locator("#submit")).toBeEnabled();
    if (!controlled) {
      await page.getByRole("button", { name: "Freeze retained weather dataset", exact: true }).click();
      await expect(page.locator("#weather-message")).toContainText("Immutable dataset selected");
    }
    await expect(page.locator("#weather-readiness")).toContainText("insufficient data");
    assert.equal((await (await fetch(origin + "/api/weather/schedules")).json()).length, 0);
    await page.getByRole("button", { name: "Enable forward validation", exact: true }).click();
    await expect(page.locator("#weather-schedule-message")).toContainText("opt-in is required");
    await page.locator("#weather-schedule-follow").check();
    await page.locator("#weather-schedule-optin").check();
    await page.locator("#weather-schedule-interval").selectOption("300");
    const pending = page.waitForResponse(r => r.url() === origin + "/api/weather/schedules" && r.request().method() === "POST");
    await page.getByRole("button", { name: "Enable forward validation", exact: true }).click();
    const response = await pending; assert.equal(response.status(), 202);
    scheduleId = (await response.json()).config.id;
    let result = await waitFor(s => !s.inflight && s.work.length === (controlled ? 12 : 2) && s.work.every(w => w.attempts >= 1 && w.last_batch));
    receipt.operations.push({ action: "initial-source-results", schedule: result }); save();
    if (controlled) {
      assert.equal(result.counts.retry, 12);
      await expect(page.locator("#weather-schedules")).toContainText("12 retry");
      await shot("preliminary-backlog");
      await paused(); phase("outage", 300); await resumed();
      result = await waitFor(s => !s.inflight && s.work.every(w => w.attempts === 2));
      assert(result.work.every(w => w.failures === 2 && w.detail.includes("HTTP 503")));
      await expect(page.locator("#weather-schedules")).toContainText("HTTP 503");
      await shot("outage-backoff");
      await paused(); phase("official", 600); await resumed();
      result = await waitFor(s => !s.inflight && s.counts.verified === 12);
      assert(result.work.every(w => w.attempts === 3));
      await shot("official-progress");
      await paused(); phase("revised", 86400); await resumed();
      result = await waitFor(s => !s.inflight && s.counts.verified === 12 && s.work.every(w => w.attempts === 4));
      const rows = await (await fetch(origin + "/api/weather/labels")).json();
      const observations = rows.flatMap(r => r.result.records).map(r => r.observation).filter(Boolean);
      assert.deepEqual([...new Set(observations.map(o => Number(o.value)))].sort(), [70, 72]);
      assert(observations.every(o => o.available_at === o.received_at));
      receipt.operations.push({ action: "controlled-revisions", schedules: result, batch_versions: rows.map(r => r.batch_version) }); save();
      await paused(); phase("before-start", 86400); await resumed();
      const marker = phaseFile + ".startup.json";
      let registered;
      for (let i = 0; i < 400; i++) {
        registered = fs.existsSync(marker) ? JSON.parse(fs.readFileSync(marker)) : null;
        if (registered?.stage === "registered") break;
        await pause(25);
      }
      assert.equal(registered?.stage, "registered", "Acquisition did not reach startup barrier");
      const requestId = registered.id;
      const beforeStart = (await (await fetch(origin + "/api/weather/labels")).json()).find(r => r.id === requestId);
      assert.equal(beforeStart.status, "running", "Ownership and running transition must be atomic");
      assert.deepEqual(beforeStart.receipts, []);
      await paused(); phase("official");
      let released;
      for (let i = 0; i < 400; i++) {
        released = JSON.parse(fs.readFileSync(marker));
        if (released.stage === "released") break;
        await pause(25);
      }
      assert.equal(released.stage, "released");
      const afterPause = (await (await fetch(origin + "/api/weather/labels")).json()).find(r => r.id === requestId);
      assert.equal(afterPause.status, "interrupted");
      assert.deepEqual(afterPause.receipts, []);
      cancelledRequest = afterPause;
      await page.getByRole("button", { name: "Refresh label acquisition", exact: true }).click();
      await expect(page.locator("#weather-labels")).toContainText("interrupted");
      receipt.operations.push({ action: "pause-at-acquisition-startup-barrier", before: beforeStart, after: afterPause }); save();
      await shot("cancelled-before-start");
    } else {
      const rows = await (await fetch(origin + "/api/weather/labels")).json();
      assert(rows.length >= 1);
      assert(rows.flatMap(r => r.receipts).every(r => r.received_at && r.url.startsWith("https://weather.com/kalshi/api/climate/primary?date=")));
      receipt.operations.push({ action: "authentic-new-acquisition", acquisitions: rows }); save();
      await page.getByRole("button", { name: "Refresh label acquisition", exact: true }).click();
      await expect(page.locator("#weather-labels")).toContainText("Receipt availability is never backdated");
      await shot("authentic-source-progress");
    }
    if (!controlled) await paused();
    const stateBytes = await download("paused-state.json");
    await page.getByRole("button", { name: "Freeze retained weather dataset", exact: true }).click();
    await expect(page.locator("#weather-message")).toContainText("Immutable dataset selected");
    if (controlled) await expect(page.locator("#weather-readiness")).toContainText("12 source-matched scalar labels");
    await expect(page.locator("#weather-readiness")).toContainText("insufficient data");
    await shot("frozen-insufficient-data");
    await stop(); await start(); await page.goto(origin);
    await expect(page.locator("#weather-schedules")).toContainText("Forward validation · paused");
    assert.deepEqual(await download("restart-state.json"), stateBytes);
    if (cancelledRequest) {
      const rows = await (await fetch(origin + "/api/weather/labels")).json();
      assert.deepEqual(rows.find(r => r.id === cancelledRequest.id), cancelledRequest);
      receipt.operations.push({ action: "restart-preserves-interrupted-request", id: cancelledRequest.id }); save();
    }
    await shot("restart-paused");
    await stop();
    const archive = path.join(repo, "data/cache", path.basename(workspace) + ".zip");
    command(["-m", "entropytrade.api.recovery", "snapshot", "--workspace", workspace, "--archive", archive], "snapshot");
    const restored = workspace + "-restored";
    command(["-m", "entropytrade.api.recovery", "restore", "--workspace", restored, "--archive", archive], "restore");
    receipt.operations.push({ action: "offline-restore", archive, sha256: sha(fs.readFileSync(archive)), restored }); save();
    workspace = restored;
    await start(); await page.goto(origin);
    await expect(page.locator("#weather-schedules")).toContainText("Forward validation · paused");
    assert.deepEqual(await download("restored-state.json"), stateBytes);
    if (cancelledRequest) {
      const rows = await (await fetch(origin + "/api/weather/labels")).json();
      assert.deepEqual(rows.find(r => r.id === cancelledRequest.id), cancelledRequest);
      receipt.operations.push({ action: "restore-preserves-interrupted-request", id: cancelledRequest.id }); save();
    }
    await shot("offline-restored");
    assert.deepEqual(receipt.page_errors, []);
    receipt.status = "passed";
  } catch (error) { receipt.status = "failed"; receipt.failure = error.stack || String(error); throw error; }
  finally { await stop(); receipt.finished_at = new Date().toISOString(); save(); }
}

test("continuous forward validation: controlled twelve-date transitions and recovery", async ({ page, browser }) => procedure(page, browser, true));
test("continuous forward validation: authentic shadow receipts and new label acquisition", async ({ page, browser }) => procedure(page, browser, false));
