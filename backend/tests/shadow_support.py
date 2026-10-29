"""CONTROLLED read-only wire fixtures; no actual fees, books or model performance evidence."""

import json

import httpx

from tests.exchange.test_gateway_http import _handler


def execution_wire(request: httpx.Request) -> httpx.Response:
    assert request.method == "GET"
    assert not any("authorization" in h or "kalshi-access" in h for h in request.headers)
    if request.url.path.endswith("/orderbook"):
        return httpx.Response(
            200,
            json={
                "orderbook_fp": {
                    "yes_dollars": [["0.4200", "10.00"]],
                    "no_dollars": [["0.5600", "4.00"]],
                }
            },
        )
    assert "/series/" in request.url.path
    ticker = request.url.path.split("/")[-1]
    payload = json.loads(
        _handler(
            httpx.Request("GET", "https://api.elections.kalshi.com/trade-api/v2/series/KXHIGHPHIL")
        ).content
    )
    payload["series"]["ticker"] = ticker
    return httpx.Response(200, json=payload)
