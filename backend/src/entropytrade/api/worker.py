"""Fixed research entry point. Explicit bounded provider opt-in; no trading controls."""

import argparse
import asyncio
import json
from datetime import date
from pathlib import Path
from typing import Any

from entropytrade.agents.evidence import EvidenceConfig
from entropytrade.agents.provider import ResearchProviderConfig
from entropytrade.api.jobs import Jobs, identifier, validate_request
from entropytrade.api.server import workspace_path
from entropytrade.data.sources import file_hash
from entropytrade.experiments.data import AdapterRegistry
from entropytrade.experiments.workflow import research_and_test
from entropytrade.families.bitcoin_history import build_history, history_data
from entropytrade.families.bitcoin_models import MODELS, BitcoinPredictions
from entropytrade.families.public import ForwardPredictions, capture_public, forward_data
from entropytrade.weather.collection import WeatherConfig
from entropytrade.weather.history import load_snapshot


def acquisition_summary(provenance: dict[str, Any]) -> dict[str, Any]:
    """Present acquisition separately from worker completion and empirical evaluation."""
    capture = provenance["capture"]
    receipts = capture["receipts"]
    successful = sum(200 <= receipt["status"] < 300 for receipt in receipts)
    ingested = successful > 0 and capture["listed_contracts"] > 0 and capture["observations"] > 0
    status = (
        "incomplete"
        if capture["failures"] or not capture["universe_complete"]
        else "complete"
        if ingested
        else "empty"
    )
    return {
        "status": status,
        "headline": f"Public acquisition {status.upper()} · {capture['family']}",
        "receipt_count": len(receipts),
        "successful_response_count": successful,
        "listed_contracts": capture["listed_contracts"],
        "observations": capture["observations"],
        "failure_count": len(capture["failures"]),
        "counts": (
            f"HTTP receipts: {len(receipts)} ({successful} successful); "
            f"listed contracts: {capture['listed_contracts']}; "
            f"observations: {capture['observations']}; "
            f"acquisition failures: {len(capture['failures'])}."
        ),
        "started_at": capture["started_at"],
        "decision_time": capture["decision_time"],
        "universe_complete": capture["universe_complete"],
        "history_complete": capture["history_complete"],
        "failure_summaries": [
            f"{f['source']}: {f['failure']} (failed at {f['failed_at']})"
            for f in capture["failures"]
        ],
        "evaluation_limit": (
            "Forward ingestion only. No historical evaluation, fitted probabilities or "
            "empirical returns. Review completion does not mean acquisition succeeded."
        ),
        "limitations": provenance["limitations"],
    }


