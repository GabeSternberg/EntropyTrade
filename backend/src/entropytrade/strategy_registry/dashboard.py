"""Read-only HTML for the strategy registry. There is no write route."""

import html
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

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
<p>Read only. This page cannot submit an order or approve live capital.</p>
{body}
</body>
</html>
"""


def render_page(registry: Registry) -> str:
    rows = registry.rows()
    body = "<p>No strategies have been recorded.</p>" if not rows else _table(rows)
    return _PAGE.format(body=body)


def open_server(
    registry: Registry,
    *,
    host: str = "127.0.0.1",
    port: int = 0,
) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((host, port), _handler(registry))


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


def _handler(registry: Registry) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if self.path.split("?", maxsplit=1)[0] != "/":
                self.send_error(404)
                return
            payload = render_page(registry).encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def do_POST(self) -> None:
            self.send_error(405)

        def log_message(self, format: str, *args: object) -> None:
            del format, args

    return Handler
