"use strict";
// Real browser + real server/worker. No route stubs, fixture results or direct job writes.
const { test, expect, chromium } = require("@playwright/test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { spawn, execFileSync } = require("node:child_process");
const { createHash } = require("node:crypto");

const repo = path.resolve(__dirname, "../..");
const evidence = process.env.ENTROPYTRADE_BROWSER_EVIDENCE;
const workspace = process.env.ENTROPYTRADE_BROWSER_WORKSPACE;
const python = process.env.ENTROPYTRADE_BROWSER_PYTHON || path.join(repo, ".venv/bin/python");
const port = Number(process.env.ENTROPYTRADE_BROWSER_PORT || 43128);
const origin = `http://127.0.0.1:${port}`;
const now = () => new Date().toISOString();
const sha = (bytes) => createHash("sha256").update(bytes).digest("hex");
const pause = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const write = (name, data) => fs.writeFileSync(path.join(evidence, name), JSON.stringify(data, null, 2) + "\n");
const git = (...args) => execFileSync("git", args, { cwd: repo, encoding: "utf8" }).trim();

test("four documented workbench workflows on the committed application", async ({ page, browser }, info) => {
  assert(workspace && path.isAbsolute(workspace), "Set a NEW absolute ENTROPYTRADE_BROWSER_WORKSPACE");
  assert(workspace.startsWith(path.join(repo, "data/cache/")));
  assert(!fs.existsSync(workspace), "Never reuse or overwrite previous acceptance runs");
  assert(!fs.existsSync(path.join(evidence, "browser-receipt.json")), "Never overwrite a receipt");
  fs.mkdirSync(evidence, { recursive: true });
  const receipt = {
    started_at_utc: now(), commit: git("rev-parse", "HEAD"), tree: git("rev-parse", "HEAD^{tree}"),
    branch: git("branch", "--show-current"), origin, workspace: path.relative(repo, workspace),
    browser: { engine: "Playwright Chromium", version: browser.version(),
      playwright: require("@playwright/test/package.json").version,
      executable: chromium.executablePath(), headless: true, fresh_context: true,
      computer_use: false, personal_chrome: false },
    workflows: [], runs: [], screenshots: [], downloads: [], lifecycle: [],
    console_errors: [], page_errors: [], failed_requests: [], acceptance_gaps: [],
    limitations: ["Synthetic performance is software evidence only.",
      "Public capture is forward evidence, never historical model evaluation.",
      "This is not the supervisor's independent final clean-checkout sign-off or V1 completion."],
  };
  const save = () => write("browser-receipt.json", receipt);
  save();
  assert(chromium.executablePath().startsWith(path.join(__dirname, ".browsers/")),
    "Only the harness's separate Playwright Chromium installation is permitted");
  const jobs = new Map();
  page.on("pageerror", (error) => { receipt.page_errors.push({ at_utc: now(), message: error.message }); save(); });
  page.on("console", (message) => {
    if (message.type() === "error") { receipt.console_errors.push({ at_utc: now(), text: message.text() }); save(); }
  });
  page.on("requestfailed", (request) => {
    receipt.failed_requests.push({ at_utc: now(), url: request.url(), error: request.failure()?.errorText }); save();
  });
  page.on("response", async (response) => {
    if (/\/api\/jobs\/[0-9a-f-]+$/.test(response.url()) && response.ok()) {
      try { const job = await response.json(); jobs.set(job.id, job); } catch { /* navigation may abort polling */ }
    }
  });
  let server;
  let epoch = 0;
  const completed = [];
  const failures = [];

  async function startServer({ denyPublic = false } = {}) {
    // Readiness requests are health probes only. Workflow writes/downloads use the UI.
    const occupied = await fetch(origin + "/api/catalog", { signal: AbortSignal.timeout(1000) }).catch(() => null);
    assert(!occupied, `Refusing to use or stop an existing listener on ${origin}`);
    epoch += 1;
    const logfile = path.join(evidence, `server-${epoch}.log`);
    const fd = fs.openSync(logfile, "a");
    const command = [python, "-m", "entropytrade.api.server", "--port", String(port), "--workspace", workspace];
    if (denyPublic) {
      assert(fs.existsSync("/usr/bin/sandbox-exec"), "Controlled public-network denial requires macOS sandbox-exec");
      command.unshift("/usr/bin/sandbox-exec", "-p", "(version 1) (allow default) (deny network-outbound)");
    }
    const env = { PATH: "/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin", PYTHONNOUSERSITE: "1",
      PYTHONDONTWRITEBYTECODE: "1", OMP_NUM_THREADS: "1", OPENBLAS_NUM_THREADS: "1",
      LOKY_MAX_CPU_COUNT: "1", TZ: "UTC", TMPDIR: "/private/tmp" };
    server = spawn(command[0], command.slice(1), { cwd: repo, env, stdio: ["ignore", fd, fd] });
    fs.closeSync(fd);
    receipt.lifecycle.push({ action: "start", at_utc: now(), epoch, pid: server.pid, command,
      environment: env, log: path.basename(logfile),
      fault_injection: denyPublic ? "OS denies outbound connections for backend and child workers; real requests fail, no response stubs" : null }); save();
    for (let attempt = 0; attempt < 100; attempt++) {
      if (server.exitCode !== null) throw new Error(`Backend exited ${server.exitCode}: ${fs.readFileSync(logfile, "utf8")}`);
      const response = await fetch(origin + "/api/catalog", { signal: AbortSignal.timeout(1000) }).catch(() => null);
      if (response?.ok) {
        const catalog = await response.json();
        assert.equal(catalog.submission_enabled, false); assert.equal(catalog.provider_enabled, false);
        receipt.lifecycle.push({ action: "ready", at_utc: now(), epoch, submission_enabled: false, provider_enabled: false }); save(); return;
      }
      await pause(100);
    }
    throw new Error("Backend not ready within ten seconds");
  }

  async function stopServer(reason) {
    if (!server || server.exitCode !== null || server.signalCode !== null) return;
    const process = server;
    receipt.lifecycle.push({ action: "SIGINT", at_utc: now(), epoch, pid: process.pid, reason }); save();
    process.kill("SIGINT");
    for (let attempt = 0; attempt < 100 && process.exitCode === null && process.signalCode === null; attempt++) await pause(100);
    if (process.exitCode === null && process.signalCode === null) {
      process.kill("SIGKILL");
      throw new Error("Backend did not stop gracefully within ten seconds");
    }
    receipt.lifecycle.push({ action: "stopped", at_utc: now(), epoch, exit_code: process.exitCode, signal: process.signalCode }); save();
  }

  async function screenshot(name) {
    const filename = `screenshots/${name}.png`;
    fs.mkdirSync(path.join(evidence, "screenshots"), { recursive: true });
    await page.screenshot({ path: path.join(evidence, filename), fullPage: true });
    receipt.screenshots.push({ at_utc: now(), file: filename, sha256: sha(fs.readFileSync(path.join(evidence, filename))) }); save();
  }

  async function load() {
    await page.goto(origin);
    await expect(page.getByRole("button", { name: "Start research" })).toBeEnabled();
    await expect(page.getByText("Research only · execution disabled", { exact: true })).toBeVisible();
  }

  async function submit(label, { example, family, mode, idea } = {}) {
    const started = now();
    if (example) await page.getByRole("button", { name: example, exact: true }).click();
    if (family) await page.getByLabel("Market family").selectOption(family);
    if (mode) await page.getByLabel("Data source").selectOption(mode);
    if (idea) await page.getByLabel("Research idea").fill(idea);
    const actualIdea = await page.getByLabel("Research idea").inputValue();
    const responsePromise = page.waitForResponse((r) => r.url() === origin + "/api/jobs" && r.request().method() === "POST");
    await page.getByRole("button", { name: "Start research" }).click();
    const response = await responsePromise; expect(response.status()).toBe(202);
    const { id } = await response.json();
    const run = { label, job_id: id, idea: actualIdea, started_at_utc: started,
      submission: "Playwright form selection, fill and submit on real loopback backend", inspected_tabs: [] };
    receipt.runs.push(run); save();
    await expect(page.locator("#run-header .run-title")).toHaveText(actualIdea);
    return run;
  }

  async function waitCompleted(run) {
    await expect.poll(() => jobs.get(run.job_id)?.status, { timeout: 210_000, intervals: [250, 500, 1500] }).toMatch(/completed|failed|cancelled|interrupted/);
    const job = jobs.get(run.job_id);
    run.status = job.status; run.finished_at_utc = now(); run.events = job.events; save();
    assert.equal(job.status, "completed", job.detail);
    await expect(page.locator("#run-header .badge").first()).toHaveText("completed");
    await expect(page.getByRole("link", { name: "Review JSON", exact: true })).toBeVisible();
    run.review = job.result;
    completed.push(run);
    write(`${run.label}-job.json`, job);
    save(); return job.result;
  }

  async function download(run, suffix = "") {
    fs.mkdirSync(path.join(evidence, "downloads"), { recursive: true });
    const retainedPath = path.join(workspace, "runs", run.job_id, "review.json");
    const retained = JSON.parse(fs.readFileSync(retainedPath, "utf8"));
    const outputs = {};
    for (const [link, extension] of [["Review JSON", "json"], ["Text report", "txt"]]) {
      const pending = page.waitForEvent("download");
      await page.getByRole("link", { name: link, exact: true }).click();
      const file = await pending;
      assert.equal(await file.failure(), null);
      assert.equal(file.suggestedFilename(), `entropytrade-${run.job_id}.${extension}`);
      const relative = `downloads/${run.label}${suffix}-${file.suggestedFilename()}`;
      await file.saveAs(path.join(evidence, relative));
      const bytes = fs.readFileSync(path.join(evidence, relative));
      if (extension === "json") assert.deepEqual(JSON.parse(bytes), retained);
      else assert.deepEqual(bytes, Buffer.from(retained.report));
      const record = { at_utc: now(), job_id: run.job_id, file: relative, suggested_filename: file.suggestedFilename(),
        bytes: bytes.length, sha256: sha(bytes), retained_review: path.relative(repo, retainedPath),
        comparison: extension === "json" ? "parsed JSON equals retained review" : "bytes equal retained review.report" };
      receipt.downloads.push(record); outputs[extension] = record;
    }
    if (suffix) {
      assert.deepEqual(outputs.json.sha256, run.downloads.json.sha256);
      assert.deepEqual(outputs.txt.sha256, run.downloads.txt.sha256);
      run.restart_downloads_identical = true;
    } else run.downloads = outputs;
    save(); return retained;
  }

  async function tab(run, name) {
    const button = page.getByRole("button", { name, exact: true });
    await button.click(); await expect(button).toHaveAttribute("aria-pressed", "true");
    await expect(page.locator("#result-content > .notice").first()).toContainText("Final holdout is excluded.");
    if (run.review.data_kind === "synthetic") {
      await expect(page.locator("#result-content > .notice").first()).toContainText("SYNTHETIC SOFTWARE DEMONSTRATION.");
    }
    run.inspected_tabs.push({ name, at_utc: now() }); save();
  }

  async function details(summary) {
    const item = page.locator("#result-content details").filter({ has: page.getByText(summary, { exact: true }) }).first();
    await item.locator("summary").click();
    await expect(item).toHaveAttribute("open", "");
    return item.locator("pre");
  }

  async function verifyArtifacts(run) {
    const root = path.join(workspace, "runs", run.job_id);
    for (const artifact of run.review.artifacts) {
      const bytes = fs.readFileSync(path.join(root, "workflow", artifact.path));
      assert.equal(`sha256:${sha(bytes)}`, artifact.sha256); assert.equal(bytes.length, artifact.bytes);
    }
    // Preserve the real raw acquisition, manifests and workflow files, not just screenshots.
    fs.cpSync(root, path.join(evidence, "runs", run.label), { recursive: true,
      filter: (source) => !source.split(path.sep).includes("mlflow") });
    run.artifact_hashes_verified = run.review.artifacts.length; save();
  }

  async function workflow(number, title, fn) {
    const record = { number, title, started_at_utc: now(), outcome: "running" };
    receipt.workflows.push(record); save();
    await test.step(`${number}. ${title}`, async () => {
      try { await fn(); record.outcome = "passed"; }
      catch (error) {
        record.outcome = "failed"; record.error = error.stack;
        failures.push(`${number}. ${title}: ${error.message}`);
        await screenshot(`workflow-${number}-failure`).catch(() => {});
      } finally { record.finished_at_utc = now(); save(); }
    });
  }

  async function publicFamily(family, { expectedFailure = false } = {}) {
    const label = `public-${family}${expectedFailure ? "-network-denied" : ""}`;
    const run = await submit(label, { example: family === "bitcoin" ? "Bitcoin" : "Weather", mode: "public",
      idea: expectedFailure ? "Bitcoin spot acquisition under deliberate OS network denial" : undefined });
    const review = await waitCompleted(run);
    assert.equal(review.final_holdout_evaluated, false);
    assert.equal(review.probability_count, 0); assert.equal(review.probabilities.length, 0);
    assert.equal(review.coverage.scalar_label_events, 0);
    assert(review.candidates.every((c) => c.forecast_metrics === null && c.scenarios.length === 0));
    const a = review.acquisition, capture = review.public_evidence.capture;
    assert.equal(a.receipt_count, capture.receipts.length);
    assert.equal(a.successful_response_count, capture.receipts.filter((r) => r.status >= 200 && r.status < 300).length);
    assert.equal(a.listed_contracts, capture.listed_contracts);
    assert.equal(a.observations, capture.observations);
    assert.equal(a.failure_count, capture.failures.length);
    run.acquisition = a;
    run.successful_ingestion = a.successful_response_count > 0 && a.listed_contracts > 0 && a.observations > 0;
    run.complete_capture = a.status === "complete";
    for (const name of ["Review", "Probabilities", "Evidence & lineage"]) {
      await tab(run, name);
      const section = page.locator("#result-content .acquisition");
      await expect(section.getByRole("heading", { name: a.headline, exact: true })).toBeVisible();
      await expect(section.locator(".acquisition-counts")).toHaveText(a.counts);
      for (const failure of a.failure_summaries) await expect(section.getByText(failure, { exact: true })).toBeVisible();
      expect(await section.locator("details").count()).toBe(0);
      await expect(section).toContainText(a.started_at); await expect(section).toContainText(a.decision_time);
      if (a.status !== "complete") await expect(section).toHaveClass(/incomplete|empty/);
      if (name === "Probabilities") await expect(page.getByText(/No eligible fitted probability records exist/)).toBeVisible();
      if (name === "Evidence & lineage") {
        const pre = await details("Capture receipts, clocks and acquisition failures");
        assert.deepEqual(JSON.parse(await pre.innerText()), capture);
        for (const receipt of capture.receipts) {
          assert(Date.parse(receipt.received_at) <= Date.parse(capture.decision_time));
        }
        const contract = review.public_evidence.contracts[0];
        if (contract) {
          const contractPre = await details(`${contract.ticker} · actual rules and available features`);
          assert.deepEqual(JSON.parse(await contractPre.innerText()), contract);
          assert(Date.parse(contract.available_at) <= Date.parse(capture.decision_time));
          assert(contract.rules_primary || contract.rules_secondary);
        }
        if (family === "bitcoin") {
          await expect(page.getByText("Bitcoin settlement sources remain unresolved and rules_known is false. Authority mentions preserve rule text; they do not verify settlement authority.", { exact: true })).toBeVisible();
          for (const c of review.public_evidence.contracts) {
            assert.equal(c.rules_known, false); assert.equal(c.settlement_basis, "unresolved");
            assert.deepEqual(c.settlement_sources, []);
            for (const mention of c.authority_mentions) assert.equal(mention.status, "unverified_mention");
          }
          run.authority_mentions = review.public_evidence.contracts.reduce((n, c) => n + c.authority_mentions.length, 0);
        }
      }
      fs.mkdirSync(path.join(evidence, "dom"), { recursive: true });
      fs.writeFileSync(path.join(evidence, "dom", `${run.label}-${name.split(" ")[0].toLowerCase()}.txt`), await page.locator("#result-content").innerText());
      await screenshot(`${run.label}-${name.split(" ")[0].toLowerCase()}`);
    }
    const exported = await download(run);
    for (const text of [a.headline, a.counts, a.started_at, a.decision_time, a.evaluation_limit,
      ...a.failure_summaries, ...a.limitations]) assert(exported.report.includes(text), text);
    await verifyArtifacts(run);
    if (expectedFailure) {
      assert.equal(a.status, "incomplete"); assert(a.failure_count > 0);
      assert.equal(a.successful_response_count, 0); assert.equal(a.receipt_count, 0);
      assert.equal(a.listed_contracts, 0); assert.equal(a.observations, 0);
      for (const failure of capture.failures) assert(Number.isFinite(Date.parse(failure.failed_at)));
      run.expected_failure_path = true;
    } else if (!run.successful_ingestion || !run.complete_capture) {
      receipt.acceptance_gaps.push({ family, job_id: run.job_id, successful_ingestion: run.successful_ingestion,
        complete_capture: run.complete_capture, acquisition: a, reason: "Fresh public capture did not meet complete successful-ingestion acceptance" });
    }
    save();
  }

  try {
    await startServer(); await load(); await screenshot("initial-workbench");
    await workflow(1, "recorded weather, typed specification and protected downloads", async () => {
      const run = await submit("recorded-weather", { example: "Weather", mode: "recorded", idea: "revision_f >= 1.25 and hours_to_close < 8" });
      const review = await waitCompleted(run);
      assert.equal(review.data_kind, "real"); assert.equal(review.final_holdout_evaluated, false);
      assert.equal(review.coverage.eligible_events, 0); assert.equal(review.coverage.scalar_label_events, 0);
      assert(review.candidates.every((c) => c.status === "INSUFFICIENT_DATA" && c.forecast_metrics === null && c.scenarios.length === 0));
      await tab(run, "Review");
      const spec = JSON.parse(await (await details("Strategy specification")).innerText());
      const specText = JSON.stringify(spec);
      for (const value of ["revision_f", "1.25", "hours_to_close", "8"]) assert(specText.includes(value));
      await expect(page.locator("#result-content .candidate .badge").first()).toHaveText("INSUFFICIENT DATA");
      await screenshot("recorded-weather-review-specification");
      await tab(run, "Probabilities");
      assert.equal(review.probability_count, 0); assert.deepEqual(review.probabilities, []);
      await expect(page.getByText(/No eligible fitted probability records exist/)).toBeVisible();
      await screenshot("recorded-weather-probabilities");
      await tab(run, "Evidence & lineage");
      await expect(page.getByText(/Final holdout evaluated: false/)).toBeVisible();
      await details("Coverage and point-in-time boundaries"); await screenshot("recorded-weather-lineage");
      await download(run); await verifyArtifacts(run);
    });
    await workflow(2, "synthetic modeling, gates, scenarios and validation probabilities", async () => {
      const run = await submit("synthetic-weather", { example: "Software demo" });
      const review = await waitCompleted(run);
      assert.equal(review.data_kind, "synthetic"); assert.equal(review.final_holdout_evaluated, false);
      const control = review.candidates.find((c) => c.candidate_id === "negative-control");
      assert.equal(control.scenarios.length, 3); assert(control.scenarios.every((s) => s.fill_count === 0));
      await tab(run, "Review");
      const gates = await details("Independent research gates and criticism");
      assert.deepEqual(JSON.parse(await gates.innerText()), review.decisions[0]);
      const negative = page.locator("article.candidate").last();
      expect(await negative.locator("tbody tr").count()).toBe(3);
      for (const row of await negative.locator("tbody tr").all()) await expect(row.locator("td").nth(1)).toHaveText("0");
      await screenshot("synthetic-weather-review-gates-scenarios");
      await tab(run, "Probabilities");
      assert(review.probability_count > 0); assert.equal(review.probabilities.length, Math.min(100, review.probability_count));
      assert(review.probabilities.every((p) => p.split === "validation" && Date.parse(p.fit_asof) <= Date.parse(p.decision_time) &&
        (p.calibration_asof === null || Date.parse(p.calibration_asof) <= Date.parse(p.decision_time))));
      run.probability_clocks = { validation_only: true, fit_before_decision: true,
        calibration_before_decision_when_present: true,
        null_calibration_records: review.probabilities.filter((p) => p.calibration_asof === null).length };
      expect(await page.locator("#result-content tbody tr").count()).toBe(review.probabilities.length);
      await expect(page.getByText(`Showing ${review.probabilities.length} of ${review.probability_count} permitted prediction records (limit 100). Only validation probabilities used by the experiment are exposed.`, { exact: true })).toBeVisible();
      await screenshot("synthetic-weather-probabilities");
      await tab(run, "Evidence & lineage");
      await expect(page.getByText(/Final holdout evaluated: false/)).toBeVisible();
      await screenshot("synthetic-weather-lineage");
      await download(run); await verifyArtifacts(run);
    });
    await workflow(3, "fresh public weather and Bitcoin acquisition through all result tabs", async () => {
      // Finish both families even if one has an assertion failure; preserve its exact error.
      const errors = [];
      for (const family of ["weather", "bitcoin"]) {
        try { await publicFamily(family); }
        catch (error) { errors.push(`${family}: ${error.stack}`); }
      }
      assert.deepEqual(errors, []);
      assert.deepEqual(receipt.acceptance_gaps, []);
      if (process.env.ENTROPYTRADE_BROWSER_DENY_PUBLIC === "1") {
        await stopServer("controlled failure-path browser test; deny backend public network at the OS boundary");
        try {
          await startServer({ denyPublic: true }); await load();
          await publicFamily("bitcoin", { expectedFailure: true });
        } finally {
          await stopServer("restore ordinary public-network access after failure-path test");
          await startServer(); await load();
        }
      } else {
        receipt.failure_path = "Not executed; set ENTROPYTRADE_BROWSER_DENY_PUBLIC=1 on macOS to exercise actual OS-denied acquisition";
        save();
      }
    });
    await workflow(4, "active cancellation, slot reuse, interrupted restart and persistent downloads", async () => {
      const cancelled = await submit("cancelled-synthetic", { example: "Software demo", idea: "Synthetic cancellation browser acceptance" });
      await expect.poll(() => jobs.get(cancelled.job_id)?.status, { timeout: 20_000 }).toBe("running");
      cancelled.status_before_cancel = jobs.get(cancelled.job_id).status; cancelled.cancel_requested_at_utc = now(); save();
      await screenshot("synthetic-active-before-cancel");
      const response = page.waitForResponse((r) => r.url().endsWith(`/${cancelled.job_id}/cancel`) && r.request().method() === "POST");
      await page.getByRole("button", { name: "Cancel run", exact: true }).click();
      assert.equal((await (await response).json()).cancelled, true);
      await expect(page.locator("#run-header .badge").first()).toHaveText("cancelled");
      await expect(page.getByText(/No completed review is available/)).toBeVisible();
      cancelled.status = "cancelled"; cancelled.finished_at_utc = now(); save();
      await screenshot("synthetic-terminal-cancelled");
      const reuse = await submit("recorded-after-cancel", { example: "Weather", mode: "recorded", idea: "Test revision_f >= 1.25 and hours_to_close < 8" });
      await waitCompleted(reuse); await download(reuse); await verifyArtifacts(reuse);
      const active = await submit("interrupted-synthetic", { example: "Software demo", idea: "Synthetic restart interruption browser acceptance" });
      await expect.poll(() => jobs.get(active.job_id)?.status, { timeout: 20_000 }).toBe("running");
      active.status_before_shutdown = jobs.get(active.job_id).status; save();
      await screenshot("synthetic-active-before-shutdown");
      await stopServer("documented shutdown during active synthetic run");
      await startServer(); await load();
      const history = page.locator("#history .history-item");
      await history.filter({ has: page.getByText(active.idea, { exact: true }) }).click();
      await expect(page.locator("#run-header .badge").first()).toHaveText("interrupted");
      active.status = "interrupted"; active.finished_at_utc = now();
      write("interrupted-job.json", jobs.get(active.job_id)); save();
      await screenshot("restart-interrupted-history");
      await history.filter({ has: page.getByText(cancelled.idea, { exact: true }) }).click();
      await expect(page.locator("#run-header .badge").first()).toHaveText("cancelled");
      write("cancelled-job-after-restart.json", jobs.get(cancelled.job_id));
      for (const run of completed) {
        await history.filter({ has: page.getByText(run.idea, { exact: true }) }).click();
        await expect(page.locator("#run-header .badge").first()).toHaveText("completed");
        await expect(page.locator("#run-header .run-title")).toHaveText(run.idea);
        await download(run, "-after-restart"); await screenshot(`${run.label}-reopened-after-restart`);
      }
      receipt.lifecycle.push({ action: "browser_restart_verified", at_utc: now(),
        interrupted_job_id: active.job_id, cancelled_job_id: cancelled.job_id,
        completed_job_ids: completed.map((r) => r.job_id), all_downloads_identical: true }); save();
    });
  } finally {
    await stopServer("acceptance harness cleanup").catch((error) => failures.push(error.message));
    receipt.finished_at_utc = now();
    receipt.outcome = failures.length ? "failed" : "passed";
    receipt.failures = failures;
    // Full reviews are saved separately and in actual browser downloads.
    for (const run of receipt.runs) delete run.review;
    save();
    await info.attach("browser-receipt", { path: path.join(evidence, "browser-receipt.json"), contentType: "application/json" });
  }
  expect(receipt.page_errors).toEqual([]);
  expect(failures).toEqual([]);
});
