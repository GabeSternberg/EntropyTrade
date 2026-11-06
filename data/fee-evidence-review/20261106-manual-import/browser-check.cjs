const { chromium } = require('playwright');
(async () => {
  const b = await chromium.launch(); const p = await b.newPage({ viewport: { width: 1440, height: 1100 } });
  const errors = []; p.on('pageerror', e => errors.push(String(e)));
  await p.goto('http://127.0.0.1:8791');
  const loc = p.locator('#fee-evidence');
  await loc.getByText('OPERATOR MANUAL IMPORT', { exact: false }).first().waitFor({ timeout: 20000 });
  console.log((await loc.innerText()).slice(0, 900));
  const [dl] = await Promise.all([p.waitForEvent('download'), p.getByRole('link', { name: 'Original fee source 1', exact: true }).first().click()]);
  const fs = require('fs'); const path = process.argv[2] + '/dl.bin'; await dl.saveAs(path);
  console.log('download sha256', require('crypto').createHash('sha256').update(fs.readFileSync(path)).digest('hex'));
  await p.screenshot({ path: process.argv[2] + '/manual-import.png', fullPage: false });
  console.log('page errors', errors.length); await b.close();
})().catch(e => { console.error(e); process.exit(1); });
