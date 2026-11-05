"""Family screening: deterministic catalog summaries, fail-closed receipts, bounded fetch."""

import asyncio
import hashlib
import json
import subprocess
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest

from entropytrade.domain.time import SimulatedClock
from entropytrade.families.screening import (
    FETCH_SCHEMA,
    ScreeningError,
    fetch_catalog,
    load_catalog,
    render_table,
    screen,
)

REPO = Path(__file__).resolve().parents[3]


def market(
    ticker: str,
    *,
    status: str = "finalized",
    result: str = "no",
    close: str = "2026-01-01T05:00:00Z",
    volume: str = "10.00",
    updated: str = "2026-01-02T00:00:00Z",
    **extra: Any,
) -> dict[str, Any]:
    event = ticker.rsplit("-", 1)[0]
    return {
        "ticker": ticker,
        "event_ticker": event,
        "status": status,
        "result": result,
        "close_time": close,
        "market_type": "binary",
        "strike_type": "between",
        "volume_fp": volume,
        "updated_time": updated,
        "rules_primary": f"If the value for {close[:10]} is between 1-2, resolves Yes.",
        **extra,
    }


def ladder(series: str, days: int, start: date = date(2026, 1, 1)) -> list[dict[str, Any]]:
    """One YES and two NO contracts per daily event."""
    out = []
    for offset in range(days):
        day = start + timedelta(days=offset)
        close = f"{day.isoformat()}T05:00:00Z"
        stem = f"{series}-{day.strftime('%y%b%d').upper()}"
        out += [
            market(f"{stem}-B1", result="yes", close=close),
            market(f"{stem}-B2", close=close),
            market(f"{stem}-B3", close=close, volume="0"),
        ]
    return out


def write(path: Path, body: object) -> Path:
    path.write_text(json.dumps(body))
    return path


def test_screen_counts_events_dates_outcomes_and_gate(tmp_path: Path) -> None:
    receipt = write(tmp_path / "a.json", {"markets": ladder("KXA", 40), "cursor": ""})
    short = write(tmp_path / "b.json", ladder("KXB", 5))
    report = screen(load_catalog([receipt, short]))

    rows = {row["series"]: row for row in report["series"]}
    a, b = rows["KXA"], rows["KXB"]
    assert (a["markets"], a["events"], a["close_dates"]) == (120, 40, 40)
    assert a["labeled_markets"] == {"yes": 40, "no": 80}
    assert (a["labeled_events"], a["labeled_dates"]) == (40, 40)
    assert a["traded_market_fraction"] == "0.667"
    assert a["total_volume"] == "800"
    assert a["markets_per_event_median"] == 3
    assert a["label_history_minimum"] == {
        "required_events": 40,
        "required_dates": 20,
        "met": True,
        "shortfalls": [],
    }
    assert b["label_history_minimum"]["shortfalls"] == [
        "5/40 finalized binary events",
        "5/20 finalized close dates",
    ]
    assert [i["sha256"] for i in report["inputs"]] == [
        "sha256:" + hashlib.sha256(p.read_bytes()).hexdigest() for p in (receipt, short)
    ]
    assert "KXA" in render_table(report)


def test_unresolved_or_one_sided_history_does_not_meet_minimum(tmp_path: Path) -> None:
    rows = ladder("KXC", 45)
    for row in rows:
        row["result"] = "no"
    rows.append(market("KXC-27JAN01-B1", status="active", result="", close="2027-01-01T05:00:00Z"))
    report = screen(load_catalog([write(tmp_path / "c.json", rows)]))
    row = report["series"][0]
    assert row["unlabeled_markets"] == 1
    assert row["labeled_events"] == 45  # The open event is not counted as labeled.
    assert row["events"] == 46
    assert row["label_history_minimum"]["shortfalls"] == [
        "finalized outcomes do not include both YES and NO"
    ]


def test_screen_is_deterministic_and_order_independent(tmp_path: Path) -> None:
    first = write(tmp_path / "1.json", ladder("KXA", 3))
    second = write(tmp_path / "2.json", ladder("KXB", 3))
    one = screen(load_catalog([first, second]))
    two = screen(load_catalog([second, first]))
    assert one["series"] == two["series"]
    assert json.dumps(one, sort_keys=True) == json.dumps(
        screen(load_catalog([first, second])), sort_keys=True
    )


def test_later_updated_time_wins_and_is_counted(tmp_path: Path) -> None:
    early = market("KXA-26JAN01-B1", status="active", result="", updated="2026-01-01T00:00:00Z")
    late = market("KXA-26JAN01-B1", result="yes", updated="2026-01-02T00:00:00Z")
    for order in ([late], [early]), ([early], [late]):
        paths = [write(tmp_path / f"{i}.json", body) for i, body in enumerate(order)]
        report = screen(load_catalog(paths))
        assert report["revised_tickers"] == 1
        assert report["series"][0]["labeled_markets"] == {"yes": 1, "no": 0}