def review_result(result: dict[str, Any], output: Path) -> dict[str, Any]:
    """Explicit review projection. Only predictions actually used by validation are shown."""
    if result["final_holdout_evaluated"]:
        raise ValueError("website reviews must not evaluate protected final holdout")
    research = json.loads(Path(result["research_artifact"]).read_text())
    research_details = {
        k: research.get(k)
        for k in (
            "status",
            "provider",
            "instruction_version",
            "pydantic_ai_version",
            "request_hash",
            "started_at",
            "finished_at",
            "limits",
            "usage",
            "responses",
            "pricing_status",
            "stages",
            "tool_calls",
            "failure",
        )
    }
    failed = result.get("status") == "RESEARCH_FAILED"
    if failed:
        # Failed research is inspectable/downloadable and cannot enter experiments.
        result = {
            **result,
            "candidates": [],
            "experiment_id": None,
            "warnings": [research["report"]],
        }
    permitted = {p for c in result["candidates"] for p in c.get("prediction_ids", [])}
    probabilities: list[dict[str, Any]] = []
    count = 0
    for path in sorted((output / "models").glob("*/predictions.jsonl")):
        for line in path.read_text().splitlines():
            prediction = json.loads(line)
            if prediction["split"] != "validation" or prediction["prediction_id"] not in permitted:
                continue
            count += 1
            if len(probabilities) < 100:
                probabilities.append(
                    {
                        k: prediction[k]
                        for k in (
                            "prediction_id",
                            "market_ticker",
                            "decision_time",
                            "model",
                            "model_hash",
                            "probability_yes",
                            "feature_hash",
                            "fit_asof",
                            "calibration_asof",
                            "split",
                        )
                    }
                )
    artifacts = [
        {
            "path": p.relative_to(output).as_posix(),
            "sha256": file_hash(p),
            "bytes": p.stat().st_size,
        }
        for p in sorted(output.rglob("*"))
        if p.is_file() and p.suffix in {".json", ".jsonl", ".md", ".parquet"}
    ]
    return {
        "schema": "workbench-review-v1",
        "reasoning": research["mode"],
        "reasoning_limit": (
            "Local templates select signal words or parse complete AND-only feature "
            "comparisons; no LLM reasoning or arbitrary prose interpretation."
            if research["mode"] == "local_templates"
            else "Provider-backed bounded research proposes hypotheses; deterministic gates "
            "control specifications, experiments and risk. No trading approval is implied."
            if research["mode"] == "provider"
            else "Predeclared mock proposals; the idea is recorded, not interpreted by an LLM."
        ),
        "research": research_details,
        "status": "research_failed" if failed else "completed",
        "formulation": research.get("note"),
        "data_kind": result["data_kind"],
        "experiment_id": result["experiment_id"],
        "research_run": result["research_run"],
        "coverage": research["coverage"],
        "hypotheses": research["hypotheses"],
        "proposals": research["candidates"],
        "decisions": research["decisions"],
        "candidates": result["candidates"],
        "probabilities": probabilities,
        "probability_count": count,
        "probability_limit": 100,
        "final_holdout_evaluated": result["final_holdout_evaluated"],
        "lineage": {
            k: result.get(k)
            for k in (
                "dataset",
                "feature_version",
                "research_hash",
                "normalized_data_hash",
                "code",
                "config",
                "resolved_models",
                "requested_trial_count",
            )
        },
        "artifacts": artifacts,
        "warnings": result["warnings"],
        "report": research["report"] if failed else Path(result["report_path"]).read_text(),
    }


