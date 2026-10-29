"""CONTROLLED integration evidence, including fixtures classified real to test adapter gates."""

import asyncio
import json
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import httpx
import pytest

from entropytrade.api.jobs import Jobs
from entropytrade.data.sources import file_hash
from entropytrade.domain.market import Market
from entropytrade.domain.strategy import ModelKind, ProbabilityModelRef, StrategySpec
from entropytrade.domain.time import SimulatedClock
from entropytrade.exchange.kalshi.recorded import market_from_body
from entropytrade.experiments.data import ExperimentData
from entropytrade.features.registry import scientific_hash
from entropytrade.ml.forward import FrozenWeather, freeze_weather
from entropytrade.ml.models import WeatherModel
from entropytrade.tracking.evaluate import evaluate
from entropytrade.tracking.market_data import ShadowTransport, capture_execution
from entropytrade.tracking.models import score
from entropytrade.tracking.replay import decision_inputs, reproduce
from entropytrade.tracking.store import TrackingStore
from entropytrade.tracking.worker import reservations
from tests.exchange.test_gateway_http import _market_body
from tests.shadow_support import execution_wire
from tests.unit.test_probability_models_r2 import examples
from tests.unit.test_tracking import ready


def fitted(kind: str = "raw_forecast", calibration: str = "none") -> WeatherModel:
    data = examples(120)
    model = WeatherModel(kind)  # type: ignore[arg-type]
    model.fit(data[:90], asof=data[90].decision)
    if calibration != "none":
        model.calibrate(data[90:], asof=data[-1].label_available, method=calibration)
    return model


def frozen(kind: str = "raw_forecast", calibration: str = "none") -> FrozenWeather:
    model = freeze_weather(
        fitted(kind, calibration),
        model_hash="sha256:" + "a" * 64,
        data_kind="real",
        protected=("CONTROLLED-holdout",),
        series=("KXHIGHPHIL",),
    )
    assert model is not None
    return model


def binding(model: FrozenWeather) -> dict[str, Any]:
    value: dict[str, Any] = {"status": "bound", "snapshot": model.model_dump(mode="json")}
    value["binding_hash"] = scientific_hash(value)
    return value


def inputs() -> tuple[StrategySpec, ExperimentData, dict[str, Market], FrozenWeather]:
    spec, data, _bundle, _fee = ready()
    model = frozen()
    original = data.samples[0]
    ticker = "KXHIGHPHIL-CONTROLLED-T89"
    assert original.book is not None
    features = {**original.features, "forecast_high_f": Decimal("95")}
    sample = original.revalidated(
        ticker=ticker,
        book=original.book.revalidated(market_ticker=ticker),
        family="KXHIGHPHIL",
        features=features,
        versions={**original.versions, "forecast_high_f": "1"},
        feature_hash=scientific_hash({k: str(v) for k, v in features.items()}),
    )
    data = data.revalidated(
        data_kind="real", samples=(sample,), provenance={"adapter": "public-forward-v1:weather"}
    )
    spec = spec.revalidated(
        market_universe=spec.market_universe.revalidated(series_tickers=("KXHIGHPHIL",)),
        model_ref=ProbabilityModelRef(family=model.family, version=model.model_hash),
    )
    original_market = market_from_body(
        _market_body(), series="KXHIGHPHIL", captured_at=sample.decision_time
    )
    market = original_market.revalidated(
        ticker=sample.ticker,
        rules=original_market.rules.revalidated(
            market_ticker=sample.ticker,
            settlement_target_date=sample.target_date,
            settlement_basis="contract_text",
        ),
        event_ticker=sample.event_id,
        series_ticker=sample.family,
        open_time=sample.decision_time - timedelta(days=1),
        close_time=sample.close_time,
    )
    return spec, data, {sample.ticker: market}, model


def saved_model(store: TrackingStore, spec: StrategySpec, model: FrozenWeather) -> dict[str, Any]:
    job_id = store.jobs.create(
        {"idea": "CONTROLLED frozen model", "family": "weather", "mode": "recorded"}
    )
    name = "models/" + "a" * 64 + "/" + model.family + ".forward.json"
    path = store.jobs.root / "runs" / job_id / "workflow" / name
    path.parent.mkdir(parents=True)
    path.write_text(model.model_dump_json())
    store.jobs.update(
        job_id,
        "completed",
        "CONTROLLED",
        status="completed",
        result={
            "data_kind": "real",
            "proposals": [
                {
                    "candidate_id": "c0",
                    "spec": spec.revalidated(model_ref=None).model_dump(mode="json"),
                }
            ],
            "candidates": [{"candidate_id": "c0", "executed_spec": spec.model_dump(mode="json")}],
            "artifacts": [{"path": name, "sha256": file_hash(path), "bytes": path.stat().st_size}],
        },
    )
    return {"job_id": job_id, "candidate_id": "c0", "interval_seconds": 60}


