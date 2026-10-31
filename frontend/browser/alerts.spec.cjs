"use strict";
// Actual managed Chromium and real listeners. Controlled failures remain software evidence.
const { test, expect, chromium } = require("@playwright/test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { spawn, spawnSync } = require("node:child_process");
const { createHash } = require("node:crypto");

test("operator alerts: acknowledgement, listener restart, recovery, recurrence and offline restore", async ({ page, browser }) => {
  const repo = path.resolve(__dirname, "../..");
  const evidence = path.join(process.env.ENTROPYTRADE_BROWSER_EVIDENCE, "alerts");
  const workspace = process.env.ENTROPYTRADE_BROWSER_WORKSPACE + "-alerts";
  const python = process.env.ENTROPYTRADE_BROWSER_PYTHON || path.join(repo, ".venv/bin/python");
  const origin = `http://127.0.0.1:${Number(process.env.ENTROPYTRADE_BROWSER_PORT || 43148)}`;
  assert(path.isAbsolute(workspace) && workspace.startsWith(path.join(repo, "data/cache/")));
  assert(!fs.existsSync(workspace));
  assert(chromium.executablePath().startsWith(path.join(__dirname, ".browsers/")));
  fs.mkdirSync(evidence, { recursive: true });
  const env = { PATH: "/usr/bin:/bin", TZ: "UTC", PYTHONNOUSERSITE: "1", PYTHONDONTWRITEBYTECODE: "1", OMP_NUM_THREADS: "1", OPENBLAS_NUM_THREADS: "1", PYTHONPATH: `${repo}/backend:${repo}/backend/src` };
  const receipt = { status: "running", browser: browser.version(), executable: chromium.executablePath(), operations: [], downloads: [], screenshots: [], page_errors: [], submission_enabled: false, limitation: "CONTROLLED health/failure/outcome signals; no authentic acquisition or empirical returns" };
  const save = () => fs.writeFileSync(path.join(evidence, "receipt.json"), JSON.stringify(receipt, null, 2));
  const pause = ms => new Promise(resolve => setTimeout(resolve, ms));
  let server, epoch = 0, mid;
  page.on("pageerror", error => { receipt.page_errors.push(error.message); save(); });
  function run(module, args) {
    const result = spawnSync(python, ["-m", module, ...args], { cwd: repo, env, encoding: "utf8", timeout: 120_000 });
    assert.equal(result.status, 0, result.stdout + result.stderr);
    return result.stdout;
  }
  function fixture(action) {
    const file = path.join(evidence, `${action}.json`);
    run("tests.integration.alerts_fixture", [action, workspace, file]);
    return JSON.parse(fs.readFileSync(file));
  }
  async function start(root = workspace) {
    assert(!await fetch(origin + "/api/catalog").catch(() => null), "Port occupied");
    const log = fs.openSync(path.join(evidence, `server-${++epoch}.log`), "a");
    server = spawn(python, ["-m", "entropytrade.api.server", "--workspace", root, "--port", origin.split(":").at(-1)], { cwd: repo, env, stdio: ["ignore", log, log] });
    fs.closeSync(log);
    for (let n = 0; n < 100; n++) {
      if (server.exitCode !== null) throw new Error(`Listener exited ${server.exitCode}`);
      const response = await fetch(origin + "/api/catalog").catch(() => null);
      if (response?.ok) { assert.equal((await response.json()).submission_enabled, false); receipt.operations.push({ start: epoch, root }); save(); return; }
      await pause(100);
    }
    throw new Error("Listener startup timeout");
  }
  async function stop() {
    if (!server || server.exitCode !== null || server.signalCode !== null) return;
    server.kill("SIGINT");
    for (let n = 0; n < 100 && server.exitCode === null && server.signalCode === null; n++) await pause(100);
    if (server.exitCode === null && server.signalCode === null) { server.kill("SIGKILL"); throw new Error("Listener shutdown timeout"); }
  }
  async function open() {
    await page.goto(origin); await expect(page.locator("#submit")).toBeEnabled();
    await page.locator("#shadow-history button").filter({ hasText: mid.slice(0, 8) }).click();
  }
  async function download(file) {
    const pending = page.waitForEvent("download");
    await page.getByRole("link", { name: "Shadow evidence JSON", exact: true }).click();
    await (await pending).saveAs(path.join(evidence, file));
    const bytes = fs.readFileSync(path.join(evidence, file));
    receipt.downloads.push({ file, sha256: createHash("sha256").update(bytes).digest("hex") }); save();
    return bytes;
  }
  async function shot(file) { await page.screenshot({ path: path.join(evidence, file), fullPage: true }); receipt.screenshots.push({ file }); save(); }
  save();
  try {
    const seeded = fixture("seed"); mid = seeded.monitor_id;
    assert.equal(seeded.alerts.filter(a => !a.resolved_at).length, 3);
    await start(); await open();
    await expect(page.locator("#shadow-alerts")).toContainText("3 open · 3 need acknowledgement");
    for (const name of ["Stale collection", "Repeated failures", "Unresolved reconciliation"]) await expect(page.locator("#shadow-alerts")).toContainText(name);
    await shot("needs-review.png");
    for (const alert of seeded.alerts) {
      const panel = page.locator(`[data-alert-id="${alert.id}"]`);
      await panel.getByRole("button", { name: "Acknowledge alert", exact: true }).click();
      await expect(panel).toContainText("Acknowledged / still open");
    }
    await expect(page.locator("#shadow-alerts")).toContainText("3 open · 0 need acknowledgement");
    const acknowledged = await download("acknowledged.json");
    const value = JSON.parse(acknowledged);
    assert(value.alerts.every(a => a.acknowledged_at && !a.resolved_at));
    assert.equal(value.submission_enabled, false); assert.equal(value.paper_account, null);
    await shot("acknowledged.png"); await stop();
    await start(); await open();
    assert.deepEqual(await download("restarted.json"), acknowledged);
    await expect(page.locator("#shadow-alerts")).toContainText("3 open · 0 need acknowledgement");
    await stop();
    fixture("recover"); await start(); await open();
    await expect(page.locator("#shadow-alerts")).toContainText("0 open · 0 need acknowledgement");
    const recovered = await download("recovered.json");
    assert(JSON.parse(recovered).alerts.every(a => a.resolved_at && a.acknowledged_at));
    await shot("recovered.png"); await stop();
    fixture("recur"); await start(); await open();
    const recurring = JSON.parse(await download("recurring.json"));
    const incident = recurring.alerts.find(a => a.kind === "repeated_failures" && !a.resolved_at);
    assert(incident && !incident.acknowledged_at);
    assert(!seeded.alerts.some(a => a.id === incident.id));
    await expect(page.locator(`[data-alert-id="${incident.id}"]`)).toContainText("Needs acknowledgement");
    await shot("recurring.png");
    const final = await download("final.json"); await stop();
    const archive = path.join(repo, "data/cache", `operator-${path.basename(workspace)}.zip`);
    run("entropytrade.api.recovery", ["snapshot", "--workspace", workspace, "--archive", archive]);
    const restored = workspace + "-restored";
    run("entropytrade.api.recovery", ["restore", "--workspace", restored, "--archive", archive]);
    await start(restored); await open();
    assert.deepEqual(await download("restored.json"), final);
    assert.deepEqual(receipt.page_errors, []); receipt.status = "passed";
  } catch (error) { receipt.status = "failed"; receipt.failure = error.stack; throw error; }
  finally { await stop(); save(); }
});
