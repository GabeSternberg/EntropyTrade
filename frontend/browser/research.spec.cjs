"use strict";
// Autonomous research: real localhost listener and managed Chromium. Real Mode submits an
// inventory-only job (no network acquisition) and follows it to evaluation; Demo Mode shows
// the labeled sample job without touching the research API.
const { test, expect, chromium } = require("@playwright/test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { spawn } = require("node:child_process");

test("autonomous research: submit, follow, inspect, export, cancel and demo isolation", async ({ page, browser }) => {
  const repo = path.resolve(__dirname, "../..");
  const evidence = path.join(process.env.ENTROPYTRADE_BROWSER_EVIDENCE, "research");
  const workspace = process.env.ENTROPYTRADE_BROWSER_WORKSPACE + "-research";
  const python = process.env.ENTROPYTRADE_BROWSER_PYTHON || path.join(repo, ".venv/bin/python");
  const origin = `http://127.0.0.1:${Number(process.env.ENTROPYTRADE_BROWSER_PORT || 43165)}`;
  assert(path.isAbsolute(workspace) && workspace.startsWith(path.join(repo, "data/cache/")));
  assert(!fs.existsSync(workspace), "workspace must be new");
  assert(chromium.executablePath().startsWith(path.join(__dirname, ".browsers/")));
  fs.mkdirSync(evidence, { recursive: true });
  const env = { PATH: "/usr/bin:/bin", TZ: "UTC", PYTHONNOUSERSITE: "1", PYTHONDONTWRITEBYTECODE: "1", PYTHONPATH: `${repo}/backend:${repo}/backend/src` };
  const receipt = { status: "running", browser: browser.version(), screenshots: [], page_errors: [], console_errors: [], demo_requests: [], posts: [] };
  const save = () => fs.writeFileSync(path.join(evidence, "receipt.json"), JSON.stringify(receipt, null, 2));
  const pause = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
  page.on("pageerror", (error) => { receipt.page_errors.push(error.message); save(); });
  page.on("console", (message) => { if (message.type() === "error") { receipt.console_errors.push(message.text()); save(); } });
  page.on("request", (request) => { if (request.method() === "POST") receipt.posts.push(new URL(request.url()).pathname); });
  async function shot(file, fullPage = false) { await page.screenshot({ path: path.join(evidence, file), fullPage }); receipt.screenshots.push(file); save(); }
  const log = fs.openSync(path.join(evidence, "server.log"), "a");
  assert(!await fetch(origin + "/api/catalog").catch(() => null), "Port occupied");
  const server = spawn(python, ["-m", "entropytrade.api.server", "--workspace", workspace, "--port", origin.split(":").at(-1)], { cwd: repo, env, stdio: ["ignore", log, log] });
  fs.closeSync(log);
  save();
  try {
    for (let n = 0; n < 100; n++) {
      if (server.exitCode !== null) throw new Error(`Listener exited ${server.exitCode}`);
      if ((await fetch(origin + "/api/research").catch(() => null))?.ok) break;
      await pause(100);
    }
    await page.setViewportSize({ width: 1440, height: 1000 });
    await page.goto(origin + "/#/research");
    const view = page.locator("#view");
    await expect(page.getByRole("heading", { name: "Autonomous Research", level: 1 })).toBeVisible();
    await expect(view.getByText("No research jobs yet")).toBeVisible();
    await expect(view.getByText("Order submission")).toBeVisible();
    await expect(page.locator("#research-provider option[value=gemini]")).toHaveAttribute("disabled", "");
    await shot("research-real-empty.png");

    // Submit an inventory-only job; acquisition is never attempted.
    await page.locator("#research-objective").fill("Find profitable strategies for Kalshi daily temperature markets using weather forecasts.");
    await page.locator("#research-acquisition").selectOption("none");
    await page.getByRole("button", { name: "Start research" }).click();
    await expect(page).toHaveURL(/#\/research\/[0-9a-f-]{36}$/);
    await expect(page.locator("#research-detail")).toContainText("Awaiting prospective evidence", { timeout: 30_000 });
    await expect(page.locator(".hyp-card")).toHaveCount(5);
    await expect(page.locator(".hyp-card").first()).toContainText("NWS forecast bias against the settlement high");
    await expect(page.locator(".hyp-card [data-status=backtest_eligible]")).toHaveCount(0);
    // Inventory-only: acquisition and features never ran, and the stepper must say so.
    await expect(page.locator("[data-step=acquiring_data]")).toHaveAttribute("data-state", "skipped");
    await expect(page.locator("[data-step=planning_data]")).toHaveAttribute("data-state", "done");
    await expect(page.locator("[data-step=registering_features]")).toHaveAttribute("data-state", "done");
    await expect(view.getByText(/Research eligibility only/)).toBeVisible();
    await shot("research-real-detail.png", true);
    await page.getByRole("tab", { name: /Data requirements/ }).click();
    await expect(view.locator(".data-table tbody tr")).toHaveCount(10);
    await expect(view.getByText("Forecast Vintages").first()).toBeVisible();
    await shot("research-real-requirements.png");
    await page.getByRole("tab", { name: /Forward collection/ }).click();
    await expect(view.getByText(/configs\/data\/collector.json captures KXHIGHPHIL/)).toBeVisible();
    await expect(view.locator("[data-status=blocked_collector_change]").first()).toBeVisible();
    await shot("research-real-forward.png");
    const href = await page.locator("#research-export").getAttribute("href");
    const report = await (await fetch(origin + href, { headers: { Host: new URL(origin).host } })).json();
    assert.equal(report.schema, "entropytrade-research-report-v1");
    assert.equal(report.job.hypotheses.length, 5);
    await page.locator("#research-resume").click();
    await expect(page.locator("#research-detail")).toContainText("Awaiting prospective evidence", { timeout: 30_000 });
    await page.locator("#research-cancel").click();
    await expect(page.locator(".research-status-row [data-status=cancelled]")).toBeVisible();
    // Reload: the job survives and is listed.
    await page.goto("about:blank");
    await page.goto(origin + "/#/research");
    await expect(view.locator(".data-table tbody tr")).toHaveCount(1);
    await expect(view.locator(".data-table tbody tr [data-status=cancelled]")).toBeVisible();
    await shot("research-real-list.png");

    // Narrow layout: no horizontal page overflow on the detail page.
    await page.locator(".data-table tbody tr").first().click();
    await expect(page.locator(".hyp-card")).toHaveCount(5);
    await page.setViewportSize({ width: 375, height: 900 });
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    assert(overflow <= 1, `horizontal overflow ${overflow}px`);
    await shot("research-mobile-detail.png");
    await page.setViewportSize({ width: 1440, height: 1000 });

    // Demo Mode: labeled sample job, and no research API traffic.
    const postsBefore = receipt.posts.length;
    page.on("request", (request) => { if (new URL(request.url()).pathname.startsWith("/api/research")) { receipt.demo_requests.push(request.url()); save(); } });
    await page.getByRole("group", { name: "Data mode" }).getByRole("button", { name: "Demo" }).click();
    await page.goto(origin + "/#/research");
    await expect(view.getByText(/Demo Mode: these research jobs are fictional examples/)).toBeVisible();
    await view.locator(".data-table tbody tr").first().click();
    await expect(view.getByText(/Demo Mode: this research job is a fictional example/)).toBeVisible();
    await page.getByRole("tab", { name: /Forward collection/ }).click();
    await expect(view.getByText(/Demo: covered by the canonical collector/)).toBeVisible();
    await shot("research-demo-detail.png");
    assert.deepEqual(receipt.demo_requests, []);
    assert.equal(receipt.posts.length, postsBefore);
    await page.getByRole("group", { name: "Data mode" }).getByRole("button", { name: "Real" }).click();
    assert.deepEqual(receipt.page_errors, []);
    assert.deepEqual(receipt.console_errors, []);
    receipt.status = "passed";
  } finally {
    server.kill("SIGINT");
    await new Promise((resolve) => server.exitCode !== null ? resolve() : server.once("exit", resolve));
    save();
  }
});

test("autonomous research acquisition: ask, approve, acquire, register features and await forward evidence", async ({ page, browser }) => {
  const repo = path.resolve(__dirname, "../..");
  const evidence = path.join(process.env.ENTROPYTRADE_BROWSER_EVIDENCE, "research-acquisition");
  const workspace = process.env.ENTROPYTRADE_BROWSER_WORKSPACE + "-research-acquisition";
  const python = process.env.ENTROPYTRADE_BROWSER_PYTHON || path.join(repo, ".venv/bin/python");
  const origin = `http://127.0.0.1:${Number(process.env.ENTROPYTRADE_BROWSER_PORT || 43165) + 1}`;
  assert(path.isAbsolute(workspace) && workspace.startsWith(path.join(repo, "data/cache/")));
  assert(!fs.existsSync(workspace), "workspace must be new");
  fs.mkdirSync(evidence, { recursive: true });
  const env = { PATH: "/usr/bin:/bin", TZ: "UTC", PYTHONNOUSERSITE: "1", PYTHONDONTWRITEBYTECODE: "1", PYTHONPATH: `${repo}/backend:${repo}/backend/src` };
  const receipt = { status: "running", browser: browser.version(), screenshots: [], page_errors: [], console_errors: [], transport: "controlled_replay" };
  const save = () => fs.writeFileSync(path.join(evidence, "receipt.json"), JSON.stringify(receipt, null, 2));
  const pause = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
  page.on("pageerror", (error) => { receipt.page_errors.push(error.message); save(); });
  page.on("console", (message) => { if (message.type() === "error") { receipt.console_errors.push(message.text()); save(); } });
  async function shot(file, fullPage = false) { await page.screenshot({ path: path.join(evidence, file), fullPage }); receipt.screenshots.push(file); save(); }
  const log = fs.openSync(path.join(evidence, "server.log"), "a");
  assert(!await fetch(origin + "/api/catalog").catch(() => null), "Port occupied");
  const server = spawn(python, ["-m", "tests.integration.research_fixture", "--workspace", workspace, "--port", origin.split(":").at(-1)], { cwd: repo, env, stdio: ["ignore", log, log] });
  fs.closeSync(log);
  try {
    for (let n = 0; n < 100; n++) {
      if (server.exitCode !== null) throw new Error(`Listener exited ${server.exitCode}`);
      if ((await fetch(origin + "/api/research").catch(() => null))?.ok) break;
      await pause(100);
    }
    await page.setViewportSize({ width: 1440, height: 1000 });
    await page.goto(origin + "/#/research");
    const view = page.locator("#view");
    await page.locator("#research-objective").fill("Find profitable strategies for Kalshi daily temperature markets using weather forecasts.");
    await page.locator("#research-depth").selectOption("quick");
    await page.locator("#research-lookback").fill("7");
    await page.locator("#research-acquisition").selectOption("ask");
    await page.getByRole("button", { name: "Start research" }).click();
    await expect(page.locator("#research-detail")).toContainText("await your approval", { timeout: 30_000 });
    await expect(view.getByText(/Controlled replay/)).toBeVisible();
    await page.getByRole("tab", { name: /Acquisitions/ }).click();
    await expect(view.locator("[data-status=awaiting_approval]")).toHaveCount(4);
    await shot("acquisition-awaiting-approval.png");
    // Approve three sources and deny one; each decision is a CSRF-protected POST.
    for (const source of ["iem-nws-pfm", "iem-nws-cli", "weather-company-labels"]) {
      await view.locator(`[data-approve="${source}"]`).click();
      await expect(view.locator(`[data-approve="${source}"]`)).toHaveCount(0, { timeout: 15_000 });
      await page.getByRole("tab", { name: /Acquisitions/ }).click();
    }
    await view.locator('[data-deny="kalshi-settled-markets"]').click();
    await expect(page.locator("#research-detail")).toContainText("Awaiting prospective evidence", { timeout: 30_000 });
    await page.getByRole("tab", { name: /Acquisitions/ }).click();
    await expect(view.locator("[data-status=completed]")).toHaveCount(3);
    await expect(view.locator("[data-status=denied]")).toHaveCount(1);
    await shot("acquisition-completed.png");
    await page.getByRole("tab", { name: /^Features/ }).click();
    for (const name of ["nws_pfm_max_f", "nws_pfm_revision_f", "nws_cli_bias_f", "settlement_high_f"]) {
      await expect(view.getByText(name, { exact: true })).toBeVisible();
    }
    await shot("acquisition-features.png");
    await page.getByRole("tab", { name: /^Sources/ }).click();
    await expect(view.getByText("open-meteo-previous-runs").first()).toBeVisible();
    await expect(view.locator("[data-status=reject]").first()).toBeVisible();
    await shot("acquisition-sources.png");
    await page.getByRole("tab", { name: /Hypotheses/ }).click();
    const bias = page.locator(".hyp-card").first();
    await expect(bias).toContainText("NWS forecast bias against the settlement high");
    await expect(bias.locator(".facet").first()).toContainText("3/3");
    await shot("acquisition-hypotheses.png", true);
    const id = new URL(page.url()).hash.split("/").at(-1);
    const job = await (await fetch(`${origin}/api/research/jobs/${id}`)).json();
    assert.equal(job.transport, "controlled_replay");
    assert.equal(job.acquisitions.filter((a) => a.status === "completed").length, 3);
    assert.ok(job.features.find((f) => f.feature_id === "nws_pfm_max_f").non_null > 0);
    assert.deepEqual(receipt.page_errors, []);
    assert.deepEqual(receipt.console_errors, []);
    receipt.status = "passed";
  } finally {
    server.kill("SIGINT");
    await new Promise((resolve) => server.exitCode !== null ? resolve() : server.once("exit", resolve));
    save();
  }
});
