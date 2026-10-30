"""Date-blocked event splits and event-weighted probability evaluation."""

import math
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime
from itertools import pairwise
from typing import Any

import numpy as np
from sklearn.linear_model import LogisticRegression  # type: ignore[import-untyped]
from sklearn.metrics import brier_score_loss, log_loss  # type: ignore[import-untyped]


@dataclass(frozen=True)
class TemporalPlan:
    fit: tuple[str, ...]
    calibration: tuple[str, ...]
    validation: tuple[str, ...]
    holdout: tuple[str, ...]
    fit_asof: datetime
    calibration_asof: datetime


def temporal_plan(
    rows: list[dict[str, Any]], boundaries: tuple[date, date, date] | None = None
) -> TemporalPlan:
    by_date: dict[str, set[str]] = defaultdict(set)
    decisions: dict[str, datetime] = {}
    event_dates: dict[str, str] = {}
    for row in rows:
        event = row["event_id"]
        day = row["target_date"]
        if event in event_dates and event_dates[event] != day:
            raise ValueError("one event cannot span multiple target dates")
        event_dates[event] = day
        by_date[day].add(event)
        at = datetime.fromisoformat(row["decision_time"])
        decisions[day] = min(decisions.get(day, at), at)
    dates = sorted(by_date)
    if len(dates) < 10:
        raise ValueError("at least ten distinct event dates required for temporal evaluation")
    n = len(dates)
    train_end = int(n * 0.6)
    validation_end = int(n * 0.8)
    calibration_start = max(1, int(train_end * 0.8))
    groups = [
        dates[:calibration_start],
        dates[calibration_start:train_end],
        dates[train_end:validation_end],
        dates[validation_end:],
    ]
    if boundaries is not None:
        if not boundaries[0] < boundaries[1] < boundaries[2]:
            raise ValueError("frozen temporal boundaries must be strictly ordered")
        cuts = [boundary.isoformat() for boundary in boundaries]
        groups = [
            [d for d in dates if d < cuts[0]],
            [d for d in dates if cuts[0] <= d < cuts[1]],
            [d for d in dates if cuts[1] <= d < cuts[2]],
            [d for d in dates if d >= cuts[2]],
        ]
    ids = [tuple(sorted(e for day in days for e in by_date[day])) for days in groups]
    if not all(ids[:3]) or (boundaries is None and not ids[3]):
        raise ValueError("temporal partitions must all contain events")
    event_decisions: dict[str, list[datetime]] = defaultdict(list)
    for row in rows:
        event_decisions[row["event_id"]].append(datetime.fromisoformat(row["decision_time"]))
    fit_asof = min(t for e in ids[1] for t in event_decisions[e])
    calibration_asof = min(t for e in ids[2] for t in event_decisions[e])
    if boundaries is None:
        for earlier, later in pairwise(ids):
            if max(t for e in earlier for t in event_decisions[e]) >= min(
                t for e in later for t in event_decisions[e]
            ):
                raise ValueError("decision schedules overlap temporal date partitions")
    elif fit_asof >= calibration_asof:
        raise ValueError("retained fitting/calibration decision cutoffs overlap")
    # Calendar membership stays frozen. Actual first decisions bound availability;
    # overnight/repeated receipts never move a label into an earlier model fit.
    return TemporalPlan(
        ids[0],
        ids[1],
        ids[2],
        ids[3],
        fit_asof,
        calibration_asof,
    )


def walk_forward_plans(rows: list[dict[str, Any]]) -> list[TemporalPlan]:
    """Two fixed expanding windows, entirely before the protected final holdout.

    These are diagnostic repetitions of the predeclared candidates, not model selection.
    Each window has its own fit/calibration cutoffs; only its validation is evaluated.
    """
    final = temporal_plan(rows)
    permitted = set(final.fit + final.calibration + final.validation)
    history = [r for r in rows if r["event_id"] in permitted]
    days = sorted({r["target_date"] for r in history})
    if len(days) < 80:
        return []
    return [
        temporal_plan([r for r in history if r["target_date"] < days[int(len(days) * f)]])
        for f in (0.625, 0.875)
    ]


def metrics(predictions: list[dict[str, Any]], *, min_events: int = 20) -> dict[str, Any]:
    if not predictions:
        return {
            "status": "no_predictions",
            "independent_events": 0,
            "contracts": 0,
            "predictions": 0,
        }
    counts: dict[str, int] = defaultdict(int)
    for record in predictions:
        counts[record["event_id"]] += 1
    p = np.array([r["probability_yes"] for r in predictions], dtype=float)
    y = np.array([r["outcome"] == "yes" for r in predictions], dtype=int)
    weights = np.array([1 / counts[r["event_id"]] for r in predictions])
    bins = []
    if not np.isfinite(p).all() or not ((p >= 0) & (p <= 1)).all():
        raise ValueError("invalid predicted probabilities")
    for index in range(10):
        lower, upper = index / 10, (index + 1) / 10
        selected = (p >= lower) & (p < upper) if index < 9 else (p >= lower) & (p <= 1)
        if selected.any():
            bins.append(
                {
                    "lower": float(lower),
                    "predicted": float(np.average(p[selected], weights=weights[selected])),
                    "observed": float(np.average(y[selected], weights=weights[selected])),
                    "predictions": int(selected.sum()),
                }
            )
    result: dict[str, Any] = {
        "status": "evaluated" if len(counts) >= min_events else "descriptive_small_sample",
        "independent_events": len(counts),
        "contracts": len({r.get("market_ticker", i) for i, r in enumerate(predictions)}),
        "predictions": len(predictions),
        "independent_date_blocks": len(
            {r["target_date"] for r in predictions if "target_date" in r}
        ),
        "brier": float(brier_score_loss(y, p, sample_weight=weights)),
        "log_loss": float(
            log_loss(y, np.clip(p, 1e-9, 1 - 1e-9), sample_weight=weights, labels=[0, 1])
        ),
        "reliability_bins": bins,
        "calibration_intercept": None,
        "calibration_slope": None,
    }
    if len(counts) >= min_events and len(set(y)) > 1:
        values = np.clip(p, 1e-6, 1 - 1e-6)
        estimator = LogisticRegression(C=1000)
        estimator.fit(np.log(values / (1 - values)).reshape(-1, 1), y, sample_weight=weights)
        result["calibration_intercept"] = float(estimator.intercept_[0])
        result["calibration_slope"] = float(estimator.coef_[0, 0])
    if not all(math.isfinite(float(result[key])) for key in ("brier", "log_loss")):
        raise ValueError("invalid evaluation metrics")
    return result
