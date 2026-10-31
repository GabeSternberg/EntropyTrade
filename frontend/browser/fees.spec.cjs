"use strict";
// Actual Chromium/localhost inspection. Controlled intentions remain separate from receipts.
const { test, expect, chromium } = require("@playwright/test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { spawn, spawnSync } = require("node:child_process");
const { createHash } = require("node:crypto");

for (const authentic of [false, true]) {
  test(`point-in-time fees: ${authentic ? "authentic refusal" : "CONTROLLED intentions"}, downloads and restart`, async ({ page, browser }) => {
    const repo = path.resolve(__dirname, "../..");
    const evidence = path.join(process.env.ENTROPYTRADE_BROWSER_EVIDENCE, authentic ? "authentic" : "controlled");
    const workspace = process.env.ENTROPYTRADE_BROWSER_WORKSPACE + (authentic ? "-authentic" : "-controlled");
    const python = process.env.ENTROPYTRADE_BROWSER_PYTHON || path.join(repo, ".venv/bin/python");
    const origin = `http://127.0.0.1:${Number(process.env.ENTROPYTRADE_BROWSER_PORT || 43146)}`;
    assert(path.isAbsolute(workspace) && workspace.startsWith(path.join(repo, "data/cache/")));
    assert(!fs.existsSync(workspace)); assert(chromium.executablePath().startsWith(path.join(__dirname, ".browsers/")));
    fs.mkdirSync(evidence, { recursive: true });
    const env = { PATH: "/usr/bin:/bin", TZ: "UTC", PYTHONNOUSERSITE: "1", PYTHONDONTWRITEBYTECODE: "1", OMP_NUM_THREADS: "1", OPENBLAS_NUM_THREADS: "1", PYTHONPATH: `${repo}/backend:${repo}/backend/src` };
    const receipt = { status: "running", browser: browser.version(), executable: chromium.executablePath(), authentic, operations: [], downloads: [], screenshots: [], page_errors: [], limitation: authentic ? "Original receipt replay, missing fee document/model evidence, no new acquisition" : "CONTROLLED intentions, not empirical evidence", submission_enabled: false };
    const save = () => fs.writeFileSync(path.join(evidence, "receipt.json"), JSON.stringify(receipt, null, 2));
    const sha = bytes => createHash("sha256").update(bytes).digest("hex");
    const pause = ms => new Promise(resolve => setTimeout(resolve, ms));
    let server, epoch = 0;
    page.on("pageerror", error => { receipt.page_errors.push(error.message); save(); });
    async function start() {
      assert(!await fetch(origin + "/api/catalog").catch(() => null), "Port occupied");
      const log = fs.openSync(path.join(evidence, `server-${++epoch}.log`), "a");
      server = spawn(python, ["-m", "entropytrade.api.server", "--workspace", workspace, "--port", origin.split(":").at(-1)], { cwd: repo, env, stdio: ["ignore", log, log] }); fs.closeSync(log);
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
      const pending = page.waitForEvent("download"); await page.getByRole("link", { name, exact: true }).first().click();
      await (await pending).saveAs(path.join(evidence, file));
      const bytes = fs.readFileSync(path.join(evidence, file)); receipt.downloads.push({ file, sha256: sha(bytes) }); save(); return bytes;
    }
    async function shot(file) { await page.screenshot({ path: path.join(evidence, file), fullPage: true }); receipt.screenshots.push({ file }); save(); }
    save();
    try {
      const setup = spawnSync(python, ["-m", "tests.integration.fee_fixture", workspace, path.join(evidence, "setup.json"), ...(authentic ? ["--authentic"] : [])], { cwd: repo, env, encoding: "utf8", timeout: 120_000 });
      assert.equal(setup.status, 0, setup.stdout + setup.stderr);
      const seeded = JSON.parse(fs.readFileSync(path.join(evidence, "setup.json")));
      await start(); await page.goto(origin); await expect(page.locator("#submit")).toBeEnabled();
      await expect(page.locator("#fee-evidence")).toContainText(authentic ? "Official schedule HTTP 429" : "CONTROLLED fee fixture");
      const versionBytes = await download("Fee version JSON", "fee-version.json");
      const sourceBytes = await download("Original fee source 1", "fee-source.bin");
      const version = JSON.parse(versionBytes); assert.equal(version.evidence_kind, authentic ? "authentic" : "controlled");
      assert.equal(sha(sourceBytes), version.sources[0].sha256.slice(7));
      assert.equal(sourceBytes.toString("base64"), version.sources[0].body_base64);
      if (authentic) { assert.equal(version.policy, null); assert.equal(version.sources[0].status, 429); }
      else { assert(version.policy.certified); assert.equal(version.rounding, "cent_ceiling_per_fill"); }
      await page.locator("#shadow-history button").filter({ hasText: seeded.monitor_id.slice(0, 8) }).click();
      await expect(page.locator("#shadow-evidence")).toContainText(authentic ? "refused" : "fee_inclusive_shadow_collateral");
      await page.getByText("Frozen fee provenance and refusals", { exact: true }).first().click();
      await shot("fees-and-shadow.png");
      const shadowBytes = await download("Shadow evidence JSON", "shadow.json");
      const shadow = JSON.parse(shadowBytes); assert.equal(shadow.submission_enabled, false);
      if (authentic) {
        assert(shadow.cycles[0].result.decisions.every(d => d.status === "blocked" && d.intent === null));
        assert(shadow.cycles[0].result.decisions.every(d => !d.gates.point_in_time_prediction && !d.gates.certified_fees));
        await page.getByLabel("Research idea", { exact: true }).fill("Test forecast_high_f > 60");
        await page.getByLabel("Data source", { exact: true }).selectOption("recorded");
        await page.getByRole("button", { name: "Start research" }).click();
        await expect(page.locator("#run-header .badge").first()).toHaveText("completed", { timeout: 120_000 });
        const frozen = JSON.parse(await download("Experiment fee evidence", "experiment-fees.json"));
        assert.deepEqual(frozen.versions, [version]);
        const review = JSON.parse(await download("Review JSON", "review.json"));
        assert.equal(review.probability_count, 0); assert(review.candidates.every(c => !c.tested && c.scenarios.length === 0));
        await shot("authentic-research-refusal.png");
      } else {
        assert.equal(shadow.cycles.filter(c => c.result.decisions[0].status === "shadow_eligible").length, 4);
        assert.equal(shadow.cycles[0].result.decisions[0].status, "risk_rejected");
      }
      await stop(); await start(); await page.reload(); await expect(page.locator("#submit")).toBeEnabled();
      assert.deepEqual(await download("Fee version JSON", "restarted-version.json"), versionBytes);
      assert.deepEqual(await download("Original fee source 1", "restarted-source.bin"), sourceBytes);
      await page.locator("#shadow-history button").filter({ hasText: seeded.monitor_id.slice(0, 8) }).click();
      assert.deepEqual(await download("Shadow evidence JSON", "restarted-shadow.json"), shadowBytes);
      await shot("restarted.png"); assert.deepEqual(receipt.page_errors, []); receipt.status = "passed";
    } catch (error) { receipt.status = "failed"; receipt.failure = error.stack; throw error; }
    finally { await stop(); save(); }
  });
}