def test_unordered_receipts_merge_cumulative_volume_and_final_result(tmp_path: Path) -> None:
    """Repeated polls can share updated_time while lifetime volume grows."""
    polled = market("KXA-26JAN01-B1", status="active", result="", volume="5.00")
    final = market("KXA-26JAN01-B1", volume="233.36", open_interest_fp="9")
    for order in ([polled], [final]), ([final], [polled]):
        paths = [write(tmp_path / f"{i}.json", body) for i, body in enumerate(order)]
        report = screen(load_catalog(paths))
        row = report["series"][0]
        assert report["merged_tickers"] == 1
        assert row["total_volume"] == "233.36"
        assert row["labeled_markets"] == {"yes": 0, "no": 1}


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"result": "yes"}, "different final results"),
        ({"close_time": "2026-01-03T05:00:00Z"}, "disagree on close_time"),
        ({"rules_primary": "other"}, "disagree on rules_primary"),
    ],
)
def test_unordered_contradictions_refuse(
    tmp_path: Path, change: dict[str, str], message: str
) -> None:
    base = market("KXA-26JAN01-B1")
    paths = [write(tmp_path / "1.json", [base]), write(tmp_path / "2.json", [base | change])]
    with pytest.raises(ScreeningError, match=message):
        load_catalog(paths)


@pytest.mark.parametrize(
    "body",
    [
        {"unexpected": []},
        {"markets": {}},
        [{"ticker": "KXA-1"}],
        ["not-an-object"],
        [{"ticker": "KXA-26JAN01-B1", "event_ticker": "KXA-26JAN01", "volume_fp": "-1"}],
        [{"ticker": "KXA-26JAN01-B1", "event_ticker": "KXA-26JAN01", "close_time": "bad"}],
        {"series": {"title": "no ticker"}},
    ],
)
def test_malformed_receipts_refuse(tmp_path: Path, body: object) -> None:
    with pytest.raises(ScreeningError):
        screen(load_catalog([write(tmp_path / "bad.json", body)]))


def test_no_receipts_and_non_json_refuse(tmp_path: Path) -> None:
    with pytest.raises(ScreeningError, match="no receipts"):
        load_catalog([])
    bad = tmp_path / "bad.json"
    bad.write_text("<html>")
    with pytest.raises(ScreeningError, match="not JSON"):
        load_catalog([bad])


def test_series_metadata_is_reported_without_markets(tmp_path: Path) -> None:
    metadata = {
        "ticker": "KXNEW",
        "title": "New",
        "frequency": "weekly",
        "fee_type": "quadratic",
        "fee_multiplier": 1,
        "settlement_sources": [{"name": "Agency", "url": "https://example.invalid"}],
        "unrelated": "dropped",
    }
    report = screen(load_catalog([write(tmp_path / "s.json", {"series": metadata})]))
    row = report["series"][0]
    assert row["markets"] == 0
    assert row["series_metadata"]["fee_type"] == "quadratic"
    assert "unrelated" not in row["series_metadata"]
    assert row["label_history_minimum"]["shortfalls"] == ["no market receipts"]
    assert report["inputs"][0]["series_metadata"] == "KXNEW"
    conflicting = write(tmp_path / "t.json", {"series": metadata | {"fee_multiplier": 2}})
    with pytest.raises(ScreeningError, match="conflicting series metadata"):
        load_catalog([tmp_path / "s.json", conflicting])


def responder(pages: dict[str, list[dict[str, Any]]], seen: list[httpx.Request]) -> Any:
    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        path = request.url.path
        if path.startswith("/trade-api/v2/series/"):
            name = path.rsplit("/", 1)[1]
            if name == "KXDOWN":
                return httpx.Response(503, text="unavailable")
            return httpx.Response(200, json={"series": {"ticker": name, "fee_type": "quadratic"}})
        name = request.url.params["series_ticker"]
        kind = "historical" if "historical" in path else "live"
        cursor = request.url.params.get("cursor", "")
        index = int(cursor or 0)
        chunks = pages.get(f"{name}:{kind}", [])
        rows = chunks[index] if index < len(chunks) else {"markets": []}
        nxt = str(index + 1) if index + 1 < len(chunks) else ""
        return httpx.Response(200, json={"markets": rows["markets"], "cursor": nxt})

    return handle


