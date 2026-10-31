"""Point-in-time fee versions and real-data refusals; controlled success is labeled."""

import json
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from entropytrade.api.jobs import Jobs
from entropytrade.execution.fee_admin import review
from entropytrade.execution.fee_evidence import FeeEvidenceStore, FeeVersion, select_fee
from entropytrade.experiments.engine import evaluate_candidate
from entropytrade.tracking.evaluate import evaluate, shadow_limits
from entropytrade.tracking.replay import decision_inputs, reproduce
from entropytrade.tracking.store import TrackingStore
from entropytrade.tracking.worker import reservations
from tests.fee_support import authentic_refusal, controlled_fee
from tests.r4_support import nonweather
from tests.unit.test_tracking import ready


def test_immutable_bytes_atomic_publish_and_corruption(tmp_path: Path) -> None:
    store = FeeEvidenceStore(tmp_path)
    version = controlled_fee()
    assert store.put(version) == store.put(version) == version.version
    (store.root / ".pending-interrupted").write_bytes(b"partial")
    assert FeeEvidenceStore(tmp_path).snapshot() == (version,)
    assert store.get(version.version).sources[0].body().startswith(b"CONTROLLED")
    (store.root / (version.version[7:] + ".json")).write_text(
        version.model_dump_json().replace(".07", ".09")
    )
    with pytest.raises(ValueError, match="checksum mismatch"):
        store.snapshot()


@pytest.mark.parametrize(
    "case",
    ["missing", "conflict", "late", "inapplicable", "expired", "future", "controlled_on_real"],
)
def test_fee_refusals_and_offline_decisions(case: str) -> None:
    spec, data, bundle, _ = ready()
    version = controlled_fee()
    when = data.samples[0].decision_time
    versions: tuple[FeeVersion, ...] = (version,)
    if case == "missing":
        versions = ()
    elif case == "conflict":
        versions = (version, version.revalidated(review="CONTROLLED conflicting review"))
    elif case == "late":
        assert version.policy
        late = when + timedelta(seconds=1)
        versions = (
            version.revalidated(
                reviewed_at=late, policy=version.policy.revalidated(available_at=late)
            ),
        )
    elif case == "inapplicable":
        versions = (version.revalidated(series=("OTHER",)),)
    elif case in {"expired", "future"}:
        assert version.policy
        versions = (
            version.revalidated(
                policy=version.policy.revalidated(
                    **(
                        {"effective_to": when}
                        if case == "expired"
                        else {"effective_from": when + timedelta(seconds=1)}
                    )
                )
            ),
        )
    elif case == "controlled_on_real":
        data = data.revalidated(data_kind="real")
        bundle = bundle.revalidated(model_metadata={**bundle.model_metadata, "data_kind": "real"})
    rows = evaluate(spec, data, bundle, fee_versions=versions)
    assert rows[0]["status"] == "blocked"
    assert rows[0]["intent"] is None
    assert not rows[0]["gates"]["certified_fees"]
    assert rows[0]["fee_evidence"]["status"] == "refused"
    assert reproduce(decision_inputs(spec, data, bundle, fee_versions=versions)) == rows


def test_asof_boundaries_and_later_conflicts_do_not_rewrite_earlier_decisions() -> None:
    version = controlled_fee()
    assert version.policy is not None
    policy = version.policy
    for when, allowed in [(version.available_at, True), (policy.effective_to, False)]:
        assert when is not None
        selected, _ = select_fee((version,), series="MENTIONS", when=when, data_kind="synthetic")
        assert (selected is not None) == allowed
    _, data, _, _ = ready()
    when = data.samples[0].decision_time
    later = when + timedelta(seconds=1)
    changed = version.revalidated(reviewed_at=later, policy=policy.revalidated(available_at=later))
    assert select_fee((version, changed), series="MENTIONS", when=when, data_kind="synthetic")[0]
    assert (
        select_fee((version, changed), series="MENTIONS", when=later, data_kind="synthetic")[0]
        is None
    )


def test_series_metadata_conflict_is_frozen_for_offline_replay() -> None:
    spec, data, bundle, _ = ready()
    metadata = ({"series": "MENTIONS", "fee_type": "quadratic", "fee_multiplier": "2"},)
    rows = evaluate(spec, data, bundle, fee_versions=(controlled_fee(),), series_fees=metadata)
    assert rows[0]["fee_evidence"]["reason"] == "series_metadata_conflict"
    assert rows == reproduce(
        decision_inputs(spec, data, bundle, fee_versions=(controlled_fee(),), series_fees=metadata)
    )


