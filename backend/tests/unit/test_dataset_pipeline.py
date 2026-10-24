"""Generic dataset joins: no invented vintages, prices, contracts or settlement labels."""

import json
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

import pyarrow.parquet as pq  # type: ignore[import-untyped]
import pytest
from hypothesis import given
from hypothesis import strategies as st

from entropytrade.data.dataset import build_dataset, make_rows
from entropytrade.data.schema import (
    DatasetConfig,
    Location,
    MarketEvidence,
    MarketState,
    Observation,
)
from entropytrade.data.sources import file_hash
from entropytrade.domain.enums import MarketResult, MarketStatus
from entropytrade.domain.ids import canonical_json
from entropytrade.exchange.kalshi.recorded import market_from_body
from tests.exchange.test_gateway_http import _market_body
from tests.support import utc

WHEN = utc(2026, 10, 2, 15)


def config() -> DatasetConfig:
    return DatasetConfig(
        locations=(
            Location(
                name="Philadelphia",
                series="KXHIGHPHIL",
                station="CLIPHL",
                timezone="America/New_York",
            ),
            Location(
                name="Chicago", series="KXHIGHCHI", station="CLIMDW", timezone="America/Chicago"
            ),
        ),
        start=WHEN.date(),
        end=WHEN.date(),
        sources=("forecast", "kalshi"),
    )


def market() -> MarketEvidence:
    body = _market_body()
    found = market_from_body(body, captured_at=WHEN - timedelta(hours=1), series="KXHIGHPHIL")
    return MarketEvidence(
        market=found,
        created_at=utc(2026, 10, 2, 12),
        capture_basis="receipt",
        raw_ref="market.json",
        raw_hash="sha256:" + "a" * 64,
    )


def observation(*, delay: int = -1) -> Observation:
    at = WHEN + timedelta(hours=delay)
    return Observation(
        source_id="forecast",
        entity_id="CLIPHL",
        variable="high_f",
        valid_on=WHEN.date(),
        value=Decimal(91),
        issued_at=at - timedelta(hours=1),
        published_at=at,
        available_at=at,
        received_at=at + timedelta(minutes=1),
        timing_basis="provider_publication",
        evidence="archived provider release timestamp",
        raw_ref="forecast.json",
        raw_hash="sha256:" + "b" * 64,
    )


def test_future_revision_unknown_clock_and_settlement_never_enter_features() -> None:
    first = observation()
    later = observation(delay=1).revalidated(value=Decimal(110))
    uncertain = first.revalidated(timing_basis="unknown", value=Decimal(120))
    settlement = first.revalidated(
        role="observation", variable="final_daily_high", value=Decimal(100)
    )
    revised_late = first.revalidated(revised_at=WHEN + timedelta(hours=2), value=Decimal(150))
    before, _ = make_rows(config(), [market()], [first], [], "v")
    after, missing = make_rows(
        config(), [market()], [first, later, uncertain, settlement, revised_late], [], "v"
    )
    assert after[0]["features_json"] == before[0]["features_json"] == '{"forecast:high_f":"91"}'
    assert after[0]["outcome"] is None
    assert json.loads(after[0]["quality_json"])["excluded_observations"] == 4
    assert missing == ["KXHIGHCHI:2026-10-02"]
    assert len(after) == 1


def test_real_contract_strikes_and_sources_are_preserved_without_cli_relabeling() -> None:
    evidence = market()
    chicago = evidence.revalidated(
        market=evidence.market.revalidated(
            ticker="KXHIGHCHI-26OCT02-B70.5",
            event_ticker="KXHIGHCHI-26OCT02",
            series_ticker="KXHIGHCHI",
            rules=evidence.market.rules.revalidated(
                market_ticker="KXHIGHCHI-26OCT02-B70.5",
                rules_primary="Resolved using NWS Daily Climate Report",
                settlement_sources=(),
            ),
            result=MarketResult.NO,
            status=MarketStatus.FINALIZED,
        )
    )
    later = evidence.revalidated(
        market=evidence.market.revalidated(
            result=MarketResult.YES,
            status=MarketStatus.FINALIZED,
            rules=evidence.market.rules.revalidated(captured_at=WHEN + timedelta(days=1)),
        )
    )
    rows, missing = make_rows(config(), [evidence, later, chicago], [], [], "v")
    assert not missing
    assert {r["market_ticker"] for r in rows} == {evidence.market.ticker, chicago.market.ticker}
    phl = next(r for r in rows if r["city"] == "Philadelphia")
    assert phl["outcome"] == "yes"
    assert json.loads(phl["rules_json"])["settlement_sources"][0]["name"] == "The Weather Company"
    assert phl["features_json"] == "{}"
    assert phl["outcome_available_at"] == (WHEN + timedelta(days=1)).isoformat()


def test_candles_and_unverified_historical_metadata_cannot_be_executable() -> None:
    evidence = market().revalidated(
        market=market().market.revalidated(
            rules=market().market.rules.revalidated(captured_at=WHEN + timedelta(days=1))
        )
    )
    candle = MarketState(
        market_ticker=evidence.market.ticker,
        event_time=WHEN,
        fidelity="candle",
        payload={"volume_fp": "1000.00", "yes_ask": {"close": "0.40"}},
        raw_ref="candle.json",
        raw_hash="sha256:" + "c" * 64,
    )
    rows, _ = make_rows(config(), [evidence], [], [candle], "v")
    assert rows[0]["execution_fidelity"] == "candle"
    assert rows[0]["executable"] is False
    assert rows[0]["rules_known_at_decision"] is False
    assert rows[0]["contract_existed_at_decision"] is True