@pytest.mark.parametrize("kind", ["raw_forecast", "forecast_error", "climatology"])
@pytest.mark.parametrize("calibration", ["none", "platt", "isotonic"])
def test_data_only_model_matches_original_distribution(kind: str, calibration: str) -> None:
    original = fitted(kind, calibration)
    model = frozen(kind, calibration)
    clone = FrozenWeather.model_validate_json(model.model_dump_json())
    strike = market_from_body(
        _market_body(), series="KXHIGHPHIL", captured_at=model.fitted_before
    ).strike
    assert strike is not None
    for forecast in (50.0, 69.5, 89.0, 100.0):
        assert clone.probability(forecast, strike) == pytest.approx(
            original.predict_proba({"forecast_high_f": forecast}, strike, unit="degF"), abs=1e-12
        )


def test_monitor_freezes_resolved_identity_and_model_across_restart(tmp_path: Path) -> None:
    spec, data, markets, model = inputs()
    store = TrackingStore(Jobs(tmp_path))
    request = saved_model(store, spec, model)
    monitor_id = store.create(request)
    first = store.get(monitor_id)
    assert first is not None
    assert first["spec"] == spec.model_dump(mode="json")
    assert first["model_binding"]["status"] == "bound"
    # Removing the original artifact cannot replace/retrain a running monitor's frozen snapshot.
    next((tmp_path / "runs").rglob("*.forward.json")).unlink()
    reopened = TrackingStore(Jobs(tmp_path))
    reopened.recover()
    current = reopened.get(monitor_id)
    assert current == first
    bundle = score(spec, data, current["model_binding"], markets)
    assert len(bundle.records) == 1
    assert bundle.records[0].model_hash == model.model_hash
    _, _, _, fee = ready()
    rows = evaluate(spec, data, bundle, fee=fee)
    assert rows[0]["status"] == "shadow_eligible"
    assert reproduce(json.loads(json.dumps(decision_inputs(spec, data, bundle, fee=fee)))) == rows


@pytest.mark.parametrize("case", ["hash", "synthetic", "changed_spec", "ambiguous"])
def test_model_binding_cannot_import_unverified_or_changed_artifacts(
    tmp_path: Path, case: str
) -> None:
    spec, _, _, model = inputs()
    store = TrackingStore(Jobs(tmp_path))
    request = saved_model(
        store, spec, model.revalidated(data_kind="synthetic") if case == "synthetic" else model
    )
    job = store.jobs.get(request["job_id"])
    assert job is not None
    result = job["result"]
    if case == "hash":
        next((tmp_path / "runs").rglob("*.forward.json")).write_text("{}")
    elif case == "changed_spec":
        result["candidates"][0]["executed_spec"]["name"] = "silently changed"
    elif case == "ambiguous":
        result["artifacts"] *= 2
    with store.jobs.connect() as db:
        db.execute("UPDATE jobs SET result=? WHERE id=?", (json.dumps(result), request["job_id"]))
    if case == "ambiguous":
        value = store.get(store.create(request))
        assert value is not None
        assert value["model_binding"]["status"] == "blocked"
    else:
        with pytest.raises(ValueError, match=r"checksum/path|synthetic model|differs"):
            store.create(request)