def test_real_receipt_keeps_original_bytes_and_refuses_without_models() -> None:
    spec, data, bundle, _ = ready()
    real = authentic_refusal()
    assert real.sources[0].status == 429
    assert real.policy is None
    data = data.revalidated(data_kind="real")
    bundle = bundle.revalidated(records=(), model_metadata={"data_kind": "real"})
    rows = evaluate(spec, data, bundle, fee_versions=(real, controlled_fee()))
    assert rows[0]["status"] == "blocked"
    assert not rows[0]["gates"]["point_in_time_prediction"]
    assert not rows[0]["gates"]["certified_fees"]
    assert rows[0]["intent"] is None


@pytest.mark.parametrize(
    "case",
    [
        "source_checksum",
        "backdated_review",
        "missing_citation",
        "rounding",
        "unbounded",
        "failed_receipt",
    ],
)
def test_invalid_certifications_are_rejected(case: str) -> None:
    version = controlled_fee().model_dump(mode="json")
    if case == "source_checksum":
        version["sources"][0]["body_base64"] = "AAAA"
    elif case == "backdated_review":
        version["reviewed_at"] = "2020-01-01T00:00:00Z"
    elif case == "missing_citation":
        version["citations"] = []
    elif case == "rounding":
        version["rounding"] = "unsupported"
    elif case == "unbounded":
        version["policy"]["effective_to"] = None
    else:
        version["sources"][0]["status"] = 429
    with pytest.raises(ValueError, match=r"fee|review|policy|failed"):
        FeeVersion.model_validate(version)


def test_browser_or_import_cannot_assign_review_clock(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="exact fields"):
        review(FeeEvidenceStore(tmp_path), {"reviewed_at": "2020-01-01"})
    with pytest.raises(ValueError, match="official HTTPS"):
        controlled_fee().revalidated(evidence_kind="authentic")


def test_fee_inclusive_reservations_survive_store_restart(tmp_path: Path) -> None:
    spec, data, bundle, _ = ready()
    # Separate events and a large position cap let repeated cycles reach the same monetary caps.
    spec = spec.revalidated(
        position_sizing=spec.position_sizing.revalidated(
            contracts=Decimal("40"), max_contracts=Decimal("1000")
        )
    )
    sample = data.samples[0]
    assert sample.book
    data = data.revalidated(
        samples=(
            sample.revalidated(
                book=sample.book.revalidated(
                    asks=(sample.book.asks[0].revalidated(quantity=Decimal("1000")),)
                )
            ),
        )
    )
    store = TrackingStore(Jobs(tmp_path))
    job = store.jobs.create(
        {"idea": "CONTROLLED fee reservation", "family": "weather", "mode": "recorded"}
    )
    store.jobs.update(
        job,
        "completed",
        "CONTROLLED",
        status="completed",
        result={
            "data_kind": "real",
            "proposals": [{"candidate_id": "c0", "spec": spec.model_dump(mode="json")}],
        },
    )
    monitor = store.create({"job_id": job, "candidate_id": "c0", "interval_seconds": 60})
    for index in range(5):
        if index:
            store = TrackingStore(Jobs(tmp_path))
            store.control(monitor, "pause")
            store.control(monitor, "resume")
        claim = store.claim()
        assert claim is not None
        reopened = store.get(monitor, export=True)
        assert reopened is not None
        held = reservations(reopened)
        rows = evaluate(spec, data, bundle, fee_versions=(controlled_fee(),), reservations=held)
        inputs = decision_inputs(spec, data, bundle, held=held, fee_versions=(controlled_fee(),))
        assert rows == reproduce(json.loads(json.dumps(inputs)))
        row = rows[0]
        if index < 4:
            assert row["status"] == "shadow_eligible"
            assert Decimal(row["intent"]["edge"]["fee_per_contract"]) > 0
        else:
            assert row["status"] == "risk_rejected"
        store.finish(
            monitor,
            claim[1],
            {
                "decisions": rows,
                "detail": "CONTROLLED software evidence",
                "contracts": [],
                "submission_enabled": False,
            },
            failed=False,
        )
    assert shadow_limits().per_event == Decimal("100")


