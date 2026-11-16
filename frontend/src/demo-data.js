"use strict";
// DEMO MODE SAMPLE DATA — FICTIONAL. Deterministically generated in the browser for product
// previews. It is never sent to the server: this file performs no network requests, and the
// data layer (shell.js) refuses to hand it to any view unless Demo Mode is active. Nothing
// here is a historical result, a market record, model evidence or trading performance.
(function () {
  const ET = (window.ET = window.ET || {});
  const DATA_KIND = "demo";
  const NOW = Date.UTC(2026, 10, 14, 15, 30, 0); // fixed demo clock for reproducible screenshots
  const HOUR = 3600e3; const DAY = 24 * HOUR;

  function rng(seed) {
    let a = seed >>> 0;
    return function () {
      a = (a + 0x6d2b79f5) >>> 0;
      let t = a;
      t = Math.imul(t ^ (t >>> 15), t | 1);
      t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }
  function hash(text) { let x = 2166136261; for (const ch of text) { x ^= ch.charCodeAt(0); x = Math.imul(x, 16777619); } return x >>> 0; }
  const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));
  const round = (v, d = 2) => Math.round(v * 10 ** d) / 10 ** d;
  function gauss(r) { return Math.sqrt(-2 * Math.log(r() || 1e-9)) * Math.cos(2 * Math.PI * r()); }
  function pick(r, list) { return list[Math.floor(r() * list.length)]; }
  function hex(r, n = 12) { let out = ""; for (let i = 0; i < n; i += 1) out += Math.floor(r() * 16).toString(16); return out; }

  // ------------------------------------------------------------- markets
  const CITIES = [["PHIL", "Philadelphia"], ["CHI", "Chicago"], ["NY", "New York"], ["AUS", "Austin"], ["MIA", "Miami"], ["DEN", "Denver"], ["LAX", "Los Angeles"]];
  function marketDefs() {
    const defs = [];
    const r = rng(7);
    CITIES.forEach(([code, city], ci) => {
      const base = [52, 44, 50, 71, 79, 47, 68][ci];
      [-2, 0, 2].forEach((off) => defs.push({
        series: `KXHIGH${code}`, category: "Weather", event: `KXHIGH${code}-26NOV15`, ticker: `KXHIGH${code}-26NOV15-T${base + off}`,
        title: `${city} high above ${base + off}°F on Nov 15?`, source: "NWS Climatological Report (daily)", close: NOW + 15.5 * HOUR, fair: clamp(0.5 - off * 0.14 + gauss(r) * 0.06, 0.04, 0.96),
      }));
    });
    ["NY", "CHI", "SEA"].forEach((code, i) => defs.push({
      series: `KXRAIN${code}`, category: "Weather", event: `KXRAIN${code}-26NOV`, ticker: `KXRAIN${code}-26NOV-T${[3, 2, 5][i]}`,
      title: `${["New York", "Chicago", "Seattle"][i]} November rainfall above ${[3, 2, 5][i]} in?`, source: "NOAA monthly climate summary", close: NOW + 16.4 * DAY, fair: [0.42, 0.37, 0.61][i],
    }));
    [94000, 96000, 98000, 100000, 102000].forEach((k, i) => defs.push({
      series: "KXBTCD", category: "Crypto", event: "KXBTCD-26NOV1417", ticker: `KXBTCD-26NOV1417-T${k}`, title: `Bitcoin above $${k.toLocaleString()} at 5pm ET today?`,
      source: "CF Benchmarks BRTI (60s average)", close: NOW + 6.5 * HOUR, fair: [0.91, 0.78, 0.52, 0.27, 0.11][i],
    }));
    [3400, 3600, 3800].forEach((k, i) => defs.push({
      series: "KXETHD", category: "Crypto", event: "KXETHD-26NOV1417", ticker: `KXETHD-26NOV1417-T${k}`, title: `Ethereum above $${k.toLocaleString()} at 5pm ET today?`,
      source: "CF Benchmarks ETH RR", close: NOW + 6.5 * HOUR, fair: [0.83, 0.49, 0.18][i],
    }));
    [["KXCPI", "CPI month-over-month above 0.2% in November?", 0.46, 26], ["KXCPICORE", "Core CPI YoY above 3.0% in November?", 0.39, 26], ["KXFED", "Fed cuts rates at the December meeting?", 0.63, 33], ["KXFEDHOLD", "Fed holds rates at the December meeting?", 0.35, 33], ["KXPAYROLLS", "November payrolls above 150K?", 0.52, 20], ["KXUNRATE", "Unemployment rate at or above 4.4% in November?", 0.31, 20], ["KXGDP", "Q4 GDP advance estimate above 2.0%?", 0.57, 75], ["KXJOBLESS", "Initial jobless claims above 230K next week?", 0.44, 5]].forEach(([series, title, fair, days]) => defs.push({
      series, category: "Economics", event: `${series}-26DEC`, ticker: `${series}-26DEC-T1`, title, source: series.startsWith("KXFED") ? "FOMC statement" : "BLS / BEA release", close: NOW + days * DAY, fair,
    }));
    [["KXINX", "S&P 500 closes above 6,200 today?", 0.58, 0.5], ["KXINXW", "S&P 500 up this week?", 0.66, 2.5], ["KXNASDAQ", "Nasdaq-100 closes above 22,000 today?", 0.41, 0.5], ["KXWTI", "WTI crude above $72 on Friday?", 0.47, 0.5], ["KXGOLD", "Gold above $2,800 at month end?", 0.55, 16], ["KXTNOTE", "10Y Treasury yield above 4.25% Friday?", 0.38, 0.5], ["KXEURUSD", "EUR/USD above 1.08 on Friday?", 0.52, 0.5]].forEach(([series, title, fair, days]) => defs.push({
      series, category: "Financials", event: `${series}-26NOV14`, ticker: `${series}-26NOV14-T1`, title, source: "Exchange official close", close: NOW + days * DAY, fair,
    }));
    [["KXHURR", "Atlantic hurricane season ends with 16+ named storms?", 0.71, 16], ["KXARCTIC", "Arctic sea-ice extent record low in March?", 0.23, 130], ["KXTEMPGLOBE", "November 2026 the warmest on record?", 0.48, 40], ["KXSNOWNYC", "Measurable snow in Central Park before Dec 1?", 0.18, 16]].forEach(([series, title, fair, days]) => defs.push({
      series, category: "Climate", event: `${series}-26`, ticker: `${series}-26-T1`, title, source: "NOAA / NSIDC", close: NOW + days * DAY, fair,
    }));
    return defs;
  }
  function priceHistory(ticker, fair, points = 168, stepMs = HOUR) {
    const r = rng(hash(ticker));
    let p = clamp(fair + gauss(r) * 0.12, 0.03, 0.97);
    const out = [];
    for (let i = points - 1; i >= 0; i -= 1) {
      p = clamp(p + (fair - p) * 0.035 + gauss(r) * 0.018, 0.01, 0.99);
      out.push({ t: NOW - i * stepMs, p: round(p, 3), v: Math.round(40 + r() * 400 * (1 + Math.abs(gauss(r)))) });
    }
    return out;
  }
  const markets = marketDefs().map((def) => {
    const r = rng(hash(def.ticker) ^ 99);
    const hist = priceHistory(def.ticker, def.fair);
    const last = hist[hist.length - 1].p;
    const dayAgo = hist[hist.length - 25].p;
    const spread = round(clamp(0.01 + r() * (def.category === "Climate" ? 0.06 : 0.04), 0.01, 0.08), 2);
    const yesBid = round(clamp(last - spread / 2, 0.01, 0.98), 2);
    const yesAsk = round(clamp(yesBid + spread, 0.02, 0.99), 2);
    const model = def.category === "Weather" || def.category === "Crypto" ? round(clamp(def.fair + gauss(r) * 0.05, 0.02, 0.98), 3) : null;
    const volume = Math.round((def.category === "Crypto" ? 60000 : def.category === "Economics" ? 42000 : 9000) * (0.3 + r() * 1.6));
    return {
      ...def, data_kind: DATA_KIND, status: "open", last, change_24h: round(last - dayAgo, 3), yes_bid: yesBid, yes_ask: yesAsk, spread,
      volume_24h: volume, open_interest: Math.round(volume * (1.5 + r() * 4)), liquidity: Math.round(800 + r() * 24000),
      model_prob: model, edge: model === null ? null : round(model - (yesBid + yesAsk) / 2, 3), spark: hist.slice(-48).map((x) => x.p),
      rules: `Resolves YES if the official ${def.source} value satisfies the contract condition at expiration. Otherwise resolves NO. Settlement uses the first final published value; revisions after settlement are ignored.`,
    };
  });
  ["KXHIGHPHIL-26NOV13-T51", "KXHIGHCHI-26NOV13-T44", "KXBTCD-26NOV1317-T96000"].forEach((ticker, i) => {
    markets.push({ series: ticker.split("-")[0], category: i === 2 ? "Crypto" : "Weather", event: ticker.split("-").slice(0, 2).join("-"), ticker, title: ["Philadelphia high above 51°F on Nov 13?", "Chicago high above 44°F on Nov 13?", "Bitcoin above $96,000 at 5pm ET Nov 13?"][i], source: i === 2 ? "CF Benchmarks BRTI (60s average)" : "NWS Climatological Report (daily)", close: NOW - (i + 1) * 20 * HOUR, fair: [1, 0, 1][i], data_kind: DATA_KIND, status: "settled", result: ["yes", "no", "yes"][i], last: [0.99, 0.01, 0.99][i], change_24h: [0.31, -0.22, 0.12][i], yes_bid: null, yes_ask: null, spread: null, volume_24h: [8420, 6120, 51200][i], open_interest: 0, liquidity: 0, model_prob: null, edge: null, spark: priceHistory(ticker, [1, 0, 1][i]).slice(-48).map((x) => x.p), rules: "Settled. Final value published by the official source." });
  });

  // ---------------------------------------------------------- strategies
  function equity(seed, days, drift, vol, start = 10000) {
    // Standardize seeded noise so the sample drift/volatility hit their targets exactly.
    const r = rng(seed); const z = Array.from({ length: days }, () => gauss(r));
    const mean = z.reduce((a, b) => a + b, 0) / days;
    const sd = Math.sqrt(z.reduce((a, b) => a + (b - mean) ** 2, 0) / days) || 1;
    let v = start; const out = [];
    z.forEach((value, k) => { if (k) v *= 1 + drift + ((value - mean) / sd) * vol; out.push({ x: NOW - (days - 1 - k) * DAY, y: round(v, 2) }); });
    return out;
  }
  function drawdown(series) { let peak = -Infinity; return series.map((p) => { peak = Math.max(peak, p.y); return { x: p.x, y: round(p.y / peak - 1, 4) }; }); }
  function stats(series) {
    const rets = series.slice(1).map((p, i) => p.y / series[i].y - 1);
    const mean = rets.reduce((a, b) => a + b, 0) / rets.length;
    const sd = Math.sqrt(rets.reduce((a, b) => a + (b - mean) ** 2, 0) / rets.length);
    return { total_return: round(series[series.length - 1].y / series[0].y - 1, 4), sharpe: round((mean / sd) * Math.sqrt(365), 2), max_drawdown: Math.min(...drawdown(series).map((p) => p.y)), daily_returns: rets };
  }
  const STRATS = [
    { id: "stg-forecast-revision", name: "Forecast revision drift", family: "Weather · daily high", status: "paper", approval: "Approved for paper", hypothesis: "Upward revisions of the official NWS high-temperature forecast in the final 18 hours are under-reflected in YES prices for threshold contracts near the forecast.", signal: "revision_f >= 1.25 AND hours_to_close < 18", sizing: "Fractional Kelly (0.15), max 40 contracts", seed: 11, drift: 0.0007, vol: 0.0085 },
    { id: "stg-ensemble-disagreement", name: "Ensemble disagreement fade", family: "Weather · daily high", status: "shadow", approval: "Approved for shadow", hypothesis: "When Open-Meteo and NWS forecasts disagree by more than 3°F, markets overprice the tail contracts; fade the extremes.", signal: "abs(forecast_disagreement_f) > 3.0 AND price_yes > 0.70", sizing: "Fixed $50 per event", seed: 23, drift: 0.0005, vol: 0.008 },
    { id: "stg-btc-spot-gap", name: "BTC spot–strike gap", family: "Crypto · BTC hourly", status: "validated", approval: "Pending review", hypothesis: "Short-dated BTC threshold contracts lag the spot-implied probability from a volatility-scaled distance to strike.", signal: "spot_gap_sigma > 0.8 AND minutes_to_close BETWEEN 20 AND 120", sizing: "Fractional Kelly (0.10), max 25 contracts", seed: 37, drift: 0.0008, vol: 0.011 },
    { id: "stg-cpi-consensus", name: "CPI consensus skew", family: "Economics · CPI", status: "backtested", approval: "Not requested", hypothesis: "Markets overweight the published consensus relative to nowcast models in the final week before CPI releases.", signal: "nowcast_minus_consensus_bp >= 8", sizing: "Fixed 10 contracts", seed: 41, drift: 0.00025, vol: 0.009 },
    { id: "stg-overnight-bias", name: "Overnight low bias", family: "Weather · daily high", status: "research", approval: "Not requested", hypothesis: "Model warm bias in overnight lows carries into next-day high contracts in coastal cities.", signal: "bias_f(7d) >= 1.5 AND coastal == true", sizing: "Fixed 5 contracts", seed: 53, drift: -0.0002, vol: 0.008 },
    { id: "stg-fed-path", name: "Fed path vs. futures", family: "Economics · FOMC", status: "draft", approval: "Not requested", hypothesis: "Event contracts on FOMC decisions deviate from fed-funds-futures-implied probabilities by more than fees in the final 48 hours.", signal: "abs(futures_implied - price_yes) > 0.06", sizing: "Not specified", seed: 67, drift: 0, vol: 0 },
  ];
  const strategies = STRATS.map((st, idx) => {
    const r = rng(st.seed);
    const hasBacktest = st.status !== "draft" && st.status !== "research";
    const curve = hasBacktest ? equity(st.seed, 240, st.drift, st.vol) : [];
    const st2 = hasBacktest ? stats(curve) : null;
    const trades = hasBacktest ? Math.round(180 + r() * 900) : 0;
    const trade_pnls = hasBacktest ? Array.from({ length: Math.min(trades, 400) }, () => round(gauss(r) * 18 + st.drift * 4000, 2)) : [];
    const wins = trade_pnls.filter((x) => x > 0).length;
    return {
      ...st, data_kind: DATA_KIND, created_at: NOW - (40 - idx * 5) * DAY, updated_at: NOW - (idx * 7 + 2) * HOUR,
      assumptions: ["Fees from the reviewed schedule effective at each decision time", "Fills at displayed top-of-book depth only; no queue priority", "Hold to settlement; no early exit", "Final protected holdout excluded from every fit"],
      universe: st.family.startsWith("Weather") ? "7 cities · threshold contracts within ±4°F of forecast" : st.family.startsWith("Crypto") ? "KXBTCD hourly strikes within ±3% of spot" : "Monthly release contracts",
      metrics: hasBacktest ? { total_return: st2.total_return, sharpe: st2.sharpe, max_drawdown: st2.max_drawdown, win_rate: round(wins / trade_pnls.length, 3), trades, profit_factor: round(trade_pnls.filter((x) => x > 0).reduce((a, b) => a + b, 0) / Math.abs(trade_pnls.filter((x) => x < 0).reduce((a, b) => a + b, 0) || 1), 2), brier: round(0.17 + r() * 0.05, 4), log_loss: round(0.5 + r() * 0.08, 4), avg_edge: round(0.015 + r() * 0.03, 3) } : null,
      equity: curve, trade_pnls, returns: st2 ? st2.daily_returns : [],
    };
  });

  const MODELS = [["Market-implied baseline", 0.214, 0.612, 0.041, 0.71], ["Logistic (forecast + revision)", 0.191, 0.566, 0.028, 0.77], ["Gradient-boosted trees", 0.184, 0.551, 0.034, 0.79], ["Calibrated ensemble", 0.179, 0.539, 0.017, 0.80]];
  const models = MODELS.map(([name, brier, log_loss, ece, auc], idx) => {
    const r = rng(300 + idx);
    const bins = Array.from({ length: 10 }, (_, i) => { const p = (i + 0.5) / 10; return { p: round(p, 3), o: round(clamp(p + gauss(r) * ece * 1.4 + (idx === 0 ? (p - 0.5) * -0.12 : 0), 0.01, 0.99), 3), n: Math.round(30 + r() * 140) }; });
    return { name, brier, log_loss, ece, auc, bins, events: 1184, data_kind: DATA_KIND };
  });

  const EXP_KINDS = ["Walk-forward backtest", "Calibration study", "Fee sensitivity", "Model comparison", "Ablation: drop revision feature", "Prospective shadow evaluation"];
  const experiments = [];
  strategies.forEach((st, si) => {
    const r = rng(500 + si);
    const count = st.status === "draft" ? 0 : st.status === "research" ? 2 : 3 + Math.floor(r() * 2);
    for (let i = 0; i < count; i += 1) {
      const status = i === 0 && st.status === "research" ? "running" : r() < 0.12 ? "failed" : "completed";
      const verdict = status !== "completed" ? null : pick(r, ["PROMISING", "PROMISING", "INSUFFICIENT_DATA", "REJECTED"]);
      experiments.push({ id: `exp-${hex(r, 8)}`, strategy_id: st.id, strategy: st.name, kind: EXP_KINDS[(si + i) % EXP_KINDS.length], status, verdict, created_at: NOW - (si * 3 + i * 2 + 1) * DAY - Math.round(r() * 20) * HOUR, duration_s: Math.round(40 + r() * 900), events: Math.round(300 + r() * 1400), dataset: `ds-${hex(r, 10)}`, brier: status === "completed" ? round(0.17 + r() * 0.06, 4) : null, log_loss: status === "completed" ? round(0.5 + r() * 0.1, 4) : null, folds: 6, data_kind: DATA_KIND });
    }
  });
  experiments.sort((a, b) => b.created_at - a.created_at);

  function walkForward(st) {
    const r = rng(hash(st.id) ^ 5);
    return Array.from({ length: 6 }, (_, i) => ({ fold: i + 1, train: `${fmtMonth(-12 + i)} – ${fmtMonth(-7 + i)}`, test: fmtMonth(-6 + i), events: Math.round(110 + r() * 90), brier: round(0.17 + r() * 0.05, 4), market_brier: round(0.2 + r() * 0.03, 4), return: round(st.drift * 30 + gauss(r) * 0.03, 4), trades: Math.round(20 + r() * 80) }));
  }
  function fmtMonth(offset) { const d = new Date(NOW); d.setUTCMonth(d.getUTCMonth() + offset); return d.toLocaleDateString("en-US", { month: "short", year: "2-digit", timeZone: "UTC" }); }
  function feeGrid(st) {
    const fees = [0, 0.5, 1, 1.5, 2]; const slips = [0, 1, 2, 3, 4];
    const base = st.metrics ? st.metrics.total_return : 0;
    return { rows: fees.map((f) => `${f.toFixed(1)}× fees`), cols: slips.map((x) => `${x}¢`), values: fees.map((f) => slips.map((x) => round(base - (f - 1) * 0.045 - x * 0.028, 4))) }; // 1× fees, 0¢ = reported backtest
  }
  function sufficiency(st) {
    const r = rng(hash(st.id) ^ 9);
    return Array.from({ length: 12 }, (_, i) => ({ label: fmtMonth(-11 + i), value: Math.round(60 + i * 9 + r() * 40), required: 100 }));
  }

  // -------------------------------------------------------- paper trading
  const paperCurve = (() => { const r = rng(808); let v = 10000; const out = []; for (let i = 29 * 24; i >= 0; i -= 1) { v += gauss(r) * 9 + 1.15; out.push({ x: NOW - i * HOUR, y: round(v, 2) }); } return out; })();
  const open = markets.filter((m) => m.status === "open");
  const positions = [0, 4, 9, 24, 12, 26, 29, 16].map((i, k) => {
    const m = open[i % open.length]; const r = rng(900 + k);
    const side = k === 4 || k === 6 ? "NO" : "YES";
    const mark = side === "YES" ? m.last : round(1 - m.last, 2);
    const entry = round(clamp(mark - 0.06 + r() * 0.1, 0.03, 0.96), 2);
    const qty = Math.min(Math.round(60 + r() * 340), Math.floor(240 / entry)); // per-event cap $250
    const strat = strategies[[0, 0, 1, 2, 1, 2, 2, 0][k]];
    return { ticker: m.ticker, title: m.title, category: m.category, side, qty, entry, mark, cost: round(qty * entry, 2), value: round(qty * mark, 2), pnl: round(qty * (mark - entry), 2), pnl_pct: round(mark / entry - 1, 4), strategy: strat.name, strategy_id: strat.id, opened_at: NOW - (k * 5 + 2) * HOUR, close: m.close, data_kind: DATA_KIND };
  });
  const fills = Array.from({ length: 28 }, (_, i) => {
    const r = rng(1200 + i); const m = open[Math.floor(r() * open.length)];
    const side = r() < 0.7 ? "YES" : "NO"; const qty = Math.round(4 + r() * 30); const price = round(clamp(m.last + gauss(r) * 0.03, 0.02, 0.98), 2);
    const settled = i > 14 && r() < 0.6;
    return { id: `fill-${hex(r, 8)}`, at: NOW - i * 3.3 * HOUR - Math.round(r() * 50) * 60e3, ticker: m.ticker, category: m.category, side, action: settled ? "Settle" : "Buy", qty, price, fee: round(Math.ceil(0.07 * qty * price * (1 - price) * 100) / 100, 2), liquidity: r() < 0.8 ? "Taker" : "Maker", strategy: strategies[Math.floor(r() * 3)].name, realized: settled ? round(gauss(r) * 18 + 4, 2) : null, data_kind: DATA_KIND };
  });
  const orders = Array.from({ length: 12 }, (_, i) => {
    const r = rng(1500 + i); const m = open[Math.floor(r() * open.length)];
    const status = ["resting", "resting", "filled", "partially filled", "cancelled", "rejected"][i % 6];
    const qty = Math.round(5 + r() * 30);
    return { id: `ord-${hex(r, 8)}`, at: NOW - i * 2.1 * HOUR, ticker: m.ticker, side: r() < 0.7 ? "YES" : "NO", type: "Limit", qty, filled: status === "filled" ? qty : status === "partially filled" ? Math.round(qty / 2) : 0, limit: round(clamp(m.yes_bid ?? 0.5, 0.02, 0.98), 2), status, reason: status === "rejected" ? "Per-event cap would be exceeded (risk check: max_event_exposure)" : status === "cancelled" ? "Book older than 30s at decision time" : "", strategy: strategies[i % 3].name, data_kind: DATA_KIND };
  });
  const realized = fills.filter((f) => f.realized !== null).reduce((a, f) => a + f.realized, 0);
  const unrealized = positions.reduce((a, p) => a + p.pnl, 0);
  const deployed = positions.reduce((a, p) => a + p.cost, 0);
  const equityNow = paperCurve[paperCurve.length - 1].y;
  const paper = {
    data_kind: DATA_KIND, name: "Demo paper account", started_at: NOW - 30 * DAY, starting_balance: 10000, equity: equityNow, cash: round(equityNow - positions.reduce((a, p) => a + p.value, 0), 2), deployed: round(deployed, 2),
    realized_pnl: round(realized + 214.6, 2), unrealized_pnl: round(unrealized, 2), fees_paid: round(fills.reduce((a, f) => a + f.fee, 0) + 38.2, 2), today_pnl: round(equityNow - paperCurve[paperCurve.length - 25].y, 2),
    curve: paperCurve, positions, fills, orders,
    by_strategy: strategies.slice(0, 3).map((st, i) => ({ id: st.id, name: st.name, pnl: [312.4, 96.8, 184.1][i], trades: [64, 22, 41][i], win_rate: [0.56, 0.53, 0.55][i], exposure: round(positions.filter((x) => x.strategy_id === st.id).reduce((a, x) => a + x.cost, 0), 2) })),
    by_category: [["Weather", 409.2], ["Crypto", 184.1]].map(([name, pnl]) => ({ name, pnl, exposure: round(positions.filter((x) => x.category === name).reduce((a, x) => a + x.cost, 0), 2) })),
    daily_pnl: Array.from({ length: 30 }, (_, i) => ({ label: new Date(NOW - (29 - i) * DAY).toLocaleDateString("en-US", { month: "short", day: "numeric", timeZone: "UTC" }), value: round(paperCurve[Math.min(paperCurve.length - 1, (i + 1) * 24)].y - paperCurve[i * 24].y, 2) })),
    limits: [
      { name: "Per-trade notional", used: 38.4, limit: 50, unit: "usd" }, { name: "Per-event exposure", used: round(Math.max(...positions.map((x) => x.cost)), 0), limit: 250, unit: "usd" },
      { name: "Total deployed", used: round(deployed, 0), limit: 4000, unit: "usd" }, { name: "Daily realized loss", used: 41.2, limit: 200, unit: "usd" },
      { name: "Drawdown from peak", used: 2.1, limit: 8, unit: "pct" }, { name: "Open orders", used: 2, limit: 20, unit: "count" },
    ],
  };

  // ------------------------------------------------------------ operations
  const COLLECTORS = [
    ["Kalshi market listings", "REST · 60s", "ok", 42, 1440, 0.002, 180], ["Kalshi order books", "REST · 30s", "ok", 18, 2880, 0.006, 240],
    ["Open-Meteo forecasts", "HTTP · hourly", "ok", 12 * 60, 168, 0, 420], ["NWS gridpoint forecasts", "HTTP · hourly", "degraded", 74 * 60, 151, 0.101, 890],
    ["NWS climate reports (CLI)", "HTTP · daily", "ok", 5.2 * 3600, 14, 0, 310], ["Coinbase BTC-USD spot", "REST · 15s", "ok", 9, 5760, 0.001, 95],
    ["Fee schedule documents", "Manual review", "stale", 9 * DAY / 1000, 0, 0, null],
  ];
  const collectors = COLLECTORS.map(([name, cadence, status, age, receipts, err, latency], i) => {
    const r = rng(2000 + i);
    return { name, cadence, status, last_success: NOW - age * 1000, receipts_24h: receipts, error_rate: err, latency_ms: latency, history: Array.from({ length: 24 }, () => (status === "degraded" && r() < 0.2 ? 0 : 1)), data_kind: DATA_KIND };
  });
  const collection_history = Array.from({ length: 14 }, (_, i) => { const r = rng(2100 + i); return { label: new Date(NOW - (13 - i) * DAY).toLocaleDateString("en-US", { month: "short", day: "numeric", timeZone: "UTC" }), value: Math.round(9800 + r() * 900 - (i === 9 ? 3400 : 0)), note: i === 9 ? "Collector restart · 4h gap (recovered)" : "" }; });
  const coverage = CITIES.map(([code, city], i) => { const r = rng(2200 + i); return { city, code, forecast: round(0.86 + r() * 0.14, 3), settlement: round(0.72 + r() * 0.26, 3), days: Math.round(48 + r() * 30), pending_labels: Math.round(r() * 4) }; });
  const quality_alerts = [
    { id: "dq-1", severity: "warning", title: "NWS gridpoint latency elevated", detail: "p95 latency 890 ms; 10% of hourly pulls retried in the last 24h.", at: NOW - 52 * 60e3, source: "NWS gridpoint forecasts" },
    { id: "dq-2", severity: "warning", title: "Fee evidence older than review window", detail: "The latest reviewed fee document was received 9 days ago. Costed intentions continue to cite the effective version.", at: NOW - 3 * HOUR, source: "Fee schedule documents" },
    { id: "dq-3", severity: "info", title: "Preliminary settlement label superseded", detail: "Chicago Nov 12 high revised 44°F → 45°F in the final CLI report; label version re-sealed.", at: NOW - 19 * HOUR, source: "NWS climate reports (CLI)" },
    { id: "dq-4", severity: "critical", title: "Order-book snapshot gap", detail: "4h gap on Nov 10 after collector restart. Affected decisions marked ineligible; no backfill.", at: NOW - 4 * DAY, source: "Kalshi order books", resolved: true },
  ];
  const snapshots = Array.from({ length: 6 }, (_, i) => { const r = rng(2300 + i); return { id: `snap-${hex(r, 6)}`, kind: ["Weather history partition", "Label partition", "Order-book archive", "Research cohort", "Weather history partition", "Fee evidence version"][i], created_at: NOW - i * 1.6 * DAY, status: i === 0 ? "active" : "sealed", records: Math.round(800 + r() * 9000), size: Math.round(2e6 + r() * 9e7), sha256: hex(r, 64), data_kind: DATA_KIND }; });
  const storage = { used: 184.6e9, capacity: 500e9, growth_per_day: 2.35e9, data_kind: DATA_KIND, breakdown: [["Order-book archive", 121.2e9], ["Market listings", 31.4e9], ["Forecast receipts", 18.9e9], ["Research runs & models", 9.7e9], ["Labels & fee evidence", 3.4e9]] };

  const alerts = [
    { id: "al-1", kind: "Stale collection", severity: "warning", at: NOW - 52 * 60e3, title: "NWS forecast pull delayed", detail: "Last successful pull 74 min ago (SLA 60 min).", route: "#/ops" },
    { id: "al-2", kind: "Risk", severity: "info", at: NOW - 2.1 * HOUR, title: "Order rejected by per-event cap", detail: "Forecast revision drift · KXHIGHCHI-26NOV15", route: "#/paper" },
    { id: "al-3", kind: "Research", severity: "ok", at: NOW - 5 * HOUR, title: "Walk-forward run completed", detail: "BTC spot–strike gap · 6 folds · PROMISING", route: "#/lab" },
    { id: "al-4", kind: "Data quality", severity: "info", at: NOW - 19 * HOUR, title: "Settlement label revised", detail: "Chicago Nov 12 high 44°F → 45°F", route: "#/ops" },
  ];
  const gates = [
    ["authentic_forward_validation", "Authentic history and forward validation", "attested"], ["certified_fees", "Certified effective fees", "attested"],
    ["provider_verification", "Authorized research-provider verification", "attested"], ["second_family", "User-approved second major family", "attested"],
    ["sustained_operation", "Sustained authentic paper/shadow operation", "open"], ["storage_runway", "Evidence storage runway decision", "open"],
    ["public_acceptance", "Public acquisition and browser acceptance", "attested"], ["final_acceptance", "Independent final V1 acceptance", "open"],
  ].map(([gate_id, title, status]) => ({ gate_id, title, status, detail: status === "attested" ? "Simulated attestation (demo)" : "No attestation (demo)" }));

  const providers = [
    { name: "Local templates", status: "ready", detail: "Deterministic formulation, no credentials" },
    { name: "Anthropic research provider", status: "configured", detail: "Model configured · per-run consent required" },
    { name: "OpenAI research provider", status: "not configured", detail: "No server configuration" },
  ];

  // A fictional autonomous-research job with the same shape as a real job detail.
  const research = (() => {
    const iso = (ms) => new Date(ms).toISOString();
    const scope = "Demo data. Research eligibility only; no hypothesis is an established edge and no order path exists.";
    const facets = (p, pt, e, et) => ({ predictive: { satisfied: p, total: pt, ready: p === pt }, execution: { satisfied: e, total: et, ready: e === et }, unregistered_features: [], unimplemented_features: [] });
    const hyp = (id, title, status, rationale, features, f, reasons) => ({
      hypothesis_id: id, status, reasons, facets: f, searches: 1, spec: {
        title, rationale, version: 1, features: features.map((name) => ({ name, role: "feature" })), label: { name: "settlement_high_f", role: "label" },
        provenance: { generator: "local_templates", template_id: "demo" }, universe: ["KXHIGHPHIL"],
        decision_schedule: [{ day_offset: -1, local_time: "18:00:00" }, { day_offset: 0, local_time: "10:00:00" }], candidate_models: ["market_baseline", "gaussian_error"],
        rules: [], timestamp_semantics: "Demo: forecasts count only when issued before the decision time.", validation_plan: "Demo: time-ordered partitions with an embargo.",
        leakage_risks: ["Demo: a day's own report is published after it ends."], invalidation: ["Demo: no improvement over the market-implied baseline."],
      } });
    const req = (kind, variable, entity, status, available, required, predictive, reason) => ({ requirement_id: `r-demo-${kind}`, kind, variable, entity, clock: kind.includes("forecast") || kind === "reference_observations" ? "issuance" : "receipt", predictive_for: predictive ? ["h-demo00000001"] : [], hypotheses: ["h-demo00000001", "h-demo00000002"], assessment: { status, events_available: available, events_required: required, reasons: [`${available} of ${required} independent dates available`, reason].filter(Boolean) } });
    const job = {
      id: "00000000-0000-4000-8000-00000000d3m0", family: "weather", universe: ["KXHIGHPHIL"], status: "awaiting_observations",
      detail: "Demo: predictive evidence acquired; awaiting decision-time quotes from the collector",
      request: { objective: "Find profitable strategies for Kalshi daily temperature markets using weather forecasts. (Demo)", provider: { provider: "local_templates", model_name: "" } },
      created_at: iso(NOW - 3 * HOUR), updated_at: iso(NOW - 40 * 60e3), checkpoint: {}, error: null, scope,
      usage: { ai_usd: "0", ai_requests: 0, input_tokens: 0, output_tokens: 0, http_requests: 96, bytes: 7_400_000, runtime_seconds: 212 },
      hypothesis_counts: { awaiting_new_observations: 4, needs_more_data: 1 },
      hypotheses: [
        hyp("h-demo00000001", "NWS forecast bias against the settlement high", "awaiting_new_observations", "Demo rationale: a bias-corrected official forecast may price threshold contracts differently from the market.", ["nws_pfm_max_f", "nws_cli_bias_f"], facets(4, 4, 0, 3), ["Demo: decision quotes (yes_quotes) with receipt clocks: 9 of 60 independent dates available"]),
        hyp("h-demo00000002", "Delayed market adjustment after forecast revisions", "awaiting_new_observations", "Demo rationale: prices may adjust gradually after a forecast revision.", ["nws_pfm_revision_f", "market_implied_probability"], facets(2, 3, 0, 3), ["Demo: market quotes are collected prospectively"]),
        hyp("h-demo00000003", "Mispricing during elevated forecast uncertainty", "needs_more_data", "Demo rationale: prices may understate ensemble spread.", ["ensemble_std_f", "market_implied_probability"], facets(1, 3, 0, 3), ["Demo: ensemble members are not captured by the collector; a configuration change needs a human."]),
      ],
      requirements: [
        req("forecast_vintages", "daytime_max_f", "CLIPHL", "satisfied", 64, 60, true),
        req("reference_observations", "daily_high_f", "CLIPHL", "satisfied", 64, 60, true),
        req("settlement_labels", "daily_high_f", "CLIPHL", "satisfied", 62, 60, true),
        req("decision_quotes", "yes_quotes", "KXHIGHPHIL", "awaiting_observations", 9, 60, false, "Demo: historical quotes are not available from any approved source"),
        req("forecast_vintages", "ensemble_member_f", "CLIPHL", "unobtainable", 0, 60, true, "Demo: no approved historical source with issuance clocks"),
      ],
      resolutions: {},
      sources: [
        { source_id: "iem-nws-pfm", name: "NWS Point Forecast Matrix archive (demo)", kind: "forecast_vintages", entity: "CLIPHL", decision: "acquire", reasons: ["Demo: issuance clocks from product headers"] },
        { source_id: "open-meteo-previous-runs", name: "Open-Meteo previous runs (demo)", kind: "forecast_vintages", entity: "CLIPHL", decision: "reject", reasons: ["Demo: values carry no issuance clock"] },
        { source_id: "kalshi-orderbook-forward", name: "Kalshi order books (forward, demo)", kind: "decision_quotes", entity: "KXHIGHPHIL", decision: "forward_collect", reasons: ["Demo: prospective only"] },
      ],
      acquisitions: [
        { source_id: "iem-nws-pfm", params: { entity: "CLIPHL", start: "2026-09-12", end: "2026-11-12" }, status: "completed", requests: 9, bytes: 6_100_000, dataset_id: "sha256:demo-pfm", detail: "Demo: 268 products parsed" },
        { source_id: "weather-company-labels", params: { entity: "CLIPHL", start: "2026-09-12", end: "2026-11-12" }, status: "completed", requests: 62, bytes: 1_200_000, dataset_id: "sha256:demo-labels", detail: "Demo: 62 official highs" },
      ],
      features: [
        { feature_id: "nws_pfm_max_f", version: "1", unit: "degF", entity: "CLIPHL", rows: 128, non_null: 126, events: 64, artifact_id: "sha256:demo-feature-1", inputs: ["sha256:demo-pfm"] },
        { feature_id: "nws_cli_bias_f", version: "1", unit: "degF", entity: "CLIPHL", rows: 128, non_null: 110, events: 55, artifact_id: "sha256:demo-feature-2", inputs: ["sha256:demo-pfm", "sha256:demo-cli"] },
      ],
      forward_requests: [
        { kind: "decision_quotes", variable: "yes_quotes", entity: "KXHIGHPHIL", collector: "canonical_local_chain", status: "awaiting_observations", events_observed: 9, events_required: 60, next_check_at: iso(NOW + 20 * HOUR), detail: "Demo: covered by the canonical collector configuration" },
      ],
      events: [
        { sequence: 1, at: iso(NOW - 3 * HOUR), stage: "queued", detail: "Demo: request saved" },
        { sequence: 2, at: iso(NOW - 3 * HOUR + 2e3), stage: "planning_data", detail: "Demo: 5 hypotheses recorded" },
        { sequence: 3, at: iso(NOW - 2.9 * HOUR), stage: "acquiring_data", detail: "Demo: acquiring NWS products and labels" },
        { sequence: 4, at: iso(NOW - 40 * 60e3), stage: "awaiting_observations", detail: "Demo: awaiting decision-time quotes" },
      ],
    };
    return { jobs: [job] };
  })();

  function deepFreeze(value) { if (value && typeof value === "object" && !Object.isFrozen(value)) { Object.freeze(value); Object.values(value).forEach(deepFreeze); } return value; }
  ET.demoData = deepFreeze({
    data_kind: DATA_KIND, now: NOW, markets, strategies, experiments, models, paper, collectors, collection_history, coverage, quality_alerts, snapshots, storage, alerts, gates, providers, research,
  });
  // Pure, deterministic helpers (no I/O).
  ET.demoTools = Object.freeze({ priceHistory, walkForward, feeGrid, sufficiency, drawdown, NOW, DAY, HOUR });
})();
