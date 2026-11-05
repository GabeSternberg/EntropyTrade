"use strict";
// Real managed Chromium/listener; accelerated source/clock evidence is explicitly CONTROLLED.
const { test, expect, chromium } = require("@playwright/test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { spawn, spawnSync } = require("node:child_process");
const { createHash } = require("node:crypto");
const pause = ms => new Promise(resolve => setTimeout(resolve, ms));
const sha = bytes => createHash("sha256").update(bytes).digest("hex");

test("bounded label partitions: 130 controlled batches, outage, cancellation, restart and restore", async ({ page, browser }) => {
  const repo = path.resolve(__dirname, "../..");
  const evidence = path.join(process.env.ENTROPYTRADE_BROWSER_EVIDENCE, "partition-controlled");
  let workspace = process.env.ENTROPYTRADE_BROWSER_WORKSPACE + "-partitions";
  const python = process.env.ENTROPYTRADE_BROWSER_PYTHON || path.join(repo, ".venv/bin/python");
  const port = Number(process.env.ENTROPYTRADE_BROWSER_PORT || 43153);
  const origin = `http://127.0.0.1:${port}`;
  assert(path.isAbsolute(workspace) && workspace.startsWith(path.join(repo, "data/cache/")));
  assert(!fs.existsSync(workspace), "Fresh workspace required");
  assert(chromium.executablePath().startsWith(path.join(__dirname, ".browsers/")));
  fs.mkdirSync(evidence, { recursive: true });
  const receiptFile = path.join(evidence, "browser-receipt.json");
  assert(!fs.existsSync(receiptFile));
  const receipt = { status: "running", started_at: new Date().toISOString(), origin, workspace,
    executable: chromium.executablePath(), browser: browser.version(), operations: [], downloads: [], screenshots: [], page_errors: [],
    evidence_scope: "CONTROLLED source reports and accelerated scheduling clock. No elapsed authentic operation, empirical fitting or performance proof." };
  const save = () => fs.writeFileSync(receiptFile, JSON.stringify(receipt, null, 2) + "\n");
  const env = { PATH: "/usr/bin:/bin", PYTHONNOUSERSITE: "1", PYTHONDONTWRITEBYTECODE: "1",
    OMP_NUM_THREADS: "1", OPENBLAS_NUM_THREADS: "1", TZ: "UTC",
    PYTHONPATH: path.join(repo, "backend") + ":" + path.join(repo, "backend/src") };
  const phaseFile = workspace + "-phase.json";
  let days = 0, server, epoch = 0, scheduleId;
  function phase(value, advance = false) {
    if (advance) days++;
    fs.writeFileSync(phaseFile + ".pending", JSON.stringify({ phase: value, now: new Date(Date.UTC(2026, 9, 31, 12) + days * 86400000).toISOString() }));
    fs.renameSync(phaseFile + ".pending", phaseFile);
  }
  function command(args, name) {
    const result = spawnSync(python, args, { cwd: repo, env, encoding: "utf8", timeout: 180000 });
    fs.writeFileSync(path.join(evidence, name + ".log"), result.stdout + result.stderr);
    assert.equal(result.status, 0, result.stdout + result.stderr);
  }
  async function start() {
    assert(!await fetch(origin + "/api/catalog").catch(() => null), "Port occupied");
    const log = fs.openSync(path.join(evidence, `server-${++epoch}.log`), "a");
    server = spawn(python, ["-m", "tests.integration.label_partition_fixture", workspace, "--phase", phaseFile, "--port", String(port)], { cwd: repo, env, stdio: ["ignore", log, log] });
    fs.closeSync(log);
    for (let i = 0; i < 600; i++) {
      if (server.exitCode !== null) throw new Error(`Listener exited ${server.exitCode}`);
      const response = await fetch(origin + "/api/catalog").catch(() => null);
      if (response?.ok) {
        const catalog = await response.json();
        assert.equal(catalog.submission_enabled, false); assert.equal(catalog.provider_enabled, false);
        receipt.operations.push({ action: "start", epoch, workspace }); save(); return;
      }
      await pause(100);
    }
    throw new Error("Listener startup timeout");
  }
  async function stop() {
    if (!server || server.exitCode !== null || server.signalCode !== null) return;
    server.kill("SIGINT");
    for (let i = 0; i < 300 && server.exitCode === null && server.signalCode === null; i++) await pause(100);
    if (server.exitCode === null && server.signalCode === null) { server.kill("SIGKILL"); throw new Error("Graceful shutdown timeout"); }
    receipt.operations.push({ action: "stop", epoch }); save();
  }
  async function shot(name, selector = "#weather-label-partition-info") {
    const file = name + ".png";
    await page.locator(selector).screenshot({ path: path.join(evidence, file) });
    receipt.screenshots.push({ file, sha256: sha(fs.readFileSync(path.join(evidence, file))) }); save();
  }
  async function download(name, linkName) {
    const pending = page.waitForEvent("download");
    await page.getByRole("link", { name: linkName, exact: true }).first().click();
    await (await pending).saveAs(path.join(evidence, name));
    const bytes = fs.readFileSync(path.join(evidence, name));
    receipt.downloads.push({ file: name, sha256: sha(bytes) }); save(); return bytes;
  }
  async function waitFor(predicate) {
    let value;
    for (let i = 0; i < 600; i++) {
      const response = await fetch(origin + "/api/weather/schedules/" + scheduleId);
      value = await response.json();
      if (response.ok && predicate(value)) return value;
      await pause(50);
    }
    throw new Error("Schedule did not reach expected state: " + JSON.stringify(value));
  }
  // Wait for the newest label render to finish so assertions and screenshots never observe
  // the previous partition's rows or a node that is about to be replaced.
  async function settled(partition) {
    const labels = page.locator("#weather-labels");
    await expect(labels).toHaveAttribute("aria-busy", "false");
    if (partition) await expect(labels).toHaveAttribute("data-partition", partition);
  }
  async function refresh() {
    await page.getByRole("button", { name: "Refresh label acquisition", exact: true }).click();
    await expect(page.locator("#weather-label-partition-info")).toContainText("retained requests");
    await settled();
  }
  async function selectPartition(partition) {
    await page.locator("#weather-label-partition").selectOption(partition);
    await settled(partition);
  }
  let stateBytes, sealBytes, labelBytes, partitionRows, originalFiles;
  function hashes() {
    const root = path.join(workspace, "runs/weather-labels");
    const inventory = {};
    function walk(dir) {
      for (const item of fs.readdirSync(dir, { withFileTypes: true })) {
        const file = path.join(dir, item.name);
        if (item.isDirectory()) walk(file);
        else if (item.name.endsWith(".json")) inventory[path.relative(root, file)] = sha(fs.readFileSync(file));
      }
    }
    walk(root); return inventory;
  }
  async function verifyReopened(name) {
    await page.goto(origin);
    await expect(page.locator("#weather-schedules")).toContainText("Forward validation · paused");
    assert.deepEqual(await download(name + "-schedule.json", "Download forward validation state"), stateBytes);
    assert.deepEqual(await (await fetch(origin + "/api/weather/label-partitions")).json(), partitionRows);
    await selectPartition("00000000");
    await expect(page.locator("#weather-label-partition-download")).toBeVisible();
    assert.deepEqual(await download(name + "-seal.json", "Download sealed label partition manifest"), sealBytes);
    assert.deepEqual(await download(name + "-labels.json", "Download label evidence"), labelBytes);
    assert.deepEqual(hashes(), originalFiles);
    await shot(name + "-archived", "#weather-label-partition");
  }
  page.on("pageerror", error => { receipt.page_errors.push(error.message); save(); }); save();
  try {
    phase("official"); command(["-m", "tests.integration.label_partition_fixture", workspace], "seed-controlled");
    await start(); await page.goto(origin); await expect(page.locator("#submit")).toBeEnabled();
    await page.locator("#weather-schedule-optin").check();
    await page.locator("#weather-schedule-interval").selectOption("300");
    await page.locator("#weather-schedule-batch").selectOption("1");
    const created = page.waitForResponse(r => r.url() === origin + "/api/weather/schedules" && r.request().method() === "POST");
    await page.getByRole("button", { name: "Enable forward validation", exact: true }).click();
    const response = await created; assert.equal(response.status(), 202); scheduleId = (await response.json()).config.id;
    for (let n = 1; n <= 129; n++) {
      if (n > 1) phase(n === 128 ? "outage" : "official", true);
      const schedule = await waitFor(s => !s.inflight && s.work[0].attempts === n && s.work[0].last_batch);
      assert.equal(schedule.status, "active");
      if ([1, 127, 128, 129].includes(n)) {
        receipt.operations.push({ action: "controlled-batch", sequence: n, schedule }); save();
        await refresh();
        await expect(page.locator("#weather-label-partition-info")).toContainText(`${n} retained requests`);
        await shot("batch-" + n);
      }
      if (n === 128) {
        assert.equal(schedule.counts.retry, 1);
        await selectPartition("00000000");
        await expect(page.locator("#weather-labels")).toContainText("HTTP 503");
        await shot("boundary-outage", "#weather-labels > section:first-child");
      }
    }
    let rows = await (await fetch(origin + "/api/weather/label-partitions")).json();
    assert.deepEqual(rows.map(p => p.requests), [128, 1]);
    assert.deepEqual(rows.map(p => p.status), ["sealed", "active"]);
    await refresh(); await selectPartition("00000001");
    await expect(page.locator("#weather-labels")).toContainText("1 verified scalar labels");
    await shot("rolled-over", "#weather-labels > section:first-child");
    // Running request in the successor partition; browser pause must interrupt with no receipt.
    phase("stall", true);
    await waitFor(s => s.sequence === 130 && s.inflight);
    for (let i = 0; i < 400; i++) {
      const requests = await (await fetch(origin + "/api/weather/labels")).json();
      const startedCalls = fs.readFileSync(phaseFile + ".calls.jsonl", "utf8").trim().split("\n").length;
      if (requests.some(r => r.status === "running") && startedCalls === 130) break;
      await pause(25);
    }
    await page.getByRole("button", { name: "Pause forward validation", exact: true }).click();
    await waitFor(s => s.status === "paused" && !s.inflight);
    await refresh();
    await expect(page.locator("#weather-labels")).toContainText("interrupted");
    await shot("cancelled-successor", "#weather-labels > section:first-child");
    rows = await (await fetch(origin + "/api/weather/label-partitions")).json();
    assert.deepEqual(rows.map(p => p.requests), [128, 2]);
    const all = [];
    for (const row of rows) all.push(...await (await fetch(origin + "/api/weather/label-partitions/" + row.partition_id)).json());
    assert.equal(all.length, 130); assert.equal(new Set(all.map(r => r.id)).size, 130);
    assert.equal(all.filter(r => r.status === "interrupted").length, 1);
    assert(all.flatMap(r => r.receipts).every(r => r.received_at && r.url.startsWith("https://weather.com/kalshi/api/climate/primary?date=")));
    const calls = fs.readFileSync(phaseFile + ".calls.jsonl", "utf8").trim().split("\n").map(JSON.parse);
    assert.equal(calls.length, 130); assert.equal(new Set(calls.map(c => c.request_id)).size, 130);
    receipt.operations.push({ action: "no-duplicate-network-requests", batches: all.length, source_calls: calls.length, distinct_request_ids: 130 }); save();
    fs.writeFileSync(path.join(evidence, "controlled-requests.json"), JSON.stringify(all, null, 2));
    fs.copyFileSync(phaseFile + ".calls.jsonl", path.join(evidence, "controlled-calls.jsonl"));
    await page.getByRole("button", { name: "Freeze retained weather dataset", exact: true }).click();
    await expect(page.locator("#weather-message")).toContainText("Immutable dataset selected");
    await expect(page.locator("#weather-readiness")).toContainText("1 source-matched scalar labels");
    await expect(page.locator("#weather-readiness")).toContainText("insufficient data");
    await shot("frozen-insufficient", "#weather-readiness");
    stateBytes = await download("paused-schedule.json", "Download forward validation state");
    partitionRows = rows;
    await selectPartition("00000000");
    await expect(page.locator("#weather-label-partition-download")).toBeVisible();
    sealBytes = await download("sealed-partition.json", "Download sealed label partition manifest");
    labelBytes = await download("archived-labels.json", "Download label evidence");
    await stop(); originalFiles = hashes();
    fs.writeFileSync(path.join(evidence, "original-label-files.json"), JSON.stringify(originalFiles, null, 2));
    await start(); await verifyReopened("restart"); await stop();
    const archive = path.join(repo, "data/cache", path.basename(workspace) + ".zip");
    command(["-m", "entropytrade.api.recovery", "snapshot", "--workspace", workspace, "--archive", archive], "snapshot");
    const restored = workspace + "-restored";
    command(["-m", "entropytrade.api.recovery", "restore", "--workspace", restored, "--archive", archive], "restore");
    receipt.operations.push({ action: "offline-restore", archive, sha256: sha(fs.readFileSync(archive)), restored }); save();
    workspace = restored; await start(); await verifyReopened("restore");
    assert.equal(fs.readFileSync(phaseFile + ".calls.jsonl", "utf8").trim().split("\n").length, 130);
    assert.deepEqual(receipt.page_errors, []); receipt.status = "passed";
  } catch (error) { receipt.status = "failed"; receipt.failure = error.stack || String(error); throw error; }
  finally { await stop(); receipt.finished_at = new Date().toISOString(); save(); }
});
