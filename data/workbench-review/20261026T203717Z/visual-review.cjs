// Supplemental readable crops made by real browser screenshots of persisted UI.
// No screenshot editing or application/source changes.
const fs = require("node:fs");
const path = require("node:path");
const { spawn } = require("node:child_process");
const { createHash } = require("node:crypto");
const assert = require("node:assert/strict");
const repo = path.resolve(__dirname, "../../..");
process.env.PLAYWRIGHT_BROWSERS_PATH = path.join(repo, "frontend/browser/.browsers");
const { chromium } = require(path.join(repo, "frontend/browser/node_modules/playwright"));
const receipt = JSON.parse(fs.readFileSync(path.join(__dirname, "browser-attempt-2/browser-receipt.json")));
const output = path.join(__dirname, "visual-review");
assert(!fs.existsSync(output), "Never overwrite prior screenshots");
fs.mkdirSync(output);
const now = () => new Date().toISOString();
const review = { started_at_utc: now(), screenshots: [], observations: [], outcome: "running" };
const save = () => fs.writeFileSync(path.join(output, "receipt.json"), JSON.stringify(review, null, 2) + "\n");
const pause = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

(async () => {
  let browser;
  let server;
  try {
    const occupied = await fetch(receipt.origin + "/api/catalog").catch(() => null);
    assert(!occupied, "Existing listener must not be touched");
    const log = fs.openSync(path.join(output, "server.log"), "w");
    server = spawn(path.join(repo, ".venv/bin/python"), ["-m", "entropytrade.api.server", "--workspace", path.join(repo, receipt.workspace)], {
      cwd: repo, env: { PATH: "/usr/bin:/bin", PYTHONNOUSERSITE: "1", PYTHONDONTWRITEBYTECODE: "1", TZ: "UTC", TMPDIR: "/private/tmp" },
      stdio: ["ignore", log, log],
    });
    fs.closeSync(log);
    for (let i = 0; i < 100; i++) {
      const ready = await fetch(receipt.origin + "/api/catalog").catch(() => null);
      if (ready?.ok) break;
      assert(server.exitCode === null, "Backend exited"); await pause(100);
    }
    browser = await chromium.launch({ headless: true, executablePath: chromium.executablePath() });
    const page = await browser.newPage({ viewport: { width: 1440, height: 1100 }, timezoneId: "UTC" });
    await page.goto(receipt.origin); await page.locator("#submit").waitFor({ state: "visible" });
    async function capture(name, locator) {
      const file = name + ".png";
      if (locator) await locator.screenshot({ path: path.join(output, file) });
      else await page.screenshot({ path: path.join(output, file), fullPage: false });
      review.screenshots.push({ at_utc: now(), file, sha256: createHash("sha256").update(fs.readFileSync(path.join(output, file))).digest("hex") }); save();
    }
    for (const label of ["synthetic-weather", "public-weather", "public-bitcoin", "public-bitcoin-network-denied"]) {
      const run = receipt.runs.find((r) => r.label === label);
      await page.locator("#history .history-item").filter({ has: page.getByText(run.idea, { exact: true }) }).click();
      if (label === "synthetic-weather") {
        await capture("synthetic-negative-control", page.locator("article.candidate").last());
        await page.getByRole("button", { name: "Probabilities", exact: true }).click();
        await page.locator("#tabs").scrollIntoViewIfNeeded();
        await capture("synthetic-validation-probabilities");
      } else {
        for (const tab of ["Review", "Probabilities", "Evidence & lineage"]) {
          await page.getByRole("button", { name: tab, exact: true }).click();
          await capture(`${label}-${tab.split(" ")[0].toLowerCase()}-acquisition`, page.locator("#result-content .acquisition"));
        }
        if (label === "public-bitcoin") {
          const contract = page.locator("#result-content details").filter({ has: page.locator("summary", { hasText: "actual rules and available features" }) }).first();
          await contract.locator("summary").click();
          await capture("bitcoin-contract-rules-authority-mentions", contract);
        }
      }
      review.observations.push({ label, job_id: run.job_id, inspected_at_utc: now() }); save();
    }
    review.outcome = "passed";
  } catch (error) { review.outcome = "failed"; review.error = error.stack; process.exitCode = 1; }
  finally {
    if (browser) await browser.close();
    if (server && server.exitCode === null) {
      server.kill("SIGINT");
      for (let i = 0; i < 100 && server.exitCode === null && server.signalCode === null; i++) await pause(100);
      if (server.exitCode === null && server.signalCode === null) { server.kill("SIGKILL"); review.outcome = "failed"; review.cleanup_error = "Server did not exit gracefully"; process.exitCode = 1; }
    }
    review.finished_at_utc = now(); save();
  }
})();
