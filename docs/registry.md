# Strategy registry

Phase 6 stores every spec the research pipeline emits and shows them on a
read-only page.

`Registry` is one SQLite file. A spec hash is inserted once. Version 1 has no
parent. A later version names a parent hash that is already stored. The same
pipeline result can be recorded twice; the second write does not add a version
or walk the lifecycle backward.

A recorded backtest moves `draft → research → backtested`. A rejection stops
at `research`. Those steps use an agent actor. They do not increase real
capital, so they need no human approval. A move into `live_small` still goes
through `LifecycleTransition`: an agent is rejected even if an approval object
is attached. A human actor with an approval that precedes the transition is
accepted. The Philadelphia demo is not promoted that far.

`log_rows` writes a local MLflow experiment named `entropytrade`. Equity is a
string parameter (`100.600000`), not a float metric. The function does not
start a tracking server.

`render_page` lists strategy, state, verdict, equity, hypothesis, and digest.
An empty registry says that nothing has been recorded. `GET /` serves that
page. `POST` is refused. The page has no submit control.

```bash
uv run python -c "
from pathlib import Path
from entropytrade.strategy_registry.dashboard import serve
from entropytrade.strategy_registry.store import load_philadelphia
serve(load_philadelphia(Path('/tmp/entropytrade-registry.sqlite')), port=43127)
"
```

The page is `http://127.0.0.1:43127/`. It cannot place an order.
