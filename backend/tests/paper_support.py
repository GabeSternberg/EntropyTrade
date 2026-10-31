"""Explicitly synthetic accounting fixtures, never an authentic trade/model/fee claim."""

from datetime import timedelta
from decimal import Decimal
from typing import Any

from entropytrade.tracking.accounting import account_hash
from entropytrade.tracking.replay import decision_inputs
from tests.fee_support import controlled_fee
from tests.unit.test_tracking import ready


def paper_inputs(before: dict[str, Any] | None = None, *, seconds: int = 0) -> dict[str, Any]:
    spec, data, bundle, _ = ready()
    spec = spec.revalidated(
        position_sizing=spec.position_sizing.revalidated(
            contracts=Decimal("2"), max_contracts=Decimal("1000")
        ),
        execution=spec.execution.revalidated(time_in_force="immediate_or_cancel"),
    )
    sample = data.samples[0]
    when = sample.decision_time + timedelta(seconds=seconds)
    assert sample.book is not None
    book = sample.book.revalidated(received_at=when)
    sample = sample.revalidated(decision_time=when, book=book)
    data = data.revalidated(samples=(sample,))
    prediction = (
        next(p for p in bundle.records if p.usable(data.samples[0]))
        if not seconds
        else (
            next(p for p in bundle.records if p.ticker == sample.ticker).revalidated(
                decision_time=when
            )
        )
    )
    bundle = bundle.revalidated(records=(prediction,))
    fill_at = when + timedelta(seconds=2)
    return {
        "schema": "shadow-paper-inputs-v2",
        "before": before,
        "before_hash": account_hash(before),
        "as_of": fill_at.isoformat(),
        "decision_inputs": decision_inputs(spec, data, bundle, fee_versions=(controlled_fee(),)),
        "event_ids": {sample.ticker: sample.event_id},
        "close_times": {sample.ticker: sample.close_time.isoformat()},
        "outcomes": [],
        "execution_series_fees": [],
        "execution_books": {
            sample.ticker: book.revalidated(received_at=fill_at).model_dump(mode="json")
        },
    }
