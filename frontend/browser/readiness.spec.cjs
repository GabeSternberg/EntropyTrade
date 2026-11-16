"use strict";
// Actual localhost services, fitted portable models and retained 1/23-day paper wires.
// All source bytes are explicitly controlled synthetic; production still refuses them.
const { test, expect, chromium } = require("@playwright/test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { spawn, spawnSync } = require("node:child_process");
const { createHash } = require("node:crypto");

for (const controlled of [false, true]) {
  test(`readiness oversight: ${controlled ? "CONTROLLED owner review and audit recovery" : "production evidence and unconfigured owner refusal"}`, async ({ page, browser }) => {
    const repo = path.resolve(__dirname, "../..");
    const prefix = controlled ? "controlled-readiness" : "production-refusal";
    const evidence = path.join(process.env.ENTROPYTRADE_BROWSER_EVIDENCE, prefix);
    let workspace = process.env.ENTROPYTRADE_BROWSER_WORKSPACE + "-" + prefix;
    const python = process.env.ENTROPYTRADE_BROWSER_PYTHON || path.join(repo, ".venv/bin/python");
    const origin = `http://127.0.0.1:${Number(process.env.ENTROPYTRADE_BROWSER_PORT || 43221) + Number(controlled)}`;
    assert(path.isAbsolute(workspace) && workspace.startsWith(path.join(repo, "data/cache/")));
    assert(!fs.existsSync(workspace), "workspace must be new");
    assert(chromium.executablePath().startsWith(path.join(__dirname, ".browsers/")));
    fs.mkdirSync(evidence, { recursive: true });
    const metadata = path.join(evidence, "setup.json");
    const env = { PATH: "/usr/bin:/bin", TZ: "UTC", PYTHONNOUSERSITE: "1", PYTHONDONTWRITEBYTECODE: "1", OMP_NUM_THREADS: "1", OPENBLAS_NUM_THREADS: "1", PYTHONPATH: `${repo}/backend:${repo}/backend/src` };
    const privateDirectory = controlled ? fs.mkdtempSync(path.join(os.tmpdir(), "entropytrade-owner-browser-")) : null;
    const ownerFile = privateDirectory && path.join(privateDirectory, "owner.json");
    // Explicit test-only credential; never a user secret. Only its derived private file is persisted.
    const passphrase = "CONTROLLED-browser-owner-passphrase-2026";
    function sourceFingerprint() {
      const files = [];
      const collect = (directory) => {
        for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
          const file = path.join(directory, entry.name);
          if (entry.isDirectory()) collect(file);
          else if (entry.isFile() && /\.(?:py|js|cjs|css|html|json)$/.test(entry.name)) files.push(file);
        }
      };
      for (const directory of ["backend/src", "backend/tests", "frontend/src", "frontend/tests"]) collect(path.join(repo, directory));
      files.push(__filename, path.join(__dirname, "playwright.config.cjs"));
      const manifest = files.sort().map((file) => [path.relative(repo, file), createHash("sha256").update(fs.readFileSync(file)).digest("hex")]);
      return { sha256: createHash("sha256").update(JSON.stringify(manifest)).digest("hex"), files: manifest.length };
    }
    if (controlled) {
      fs.chmodSync(privateDirectory, 0o700);
      // Test setup invokes the same private-file initializer directly; production CLI
      // deliberately requires an interactive TTY and is never bypassed by an HTTP API.
      const setup = spawnSync(python, ["-c", "import sys; from pathlib import Path; from entropytrade.api.owner import initialize; initialize(Path(sys.argv[1]), Path.cwd(), 'browser-owner', sys.stdin.read())", ownerFile], { cwd: repo, env, input: passphrase, encoding: "utf8" });
      assert.equal(setup.status, 0, setup.stderr);
      assert.equal(fs.statSync(ownerFile).mode & 0o777, 0o600);
    }
    const receipt = { status: "running", data_kind: "synthetic", controlled_readiness: controlled, browser: browser.version(), source_before: sourceFingerprint(), posts: [], sensitive_requests: [], screenshots: [], downloads: [], page_errors: [], console_errors: [] };
    const save = () => fs.writeFileSync(path.join(evidence, "receipt.json"), JSON.stringify(receipt, null, 2));
    page.on("pageerror", (error) => { receipt.page_errors.push(error.message); save(); });
    page.on("console", (message) => { if (message.type() === "error") { receipt.console_errors.push(message.text()); save(); } });
    page.on("request", (request) => {
      const pathname = new URL(request.url()).pathname;
      if (/^\/api\/(owner|controls|readiness)(\/|$)/.test(pathname) || /\/(readiness|monitoring)$/.test(pathname)) receipt.sensitive_requests.push({ path: pathname, method: request.method() });
      if (request.method() !== "POST") return;
      receipt.posts.push({ path: pathname, body: pathname === "/api/owner/login" ? { password: "[REDACTED CONTROLLED TEST INPUT]" } : request.postDataJSON() }); save();
    });
    let server, monitorId, epoch = 0;
    const pause = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
    const get = async (url) => { const response = await fetch(origin + url); assert(response.ok, `${response.status}: ${url}`); return response.json(); };
    async function start() {
      assert(!await fetch(origin + "/api/catalog").catch(() => null), "Port occupied");
      const log = fs.openSync(path.join(evidence, `server-${++epoch}.log`), "a");
      server = spawn(python, ["-m", "tests.integration.research_readiness_fixture", "--workspace", workspace, "--port", origin.split(":").at(-1), "--metadata", metadata, "--cycles", controlled ? "23" : "1", ...(monitorId ? ["--monitor-id", monitorId] : []), ...(ownerFile ? ["--owner-file", ownerFile, "--controlled-readiness"] : [])], { cwd: repo, env, stdio: ["ignore", log, log] });
      fs.closeSync(log);
      for (let n = 0; n < 1800; n++) {
        if (server.exitCode !== null) throw new Error(`Listener exited ${server.exitCode}; inspect server-${epoch}.log`);
        if ((await fetch(origin + "/api/owner").catch(() => null))?.ok) { monitorId ||= JSON.parse(fs.readFileSync(metadata)).monitor_id; return; }
        await pause(100);
      }
      throw new Error("Readiness fixture startup timeout");
    }
    async function stop() {
      if (!page.isClosed()) await page.goto("about:blank");
      if (!server || server.exitCode !== null || server.signalCode !== null) return;
      server.kill("SIGINT");
      await new Promise((resolve) => server.exitCode !== null ? resolve() : server.once("exit", resolve));
    }
    async function shot(file) { await page.evaluate(() => window.scrollTo(0, 0)); await page.screenshot({ path: path.join(evidence, file), fullPage: true }); receipt.screenshots.push(file); save(); }
    async function open() {
      await page.goto(origin + `/#/paper/${monitorId}`);
      await expect(page.locator("#paper-governance").getByRole("button", { name: "Save readiness proposal", exact: true })).toBeVisible({ timeout: 90_000 });
    }
    async function signIn() {
      await page.locator("#owner-access").click();
      const modal = page.getByRole("dialog", { name: "Owner access", exact: true });
      await modal.getByLabel("Owner passphrase").fill(passphrase);
      await modal.getByRole("button", { name: "Sign in", exact: true }).click();
      await expect(modal.getByText(/Signed in for readiness review/)).toBeVisible({ timeout: 90_000 });
      await expect(modal.getByLabel("Owner passphrase")).toHaveCount(0);
      await modal.getByRole("button", { name: "Close", exact: true }).click();
      const cookies = await page.context().cookies(origin);
      const owner = cookies.find((cookie) => cookie.name.startsWith("et_owner_"));
      assert(owner?.httpOnly && owner.sameSite === "Strict");
      assert(!await page.evaluate(() => Object.keys(localStorage).some((key) => /owner|password|session/i.test(key))));
    }
    async function saveProposal(capital, loss) {
      const governance = page.locator("#paper-governance");
      await governance.getByLabel("Proposed capital in dollars").fill(capital);
      await governance.getByLabel("Proposed maximum loss in dollars").fill(loss);
      const response = page.waitForResponse((item) => item.request().method() === "POST" && new URL(item.url()).pathname === `/api/monitors/${monitorId}/readiness`);
      await governance.getByRole("button", { name: "Save readiness proposal", exact: true }).click();
      const saved = await response;
      const value = await saved.json();
      if (saved.status() !== 201) { receipt.api_error = value; save(); }
      assert.equal(saved.status(), 201, JSON.stringify(value));
      const id = value.id || value.proposal?.id;
      assert(id?.startsWith("sha256:"));
      await expect(governance.locator(".readiness-record")).toContainText(id, { timeout: 90_000 });
      return id;
    }
    async function recordDownload(file) {
      const waiting = page.waitForEvent("download");
      await page.getByRole("link", { name: "Readiness record JSON", exact: true }).click();
      await (await waiting).saveAs(path.join(evidence, file));
      const bytes = fs.readFileSync(path.join(evidence, file));
      receipt.downloads.push({ file, sha256: createHash("sha256").update(bytes).digest("hex") }); save();
      return JSON.parse(bytes);
    }
    try {
      await start(); await open();
      const governance = page.locator("#paper-governance");
      await expect(governance.getByText(/execution_authorized=false/)).toBeVisible();
      const initial = await get(`/api/monitors/${monitorId}/readiness`);
      assert.equal(initial.submission_enabled, false);
      if (!controlled) {
        assert.equal(initial.preview.eligible, false);
        await expect(governance.getByText(/Owner access is not configured/)).toBeVisible();
        const id = await saveProposal("100.00", "10.00");
        await expect(governance.getByRole("button", { name: "Approve readiness review", exact: true })).toBeDisabled();
        const record = await get(`/api/readiness/${encodeURIComponent(id)}`);
        assert.equal(record.payload.eligible, false);
        assert.equal(record.payload.execution_authorized, false);
        await page.locator("#global-halt").click();
        const halt = page.getByRole("dialog", { name: "Global paper halt", exact: true });
        await halt.getByLabel("Global halt reason").fill("Controlled refusal acceptance");
        await halt.getByRole("button", { name: "Halt new paper orders", exact: true }).click();
        await expect(halt.getByRole("button", { name: "Release global halt", exact: true })).toBeDisabled({ timeout: 90_000 });
        await halt.getByRole("button", { name: "Close", exact: true }).click();
        assert.equal((await get("/api/controls")).halted, true);
        assert(!receipt.posts.some((post) => /owner\/login|\/review|\/release/.test(post.path)));
        await shot("production-blocked-readiness.png");
      } else {
        assert.equal(initial.preview.eligible, true, JSON.stringify(initial.preview.reasons));
        await signIn();
        const first = await saveProposal("100.00", "10.00");
        await governance.getByLabel("Readiness review note").fill("Reviewed actual retained synthetic wires and bounded capital");
        await governance.getByRole("button", { name: "Approve readiness review", exact: true }).click();
        await expect.poll(async () => (await get(`/api/readiness/${encodeURIComponent(first)}`)).status, { timeout: 90_000 }).toBe("approved");
        const approved = await get(`/api/readiness/${encodeURIComponent(first)}`);
        assert.equal(approved.payload.execution_authorized, false);
        assert.equal(approved.payload.submission_enabled, false);
        receipt.evidence = { cycles: approved.payload.facts.paper_prefix.length, independent_events: approved.payload.facts.scores.independent_events, evidence_hash: approved.payload.facts.evidence_hash };
        await expect(governance.locator('.readiness-record [data-status="approved"]')).toBeVisible({ timeout: 90_000 });
        const monitoringResponse = page.waitForResponse((item) => item.request().method() === "GET" && new URL(item.url()).pathname === `/api/monitors/${monitorId}/monitoring`);
        await governance.getByRole("tab", { name: "Monitoring", exact: true }).click();
        const observed = await monitoringResponse;
        assert.equal(observed.status(), 200);
        const monitoring = await observed.json();
        assert.equal(monitoring.monitor_id, monitorId);
        assert.equal(monitoring.submission_enabled, false);
        assert.equal(typeof monitoring.evaluation.status, "string");
        await expect(governance.getByText(monitoring.evaluation.status.replaceAll("_", " "), { exact: true }).first()).toBeVisible();
        for (const signal of monitoring.evaluation.signals || []) if (signal.reason) await expect(governance).toContainText(signal.reason);
        receipt.monitoring = { status: monitoring.evaluation.status, evidence_as_of: monitoring.evaluation.evidence_as_of, signal_kinds: (monitoring.evaluation.signals || []).map((signal) => signal.kind), incident_ids: (monitoring.incidents || []).map((incident) => incident.id) };
        await shot("actual-readiness-monitoring.png");
        await governance.getByRole("tab", { name: "Readiness", exact: true }).click();
        const second = await saveProposal("200.00", "15.00");
        await governance.getByLabel("Readiness review note").fill("Reject this larger proposed envelope for controlled review coverage");
        await governance.getByRole("button", { name: "Reject readiness review", exact: true }).click();
        await expect.poll(async () => (await get(`/api/readiness/${encodeURIComponent(second)}`)).status, { timeout: 90_000 }).toBe("rejected");
        await expect(governance.locator('.readiness-record [data-status="rejected"]')).toBeVisible({ timeout: 90_000 });
        await governance.getByText("Rollback from a prior server proposal", { exact: true }).click();
        await governance.getByRole("combobox", { name: "Prior readiness proposal", exact: true }).selectOption(first);
        await governance.getByLabel("Rollback proposal reason").fill("Review prior server references without replacing the deployed model");
        const rollbackResponse = page.waitForResponse((item) => item.request().method() === "POST" && new URL(item.url()).pathname.endsWith("/rollback"));
        await governance.getByRole("button", { name: "Create pending rollback proposal", exact: true }).click();
        const rolled = await rollbackResponse; assert.equal(rolled.status(), 201);
        const rollback = await rolled.json(); const third = rollback.id || rollback.proposal?.id;
        assert(third && third !== first && third !== second);
        await expect(governance.locator(".readiness-record")).toContainText(third, { timeout: 90_000 });
        assert.equal((await get(`/api/readiness/${encodeURIComponent(third)}`)).status, "proposed");
        await page.locator("#owner-access").click();
        const owner = page.getByRole("dialog", { name: "Owner access", exact: true });
        await owner.getByRole("button", { name: "Sign out", exact: true }).click();
        await expect(owner.getByLabel("Owner passphrase")).toBeVisible({ timeout: 90_000 });
        await owner.getByRole("button", { name: "Close", exact: true }).click();
        await governance.getByLabel("Readiness revocation reason").fill("Withdraw pending controlled proposal");
        await governance.getByRole("button", { name: "Revoke readiness proposal", exact: true }).click();
        await expect.poll(async () => (await get(`/api/readiness/${encodeURIComponent(third)}`)).status, { timeout: 90_000 }).toBe("revoked");
        await page.locator("#global-halt").click();
        let halt = page.getByRole("dialog", { name: "Global paper halt", exact: true });
        await halt.getByLabel("Global halt reason").fill("Check the persistent global barrier");
        await halt.getByRole("button", { name: "Halt new paper orders", exact: true }).click();
        await expect(halt.getByRole("button", { name: "Release global halt", exact: true })).toBeDisabled({ timeout: 90_000 });
        await halt.getByRole("button", { name: "Close", exact: true }).click();
        const haltedMonitor = await get(`/api/monitors/${monitorId}`);
        await signIn(); await page.locator("#global-halt").click();
        halt = page.getByRole("dialog", { name: "Global paper halt", exact: true });
        await halt.getByLabel("Global halt reason").fill("Owner reviewed the barrier state");
        await halt.getByRole("button", { name: "Release global halt", exact: true }).click();
        await expect(halt.getByRole("button", { name: "Halt new paper orders", exact: true })).toBeVisible({ timeout: 90_000 });
        await halt.getByRole("button", { name: "Close", exact: true }).click();
        const releasedMonitor = await get(`/api/monitors/${monitorId}`);
        assert.equal(releasedMonitor.status, haltedMonitor.status, "release does not resume a deployment");
        assert.deepEqual(releasedMonitor.model_binding, haltedMonitor.model_binding);
        const before = await recordDownload("revoked-readiness.json");
        await governance.getByRole("tab", { name: "Audit", exact: true }).click();
        await expect(governance).toContainText("browser-owner");
        await shot("owner-readiness-audit.png");
        await page.setViewportSize({ width: 375, height: 900 });
        assert(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth) <= 1);
        await shot("readiness-mobile.png");
        await stop(); await start(); await open();
        assert.equal((await page.request.get(origin + "/api/owner").then((response) => response.json())).authenticated, false, "RAM-only owner sessions expire on restart");
        await governance.getByRole("combobox", { name: "Frozen readiness proposal", exact: true }).selectOption(third);
        await expect(governance.locator(".readiness-record")).toContainText(third);
        const restarted = await recordDownload("restarted-readiness.json");
        assert.deepEqual(restarted.payload, before.payload); assert.deepEqual(restarted.events, before.events);
        await stop();
        const archive = path.join(evidence, "workspace.zip");
        for (const recovery of ["snapshot", "restore"]) {
          const target = recovery === "snapshot" ? workspace : workspace + "-restored";
          const result = spawnSync(python, ["-m", "tests.integration.research_readiness_fixture", "--workspace", target, "--recover", recovery, "--archive", archive], { cwd: repo, env, encoding: "utf8", timeout: 180_000 });
          assert.equal(result.status, 0, result.stderr); receipt[recovery] = JSON.parse(result.stdout);
          if (recovery === "restore") workspace = target;
        }
        await start(); await open();
        await governance.getByRole("combobox", { name: "Frozen readiness proposal", exact: true }).selectOption(third);
        await expect(governance.locator(".readiness-record")).toContainText(third);
        const restored = await recordDownload("restored-readiness.json");
        assert.deepEqual(restored.payload, before.payload); assert.deepEqual(restored.events, before.events);
        assert.equal((await get("/api/controls")).halted, false);
        await expect(page.getByRole("switch", { name: "Live trading (disabled)" })).toBeDisabled();
        await shot("restored-readiness.png");
      }
      const beforeDemo = receipt.sensitive_requests.length;
      const writesBeforeDemo = receipt.posts.length;
      await page.locator("#mode-switch").getByRole("button", { name: "Demo", exact: true }).click();
      await expect(page.locator("#owner-access")).toBeDisabled();
      await expect(page.locator("#global-halt")).toBeDisabled();
      await pause(750);
      assert.equal(receipt.sensitive_requests.length, beforeDemo, "Demo performs no owner, review, monitoring or halt I/O");
      assert.equal(receipt.posts.length, writesBeforeDemo, "Demo dispatches no writes");
      await shot("demo-oversight-disabled.png");
      receipt.status = "passed";
    } catch (error) { receipt.status = "failed"; receipt.error = error.stack || error.message; save(); throw error; }
    finally {
      await stop();
      if (privateDirectory) fs.rmSync(privateDirectory, { recursive: true, force: true });
      const completed = receipt.status === "passed";
      receipt.source_after = sourceFingerprint();
      const sourceChanged = receipt.source_before.sha256 !== receipt.source_after.sha256;
      if (completed && (receipt.page_errors.length || receipt.console_errors.length || sourceChanged)) {
        receipt.status = "failed";
        receipt.error = sourceChanged ? "Application or acceptance source changed during execution" : "Browser page or console errors were recorded";
      }
      save();
      if (completed) { assert.deepEqual(receipt.page_errors, []); assert.deepEqual(receipt.console_errors, []); assert.deepEqual(receipt.source_after, receipt.source_before, "application and acceptance source must remain frozen"); }
    }
  });
}
