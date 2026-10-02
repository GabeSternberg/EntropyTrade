"""Philadelphia forecast revision. The rule is frozen. It is not scored.

Two vintages of the same valid day are required. The stored previous-runs
file has one lead-time series. The previous-runs API refused a model run.
No rows are invented. This module does not open a socket.
"""

import json
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from entropytrade.weather.informational_rules import (
    BRACKET_CAP,
    BRACKET_FLOOR,
    PRICE_THRESHOLD,
)

RULE_NAME = "forecast_revision_up"
FIDELITY = "trade-print"
DECISION_HOUR_UTC = 15
EARLIER_HOUR_UTC = 3
REVISION_MINIMUM_F = Decimal(2)
_NOT_SCORED = "not scored"
_ERROR = Path("open-meteo/two-vintages.error.json")
_CALL = Path("open-meteo/two-vintages.json")
_PREVIOUS = Path("open-meteo/previous-runs.json")


@dataclass(frozen=True)
class RevisionAttempt:
    """One hypothesis. ``scored`` and ``promoted`` stay false."""

    name: str
    hypotheses: int
    scored: bool
    promoted: bool
    two_vintages: bool
    fires: str
    fills: str
    optimistic_equity: str
    validation_equity: str
    fidelity: str
    guaranteed_fill: bool
    http_status: int
    error_body: str


def load_revision(root: Path) -> RevisionAttempt:
    """Read the stored refusal. A missing vintage is not turned into a row."""
    _frozen()
    call = _object(root / _CALL)
    url = _text(call.get("url"), "url")
    if not url.startswith("https://previous-runs-api.open-meteo.com/"):
        raise ValueError("the vintage call did not use previous-runs")
    if "run=" not in url:
        raise ValueError("the vintage call did not ask for a model run")
    if call.get("http_status") != 400:
        raise ValueError("the vintage call was not the stored refusal")
    if call.get("two_vintages") is not False or call.get("scored") is not False:
        raise ValueError("the vintage call claims a score")
    if call.get("promoted") is not False:
        raise ValueError("the revision was promoted")
    body = (root / _ERROR).read_text(encoding="utf-8")
    parsed = json.loads(body)
    if not isinstance(parsed, dict) or parsed.get("error") is not True:
        raise ValueError("the stored body is not an API error")
    if "temperature" in body or "hourly" in body:
        raise ValueError("the error body contains a forecast row")
    previous = _object(root / _PREVIOUS)
    if "available_at" in previous or "run" in previous:
        raise ValueError("previous-runs names a vintage the rule did not store")
    hourly = previous.get("hourly")
    if not isinstance(hourly, dict):
        raise ValueError("previous-runs has no hourly object")
    series = tuple(key for key in hourly if key != "time")
    if series != ("temperature_2m_previous_day1",):
        raise ValueError("previous-runs is not the single stored series")
    return RevisionAttempt(
        name=RULE_NAME,
        hypotheses=1,
        scored=False,
        promoted=False,
        two_vintages=False,
        fires=_NOT_SCORED,
        fills=_NOT_SCORED,
        optimistic_equity=_NOT_SCORED,
        validation_equity=_NOT_SCORED,
        fidelity=FIDELITY,
        guaranteed_fill=False,
        http_status=400,
        error_body=body,
    )


def revision_lines(root: Path) -> tuple[str, ...]:
    """The scan note's revision section. It does not invent equity."""
    attempt = load_revision(root)
    if attempt.scored or attempt.two_vintages or attempt.promoted:
        raise ValueError("the revision section must not invent a score")
    return (
        "## Revision",
        "",
        f"`{attempt.name}` is one hypothesis. It was not scored.",
        "",
        "At 15:00 UTC, take two vintages of the same valid day's hourly",
        "temperature whose available_at is at or before the decision. Later",
        "vintage: latest run with available_at <= 15:00 UTC. Earlier vintage:",
        "latest run with available_at <= 03:00 UTC the same day. Daily max is",
        "the max of that vintage's hourly values. Revision = later_max -",
        "earlier_max. If either vintage is missing, no trade.",
        "",
        "The rule fires only when revision >= 2 F and the later max is inside",
        "80-81 inclusive. Optimistic may assume one YES at a B80.5 print at or",
        "before 15:00 UTC with price <= 0.40. Base and conservative do not",
        "treat a print as a fill. Fidelity is trade-print. A print is not a",
        "guaranteed fill. The fee coefficient stays unset. Train, then",
        "validation. The holdout is not scored.",
        "",
        "Two vintages are not on disk. The previous-runs API refused a model",
        "run. The stored body is:",
        "",
        attempt.error_body,
        "",
        f"Fires: {attempt.fires}. Fills: {attempt.fills}.",
        f"Optimistic equity: {attempt.optimistic_equity}.",
        f"Validation equity: {attempt.validation_equity}.",
        "Nothing was promoted.",
    )


def _frozen() -> None:
    if Decimal(80) != BRACKET_FLOOR or Decimal(81) != BRACKET_CAP:
        raise ValueError("the bracket was changed")
    if Decimal("0.4000") != PRICE_THRESHOLD:
        raise ValueError("the price threshold was changed")
    if Decimal(2) != REVISION_MINIMUM_F:
        raise ValueError("the revision minimum was changed")
    if DECISION_HOUR_UTC != 15 or EARLIER_HOUR_UTC != 3:
        raise ValueError("the revision clock was changed")


def _object(path: Path) -> dict[str, object]:
    payload: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path.name} is not an object")
    return payload


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or value == "":
        raise ValueError(f"{label} is missing")
    return value