def test_fetch_retains_every_response_and_screens_verified_receipts(tmp_path: Path) -> None:
    rows = ladder("KXA", 4)
    pages = {
        "KXA:live": [{"markets": rows[:6]}, {"markets": rows[6:]}],
        "KXA:historical": [{"markets": rows[:3]}],
    }
    seen: list[httpx.Request] = []
    clock = SimulatedClock(datetime(2026, 11, 5, tzinfo=UTC))
    root = tmp_path / "fetch"
    manifest = asyncio.run(
        fetch_catalog(
            root,
            ["KXA", "KXDOWN"],
            inner=httpx.MockTransport(responder(pages, seen)),
            clock=clock,
        )
    )
    assert manifest["schema"] == FETCH_SCHEMA
    assert [c["status"] for c in manifest["calls"]] == [200, 200, 200, 200, 503]
    assert manifest["calls"][-1]["path"].endswith(".error.json")
    assert all(r.method == "GET" and "authorization" not in r.headers for r in seen)
    assert seen[2].url.params["cursor"] == "1"
    with pytest.raises(FileExistsError):
        asyncio.run(fetch_catalog(root, ["KXA"], inner=httpx.MockTransport(responder({}, []))))

    report = screen(load_catalog(fetched=[root]))
    rows_by_series = {r["series"]: r for r in report["series"]}
    assert rows_by_series["KXA"]["markets"] == 12
    assert rows_by_series["KXA"]["series_metadata"]["fee_type"] == "quadratic"
    assert "KXDOWN" not in rows_by_series  # Failed responses are retained, never screened.

    tampered = root / manifest["calls"][1]["path"]
    tampered.write_bytes(tampered.read_bytes() + b" ")
    with pytest.raises(ScreeningError, match="hash does not match"):
        load_catalog(fetched=[root])


def test_fetch_records_transport_errors_and_budget_without_retry(tmp_path: Path) -> None:
    calls = 0

    def handle(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if request.url.path.endswith("/KXERR"):
            raise httpx.ConnectError("proxy denied", request=request)
        if "series_ticker" in request.url.params:
            return httpx.Response(200, json={"markets": [], "cursor": "more"})
        return httpx.Response(200, json={"series": {"ticker": "X"}})

    manifest = asyncio.run(
        fetch_catalog(
            tmp_path / "f",
            ["KXERR"] + [f"KXS{i}" for i in range(5)],
            max_pages=5,
            inner=httpx.MockTransport(handle),
        )
    )
    errors = [c for c in manifest["calls"] if "error" in c]
    assert errors[0]["error"].startswith("ConnectError")
    assert any("budget exceeded" in c["error"] for c in errors[1:])
    assert calls == 20  # The inherited per-run request cap holds; nothing is retried.


@pytest.mark.parametrize("series", [[], ["kxlower"], ["../markets"], ["A" * 41]])
def test_fetch_rejects_invalid_series_before_any_request(tmp_path: Path, series: list[str]) -> None:
    def forbidden(request: httpx.Request) -> httpx.Response:
        raise AssertionError(f"unexpected request {request.url}")

    with pytest.raises(ScreeningError):
        asyncio.run(fetch_catalog(tmp_path / "x", series, inner=httpx.MockTransport(forbidden)))
    assert not (tmp_path / "x").exists()


def test_cli_screens_retained_public_receipts_without_network(tmp_path: Path) -> None:
    """Actual retained KXHIGHPHIL catalog receipts screen offline and reproducibly."""
    receipts = sorted((REPO / "data/public/kalshi-public").glob("historical-0*.json"))
    receipts += sorted((REPO / "data/public/kalshi-public").glob("markets-*.json"))
    receipts.append(REPO / "data/public/kalshi-fees/KXHIGHPHIL.json")
    args = [a for p in receipts for a in ("--receipt", str(p))]
    output = tmp_path / "screen.json"
    command = [sys.executable, "-c", "from entropytrade.cli import main; main()"]
    command += ["family-screen", *args]
    done = subprocess.run(  # noqa: S603 - fixed interpreter and repository paths
        [*command, "--output", str(output)], capture_output=True, text=True, check=True
    )
    assert "| KXHIGHPHIL |" in done.stdout
    report = json.loads(output.read_text())
    row = report["series"][0]
    assert row["series"] == "KXHIGHPHIL"
    assert row["labeled_events"] >= 40
    assert row["label_history_minimum"]["met"]
    assert row["series_metadata"]["frequency"] == "daily"
    refused = subprocess.run(  # noqa: S603 - fixed interpreter and repository paths
        [*command, "--output", str(output)], capture_output=True, text=True, check=False
    )
    assert refused.returncode != 0
    assert "already exists" in refused.stderr


def test_rule_templates_ignore_dates_and_strikes_but_count_wording(tmp_path: Path) -> None:
    rows = [
        market("KXA-26JAN01-B1", rules_primary="High for January 01, 2026 is 35-36°, Yes."),
        market("KXA-26FEB02-B1", rules_primary="High for Feb 2, 2026 is 40-41°, Yes."),
        market("KXA-26MAY03-B1", rules_primary="High for May 3, 2026 is 50-51°, Yes."),
        market("KXA-26OCT03-B1", rules_primary="Max at CLIPHL for Oct 3, 2026 per TWC, Yes."),
    ]
    report = screen(load_catalog([write(tmp_path / "r.json", rows)]))
    assert report["series"][0]["rule_templates"] == 2
