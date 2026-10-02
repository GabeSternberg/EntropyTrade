"""HTML for the strategy registry. It cannot submit an order.

``POST /halt`` writes the local HALT sentinel when a directory was configured.
``POST /`` stays refused. Nothing here reaches an exchange.
"""

import html
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from entropytrade.risk.engine import halt_sentinel
from entropytrade.strategy_registry.store import Registry, RegistryRow

_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>EntropyTrade registry</title>
<style>
body {{ font-family: system-ui, sans-serif; margin: 1.25rem; color: #1c1917; }}
table {{ border-collapse: collapse; width: 100%; }}
th, td {{
  border-bottom: 1px solid #d6d3d1;
  text-align: left;
  padding: 0.45rem;
  vertical-align: top;
}}
td.narrow {{ word-break: break-all; }}
</style>
</head>
<body>
<h1>Strategy registry</h1>
<p>This page cannot submit an order or approve live capital.</p>
{pause}
{body}
</body>
</html>
"""

_PAUSE = (
    '<form method="post" action="/halt">'
    '<button type="submit">Pause new orders</button>'
    "</form>"
    "<p>Pause writes a HALT file. It does not submit an order.</p>"
)


def render_page(registry: Registry, *, pause: bool = False) -> str:
    rows = registry.rows()
    body = "<p>No strategies have been recorded.</p>" if not rows else _table(rows)
    control = _PAUSE if pause else ""
    return _PAGE.format(pause=control, body=body)


def open_server(
    registry: Registry,
    *,
    host: str = "127.0.0.1",
    port: int = 0,
    halt_directory: Path | None = None,
) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((host, port), _handler(registry, halt_directory))


def serve(registry: Registry, *, host: str = "127.0.0.1", port: int = 43127) -> None:
    """Block and serve ``GET /``. Other methods and paths are refused."""
    server = open_server(registry, host=host, port=port)
    try:
        server.serve_forever()
    finally:
        server.server_close()


def _table(rows: tuple[RegistryRow, ...]) -> str:
    head = (
        "<table><thead><tr>"
        "<th>Strategy</th><th>State</th><th>Verdict</th>"
        "<th>Equity</th><th>Hypothesis</th><th>Digest</th>"
        "</tr></thead><tbody>"
    )
    body = "".join(_tr(row) for row in rows)
    return head + body + "</tbody></table>"


def _tr(row: RegistryRow) -> str:
    cells = (
        f"{row.strategy_id} v{row.version}",
        row.state,
        row.verdict,
        row.ending_equity or "—",
        row.hypothesis,
        row.digest or "—",
    )
    rendered = "".join(f"<td>{html.escape(cell)}</td>" for cell in cells)
    return f"<tr>{rendered}</tr>"


def _handler(
    registry: Registry,
    halt_directory: Path | None,
) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if self.path.split("?", maxsplit=1)[0] != "/":
                self.send_error(404)
                return
            payload = render_page(registry, pause=halt_directory is not None).encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def do_POST(self) -> None:
            path = self.path.split("?", maxsplit=1)[0]
            if path != "/halt" or halt_directory is None:
                self.send_error(405)
                return
            halt_sentinel(halt_directory).write_text("pause\n", encoding="utf-8")
            self.send_response(204)
            self.end_headers()

        def log_message(self, format: str, *args: object) -> None:
            del format, args

    return Handler
