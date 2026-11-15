"use strict";
// Managed Chromium and actual localhost listener/workers. Controlled HTTP is labeled in the page.
const { test, expect } = require("@playwright/test");
const assert = require("node:assert/strict");
const fs = require("node:fs/promises");
const path = require("node:path");
const { spawn } = require("node:child_process");

const repo = path.resolve(__dirname, "../..");
const python = process.env.ENTROPYTRADE_BROWSER_PYTHON || path.join(repo, ".venv/bin/python");
const port = Number(process.env.ENTROPYTRADE_BROWSER_PORT || 43155);
const origin = "http://127.0.0.1:" + port;
const evidence = process.env.ENTROPYTRADE_BROWSER_EVIDENCE;
const fixtureKey = "controlled-gemini-fixture-key";
const pause = ms => new Promise(resolve => setTimeout(resolve, ms));

async function withServer(mode, callback) {
  const base = process.env.ENTROPYTRADE_BROWSER_WORKSPACE;
  assert(base && path.isAbsolute(base));
  const workspace = base + "-cis1990-" + mode;
  assert(workspace.startsWith(path.join(repo, "data/cache/")));
  await fs.mkdir(workspace, { recursive: false });
  assert.equal(await fetch(origin + "/api/catalog").catch(() => null), null, "Use a free listener port");
  const log = await fs.open(path.join(evidence, "cis1990-" + mode + "-server.log"), "w");
  const live = mode === "no-key";
  const command = ["-m", live ? "entropytrade.api.server" : "tests.integration.cis1990_fixture",
    "--workspace", workspace, "--port", String(port)];
  if (mode === "outage") command.push("--outage");
  const env = { PATH: "/usr/bin:/bin", PYTHONNOUSERSITE: "1", PYTHONDONTWRITEBYTECODE: "1",
    OMP_NUM_THREADS: "1", OPENBLAS_NUM_THREADS: "1", TZ: "UTC",
    PYTHONPATH: [path.join(repo, "backend"), path.join(repo, "backend/src")].join(path.delimiter),
    ...(mode === "outage" ? { GEMINI_API_KEY: fixtureKey } : {}) };
  const server = spawn(python, command, { cwd: repo, env, stdio: ["ignore", log.fd, log.fd] });
  const done = new Promise(resolve => server.once("exit", resolve));
  await log.close();
  try {
    await expect.poll(async () => {
      if (server.exitCode !== null) throw new Error("Listener exited " + server.exitCode);
      return (await fetch(origin + "/api/cis1990").catch(() => null))?.status;
    }).toBe(200);
    await callback();
  } finally {
    if (server.exitCode === null && server.signalCode === null) {
      server.kill("SIGINT");
      let timer;
      try {
        await Promise.race([done, new Promise((resolve, reject) => {
          timer = setTimeout(() => { server.kill("SIGKILL"); reject(new Error("Listener shutdown timed out")); }, 7000);
        })]);
      } finally { clearTimeout(timer); }
    }
  }
}

