"use strict";
// Separate CONTROLLED sustained collection and authentic insufficiency; managed Chromium.
const { test, expect, chromium } = require("@playwright/test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { spawn, spawnSync } = require("node:child_process");
const { createHash } = require("node:crypto");

for (const { controlled, cohort } of [{ controlled: true, cohort: false }, { controlled: false, cohort: false }, { controlled: true, cohort: true }]) {
test(`${cohort ? "research cohort" : "sustained shadow history"}: ${controlled ? "CONTROLLED 130 captures" : "authentic insufficiency"}, partition research and restore`, async ({ page, browser }) => {
  const repo = path.resolve(__dirname, "../..");
  const evidence = path.join(process.env.ENTROPYTRADE_BROWSER_EVIDENCE, cohort ? "cohort" : controlled ? "controlled" : "authentic");
  let workspace = process.env.ENTROPYTRADE_BROWSER_WORKSPACE + (cohort ? "-cohort" : controlled ? "-controlled" : "-authentic");
  const python = process.env.ENTROPYTRADE_BROWSER_PYTHON || path.join(repo, ".venv/bin/python");
  const port = Number(process.env.ENTROPYTRADE_BROWSER_PORT || 43144);
  const origin = `http://127.0.0.1:${port}`;
  assert(path.isAbsolute(workspace) && workspace.startsWith(path.join(repo, "data/cache/")));
  assert(!fs.existsSync(workspace), "Use a fresh workspace");
  assert(chromium.executablePath().startsWith(path.join(__dirname, ".browsers/")));
  fs.mkdirSync(evidence, { recursive: true });
  const receiptFile = path.join(evidence, "weather-browser-receipt.json");
  assert(!fs.existsSync(receiptFile));
  const receipt = { status: "running", started_at: new Date().toISOString(), origin, workspace,
    browser: browser.version(), executable: chromium.executablePath(), operations: [],
    screenshots: [], downloads: [], page_errors: [],
    limitations: [controlled ? "CONTROLLED collector with simulated clocks and wire data, no empirical evidence." : "Authentic original shadow receipt replay, not new acquisition.",
      cohort ? "CONTROLLED scalar labels exercise model fitting/calibration only. No empirical performance or certified fees." : "Source-matched scalar highs and certified fees are absent; no empirical model or returns.",
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
    const seeded = spawnSync(python, ["-m", cohort ? "tests.integration.cohort_fixture" : "tests.integration.shadow_history_fixture", workspace, path.join(evidence, "authentic-inputs.json"), ...(controlled ? [] : ["--authentic"])], { cwd: repo, env, encoding: "utf8", timeout: 300_000 });
    assert.equal(seeded.status, 0, seeded.stdout + seeded.stderr);
    receipt.operations.push({ action: "import", evidence: JSON.parse(fs.readFileSync(path.join(evidence, "authentic-inputs.json"))) }); save();
    await start(); await page.goto(origin);
    await expect(page.locator("#submit")).toBeEnabled();
    await expect(page.locator("#weather-partition-counts")).toContainText(controlled ? "130 retained inputs across 2 bounded partitions" : "2 retained inputs across 1 bounded partitions");
    if (cohort) {
      const values = await page.locator("#weather-cohort option").evaluateAll(options => options.map(o => o.value));
      assert.equal(values.length, 2);
      await page.getByLabel("Cohort history partitions", { exact: true }).selectOption(values);
    } else {
      await page.getByLabel("History partition", { exact: true }).selectOption({ index: 1 });
      if (controlled) await page.getByLabel("Outcome partition", { exact: true }).selectOption({ index: 2 });
    }
    await screenshot("partition-selection");
    const freezeName = cohort ? "Freeze research cohort" : "Freeze retained weather dataset";
    await page.getByRole("button", { name: freezeName, exact: true }).click();
    await expect(page.locator("#weather-message")).toContainText(cohort ? "Immutable research cohort selected" : "Immutable dataset selected", { timeout: 120_000 });
    const counts = cohort ? "200 events on 100 dates" : controlled ? "1 events on 1 dates" : "4 events on 2 dates";
    await expect(page.locator("#weather-readiness")).toContainText(counts);
    if (cohort) {
      await expect(page.locator("#weather-readiness")).toContainText("ready for model gates");
      await expect(page.locator("#weather-readiness")).toContainText("Research cohort · 2 retained history partitions");
      await expect(page.locator("#weather-readiness")).toContainText("20 protected events");
    } else {
      await expect(page.locator("#weather-readiness")).toContainText("0 source-matched scalar labels");
      await expect(page.locator("#weather-readiness")).toContainText("fit: 0/60");
      await expect(page.locator("#weather-readiness")).toContainText(controlled ? "128 verified shadow cycles" : "2 verified shadow cycles");
    }
    const selected = await page.locator("#weather-dataset").inputValue();
    assert.match(selected, /^[0-9a-f]{64}$/);
    await expect(page.locator("#mode")).toHaveValue("weather_history");
    await screenshot("dataset");
    // A repeated freeze must reuse the same immutable identity and counts.
    await page.getByRole("button", { name: freezeName, exact: true }).click();
    await expect(page.getByRole("button", { name: freezeName, exact: true })).toBeEnabled({ timeout: 120_000 });
    await expect(page.locator("#weather-dataset option")).toHaveCount(1);
    await expect(page.locator("#weather-dataset")).toHaveValue(selected);
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
    assert.equal(review.coverage.independent_events, cohort ? 180 : controlled ? 1 : 4);
    assert(cohort ? review.probability_count > 0 : review.probability_count === 0);
    assert.equal(review.final_holdout_evaluated, false);
    assert(review.candidates.length > 0);
    assert(review.candidates.every(c => c.status === "INSUFFICIENT_DATA" && !c.tested && c.scenarios.length === 0));
    const inputsBytes = await download("Shadow experiment inputs", "shadow-inputs.json");
    const inputs = JSON.parse(inputsBytes);
    assert.equal(inputs.submission_enabled, false);
    assert.equal(inputs.cycles.length, cohort ? 0 : controlled ? 128 : 2);
    for (const cycle of inputs.cycles) for (const sample of cycle.experiment_data.samples) {
      assert(sample.versions.forecast_high_f);
      if (sample.book) assert(new Date(sample.book.received_at) <= new Date(sample.decision_time));
      assert(controlled ? sample.outcome === "yes" : sample.outcome === null);
    }
    for (const tab of ["Review", "Probabilities", "Evidence & lineage"]) {
      await page.getByRole("button", { name: tab, exact: true }).click();
      await expect(page.locator("#result-content .weather-history")).toContainText(counts);
      await expect(page.locator("#result-content")).toContainText("Final holdout is excluded");
      await screenshot(tab.replaceAll(/[^a-z]/gi, "-"));
    }
    await stop();
    const archive = path.join(evidence, "offline.zip");
    const restored = workspace + "-restored";
    for (const [action, target] of [["snapshot", workspace], ["restore", restored]]) {
      const result = spawnSync(python, ["-m", "entropytrade.api.recovery", action, "--workspace", target, "--archive", archive], { cwd: repo, env, encoding: "utf8", timeout: 180_000 });
      assert.equal(result.status, 0, result.stdout + result.stderr);
      receipt.operations.push({ action, receipt: JSON.parse(result.stdout) }); save();
    }
    workspace = restored;
    await start(); await page.goto(origin);
    await expect(page.locator("#weather-dataset")).toHaveValue(selected);
    await page.locator("#history button").filter({ has: page.getByText(idea, { exact: true }) }).click();
    await expect(page.locator("#run-header .badge").first()).toHaveText("completed");
    assert.deepEqual(await download("Review JSON", "restart-review.json"), reviewBytes);
    assert.deepEqual(await download("Text report", "restart-report.txt"), reportBytes);
    assert.deepEqual(await download("Shadow experiment inputs", "restart-shadow-inputs.json"), inputsBytes);
    await expect(page.locator("#weather-partition-counts")).toContainText(controlled ? "130 retained inputs" : "2 retained inputs");
    await screenshot("restart");
    assert.deepEqual(receipt.page_errors, []);
    receipt.status = "passed";
  } catch (error) {
    receipt.status = "failed"; receipt.failure = error.stack || String(error); throw error;
  } finally {
    await stop(); receipt.finished_at = new Date().toISOString(); save();
  }
});

}
