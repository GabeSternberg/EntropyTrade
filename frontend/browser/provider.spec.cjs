"use strict";
// Real Playwright-managed Chromium, localhost, durable jobs and worker subprocesses.
// The first listener controls only provider HTTP; the second is unmodified/no credentials.
const { test, expect, chromium } = require("@playwright/test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { spawn } = require("node:child_process");
const { createHash } = require("node:crypto");

test("provider-backed website: opt-in, typed candidates, failures, cancellation and recovery", async ({ page, browser }) => {
  const repo = path.resolve(__dirname, "../..");
  const evidence = process.env.ENTROPYTRADE_BROWSER_EVIDENCE;
  const workspace = process.env.ENTROPYTRADE_BROWSER_WORKSPACE + "-provider";
  const python = process.env.ENTROPYTRADE_BROWSER_PYTHON || path.join(repo, ".venv/bin/python");
  const port = Number(process.env.ENTROPYTRADE_BROWSER_PORT || 43136) + 2;
  const origin = `http://127.0.0.1:${port}`;
  assert(path.isAbsolute(workspace) && workspace.startsWith(path.join(repo, "data/cache/")));
  assert(!fs.existsSync(workspace), "Use a fresh workspace");
  assert(chromium.executablePath().startsWith(path.join(__dirname, ".browsers/")));
  fs.mkdirSync(evidence, { recursive: true });
  const receiptFile = path.join(evidence, "provider-browser-receipt.json");
  assert(!fs.existsSync(receiptFile));
  const receipt = { status: "running", started_at: new Date().toISOString(), origin, workspace,
    browser: browser.version(), executable: chromium.executablePath(), operations: [],
    screenshots: [], downloads: [], page_errors: [],
    limitations: ["Controlled provider HTTP proves software integration, never external provider access.",
      "Recorded weather is authentic but insufficient for empirical fitting/returns.",
      "External provider check BLOCKED: no separately authorized credentials; no key accessed.",
      "V1, empirical fitting, certified fees and two-family validation remain incomplete."] };
  const save = () => fs.writeFileSync(receiptFile, JSON.stringify(receipt, null, 2) + "\n");
  const sha = bytes => createHash("sha256").update(bytes).digest("hex");
  const pause = ms => new Promise(resolve => setTimeout(resolve, ms));
  const env = { PATH: "/usr/bin:/bin", PYTHONNOUSERSITE: "1", PYTHONDONTWRITEBYTECODE: "1",
    OMP_NUM_THREADS: "1", OPENBLAS_NUM_THREADS: "1", TZ: "UTC",
    PYTHONPATH: path.join(repo, "backend") + ":" + path.join(repo, "backend/src") };
  page.on("pageerror", error => { receipt.page_errors.push(error.message); save(); });
  let server, epoch = 0;
  async function start(controlled) {
    assert(!await fetch(origin + "/api/catalog").catch(() => null), "Port is occupied");
    const log = fs.openSync(path.join(evidence, `provider-server-${++epoch}.log`), "a");
    const module = controlled ? "tests.integration.provider_fixture" : "entropytrade.api.server";
    const args = ["-m", module, "--workspace", workspace, "--port", String(port)];
    if (!controlled) args.push("--research-provider", "openai", "--research-model", "gpt-4.1-mini");
    server = spawn(python, args, { cwd: repo, env, stdio: ["ignore", log, log] });
    fs.closeSync(log);
    for (let i = 0; i < 100; i++) {
      if (server.exitCode !== null) throw new Error(`Server exited ${server.exitCode}`);
      const response = await fetch(origin + "/api/catalog").catch(() => null);
      if (response?.ok) {
        const catalog = await response.json();
        assert.equal(catalog.submission_enabled, false); assert.equal(catalog.provider_enabled, true);
        assert.deepEqual(catalog.research_provider, { provider: "openai", model_name: "gpt-4.1-mini" });
        receipt.operations.push({ action: "start", controlled_provider_http: controlled, epoch }); save(); return;
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
    const file = `provider-${name}.png`;
    await page.screenshot({ path: path.join(evidence, file), fullPage: true });
    receipt.screenshots.push({ file, sha256: sha(fs.readFileSync(path.join(evidence, file))) }); save();
  }
  async function download(link, name) {
    const pending = page.waitForEvent("download");
    await page.getByRole("link", { name: link, exact: true }).click();
    const file = `provider-${name}`;
    await (await pending).saveAs(path.join(evidence, file));
    const bytes = fs.readFileSync(path.join(evidence, file));
    receipt.downloads.push({ file, sha256: sha(bytes) }); save(); return bytes;
  }
  async function submit(idea) {
    await page.getByLabel("Research idea", { exact: true }).fill(idea);
    await page.getByLabel("Hypothesis formulation").selectOption("provider");
    await expect(page.locator("#enable-provider")).not.toBeChecked();
    // Browser-required consent must prevent a submission without opt-in.
    await page.getByRole("button", { name: "Start research" }).click();
    await expect(page.locator("#enable-provider")).not.toBeChecked();
    await page.locator("#enable-provider").check();
    const pending = page.waitForResponse(r => r.url() === origin + "/api/jobs" && r.request().method() === "POST");
    await page.getByRole("button", { name: "Start research" }).click();
    const response = await pending; assert.equal(response.status(), 202);
    const { id } = await response.json();
    await expect(page.locator("#run-header h2")).toHaveText(idea);
    await expect(page.locator("#enable-provider")).not.toBeChecked();
    receipt.operations.push({ action: "submit", id, idea }); save(); return id;
  }
  async function reopen(idea, status) {
    const submitted = receipt.operations.find(operation => operation.action === "submit" && operation.idea === idea);
    assert(submitted, "Reopened run must match a recorded submitted job");
    await page.locator("#history button").filter({ has: page.getByText(idea, { exact: true }) }).click();
    // Consecutive runs may share a status. Wait for this run to render before
    // downloading; the prior run's failed badge alone cannot identify it.
    await expect(page.locator("#run-header h2")).toHaveText(idea);
    await expect(page.locator("#run-header .badge").first()).toHaveText(status);
    if (["completed", "failed"].includes(status)) {
      await expect(page.getByRole("link", { name: "Review JSON", exact: true })).toHaveAttribute("href", `/api/jobs/${submitted.id}/review`);
      await expect(page.getByRole("link", { name: "Text report", exact: true })).toHaveAttribute("href", `/api/jobs/${submitted.id}/report`);
    }
  }
  save();
  try {
    await start(true); await page.goto(origin);
    const idea = "CONTROLLED provider transport: investigate Philadelphia forecast revisions and model disagreement";
    await submit(idea);
    await expect(page.locator("#run-header .badge").first()).toHaveText("completed", { timeout: 90_000 });
    await expect(page.locator("article.candidate")).toHaveCount(3);
    await expect(page.locator("#result-content")).toContainText("Provider-backed bounded research");
    const reviewBytes = await download("Review JSON", "success.json");
    const reportBytes = await download("Text report", "success.txt");
    const review = JSON.parse(reviewBytes);
    assert.equal(review.reasoning, "provider"); assert.equal(review.data_kind, "real");
    assert.equal(review.hypotheses.length, 3); assert.equal(review.proposals.length, 3);
    assert.equal(review.research.stages.length, 4); assert.equal(review.final_holdout_evaluated, false);
    assert(review.candidates.every(c => !c.tested && c.scenarios.length === 0));
    assert.equal(review.probability_count, 0); assert(review.experiment_id.startsWith("sha256:"));
    assert(!reviewBytes.includes(Buffer.from("fixture-dedicated-key")));
    for (const tab of ["Review", "Probabilities", "Evidence & lineage"]) {
      await page.getByRole("button", { name: tab, exact: true }).click();
      await expect(page.locator("#result-content")).toContainText("Final holdout is excluded");
      await screenshot(`success-${tab.replaceAll(/[^a-z]/gi, "-")}`);
    }
    const outage = "CONTROLLED outage: preserve provider failure";
    await submit(outage);
    await expect(page.locator("#run-header .badge").first()).toHaveText("failed", { timeout: 90_000 });
    await expect(page.locator("#result-content")).toContainText("No candidates validated and no deterministic experiments ran");
    const failedBytes = await download("Review JSON", "outage.json");
    const failed = JSON.parse(failedBytes);
    assert.equal(failed.experiment_id, null); assert.equal(failed.research.failure.stage, "research");
    assert(!failedBytes.includes(Buffer.from("fixture-dedicated-key")));
    await screenshot("outage");

    const pricingFailures = [];
    for (const [label, requests] of [["first", 1], ["second", 2]]) {
      const idea = `CONTROLLED unpriced ${label}: refuse further provider requests`;
      await submit(idea);
      await expect(page.locator("#run-header .badge").first()).toHaveText("failed", { timeout: 90_000 });
      await expect(page.locator("#result-content")).toContainText("pricing is unavailable");
      await expect(page.locator("#result-content")).toContainText("No candidates validated and no deterministic experiments ran");
      const bytes = await download("Review JSON", `unpriced-${label}.json`);
      const failed = JSON.parse(bytes);
      assert.equal(failed.experiment_id, null); assert.deepEqual(failed.candidates, []);
      assert.equal(failed.research.failure.type, "ResearchPricingError");
      assert.equal(failed.research.pricing_status, "unavailable");
      assert.equal(failed.research.usage.requests, requests);
      assert.equal(failed.research.responses.length, requests);
      assert.equal(failed.research.responses.at(-1).usage.cost, null);
      assert.equal(failed.research.usage.cost === null, requests === 1);
      assert(!bytes.includes(Buffer.from("fixture-dedicated-key")));
      for (const tab of ["Review", "Probabilities", "Evidence & lineage"]) {
        await page.getByRole("button", { name: tab, exact: true }).click();
        await expect(page.locator("#result-content")).toContainText("pricing is unavailable");
      }
      await download("Text report", `unpriced-${label}.txt`);
      await screenshot(`unpriced-${label}`);
      pricingFailures.push({ idea, label, bytes });
    }

    const cancelled = "CONTROLLED slow: cancel provider request";
    await submit(cancelled);
    await expect(page.locator("#progress")).toContainText("research_research", { timeout: 30_000 });
    await page.getByRole("button", { name: "Cancel run", exact: true }).click();
    await expect(page.locator("#run-header .badge").first()).toHaveText("cancelled");
    const interrupted = "CONTROLLED slow: interrupt provider request";
    await submit(interrupted);
    await expect(page.locator("#progress")).toContainText("research_research", { timeout: 30_000 });
    await stop(); await start(false); await page.goto(origin);
    await reopen(interrupted, "interrupted"); await screenshot("recovered-interruption");
    await reopen(cancelled, "cancelled");
    await reopen(idea, "completed");
    assert.deepEqual(await download("Review JSON", "success-restarted.json"), reviewBytes);
    assert.deepEqual(await download("Text report", "success-restarted.txt"), reportBytes);
    await reopen(outage, "failed");
    assert.deepEqual(await download("Review JSON", "outage-restarted.json"), failedBytes);
    for (const { idea, label, bytes } of pricingFailures) {
      await reopen(idea, "failed");
      assert.deepEqual(await download("Review JSON", `unpriced-${label}-restarted.json`), bytes);
    }
    const missing = "Unmodified worker without separately configured research credentials";
    await submit(missing);
    await expect(page.locator("#run-header .badge").first()).toHaveText("failed", { timeout: 90_000 });
    await expect(page.locator("#result-content")).toContainText("ResearchCredentialError");
    const noKey = JSON.parse(await download("Review JSON", "missing-credential.json"));
    assert.equal(noKey.research.usage.requests, 0); assert.equal(noKey.research.failure.stage, "setup");
    assert.equal(noKey.research.failure.type, "ResearchCredentialError");
    await download("Text report", "missing-credential.txt");
    await screenshot("missing-credential");
    assert.deepEqual(receipt.page_errors, []);
    receipt.status = "passed";
  } catch (error) { receipt.status = "failed"; receipt.failure = error.stack; throw error; }
  finally { await stop(); receipt.finished_at = new Date().toISOString(); save(); }
});
