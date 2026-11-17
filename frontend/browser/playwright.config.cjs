const path = require("node:path");
const { defineConfig, chromium } = require("@playwright/test");

const evidence = process.env.ENTROPYTRADE_BROWSER_EVIDENCE;
if (!evidence || !path.isAbsolute(evidence)) {
  throw new Error("Set ENTROPYTRADE_BROWSER_EVIDENCE to a NEW absolute evidence directory");
}
// Never select a Chrome channel, user profile, CDP endpoint or system executable.
process.env.PLAYWRIGHT_BROWSERS_PATH ||= path.join(__dirname, ".browsers");

module.exports = defineConfig({
  testDir: __dirname,
  testMatch: ["workbench.spec.cjs", "bitcoin-history.spec.cjs", "shadow.spec.cjs", "recovery.spec.cjs", "provider.spec.cjs", "weather-history.spec.cjs", "weather-labels.spec.cjs", "forward-validation.spec.cjs", "label-partitions.spec.cjs", "shadow-history.spec.cjs", "fees.spec.cjs", "paper.spec.cjs", "alerts.spec.cjs", "prospective.spec.cjs", "redesign.spec.cjs", "cis1990.spec.cjs", "research.spec.cjs", "research-paper.spec.cjs", "readiness.spec.cjs", "lifecycle.spec.cjs"],
  workers: 1,
  retries: 0,
  timeout: 600_000,
  expect: { timeout: 10_000 },
  outputDir: path.join(evidence, "playwright-artifacts"),
  reporter: [
    ["list"],
    ["json", { outputFile: path.join(evidence, "playwright-results.json") }],
    ["junit", { outputFile: path.join(evidence, "playwright-results.xml") }],
  ],
  use: {
    browserName: "chromium",
    headless: true,
    launchOptions: { executablePath: chromium.executablePath() },
    viewport: { width: 1440, height: 1100 },
    locale: "en-US",
    timezoneId: "UTC",
    acceptDownloads: true,
    trace: "on",
    screenshot: "only-on-failure",
  },
});
