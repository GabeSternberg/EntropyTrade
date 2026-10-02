"""Sequence gaps, reconnect, and restart-safe recording. No network."""

import json
from decimal import Decimal
from pathlib import Path

from entropytrade.domain.enums import MarketStatus, MarketType, OutcomeSide
from entropytrade.domain.historical import ApiOrigin
from entropytrade.domain.market import (
    Market,
    MarketRules,
    PriceRange,
    SettlementSource,
    TickSchedule,
)
from entropytrade.domain.market_data import TradePrint
from entropytrade.exchange.feed import (
    AppliedBook,
    AppliedTrade,
    CollectorFeed,
    GapEffect,
    StaleBook,
)
from entropytrade.exchange.frames import (
    BookDeltaFrame,
    BookLevel,
    BookSnapshotFrame,
    TradeFrame,
    parse_frame,
)
from entropytrade.exchange.kalshi.stream import LiveIngest
from entropytrade.exchange.sequence import GapKind
from entropytrade.exchange.settlement import parse_settlement
from entropytrade.storage.recorder import Recorder
from tests.support import utc

TICKER = "KXHIGHPHIL-26OCT02-T89"
WHEN = utc(2026, 10, 2, 15)


def _level(price: str, quantity: str) -> BookLevel:
    return BookLevel(price=Decimal(price), quantity=Decimal(quantity))


def _snapshot(seq: int, *, yes: str = "0.4200", no: str = "0.5600") -> BookSnapshotFrame:
    return BookSnapshotFrame(
        sid=7,
        seq=seq,
        market_ticker=TICKER,
        yes=(_level(yes, "10.00"),),
        no=(_level(no, "8.00"),),
        received_at=WHEN,
    )


def _delta(
    seq: int,
    *,
    side: str = "yes",
    price: str = "0.4200",
    delta: str = "-10.00",
) -> BookDeltaFrame:
    return BookDeltaFrame(
        sid=7,
        seq=seq,
        market_ticker=TICKER,
        side=side,  # type: ignore[arg-type]
        price=Decimal(price),
        delta=Decimal(delta),
        received_at=WHEN,
    )


def test_trade_gap_is_reported_and_the_print_is_kept() -> None:
    feed = CollectorFeed()
    feed.note_reconnect(WHEN)
    first = TradeFrame(
        sid=3,
        seq=1,
        market_ticker=TICKER,
        trade_id="t1",
        yes_price=Decimal("0.4000"),
        quantity=Decimal("1.00"),
        taker_side=OutcomeSide.YES,
        executed_at=WHEN,
        received_at=WHEN,
    )
    skipped = first.model_copy(update={"seq": 3, "trade_id": "t3"})
    assert feed.apply(first)[0].__class__ is AppliedTrade
    effects = feed.apply(skipped)
    assert isinstance(effects[0], GapEffect)
    assert effects[0].kind is GapKind.GAP
    assert effects[0].expected == 2
    assert isinstance(effects[1], AppliedTrade)
    assert effects[1].trade.trade_id == "t3"


def test_reconnect_refuses_deltas_until_a_snapshot() -> None:
    feed = CollectorFeed()
    feed.note_reconnect(WHEN)
    feed.apply(_snapshot(1))
    feed.note_disconnect(WHEN)
    feed.note_reconnect(WHEN)
    assert isinstance(feed.apply(_delta(2))[0], StaleBook)
    applied = feed.apply(_snapshot(1))
    assert isinstance(applied[0], AppliedBook)
    assert applied[0].book.best_bid is not None
    assert applied[0].book.best_bid.price == Decimal("0.4200")


def test_sdk_book_tracker_drops_a_gapped_delta_and_a_duplicate() -> None:
    feed = CollectorFeed()
    ingest = LiveIngest(feed)
    ingest.note_reconnect(WHEN)
    first = ingest.push(_snapshot(1))
    assert isinstance(first[0], AppliedBook)
    assert first[0].book.best_bid is not None
    gapped = ingest.push(_delta(3))
    assert isinstance(gapped[0], GapEffect)
    assert gapped[0].kind is GapKind.GAP
    assert feed.book(TICKER) is None
    again = ingest.push(_snapshot(4))
    assert isinstance(again[0], AppliedBook)
    applied = ingest.push(_delta(5, delta="-1.00"))
    assert isinstance(applied[0], AppliedBook)
    duplicate = ingest.push(_delta(5, delta="-1.00"))
    assert isinstance(duplicate[0], GapEffect)
    assert duplicate[0].kind is GapKind.DUPLICATE
    book = feed.book(TICKER)
    assert book is not None
    assert book.best_bid is not None
    assert book.best_bid.quantity == Decimal("9.00")


