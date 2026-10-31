"use strict";
// Real managed Chromium, localhost listener, page interaction/downloads, restart and offline replay.
const { test, expect, chromium } = require("@playwright/test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { spawn, spawnSync } = require("node:child_process");
const { createHash } = require("node:crypto");

for (const authentic of [false, true]) {
  test(`durable paper account: ${authentic ? "authentic refusal" : "CONTROLLED synthetic fills"}, downloads, restart and offline replay`, async ({ page, browser }) => {
    const repo = path.resolve(__dirname, "../..");
    const evidence = path.join(process.env.ENTROPYTRADE_BROWSER_EVIDENCE, authentic ? "authentic" : "controlled");
    const workspace = process.env.ENTROPYTRADE_BROWSER_WORKSPACE + (authentic ? "-authentic" : "-controlled");
    const python = process.env.ENTROPYTRADE_BROWSER_PYTHON || path.join(repo, ".venv/bin/python");
    const origin = `http://127.0.0.1:${Number(process.env.ENTROPYTRADE_BROWSER_PORT || 43148)}`;
    assert(path.isAbsolute(workspace) && workspace.startsWith(path.join(repo, "data/cache/")));
    assert(!fs.existsSync(workspace));
    assert(chromium.executablePath().startsWith(path.join(__dirname, ".browsers/")));
    fs.mkdirSync(evidence, { recursive: true });
    const env = { PATH: "/usr/bin:/bin", TZ: "UTC", PYTHONNOUSERSITE: "1", PYTHONDONTWRITEBYTECODE: "1", OMP_NUM_THREADS: "1", OPENBLAS_NUM_THREADS: "1", PYTHONPATH: `${repo}/backend:${repo}/backend/src` };
    const receipt = { status: "running", browser: browser.version(), executable: chromium.executablePath(), authentic, operations: [], downloads: [], screenshots: [], page_errors: [], limitation: authentic ? "Original authentic receipts; missing models/fees, zero fills; no new acquisition" : "CONTROLLED SYNTHETIC accounting only; never empirical performance", submission_enabled: false };
    const save = () => fs.writeFileSync(path.join(evidence, "receipt.json"), JSON.stringify(receipt, null, 2));
    const sha = bytes => createHash("sha256").update(bytes).digest("hex");
    const pause = ms => new Promise(resolve => setTimeout(resolve, ms));
    let server, epoch = 0;
    page.on("pageerror", error => { receipt.page_errors.push(error.message); save(); });
    async function start() {
      assert(!await fetch(origin + "/api/catalog").catch(() => null), "Port occupied");
      const log = fs.openSync(path.join(evidence, `server-${++epoch}.log`), "a");
      server = spawn(python, ["-m", "entropytrade.api.server", "--workspace", workspace, "--port", origin.split(":").at(-1)], { cwd: repo, env, stdio: ["ignore", log, log] });
      fs.closeSync(log);
      for (let n = 0; n < 100; n++) {
        if (server.exitCode !== null) throw new Error(`Listener exited ${server.exitCode}`);
        const response = await fetch(origin + "/api/catalog").catch(() => null);
        if (response?.ok) { assert.equal((await response.json()).submission_enabled, false); receipt.operations.push({ start: epoch }); save(); return; }
        await pause(100);
      }
      throw new Error("Listener startup timeout");
    }
    async function stop() {
      if (!server || server.exitCode !== null || server.signalCode !== null) return;
      server.kill("SIGINT");
      for (let n = 0; n < 100 && server.exitCode === null && server.signalCode === null; n++) await pause(100);
      if (server.exitCode === null && server.signalCode === null) { server.kill("SIGKILL"); throw new Error("Listener shutdown timeout"); }
    }
    async function download(name, file) {
      const pending = page.waitForEvent("download"); await page.getByRole("link", { name, exact: true }).click();
      await (await pending).saveAs(path.join(evidence, file));
      const bytes = fs.readFileSync(path.join(evidence, file)); receipt.downloads.push({ file, sha256: sha(bytes) }); save(); return bytes;
    }
    async function shot(file) { await page.screenshot({ path: path.join(evidence, file), fullPage: true }); receipt.screenshots.push({ file }); save(); }
    save();
    try {
      const setup = spawnSync(python, ["-m", "tests.integration.paper_fixture", workspace, path.join(evidence, "setup.json"), ...(authentic ? ["--authentic"] : [])], { cwd: repo, env, encoding: "utf8", timeout: 120_000 });
      assert.equal(setup.status, 0, setup.stdout + setup.stderr);
      const seeded = JSON.parse(fs.readFileSync(path.join(evidence, "setup.json")));
      await start(); await page.goto(origin); await expect(page.locator("#submit")).toBeEnabled();
      await page.locator("#shadow-history button").filter({ hasText: seeded.monitor_id.slice(0, 8) }).click();
      await expect(page.locator("#paper-account")).toContainText("Simulated paper account");
      await expect(page.locator("#paper-account")).toContainText(authentic ? "eligibility can remain blocked" : "CONTROLLED SYNTHETIC");
      await page.getByText("Simulated decisions, execution risk, fills and settlements", { exact: true }).first().click();
      await page.getByText("Paper account state and liquidity consumption", { exact: true }).click();
      await shot("paper-account.png");
      const accountBytes = await download("Paper account JSON", "account.json");
      const shadowBytes = await download("Shadow evidence JSON", "shadow.json");
      const account = JSON.parse(accountBytes), shadow = JSON.parse(shadowBytes);
      assert.equal(account.submission_enabled, false); assert.equal(shadow.submission_enabled, false);
      assert.deepEqual(account.account, shadow.paper_account); assert.deepEqual(account.summary, seeded.summary);
      assert.deepEqual(shadow.fills, []); assert.equal(shadow.performance, null);
      if (authentic) {
        assert.equal(account.summary.fill_count, 0); assert.equal(account.summary.fees, "0.000000");
        assert(shadow.cycles[0].result.paper.decisions.every(d => d.status === "blocked" && d.intent === null));
        assert(shadow.cycles[0].result.paper.decisions.every(d => !d.gates.point_in_time_prediction && !d.gates.certified_fees));
      } else {
        assert.equal(account.summary.fill_count, 2); assert.equal(account.summary.settlement_count, 1);
        assert.deepEqual(account.summary.positions, []); assert.equal(account.summary.cash, "1001.420000");
        assert(shadow.cycles.some(c => c.result.paper.executions.some(e => e.reason === "liquidity_exhausted")));
        assert(shadow.cycles.some(c => c.result.paper.executions.some(e => e.unsubmitted_quantity === "1.00")));
        assert.equal(shadow.cycles.flatMap(c => c.result.paper.settlements).length, 1);
      }
      await stop();
      const offline = spawnSync(python, ["-m", "entropytrade.tracking.accounting", path.join(evidence, "shadow.json")], { cwd: repo, env, encoding: "utf8", timeout: 120_000 });
      assert.equal(offline.status, 0, offline.stderr); receipt.offline = JSON.parse(offline.stdout); assert(receipt.offline.verified); save();
      await start(); await page.reload(); await expect(page.locator("#submit")).toBeEnabled();
      await page.locator("#shadow-history button").filter({ hasText: seeded.monitor_id.slice(0, 8) }).click();
      assert.deepEqual(await download("Paper account JSON", "restarted-account.json"), accountBytes);
      assert.deepEqual(await download("Shadow evidence JSON", "restarted-shadow.json"), shadowBytes);
      await shot("restarted.png"); assert.deepEqual(receipt.page_errors, []); receipt.status = "passed";
    } catch (error) { receipt.status = "failed"; receipt.failure = error.stack; throw error; }
    finally { await stop(); save(); }
  });
}
