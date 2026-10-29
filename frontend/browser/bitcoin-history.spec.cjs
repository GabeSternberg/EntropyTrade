"use strict";
// Real local listener/worker/browser. Populated setup is explicitly CONTROLLED software evidence.
const { test, expect, chromium } = require("@playwright/test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { spawn, spawnSync } = require("node:child_process");
const { createHash } = require("node:crypto");

for (const kind of ["empty", "controlled", ...(process.env.ENTROPYTRADE_BROWSER_RETAINED ? ["retained"] : [])]) {
const populated = kind !== "empty", retained = kind === "retained";
test(`Bitcoin retained history: ${retained ? "REAL retained receipts" : populated ? "CONTROLLED populated" : "honest empty"} result, downloads and restart`, async ({ page, browser }) => {
  const repo = path.resolve(__dirname, "../..");
  const evidence = process.env.ENTROPYTRADE_BROWSER_EVIDENCE;
  const workspace = process.env.ENTROPYTRADE_BROWSER_WORKSPACE + (populated ? `-${kind}` : "");
  const origin = `http://127.0.0.1:${Number(process.env.ENTROPYTRADE_BROWSER_PORT || 43129)}`;
  assert(workspace && path.isAbsolute(workspace) && workspace.startsWith(path.join(repo, "data/cache/")));
  assert(!fs.existsSync(workspace), "Use a new workspace");
  assert(chromium.executablePath().startsWith(path.join(__dirname, ".browsers/")));
  fs.mkdirSync(evidence, { recursive: true });
  const prefix = kind;
  const receiptPath = path.join(evidence, `${prefix}-history-browser-receipt.json`);
  assert(!fs.existsSync(receiptPath));
  const receipt = { started_at: new Date().toISOString(), browser: browser.version(), executable: chromium.executablePath(),
    origin, workspace, status: "running", page_errors: [], downloads: [], screenshots: [],
    evidence_kind: retained ? "REAL RETAINED RECEIPT REPLAY" : populated ? "CONTROLLED SOFTWARE EVIDENCE" : "empty workspace insufficiency",
    limitations: [retained ? "Verified real receipts imported before page interaction. Replay is not browser acquisition; insufficient history establishes no empirical model performance." : populated ? "CONTROLLED market/source/outcome setup; actual listener and unmodified subprocess worker. No empirical evidence. Adapter data_kind=real denotes the receipt-processing path only." : "Empty real workspace, no historical performance or successful network ingestion claimed.",
      "Controlled synthetic model checks are separate pytest evidence."] };
  const save = () => fs.writeFileSync(receiptPath, JSON.stringify(receipt, null, 2) + "\n");
  const hash = (bytes) => createHash("sha256").update(bytes).digest("hex");
  page.on("pageerror", error => { receipt.page_errors.push(error.message); save(); });
  let server;
  const pause = ms => new Promise(resolve => setTimeout(resolve, ms));
  async function start(epoch) {
    const occupied = await fetch(origin + "/api/catalog").catch(() => null);
    assert(!occupied, "Refusing to use an existing server");
    const log = fs.openSync(path.join(evidence, `${prefix}-history-server-${epoch}.log`), "a");
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
    name = `${prefix}-${name}`;
    const file = path.join(evidence, name);
    await page.screenshot({ path: file, fullPage: true });
    receipt.screenshots.push({ file: name, sha256: hash(fs.readFileSync(file)) }); save();
  }
  async function download(label, suffix) {
    const pending = page.waitForEvent("download");
    await page.getByRole("link", { name: label, exact: true }).click();
    const item = await pending;
    const file = `${prefix}-${suffix}-${item.suggestedFilename()}`;
    await item.saveAs(path.join(evidence, file));
    const bytes = fs.readFileSync(path.join(evidence, file));
    receipt.downloads.push({ file, sha256: hash(bytes) }); save(); return bytes;
  }
  save();
  try {
    if (populated) {
      const setup = spawnSync(path.join(repo, ".venv/bin/python"), ["-m", retained ? "tests.integration.bitcoin_history_retained" : "tests.integration.bitcoin_history_fixture", workspace,
        ...(retained ? [process.env.ENTROPYTRADE_BROWSER_RETAINED] : [])],
        { cwd: repo, encoding: "utf8", timeout: 30_000,
          env: { PATH: "/usr/bin:/bin", PYTHONPATH: [path.join(repo, "backend/src"), path.join(repo, "backend")].join(path.delimiter),
            PYTHONNOUSERSITE: "1", PYTHONDONTWRITEBYTECODE: "1", TZ: "UTC", TMPDIR: "/tmp", OMP_NUM_THREADS: "1", OPENBLAS_NUM_THREADS: "1" } });
      fs.writeFileSync(path.join(evidence, `${prefix}-setup.log`), `${setup.stdout || ""}${setup.stderr || ""}`);
      assert.equal(setup.status, 0, String(setup.error || setup.stderr));
      receipt.fixture = JSON.parse(fs.readFileSync(path.join(workspace, retained ? "retained-inputs.json" : "controlled-fixture.json")));
      save();
    }
    await start(1);
    await page.goto(origin);
    await page.getByLabel("Market family").selectOption("bitcoin");
    await page.getByLabel("Data source").selectOption("history");
    await page.getByLabel("Research idea", { exact: true }).fill("Test scaled_moneyness > 0");
    await page.getByRole("button", { name: "Start research" }).click();
    await expect(page.locator("#run-header")).toContainText("completed", { timeout: 60_000 });
    for (const tab of ["Review", "Probabilities", "Evidence & lineage"]) {
      await page.getByRole("button", { name: tab, exact: true }).click();
      await expect(page.locator("#result-content")).toContainText(`${retained ? receipt.fixture.capture_count : populated ? 3 : 0} retained captures`);
      if (retained) {
        await expect(page.locator("#result-content")).toContainText(`${receipt.fixture.retained_events} events on ${receipt.fixture.retained_dates} dates · ${receipt.fixture.protected_events} protected events`);
        for (const summary of receipt.fixture.readiness.summaries) await expect(page.locator("#result-content")).toContainText(summary);
      } else if (populated) await expect(page.locator("#result-content")).toContainText("3 events on 3 dates · 1 protected events");
      await expect(page.locator("#result-content")).toContainText("Final holdout is excluded");
      await expect(page.locator("#result-content")).toContainText("trading backtests and returns remain blocked");
      await screenshot(`history-${tab.split(" ")[0].toLowerCase()}.png`);
    }
    const before = await download("Review JSON", "before");
    const review = JSON.parse(before);
    assert.equal(review.data_kind, "real");
    assert.equal(review.bitcoin_history.capture_count, retained ? receipt.fixture.capture_count : populated ? 3 : 0);
    assert.equal(review.probability_count, 0);
    assert.equal(review.final_holdout_evaluated, false);
    assert(review.candidates.every(c => c.status === (populated ? "INSUFFICIENT_DATA" : "UNSUPPORTED") && !c.scenarios.length && c.forecast_metrics === null));
    if (populated) {
      assert.deepEqual(review.bitcoin_history.partition, receipt.fixture.partition);
      assert.equal(review.bitcoin_history.reconciliation.requested, 0);
      assert.equal(review.bitcoin_history.reconciliation.retained_receipts, retained ? receipt.fixture.receipts.length : 3);
      if (retained) {
        assert.deepEqual(review.bitcoin_history.readiness, receipt.fixture.readiness);
        const identity = r => `${r.hash}|${r.received_at}|${r.path}|${r.status}`;
        assert.deepEqual(review.bitcoin_history.reconciliation.receipts.map(identity).sort(), receipt.fixture.receipts.map(identity).sort());
        assert.equal(review.bitcoin_history.readiness.minimum_evidence_met, false);
      } else assert(review.bitcoin_history.reconciliation.receipts.every(r => r.received_at === receipt.fixture.received_at));
      assert(JSON.stringify(review.candidates).includes("received before fit cutoff"));
    }
    const report = await download("Text report", "before");
    assert(report.toString().includes("receipt-time official binary targets"));
    if (retained) for (const summary of receipt.fixture.readiness.summaries) assert(report.toString().includes(summary));
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
    await stop();
    if (fs.existsSync(workspace)) fs.cpSync(workspace, path.join(evidence, `${prefix}-workspace`), { recursive: true,
      filter: source => !/(?:-wal|-shm|\.lock)$/.test(source) });
    receipt.finished_at = new Date().toISOString(); save();
  }
});
}
