"use strict";
// Real listener, installed workers, actual page interactions. No response/clock fixtures.
const { test, expect, chromium } = require("@playwright/test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { spawn, execFileSync } = require("node:child_process");
const { createHash } = require("node:crypto");

test("local operation and recovery: installed research, snapshot, restore and shadow lifecycle", async ({ page, browser }) => {
  const repo = path.resolve(__dirname, "../..");
  const evidence = process.env.ENTROPYTRADE_BROWSER_EVIDENCE;
  const original = process.env.ENTROPYTRADE_BROWSER_WORKSPACE;
  const python = process.env.ENTROPYTRADE_BROWSER_PYTHON || path.join(repo, ".venv/bin/python");
  const origin = `http://127.0.0.1:${Number(process.env.ENTROPYTRADE_BROWSER_PORT || 43134)}`;
  assert(original && path.isAbsolute(original) && original.startsWith(path.join(repo, "data/cache/")));
  const restored = original + "-restored";
  const archive = original + ".zip"; // unique per run, never a fixed shared path
  for (const p of [original, restored, archive]) assert(!fs.existsSync(p), "Acceptance paths must be new");
  assert(chromium.executablePath().startsWith(path.join(__dirname, ".browsers/")));
  fs.mkdirSync(evidence, { recursive: true });
  const receiptPath = path.join(evidence, "recovery-browser-receipt.json");
  assert(!fs.existsSync(receiptPath));
  const receipt = { status: "running", started_at: new Date().toISOString(), origin, repo, python,
    browser: browser.version(), executable: chromium.executablePath(), original, restored,
    page_errors: [], downloads: [], screenshots: [], operations: [],
    limitations: ["Synthetic models/backtests prove software behavior only.",
      "Authentic shadow sources may be insufficient; no fitted real model or certified fees are supplied.",
      "Frozen fitted-model/reservation recovery is covered by separate CONTROLLED Python checks.",
      "This does not pass empirical, provider, second-family or V1 release gates."] };
  const save = () => fs.writeFileSync(receiptPath, JSON.stringify(receipt, null, 2) + "\n");
  const hash = bytes => createHash("sha256").update(bytes).digest("hex");
  const pause = ms => new Promise(resolve => setTimeout(resolve, ms));
  const env = { PATH: "/usr/bin:/bin", PYTHONNOUSERSITE: "1", PYTHONDONTWRITEBYTECODE: "1",
    TZ: "UTC", TMPDIR: path.join(repo, "data/cache"), OMP_NUM_THREADS: "1", OPENBLAS_NUM_THREADS: "1", LOKY_MAX_CPU_COUNT: "1" };
  let server, epoch = 0, workspace = original;
  page.on("pageerror", error => { receipt.page_errors.push(error.message); save(); });
  async function start() {
    assert(!await fetch(origin + "/api/catalog").catch(() => null), "Port is occupied");
    const log = fs.openSync(path.join(evidence, `recovery-server-${++epoch}.log`), "a");
    server = spawn(python, ["-m", "entropytrade.api.server", "--port", new URL(origin).port, "--workspace", workspace],
      { cwd: repo, env, stdio: ["ignore", log, log] });
    fs.closeSync(log);
    for (let i = 0; i < 100; i++) {
      if (server.exitCode !== null) throw new Error(`Server exited ${server.exitCode}; see recovery-server-${epoch}.log`);
      const response = await fetch(origin + "/api/catalog").catch(() => null);
      if (response?.ok) {
        const catalog = await response.json();
        assert.equal(catalog.submission_enabled, false); assert.equal(catalog.provider_enabled, false);
        receipt.operations.push({ action: "start", epoch, workspace, at: new Date().toISOString() }); save(); return;
      }
      await pause(100);
    }
    throw new Error("Listener did not become ready");
  }
  async function stop() {
    if (!server || server.exitCode !== null || server.signalCode !== null) return;
    server.kill("SIGINT");
    for (let i = 0; i < 100 && server.exitCode === null && server.signalCode === null; i++) await pause(100);
    if (server.exitCode === null && server.signalCode === null) { server.kill("SIGKILL"); throw new Error("Server did not stop"); }
    receipt.operations.push({ action: "stop", epoch, at: new Date().toISOString() }); save();
  }
  async function screenshot(name) {
    await page.screenshot({ path: path.join(evidence, name), fullPage: true });
    receipt.screenshots.push({ file: name, sha256: hash(fs.readFileSync(path.join(evidence, name))) }); save();
  }
  async function download(link, name) {
    const pending = page.waitForEvent("download");
    await page.getByRole("link", { name: link, exact: true }).click();
    await (await pending).saveAs(path.join(evidence, name));
    const bytes = fs.readFileSync(path.join(evidence, name));
    receipt.downloads.push({ file: name, sha256: hash(bytes) }); save(); return bytes;
  }
  function recover(action, target) {
    const result = JSON.parse(execFileSync(python, ["-m", "entropytrade.api.recovery", action,
      "--workspace", target, "--archive", archive], { cwd: repo, env, encoding: "utf8" }));
    receipt.operations.push({ action, result, at: new Date().toISOString() }); save(); return result;
  }
  async function selectMonitor(id) {
    await page.locator("#shadow-history button").filter({ hasText: id.slice(0, 8) }).click();
    await expect(page.locator("#shadow-evidence")).toContainText(id);
  }
  save();
  try {
    await start();
    await page.goto(origin);
    await page.getByLabel("Data source", { exact: true }).selectOption("synthetic");
    await page.getByLabel("Research idea", { exact: true }).fill("CONTROLLED synthetic software demonstration");
    await page.getByRole("button", { name: "Start research" }).click();
    await expect(page.locator("#run-header")).toContainText("completed", { timeout: 180_000 });
    const synthetic = await download("Review JSON", "synthetic-review.json");
    const syntheticReport = await download("Text report", "synthetic-report.txt");
    const result = JSON.parse(synthetic);
    assert.equal(result.data_kind, "synthetic"); assert.equal(result.final_holdout_evaluated, false);
    assert(result.candidates.length > 0 && result.probability_count > 0);
    for (const tab of ["Review", "Probabilities", "Evidence & lineage"]) {
      await page.getByRole("button", { name: tab, exact: true }).click();
      await expect(page.locator("#result-content")).not.toBeEmpty();
    }
    await screenshot("synthetic-lineage.png");
    await expect(page.getByRole("button", { name: "Start shadow monitor", exact: true })).toBeDisabled();

    await page.getByLabel("Data source", { exact: true }).selectOption("recorded");
    await page.getByLabel("Research idea", { exact: true }).fill("Test forecast_high_f > 70");
    await page.getByRole("button", { name: "Start research" }).click();
    await expect(page.locator("#run-header h2")).toHaveText("Test forecast_high_f > 70");
    await expect(page.locator("#run-header")).toContainText("completed", { timeout: 90_000 });
    const real = await download("Review JSON", "recorded-review.json");
    assert.equal(JSON.parse(real).data_kind, "real");
    assert.equal(JSON.parse(real).probability_count, 0);
    await screenshot("recorded-insufficient.png");
    await page.getByLabel("Poll interval").selectOption("60");
    await page.getByRole("button", { name: "Start shadow monitor", exact: true }).click();
    await expect(page.locator("#shadow-evidence")).toContainText(/Cycle 1 · (completed|failed)/, { timeout: 250_000 });
    await page.getByRole("button", { name: "Pause monitor", exact: true }).click();
    await expect(page.locator("#shadow-evidence")).toContainText("Shadow monitor · paused");
    const pausedBytes = await download("Shadow evidence JSON", "paused-original.json");
    const paused = JSON.parse(pausedBytes);
    const cycle = paused.cycles.find(c => c.sequence === 1);
    assert(cycle.result?.capture && cycle.result?.execution, "Expected structured source/execution evidence");
    assert(cycle.result.artifacts.length > 0);
    assert.equal(paused.submission_enabled, false); assert.deepEqual(paused.fills, []); assert.equal(paused.performance, null);
    assert(cycle.result.decisions.every(d => d.prediction === null && d.intent === null && d.status === "blocked"));
    receipt.authentic_acquisition = cycle.result.capture;
    await screenshot("paused-original.png");

    // Create an independent active monitor, then stop during its fresh first cycle.
    await page.getByRole("button", { name: "Start shadow monitor", exact: true }).click();
    await expect(page.locator("#shadow-evidence")).toContainText("Cycle 1 · running", { timeout: 10_000 });
    const active = JSON.parse(await download("Shadow evidence JSON", "active-before-stop.json"));
    assert.notEqual(active.id, paused.id);
    await stop();
    const stoppedCycles = JSON.parse(execFileSync(python, ["-c",
      "import json,sqlite3,sys; db=sqlite3.connect(sys.argv[1]+'?mode=ro',uri=True); db.row_factory=sqlite3.Row; print(json.dumps([dict(r) for r in db.execute('SELECT * FROM shadow_cycles WHERE monitor_id=? ORDER BY sequence',(sys.argv[2],))])); db.close()",
      "file:" + path.join(original, "jobs.sqlite"), active.id], { env, encoding: "utf8" }));
    assert.equal(stoppedCycles.length, 1);
    assert.notEqual(stoppedCycles[0].status, "running");
    // A very fast authentic request may finish while SIGINT is delivered. Both a
    // committed result and an interrupted partial cycle must keep their exact bytes.
    receipt.active_cycle_at_stop = stoppedCycles[0].status; save();
    recover("snapshot", original);
    fs.copyFileSync(archive, path.join(evidence, "workspace.zip"));
    const manifest = JSON.parse(execFileSync(python, ["-c", "import json,sys,zipfile; print(zipfile.ZipFile(sys.argv[1]).read('manifest.json').decode())", archive], { env, encoding: "utf8" }));
    fs.writeFileSync(path.join(evidence, "snapshot-manifest.json"), JSON.stringify(manifest, null, 2));
    recover("restore", restored);
    // Compare authoritative bytes before server recovery writes any new lifecycle event.
    for (const item of manifest.files) {
      const target = path.join(restored, item.path);
      assert.equal(fs.statSync(target).size, item.bytes);
      assert.equal("sha256:" + hash(fs.readFileSync(target)), item.sha256);
    }
    workspace = restored;
    await start(); await page.reload();
    await selectMonitor(paused.id);
    await expect(page.locator("#shadow-evidence")).toContainText("Shadow monitor · paused");
    assert.deepEqual(await download("Shadow evidence JSON", "paused-restored.json"), pausedBytes);
    await screenshot("paused-restored.png");
    await selectMonitor(active.id);
    await expect(page.locator("#shadow-evidence")).toContainText(/Cycle 2 · (completed|failed)/, { timeout: 250_000 });
    await page.getByRole("button", { name: "Pause monitor", exact: true }).click();
    await expect(page.locator("#shadow-evidence")).toContainText("Shadow monitor · paused");
    const recovered = JSON.parse(await download("Shadow evidence JSON", "active-recovered.json"));
    const prior = recovered.cycles.find(c => c.sequence === 1);
    for (const key of ["id", "status", "started_at", "finished_at", "digest"]) assert.equal(prior[key], stoppedCycles[0][key]);
    assert.deepEqual(recovered.model_binding, active.model_binding);
    const fresh = recovered.cycles.find(c => c.sequence === 2);
    assert.notEqual(fresh.id, active.cycles[0].id);
    assert(fresh.result.capture && fresh.result.execution);
    assert(new Date(fresh.result.capture.started_at) >= new Date(receipt.operations.find(o => o.action === "restore").at));
    await screenshot("active-recovered.png");

    // Reopen both research results through saved history and compare browser downloads.
    await page.locator("#history button").filter({ hasText: "CONTROLLED synthetic software demonstration" }).click();
    await expect(page.locator("#run-header")).toContainText("completed");
    assert.deepEqual(await download("Review JSON", "synthetic-restored.json"), synthetic);
    assert.deepEqual(await download("Text report", "synthetic-restored.txt"), syntheticReport);
    await page.locator("#history button").filter({ hasText: "Test forecast_high_f > 70" }).click();
    assert.deepEqual(await download("Review JSON", "recorded-restored.json"), real);
    // Cancellation still uses the actual queue/worker through the form.
    await page.getByLabel("Data source", { exact: true }).selectOption("synthetic");
    await page.getByLabel("Research idea", { exact: true }).fill("Cancel this software demonstration");
    await page.getByRole("button", { name: "Start research" }).click();
    await page.getByRole("button", { name: "Cancel run", exact: true }).click();
    await expect(page.locator("#run-header")).toContainText("cancelled");
    await stop(); await start(); await page.reload();
    await page.locator("#history button").filter({ hasText: "Cancel this software demonstration" }).click();
    await expect(page.locator("#run-header")).toContainText("cancelled");
    await selectMonitor(paused.id);
    assert.deepEqual(await download("Shadow evidence JSON", "paused-second-restart.json"), pausedBytes);
    assert.deepEqual(receipt.page_errors, []);
    receipt.status = "passed";
  } catch (error) { receipt.status = "failed"; receipt.failure = error.stack; throw error; }
  finally { await stop(); receipt.finished_at = new Date().toISOString(); save(); }
});
