"use strict";
// Real managed Chromium and actual localhost pages. No route interception or browser mocks.
const { test, expect, chromium } = require("@playwright/test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { spawn, spawnSync } = require("node:child_process");
const { createHash } = require("node:crypto");

for (const authentic of [false, true]) {
  test(`prospective forecast evaluation: ${authentic ? "authentic insufficiency" : "CONTROLLED synthetic diagnostics"}, downloads, restart and offline restore`, async ({ page, browser }) => {
    const repo = path.resolve(__dirname, "../..");
    const evidence = path.join(process.env.ENTROPYTRADE_BROWSER_EVIDENCE, authentic ? "authentic" : "controlled");
    const original = process.env.ENTROPYTRADE_BROWSER_WORKSPACE + (authentic ? "-authentic" : "-controlled");
    let workspace = original;
    const python = process.env.ENTROPYTRADE_BROWSER_PYTHON || path.join(repo, ".venv/bin/python");
    const origin = `http://127.0.0.1:${Number(process.env.ENTROPYTRADE_BROWSER_PORT || 43154)}`;
    assert(path.isAbsolute(workspace) && workspace.startsWith(path.join(repo, "data/cache/")));
    assert(!fs.existsSync(workspace) && !fs.existsSync(evidence));
    assert(chromium.executablePath().startsWith(path.join(__dirname, ".browsers/")));
    fs.mkdirSync(evidence, { recursive: true });
    const env = { PATH: "/usr/bin:/bin", TZ: "UTC", PYTHONNOUSERSITE: "1", PYTHONDONTWRITEBYTECODE: "1", OMP_NUM_THREADS: "1", OPENBLAS_NUM_THREADS: "1", PYTHONPATH: `${repo}/backend:${repo}/backend/src` };
    const receipt = { status: "running", browser: browser.version(), executable: chromium.executablePath(), authentic, starts: [], downloads: [], screenshots: [], page_errors: [], submission_enabled: false,
      limitation: authentic ? "Unchanged authentic receipts; no usable forecast or empirical metrics" : "CONTROLLED SYNTHETIC diagnostics; never empirical validation or returns" };
    const save = () => fs.writeFileSync(path.join(evidence, "receipt.json"), JSON.stringify(receipt, null, 2));
    const pause = ms => new Promise(resolve => setTimeout(resolve, ms));
    const sha = bytes => createHash("sha256").update(bytes).digest("hex");
    let server, epoch = 0;
    page.on("pageerror", error => { receipt.page_errors.push(error.message); save(); });
    function command(args) {
      const result = spawnSync(python, args, { cwd: repo, env, encoding: "utf8", timeout: 120_000 });
      assert.equal(result.status, 0, result.stdout + result.stderr); return result.stdout;
    }
    async function start() {
      assert(!await fetch(origin + "/api/catalog").catch(() => null), "Port occupied");
      const log = fs.openSync(path.join(evidence, `server-${++epoch}.log`), "a");
      server = spawn(python, ["-m", "entropytrade.api.server", "--workspace", workspace, "--port", origin.split(":").at(-1)], { cwd: repo, env, stdio: ["ignore", log, log] }); fs.closeSync(log);
      for (let n = 0; n < 100; n++) {
        if (server.exitCode !== null) throw new Error(`Listener exited ${server.exitCode}`);
        const response = await fetch(origin + "/api/catalog").catch(() => null);
        if (response?.ok) { receipt.starts.push({ epoch, workspace }); save(); return; }
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
    async function download(label, file) {
      const pending = page.waitForEvent("download"); await page.getByRole("link", { name: label, exact: true }).click();
      await (await pending).saveAs(path.join(evidence, file)); const bytes = fs.readFileSync(path.join(evidence, file));
      receipt.downloads.push({ file, sha256: sha(bytes) }); save(); return bytes;
    }
    async function inspect(mid, screenshot) {
      await page.goto("about:blank"); await page.goto(origin + "/#/workbench"); await expect(page.locator("#submit")).toBeEnabled();
      await page.locator("#shadow-history button").filter({ hasText: mid.slice(0, 8) }).click();
      await expect(page.locator("#shadow-evaluation")).toContainText("evidence cutoff");
      await expect(page.locator("#shadow-evaluation")).toContainText(authentic ? "Insufficient evidence: no forecast metrics" : "CONTROLLED SYNTHETIC");
      await page.getByText("Forecast, source and outcome lineage", { exact: true }).click();
      await page.locator("#shadow-evaluation").scrollIntoViewIfNeeded();
      await page.screenshot({ path: path.join(evidence, screenshot), fullPage: false }); receipt.screenshots.push(screenshot); save();
    }
    save();
    try {
      command(["-m", "tests.integration.prospective_fixture", workspace, path.join(evidence, "setup.json"), ...(authentic ? ["--authentic"] : [])]);
      const setup = JSON.parse(fs.readFileSync(path.join(evidence, "setup.json")));
      await start(); await inspect(setup.monitor_id, "evaluation.png");
      const json = await download("Forecast evaluation JSON", "evaluation.json");
      const csv = await download("Forecast observations CSV", "observations.csv");
      const value = JSON.parse(json); assert.deepEqual(value, setup.report);
      assert.equal(value.submission_enabled, false); assert.equal(value.historical_validation, false); assert.equal(value.performance, null);
      if (authentic) { assert.equal(value.counts.matched, 0); assert.equal(value.counts.refused, 24); assert.deepEqual(value.diagnostics, []); }
      else { assert.equal(value.counts.matched_events, 10); assert.equal(value.counts.poll_observations, 39); assert.equal(value.observations[0].outcome_revisions, 1); assert.equal(value.diagnostics[0].metrics.event_weighted_brier, .0875); }
      await stop();
      const offline = JSON.parse(command(["-m", "entropytrade.tracking.prospective", "--workspace", workspace, "--monitor", setup.monitor_id]));
      assert.deepEqual(offline, value); receipt.offline_replay_identical = true; save();
      await start(); await inspect(setup.monitor_id, "restarted.png");
      assert.deepEqual(await download("Forecast evaluation JSON", "restarted-evaluation.json"), json);
      assert.deepEqual(await download("Forecast observations CSV", "restarted-observations.csv"), csv);
      await stop();
      const archive = original + ".zip";
      command(["-m", "entropytrade.api.recovery", "snapshot", "--workspace", workspace, "--archive", archive]);
      workspace = original + "-restored";
      command(["-m", "entropytrade.api.recovery", "restore", "--workspace", workspace, "--archive", archive]);
      receipt.archive = { file: archive, sha256: sha(fs.readFileSync(archive)) }; save();
      await start(); await inspect(setup.monitor_id, "offline-restored.png");
      assert.deepEqual(await download("Forecast evaluation JSON", "restored-evaluation.json"), json);
      assert.deepEqual(await download("Forecast observations CSV", "restored-observations.csv"), csv);
      assert.deepEqual(receipt.page_errors, []); receipt.status = "passed";
    } catch (error) { receipt.status = "failed"; receipt.failure = error.stack; throw error; }
    finally { await stop(); save(); }
  });
}