test("CIS 1990 accepts a masked browser key and shows a controlled four-stage run", async ({ page }) => {
  await withServer("controlled", async () => {
    const errors = [];
    page.on("pageerror", error => errors.push(error.message));
    await page.goto(origin);
    await page.getByRole("link", { name: "CIS 1990 Research Demo", exact: true }).click();
    await expect(page.getByRole("heading", { name: "CIS 1990 Research Demo", exact: true })).toBeVisible();
    const run = page.getByRole("button", { name: "Run Philadelphia Weather Research", exact: true });
    const key = page.getByLabel("Gemini API key", { exact: true });
    await expect(run).toBeDisabled();
    await expect(key).toHaveAttribute("type", "password");
    await key.fill(fixtureKey);
    await page.getByRole("button", { name: "Show key", exact: true }).click();
    await expect(key).toHaveAttribute("type", "text");
    await expect(key).toHaveValue(fixtureKey);
    await page.getByRole("button", { name: "Hide key", exact: true }).click();
    await expect(key).toHaveAttribute("type", "password");
    await page.getByRole("button", { name: "Show key", exact: true }).click();
    await expect(run).toBeEnabled();
    await run.click();
    await expect(key).toHaveAttribute("type", "password");
    await expect(key).toHaveValue("");
    await expect(page.locator("#course-stage-research [data-status]")).toHaveText("running");
    await expect(run).toBeDisabled();
    await expect(page.getByText("Controlled HTTP test run. Sources and model responses are fixture data.")).toBeVisible();
    for (const role of ["research", "hypothesis", "quant", "critic"]) {
      await expect(page.locator("#course-stage-" + role + " [data-status]")).toHaveText("completed");
    }
    await expect(page.getByRole("heading", { name: "Controlled source evidence" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Live source evidence" })).toHaveCount(0);
    await expect(page.locator('[data-view="cis1990"]').getByText("Real data · local workspace", { exact: true })).toHaveCount(0);
    await page.getByText("KXHIGHPHIL-26OCT03-T77 · 2026-10-03", { exact: true }).click();
    await expect(page.getByText(/If the maximum temperature recorded at Philadelphia/).first()).toBeVisible();
    await expect(page.getByRole("table", { name: "Philadelphia forecast coverage" })).toContainText("24/24");
    await expect(page.getByRole("heading", { name: "Hypotheses", exact: true })).toBeVisible();
    await expect(page.getByText("No candidates are eligible for backtesting.", { exact: false })).toBeVisible();
    await expect(page.getByText("Structured strategy proposal").first()).toBeVisible();
    await expect(page.getByRole("table", { name: "Provider request timings and usage" })).toContainText("100 / 100");
    await expect(page.getByText("Evidence tool calls")).toBeVisible();
    const download = page.waitForEvent("download");
    await page.getByRole("link", { name: "Download trace JSON" }).click();
    const file = path.join(evidence, "cis1990-controlled-trace.json");
    await (await download).saveAs(file);
    const text = await fs.readFile(file, "utf8");
    const trace = JSON.parse(text);
    assert.equal(trace.data_mode, "controlled_http");
    assert.equal(trace.provider.model_name, "gemini-3.5-flash-lite");
    assert.equal(trace.usage.requests, 6);
    assert(!text.includes(fixtureKey));
    assert(!((await page.locator("body").textContent()).includes(fixtureKey)));
    assert(!await page.evaluate(value => [localStorage, sessionStorage].some(storage =>
      Object.entries(storage).flat().some(item => item.includes(value))), fixtureKey));
    await page.reload();
    await expect(page.locator("#course-stage-critic [data-status]")).toHaveText("completed");
    await expect(key).toHaveValue("");
    const labels = page.locator(".course-result dt").filter({ hasText: /^(Test|Falsification|Reason)$/ });
    expect(await labels.count()).toBeGreaterThanOrEqual(3);
    for (const label of await labels.all()) {
      await expect(label).toHaveCSS("white-space", "nowrap");
      await expect(label.locator("+ dd")).toHaveCSS("display", "inline");
      await expect(label.locator("+ dd")).toHaveCSS("text-align", "left");
    }
    await page.screenshot({ path: path.join(evidence, "cis1990-controlled.png"), fullPage: true });
    await page.setViewportSize({ width: 2560, height: 900 });
    expect(await page.locator('[data-view="cis1990"]').evaluate(view => view.clientWidth)).toBeGreaterThan(1560);
    await page.setViewportSize({ width: 375, height: 812 });
    for (const label of await labels.all()) {
      const [term, description] = await label.evaluate(element =>
        [element, element.nextElementSibling].map(node => node.getBoundingClientRect().toJSON()));
      expect(description.x).toBeCloseTo(term.x);
      expect(description.width).toBeCloseTo(term.width);
    }
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(375);
    assert.deepEqual(errors, []);
  });
});

test("CIS 1990 reports a provider outage and retains its failed trace", async ({ page }) => {
  await withServer("outage", async () => {
    await page.goto(origin + "/#/cis1990");
    await page.getByRole("button", { name: "Run Philadelphia Weather Research" }).click();
    await expect(page.locator("#course-stage-research [data-status]")).toHaveText("failed");
    await expect(page.getByRole("alert")).toContainText("HTTP 503");
    await expect(page.locator("#course-stage-critic [data-status]")).toHaveText("not reached");
    await expect(page.getByRole("link", { name: "Download trace JSON" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Controlled source evidence" })).toBeVisible();
  });
});

test("CIS 1990 keeps credential entry out of fictional Demo Mode", async ({ page }) => {
  await withServer("no-key", async () => {
    const courseRequests = [];
    page.on("request", request => { if (request.url().includes("/api/cis1990")) courseRequests.push(request.method()); });
    await page.goto(origin);
    await page.getByRole("button", { name: "Demo", exact: true }).click();
    await page.getByRole("link", { name: "CIS 1990 Research Demo", exact: true }).click();
    await expect(page.getByText("Live research is available in Real Mode")).toBeVisible();
    await expect(page.getByRole("button", { name: "Run Philadelphia Weather Research" })).toHaveCount(0);
    await expect(page.getByLabel("Gemini API key")).toHaveCount(0);
    assert.deepEqual(courseRequests, []);
    await page.locator('[data-view="cis1990"]').getByRole("button", { name: "Switch to Real Mode" }).click();
    await expect(page.getByRole("button", { name: "Run Philadelphia Weather Research" })).toBeDisabled();
    await expect(page.getByLabel("Gemini API key")).toHaveAttribute("type", "password");
    assert.deepEqual(courseRequests, ["GET"]);
    await page.screenshot({ path: path.join(evidence, "cis1990-missing-key.png"), fullPage: true });
  });
});
