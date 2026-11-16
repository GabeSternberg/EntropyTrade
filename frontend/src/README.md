# Local website

`uv run entropytrade-web` serves this buildless HTML/CSS/JavaScript application from the
checkout at `http://127.0.0.1:43128`. It calls only the same-origin local API. There is no
frontend package install, bundler, external script, CDN, web font, credential form, order
endpoint or hosting service. The server's strict Content-Security-Policy allows only
same-origin scripts and styles, and it serves a fixed allowlist of files (`ASSETS` in
`backend/src/entropytrade/api/server.py`).

## Structure

| File | Role |
| --- | --- |
| `index.html` | Application shell plus the Research Workbench markup (all original element IDs kept) |
| `style.css` | Design system: dark tokens, layout, components, charts, responsive rules, workbench theme |
| `ui.js` | DOM builders (text nodes only), icons, formatting, cards, tables, tabs, dialogs, SVG charts |
| `demo-data.js` | Deterministic, frozen, fictional Demo Mode sample data (no I/O) |
| `views-markets.js` | Overview and Market Explorer |
| `views-lab.js` | Strategy Lab and Backtesting & Analytics |
| `views-ops.js` | Paper Trading, Data & Operations and Settings |
| `views-research.js` | Persistent research, acquisition, modeling and validation history, evidence gaps, paper eligibility and explicit paper deployment requests |
| `views-cis1990.js` | CIS 1990 course workflow |
| `shell.js` | Data mode, GET reader, guarded explicit writes, hash router, navigation, command palette (⌘K / Ctrl K) |
| `app.js` | The original research workbench logic (research runs, datasets, labels, shadow, fees, gates) |

Routes are hash-based: `#/overview`, `#/markets[/TICKER]`, `#/lab[/STRATEGY]`,
`#/analytics`, `#/paper[/MONITOR]`, `#/research[/JOB]`, `#/workbench`, `#/ops`, `#/settings[/SECTION]`.

## Real Mode and Demo Mode

**Real Mode** (the default) shows only this workspace's data from the local API and renders
honest loading, empty, unavailable and error states. Things the website deliberately does not
read are labeled as unavailable rather than filled in: live Kalshi listings and collector
health (the read-only collector runs as a separate process; `data/cache/chain` is never read),
storage runway (an open V1 gate) and authentic backtest performance (no real run has passed
the evidence gates).

**Demo Mode** is a product preview. Every page shows a persistent "Demo Mode" banner, a
"Demo data · simulated" source chip, "Simulated" card tags and a SIMULATED chart watermark.
Its isolation is enforced at the presentation boundary and covered by tests:

- `demo-data.js` performs no network requests and its data is deep-frozen.
- Views obtain sample data only through `ET.demo()`, which throws outside Demo Mode.
- Views read real data only through `ET.api()`, which issues same-origin `GET` requests to
  `/api/` paths and refuses to run in Demo Mode. Explicit research and paper writes use
  `ET.mutate()`, which rechecks the current mode immediately before dispatch and requires a
  CSRF token. Saved Real Mode handlers cannot write after switching to Demo Mode.
  Deployment requests carry experiment/model references and a fixed compatibility interval;
  the frozen trained schedule controls collection. Models, strategy specifications and risk
  overrides never come from the browser.
- Demo interactions (e.g. "Create simulated draft") stay in browser memory for the session.
- The **Research Workbench always uses the real workspace**, in either mode. The
  workbench (`app.js`) never reads demo data.
- Live order entry and real-money controls remain disabled. Paper deployment requires an
  explicit user action and independently rechecked server eligibility; a disabled button is
  never the financial gate.

The mode, density and sidebar preferences are stored in this browser's `localStorage` only.

## Tests

```bash
node --test frontend/tests/*.test.cjs
uv run pytest backend/tests/unit/test_workbench_http.py
```

The Node tests cover workbench presentation, the data-mode boundary and the demo dataset.
The Python tests check the asset allowlist, CSP-safe scripts and demo isolation. Browser
regression is `frontend/browser/redesign.spec.cjs` (see the browser README); all original
workbench specs open `/#/workbench`.

Formulation in the workbench is template-only: documented signals or complete AND-only
comparisons; synthetic mode uses fixed mock proposals. Provider-backed research is a separate
server configuration with per-run consent. Review completion and successful forward ingestion
never imply historical evaluation. See [the workbench guide](../../docs/workbench.md).


## Research paper deployments

Open a research job's **Paper eligibility** tab to inspect exact model/strategy versions,
validation checks, trained decision schedule and current evidence refusals. An eligible proposal offers **Start paper
deployment**; a previously created deployment links to its existing account. Synthetic
experiments are explicitly labeled and production promotion refuses them.

The Paper Trading page lists the actual workspace accounts. Selecting one shows its frozen
research/model lineage, committed account/positions with their observation clock, current
cost-basis drawdown, execution and risk events, collection cycles and audit history. Headline
totals disclose when they include controlled synthetic accounts. It refreshes every five seconds while open, fetches active or
selected account details and preserves expanded evidence sections. Paused accounts can
resume; suspension and cancellation are terminal. Both retain earlier accounting and source
artifacts. JSON downloads and the original workbench execution view remain available.

No account balance, simulated fill or P&L is invented before a committed incoming-data cycle.
Paper controls cannot edit model coefficients, exchange credentials, fee policies or risk limits.
