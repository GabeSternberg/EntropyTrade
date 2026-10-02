"""Maker fractions stated in the vendored Kalshi series reference.

``.agents/skills/kalshi-docs/api-reference/market/get-series.md`` says
``quadratic_with_combo_maker_fees`` uses a 0.5 maker multiplier instead of
0.25. That file does not state the taker quadratic coefficient. The
fee-schedule PDF is the document that would, and the retry of it returned
HTTP 429. This module does not invent a coefficient.
"""

from decimal import Decimal

from entropytrade.domain.enums import FeeType

PUBLISHED_FEE_VERSION = "kalshi-docs-maker-fractions-v1"
CITATION = ".agents/skills/kalshi-docs/api-reference/market/get-series.md"
ROUNDING_CITATION = ".agents/skills/kalshi-docs/getting_started/fee_rounding.md"

# The cited sentence names these two maker multipliers. ``quadratic`` is the
# general table, not the maker-fee structure, so its maker fraction is zero.
MAKER_FRACTIONS: dict[FeeType, Decimal] = {
    FeeType.QUADRATIC: Decimal(0),
    FeeType.QUADRATIC_WITH_MAKER_FEES: Decimal("0.25"),
    FeeType.QUADRATIC_WITH_COMBO_MAKER_FEES: Decimal("0.5"),
}

# Not stated in CITATION or in ROUNDING_CITATION. Left unset on purpose.
QUADRATIC_COEFFICIENT: Decimal | None = None
