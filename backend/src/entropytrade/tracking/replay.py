"""Credential-free offline verification of retained shadow decisions; never polls a source."""

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from entropytrade.data.sources import file_hash
from entropytrade.domain.strategy import StrategySpec
from entropytrade.exchange.kalshi.recorded import public_book_from_body
from entropytrade.execution.fee_evidence import FeeVersion
from entropytrade.execution.fee_policy import FeePolicy
from entropytrade.experiments.data import ExperimentData, PredictionBundle
from entropytrade.features.registry import scientific_hash
from entropytrade.tracking.evaluate import evaluate, protected_events


def decision_inputs(
    spec: StrategySpec,
    data: ExperimentData,
    bundle: PredictionBundle,
    *,
    held: tuple[dict[str, Any], ...] = (),
    acquisition_complete: bool = True,
    fee: FeePolicy | None = None,
    fee_versions: tuple[FeeVersion, ...] | None = None,
    series_fees: tuple[dict[str, Any], ...] = (),
) -> dict[str, Any]:
    protected = protected_events(data, bundle)
    samples = tuple(
        s.revalidated(outcome=None, outcome_available_at=None)
        for s in data.samples
        if s.event_id not in protected
    )
    safe_data = data.revalidated(
        samples=samples,
        protected_events=protected,
        provenance={"purpose": "shadow replay; targets withheld"},
    )
    metadata = {"original_metadata_hash": scientific_hash(bundle.model_metadata)}
    if "data_kind" in bundle.model_metadata:
        # Preserve the supplied classification, including invalid values. Inferring it from
        # the dataset would turn an unknown/mismatched model into an eligible replay.
        metadata["data_kind"] = bundle.model_metadata["data_kind"]
    safe_bundle = bundle.revalidated(
        model_metadata=metadata,
        records=tuple(
            p
            for p in bundle.records
            if p.partition != "holdout" and any(p.usable(s) for s in samples)
        ),
    )
    result = {
        "schema": "shadow-inputs-v1",
        "spec": spec.model_dump(mode="json"),
        "data": {
            **safe_data.model_dump(mode="json", exclude_computed_fields=True),
            "protected_events": sorted(protected),
        },
        "bundle": safe_bundle.model_dump(mode="json", exclude_computed_fields=True),
        "reservations": held,
        "acquisition_complete": acquisition_complete,
        "fee": fee.model_dump(mode="json", exclude_computed_fields=True) if fee else None,
    }

    if fee_versions is not None:
        result["fee_versions"] = [v.model_dump(mode="json") for v in fee_versions]
        result["series_fees"] = list(series_fees)
    return result


def reproduce(inputs: dict[str, Any]) -> list[dict[str, Any]]:
    if inputs["schema"] != "shadow-inputs-v1":
        raise ValueError("unknown shadow input schema")
    return evaluate(
        StrategySpec.model_validate(inputs["spec"]),
        ExperimentData.model_validate(inputs["data"]),
        PredictionBundle.model_validate(inputs["bundle"]),
        reservations=tuple(inputs["reservations"]),
        acquisition_complete=inputs["acquisition_complete"],
        fee=FeePolicy.model_validate(inputs["fee"]) if inputs["fee"] else None,
        series_fees=tuple(inputs.get("series_fees", ())),
        fee_versions=tuple(FeeVersion.model_validate(v) for v in inputs["fee_versions"])
        if "fee_versions" in inputs
        else None,
    )


def _verify_capture(
    root: Path, directory: str, capture: dict[str, Any], artifacts: dict[str, str]
) -> None:
    """Resolve every receipt in its own capture, including failed responses and series."""
    summary = f"{directory}/summary.json"
    if summary not in artifacts or json.loads((root / summary).read_text()) != capture:
        raise ValueError("shadow capture summary mismatch")
    refs: set[str] = set()
    for receipt in capture["receipts"]:
        ref = receipt["raw_ref"]
        path = (root / ref).resolve()
        if (
            ref in refs
            or Path(ref).parent.as_posix() != directory
            or not path.is_relative_to((root / directory).resolve())
            or not path.is_file()
            or artifacts.get(ref) != receipt["sha256"]
            or file_hash(path) != receipt["sha256"]
        ):
            raise ValueError("shadow raw receipt checksum/path mismatch")
        refs.add(ref)
    for fee in capture.get("fee_evidence", []):
        if fee["receipt"] not in capture["receipts"] or fee["version"] != scientific_hash(
            {"receipt": fee["receipt"], "series": fee["series"]}
        ):
            raise ValueError("shadow fee receipt binding mismatch")


def verify(root: Path) -> dict[str, Any]:
    result = json.loads((root / "result.json").read_text())
    artifacts = result["artifacts"]
    if not any(a["path"] == "decision-inputs.json" for a in artifacts):
        raise ValueError("cycle has no committed replay inputs (failed or interrupted)")
    for artifact in artifacts:
        path = (root / artifact["path"]).resolve()
        if not path.is_relative_to(root.resolve()) or file_hash(path) != artifact["sha256"]:
            raise ValueError("shadow artifact checksum/path mismatch")
    hashes = {a["path"]: a["sha256"] for a in artifacts}
    if result.get("execution") is not None:
        _verify_capture(root, "execution", result["execution"], hashes)
    later = result.get("paper_execution")
    if later is not None:
        _verify_capture(root, "paper-execution", later, hashes)
        inputs = result["paper_inputs"]
        books = inputs["execution_books"]
        if (
            inputs["execution_series_fees"] != later["fee_evidence"]
            or len(books) != later["book_count"]
        ):
            raise ValueError("paper execution capture binding mismatch")
        for ticker, saved in books.items():
            receipts = [
                r
                for r in later["receipts"]
                if r["status"] == 200 and r["path"] == f"/trade-api/v2/markets/{ticker}/orderbook"
            ]
            if len(receipts) != 1:
                raise ValueError("paper book lacks unique successful receipt")
            receipt = receipts[0]
            book = public_book_from_body(
                json.loads((root / receipt["raw_ref"]).read_text()),
                ticker=ticker,
                received_at=datetime.fromisoformat(receipt["received_at"]),
            )
            if book.model_dump(mode="json") != saved:
                raise ValueError("paper book differs from retained raw receipt")
    rows = reproduce(json.loads((root / "decision-inputs.json").read_text()))
    if json.loads(json.dumps(rows)) != result["decisions"]:
        raise ValueError("shadow decisions differ from retained result")
    if "paper" in result:
        from entropytrade.tracking.accounting import reproduce as reproduce_paper

        paper_inputs = json.loads((root / "paper-inputs.json").read_text())
        if (
            paper_inputs != result["paper_inputs"]
            or reproduce_paper(paper_inputs) != result["paper"]
        ):
            raise ValueError("paper accounting differs from retained result")
    return {
        "verified": True,
        "decision_count": len(rows),
        "submission_enabled": False,
        "limitation": "Reproduces decisions only; does not certify source truth or performance",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cycle", type=Path)
    args = parser.parse_args()
    # JSON output is deliberately a local verification command, never an execution control.
    print(json.dumps(verify(args.cycle), sort_keys=True))  # noqa: T201


if __name__ == "__main__":
    main()
