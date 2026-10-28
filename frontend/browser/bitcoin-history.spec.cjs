"use strict";
// Real local listener/worker/browser, with no response stubs or synthetic replacement data.
const { test, expect, chromium } = require("@playwright/test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { spawn } = require("node:child_process");
const { createHash } = require("node:crypto");

test("Bitcoin retained history: honest empty result, downloads and restart", async ({ page, browser }) => {
  const repo = path.resolve(__dirname, "../..");
  const evidence = process.env.ENTROPYTRADE_BROWSER_EVIDENCE;
  const workspace = process.env.ENTROPYTRADE_BROWSER_WORKSPACE;
  const origin = `http://127.0.0.1:${Number(process.env.ENTROPYTRADE_BROWSER_PORT || 43129)}`;
  assert(workspace && path.isAbsolute(workspace) && workspace.startsWith(path.join(repo, "data/cache/")));
  assert(!fs.existsSync(workspace), "Use a new workspace");
  assert(chromium.executablePath().startsWith(path.join(__dirname, ".browsers/")));
  fs.mkdirSync(evidence, { recursive: true });
  const receiptPath = path.join(evidence, "history-browser-receipt.json");
  assert(!fs.existsSync(receiptPath));
  const receipt = { started_at: new Date().toISOString(), browser: browser.version(), executable: chromium.executablePath(),
    origin, workspace, status: "running", page_errors: [], downloads: [], screenshots: [],
    limitations: ["Empty real workspace, no historical performance or successful network ingestion claimed.",
      "Controlled synthetic model checks are separate pytest evidence."] };
  const save = () => fs.writeFileSync(receiptPath, JSON.stringify(receipt, null, 2) + "\n");
  const hash = (bytes) => createHash("sha256").update(bytes).digest("hex");
  page.on("pageerror", error => { receipt.page_errors.push(error.message); save(); });
  let server;
  const pause = ms => new Promise(resolve => setTimeout(resolve, ms));
  async function start(epoch) {
    const occupied = await fetch(origin + "/api/catalog").catch(() => null);
    assert(!occupied, "Refusing to use an existing server");
    const log = fs.openSync(path.join(evidence, `history-server-${epoch}.log`), "a");
    server = spawn(path.join(repo, ".venv/bin/python"), ["-m", "entropytrade.api.server", "--port", new URL(origin).port, "--workspace", workspace],
      { cwd: repo, env: { PATH: "/usr/bin:/bin", PYTHONNOUSERSITE: "1", PYTHONDONTWRITEBYTECODE: "1", TZ: "UTC", TMPDIR: "/tmp", OMP_NUM_THREADS: "1", OPENBLAS_NUM_THREADS: "1" }, stdio: ["ignore", log, log] });
    fs.closeSync(log);
    for (let i = 0; i < 100; i++) {
      if (server.exitCode !== null) throw new Error(`Server exited ${server.exitCode}; inspect history-server-${epoch}.log`);
      const response = await fetch(origin + "/api/catalog").catch(() => null);
      if (response?.ok) {
        const catalog = await response.json();
        assert.equal(catalog.submission_enabled, false);
        assert.equal(catalog.provider_enabled, false);
        return;
      }
      await pause(100);
    }
    throw new Error("Local listener not ready in ten seconds");
  }
  async function stop() {
    if (!server || server.exitCode !== null || server.signalCode !== null) return;
    server.kill("SIGINT");
    for (let i = 0; i < 100 && server.exitCode === null && server.signalCode === null; i++) await pause(100);
    if (server.exitCode === null && server.signalCode === null) { server.kill("SIGKILL"); throw new Error("Server did not stop"); }
  }
  async function screenshot(name) {
    const file = path.join(evidence, name);
    await page.screenshot({ path: file, fullPage: true });
    receipt.screenshots.push({ file: name, sha256: hash(fs.readFileSync(file)) }); save();
  }
  async function download(label, suffix) {
    const pending = page.waitForEvent("download");
    await page.getByRole("link", { name: label, exact: true }).click();
    const item = await pending;
    const file = `${suffix}-${item.suggestedFilename()}`;
    await item.saveAs(path.join(evidence, file));
    const bytes = fs.readFileSync(path.join(evidence, file));
    receipt.downloads.push({ file, sha256: hash(bytes) }); save(); return bytes;
  }
  save();
  try {
    await start(1);
    await page.goto(origin);
    await page.getByLabel("Market family").selectOption("bitcoin");
    await page.getByLabel("Data source").selectOption("history");
    await page.getByLabel("Research idea", { exact: true }).fill("Research Bitcoin spot");
    await page.getByRole("button", { name: "Start research" }).click();
    await expect(page.locator("#run-header")).toContainText("completed", { timeout: 60_000 });
    for (const tab of ["Review", "Probabilities", "Evidence & lineage"]) {
      await page.getByRole("button", { name: tab, exact: true }).click();
      await expect(page.locator("#result-content")).toContainText("0 retained captures");
      await expect(page.locator("#result-content")).toContainText("Final holdout is excluded");
      await expect(page.locator("#result-content")).toContainText("trading backtests and returns remain blocked");
      await screenshot(`history-${tab.split(" ")[0].toLowerCase()}.png`);
    }
    const before = await download("Review JSON", "before");
    const review = JSON.parse(before);
    assert.equal(review.data_kind, "real");
    assert.equal(review.bitcoin_history.capture_count, 0);
    assert.equal(review.probability_count, 0);
    assert.equal(review.final_holdout_evaluated, false);
    assert(review.candidates.every(c => c.status === "UNSUPPORTED" && !c.scenarios.length));
    const report = await download("Text report", "before");
    assert(report.toString().includes("receipt-time official binary targets"));
    await stop(); await start(2); await page.reload();
    await page.locator(".history-item").first().click();
    await expect(page.locator("#run-header")).toContainText("completed");
    assert.deepEqual(await download("Review JSON", "after"), before);
    assert.deepEqual(await download("Text report", "after"), report);
    await screenshot("history-reopened.png");
    assert.deepEqual(receipt.page_errors, []);
    receipt.status = "passed";
  } catch (error) {
    receipt.status = "failed"; receipt.failure = String(error); throw error;
  } finally {
    await stop(); receipt.finished_at = new Date().toISOString(); save();
  }
});