def execute_job(jobs: Jobs, repo: Path, job_id: str) -> None:
    job = jobs.get(job_id)
    if job is None or job["status"] != "running":
        return
    request = validate_request(job["request"], stored=True)
    run = jobs.root / "runs" / identifier(job_id)
    run.mkdir(parents=True, exist_ok=False)

    def progress(stage: str, detail: str) -> None:
        if not jobs.update(job_id, stage, detail):
            raise InterruptedError("job is no longer active")

    try:
        adapters = None
        config_path = repo / "configs/research/weather.json"
        public = None
        history = None
        weather_history = None
        if request["mode"] == "weather_history":
            progress("dataset", "Verifying immutable retained weather snapshot and original clocks")
            root = jobs.root / "runs/weather-datasets" / request["dataset_id"]
            weather_history = load_snapshot(root)
            config = EvidenceConfig(
                root=root.resolve(),
                features=weather_history["features"],
                holdout_start=date.fromisoformat(
                    weather_history["identity"]["temporal_boundaries"][2]
                ),
            )
            config_path = run / "evidence.json"
            config_path.write_text(config.model_dump_json(indent=2))
        elif request["mode"] == "history":
            progress(
                "reconciling",
                "Verifying retained Bitcoin receipts and fetching later official outcomes",
            )
            captures, previous = jobs.bitcoin_inputs()
            history = asyncio.run(build_history(run / "history", captures, previous=previous))
            output = run / "workflow"
            adapters = AdapterRegistry()
            adapters.register(
                "bitcoin", history_data, BitcoinPredictions(history, output / "models")
            )
            boundary = min(
                (s.target_date for s in history.samples if s.event_id in history.protected_events),
                default=date.max,
            )
            config = EvidenceConfig(
                root=run.resolve(),
                features="history",
                holdout_start=boundary,
                model_families=MODELS,
            )
            config_path = run / "evidence.json"
            config_path.write_text(config.model_dump_json(indent=2))
        elif request["mode"] == "public":
            progress(
                "fetching", "Fetching bounded public contract rules and forward source receipts"
            )
            weather = WeatherConfig.model_validate_json(
                (repo / "configs/data/weather-forward.json").read_text()
            )
            public = asyncio.run(
                capture_public(run / "public", family=request["family"], weather=weather)
            )
            adapters = AdapterRegistry()
            adapters.register(request["family"], forward_data, ForwardPredictions())
            config = EvidenceConfig(
                root=run.resolve(),
                features="public",
                holdout_start=date.max,
                model_families=("forward_only",),
            )
            config_path = run / "evidence.json"
            config_path.write_text(config.model_dump_json(indent=2))
        elif request["mode"] == "recorded":
            config = EvidenceConfig.model_validate_json(config_path.read_text())
            # The repository config is trusted; make its fixed relative root independent of cwd.
            config_path = run / "evidence.json"
            config_path.write_text(
                config.revalidated(root=(repo / config.root).resolve()).model_dump_json()
            )
        output = run / "workflow"
        use_provider = request.get("reasoning") == "provider"
        result = research_and_test(
            prompt=request["idea"],
            evidence_config=config_path,
            output=output,
            registry=jobs.root / "registry.sqlite",
            tracking=run / "mlflow",
            offline=not use_provider,
            enable_provider=use_provider,
            provider=(
                ResearchProviderConfig.model_validate(request["research_provider"])
                if use_provider
                else None
            ),
            synthetic=request["mode"] == "synthetic",
            days=240,
            adapters=adapters,
            market_family=request["family"],
            progress=progress,
            local_templates=not use_provider and request["mode"] != "synthetic",
        )
        failed = result.get("status") == "RESEARCH_FAILED"
        progress("review", "Saving protected research and experiment evidence")
        review = review_result(result, output)
        if weather_history is not None:
            summary = {
                k: weather_history[k]
                for k in (
                    "dataset_id",
                    "capture_count",
                    "observation_count",
                    "readiness",
                    "identity",
                )
            }
            review["weather_history"] = summary
            review["report"] = "\n".join(
                [
                    "Retained weather dataset " + summary["dataset_id"],
                    json.dumps(summary["readiness"], sort_keys=True),
                    "",
                    review["report"],
                ]
            )
        if history is not None:
            review["bitcoin_history"] = history.provenance
            review["report"] = "\n".join(
                [
                    "Retained Bitcoin history · receipt-time official binary targets",
                    f"Captures: {history.provenance['capture_count']}; "
                    f"retained events: {history.provenance['retained_events']}; "
                    f"protected events: {len(history.protected_events)}.",
                    *history.provenance["limitations"],
                    *history.provenance["readiness"]["summaries"],
                    history.provenance["readiness"]["limitation"],
                    "Reconciliation: "
                    + json.dumps(history.provenance["reconciliation"], sort_keys=True),
                    "",
                    review["report"],
                ]
            )
        if public is not None:
            review["public_evidence"] = public.provenance
            review["public_manifest"] = json.loads((run / "public/manifest.json").read_text())
            summary = acquisition_summary(public.provenance)
            review["acquisition"] = summary
            review["report"] = "\n".join(
                [
                    summary["headline"],
                    summary["counts"],
                    f"Capture started (UTC): {summary['started_at']}",
                    f"Decision / capture end (UTC): {summary['decision_time']}",
                    f"Universe complete: {summary['universe_complete']}; "
                    f"history complete: {summary['history_complete']}",
                    summary["evaluation_limit"],
                    "Acquisition failure summary:",
                    *(summary["failure_summaries"] or ["None recorded."]),
                    *summary["limitations"],
                    "",
                    review["report"],
                ]
            )
        review_path = run / "review.json"
        review_path.write_text(json.dumps(review, sort_keys=True, indent=2, allow_nan=False))
        jobs.update(
            job_id,
            "failed" if failed else "completed",
            (
                "Research failed; inspect the saved failure, provider stage and budget evidence"
                if failed
                else f"Review saved; public acquisition {review['acquisition']['status']} "
                f"({review['acquisition']['failure_count']} failures); forward ingestion only"
                if public is not None
                else "Review saved; inspect candidate gates and evidence limitations"
            ),
            status="failed" if failed else "completed",
            result=review,
        )
    except InterruptedError:
        jobs.update(job_id, "interrupted", "Run was interrupted", status="interrupted")
    except Exception as exc:  # noqa: BLE001 - worker boundary, persisted failure, no fallback
        jobs.update(
            job_id,
            "failed",
            f"Research worker failed ({type(exc).__name__}); no result substituted",
            status="failed",
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--job", required=True)
    args = parser.parse_args()
    execute_job(
        Jobs(workspace_path(args.repo, args.workspace)), args.repo.resolve(), identifier(args.job)
    )


if __name__ == "__main__":
    main()
