"""Read-only series discovery: retained receipts, verified listing, no ranking or selection."""

import asyncio
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest

from entropytrade.domain.time import SimulatedClock
from entropytrade.families.discovery import (
    DISCOVERY_SCHEMA,
    LISTING_SCHEMA,
    discover_series,
    list_discovered,
)
from entropytrade.families.screening import ScreeningError

CATALOG: dict[str, list[dict[str, Any]]] = {
    "Economics": [
        {
            "ticker": "KXZETA",
            "title": "Zeta index",
            "category": "Economics",
            "frequency": "monthly",
            "tags": ["Index", "Index"],
            "fee_type": "quadratic",
            "settlement_sources": [{"name": "Agency", "url": "https://agency.example"}],
        },
        {"ticker": "KXALPHA", "title": "Alpha", "category": "Economics", "frequency": "weekly"},
    ],
    "Science and Technology": [
        {"ticker": "KXBETA", "title": "Beta", "category": "Science and Technology"}
    ],
}


def responder(seen: list[httpx.Request]) -> Any:
    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        category = request.url.params["category"]
        if category not in CATALOG:
            return httpx.Response(503, text="unavailable")
        return httpx.Response(200, json={"series": CATALOG[category]})

    return handle


def discover(root: Path, categories: list[str], seen: list[httpx.Request]) -> dict[str, Any]:
    clock = SimulatedClock(datetime(2026, 11, 6, tzinfo=UTC))
    return asyncio.run(
        discover_series(root, categories, inner=httpx.MockTransport(responder(seen)), clock=clock)
    )


def test_discovery_retains_every_response_and_lists_deterministically(tmp_path: Path) -> None:
    seen: list[httpx.Request] = []
    root = tmp_path / "discover"
    manifest = discover(root, ["Economics", "Science and Technology", "Missing"], seen)
    assert manifest["schema"] == DISCOVERY_SCHEMA
    assert [c["status"] for c in manifest["calls"]] == [200, 200, 503]
    assert manifest["calls"][-1]["path"].endswith(".error.json")
    assert (root / manifest["calls"][-1]["path"]).read_bytes() == b"unavailable"
    assert all(r.method == "GET" and "authorization" not in r.headers for r in seen)
    assert all(r.url.path == "/trade-api/v2/series" for r in seen)

    listing = list_discovered([root])
    assert listing["schema"] == LISTING_SCHEMA
    assert [r["ticker"] for r in listing["series"]] == ["KXALPHA", "KXBETA", "KXZETA"]
    assert listing["counts"]["by_category"] == {"Economics": 2, "Science and Technology": 1}
    zeta = listing["series"][2]
    assert zeta["tags"] == ["Index"]
    assert zeta["settlement_sources"] == ["Agency"]
    assert zeta["receipt_sha256"] == manifest["calls"][0]["sha256"]
    assert listing["unusable_calls"] == [{"category": "Missing", "status": 503, "error": None}]
    assert list_discovered([root]) == listing  # No wall-clock or ordering dependence.
    with pytest.raises(FileExistsError):
        discover(root, ["Economics"], [])


def test_tampered_or_escaping_receipts_refuse(tmp_path: Path) -> None:
    root = tmp_path / "discover"
    manifest = discover(root, ["Economics"], [])
    receipt = root / manifest["calls"][0]["path"]
    original = receipt.read_bytes()
    receipt.write_bytes(original + b" ")
    with pytest.raises(ScreeningError, match="hash does not match"):
        list_discovered([root])
    receipt.write_bytes(original)
    manifest["calls"][0]["path"] = "../outside.json"
    (root / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ScreeningError, match="escapes"):
        list_discovered([root])


def test_conflicting_descriptions_of_one_ticker_refuse(tmp_path: Path) -> None:
    first = tmp_path / "a"
    discover(first, ["Economics"], [])
    second = tmp_path / "b"
    CATALOG["Conflict"] = [{"ticker": "KXALPHA", "title": "Different", "category": "Economics"}]
    try:
        discover(second, ["Conflict"], [])
    finally:
        del CATALOG["Conflict"]
    with pytest.raises(ScreeningError, match="conflicting"):
        list_discovered([first, second])
    # The identical description retained twice is the same series, listed once.
    third = tmp_path / "c"
    discover(third, ["Economics"], [])
    assert len(list_discovered([first, third])["series"]) == 2


@pytest.mark.parametrize(
    "body",
    [{"series": {"ticker": "KXA"}}, {"series": [{"title": "no ticker"}]}, ["KXA"]],
)
def test_malformed_listings_refuse(tmp_path: Path, body: object) -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=body)

    root = tmp_path / "discover"
    asyncio.run(discover_series(root, ["Economics"], inner=httpx.MockTransport(handle)))
    with pytest.raises(ScreeningError):
        list_discovered([root])


def test_transport_errors_and_byte_budget_are_recorded_without_retry(tmp_path: Path) -> None:
    calls: list[str] = []

    def handle(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.params["category"])
        if request.url.params["category"] == "Economics":
            raise httpx.ConnectError("offline", request=request)
        return httpx.Response(200, content=b"x" * 2_000_001)

    root = tmp_path / "discover"
    manifest = asyncio.run(
        discover_series(root, ["Economics", "Sports"], inner=httpx.MockTransport(handle))
    )
    assert calls == ["Economics", "Sports"]
    assert manifest["calls"][0]["error"].startswith("ConnectError")
    assert "byte budget" in manifest["calls"][1]["error"]
    assert list(root.joinpath("raw").iterdir()) == []
    assert len(list_discovered([root])["unusable_calls"]) == 2


@pytest.mark.parametrize(
    "categories", [[], ["Economics", "Economics"], ["../x"], ["a" * 61], ["C"] * 13]
)
def test_invalid_categories_refuse_before_any_request(
    tmp_path: Path, categories: list[str]
) -> None:
    def forbidden(request: httpx.Request) -> httpx.Response:
        raise AssertionError("no request may be sent")

    with pytest.raises(ScreeningError):
        asyncio.run(
            discover_series(tmp_path / "x", categories, inner=httpx.MockTransport(forbidden))
        )
    assert not (tmp_path / "x").exists()


def test_transport_permits_only_the_series_list() -> None:
    from entropytrade.families.discovery import DiscoveryTransport

    transport = DiscoveryTransport()
    assert transport.permits_path(httpx.URL("https://api.elections.kalshi.com/trade-api/v2/series"))
    for url in (
        "https://api.elections.kalshi.com/trade-api/v2/series/KXA",
        "https://api.elections.kalshi.com/trade-api/v2/markets",
        "https://api.elections.kalshi.com/trade-api/v2/portfolio/orders",
        "https://example.com/trade-api/v2/series",
    ):
        assert not transport.permits_path(httpx.URL(url))


def test_cli_lists_retained_discovery_offline(tmp_path: Path) -> None:
    root = tmp_path / "discover"
    discover(root, ["Economics"], [])
    output = tmp_path / "listing.json"
    command = [sys.executable, "-c", "from entropytrade.cli import main; main()"]
    command += ["family-discover", "--discovered", str(root), "--output", str(output)]
    done = subprocess.run(  # noqa: S603 - fixed interpreter and temporary paths
        command, capture_output=True, text=True, check=True
    )
    assert "| KXZETA | Economics | monthly | quadratic | Agency | Zeta index |" in done.stdout
    assert json.loads(output.read_text()) == list_discovered([root])
    refused = subprocess.run(  # noqa: S603 - fixed interpreter and temporary paths
        command, capture_output=True, text=True, check=False
    )
    assert refused.returncode != 0
    assert "already exists" in refused.stderr