@pytest.mark.parametrize(
    "case",
    [
        "future_fit",
        "future_calibration",
        "wrong_hash",
        "wrong_family",
        "synthetic",
        "schema",
        "series",
        "feature_version",
        "null_feature",
        "rules",
        "adapter",
        "holdout",
        "tamper",
        "calibration",
    ],
)
def test_forward_scoring_refuses_incompatible_or_future_evidence(case: str) -> None:
    spec, data, markets, model = inputs()
    sample = data.samples[0]
    if case == "future_fit":
        model = model.revalidated(fitted_before=sample.decision_time + timedelta(seconds=1))
    elif case == "future_calibration":
        model = frozen(calibration="platt").revalidated(
            calibrated_before=sample.decision_time + timedelta(seconds=1)
        )
        spec = spec.revalidated(calibration="platt", model_kind=ModelKind.DOMAIN_STATISTICAL)
    elif case == "wrong_hash":
        spec = spec.revalidated(model_ref=spec.model_ref.revalidated(version="sha256:" + "c" * 64))  # type: ignore[union-attr]
    elif case == "wrong_family":
        spec = spec.revalidated(model_ref=spec.model_ref.revalidated(family="ridge"))  # type: ignore[union-attr]
    elif case == "synthetic":
        model = model.revalidated(data_kind="synthetic")
    elif case == "series":
        model = model.revalidated(series=("KXHIGHCHI",))
    elif case == "feature_version":
        data = data.revalidated(samples=(sample.revalidated(versions={"forecast_high_f": "2"}),))
    elif case == "null_feature":
        data = data.revalidated(samples=(sample.revalidated(features={"forecast_high_f": None}),))
    elif case == "rules":
        data = data.revalidated(samples=(sample.revalidated(rules_known=False),))
    elif case == "adapter":
        data = data.revalidated(provenance={"adapter": "public-forward-v1:bitcoin"})
    elif case == "holdout":
        model = model.revalidated(protected_events=(sample.event_id,))
    elif case == "calibration":
        spec = spec.revalidated(calibration="platt", model_kind=ModelKind.DOMAIN_STATISTICAL)
    value = binding(model)
    if case == "tamper":
        value["snapshot"]["bias_f"] = 100
    elif case == "schema":
        value["snapshot"]["feature_schema_hash"] = "sha256:" + "0" * 64
        value["binding_hash"] = scientific_hash(
            {k: v for k, v in value.items() if k != "binding_hash"}
        )
    bundle = score(spec, data, value, markets)
    assert bundle.records == ()
    assert bundle.refusals or case == "holdout"
    _, _, _, fee = ready()
    rows = evaluate(spec, data, bundle, fee=fee)
    assert all(r["intent"] is None and r["risk"] is None for r in rows)
    assert reproduce(json.loads(json.dumps(decision_inputs(spec, data, bundle, fee=fee)))) == rows


def test_sized_books_and_versioned_fees_are_causal_but_do_not_certify_a_coefficient(
    tmp_path: Path,
) -> None:
    spec, data, markets, model = inputs()
    clock = SimulatedClock(data.samples[0].decision_time)
    original_available = data.samples[0].features_available_at

    def wire(request: httpx.Request) -> httpx.Response:
        clock.advance(timedelta(seconds=1))
        return execution_wire(request)

    captured, evidence = asyncio.run(
        capture_execution(
            tmp_path / "execution", data, markets, transport=httpx.MockTransport(wire), clock=clock
        )
    )
    sample = captured.samples[0]
    assert evidence["book_count"] == 1
    assert evidence["failures"] == []
    assert len(evidence["receipts"]) == 2
    assert sample.features_available_at == original_available < sample.decision_time
    assert sample.book is not None
    assert sample.book.received_at <= sample.decision_time
    assert sample.book.asks[0].price == Decimal("0.44")
    assert sample.book.asks[0].quantity == Decimal(4)
    assert sample.feature_hash != data.samples[0].feature_hash
    fee = evidence["fee_evidence"][0]
    assert not fee["certified"]
    assert fee["version"].startswith("sha256:")
    assert fee["receipt"]["sha256"] == file_hash(tmp_path / fee["receipt"]["raw_ref"])
    bundle = score(spec, captured, binding(model), markets)
    assert len(bundle.records) == 1
    rows = evaluate(spec, captured, bundle)
    assert rows[0]["reasons"] == ["certified_fees"]
    assert reproduce(json.loads(json.dumps(decision_inputs(spec, captured, bundle)))) == rows


@pytest.mark.parametrize("status", [401, 429, 500])
def test_execution_capture_failures_withhold_books_and_remain_durable(
    tmp_path: Path, status: int
) -> None:
    spec, data, markets, model = inputs()
    captured, evidence = asyncio.run(
        capture_execution(
            tmp_path / "execution",
            data,
            markets,
            transport=httpx.MockTransport(lambda _: httpx.Response(status, json={})),
            clock=SimulatedClock(data.samples[0].decision_time),
        )
    )
    assert len(evidence["failures"]) == len(evidence["receipts"]) == 2
    assert evidence["book_count"] == 0
    assert evidence["fee_evidence"] == []
    assert captured.samples[0].book is None  # never reuse the input/last cycle book on failure
    bundle = score(spec, captured, binding(model), markets)
    rows = evaluate(spec, captured, bundle, acquisition_complete=False)
    assert rows[0]["status"] == "blocked"
    assert rows[0]["intent"] is None
    assert json.loads((tmp_path / "execution/summary.json").read_text()) == evidence


