"""Read-only SQLite URIs must not depend on the SQLite build's SQLITE_USE_URI default.

Without ``uri=True`` the standard library passes ``file:...?mode=ro`` as a literal
filename. Builds compiled with SQLITE_USE_URI=1 hide that defect; other interpreters
(for example uv-managed CPython) refuse recovery with "unable to open database file".
"""

import ast
import sqlite3
from pathlib import Path

import pytest

SOURCE = Path(__file__).resolve().parents[2] / "src" / "entropytrade"


def _uri_connect_calls() -> list[tuple[str, int, bool]]:
    found = []
    for path in sorted(SOURCE.rglob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(), str(path))):
            if not (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "connect"
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "sqlite3"
                and node.args
            ):
                continue
            literals = [
                n.value
                for n in ast.walk(node.args[0])
                if isinstance(n, ast.Constant) and isinstance(n.value, str)
            ]
            uses_uri = "as_uri" in ast.unparse(node.args[0]) or any(
                "mode=" in s or s.startswith("file:") for s in literals
            )
            if uses_uri:
                explicit = any(
                    k.arg == "uri" and isinstance(k.value, ast.Constant) and k.value.value is True
                    for k in node.keywords
                )
                found.append((str(path.relative_to(SOURCE)), node.lineno, explicit))
    return found


def test_every_sqlite_uri_connection_enables_uri_parsing() -> None:
    calls = _uri_connect_calls()
    assert len(calls) >= 8  # recovery, recovery proof, evidence and recorder readers
    assert [c for c in calls if not c[2]] == []


def test_read_only_uri_opens_wal_database_without_build_uri_default(tmp_path: Path) -> None:
    path = tmp_path / "jobs.sqlite"
    writer = sqlite3.connect(path)
    writer.execute("PRAGMA journal_mode=WAL")
    writer.execute("CREATE TABLE t(x)")
    writer.execute("INSERT INTO t VALUES (1)")
    writer.commit()
    reader = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)
    try:
        assert reader.execute("SELECT x FROM t").fetchall() == [(1,)]
        with pytest.raises(sqlite3.OperationalError):
            reader.execute("INSERT INTO t VALUES (2)")
    finally:
        reader.close()
        writer.close()