def test_repeated_builds_are_identical_and_detect_tampered_sources(tmp_path: Path) -> None:
    root = tmp_path / "source"
    root.mkdir()
    (root / "market.json").write_text(json.dumps(_market_body()), encoding="utf-8")
    (root / "forecast.json").write_text('{"high_f":"91"}', encoding="utf-8")
    evidence = market().revalidated(raw_hash=file_hash(root / "market.json"))
    obs = observation().revalidated(raw_hash=file_hash(root / "forecast.json"))
    (root / "markets.jsonl").write_text(
        evidence.model_dump_json(exclude_computed_fields=True) + "\n", encoding="utf-8"
    )
    (root / "observations.jsonl").write_text(obs.model_dump_json() + "\n", encoding="utf-8")
    output = tmp_path / "datasets"
    first = build_dataset(config=config(), sources=[root], output=output)
    second = build_dataset(config=config(), sources=[root], output=tmp_path / "fresh")
    assert first == second
    folder = output / first["dataset_version"].removeprefix("sha256:")
    fresh = tmp_path / "fresh" / first["dataset_version"].removeprefix("sha256:")
    assert file_hash(folder / "rows.parquet") == file_hash(fresh / "rows.parquet")
    assert file_hash(folder / "observations.parquet") == file_hash(fresh / "observations.parquet")
    rows = pq.read_table(folder / "rows.parquet").to_pylist()
    assert len(rows) == 1
    assert rows[0]["features_json"] == '{"forecast:high_f":"91"}'
    assert first["coverage"]["contracts"] == 1
    (root / "forecast.json").write_text('{"high_f":"110"}', encoding="utf-8")
    with pytest.raises(ValueError, match="hash mismatch"):
        build_dataset(config=config(), sources=[root], output=output)


@given(hours=st.integers(min_value=1, max_value=48))
def test_appending_future_information_cannot_improve_visible_forecast(hours: int) -> None:
    future = observation().revalidated(
        available_at=WHEN + timedelta(hours=hours), value=Decimal(123)
    )
    base, _ = make_rows(config(), [market()], [observation()], [], "v")
    altered, _ = make_rows(config(), [market()], [observation(), future], [], "v")
    assert altered[0]["features_json"] == base[0]["features_json"]


def test_unknown_and_receipt_based_timing_are_not_equivalent() -> None:
    unknown = observation().revalidated(timing_basis="unknown", available_at=None)
    assert not unknown.known_at(WHEN)
    with pytest.raises(ValueError, match="cannot precede receipt"):
        observation().revalidated(timing_basis="received")
    assert canonical_json(config().model_dump(mode="json"))


def test_recorder_metadata_and_books_flow_into_dataset_and_disconnect_invalidates(
    tmp_path: Path,
) -> None:
    from entropytrade.data.recording import recorded_inputs
    from entropytrade.domain.historical import ApiOrigin
    from entropytrade.exchange.feed import CollectorFeed
    from entropytrade.storage.recorder import Recorder
    from tests.exchange.test_feed_recorder import _snapshot

    store = Recorder(tmp_path / "collector.sqlite")
    store.bind_environment("production")
    evidence = market()
    raw = json.dumps({"markets": [_market_body()]}).encode()
    receipt = store.record_http(
        path="/markets", status=200, body=raw, received_at=evidence.market.rules.captured_at
    )
    store.save_market(evidence.market, ApiOrigin.LIVE, raw_receipt_id=receipt)
    session = store.start_session(WHEN - timedelta(hours=1))
    frame = _snapshot(1)
    feed = CollectorFeed()
    feed.note_reconnect(WHEN)
    effects = feed.apply(frame)
    store.record_message(
        session=session,
        ordinal=1,
        raw="original socket message",
        received_at=WHEN,
        frame=frame,
        effects=tuple(
            json.dumps({"kind": type(e).__name__, "value": e.model_dump(mode="json")})
            for e in effects
        ),
    )
    store.end_session(session, WHEN + timedelta(seconds=10), "stopped")
    store.close()
    metadata, states, digest = recorded_inputs(tmp_path / "collector.sqlite")
    assert len(metadata) == 1
    assert metadata[0].raw_ref == f"recording:http:{receipt}"
    assert metadata[0].created_at == utc(2026, 10, 2, 12)
    rows, _ = make_rows(config(), metadata, [], states, digest)
    assert rows[0]["execution_fidelity"] == "order_book"
    assert rows[0]["executable"] is True
    # No fill or current book may be inferred after the recorded disconnect.
    later = config().revalidated(decision_utc=("15:01",))
    after, _ = make_rows(later, metadata, [], states, digest)
    assert after[0]["executable"] is False
    assert after[0]["market_state_json"] is None


def test_market_state_rejects_event_time_disguised_as_receipt() -> None:
    with pytest.raises(ValueError, match="receipt clock"):
        MarketState(
            market_ticker="TEST",
            event_time=WHEN,
            available_at=WHEN,
            received_at=WHEN + timedelta(days=1),
            fidelity="quote",
            payload={},
            raw_ref="q",
            raw_hash="sha256:" + "a" * 64,
        )


def test_legacy_fetch_manifest_is_not_a_verified_historical_receipt() -> None:
    legacy = market().revalidated(capture_basis="legacy_manifest")
    rows, _ = make_rows(config(), [legacy], [], [], "v")
    assert rows[0]["rules_known_at_decision"] is False
    assert json.loads(rows[0]["quality_json"])["metadata_reconstructed"] is True
