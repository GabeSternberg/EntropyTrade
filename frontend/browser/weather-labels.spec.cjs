"use strict";
// Authentic retained receipts, real localhost, ordinary workers, managed Chromium.
const { test, expect, chromium } = require("@playwright/test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { spawn, spawnSync } = require("node:child_process");
const { createHash } = require("node:crypto");

test("authentic weather labels: acquire, inspect provenance, freeze and restart", async ({ page, browser }) => {
  const repo = path.resolve(__dirname, "../..");
  const evidence = process.env.ENTROPYTRADE_BROWSER_EVIDENCE;
  const workspace = process.env.ENTROPYTRADE_BROWSER_WORKSPACE + "-weather-labels";
  const python = process.env.ENTROPYTRADE_BROWSER_PYTHON || path.join(repo, ".venv/bin/python");
  const port = Number(process.env.ENTROPYTRADE_BROWSER_PORT || 43149);
  const origin = `http://127.0.0.1:${port}`;
  assert(path.isAbsolute(workspace) && workspace.startsWith(path.join(repo, "data/cache/")));
  assert(!fs.existsSync(workspace), "Use a fresh workspace");
  assert(chromium.executablePath().startsWith(path.join(__dirname, ".browsers/")));
  fs.mkdirSync(evidence, { recursive: true });
  const receiptFile = path.join(evidence, "weather-label-browser-receipt.json");
  assert(!fs.existsSync(receiptFile));
  const receipt = { status: "running", started_at: new Date().toISOString(), origin, workspace,
    browser: browser.version(), executable: chromium.executablePath(), operations: [],
    screenshots: [], downloads: [], page_errors: [],
    limitations: ["Original forward forecast receipt replay plus NEW authentic settlement-source acquisition.",
      "Official source availability starts at NEW receipt time; preliminary or inaccessible reports remain refused. Sparse history yields no empirical model or returns.",
      "External provider verification deferred; no credentials accessed. V1 remains incomplete."] };
  const save = () => fs.writeFileSync(receiptFile, JSON.stringify(receipt, null, 2) + "\n");
  const sha = bytes => createHash("sha256").update(bytes).digest("hex");
  const pause = ms => new Promise(resolve => setTimeout(resolve, ms));
  const env = { PATH: "/usr/bin:/bin", PYTHONNOUSERSITE: "1", PYTHONDONTWRITEBYTECODE: "1",
    OMP_NUM_THREADS: "1", OPENBLAS_NUM_THREADS: "1", TZ: "UTC",
    PYTHONPATH: path.join(repo, "backend") + ":" + path.join(repo, "backend/src") };
  page.on("pageerror", error => { receipt.page_errors.push(error.message); save(); });
  let server, epoch = 0;
  async function start() {
    assert(!await fetch(origin + "/api/catalog").catch(() => null), "Port is occupied");
    const log = fs.openSync(path.join(evidence, `weather-server-${++epoch}.log`), "a");
    server = spawn(python, ["-m", "entropytrade.api.server", "--workspace", workspace, "--port", String(port)], { cwd: repo, env, stdio: ["ignore", log, log] });
    fs.closeSync(log);
    for (let i = 0; i < 100; i++) {
      if (server.exitCode !== null) throw new Error(`Server exited ${server.exitCode}`);
      const response = await fetch(origin + "/api/catalog").catch(() => null);
      if (response?.ok) {
        const catalog = await response.json();
        assert.equal(catalog.submission_enabled, false); assert.equal(catalog.provider_enabled, false);
        receipt.operations.push({ action: "start", epoch }); save(); return;
      }
      await pause(100);
    }
    throw new Error("Listener startup timed out");
  }
  async function stop() {
    if (!server || server.exitCode !== null || server.signalCode !== null) return;
    server.kill("SIGINT");
    for (let i = 0; i < 100 && server.exitCode === null && server.signalCode === null; i++) await pause(100);
    if (server.exitCode === null && server.signalCode === null) { server.kill("SIGKILL"); throw new Error("Server shutdown timed out"); }
    receipt.operations.push({ action: "stop", epoch }); save();
  }
  async function screenshot(name) {
    const file = `weather-${name}.png`;
    await page.screenshot({ path: path.join(evidence, file), fullPage: true });
    receipt.screenshots.push({ file, sha256: sha(fs.readFileSync(path.join(evidence, file))) }); save();
  }
  async function download(link, name) {
    const pending = page.waitForEvent("download");
    await page.getByRole("link", { name: link, exact: true }).click();
    const file = `weather-${name}`;
    await (await pending).saveAs(path.join(evidence, file));
    const bytes = fs.readFileSync(path.join(evidence, file));
    receipt.downloads.push({ file, sha256: sha(bytes) }); save(); return bytes;
  }
  save();
  try {
    // The importer confines metadata to the installed repository. Locked runs keep
    // browser evidence beside that repository, so retain a copy after import succeeds.
    const imported = workspace + "-authentic-inputs.json";
    const seeded = spawnSync(python, ["-m", "tests.integration.weather_history_retained", workspace, imported], { cwd: repo, env, encoding: "utf8", timeout: 30_000 });
    assert.equal(seeded.status, 0, seeded.stdout + seeded.stderr);
    fs.copyFileSync(imported, path.join(evidence, "authentic-inputs.json"), fs.constants.COPYFILE_EXCL);
    receipt.operations.push({ action: "import", evidence: JSON.parse(fs.readFileSync(path.join(evidence, "authentic-inputs.json"))) }); save();
    await start(); await page.goto(origin + "/#/workbench");
    await expect(page.locator("#submit")).toBeEnabled();
    await page.getByRole("button", { name: "Freeze retained weather dataset", exact: true }).click();
    await expect(page.locator("#weather-message")).toContainText("Immutable dataset selected");
    await expect(page.locator("#weather-readiness")).toContainText("4 events on 2 dates");
    await expect(page.locator("#weather-readiness")).toContainText("0 source-matched scalar labels");
    await expect(page.locator("#weather-readiness")).toContainText("fit: 0/60");
    let selected = await page.locator("#weather-dataset").inputValue();
    assert.match(selected, /^[0-9a-f]{64}$/);
    await expect(page.locator("#mode")).toHaveValue("weather_history");
    await screenshot("dataset");
    // A repeated freeze must reuse the same immutable identity and counts.
    await page.getByRole("button", { name: "Freeze retained weather dataset", exact: true }).click();
    await expect(page.locator("#weather-freeze")).toBeEnabled();
    await expect(page.locator("#weather-dataset option")).toHaveCount(1);
    await expect(page.locator("#weather-dataset")).toHaveValue(selected);
    const acquisition = page.waitForResponse(r => r.url() === origin + "/api/weather/labels" && r.request().method() === "POST");
    await page.getByRole("button", { name: "Acquire settlement labels", exact: true }).click();
    const createdLabels = await acquisition; assert.equal(createdLabels.status(), 202);
    const acquisitionId = (await createdLabels.json()).id;
    let labels;
    for (let i = 0; i < 150; i++) {
      await page.getByRole("button", { name: "Refresh label acquisition", exact: true }).click();
      const rows = await (await fetch(origin + "/api/weather/labels")).json();
      labels = rows.find(r => r.id === acquisitionId);
      if (["completed", "failed", "interrupted"].includes(labels?.status)) break;
      await pause(1000);
    }
    assert.equal(labels.status, "completed", JSON.stringify(labels));
    assert(labels.result.verified_events + labels.result.refused_events === 4);
    assert(labels.result.records.every(r => r.observation || r.refusal));
    assert(labels.result.receipts.length === 2);
    receipt.operations.push({ action: "authentic-label-acquisition", id: acquisitionId, result: labels.result }); save();
    await page.getByRole("button", { name: "Refresh label acquisition", exact: true }).click();
    await expect(page.locator("#weather-labels")).toContainText(`${labels.result.verified_events} verified scalar labels`);
    await page.locator("#weather-labels summary").click();
    await expect(page.locator("#weather-labels")).toContainText("https://weather.com/kalshi/api/climate/primary");
    await screenshot("acquisition");
    const labelBytes = await download("Download label evidence", "labels.json");
    const labelBatch = JSON.parse(labelBytes);
    assert.equal(labelBatch.source_dataset, "sha256:" + selected);
    assert(labelBatch.receipts.every(r => r.received_at && r.url.startsWith("https://weather.com/kalshi/api/climate/primary?date=")));
    await page.getByRole("button", { name: "Freeze retained weather dataset", exact: true }).click();
    await expect(page.locator("#weather-message")).toContainText("Immutable dataset selected");
    await expect(page.locator("#weather-readiness")).toContainText(`${labels.result.verified_events} source-matched scalar labels`);
    await page.locator("#weather-readiness summary").filter({ hasText: "Settlement label provenance and refusals" }).click();
    await expect(page.locator("#weather-readiness")).toContainText("weather-company");
    selected = await page.locator("#weather-dataset").inputValue();
    await screenshot("labelled-dataset");
    // Explicit selection, then natural-language/local-template research through the normal worker.
    await page.getByLabel("Weather dataset", { exact: true }).selectOption(selected);
    const idea = "Test forecast_high_f > 60";
    await page.getByLabel("Research idea", { exact: true }).fill(idea);
    const created = page.waitForResponse(r => r.url() === origin + "/api/jobs" && r.request().method() === "POST");
    await page.getByRole("button", { name: "Start research" }).click();
    const response = await created; assert.equal(response.status(), 202);
    const { id } = await response.json();
    receipt.operations.push({ action: "research", id, dataset_id: selected }); save();
    await expect(page.locator("#run-header .badge").first()).toHaveText("completed", { timeout: 120_000 });
    const reviewBytes = await download("Review JSON", "review.json");
    const reportBytes = await download("Text report", "report.txt");
    const review = JSON.parse(reviewBytes);
    assert.equal(review.weather_history.dataset_id, "sha256:" + selected);
    assert.equal(review.coverage.independent_events, 4);
    assert.equal(review.probability_count, 0);
    assert.equal(review.final_holdout_evaluated, false);
    assert(review.candidates.length > 0);
    assert(review.candidates.every(c => c.status === "INSUFFICIENT_DATA" && !c.tested && c.scenarios.length === 0));
    for (const tab of ["Review", "Probabilities", "Evidence & lineage"]) {
      await page.getByRole("button", { name: tab, exact: true }).click();
      await expect(page.locator("#result-content .weather-history")).toContainText("4 events on 2 dates");
      await expect(page.locator("#result-content")).toContainText("Final holdout is excluded");
      await screenshot(tab.replaceAll(/[^a-z]/gi, "-"));
    }
    await stop(); await start(); await page.goto(origin + "/#/workbench");
    await expect(page.locator("#weather-dataset")).toHaveValue(selected);
    await page.locator("#history button").filter({ has: page.getByText(idea, { exact: true }) }).click();
    await expect(page.locator("#run-header .badge").first()).toHaveText("completed");
    assert.deepEqual(await download("Download label evidence", "restart-labels.json"), labelBytes);
    assert.deepEqual(await download("Review JSON", "restart-review.json"), reviewBytes);
    assert.deepEqual(await download("Text report", "restart-report.txt"), reportBytes);
    await screenshot("restart");
    assert.deepEqual(receipt.page_errors, []);
    receipt.status = "passed";
  } catch (error) {
    receipt.status = "failed"; receipt.failure = error.stack || String(error); throw error;
  } finally {
    await stop(); receipt.finished_at = new Date().toISOString(); save();
  }
});
