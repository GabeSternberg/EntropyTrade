"""Import boundaries: venue SDKs and agent frameworks stay behind their packages."""

import ast
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[2] / "src" / "entropytrade"

BANNED = {
    "kalshi": "entropytrade/exchange/kalshi",
    "pydantic_ai": "entropytrade/agents",
}


def test_banned_imports_stay_in_their_package() -> None:
    violations: list[str] = []
    for path in SOURCE.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            modules: list[str] = []
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module is not None:
                modules = [node.module]
            for module in modules:
                root = module.split(".", maxsplit=1)[0]
                allowed = BANNED.get(root)
                if allowed is None:
                    continue
                relative = path.relative_to(SOURCE.parent.parent).as_posix()
                if allowed not in relative:
                    violations.append(f"{relative} imports {module}")
    assert violations == []


def test_domain_does_not_import_the_gateway_or_agents() -> None:
    domain = SOURCE / "domain"
    forbidden = ("entropytrade.exchange", "entropytrade.agents", "entropytrade.execution")
    for path in domain.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for name in forbidden:
            assert name not in text, f"{path.name} references {name}"
