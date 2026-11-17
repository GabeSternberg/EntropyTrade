"use strict";
// Real localhost services and managed Chromium. Count-only metadata probes are
// separated from the single actual synthetic C fit/replay/D paper lineage.
const { test, expect, chromium } = require("@playwright/test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { spawn } = require("node:child_process");
const { createHash } = require("node:crypto");

const repo = path.resolve(__dirname, "../..");
const pause = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const sha = (bytes) => createHash("sha256").update(bytes).digest("hex");
function manifest(directory, include = () => true) {
  const files = [];
  function walk(current) {
    if (!fs.existsSync(current)) return;
    for (const entry of fs.readdirSync(current, { withFileTypes: true })) {
      const file = path.join(current, entry.name);
      if (entry.isDirectory()) walk(file);
      else if (entry.isFile() && include(file)) files.push([path.relative(directory, file), sha(fs.readFileSync(file))]);
    }
  }
  walk(directory);
  return files.sort(([a], [b]) => a.localeCompare(b));
}
function sourceFingerprint() {
  const files = [];
  for (const directory of ["backend/src", "backend/tests", "frontend/src", "frontend/tests"]) {
    files.push(...manifest(path.join(repo, directory), (file) => !file.includes("/__pycache__/") && /\.(py|js|cjs|css|html|json|gz|csv)$/.test(file)).map(([file, digest]) => [directory + "/" + file, digest]));
  }
  for (const file of fs.readdirSync(__dirname).filter((file) => file.endsWith(".cjs")).sort()) files.push(["frontend/browser/" + file, sha(fs.readFileSync(path.join(__dirname, file)))]);
  return { sha256: sha(JSON.stringify(files)), files: files.length };
}

async function setup(page, browser, scenario, portOffset) {
  const evidence = path.join(process.env.ENTROPYTRADE_BROWSER_EVIDENCE, "lifecycle-" + scenario);
  const workspace = process.env.ENTROPYTRADE_BROWSER_WORKSPACE + "-lifecycle-" + scenario;
  const python = process.env.ENTROPYTRADE_BROWSER_PYTHON || path.join(repo, ".venv/bin/python");
  const origin = `http://127.0.0.1:${Number(process.env.ENTROPYTRADE_BROWSER_PORT || 43231) + portOffset}`;
  assert(path.isAbsolute(workspace) && workspace.startsWith(path.join(repo, "data/cache/")));
  assert(!fs.existsSync(workspace), "workspace must be new");
  assert(!fs.existsSync(evidence), "evidence directory must be new");
  assert(chromium.executablePath().startsWith(path.join(__dirname, ".browsers/")));
  assert(!await fetch(origin + "/api/catalog").catch(() => null), "Port occupied");
  fs.mkdirSync(evidence, { recursive: true });
  const metadataFile = path.join(evidence, "setup.json");
  const receipt = { status: "running", scenario, browser: browser.version(), source_before: sourceFingerprint(), screenshots: [], downloads: [], api_requests: [], posts: [], page_errors: [], console_errors: [], submission_enabled: false };
  const save = () => fs.writeFileSync(path.join(evidence, "receipt.json"), JSON.stringify(receipt, null, 2) + "\n");
  page.on("pageerror", (error) => { receipt.page_errors.push(error.message); save(); });
  page.on("console", (message) => { if (message.type() === "error") { receipt.console_errors.push(message.text()); save(); } });
  page.on("request", (request) => {
    const pathname = new URL(request.url()).pathname;
    if (!pathname.startsWith("/api/")) return;
    receipt.api_requests.push({ path: pathname, method: request.method() });
    if (request.method() === "POST") receipt.posts.push({ path: pathname, body: request.postDataJSON() });
    save();
  });
  const env = { PATH: "/usr/bin:/bin", TZ: "UTC", PYTHONNOUSERSITE: "1", PYTHONDONTWRITEBYTECODE: "1", OMP_NUM_THREADS: "1", OPENBLAS_NUM_THREADS: "1", PYTHONPATH: `${repo}/backend:${repo}/backend/src` };
  const log = fs.openSync(path.join(evidence, "server.log"), "a");
  const server = spawn(python, ["-m", "tests.integration.lifecycle_fixture", "--workspace", workspace, "--port", new URL(origin).port, "--metadata", metadataFile, "--scenario", scenario], { cwd: repo, env, stdio: ["ignore", log, log] });
  fs.closeSync(log);
  const get = async (url) => {
    const response = await fetch(origin + url);
    assert(response.ok, `${response.status}: ${url}`);
    return response.json();
  };
  const run = { evidence, workspace, origin, receipt, save, get, metadata: null };
  run.ready = async () => {
    for (let n = 0; n < 1800; n++) {
      if (server.exitCode !== null) throw new Error(`Listener exited ${server.exitCode}; inspect lifecycle-${scenario}/server.log`);
      if (fs.existsSync(metadataFile) && (await fetch(origin + "/api/catalog").catch(() => null))?.ok) {
        run.metadata = JSON.parse(fs.readFileSync(metadataFile));
        run.originals = manifest(workspace, (file) => !/\.sqlite(?:-wal|-shm)?$|\.lock$/.test(file));
        fs.writeFileSync(path.join(evidence, "retained-original-hashes.json"), JSON.stringify(run.originals, null, 2) + "\n");
        return;
      }
      await pause(100);
    }
    throw new Error("Lifecycle fixture startup timeout");
  };
  run.shot = async (file) => { await page.evaluate(() => window.scrollTo(0, 0)); await page.screenshot({ path: path.join(evidence, file), fullPage: true }); receipt.screenshots.push(file); save(); };
  run.download = async (locator, file) => {
    const waiting = page.waitForEvent("download");
    await locator.click();
    await (await waiting).saveAs(path.join(evidence, file));
    const bytes = fs.readFileSync(path.join(evidence, file));
    receipt.downloads.push({ file, sha256: sha(bytes) }); save();
    return JSON.parse(bytes);
  };
  run.finish = async () => {
    if (!page.isClosed()) await page.goto("about:blank");
    if (server.exitCode === null && server.signalCode === null) {
      server.kill("SIGINT");
      await new Promise((resolve) => server.exitCode !== null ? resolve() : server.once("exit", resolve));
    }
    receipt.source_after = sourceFingerprint();
    if (run.originals) {
      const after = new Map(manifest(workspace, (file) => !/\.sqlite(?:-wal|-shm)?$|\.lock$/.test(file)));
      receipt.retained_originals_unchanged = run.originals.every(([file, digest]) => after.get(file) === digest);
    }
    const completed = receipt.status === "passed";
    if (completed && (receipt.page_errors.length || receipt.console_errors.length || receipt.source_before.sha256 !== receipt.source_after.sha256 || receipt.retained_originals_unchanged === false)) receipt.status = "failed";
    save();
    if (completed) {
      assert.deepEqual(receipt.page_errors, []);
      assert.deepEqual(receipt.console_errors, []);
      assert.deepEqual(receipt.source_after, receipt.source_before, "Application and acceptance source must stay frozen");
      assert.equal(receipt.retained_originals_unchanged, true, "Existing evidence files must retain their original bytes");
    }
  };
  save();
  return run;
}

for (const [scenario, offset] of [["empty", 0], ["unavailable", 1]]) {
  test(`unified lifecycle summary: actual ${scenario} workspace`, async ({ page, browser }) => {
    const run = await setup(page, browser, scenario, offset);
    try {
      await run.ready();
      const summary = await run.get("/api/workspace/summary");
      assert.equal(summary.recorded_metadata_only, true);
      await page.goto(run.origin + "/#/overview");
      const research = page.locator('[data-summary-component="research_jobs"]');
      await expect(research.locator(".kpi-value")).toHaveText(scenario === "empty" ? "0" : "—");
      if (scenario === "empty") {
        assert.equal(summary.components.research_jobs.available, true);
        assert.equal(summary.components.research_jobs.initialized, false);
        assert.equal(summary.components.research_jobs.counts.total, 0);
        await expect(research).toContainText("not started");
      } else {
        assert.equal(summary.components.research_jobs.available, false);
        assert.equal(summary.components.research_jobs.counts, null);
        assert.equal(summary.components.legacy_jobs.available, true);
        await expect(research).toContainText("unavailable");
        await expect(page.locator('[data-summary-component="legacy_jobs"] .kpi-value')).toHaveText("0");
        await expect(page.getByText("Recorded metadata unavailable").first()).toBeVisible();
      }
      await expect(page.getByText(/A recorded result, validation, model or readiness review does not prove/)).toBeVisible();
      await run.shot(scenario + "-overview.png");
      run.receipt.summary = summary;
      run.receipt.status = "passed";
    } catch (error) { run.receipt.status = "failed"; run.receipt.error = error.stack || error.message; throw error; }
    finally { await run.finish(); }
  });
}

test("unified lifecycle: actual persisted research, exact evidence links, Demo isolation and legacy handoff", async ({ page, browser }) => {
  const run = await setup(page, browser, "mixed", 2);
  const view = page.locator("#view");
  const navigate = async (hash) => { await page.evaluate((value) => { window.location.hash = value; }, hash); await expect(page).toHaveURL(run.origin + "/" + hash); };
  try {
    await run.ready();
    const meta = run.metadata;
    const summary = await run.get("/api/workspace/summary");
    for (const [key, total] of Object.entries(meta.expected_totals)) assert.equal(summary.components[key].counts.total, total, key);
    assert(summary.components.research_jobs.counts.total > 50);
    assert(summary.components.experiments.counts.total > 50);
    assert(summary.components.legacy_jobs.counts.total > 50);
    assert.equal(summary.components.paper_accounts.counts.by_data_kind.synthetic, 1);
    assert(summary.components.experiments.counts.by_data_kind.real > 0);
    assert(summary.components.experiments.counts.by_data_kind.synthetic > 0);
    assert.equal(summary.components.experiments.counts.with_recorded_model, 1);
    assert(Object.values(summary.components).every((component) => component.recent.length <= 10));
    run.receipt.summary_before = summary;
    await page.goto(run.origin + "/#/overview");
    for (const key of ["research_jobs", "experiments", "legacy_jobs", "course_jobs", "paper_accounts"]) await expect(page.locator(`[data-summary-component="${key}"] .kpi-value`)).toHaveText(String(meta.expected_totals[key]));
    await expect(page.locator('[data-summary-records="experiments"]')).toContainText("real:");
    await expect(page.locator('[data-summary-records="experiments"]')).toContainText("synthetic:");
    await expect(page.locator('[data-summary-records="paper_accounts"]')).toContainText("synthetic: 1");
    await expect(view.getByText(/Counts and statuses describe stored metadata/)).toBeVisible();
    await run.shot("mixed-full-counts-overview.png");

    // Summary references, not positional list selection, choose the actual C record.
    const experimentHash = `#/research/${meta.job_id}?tab=experiments&experiment=${encodeURIComponent(meta.experiment_id)}`;
    await page.locator('[data-summary-records="experiments"] .summary-ref').filter({ hasText: meta.experiment_id }).click();
    await expect(page).toHaveURL(run.origin + "/" + experimentHash);
    const experiment = page.locator(`[data-experiment="${meta.experiment_id}"]`);
    await expect(experiment).toBeVisible();
    await expect(page.locator(".research-experiment")).toHaveCount(1);
    await expect(experiment.getByText("Validation metrics and baselines", { exact: true })).toBeVisible();
    await expect(experiment.getByText("Recorded backtest performance", { exact: true })).toBeVisible();
    await expect(experiment.getByText("Independent validation", { exact: true })).toBeVisible();
    await expect(experiment.getByText(/CONTROLLED SYNTHETIC/)).toBeVisible();
    const report = await run.download(page.locator("#research-export"), "actual-synthetic-research.json");
    assert.equal(report.job.id, meta.job_id);
    const result = report.job.experiments.find((item) => item.id === meta.experiment_id).result;
    assert.equal(result.data_kind, "synthetic");
    assert(Object.values(result.models).some((model) => model.artifact_hash));
    assert(result.backtest.performance.scenarios.length > 0);
    assert.equal(result.validation.holdout_evaluated, false);
    await page.reload();
    await expect(experiment).toBeVisible();
    await run.shot("exact-model-validation-backtest.png");
    await experiment.getByRole("link", { name: "Exact paper eligibility", exact: true }).click();
    const proposal = page.locator(`[data-paper-proposal="${meta.experiment_id}"]`);
    await expect(proposal.first()).toBeVisible({ timeout: 90_000 });
    assert((await page.locator("[data-paper-proposal]").evaluateAll((nodes) => nodes.map((node) => node.dataset.paperProposal))).every((id) => id === meta.experiment_id));
    await page.goBack(); await expect(experiment).toBeVisible();
    await page.goForward(); await expect(proposal.first()).toBeVisible();
    await run.shot("exact-research-paper-proposal.png");

    const accountHash = `#/paper/${meta.monitor_id}?tab=account`;
    await navigate(accountHash);
    await expect(page.locator("#paper-governance")).toBeVisible({ timeout: 90_000 });
    await expect(view.getByText(/CONTROLLED SYNTHETIC accounting/)).toBeVisible();
    const monitor = await run.download(page.getByRole("link", { name: "Execution evidence JSON", exact: true }), "actual-paper-export.json");
    const account = await run.download(page.getByRole("link", { name: "Paper account JSON", exact: true }), "actual-paper-account.json");
    assert.equal(monitor.source_kind, "autonomous_research");
    assert.equal(monitor.research_job_id, meta.job_id);
    assert.equal(monitor.experiment_id, meta.experiment_id);
    assert.equal(monitor.cycle_count, 1);
    assert.equal(account.summary.data_kind, "synthetic");
    assert.equal(account.submission_enabled, false);
    assert.equal(account.summary.state_hash, monitor.paper_summary.state_hash);
    assert(account.summary.fill_count > 0, "Actual incoming computation must produce simulated fills");
    await expect(page.getByRole("switch", { name: "Live trading (disabled)" })).toBeDisabled();
    run.receipt.paper = { monitor_id: meta.monitor_id, cycles: monitor.cycle_count, source_kind: monitor.source_kind, data_kind: monitor.paper_summary.data_kind };
    await run.shot("exact-paper-account.png");
    await page.locator("#paper-deployment").getByRole("link", { name: meta.experiment_id, exact: true }).click();
    await expect(page).toHaveURL(run.origin + "/" + experimentHash);
    await expect(experiment).toBeVisible();
    await page.goBack();
    await expect(page.locator("#paper-deployment")).toBeVisible();

    const readinessHash = `#/paper/${meta.monitor_id}?tab=readiness`;
    await navigate(readinessHash);
    const governance = page.locator("#paper-governance");
    await governance.getByLabel("Proposed capital in dollars").fill("100.00");
    await governance.getByLabel("Proposed maximum loss in dollars").fill("10.00");
    const saving = page.waitForResponse((response) => response.request().method() === "POST" && new URL(response.url()).pathname === `/api/monitors/${meta.monitor_id}/readiness`, { timeout: 90_000 });
    await governance.getByRole("button", { name: "Save readiness proposal", exact: true }).click();
    const saved = await saving; const readiness = await saved.json();
    assert.equal(saved.status(), 201, JSON.stringify(readiness));
    const proposalId = readiness.id || readiness.proposal.id;
    assert.equal(readiness.proposal.payload.eligible, false);
    assert.equal(readiness.proposal.payload.execution_authorized, false);
    assert.equal(readiness.proposal.payload.submission_enabled, false);
    const selectedReadinessHash = readinessHash + "&proposal=" + encodeURIComponent(proposalId);
    await expect(page).toHaveURL(run.origin + "/" + selectedReadinessHash);
    await expect(governance.getByRole("button", { name: "Approve readiness review", exact: true })).toBeDisabled();
    await expect(governance.getByText(/Owner access is not configured/)).toBeVisible();
    const readinessRecord = await run.download(page.getByRole("link", { name: "Readiness record JSON", exact: true }), "blocked-readiness.json");
    assert.equal(readinessRecord.id, proposalId);
    await page.reload();
    await expect(page.getByRole("link", { name: "Readiness record JSON", exact: true })).toHaveAttribute("href", `/api/readiness/${encodeURIComponent(proposalId)}`, { timeout: 90_000 });
    await run.shot("exact-blocked-readiness.png");

    const alertHash = `#/ops?tab=alerts&monitor=${meta.monitor_id}&alert=${meta.alert_id}`;
    await navigate(alertHash);
    await expect(page.locator(`[data-alert="${meta.alert_id}"]`)).toBeVisible({ timeout: 90_000 });
    await expect(page.locator(".alerts-filter")).toContainText(meta.monitor_id);
    await page.reload();
    await expect(page.locator(`[data-alert="${meta.alert_id}"]`)).toBeVisible();
    await run.shot("exact-stale-collection-alert.png");
    await page.locator(`[data-alert="${meta.alert_id}"]`).locator("xpath=ancestor::tr").locator(`a[href="#/paper/${meta.monitor_id}?tab=monitoring"]`).click();
    await expect(page).toHaveURL(run.origin + `/#/paper/${meta.monitor_id}?tab=monitoring`);
    await expect(governance.getByText("Observed signals", { exact: true })).toBeVisible({ timeout: 90_000 });
    const monitoring = await run.get(`/api/monitors/${meta.monitor_id}/monitoring`);
    assert.equal(monitoring.monitor_id, meta.monitor_id);
    assert.equal(monitoring.submission_enabled, false);
    const investigationIds = [...new Set((monitoring.investigations || []).map((item) => item.research_job_id).filter(Boolean))];
    for (const id of investigationIds) {
      const investigation = await run.get(`/api/research/jobs/${id}`);
      assert.equal(investigation.request.acquisition, "none");
      assert.equal(investigation.request.provider.provider, "local_templates");
      assert.equal(investigation.request.budget.max_http_requests, 0);
      assert.equal(investigation.request.budget.max_bytes, 0);
      assert.equal(investigation.request.paper_preference, "never");
      assert(investigation.request.objective.startsWith("Investigate retained paper incident "));
    }
    run.receipt.monitoring = { evaluation: monitoring.evaluation.status, investigation_job_ids: investigationIds };
    fs.writeFileSync(path.join(run.evidence, "actual-monitoring-investigations.json"), JSON.stringify(monitoring, null, 2) + "\n");
    await page.goBack(); await expect(page).toHaveURL(run.origin + "/" + alertHash);

    // Explicit palette entry starts a durable, ordinary inventory-only job.
    await page.getByRole("button", { name: "Search (Command K)", exact: true }).click();
    await page.getByRole("searchbox", { name: "Search", exact: true }).fill("New research");
    await page.getByRole("option", { name: /New research/ }).click();
    await expect(page).toHaveURL(run.origin + "/#/research?new=1");
    const objective = "CONTROLLED browser lifecycle: investigate Bitcoin daily threshold outcomes with point in time source evidence.";
    await page.locator("#research-objective").fill(objective);
    await page.locator("#research-family").selectOption("bitcoin");
    await page.locator("#research-provider").selectOption("local_templates");
    await page.locator("#research-acquisition").selectOption("none");
    const submitting = page.waitForResponse((response) => response.request().method() === "POST" && new URL(response.url()).pathname === "/api/research/jobs");
    await page.locator("#research-submit").click();
    const submitted = await submitting; const created = await submitted.json();
    assert.equal(submitted.status(), 202);
    await expect(page).toHaveURL(run.origin + `/#/research/${created.id}`);
    await expect.poll(async () => (await run.get(`/api/research/jobs/${created.id}`)).status, { timeout: 90_000 }).toMatch(/awaiting_observations|evaluated|awaiting_authorization/);
    const persisted = await run.get(`/api/research/jobs/${created.id}`);
    assert.equal(persisted.request.objective, objective);
    assert.equal(persisted.request.provider.provider, "local_templates");
    assert(persisted.events.some((event) => event.stage === persisted.status));
    await page.reload();
    await expect(page.locator(".research-status-row").locator(`[data-status="${persisted.status}"]`)).toBeVisible();
    await page.getByRole("tab", { name: /Data requirements/ }).click();
    await expect(view.getByText(/missing|awaiting|unobtainable|partial/i).first()).toBeVisible();
    await page.getByRole("tab", { name: /Modeling & validation/ }).click();
    await expect(view.getByText(/No fitted validation metrics|No experiments/).first()).toBeVisible();
    run.receipt.new_job = { id: created.id, status: persisted.status, provider: persisted.request.provider.provider, events: persisted.events.map((event) => event.stage) };
    await run.shot("actual-new-persistent-research-status.png");

    // Lazy Real legacy and course handoffs stay usable. These records explicitly
    // describe cancellation before execution and carry no invented result.
    await page.evaluate(async (id) => { await window.ET.openRun(id); }, meta.legacy_job_id);
    await expect(page.locator("#workbench-view")).toBeVisible();
    await expect(page.locator("#run-header")).toContainText("CONTROLLED metadata-only recorded");
    await expect(page.locator("#run-header")).toContainText("cancelled");
    await page.getByLabel("Research idea", { exact: true }).fill("CONTROLLED stale legacy handler must never dispatch");
    await page.evaluate(() => { window.__lifecycleLegacySubmit = document.querySelector("#submit"); });
    await navigate(`#/cis1990/${meta.course_job_id}`);
    await expect(page.getByRole("heading", { name: "CIS 1990 Research Demo", exact: true })).toBeVisible();
    await expect(view).toContainText("CONTROLLED metadata-only cis1990");
    await page.getByLabel("Gemini API key", { exact: true }).fill("CONTROLLED-browser-never-dispatched");
    await page.evaluate(() => { window.__lifecycleCourseSubmit = [...document.querySelectorAll("button")].find((button) => button.textContent === "Run Philadelphia Weather Research"); });
    await run.shot("real-legacy-course-handoff.png");
    const hiddenBefore = run.receipt.api_requests.length;
    await page.evaluate(() => { window.__lifecycleLegacySubmit.disabled = false; window.__lifecycleLegacySubmit.click(); });
    await pause(1800);
    assert.equal(run.receipt.api_requests.length, hiddenBefore, "Hidden legacy handlers/polling must dispatch no API requests");

    // Every API request is counted, including reads and handlers saved in Real.
    await page.locator("#mode-switch").getByRole("button", { name: "Demo", exact: true }).click();
    await expect(page.locator("body")).toHaveClass(/mode-demo/);
    const demoBefore = run.receipt.api_requests.length;
    await page.evaluate(() => { window.__lifecycleLegacySubmit.disabled = false; window.__lifecycleLegacySubmit.click(); window.__lifecycleCourseSubmit.disabled = false; window.__lifecycleCourseSubmit.click(); });
    for (const hash of ["#/overview", "#/research?new=1", "#/lab", "#/analytics", "#/paper", "#/ops?tab=alerts", "#/workbench", "#/cis1990"]) {
      await navigate(hash);
      await expect(page.locator("#view:visible, #workbench-view:visible").first()).toBeVisible();
    }
    await navigate("#/workbench");
    await expect(page.locator("#submit")).toBeDisabled();
    await pause(1900);
    assert.equal(run.receipt.api_requests.length, demoBefore, "Demo must dispatch ZERO API reads or writes, including stale handlers and polling");
    run.receipt.demo_api_requests = run.receipt.api_requests.slice(demoBefore);
    await run.shot("demo-workbench-zero-api.png");
    await page.locator("#mode-switch").getByRole("button", { name: "Real", exact: true }).click();
    await expect(page.locator("#submit")).toBeEnabled();
    await page.evaluate(async (id) => { await window.ET.openRun(id); }, meta.legacy_job_id);
    await expect(page.locator("#run-header")).toContainText("CONTROLLED metadata-only recorded");

    // Exact selected scientific context survives a narrow reload and history.
    await navigate(experimentHash);
    await expect(experiment).toBeVisible();
    await page.setViewportSize({ width: 375, height: 900 });
    await page.reload();
    await expect(experiment).toBeVisible();
    assert(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth) <= 1);
    await run.shot("mobile-375-exact-experiment.png");
    await navigate(selectedReadinessHash);
    await expect(page.getByRole("link", { name: "Readiness record JSON", exact: true })).toBeVisible({ timeout: 90_000 });
    assert(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth) <= 1);
    await run.shot("mobile-375-exact-readiness.png");
    const unknown = "sha256:" + "f".repeat(64);
    await navigate(`#/research/${meta.job_id}?tab=experiments&experiment=${encodeURIComponent(unknown)}`);
    await expect(page.locator(".research-experiment")).toHaveCount(0);
    await expect(view.getByText(/Selected experiment.*not found|Experiment not found/i)).toBeVisible();
    run.receipt.summary_after = await run.get("/api/workspace/summary");
    assert.equal(run.receipt.summary_after.components.research_jobs.counts.total, meta.expected_totals.research_jobs + 1 + investigationIds.length,
      "Full summary includes the submitted job and exact server-created bounded incident investigations");
    run.receipt.status = "passed";
  } catch (error) { run.receipt.status = "failed"; run.receipt.error = error.stack || error.message; throw error; }
  finally { await run.finish(); }
});
