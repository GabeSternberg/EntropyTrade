"use strict";
// Redesigned shell: real localhost listener, managed Chromium, Real/Demo modes, navigation,
// interactions, responsive layout, demo isolation and rendered screenshots.
const { test, expect, chromium } = require("@playwright/test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { spawn } = require("node:child_process");

const SECTIONS = [
  ["overview", "Overview"], ["markets", "Market Explorer"], ["lab", "Strategy Lab"], ["analytics", "Backtesting & Analytics"],
  ["paper", "Paper Trading"], ["workbench", "Research Workbench"], ["ops", "Data & Operations"], ["settings", "Settings"],
];

test("redesigned shell: real and demo modes, interactions, isolation and responsive layout", async ({ page, browser }) => {
  const repo = path.resolve(__dirname, "../..");
  const evidence = path.join(process.env.ENTROPYTRADE_BROWSER_EVIDENCE, "redesign");
  const workspace = process.env.ENTROPYTRADE_BROWSER_WORKSPACE + "-redesign";
  const python = process.env.ENTROPYTRADE_BROWSER_PYTHON || path.join(repo, ".venv/bin/python");
  const origin = `http://127.0.0.1:${Number(process.env.ENTROPYTRADE_BROWSER_PORT || 43160)}`;
  assert(path.isAbsolute(workspace) && workspace.startsWith(path.join(repo, "data/cache/")));
  assert(!fs.existsSync(workspace), "workspace must be new");
  assert(chromium.executablePath().startsWith(path.join(__dirname, ".browsers/")));
  fs.mkdirSync(evidence, { recursive: true });
  const env = { PATH: "/usr/bin:/bin", TZ: "UTC", PYTHONNOUSERSITE: "1", PYTHONDONTWRITEBYTECODE: "1", PYTHONPATH: `${repo}/backend:${repo}/backend/src` };
  const receipt = { status: "running", browser: browser.version(), screenshots: [], page_errors: [], console_errors: [], demo_requests: [], submission_enabled: false };
  const save = () => fs.writeFileSync(path.join(evidence, "receipt.json"), JSON.stringify(receipt, null, 2));
  const pause = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
  page.on("pageerror", (error) => { receipt.page_errors.push(error.message); save(); });
  page.on("console", (message) => { if (message.type() === "error") { receipt.console_errors.push(message.text()); save(); } });
  async function shot(file, fullPage = false) { await expect(page.locator(".toast")).toHaveCount(0, { timeout: 8000 }); if (!file.includes("detail")) await page.evaluate(() => window.scrollTo(0, 0)); await page.screenshot({ path: path.join(evidence, file), fullPage }); receipt.screenshots.push(file); save(); }
  async function go(key) { await page.locator(`.nav-item[data-key="${key}"]`).click(); await expect(page.locator(key === "workbench" ? "#workbench-title" : ".page-head h1").first()).toBeVisible(); }
  const log = fs.openSync(path.join(evidence, "server.log"), "a");
  assert(!await fetch(origin + "/api/catalog").catch(() => null), "Port occupied");
  const server = spawn(python, ["-m", "entropytrade.api.server", "--workspace", workspace, "--port", origin.split(":").at(-1)], { cwd: repo, env, stdio: ["ignore", log, log] });
  fs.closeSync(log);
  save();
  try {
    for (let n = 0; n < 100; n++) {
      if (server.exitCode !== null) throw new Error(`Listener exited ${server.exitCode}`);
      if ((await fetch(origin + "/api/catalog").catch(() => null))?.ok) break;
      await pause(100);
    }
    await page.setViewportSize({ width: 1440, height: 900 });

    // ---- Real Mode: honest empty and unavailable states from the actual local API.
    await page.goto(origin);
    await expect(page.locator("body")).toHaveClass(/mode-real/);
    await expect(page.locator("#mode-banner")).toBeHidden();
    await expect(page.getByRole("heading", { name: "Overview", level: 1 })).toBeVisible();
    const view = page.locator("#view");
    await expect(view.getByText("Real data · local workspace")).toBeVisible();
    await expect(view.getByText("No research runs yet")).toBeVisible();
    await expect(view.getByText("No live market feed in the website")).toBeVisible();
    await expect(view.getByText(/of 8 gates are not attested/)).toBeVisible();
    await shot("real-overview.png");
    for (const [key, title] of SECTIONS) {
      await go(key);
      await expect(page).toHaveTitle(new RegExp(`${key === "analytics" ? "Backtesting" : title.replace("&", "&")} · EntropyTrade`));
    }
    await go("paper");
    await expect(view.getByText("No simulated paper accounts in this workspace")).toBeVisible();
    await expect(page.getByRole("switch", { name: "Live trading (disabled)" })).toBeDisabled();
    await shot("real-paper.png");
    await go("analytics");
    await expect(view.getByText("No authentic backtest has passed the evidence gates")).toBeVisible();
    await go("ops");
    await expect(view.getByText("Collector status is not exposed to the website")).toBeVisible();
    await shot("real-operations.png");
    // Real "New hypothesis" hands off to the workbench with the idea prefilled; nothing is submitted.
    await go("lab");
    await page.getByRole("button", { name: "New hypothesis" }).click();
    await page.getByRole("dialog").getByRole("textbox", { name: "Hypothesis" }).fill("revision_f >= 1.25 and hours_to_close < 8");
    await page.getByRole("button", { name: "Continue in workbench" }).click();
    await expect(page.locator("#workbench-view")).toBeVisible();
    await expect(page.getByLabel("Research idea", { exact: true })).toHaveValue("revision_f >= 1.25 and hours_to_close < 8");
    await expect(page.locator("#submit")).toBeEnabled();
    await expect(page.locator("#history")).toContainText("Your research history will appear here.");
    await shot("real-workbench.png");

    // ---- Demo Mode: clearly labeled, browser-only sample data; no writes leave the page.
    const writes = [];
    page.on("request", (request) => {
      if (request.method() !== "GET" || /demo/i.test(request.url())) writes.push(`${request.method()} ${request.url()}`);
      if (request.url().includes("/api/")) receipt.demo_requests.push(request.url());
    });
    await go("overview");
    await page.getByRole("group", { name: "Data mode" }).getByRole("button", { name: "Demo" }).click();
    await expect(page.locator("body")).toHaveClass(/mode-demo/);
    await expect(page.locator("#mode-banner")).toBeVisible();
    await expect(page.locator("#mode-banner")).toContainText("fictional sample data");
    await expect(view.getByText("Demo data · simulated")).toBeVisible();
    await expect(page.locator(".kpi-label", { hasText: "Paper equity" })).toBeVisible();
    await expect(page.locator(".chart .watermark").first()).toHaveText("SIMULATED");
    await page.getByRole("group", { name: "Equity range" }).getByRole("button", { name: "1W", exact: true }).click();
    await shot("demo-overview.png");

    await go("markets");
    const count = page.locator(".results-title");
    await expect(count).toContainText(/of 54 markets/);
    const before = await count.textContent();
    await page.getByRole("searchbox", { name: "Search markets" }).fill("bitcoin");
    await expect(count).not.toHaveText(before);
    await expect(page.locator(".data-table tbody tr")).toHaveCount(5);
    await page.getByRole("searchbox", { name: "Search markets" }).fill("");
    await page.getByRole("group", { name: "Market status" }).getByRole("button", { name: "Settled", exact: true }).click();
    await expect(count).toContainText("3 of 54");
    await page.getByRole("group", { name: "Market status" }).getByRole("button", { name: "Open", exact: true }).click();
    await page.getByRole("button", { name: "Model edge", exact: true }).click();
    await expect(page.locator('th[aria-sort]')).toHaveCount(1);
    await shot("demo-markets.png");
    await page.locator(".data-table tbody tr").first().click();
    await expect(page.getByRole("heading", { name: "Order book" })).toBeVisible();
    await page.getByRole("group", { name: "Chart range" }).getByRole("button", { name: "24H", exact: true }).click();
    await expect(page.getByRole("button", { name: "Trade (disabled)" })).toBeDisabled();
    await page.locator(".chart-host svg").first().hover();
    await expect(page.locator(".chart-tip").first()).toBeVisible();
    await shot("demo-market-detail.png");

    await go("lab");
    await page.getByRole("tab", { name: /Experiments/ }).click();
    await page.locator(".data-table tbody tr").first().click();
    await expect(page.getByRole("dialog")).toContainText("Evidence");
    await page.getByRole("dialog").getByRole("button", { name: "Close", exact: true }).click();
    await page.getByRole("tab", { name: /Model comparison/ }).click();
    await expect(page.getByLabel("Calibration reliability diagram")).toBeVisible();
    await page.getByRole("tab", { name: /Strategies/ }).click();
    await page.getByRole("button", { name: "New hypothesis" }).click();
    await page.getByRole("dialog").getByRole("textbox", { name: "Hypothesis" }).fill("Test spread compression near close");
    await page.getByRole("button", { name: "Create simulated draft" }).click();
    await expect(view.getByText("session draft")).toBeVisible();
    await shot("demo-strategy-lab.png");
    await view.locator(".data-table tbody tr", { hasText: "Forecast revision drift" }).click();
    await expect(page.getByRole("heading", { name: "Forecast revision drift", level: 1 })).toBeVisible();
    await expect(page.getByRole("button", { name: "Request promotion" })).toBeDisabled();
    await shot("demo-strategy-detail.png");

    await go("analytics");
    for (const tab of ["Risk & drawdown", "Calibration", "Fees & slippage", "Walk-forward & data", "Performance"]) {
      await page.getByRole("tab", { name: tab }).click();
      await expect(page.getByRole("tab", { name: tab })).toHaveAttribute("aria-selected", "true");
      if (tab === "Fees & slippage") await shot("demo-analytics-costs.png");
    }
    await shot("demo-analytics.png");

    await go("paper");
    await page.getByRole("tab", { name: /Fills/ }).click();
    await page.getByRole("tab", { name: /Orders/ }).click();
    await page.locator(".data-table tbody tr", { hasText: "rejected" }).first().click();
    await expect(page.getByRole("dialog")).toContainText("max_event_exposure");
    await page.getByRole("dialog").getByRole("button", { name: "Close", exact: true }).click();
    await expect(page.getByRole("button", { name: "Place order" })).toBeDisabled();
    await shot("demo-paper.png");

    await go("ops");
    await expect(view.getByText("Data-quality alerts")).toBeVisible();
    await shot("demo-operations.png");
    await go("settings");
    await page.getByRole("link", { name: "Risk & approvals" }).click();
    await expect(page.getByRole("heading", { name: "V1 acceptance gates" })).toBeVisible();
    await shot("demo-settings.png");

    // The workbench stays real in Demo Mode.
    await go("workbench");
    await expect(page.getByText("Research only · execution disabled", { exact: true })).toBeVisible();
    await expect(page.locator("#submit")).toBeEnabled();

    // Command palette.
    await page.keyboard.press("Control+k");
    await page.getByRole("searchbox", { name: "Search" }).fill("Paper");
    await page.keyboard.press("Enter");
    await expect(page.getByRole("heading", { name: "Paper Trading", level: 1 })).toBeVisible();

    // ---- Responsive: no horizontal page overflow; off-canvas navigation works.
    await page.setViewportSize({ width: 375, height: 812 });
    for (const [key] of SECTIONS) {
      await page.goto(`${origin}/#/${key}`);
      await expect(page.locator(key === "workbench" ? "#workbench-title" : ".page-head h1").first()).toBeVisible();
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
      assert.ok(overflow <= 1, `${key} overflows horizontally by ${overflow}px`);
    }
    await page.getByRole("button", { name: "Open navigation" }).click();
    await expect(page.locator(".nav-item[data-key=markets]")).toBeVisible();
    await page.locator(".nav-item[data-key=markets]").click();
    await expect(page.getByRole("heading", { name: "Market Explorer", level: 1 })).toBeVisible();
    await expect(page.locator("body")).not.toHaveClass(/nav-open/);
    await pause(400); // let the off-canvas navigation finish sliding closed
    await shot("demo-mobile-markets.png");
    await page.setViewportSize({ width: 768, height: 1024 });
    await page.goto(`${origin}/#/overview`);
    await shot("demo-tablet-overview.png");

    // Back to Real Mode: demo figures disappear.
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.getByRole("button", { name: "Switch to Real Mode" }).click();
    await expect(page.locator("#mode-banner")).toBeHidden();
    await expect(view.getByText("$10,784.00")).toHaveCount(0);

    assert.deepEqual(writes, [], "Demo Mode must not send writes or demo data");
    assert.deepEqual(receipt.page_errors, []);
    assert.deepEqual(receipt.console_errors, []);
    receipt.status = "passed"; save();
  } catch (error) {
    receipt.status = "failed"; receipt.error = String(error.stack || error); save();
    await page.screenshot({ path: path.join(evidence, "failure.png"), fullPage: true }).catch(() => {});
    throw error;
  } finally {
    server.kill("SIGINT");
    for (let n = 0; n < 100 && server.exitCode === null && server.signalCode === null; n++) await pause(100);
    if (server.exitCode === null && server.signalCode === null) server.kill("SIGKILL");
  }
});