def test_frozen_scoring_reservations_survive_cycles_restart_and_outcome_release(
    tmp_path: Path,
) -> None:
    spec, data, markets, model = inputs()
    _, _, _, fee = ready()
    store = TrackingStore(Jobs(tmp_path))
    monitor_id = store.create(saved_model(store, spec, model))
    claim = store.claim()
    assert claim is not None
    bundle = score(spec, data, binding(model), markets)
    rows = evaluate(spec, data, bundle, fee=fee)
    assert rows[0]["status"] == "shadow_eligible"
    result = {"detail": "CONTROLLED intentions only", "decisions": rows}
    assert store.finish(*claim, result)
    reopened = TrackingStore(Jobs(tmp_path))
    reopened.recover()
    monitor = reopened.get(monitor_id, export=True)
    assert monitor is not None
    held = reservations(monitor)
    again = evaluate(spec, data, bundle, fee=fee, reservations=held)
    assert again[0]["status"] == "no_signal"
    assert (
        reproduce(json.loads(json.dumps(decision_inputs(spec, data, bundle, held=held, fee=fee))))
        == again
    )
    monitor["contracts"] = [
        {
            "ticker": data.samples[0].ticker,
            "outcome": {"available_at": data.samples[0].close_time.isoformat()},
        }
    ]
    assert reservations(monitor) == ()


@pytest.mark.parametrize(
    "url",
    [
        "https://api.elections.kalshi.com/trade-api/v2/portfolio/orders",
        "https://api.elections.kalshi.com/trade-api/v2/series/OTHER",
        "http://api.elections.kalshi.com/trade-api/v2/series/KXHIGHPHIL",
        "https://example.com/trade-api/v2/series/KXHIGHPHIL",
    ],
)
def test_execution_transport_cannot_access_other_destinations(url: str) -> None:
    transport = ShadowTransport(
        {"/trade-api/v2/series/KXHIGHPHIL"}, httpx.MockTransport(execution_wire)
    )
    with pytest.raises(ValueError, match="denied"):
        asyncio.run(transport.handle_async_request(httpx.Request("GET", url)))


@pytest.mark.parametrize(
    "case", ["ticker", "series", "event", "close", "future_rules", "target", "closed", "unverified"]
)
def test_forward_probability_is_bound_to_exact_point_in_time_contract(case: str) -> None:
    spec, data, markets, model = inputs()
    sample = data.samples[0]
    market = markets[sample.ticker]
    if case == "ticker":
        market = market.revalidated(
            ticker="OTHER", rules=market.rules.revalidated(market_ticker="OTHER")
        )
    elif case == "series":
        market = market.revalidated(series_ticker="KXHIGHCHI")
    elif case == "event":
        market = market.revalidated(event_ticker="OTHER")
    elif case == "close":
        market = market.revalidated(close_time=market.close_time + timedelta(seconds=1))
    elif case == "future_rules":
        market = market.revalidated(
            rules=market.rules.revalidated(captured_at=sample.decision_time + timedelta(seconds=1))
        )
    elif case == "target":
        market = market.revalidated(
            rules=market.rules.revalidated(
                settlement_target_date=sample.target_date + timedelta(days=1)
            )
        )
    elif case == "unverified":
        market = market.revalidated(rules=market.rules.revalidated(settlement_basis="unresolved"))
    elif case == "closed":
        data = data.revalidated(samples=(sample.revalidated(decision_time=sample.close_time),))
    bundle = score(spec, data, binding(model), {sample.ticker: market})
    assert not bundle.records
    assert bundle.refusals


def test_decimal_strike_tickers_are_supported_within_exact_get_allowlist(tmp_path: Path) -> None:
    _, data, markets, _ = inputs()
    original = data.samples[0]
    ticker = "KXHIGHPHIL-26OCT29-B77.5"
    sample = original.revalidated(ticker=ticker, book=None)
    market = markets[original.ticker]
    market = market.revalidated(ticker=ticker, rules=market.rules.revalidated(market_ticker=ticker))
    captured, evidence = asyncio.run(
        capture_execution(
            tmp_path / "execution",
            data.revalidated(samples=(sample,)),
            {ticker: market},
            transport=httpx.MockTransport(execution_wire),
            clock=SimulatedClock(sample.decision_time),
        )
    )
    assert evidence["book_count"] == 1
    assert evidence["failures"] == []
    assert captured.samples[0].book is not None
    assert captured.samples[0].book.market_ticker == ticker
