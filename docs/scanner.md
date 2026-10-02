# Structural scanner

Phase 7 compares executable asks inside one event. It does not call an
exchange and it does not use a model.

`scan_ladder` flags a higher `greater` strike whose YES ask is strictly above
a lower strike's YES ask. A crossed book is left out of the ladder.
`scan_exhaustive` flags a set of YES asks that sum to less than 1. That check
is only meaningful when the contracts are mutually exclusive and exhaustive;
the caller decides the set. `complement_gap` adds the YES ask to the NO ask
implied by the YES bid. On an uncrossed book that sum is at least 1, so the
function returns nothing. A crossed book is skipped rather than traded.

`paper_ladder` still reports the violation when it does not trade. It buys
one YES on the lower strike and one NO on the higher strike only when that
package, plus taker fees from the series schedule, costs less than 1, and
only when the risk gate approves both legs at the requested size. A rejection
or a fee that consumes the edge leaves the ledger unchanged. The coefficient
is an argument. Makers are not charged unless the schedule says so.

Books can be built from a recorded `BookSnapshotFrame`. Deltas are not folded
in here. A live WebSocket session is still unverified.