def test_experiment_uses_frozen_versions_and_refuses_missing_future_evidence() -> None:
    data, provider, research, config = nonweather()
    config = config.revalidated(fee_policy=None, fee_versions=(controlled_fee(),))
    candidate = research["candidates"][0]
    first = evaluate_candidate(candidate, research, data, provider, config)
    assert first["tested"]
    assert first["scenarios"]
    for scenario in first["scenarios"]:
        assert Decimal(scenario["fees_paid"]) > 0
        assert scenario["fee_bindings"]
        assert all(a["version"] == controlled_fee().version for a in scenario["fee_bindings"])
    frozen = type(config).model_validate_json(config.model_dump_json())
    assert evaluate_candidate(candidate, research, data, provider, frozen) == first
    refused = evaluate_candidate(
        candidate, research, data, provider, config.revalidated(fee_versions=())
    )
    assert not refused["tested"]
    assert not refused["scenarios"]
    assert "missing_fee_evidence" in " ".join(refused["reasons"])


def test_fee_change_between_decision_and_fill_and_portable_experiment(tmp_path: Path) -> None:
    from entropytrade.experiments.engine import run_experiments
    from entropytrade.experiments.fee_replay import verify

    data, provider, research, config = nonweather()
    version = controlled_fee()
    assert version.policy is not None
    boundary = data.samples[50].decision_time + timedelta(microseconds=500000)
    earlier = version.revalidated(policy=version.policy.revalidated(effective_to=boundary))
    later = version.revalidated(
        policy=version.policy.revalidated(
            effective_from=boundary,
            schedule=version.policy.schedule.revalidated(quadratic_coefficient=Decimal(".14")),
        )
    )
    config = config.revalidated(fee_policy=None, fee_versions=(earlier, later))
    result = run_experiments(
        research=research,
        data=data,
        provider=provider,
        config=config,
        registry_path=tmp_path / "registry.sqlite",
        output=tmp_path / "experiments",
        tracking=tmp_path / "mlflow",
    )
    first = result["candidates"][0]
    assert first["tested"]
    bindings = first["scenarios"][0]["fee_bindings"]
    assert bindings[0]["version"] == earlier.version
    assert bindings[1]["version"] == later.version
    experiment = tmp_path / "experiments" / result["experiment_id"][7:]
    assert verify(experiment)["verified"] is True
    inputs = json.loads((experiment / "replay-inputs.json").read_text())
    for sample in inputs["data"]["samples"]:
        if sample["event_id"] in data.protected_events:
            assert sample["outcome"] is None
            assert sample["features"] == {}
    assert "fixture.invalid" in (experiment / "replay-inputs.json").read_text()


def test_series_metadata_alone_never_certifies() -> None:
    from entropytrade.features.registry import scientific_hash

    version = controlled_fee()
    assert version.policy is not None
    source = version.sources[0].revalidated(
        url="https://api.elections.kalshi.com/trade-api/v2/series/MENTIONS"
    )
    with pytest.raises(ValueError, match="series metadata alone"):
        version.revalidated(
            sources=(source,),
            policy=version.policy.revalidated(
                evidence_hash=scientific_hash([source.model_dump(mode="json")])
            ),
        )


@pytest.mark.parametrize("case", ["conflict", "late", "inapplicable", "expired"])
def test_experiments_refuse_invalid_evidence_before_any_scenario(case: str) -> None:
    data, provider, research, config = nonweather()
    version = controlled_fee()
    assert version.policy is not None
    versions: tuple[FeeVersion, ...]
    if case == "conflict":
        versions = (version, version.revalidated(review="CONTROLLED conflicting claim"))
    elif case == "late":
        when = data.samples[69].decision_time + timedelta(seconds=1)
        versions = (
            version.revalidated(
                reviewed_at=when, policy=version.policy.revalidated(available_at=when)
            ),
        )
    elif case == "inapplicable":
        versions = (version.revalidated(series=("OTHER",)),)
    else:
        versions = (
            version.revalidated(
                policy=version.policy.revalidated(effective_to=data.samples[50].decision_time)
            ),
        )
    result = evaluate_candidate(
        research["candidates"][0],
        research,
        data,
        provider,
        config.revalidated(fee_policy=None, fee_versions=versions),
    )
    assert result["tested"] is False
    assert result["scenarios"] == []
    assert "point-in-time fee evidence refused" in " ".join(result["reasons"])