def test_no_bid_becomes_a_yes_ask() -> None:
    feed = CollectorFeed()
    feed.note_reconnect(WHEN)
    effect = feed.apply(_snapshot(1))
    assert isinstance(effect[0], AppliedBook)
    book = effect[0].book
    assert book.best_ask is not None
    assert book.best_ask.price == Decimal("0.4400")


def test_kxhigh_source_comes_from_the_contract_text() -> None:
    later = parse_settlement(
        "Resolved according to The Weather Company at weather.com/kalshi.",
        "",
        "KXHIGHPHIL-26OCT02-T89",
    )
    assert later.basis == "contract_text"
    assert later.sources[0].name == "The Weather Company"
    earlier = parse_settlement(
        "The market resolves on the NWS Daily Climate Report.",
        "",
        "KXHIGHPHIL-26JUL31-T89",
    )
    assert earlier.basis == "contract_text"
    assert earlier.sources[0].name == "NWS Daily Climate Report"
    scheduled = parse_settlement(
        "Highest temperature in Philadelphia.",
        "",
        "KXHIGHPHIL-26OCT02-T89",
    )
    assert scheduled.basis == "kxhigh_schedule"
    assert scheduled.sources[0].name == "The Weather Company"
    before = parse_settlement("Highest temperature in Philadelphia.", "", "KXHIGHPHIL-26JUL31-T89")
    assert before.sources[0].name == "NWS Daily Climate Report"
    less_is_not_inferred_here = parse_settlement("unrelated", "", "SOME-MARKET")
    assert less_is_not_inferred_here.basis == "unresolved"


def test_recorder_restart_does_not_duplicate_rows(tmp_path: Path) -> None:
    path = tmp_path / "recorder.sqlite"
    rules = MarketRules(
        market_ticker=TICKER,
        rules_primary="Resolved according to The Weather Company.",
        settlement_sources=(
            SettlementSource(name="The Weather Company", url="https://weather.com/kalshi"),
        ),
        captured_at=WHEN,
    )
    frame = _snapshot(1)
    trade = TradeFrame(
        sid=3,
        seq=1,
        market_ticker=TICKER,
        trade_id="trade-1",
        yes_price=Decimal("0.4000"),
        quantity=Decimal("2.00"),
        taker_side=OutcomeSide.NO,
        executed_at=WHEN,
        received_at=WHEN,
    )

    def write(store: Recorder) -> None:
        store.save_raw(
            origin=ApiOrigin.LIVE,
            path="/markets",
            status=200,
            body=b'{"ok":true}',
            received_at=WHEN,
        )
        store.save_frame(frame)
        store.save_trade(
            TradePrint(
                trade_id=trade.trade_id,
                market_ticker=trade.market_ticker,
                yes_price=trade.yes_price,
                quantity=trade.quantity,
                taker_side=trade.taker_side,
                executed_at=trade.executed_at,
                received_at=trade.received_at,
            ),
            ApiOrigin.LIVE,
        )

    market = Market(
        ticker=TICKER,
        event_ticker="KXHIGHPHIL-26OCT02",
        market_type=MarketType.BINARY,
        title="Philadelphia high",
        status=MarketStatus.ACTIVE,
        open_time=utc(2026, 10, 2, 8),
        close_time=utc(2026, 10, 3, 4),
        rules=rules,
        tick_schedule=TickSchedule(
            ranges=(PriceRange(start=Decimal(0), end=Decimal(1), step=Decimal("0.01")),)
        ),
        exchange_index=0,
    )
    store = Recorder(path)
    store.save_market(market, ApiOrigin.LIVE)
    store.save_market(
        market.revalidated(rules=rules.revalidated(captured_at=utc(2026, 10, 2, 16))),
        ApiOrigin.LIVE,
    )
    write(store)
    write(store)
    assert store.count("rule_versions") == 1
    assert store.count("market_metadata") == 1
    assert store.count("frames") == 1
    assert store.count("trades") == 1
    assert store.count("raw_payloads") == 1
    store.close()

    reopened = Recorder(path)
    write(reopened)
    assert reopened.count("frames") == 1
    assert reopened.count("trades") == 1
    payloads = reopened.frame_payloads()
    replayed = CollectorFeed()
    parsed = parse_frame(payloads[0])
    replayed.note_reconnect(parsed.received_at)
    effect = replayed.apply(parsed)
    assert isinstance(effect[0], AppliedBook)
    assert effect[0].book.best_bid is not None
    reopened.close()
    assert rules.rules_hash.startswith("sha256:")
    json.loads(payloads[0])


def test_adapter_source_does_not_call_from_env() -> None:
    root = Path(__file__).resolve().parents[2] / "src" / "entropytrade" / "exchange" / "kalshi"
    for path in root.rglob("*.py"):
        assert "from_env(" not in path.read_text(encoding="utf-8")
