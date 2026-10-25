"use strict";
const $ = (id) => document.getElementById(id);
const state = { token: null, job: null, tab: "review", updated: null, busy: false };
const terminal = new Set(["completed", "failed", "cancelled", "interrupted"]);
function node(tag, text, className) {
  const element = document.createElement(tag);
  if (text !== undefined && text !== null) element.textContent = String(text);
  if (className) element.className = className;
  return element;
}
function append(parent, ...children) { children.forEach((child) => parent.append(child)); return parent; }
function panel(title) { return append(node("section", null, "panel"), node("h2", title)); }
function badge(value) {
  const text = String(value).replaceAll("_", " ");
  const kind = /INSUFFICIENT|UNSUPPORTED|interrupted|synthetic/i.test(value) ? "amber" :
    /REJECT|INVALID|failed|cancelled|incomplete|empty/i.test(value) ? "red" : /completed|BACKTESTED|PROMISING/i.test(value) ? "green" : "";
  return node("span", text, `badge ${kind}`);
}
function notice(text, error = false) { return node("div", text, `notice${error ? " error" : ""}`); }
function detail(title, value) {
  return append(node("details"), node("summary", title), node("pre", typeof value === "string" ? value : JSON.stringify(value, null, 2)));
}
function list(items) { return append(node("ul"), ...items.map((text) => node("li", text))); }
function dateText(value) { return new Date(value).toLocaleString(); }
function table(headers, rows) {
  const tableNode = node("table");
  append(tableNode, append(node("thead"), append(node("tr"), ...headers.map((h) => node("th", h)))));
  append(tableNode, append(node("tbody"), ...rows.map((row) => append(node("tr"), ...row.map((value) => node("td", value ?? "—"))))));
  return append(node("div", null, "table-wrap"), tableNode);
}
async function api(path, body) {
  const response = await fetch(path, body === undefined ? {} : {
    method: "POST", headers: { "Content-Type": "application/json", "X-EntropyTrade-CSRF": state.token }, body: JSON.stringify(body),
  });
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || `Request failed (${response.status})`);
  return result;
}
function modeHelp() {
  const bitcoin = $("family").value === "bitcoin";
  for (const option of $("mode").options) option.disabled = bitcoin && option.value !== "public";
  if (bitcoin) $("mode").value = "public";
  const mode = $("mode").value;
  $("mode-help").textContent = mode === "synthetic" ?
    "Generated weather data + mock proposals. Trains models and simulates backtests to verify software; no real performance evidence. May take a few minutes." : mode === "recorded" ?
    "Six historical city/day events across three dates. Certified forecast vintages and scalar highs are absent; expect an insufficient-data result." : bitcoin ?
    "Fetch actual KXBTC contract rules and Coinbase BTC-USD spot. Spot is a covariate, never a settlement label. Forward capture only; no historical evaluation." :
    "Fetch Philadelphia/Chicago contract rules and current Open-Meteo/NWS forecast vintages. New receipts cannot backfill historical features or outcomes.";
  $("reasoning").options[0].textContent = mode === "synthetic" ? "Explicit mock proposals · software demonstration" : "Local templates · no provider credentials";
  $("reasoning-help").hidden = mode === "synthetic";
}
async function history() {
  const rows = await api("/api/jobs");
  $("history").replaceChildren();
  if (!rows.length) $("history").append(node("p", "Your research history will appear here.", "hint"));
  rows.forEach((job) => {
    const button = append(node("button", null, `history-item${state.job?.id === job.id ? " selected" : ""}`),
      node("span", job.request.idea, "idea"), append(node("span", null, "meta"), badge(job.status), node("span", `${job.request.family} · ${job.request.mode}`)), node("span", dateText(job.created_at), "hint"));
    button.type = "button";
    button.addEventListener("click", () => selectJob(job.id));
    $("history").append(button);
  });
}
async function selectJob(id) {
  state.updated = null;
  state.tab = "review";
  const job = await api(`/api/jobs/${id}`);
  state.job = job;
  renderJob();
  await history();
}
function renderJob() {
  const job = state.job;
  state.updated = job.updated_at;
  const header = node("section", null, "panel");
  const tools = node("div", null, "run-tools");
  if (!terminal.has(job.status)) {
    const cancel = node("button", "Cancel run"); cancel.type = "button";
    cancel.addEventListener("click", async () => {
      try { await api(`/api/jobs/${job.id}/cancel`, {}); await selectJob(job.id); }
      catch (error) { $("connection").replaceChildren(notice(error.message, true)); }
    }); tools.append(cancel);
  }
  if (job.result) {
    const report = node("a", "Text report"); report.href = `/api/jobs/${job.id}/report`; report.download = `entropytrade-${job.id}.txt`;
    const review = node("a", "Review JSON"); review.href = `/api/jobs/${job.id}/review`; review.download = `entropytrade-${job.id}.json`;
    append(tools, report, review);
  }
  append(header, append(node("div", null, "run-top"), node("p", "02 / RESEARCH RUN", "eyebrow"), tools), node("h2", job.request.idea, "run-title"),
    append(node("div", null, "meta"), badge(job.status), badge(job.request.mode === "synthetic" ? "SYNTHETIC" : "REAL EVIDENCE"), node("span", `${job.request.family} · ${dateText(job.created_at)}`)), node("p", job.detail, "hint"));
  $("run-header").replaceChildren(header);
  const timeline = append(node("details", null, "panel timeline"), node("summary", `Run progress · ${job.events.length} recorded stages`));
  if (!terminal.has(job.status)) timeline.open = true;
  timeline.append(append(node("ol"), ...job.events.map((event) => append(node("li"), node("strong", event.stage), node("div", event.detail), node("time", dateText(event.at))))));
  $("progress").replaceChildren(timeline);
  $("tabs").hidden = !job.result;
  renderResult();
}
function renderResult() {
  const job = state.job, result = job.result;
  document.querySelectorAll("[data-tab]").forEach((button) => button.setAttribute("aria-pressed", String(button.dataset.tab === state.tab)));
  const content = $("result-content"); content.replaceChildren();
  if (!result) {
    content.append(notice(terminal.has(job.status) ? `${job.detail}. No completed review is available. Partial artifacts are retained locally.` : "The bounded worker is preparing this run. You can leave this page open; progress and saved history update automatically."));
    return;
  }
  content.append(notice(`${result.data_kind === "synthetic" ? "SYNTHETIC SOFTWARE DEMONSTRATION. " : "REAL EVIDENCE. "}${result.reasoning_limit} Final holdout is excluded.`));
  if (result.acquisition) renderAcquisition(content, result.acquisition);
  if (state.tab === "review") renderReview(content, result);
  if (state.tab === "probabilities") renderProbabilities(content, result);
  if (state.tab === "lineage") renderLineage(content, result);
}
function renderAcquisition(content, acquisition) {
  const section = panel(acquisition.headline);
  section.classList.add("acquisition", acquisition.status);
  section.append(node("p", acquisition.counts, "acquisition-counts"), notice(acquisition.evaluation_limit, acquisition.status !== "complete"));
  if (acquisition.failure_summaries.length) append(section, node("h3", "Acquisition failures"), list(acquisition.failure_summaries));
  else section.append(node("p", "No acquisition failures recorded.", "hint"));
  section.append(node("p", `Capture (UTC): ${acquisition.started_at} → ${acquisition.decision_time}. Universe complete: ${acquisition.universe_complete}. History complete: ${acquisition.history_complete}.`, "hint"), list(acquisition.limitations));
  content.append(section);
}
function renderReview(content, result) {
  const coverage = result.coverage, stats = node("div", null, "stats");
  [[coverage.independent_events, "Independent events"], [coverage.date_blocks, "Date blocks"], [coverage.eligible_events, "Eligible feature events"], [coverage.scalar_label_events, "Source-matched labels"]].forEach(([value, label]) => stats.append(append(node("div", null, "stat"), node("strong", value), node("span", label))));
  content.append(stats);
  if (result.formulation) content.append(append(panel("Formulation limits"), list(result.formulation.limitations)));
  result.candidates.forEach((candidate) => {
    const proposal = result.proposals.find((p) => p.candidate_id === candidate.candidate_id);
    const hypothesis = result.hypotheses.find((h) => h.hypothesis_id === proposal?.hypothesis_id);
    const decision = result.decisions.find((d) => d.candidate_id === candidate.candidate_id);
    const card = node("article", null, "panel candidate");
    append(card, append(node("div", null, "candidate-title"), node("h2", proposal?.spec?.name || candidate.candidate_id), badge(candidate.status)), node("p", hypothesis?.mechanism, "mechanism"),
      node("p", "Experiment decision", "label"), list(candidate.reasons.length ? candidate.reasons : ["Inspect validation and execution diagnostics below."]));
    if (hypothesis) append(card, node("p", "Falsification", "label"), node("p", hypothesis.falsification, "small"), detail("Typed hypothesis", hypothesis));
    if (candidate.forecast_metrics) card.append(detail("Forecast validation metrics", candidate.forecast_metrics));
    else card.append(node("p", "No eligible forecast validation metrics. Missing history is not replaced with estimated performance.", "hint"));
    if (candidate.scenarios?.length) {
      append(card, node("p", "Simulated execution scenarios · never observed fills", "label"), table(["Scenario", "Fills", "Simulated P&L", "Fees", "Drawdown at cost"], candidate.scenarios.map((s) => [s.scenario, s.fill_count, s.net_pnl, s.fees_paid, s.drawdown_at_cost])), detail("Full execution diagnostics", candidate.scenarios));
    }
    if (decision) card.append(detail("Independent research gates and criticism", decision));
    card.append(detail(proposal?.spec ? "Strategy specification" : "Unsupported proposal", proposal?.spec || proposal));
    content.append(card);
  });
  content.append(append(panel("Evaluation limits"), list(result.warnings)));
}
function renderProbabilities(content, result) {
  const section = panel("Validation probabilities");
  section.append(node("p", `Showing ${result.probabilities.length} of ${result.probability_count} permitted prediction records (limit ${result.probability_limit}). Only validation probabilities used by the experiment are exposed.`, "small"));
  if (!result.probabilities.length) section.append(notice("No eligible fitted probability records exist for this run. Current spot prices, forecasts and market quotes do not supply a probability model."));
  else section.append(table(["Contract", "Decision (UTC)", "Model", "P(YES)", "Fit as of", "Calibration as of"], result.probabilities.map((p) => [p.market_ticker, p.decision_time, p.model, Number(p.probability_yes).toFixed(4), p.fit_asof, p.calibration_asof])));
  section.append(detail("Prediction identities and feature/model lineage", result.probabilities));
  content.append(section);
}
function renderLineage(content, result) {
  const lineage = panel("Reproducible identities");
  const identities = append(node("ul", null, "evidence-list"), ...Object.entries({ experiment_id: result.experiment_id, research_run: result.research_run, ...result.lineage }).map(([key, value]) => append(node("li"), node("strong", key), node("code", typeof value === "string" ? value : JSON.stringify(value)))));
  append(lineage, identities, node("p", `${result.lineage.requested_trial_count} candidate/scenario trials requested. Final holdout evaluated: ${result.final_holdout_evaluated}.`, "hint")); content.append(lineage);
  if (result.public_evidence) {
    const evidence = panel("Public source evidence");
    append(evidence, list(result.public_evidence.limitations), detail("Capture receipts, clocks and acquisition failures", result.public_evidence.capture));
    if (result.public_evidence.capture.family === "bitcoin") evidence.append(notice("Bitcoin settlement sources remain unresolved and rules_known is false. Authority mentions preserve rule text; they do not verify settlement authority."));
    for (const contract of result.public_evidence.contracts) evidence.append(detail(`${contract.ticker} · actual rules and available features`, contract));
    evidence.append(detail("Immutable public input manifest", result.public_manifest)); content.append(evidence);
  }
  const artifacts = panel("Saved artifact checksums");
  append(artifacts, node("p", "Artifact paths are relative to this run's local workflow directory. Review downloads contain the protected result projection; the server does not expose arbitrary local files.", "small"), table(["Artifact", "SHA-256", "Bytes"], result.artifacts.map((a) => [a.path, a.sha256, a.bytes])), detail("Coverage and point-in-time boundaries", result.coverage)); content.append(artifacts);
}
$("family").addEventListener("change", modeHelp); $("mode").addEventListener("change", modeHelp);
document.querySelectorAll("[data-example]").forEach((button) => button.addEventListener("click", () => {
  const example = button.dataset.example;
  $("family").value = example === "bitcoin" ? "bitcoin" : "weather";
  $("mode").value = example === "synthetic" ? "synthetic" : example === "bitcoin" ? "public" : "recorded";
  $("idea").value = example === "bitcoin" ? "Does Bitcoin spot relative to the actual strike help estimate KXBTC probabilities?" : example === "synthetic" ? "Demonstrate temporal modeling and execution gates on explicitly synthetic weather data." : "Do upward forecast revisions improve weather contract probabilities?";
  modeHelp(); $("idea").focus();
}));
document.querySelectorAll("[data-tab]").forEach((button) => button.addEventListener("click", () => { state.tab = button.dataset.tab; renderResult(); }));
$("refresh").addEventListener("click", () => history().catch((error) => $("connection").replaceChildren(notice(error.message, true))));
$("research-form").addEventListener("submit", async (event) => {
  event.preventDefault(); if (!state.token) return;
  $("submit").disabled = true; $("form-message").textContent = "Saving research request…";
  try {
    const response = await api("/api/jobs", { idea: $("idea").value, family: $("family").value, mode: $("mode").value });
    await selectJob(response.id); $("form-message").textContent = "Request saved. Follow its progress on the right.";
  } catch (error) { $("form-message").textContent = error.message; }
  finally { $("submit").disabled = false; }
});
async function initialize() {
  modeHelp(); $("submit").disabled = true;
  try { const catalog = await api("/api/catalog"); state.token = catalog.csrf_token; await history(); $("submit").disabled = false; }
  catch (error) { $("connection").replaceChildren(notice(`Cannot connect to the local workbench: ${error.message}. Reload after the server is available.`, true)); }
}
setInterval(async () => {
  if (state.busy) return;
  state.busy = true;
  try {
    if (state.job && !terminal.has(state.job.status)) {
      const requestedId = state.job.id;
      const job = await api(`/api/jobs/${requestedId}`);
      if (state.job.id === requestedId && job.updated_at !== state.updated) { state.job = job; renderJob(); await history(); }
    }
    $("connection").replaceChildren();
  } catch (error) { $("connection").replaceChildren(notice(`Progress connection interrupted: ${error.message}. Retrying…`, true)); }
  finally { state.busy = false; }
}, 1500);
initialize();
