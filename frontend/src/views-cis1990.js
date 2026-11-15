"use strict";
// The course workflow uses the localhost worker. This view never reads fictional demo data.
(function () {
  const ET = window.ET;
  const { h, fmt, pill, statusPill, button, card, callout, kv, dataTable } = ET;
  const endpoint = "/api/cis1990";
  const title = "CIS 1990 Research Demo";
  const roles = { research: "Research", hypothesis: "Hypothesis", quant: "Quant", critic: "Critic" };
  const terminal = new Set(["completed", "failed", "cancelled", "interrupted"]);
  const duration = (ms) => ms == null ? "—" : ms >= 1000 ? fmt.num(ms / 1000, 2) + " s" : fmt.num(ms) + " ms";
  const usCost = (cost) => cost == null ? "Unavailable" : fmt.usd(cost, 6);
  const details = (summary, text) => h("details", { class: "course-detail" },
    h("summary", summary), h("pre", typeof text === "string" ? text : JSON.stringify(text, null, 2)));
  const bullets = (values) => values?.length ? h("ul", { class: "course-list" }, values.map(v => h("li", v))) : null;
  const columns = (...fields) => fields.map(([key, label, render]) => ({ key, label, render, sortable: false }));

  function stageCards(job) {
    const saved = job?.result?.stages || [];
    const lastEvent = job?.events?.at(-1);
    const failedStage = job?.result?.failure?.stage;
    return h("div", { class: "grid course-stages", "aria-label": "Four agent stages" },
      Object.entries(roles).map(([key, name]) => {
        const stage = saved.find(item => item.role === key);
        const started = job?.events?.some(event => event.stage === "research_" + key);
        const state = stage ? "completed" : failedStage === key || (started && job?.status === "failed") ? "failed" :
          lastEvent?.stage === "research_" + key ? "running" : started ? job.status : terminal.has(job?.status) ? "not reached" : "pending";
        return card({ title: name, actions: statusPill(state), className: "course-stage", id: "course-stage-" + key },
          stage ? h("p", { class: "muted" }, "Completed in ", duration(stage.latency_ms)) : null,
          stage ? details(name + " output", stage.output) : null,
          state === "failed" ? h("p", job.result?.failure?.reason || job.detail) : null);
      }));
  }

  function sourcesView(sources, controlled) {
    const market = sources.current_markets;
    const weather = sources.weather;
    function sourceCard(name, source, content) {
      return card({ title: name, actions: statusPill(source.status === "available" ? "available" : "incomplete") },
        content, h("ul", { class: "course-list course-receipts" }, source.requests.map(request =>
          h("li", h("code", request.url),
            h("p", [request.http_status && "HTTP " + request.http_status, request.error,
              duration(request.latency_ms), request.received_at && fmt.date(request.received_at)].filter(Boolean).join(" · "))))),
        details("Source receipt details", source.requests));
    }
    return h("section", { class: "stack", "aria-label": "Source evidence" },
      h("h2", controlled ? "Controlled source evidence" : "Live source evidence"),
      h("div", { class: "grid g-1-1" },
        sourceCard("Kalshi contract rules", market,
          market.items.length ? market.items.map(item =>
            details(item.ticker + " · " + item.target_date, [item.rules.rules_primary,
              item.rules.rules_secondary, ...item.rules.settlement_sources.map(source => source.name)].join("\n\n"))) :
            callout("No usable open Philadelphia contract rules were returned.", "warn")),
        sourceCard("NWS hourly forecast", weather,
          weather.items.length ? [
            h("p", "Matching market dates " + (weather.market_dates_with_forecast.join(", ") || "unavailable")),
            dataTable({
              caption: "Philadelphia forecast coverage", dense: true,
              columns: columns(["target_date", "Target date"], ["hours", "Hours", row => row.hours_returned + "/" + row.hours_expected],
                ["high", "Full-day proxy °F", row => row.projected_hourly_max_f ?? "—"],
                ["partial", "Sample max °F", row => row.max_in_returned_hours_f ?? "—"]),
              rows: weather.items,
            }),
            h("p", { class: "muted" }, "A sample maximum covers only the forecast hours returned. The contract’s rule names its settlement authority."),
          ] : callout("Weather forecast evidence is unavailable.", "warn"))));
  }

  function researchOutputs(result, status) {
    const output = (role) => result.stages?.find(stage => stage.role === role)?.output;
    const hypotheses = output("hypothesis")?.hypotheses || [];
    const candidates = output("quant")?.candidates || [];
    const verdicts = output("critic")?.verdicts || [];
    const decisions = result.decisions || [];
    const note = output("research");
    if (!note && !hypotheses.length && !candidates.length) return null;
    const ready = decisions.filter(decision => decision.status === "READY_FOR_EXPERIMENT").length;
    const eligibility = status === "completed"
      ? ready ? ready + " candidate(s) eligible for an experiment. This research run did not execute a backtest."
        : "No candidates are eligible for backtesting. Review the Critic and deterministic reasons below."
      : terminal.has(status) ? "The run ended before backtest eligibility was determined."
        : "Backtest eligibility awaits a completed review.";
    return h("section", { class: "stack", "aria-label": "Research results" },
      h("h2", "Research results"),
      note ? card({ title: "Research findings" }, h("p", note.market_understanding), bullets(note.limitations)) : null,
      hypotheses.length ? card({ title: "Hypotheses", subtitle: "Unverified proposals" },
        hypotheses.map(item => h("article", { class: "course-result" },
          h("p", h("strong", item.hypothesis_id), " · ", item.mechanism),
          kv([["Test", item.test], ["Falsification", item.falsification]])))) : null,
      candidates.length ? card({ title: "Strategy proposals and Critic decisions" },
        callout(eligibility, status === "completed" && !ready ? "warn" : "info"),
        candidates.map(candidate => {
          const decision = decisions.find(item => item.candidate_id === candidate.candidate_id);
          const verdict = decision?.critic || verdicts.find(item => item.candidate_id === candidate.candidate_id);
          return h("article", { class: "course-result" },
            h("h4", candidate.spec?.name || candidate.candidate_id),
            h("p", { class: "muted" }, candidate.candidate_id + " · " + candidate.hypothesis_id),
            decision ? pill(fmt.words(decision.status), decision.status === "REJECTED" ? "neg" : decision.status === "READY_FOR_EXPERIMENT" ? "pos" : "warn") : null,
            candidate.spec ? details("Structured strategy proposal", candidate.spec) :
              h("p", candidate.missing_capability || "A typed proposal was withheld."),
            verdict ? kv([["Critic", verdict.accept_for_experiment ? "Accept for consideration" : "Reject"],
              ["Reason", verdict.reason]]) : null,
            bullets(decision?.reasons));
        })) : null);
  }

  function execution(job) {
    const result = job.result;
    const trace = result?.run_id;
    const usage = result?.usage || {};
    const modelCalls = [...(result?.responses || []), ...(result?.model_request_failures || [])]
      .sort((a, b) => a.started_at.localeCompare(b.started_at));
    return card({ title: "Execution trace", actions: trace ? h("a", {
      class: "btn sm", href: endpoint + "/" + job.id + "/trace", download: "cis1990-" + job.id + ".json",
    }, "Download trace JSON") : null },
      trace ? kv([
        ["Provider / requested model", result.provider.provider + " / " + result.provider.model_name],
        ["Returned models", [...new Set(modelCalls.map(call => call.model_name).filter(Boolean))].join(", ") || "No model returned"],
        ["Input / output tokens", fmt.num(usage.input_tokens) + " / " + fmt.num(usage.output_tokens)],
        ["Model calls", modelCalls.length],
        ["Elapsed", duration(Date.parse(result.finished_at) - Date.parse(result.started_at))],
        [result.pricing_status === "unavailable" && usage.cost != null ? "Known cost subtotal" : "Estimated cost", usCost(usage.cost)],
      ]) : null,
      modelCalls.length ? dataTable({ caption: "Provider request timings and usage", dense: true, rows: modelCalls,
        columns: columns(["stage", "Stage", row => roles[row.stage] || row.stage], ["status", "Status"],
          ["latency", "Latency", row => duration(row.latency_ms)], ["tokens", "Input / output",
            row => row.usage ? fmt.num(row.usage.input_tokens) + " / " + fmt.num(row.usage.output_tokens) : "—"],
          ["cost", "Estimated cost", row => usCost(row.usage?.cost)]),
      }) : null,
      result?.tool_activity?.length ? details("Evidence tool calls", result.tool_activity) : null,
      job.events?.length ? details("Job timeline", job.events.map(event =>
        event.at + " · " + fmt.words(event.stage) + " · " + event.detail).join("\n")) : null);
  }

  ET.views.cis1990 = async (root, ctx) => {
    const subtitle = "Research Philadelphia daily-high temperature with Kalshi, NWS and Gemini.";
    const header = h("header", { class: "page-head" },
      h("div", { class: "page-titles" }, h("h1", title), h("p", { class: "page-sub" }, subtitle)));
    root.append(header);
    if (ET.mode() === "demo") {
      root.append(ET.unavailable("Live research is available in Real Mode", "Switch modes to open the server-backed course workflow.",
          button("Switch to Real Mode", { variant: "primary", onclick: () => ET.setMode("real") })));
      return;
    }

    const start = button("Run Philadelphia Weather Research", { variant: "primary", disabled: true }, "play");
    const message = h("div", { role: "status", "aria-live": "polite" }, "Checking server configuration…");
    const content = h("div", { class: "stack" }, stageCards(null));
    const issue = h("div");
    header.append(h("div", { class: "page-actions" }, start));
    root.append(message, issue, content);
    const config = await ET.api(endpoint, { fresh: true });
    if (!ctx.isCurrent()) return;

    let displayed;
    async function post(path) {
      const response = await fetch(path, {
        method: "POST", credentials: "same-origin",
        headers: { "Content-Type": "application/json", "X-EntropyTrade-CSRF": config.csrf_token },
        body: "{}",
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || "Course request failed");
      return result;
    }
    function render(job) {
      const result = job?.result;
      const active = job && !terminal.has(job.status);
      start.disabled = !config.configured || !!active;
      const cancel = active ? button("Cancel run", { variant: "ghost sm", onclick: async () => {
        if (!ctx.isCurrent()) return;
        try { await post(endpoint + "/" + job.id + "/cancel"); }
        catch (error) { if (ctx.isCurrent()) issue.replaceChildren(callout(error.message, "error")); }
      } }) : null;
      message.replaceChildren(
        h("span", { class: "muted" }, "Runtime · Gemini / " + config.model_name),
        ...(job ? [statusPill(job.status), h("span", job.detail)] : []),
        ...(cancel ? [cancel] : []));
      if (!config.configured) {
        issue.replaceChildren(callout("Set GEMINI_API_KEY on the server and restart EntropyTrade to run research.", "warn"));
      }
      displayed = job?.updated_at;
      const failure = result?.failure;
      const controlled = result?.data_mode === "controlled_http";
      content.replaceChildren(
        ...[
          controlled ? callout("Controlled HTTP test run. Sources and model responses are fixture data.", "warn") : null,
          failure ? callout([failure.type, roles[failure.stage] || failure.stage,
            failure.http_status && "HTTP " + failure.http_status, failure.reason].filter(Boolean).join(" · "), "error") :
            job?.status === "failed" ? callout(job.detail, "error") : null,
          stageCards(job),
          result?.current_sources?.weather ? sourcesView(result.current_sources, controlled) : null,
          result ? researchOutputs(result, job.status) : null,
          job ? execution(job) : null,
        ].filter(Boolean));
    }

    async function watch(id) {
      while (ctx.isCurrent()) {
        try {
          const job = await ET.api(endpoint + "/" + id, { fresh: true });
          if (!ctx.isCurrent()) return;
          if (job.updated_at !== displayed) render(job);
          if (terminal.has(job.status)) return;
        } catch (error) {
          if (ctx.isCurrent()) issue.replaceChildren(ET.errorState(error.message, ET.route));
          return;
        }
        await new Promise(resolve => setTimeout(resolve, 850));
      }
    }

    render(config.latest);
    if (config.latest && !terminal.has(config.latest.status)) void watch(config.latest.id);
    start.addEventListener("click", async () => {
      if (!ctx.isCurrent() || ET.mode() !== "real") return;
      start.disabled = true;
      issue.replaceChildren();
      message.textContent = "Queuing Philadelphia weather research…";
      content.replaceChildren(stageCards(null));
      try {
        const result = await post(endpoint);
        displayed = null;
        await watch(result.id);
      } catch (error) {
        if (!ctx.isCurrent()) return;
        issue.replaceChildren(ET.errorState(error.message, ET.route));
        message.textContent = "Could not start the run.";
      }
    });
  };
})();
