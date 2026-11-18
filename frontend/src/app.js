"use strict";
const $ = (id) => document.getElementById(id);
const state = { token: null, job: null, tab: "review", updated: null, busy: false, monitor: null, provider: null, weatherDatasets: [] };
// The legacy workbench has its own transport, but shares the shell's current mode and
// route boundary. Every activation owns an epoch; leaving it invalidates reads, writes,
// saved controls and responses even if this same workbench is opened again immediately.
const legacy = { active: false, epoch: 0, ready: false, pending: null, timer: null, controller: null };
function legacyVisible() {
  const shell = globalThis.window?.ET;
  return shell?.mode?.() === "real" && shell.workbenchActive?.() === true &&
    $("workbench-view")?.hidden === false && document.visibilityState !== "hidden";
}
function inactiveError() { return Object.assign(new Error("The Real workbench is inactive"), { cancelled: true }); }
function requireLegacy(epoch = legacy.epoch) {
  if (!legacy.active || epoch !== legacy.epoch || !legacyVisible()) throw inactiveError();
  return epoch;
}
function currentLegacy(epoch) { return legacy.active && epoch === legacy.epoch && legacyVisible(); }
function workbenchBusy(value) {
  $("workbench-view").inert = value;
  $("workbench-view").setAttribute("aria-busy", String(value));
}
const staticListeners = [];
function listen(element, type, handler) {
  // Static form controls survive navigation. Controls rendered from saved records belong
  // to the activation that rendered them, and can never act on a later activation.
  const binding = { element, type, handler, wrapper: null };
  bindListener(binding);
  if (!legacy.active) staticListeners.push(binding);
}
function bindListener(binding) {
  const { element, type, handler } = binding, epoch = legacy.epoch;
  if (binding.wrapper) element.removeEventListener(type, binding.wrapper);
  binding.wrapper = (event) => {
    if (!legacy.ready || !currentLegacy(epoch)) {
      event.preventDefault?.(); event.stopImmediatePropagation?.(); return;
    }
    try {
      return Promise.resolve(handler(event, epoch)).catch((error) => {
        if (!error.cancelled && currentLegacy(epoch)) $("connection").replaceChildren(notice(error.message, true));
      });
    } catch (error) {
      if (!error.cancelled && currentLegacy(epoch)) $("connection").replaceChildren(notice(error.message, true));
    }
  };
  element.addEventListener(type, binding.wrapper);
}
const terminal = new Set(["completed", "failed", "cancelled", "interrupted"]);
function node(tag, text, className) {
  const element = document.createElement(tag);
  if (text !== undefined && text !== null) element.textContent = String(text);
  if (className) element.className = className;
  if (tag === "a") listen(element, "click", () => {});
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
async function api(path, body, epoch = requireLegacy()) {
  requireLegacy(epoch);
  try {
    const response = await fetch(path, {
      method: body === undefined ? "GET" : "POST", credentials: "same-origin", signal: legacy.controller?.signal,
      ...(body === undefined ? {} : {
        headers: { "Content-Type": "application/json", "X-EntropyTrade-CSRF": state.token }, body: JSON.stringify(body),
      }),
    });
    requireLegacy(epoch);
    const result = await response.json();
    requireLegacy(epoch);
    if (!response.ok) throw new Error(result.error || `Request failed (${response.status})`);
    return result;
  } catch (error) {
    requireLegacy(epoch); // An aborted/stale request is never a connection error in a newer view.
    throw error;
  }
}
function modeHelp() {
  const bitcoin = $("family").value === "bitcoin";
  for (const option of $("mode").options) option.disabled = bitcoin ? !["public", "history"].includes(option.value) : option.value === "history";
  if (bitcoin && !["public", "history"].includes($("mode").value)) $("mode").value = "public";
  if (!bitcoin && $("mode").value === "history") $("mode").value = "recorded";
  const mode = $("mode").value;
  $("mode-help").textContent = mode === "synthetic" ?
    "Generated weather data + mock proposals. Trains models and simulates backtests to verify software; no real performance evidence. May take a few minutes." : mode === "history" ?
    "Reuse completed Bitcoin captures in this workspace, fetch up to ten later official results, and test binary models only with enough independent receipt-time history. Repeat captures on different dates; a current fetch cannot backfill old decisions. No execution returns." : mode === "weather_history" ?
    "Use the selected immutable dataset of retained weather receipts. Review readiness and exact evidence shortages below. Models fit only through existing evidence gates; holdout dates remain frozen." : mode === "recorded" ?
    "Six historical city/day events across three dates. Certified forecast vintages and scalar highs are absent; expect an insufficient-data result." : bitcoin ?
    "Fetch actual KXBTC contract rules and Coinbase BTC-USD spot. Spot is a covariate, never a settlement label. Forward capture only; no historical evaluation." :
    "Fetch Philadelphia/Chicago contract rules and current Open-Meteo/NWS forecast vintages. New receipts cannot backfill historical features or outcomes.";
  $("reasoning").options[0].textContent = mode === "synthetic" ? "Explicit mock proposals · software demonstration" : "Local templates · no provider credentials";
  $("reasoning").options[1].disabled = !state.provider || mode === "synthetic";
  if (mode === "synthetic") $("reasoning").value = "local";
  reasoningHelp();
}
function reasoningHelp() {
  const provider = $("reasoning").value === "provider";
  $("provider-options").hidden = !provider;
  $("reasoning-help").hidden = provider || $("mode").value === "synthetic";
  $("enable-provider").checked = false;
  $("enable-provider").required = provider;
  $("provider-help").textContent = state.provider ? `Server configuration: ${state.provider.provider} / ${state.provider.model_name}. Missing credentials or provider errors produce a saved failure; no mock fallback.` : "Configure the research provider/model on the server to enable this option.";
}
async function history(epoch = requireLegacy()) {
  const rows = await api("/api/jobs", undefined, epoch); requireLegacy(epoch);
  $("history").replaceChildren();
  if (!rows.length) $("history").append(node("p", "Your research history will appear here.", "hint"));
  rows.forEach((job) => {
    const button = append(node("button", null, `history-item${state.job?.id === job.id ? " selected" : ""}`),
      node("span", job.request.idea, "idea"), append(node("span", null, "meta"), badge(job.status), node("span", `${job.request.family} · ${job.request.mode}`)), node("span", dateText(job.created_at), "hint"));
    button.type = "button";
    listen(button, "click", () => selectJob(job.id));
    $("history").append(button);
  });
}
let jobSelection = 0;
async function selectJob(id, epoch = requireLegacy()) {
  requireLegacy(epoch);
  const selection = ++jobSelection;
  state.updated = null;
  state.tab = "review";
  const job = await api(`/api/jobs/${id}`, undefined, epoch); requireLegacy(epoch);
  if (selection !== jobSelection) return;
  state.job = job;
  renderJob();
  await history(epoch);
}
function renderJob() {
  const job = state.job;
  state.updated = job.updated_at;
  const header = node("section", null, "panel");
  const tools = node("div", null, "run-tools");
  if (!terminal.has(job.status)) {
    const cancel = node("button", "Cancel run"); cancel.type = "button";
    listen(cancel, "click", async (_, epoch) => {
      try { await api(`/api/jobs/${job.id}/cancel`, {}, epoch); requireLegacy(epoch); await selectJob(job.id, epoch); }
      catch (error) { if (error.cancelled) return; $("connection").replaceChildren(notice(error.message, true)); }
    }); tools.append(cancel);
  }
  if (job.result) {
    const report = node("a", "Text report"); report.href = `/api/jobs/${job.id}/report`; report.download = `entropytrade-${job.id}.txt`;
    const review = node("a", "Review JSON"); review.href = `/api/jobs/${job.id}/review`; review.download = `entropytrade-${job.id}.json`;
    append(tools, report, review);
    if (job.result.artifacts?.some(a => a.path === "fee-evidence.json")) {
      const fees = node("a", "Experiment fee evidence"); fees.href = `/api/jobs/${job.id}/fee-evidence`; fees.download = `experiment-fees-${job.id}.json`; tools.append(fees);
    }
    if (job.result.artifacts?.some(a => a.path === "shadow-replay.json")) {
      const inputs = node("a", "Shadow experiment inputs"); inputs.href = `/api/jobs/${job.id}/shadow-inputs`; inputs.download = `shadow-inputs-${job.id}.json`; tools.append(inputs);
    }
  }
  append(header, append(node("div", null, "run-top"), node("p", "02 / RESEARCH RUN", "eyebrow"), tools), node("h2", job.request.idea, "run-title"),
    append(node("div", null, "meta"), badge(job.status), badge(job.request.mode === "synthetic" ? "SYNTHETIC" : "REAL EVIDENCE"), node("span", `${job.request.family} · ${dateText(job.created_at)}`)), node("p", job.detail, "hint"));
  $("run-header").replaceChildren(header);
  const timeline = append(node("details", null, "panel timeline"), node("summary", `Run progress · ${job.events.length} recorded stages`));
  if (!terminal.has(job.status)) timeline.open = true;
  timeline.append(append(node("ol"), ...job.events.map((event) => append(node("li"), node("strong", event.stage), node("div", event.detail), node("time", dateText(event.at))))));
  $("progress").replaceChildren(timeline);
  $("tabs").hidden = !job.result;
  shadowCandidates();
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
  if (result.weather_history) renderWeatherHistory(content, result.weather_history);
  if (result.bitcoin_history) renderBitcoinHistory(content, result.bitcoin_history);
  if (result.research) {
    const research = panel(`Research orchestration · ${result.reasoning}`);
    research.append(node("p", `Provider: ${result.research.provider ? `${result.research.provider.provider} / ${result.research.provider.model_name}` : "none"}. Status: ${result.research.status}.`, "hint"));
    if (result.research.failure) research.append(notice(`${result.research.failure.type} at ${result.research.failure.stage}: ${result.research.failure.reason}`, true));
    research.append(detail("Research stages, evidence tools, budgets and usage", result.research));
    content.append(research);
  }
  if (result.status === "research_failed") content.append(notice("Research failed. No candidates validated and no deterministic experiments ran. Failure evidence and report remain downloadable.", true));
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
function renderWeatherHistory(content, snapshot) {
  const r = snapshot.readiness;
  const section = panel("Retained weather dataset · " + r.status.replaceAll("_", " "));
  section.classList.add("weather-history");
  section.append(node("code", snapshot.dataset_id), node("p", `${snapshot.capture_count} captures · ${snapshot.observation_count} deduplicated observations · ${r.independent_events} events on ${r.date_blocks} dates · ${r.protected_events} protected events.`),
    node("p", `${r.eligible_events} eligible forecast events · ${r.scalar_label_events} source-matched scalar labels · ${r.binary_label_events} binary-label events (unprotected).`),
    table(["Partition", "Events / dates", "Timely matched labels", "Required", "Shortage", "Label cutoff"], Object.entries(r.partitions).map(([name, p]) => [name, `${p.events} / ${p.dates}`, p.timely_source_matched_events, p.minimum_events, p.shortage, p.label_cutoff])),
    list(r.blockers), list(r.limitations));
  if (r.shadow_audit) section.append(node("p", `${r.shadow_audit.verified_cycles} verified shadow cycles · ${r.shadow_audit.decision_samples} exact decision samples · ${r.shadow_audit.sized_books} sized books · ${r.shadow_audit.stale_books} stale books.`), notice(r.shadow_audit.limitation), list(r.shadow_audit.execution_blockers || []), detail("Shadow replay lineage", r.shadow_audit));
  if (r.cohort) section.append(node("p", `Research cohort · ${r.cohort.batches.length} retained history partitions · at most ${r.cohort.partition_size} inputs per batch. Shared frozen calendar; independent events counted once.`), detail("Cohort batches and immutable identities", r.cohort));
  if (snapshot.identity?.selection) section.append(detail("Selected history and outcome partitions", snapshot.identity.selection));
  if (r.label_acquisition) section.append(detail("Settlement label provenance and refusals", r.label_acquisition));
  if (r.capture_audit) section.append(node("p", `${r.incomplete_captures} incomplete captures · ${r.capture_failures} acquisition failures.`), detail("Original capture clocks, receipts and acquisition failures", r.capture_audit));
  content.append(section);
}
// Refresh clicks and partition changes can overlap; only the newest request may render, so
// rows never describe a partition other than the one selected. aria-busy marks completion.
let weatherLabelsSequence = 0;
async function weatherLabels(epoch = requireLegacy()) {
  requireLegacy(epoch);
  const sequence = ++weatherLabelsSequence;
  const content = $("weather-labels");
  content.setAttribute("aria-busy", "true");
  try { await renderWeatherLabels(sequence, content, epoch); }
  finally { if (currentLegacy(epoch) && sequence === weatherLabelsSequence) content.setAttribute("aria-busy", "false"); }
}
async function renderWeatherLabels(sequence, content, epoch) {
  const partitions = await api("/api/weather/label-partitions", undefined, epoch); requireLegacy(epoch);
  if (sequence !== weatherLabelsSequence) return;
  const select = $("weather-label-partition");
  const previous = select.value;
  select.replaceChildren();
  for (const partition of partitions) {
    const option = node("option", `${partition.partition_id} · ${partition.status} · ${partition.requests}/${partition.request_limit} requests`);
    option.value = partition.partition_id; select.append(option);
  }
  select.value = partitions.some(p => p.partition_id === previous) ? previous : partitions.at(-1)?.partition_id || "";
  const selected = partitions.find(p => p.partition_id === select.value);
  $("weather-label-partition-info").textContent = `${partitions.length} label partitions · ${partitions.reduce((n, p) => n + p.requests, 0)} retained requests. Each partition holds at most 128 requests; sealed receipts stay immutable. Select a partition to inspect all its requests.`;
  const manifest = $("weather-label-partition-download");
  manifest.hidden = selected?.status !== "sealed";
  manifest.href = `/api/weather/label-partitions/${select.value}/manifest`;
  manifest.download = `label-partition-${select.value}.json`;
  const partition = select.value;
  const rows = selected ? await api("/api/weather/label-partitions/" + partition, undefined, epoch) : [];
  requireLegacy(epoch);
  if (sequence !== weatherLabelsSequence) return;
  content.replaceChildren(); content.dataset.partition = partition;
  for (const request of rows.slice().reverse()) {
    const section = panel("Label acquisition · " + request.status);
    section.append(node("p", request.detail), node("code", request.id));
    if (request.result) {
      const result = request.result;
      section.append(node("p", `${result.verified_events} verified scalar labels · ${result.refused_events} refused events. Receipt availability is never backdated.`));
      section.append(detail("Source receipts, rule bindings and label clocks", result));
      const link = node("a", "Download label evidence");
      link.href = "/api/weather/labels/" + result.version.slice(7);
      link.download = "weather-labels-" + request.id + ".json"; section.append(link);
    }
    content.append(section);
  }
}
listen($("weather-label-partition"), "change", () => weatherLabels().catch(error => { if (error.cancelled) return; $("weather-label-message").textContent = error.message; }));
listen($("weather-label-refresh"), "click", () => weatherLabels().catch(error => { if (error.cancelled) return; $("weather-label-message").textContent = error.message; }));
listen($("weather-label-partition-download"), "click", () => {});
listen($("weather-label-acquire"), "click", async (_, epoch) => {
  $("weather-label-acquire").disabled = true;
  try {
    const dataset_id = $("weather-dataset").value;
    if (!dataset_id) throw new Error("Freeze and select a retained weather dataset first.");
    await api("/api/weather/labels", { id: crypto.randomUUID(), dataset_id }, epoch); requireLegacy(epoch);
    $("weather-label-message").textContent = "Acquisition queued. Refresh to inspect receipts and refusals, then freeze a new dataset to include verified labels.";
    await weatherLabels(epoch);
  } catch (error) { if (error.cancelled) return; $("weather-label-message").textContent = error.message; }
  finally { if (currentLegacy(epoch)) $("weather-label-acquire").disabled = false; }
});
async function weatherSchedules(epoch = requireLegacy()) {
  const rows = await api("/api/weather/schedules", undefined, epoch); requireLegacy(epoch);
  const encoded = JSON.stringify(rows);
  if (state.scheduleJSON === encoded) return;
  state.scheduleJSON = encoded;
  const content = $("weather-schedules"); content.replaceChildren();
  if (!rows.length) content.append(node("p", "No continuous validation enabled. Label collection is opt-in.", "hint"));
  for (const schedule of rows) {
    const section = panel("Forward validation · " + schedule.status);
    section.dataset.scheduleId = schedule.config.id;
    section.append(node("code", schedule.config.id), node("p", schedule.detail),
      node("p", `${schedule.counts.pending || 0} pending · ${schedule.counts.retry || 0} retry · ${schedule.counts.verified || 0} verified · ${schedule.counts.refused || 0} refused dates`),
      node("p", `At most ${schedule.config.batch_dates} dates per batch · retry starts at ${schedule.config.interval_seconds} seconds · ${schedule.config.follow_retained ? "Following retained public/shadow weather inputs" : "Selected immutable dataset"}.`),
      node("p", schedule.limitation));
    if (schedule.inflight) section.append(node("p", "Active batch: " + schedule.inflight));
    section.append(table(["Date", "State", "Attempts", "Next check", "Detail"], schedule.work.map(w => [w.day, w.status, w.attempts, w.next_at, w.detail])));
    const action = schedule.status === "active" ? "pause" : "resume";
    const control = node("button", action === "pause" ? "Pause forward validation" : "Resume forward validation");
    control.type = "button";
    listen(control, "click", async (_, epoch) => {
      control.disabled = true;
      try { await api(`/api/weather/schedules/${schedule.config.id}/${action}`, {}, epoch); requireLegacy(epoch); await weatherSchedules(epoch); }
      catch (error) { if (error.cancelled) return; $("weather-schedule-message").textContent = error.message; }
      finally { if (currentLegacy(epoch)) control.disabled = false; }
    });
    const link = node("a", "Download forward validation state");
    link.href = "/api/weather/schedules/" + schedule.config.id;
    link.download = "forward-validation-" + schedule.config.id + ".json";
    section.append(control, link, detail("Pinned targets, batches and operator history", schedule));
    content.append(section);
  }
}
listen($("weather-schedule-refresh"), "click", () => weatherSchedules().catch(error => { if (error.cancelled) return; $("weather-schedule-message").textContent = error.message; }));
listen($("weather-schedule-create"), "click", async (_, epoch) => {
  const button = $("weather-schedule-create"); button.disabled = true;
  try {
    if (!$("weather-schedule-optin").checked) throw new Error("Explicit continuous validation opt-in is required.");
    const dataset_id = $("weather-dataset").value;
    if (!dataset_id) throw new Error("Freeze and select a retained weather dataset first.");
    await api("/api/weather/schedules", { id: crypto.randomUUID(), dataset_id, enabled: true,
      interval_seconds: Number($("weather-schedule-interval").value),
      batch_dates: Number($("weather-schedule-batch").value), follow_retained: $("weather-schedule-follow").checked }, epoch); requireLegacy(epoch);
    $("weather-schedule-optin").checked = false;
    $("weather-schedule-message").textContent = "Forward validation enabled. Inspect the durable backlog below; pause at any time.";
    await weatherSchedules(epoch);
  } catch (error) { if (error.cancelled) return; $("weather-schedule-message").textContent = error.message; }
  finally { if (currentLegacy(epoch)) button.disabled = false; }
});
async function weatherPartitions(epoch = requireLegacy()) {
  const catalog = await api("/api/weather/partitions", undefined, epoch); requireLegacy(epoch);
  for (const [id, placeholder] of [["weather-partition", "All retained inputs (up to 128)"], ["weather-outcomes", "Same partition as history"]]) {
    const select = $(id), previous = select.value;
    const empty = node("option", placeholder); empty.value = "";
    select.replaceChildren(empty, ...catalog.partitions.map(p => {
      const option = node("option", `Partition ${p.number} · ${p.inputs} inputs (${p.shadow_cycles} shadow) · ${p.first_at} → ${p.last_at}`);
      option.value = p.partition_id; return option;
    }));
    if (catalog.partitions.some(p => p.partition_id === previous)) select.value = previous;
  }
  for (const id of ["weather-cohort", "weather-cohort-outcomes"]) {
    const select = $(id), previous = Array.from(select.selectedOptions).map(o => o.value);
    select.replaceChildren(...catalog.partitions.map(p => {
      const option = node("option", `Partition ${p.number} · ${p.inputs} inputs · ${p.first_at} → ${p.last_at}`);
      option.value = p.partition_id; option.selected = previous.includes(p.partition_id); return option;
    }));
  }
  $("weather-partition-counts").textContent = `${catalog.total_inputs} retained inputs across ${catalog.partitions.length} bounded partitions. Each selection processes at most ${catalog.partition_size} captures and ${catalog.partition_size} outcome cycles. Receipts are preserved; model calendar boundaries stay frozen. Later outcomes can come from a separate partition.`;
}
listen($("weather-partitions-refresh"), "click", () => weatherPartitions().catch(error => { if (error.cancelled) return; $("weather-message").textContent = error.message; }));
async function weatherDatasets(selected, epoch = requireLegacy()) {
  const rows = await api("/api/weather/datasets", undefined, epoch); requireLegacy(epoch);
  state.weatherDatasets = rows;
  const previous = selected || $("weather-dataset").value || globalThis.localStorage?.getItem("entropytrade-weather-dataset");
  $("weather-dataset").replaceChildren(...(rows.length ? rows.map((snapshot) => {
    const option = node("option", `${snapshot.dataset_id.slice(7, 19)} · ${snapshot.readiness.independent_events} events · ${snapshot.readiness.status}`);
    option.value = snapshot.dataset_id.slice(7); return option;
  }) : [node("option", "No retained dataset yet")]));
  if (rows.length && rows.some(s => s.dataset_id.slice(7) === previous)) $("weather-dataset").value = previous;
  if (rows.length && $("family").value === "weather" && $("mode").value === "recorded") {
    $("mode").value = "weather_history"; modeHelp();
  }
  showWeatherReadiness();
}
function showWeatherReadiness() {
  $("weather-readiness").replaceChildren();
  const snapshot = state.weatherDatasets.find(s => s.dataset_id.slice(7) === $("weather-dataset").value);
  if (snapshot) {
    globalThis.localStorage?.setItem("entropytrade-weather-dataset", snapshot.dataset_id.slice(7));
    renderWeatherHistory($("weather-readiness"), snapshot);
  }
}
listen($("weather-dataset"), "change", () => {
  $("family").value = "weather"; $("mode").value = "weather_history"; modeHelp(); showWeatherReadiness();
});
listen($("weather-cohort-freeze"), "click", async (_, epoch) => {
  $("weather-cohort-freeze").disabled = true;
  $("weather-message").textContent = "Verifying cohort batches and rebuilding point-in-time features…";
  try {
    const partition_ids = Array.from($("weather-cohort").selectedOptions).map(o => o.value);
    const outcome_partition_ids = Array.from($("weather-cohort-outcomes").selectedOptions).map(o => o.value);
    const selection = { partition_ids, ...(outcome_partition_ids.length ? { outcome_partition_ids } : {}) };
    const snapshot = await api("/api/weather/datasets", selection, epoch); requireLegacy(epoch);
    await weatherDatasets(snapshot.dataset_id.slice(7), epoch); requireLegacy(epoch);
    $("family").value = "weather"; $("mode").value = "weather_history"; modeHelp();
    $("weather-message").textContent = "Immutable research cohort selected. Review its evidence gates, then start research.";
  } catch (error) { if (error.cancelled) return; $("weather-message").textContent = error.message; }
  finally { if (currentLegacy(epoch)) $("weather-cohort-freeze").disabled = false; }
});
listen($("weather-freeze"), "click", async (_, epoch) => {
  $("weather-freeze").disabled = true;
  $("weather-message").textContent = "Verifying receipts and freezing dataset…";
  try {
    const selection = {};
    if ($("weather-partition").value) selection.partition_id = $("weather-partition").value;
    if ($("weather-outcomes").value) selection.outcome_partition_id = $("weather-outcomes").value;
    const snapshot = await api("/api/weather/datasets", selection, epoch); requireLegacy(epoch);
    await weatherDatasets(snapshot.dataset_id.slice(7), epoch); requireLegacy(epoch);
    $("family").value = "weather"; $("mode").value = "weather_history"; modeHelp();
    $("weather-message").textContent = "Immutable dataset selected. Review its shortages, then start research.";
  } catch (error) { if (error.cancelled) return; $("weather-message").textContent = error.message; }
  finally { if (currentLegacy(epoch)) $("weather-freeze").disabled = false; }
});
function renderBitcoinHistory(content, history) {
  const section = panel("Retained Bitcoin history");
  const reconciliation = history.reconciliation;
  section.append(node("p", `${history.capture_count} retained captures · ${history.retained_events} events on ${history.retained_dates} dates · ${history.protected_events} protected events.`),
    node("p", `Official outcome reads: ${reconciliation.requested}; deferred by budget: ${reconciliation.deferred}; retained response receipts: ${reconciliation.receipts.length}; current failures: ${reconciliation.failures.length}.`), list(history.limitations));
  if (reconciliation.failures.length) section.append(list(reconciliation.failures.map((failure) => `${failure.ticker}: ${failure.failure} (${failure.failed_at})`)));
  if (history.readiness) section.append(list(history.readiness.summaries), node("p", history.readiness.limitation, "hint"), detail("Minimum model evidence and exact shortages", history.readiness));
  section.append(detail("Outcome reconciliation clocks and response identities", reconciliation));
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
    if (candidate.fee_evidence) card.append(detail("Frozen fee selection and refusals", candidate.fee_evidence));
    if (candidate.model_lineage) card.append(detail("Probability model lineage and refusals", candidate.model_lineage));
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
listen($("family"), "change", modeHelp); listen($("mode"), "change", modeHelp);
listen($("reasoning"), "change", reasoningHelp);
document.querySelectorAll("[data-example]").forEach((button) => listen(button, "click", () => {
  const example = button.dataset.example;
  $("family").value = example === "bitcoin" ? "bitcoin" : "weather";
  $("mode").value = example === "synthetic" ? "synthetic" : example === "bitcoin" ? "public" : "recorded";
  $("idea").value = example === "bitcoin" ? "Does Bitcoin spot relative to the actual strike help estimate KXBTC probabilities?" : example === "synthetic" ? "Demonstrate temporal modeling and execution gates on explicitly synthetic weather data." : "Do upward forecast revisions improve weather contract probabilities?";
  modeHelp(); $("idea").focus();
}));
document.querySelectorAll("[data-tab]").forEach((button) => listen(button, "click", () => { state.tab = button.dataset.tab; renderResult(); }));
listen($("refresh"), "click", () => history().catch((error) => { if (!error.cancelled) $("connection").replaceChildren(notice(error.message, true)); }));
listen($("research-form"), "submit", async (event, epoch) => {
  event.preventDefault(); if (!state.token) return;
  $("submit").disabled = true; $("form-message").textContent = "Saving research request…";
  try {
    const reasoning = $("reasoning").value;
    const response = await api("/api/jobs", { ...($("mode").value === "weather_history" ? { dataset_id: $("weather-dataset").value } : {}), idea: $("idea").value, family: $("family").value, mode: $("mode").value, reasoning, enable_provider: reasoning === "provider" && $("enable-provider").checked }, epoch); requireLegacy(epoch);
    $("enable-provider").checked = false;
    await selectJob(response.id, epoch); requireLegacy(epoch); $("form-message").textContent = "Request saved. Follow its progress on the right.";
  } catch (error) { if (error.cancelled) return; $("form-message").textContent = error.message; }
  finally { if (currentLegacy(epoch)) $("submit").disabled = false; }
});
async function v1Gates(epoch = requireLegacy()) {
  const content = $("v1-gates");
  try {
    const report = await api("/api/v1-gates", undefined, epoch); requireLegacy(epoch);
    content.replaceChildren(node("p", report.v1_complete ? "Every gate is attested." : `V1 incomplete: ${report.open.length} of ${report.gates.length} gates are not attested.`, "hint"));
    report.gates.forEach((gate) => content.append(append(node("section", null, `v1-gate v1-gate-${gate.status}`),
      node("h4", `${gate.title} · ${gate.status}`),
      node("p", `${gate.reference ? `${gate.reference} · ` : ""}${gate.detail}`, "small"))));
  } catch (error) { if (error.cancelled) throw error; content.replaceChildren(notice(`V1 gate report unavailable: ${error.message}`, true)); }
}
async function feeEvidence(epoch = requireLegacy()) {
  const content = $("fee-evidence");
  try {
    const catalog = await api("/api/fees", undefined, epoch); requireLegacy(epoch); content.replaceChildren();
    if (!catalog.versions?.length) { content.append(notice("Missing fee evidence. Costed shadow intentions and real backtests refuse without applicable reviewed documents.")); return; }
    for (const version of catalog.versions) {
      const section = append(node("section"), node("h3", version.evidence_kind === "controlled" ? "CONTROLLED fee fixture · software evidence only" : "Authentic source receipt"),
        node("p", version.policy ? `Reviewed fee schedule · ${version.series.join(", ")}` : version.refusal),
        node("p", `Available: ${version.available_at} · Effective: ${version.policy?.effective_from || "unverified"} → ${version.policy?.effective_to || "unverified"}`, "small"));
      const download = node("a", "Fee version JSON"); download.href = `/api/fees/${version.version.slice(7)}`; download.download = `fee-${version.version.slice(7)}.json`; section.append(download);
      version.sources.forEach((source, index) => {
        const link = node("a", `Original fee source ${index + 1}`); link.href = `${download.href}/sources/${index}`; link.download = `fee-source-${index}.bin`;
        const origin = source.manual_import
          ? `OPERATOR MANUAL IMPORT (no system-observed HTTP) · Imported ${source.received_at} · Operator-attested download ${source.manual_import.operator_downloaded_at} · ${source.manual_import.note}`
          : `HTTP ${source.status} · Received ${source.received_at}`;
        section.append(node("p", `${source.url} · ${origin} · ${source.sha256}`, "small"), link);
      });
      section.append(detail("Fee coefficients, scope, review and citations", version)); content.append(section);
    }
  } catch (error) { if (error.cancelled) throw error; content.replaceChildren(notice(`Fee evidence refused: ${error.message}`, true)); }
}

function shadowCandidates() {
  const job = state.job;
  const proposals = job?.status === "completed" && job.result?.data_kind === "real" ?
    job.result.proposals.filter((p) => p.spec) : [];
  $("shadow-candidate").replaceChildren(...(proposals.length ? proposals.map((p) => {
    const option = node("option", p.spec.name); option.value = p.candidate_id; return option;
  }) : [node("option", "Select a completed real run with typed candidates")]));
  $("shadow-candidate").disabled = !proposals.length;
  $("shadow-start").disabled = !proposals.length || !state.token;
}
async function shadowHistory(epoch = requireLegacy()) {
  await shadowAlerts(epoch); requireLegacy(epoch);
  const monitors = await api("/api/monitors", undefined, epoch); requireLegacy(epoch);
  $("shadow-history").replaceChildren();
  if (!monitors.length) $("shadow-history").append(node("p", "No saved shadow monitors.", "hint"));
  monitors.forEach((monitor) => {
    const button = node("button", `${monitor.family} / ${monitor.candidate_id} · ${monitor.status} · ${monitor.id.slice(0, 8)}`);
    listen(button, "click", () => selectMonitor(monitor.id).catch(shadowError));
    $("shadow-history").append(button);
  });
}
const alertNames = { stale_collection: "Stale collection", repeated_failures: "Repeated failures", unresolved_reconciliation: "Unresolved reconciliation" };
let alertVersion;
async function shadowAlerts(epoch = requireLegacy()) {
  const { alerts } = await api("/api/alerts", undefined, epoch); requireLegacy(epoch);
  const version = JSON.stringify(alerts);
  if (version === alertVersion) return;
  alertVersion = version;
  const content = $("shadow-alerts"); content.replaceChildren(node("h3", "Operator alerts"));
  const open = alerts.filter(a => !a.resolved_at);
  content.append(node("p", `${open.length} open · ${open.filter(a => !a.acknowledged_at).length} need acknowledgement. Acknowledging records review; recovery resolves the condition.`, "hint"));
  alerts.forEach(alert => {
    const panel = append(node("section", null, "operator-alert"),
      node("h4", `${alertNames[alert.kind]} · ${alert.resolved_at ? "Resolved" : alert.acknowledged_at ? "Acknowledged / still open" : "Needs acknowledgement"}`),
      node("p", `${alert.monitor_id.slice(0, 8)} · detected ${alert.opened_at}`, "small"));
    panel.dataset.alertId = alert.id;
    const inspect = node("button", "Inspect monitor");
    listen(inspect, "click", () => selectMonitor(alert.monitor_id, true).catch(shadowError));
    panel.append(inspect);
    if (!alert.resolved_at && !alert.acknowledged_at) {
      const ack = node("button", "Acknowledge alert");
      listen(ack, "click", async (_, epoch) => {
        ack.disabled = true;
        try {
          await api(`/api/monitors/${alert.monitor_id}/acknowledge`, { alert_id: alert.id }, epoch); requireLegacy(epoch);
          await shadowAlerts(epoch); requireLegacy(epoch); if (state.monitor) await selectMonitor(state.monitor.id, true, epoch);
        } catch (error) { if (error.cancelled) return; ack.disabled = false; shadowError(error); }
      });
      panel.append(ack);
    }
    panel.append(detail("Alert evidence and lifecycle", alert)); content.append(panel);
  });
}
function shadowError(error) { if (!error.cancelled) $("shadow-message").textContent = error.message; }
let monitorSelection = 0;
async function selectMonitor(id, force = false, epoch = requireLegacy()) {
  requireLegacy(epoch);
  const selection = ++monitorSelection;
  const monitor = await api(`/api/monitors/${id}`, undefined, epoch); requireLegacy(epoch);
  if (selection !== monitorSelection) return;
  const version = JSON.stringify([monitor.status, monitor.failures, monitor.next_at, monitor.cycle_count,
    monitor.cycles[0]?.status, monitor.cycles[0]?.finished_at, monitor.events.length, monitor.alerts]);
  if (!force && state.monitor?.id === id && state.monitor.version === version) return;
  state.monitor = { id, version };
  const content = $("shadow-evidence"); content.replaceChildren();
  append(content, node("h3", `Shadow monitor · ${monitor.status}`), node("p", monitor.id, "small"),
    notice("SHADOW / SIMULATED PAPER ONLY · submission disabled · no observed fills or profitability claim. Monitoring does not approve a strategy."),
    node("p", `${monitor.cycle_count} durable cycles; showing latest ${monitor.cycles.length}. ${monitor.source_kind === "autonomous_research" ? "Trained decision point: " + window.ET.fmt.decisionPoint(monitor.model_binding?.snapshot?.selected_schedule) : "Poll every " + monitor.interval_seconds + "s"}. Next eligible poll: ${monitor.next_at}. Consecutive failures: ${monitor.failures}.`, "hint"));
  const actions = monitor.status === "active" ? ["pause"] : monitor.status === "paused" ? ["resume"] : [];
  if (monitor.source_kind === "autonomous_research" && ["active", "paused"].includes(monitor.status)) actions.push("suspend");
  if (monitor.source_kind === "autonomous_research" && monitor.status !== "cancelled") actions.push("cancel");
  const controls = actions.map((action) => {
    const control = node("button", ({ pause: "Pause monitor", resume: "Resume monitor", suspend: "Suspend monitor", cancel: "Cancel monitor" })[action]);
    listen(control, "click", async (_, epoch) => {
      try { await api(`/api/monitors/${id}/${action}`, {}, epoch); requireLegacy(epoch); await selectMonitor(id, true, epoch); requireLegacy(epoch); await shadowHistory(epoch); }
      catch (error) { if (error.cancelled) return; shadowError(error); }
    });
    return control;
  });
  const download = node("a", "Shadow evidence JSON"); download.href = `/api/monitors/${id}/export`; download.download = `shadow-${id}.json`;
  append(content, append(node("div", null, "run-tools"), ...controls, download),
    detail("Frozen strategy and research identity", { source_kind: monitor.source_kind || "legacy", job_id: monitor.job_id, research_job_id: monitor.research_job_id, experiment_id: monitor.experiment_id, candidate_id: monitor.candidate_id, spec_hash: monitor.spec_hash, spec: monitor.spec }),
    detail("Frozen model binding", monitor.model_binding || { status: "blocked", reason: "Legacy monitor has no frozen model binding" }),
    detail("Lifecycle and recovery events", monitor.events),
    detail("Durable operator alerts", monitor.alerts || []),
    detail("Tracked contracts and subsequent official outcomes", monitor.contracts));
  const evaluationPanel = append(node("section"), node("h3", "Prospective forecast evaluation"));
  evaluationPanel.id = "shadow-evaluation";
  evaluationPanel.append(node("p", "Loading retained forecast evidence…", "hint"));
  content.append(evaluationPanel);
  const evaluation = prospectiveEvaluation(id, evaluationPanel, epoch, selection);
  const account = monitor.paper_summary;
  if (account) {
    const panel = append(node("section"), node("h3", "Simulated paper account"));
    panel.id = "paper-account";
    const paperDownload = node("a", "Paper account JSON");
    paperDownload.href = `/api/monitors/${id}/paper`; paperDownload.download = `paper-${id}.json`;
    panel.append(paperDownload);
    if (account.status === "simulated") {
      panel.append(notice(account.data_kind === "synthetic" ? "CONTROLLED SYNTHETIC · software evidence only" : "Simulated accounting on retained real evidence; eligibility can remain blocked."),
        table(["Cash", "Fees paid", "Realized simulated P&L", "Equity at cost", "Fills", "Settlements"], [[account.cash, account.fees, account.realized_pnl, account.equity_at_cost, account.fill_count, account.settlement_count]]),
        node("p", account.limitation, "hint"), detail("Simulated positions", account.positions),
        detail("Paper account state and liquidity consumption", monitor.paper_account));
    } else panel.append(node("p", account.reason, "hint"));
    content.append(panel);
  }
  monitor.cycles.forEach((cycle) => {
    const section = append(node("section"), node("h3", `Cycle ${cycle.sequence} · ${cycle.status}`), node("p", cycle.detail, "hint"));
    const result = cycle.result;
    if (result) {
      if (result.cycle_mode === "reconcile_only") section.append(notice("Settlement-only reconciliation: official outcomes for existing positions; no new predictions, quotes or paper orders."));
      section.append(node("p", `Decisions: ${result.decisions?.length || 0}; quotes: ${result.quotes?.length || 0}; official outcomes: ${result.outcomes?.length || 0}.`, "small"));
      if (result.failure) section.append(notice(result.failure, true));
      if (result.model_refusals && Object.keys(result.model_refusals).length) section.append(notice(`Model scoring blocked: ${Object.values(result.model_refusals).join("; ")}`, true));
      if (result.execution) section.append(node("p", `Sized books: ${result.execution.book_count}; deferred contracts: ${result.execution.deferred_tickers.length}; execution capture failures: ${result.execution.failures.length}. Fee evidence is checked independently at each decision.`, "hint"));
      if (result.decisions?.length) {
        section.append(table(["Fee series", "Fee status", "Version / refusal"], result.decisions.map(d => [d.fee_evidence?.series, d.fee_evidence?.status || "legacy", d.fee_evidence?.version || d.fee_evidence?.reason || "Uncertified legacy evidence"])));
        section.append(detail("Frozen fee provenance and refusals", { versions: result.fee_versions || [], decisions: result.decisions.map(d => d.fee_evidence) }));
      }
      if (result.decisions?.length) section.append(table(["Contract", "Status", "P(YES)", "Reasons"], result.decisions.map((d) => [d.ticker, d.status, d.prediction?.probability_yes, d.reasons.join(", ")])));
      if (result.paper) {
        section.append(detail("Simulated decisions, execution risk, fills and settlements", result.paper));
        section.append(table(["Paper contract", "Execution status", "Refusal / fill quantity"], (result.paper.executions || []).map(e => [e.ticker, e.status, e.reason || e.order?.filled_quantity])));
        section.append(table(["Paper decision", "Status", "Reasons"], (result.paper.decisions || []).map(d => [d.ticker, d.status, d.reasons.join(", ")])));
      }
      section.append(detail("Source receipts, predictions, intended orders, risk checks and artifacts", result));
    }
    section.append(node("code", cycle.digest || "No committed result digest")); content.append(section);
  });
  await evaluation; requireLegacy(epoch);
}
async function prospectiveEvaluation(id, panel, epoch = requireLegacy(), selection = null) {
  try {
    const report = await api(`/api/monitors/${id}/evaluation`, undefined, epoch); requireLegacy(epoch);
    if (selection !== null && selection !== monitorSelection) return;
    panel.replaceChildren(node("h3", "Prospective forecast evaluation"),
      notice("Monitoring diagnostics only · separate from historical validation and simulated paper accounting · no profitability claim."),
      node("p", `Status: ${report.status} · evidence cutoff: ${report.as_of || "No retained observations"}.`));
    const json = node("a", "Forecast evaluation JSON"); json.href = `/api/monitors/${id}/evaluation`; json.download = `forecast-evaluation-${id}.json`;
    const csv = node("a", "Forecast observations CSV"); csv.href = `/api/monitors/${id}/evaluation.csv`; csv.download = `forecast-observations-${id}.csv`;
    panel.append(append(node("div", null, "run-tools"), json, csv));
    const c = report.counts;
    panel.append(table(["Pending", "Refused", "Matched", "Independent events", "Target dates", "Matched events / dates", "Poll observations"],
      [[c.pending, c.refused, c.matched, c.independent_events, c.independent_dates, `${c.matched_events} / ${c.matched_dates}`, c.poll_observations]]));
    if (!report.diagnostics.some(g => g.metrics)) panel.append(notice(report.status === "refused"
      ? "Evidence verification refused: no forecast metrics. Inspect the retained failures below."
      : "Insufficient evidence: no forecast metrics. Ten matched independent events on five target dates per model are required."));
    report.diagnostics.forEach(group => {
      panel.append(notice(group.data_kind === "synthetic" ? "CONTROLLED SYNTHETIC · software demonstration only; never empirical performance" : "Authentic retained evidence · descriptive monitoring only"),
        node("p", `${group.model_hash} · ${group.calibration} · ${group.independent_events} matched events / ${group.independent_dates} dates.`, "small"));
      if (group.metrics) panel.append(table(["Event-weighted Brier score", "Event-weighted log loss"], [[group.metrics.event_weighted_brier, group.metrics.event_weighted_log_loss]]), detail("Forecast reliability bins", group.metrics.reliability_bins));
    });
    panel.append(table(["Contract", "Event / date", "Status", "P(YES)", "Official result", "Available at", "Revisions", "Reason"], report.observations.map(r =>
      [r.ticker, `${r.event_id} / ${r.target_date}`, r.status, r.prediction?.probability_yes, r.outcome?.result, r.outcome?.available_at, r.outcome_revisions, r.reason])),
      detail("Forecast, source and outcome lineage", report.observations),
      detail("Excluded, failed and interrupted evidence", { excluded_protected_events: c.excluded_protected_events, cycle_statuses: report.cycle_statuses, failures: report.cycle_failures }),
      list(report.limitations), node("code", report.report_hash));
  } catch (error) { if (error.cancelled) return;
    if (selection !== null && selection !== monitorSelection) return;
    panel.replaceChildren(node("h3", "Prospective forecast evaluation"), notice(error.message, true));
  }
}
listen($("shadow-start"), "click", async (_, epoch) => {
  $("shadow-start").disabled = true;
  try {
    const monitor = await api("/api/monitors", { job_id: state.job.id, candidate_id: $("shadow-candidate").value, interval_seconds: Number($("shadow-interval").value) }, epoch); requireLegacy(epoch);
    $("shadow-message").textContent = "Monitor saved. Fresh evidence will accrue while this server runs.";
    await selectMonitor(monitor.id, true, epoch); requireLegacy(epoch); await shadowHistory(epoch);
  } catch (error) { if (error.cancelled) return; shadowError(error); }
  finally { if (currentLegacy(epoch)) shadowCandidates(); }
});
async function initialize(epoch) {
  modeHelp(); $("submit").disabled = true;
  try {
    const catalog = await api("/api/catalog", undefined, epoch); requireLegacy(epoch);
    state.token = catalog.csrf_token;
    state.provider = catalog.provider_enabled ? catalog.research_provider : null;
    modeHelp();
    for (const load of [history, shadowHistory, weatherDatasets, weatherPartitions, weatherLabels, weatherSchedules, feeEvidence, v1Gates]) {
      await (load === weatherDatasets ? load(undefined, epoch) : load(epoch)); requireLegacy(epoch);
    }
    // Rebuild selected records and their controls in this activation, including terminal
    // records that polling would otherwise never redraw.
    if (state.job) { await selectJob(state.job.id, epoch); requireLegacy(epoch); }
    if (state.monitor) { await selectMonitor(state.monitor.id, true, epoch); requireLegacy(epoch); }
    for (const id of ["weather-label-acquire", "weather-schedule-create", "weather-cohort-freeze", "weather-freeze"]) $(id).disabled = false;
    // Inputs can change while the read-only panels initialize. Their event handlers
    // are intentionally gated until ready; reconcile current values before enabling
    // submission so a selected provider never has an invisible consent control.
    modeHelp(); shadowCandidates(); $("submit").disabled = false;
    $("connection").replaceChildren();
  } catch (error) {
    if (!error.cancelled) $("connection").replaceChildren(notice(`Cannot connect to the local workbench: ${error.message}. Reload after the server is available.`, true));
    throw error;
  }
}
async function poll(epoch) {
  if (state.busy || !legacy.ready || !legacyVisible() || !legacy.active || epoch !== legacy.epoch) return;
  state.busy = true;
  try {
    if (state.job && !terminal.has(state.job.status)) {
      const requestedId = state.job.id;
      const selection = jobSelection;
      const job = await api(`/api/jobs/${requestedId}`, undefined, epoch); requireLegacy(epoch);
      if (selection === jobSelection && state.job?.id === requestedId && job.updated_at !== state.updated) { state.job = job; renderJob(); await history(epoch); }
    }
    await shadowHistory(epoch);
    await weatherSchedules(epoch);
    if (state.monitor) await selectMonitor(state.monitor.id, false, epoch);
    requireLegacy(epoch); $("connection").replaceChildren();
  } catch (error) {
    if (!error.cancelled) $("connection").replaceChildren(notice(`Progress connection interrupted: ${error.message}. Retrying…`, true));
  } finally { if (epoch === legacy.epoch) state.busy = false; }
}
function deactivateWorkbench() {
  legacy.active = false; legacy.ready = false; legacy.epoch += 1;
  workbenchBusy(true);
  legacy.controller?.abort(); legacy.controller = null;
  if (legacy.timer !== null) clearInterval(legacy.timer);
  legacy.timer = null; legacy.pending = null; state.busy = false;
  state.token = null; jobSelection += 1; monitorSelection += 1; weatherLabelsSequence += 1;
  $("submit").disabled = true; $("shadow-start").disabled = true;
}
async function activateWorkbench() {
  if (!legacyVisible()) { deactivateWorkbench(); throw inactiveError(); }
  if (legacy.active && legacy.pending) return legacy.pending;
  if (legacy.active && legacy.ready) return;
  legacy.active = true;
  // History rows can render before the remaining panels finish loading. Browser
  // interaction must wait for readiness instead of dispatching an ignored click.
  workbenchBusy(true);
  const epoch = ++legacy.epoch;
  alertVersion = undefined; state.scheduleJSON = null;
  staticListeners.forEach(bindListener);
  legacy.controller = typeof AbortController === "function" ? new AbortController() : null;
  const pending = initialize(epoch).then(() => {
    requireLegacy(epoch); legacy.ready = true; workbenchBusy(false);
    legacy.timer = setInterval(() => poll(epoch), 1500);
  });
  legacy.pending = pending;
  try { await pending; }
  catch (error) {
    if (epoch === legacy.epoch) { legacy.active = false; legacy.ready = false; legacy.controller?.abort(); state.token = null; }
    throw error;
  }
  finally { if (epoch === legacy.epoch) legacy.pending = null; }
}
window.ET.legacyWorkbench = {
  activate: activateWorkbench, deactivate: deactivateWorkbench,
  selectJob: async (id) => {
    const pending = activateWorkbench(), epoch = legacy.epoch;
    await pending; requireLegacy(epoch); return selectJob(id, epoch);
  },
  selectMonitor: async (id, force = true) => {
    const pending = activateWorkbench(), epoch = legacy.epoch;
    await pending; requireLegacy(epoch); return selectMonitor(id, force, epoch);
  },
};
// A background tab also stops work. Returning to an already visible Real workbench
// resumes through the same readiness boundary as route navigation.
document.addEventListener("visibilitychange", () => {
  if (legacyVisible()) activateWorkbench().catch(() => {});
  else deactivateWorkbench();
});
$("submit").disabled = true;
workbenchBusy(true);
// Deferred scripts run in order after the DOM becomes interactive. The shell may
// have opened this route before the legacy controller was registered.
if (legacyVisible()) activateWorkbench().catch(() => {});
