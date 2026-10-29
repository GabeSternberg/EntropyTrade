"use strict";
// Actual page/listener/workers. No interception, fixtures, fake clocks, or direct API writes.
const { test, expect, chromium } = require("@playwright/test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { spawn } = require("node:child_process");
const { createHash } = require("node:crypto");

test("continuous shadow: research, capture, pause, restart, resume and durable evidence", async ({ page, browser }) => {
  const repo = path.resolve(__dirname, "../..");
  const evidence = process.env.ENTROPYTRADE_BROWSER_EVIDENCE;
  const workspace = process.env.ENTROPYTRADE_BROWSER_WORKSPACE;
  const origin = `http://127.0.0.1:${Number(process.env.ENTROPYTRADE_BROWSER_PORT || 43130)}`;
  assert(workspace && path.isAbsolute(workspace) && workspace.startsWith(path.join(repo, "data/cache/")));
  assert(!fs.existsSync(workspace), "Use a new workspace");
  assert(chromium.executablePath().startsWith(path.join(__dirname, ".browsers/")));
  fs.mkdirSync(evidence, { recursive: true });
  const receiptPath = path.join(evidence, "shadow-browser-receipt.json");
  assert(!fs.existsSync(receiptPath));
  const receipt = { started_at: new Date().toISOString(), status: "running", browser: browser.version(),
    executable: chromium.executablePath(), origin, workspace, page_errors: [], screenshots: [], downloads: [],
    limitations: ["Real forward access may fail; completed capture and successful ingestion are asserted separately.",
      "No empirical model, fee/depth certification, profitability or release acceptance is implied."] };
  const save = () => fs.writeFileSync(receiptPath, JSON.stringify(receipt, null, 2) + "\n");
  const hash = bytes => createHash("sha256").update(bytes).digest("hex");
  const pause = ms => new Promise(resolve => setTimeout(resolve, ms));
  let server;
  page.on("pageerror", error => { receipt.page_errors.push(error.message); save(); });
  async function start(epoch) {
    assert(!await fetch(origin + "/api/catalog").catch(() => null), "Port already in use");
    const log = fs.openSync(path.join(evidence, `shadow-server-${epoch}.log`), "a");
    server = spawn(path.join(repo, ".venv/bin/python"), ["-m", "entropytrade.api.server", "--port", new URL(origin).port, "--workspace", workspace], {
      cwd: repo, env: { PATH: "/usr/bin:/bin", PYTHONNOUSERSITE: "1", PYTHONDONTWRITEBYTECODE: "1", TZ: "UTC", TMPDIR: "/tmp", OMP_NUM_THREADS: "1", OPENBLAS_NUM_THREADS: "1" },
      stdio: ["ignore", log, log],
    });
    fs.closeSync(log);
    for (let attempt = 0; attempt < 100; attempt++) {
      if (server.exitCode !== null) throw new Error(`Server exited ${server.exitCode}; inspect shadow-server-${epoch}.log`);
      if ((await fetch(origin + "/api/catalog").catch(() => null))?.ok) return;
      await pause(100);
    }
    throw new Error("Listener unavailable after ten seconds");
  }
  async function stop() {
    if (!server || server.exitCode !== null || server.signalCode !== null) return;
    server.kill("SIGINT");
    for (let i = 0; i < 100 && server.exitCode === null && server.signalCode === null; i++) await pause(100);
    if (server.exitCode === null && server.signalCode === null) { server.kill("SIGKILL"); throw new Error("Server did not stop"); }
  }
  async function screenshot(name) {
    await page.screenshot({ path: path.join(evidence, name), fullPage: true });
    receipt.screenshots.push({ file: name, sha256: hash(fs.readFileSync(path.join(evidence, name))) }); save();
  }
  async function download(name) {
    const pending = page.waitForEvent("download");
    await page.getByRole("link", { name: "Shadow evidence JSON", exact: true }).click();
    const file = await pending;
    await file.saveAs(path.join(evidence, name));
    const bytes = fs.readFileSync(path.join(evidence, name));
    receipt.downloads.push({ file: name, sha256: hash(bytes) }); save(); return bytes;
  }
  save();
  try {
    await start(1);
    await page.goto(origin);
    await expect(page.getByRole("button", { name: "Start shadow monitor", exact: true })).toBeDisabled();
    await page.getByLabel("Research idea", { exact: true }).fill("Test forecast_high_f > 70");
    await page.getByRole("button", { name: "Start research" }).click();
    await expect(page.locator("#run-header")).toContainText("completed", { timeout: 90_000 });
    await expect(page.getByLabel("Candidate to monitor")).toBeEnabled();
    await page.getByLabel("Poll interval").selectOption("60");
    await page.getByRole("button", { name: "Start shadow monitor", exact: true }).click();
    await expect(page.locator("#shadow-evidence")).toContainText(/Cycle 1 · (completed|failed)/, { timeout: 250_000 });
    await page.getByRole("button", { name: "Pause monitor", exact: true }).click();
    await expect(page.locator("#shadow-evidence")).toContainText("Shadow monitor · paused");
    const first = await download("shadow-paused.json");
    const parsed = JSON.parse(first);
    assert.equal(parsed.submission_enabled, false);
    assert.deepEqual(parsed.fills, []);
    assert.equal(parsed.performance, null);
    const originalCycle = parsed.cycles.find(c => c.sequence === 1);
    assert(originalCycle.result);
    assert.equal(originalCycle.result.submission_enabled, false);
    assert(originalCycle.result.capture, `Missing structured source evidence: ${originalCycle.result.failure || originalCycle.detail}`);
    assert(originalCycle.result.execution, "Missing structured book and fee evidence");
    {
      receipt.acquisition = originalCycle.result.capture;
      assert(originalCycle.result.artifacts.length);
      assert.equal(originalCycle.result.execution.submission_enabled, false);
      assert(Array.isArray(originalCycle.result.execution.receipts));
      assert(originalCycle.result.execution.fee_evidence.every(f => f.certified === false && f.version.startsWith("sha256:")));
      assert(Object.keys(originalCycle.result.model_refusals).length);
      assert(originalCycle.result.decisions.every(d => d.prediction === null && d.intent === null && d.status === "blocked"));
    }
    await screenshot("shadow-paused.png");
    await stop();
    await start(2);
    await page.reload();
    await page.locator("#shadow-history button").first().click();
    await expect(page.locator("#shadow-evidence")).toContainText("Shadow monitor · paused");
    assert.equal(hash(await download("shadow-restarted.json")), hash(first));
    await screenshot("shadow-restarted.png");
    await page.getByRole("button", { name: "Resume monitor", exact: true }).click();
    await expect(page.locator("#shadow-evidence")).toContainText(/Cycle 2 · (completed|failed)/, { timeout: 250_000 });
    await page.getByRole("button", { name: "Pause monitor", exact: true }).click();
    const second = JSON.parse(await download("shadow-second-cycle.json"));
    assert.equal(second.cycles.find(c => c.sequence === 1).digest, originalCycle.digest);
    assert.equal(second.cycle_count, 2);
    assert.equal(second.submission_enabled, false);
    assert(second.cycles.find(c => c.sequence === 2).result.capture);
    assert(second.cycles.find(c => c.sequence === 2).result.execution);
    await screenshot("shadow-second-cycle.png");
    assert.deepEqual(receipt.page_errors, []);
    receipt.status = "passed";
  } catch (error) { receipt.status = "failed"; receipt.failure = error.stack; throw error; }
  finally { await stop(); receipt.finished_at = new Date().toISOString(); save(); }
});
