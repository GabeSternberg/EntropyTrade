"""Registry lineage, local MLflow params, and the read-only page."""

import http.client
import threading
from pathlib import Path

import pytest

from entropytrade.agents.fixture import WHEN, demo_specs
from entropytrade.agents.pipeline import run_philadelphia_demo
from entropytrade.domain.enums import ActorKind
from entropytrade.domain.lifecycle import Actor, HumanApproval, LifecycleState, LifecycleTransition
from entropytrade.domain.strategy import StrategySpec
from entropytrade.strategy_registry.dashboard import open_server, render_page
from entropytrade.strategy_registry.experiments import log_rows
from entropytrade.strategy_registry.store import Registry, RegistryError, human_approval


def test_recording_twice_does_not_add_a_version(tmp_path: Path) -> None:
    registry = Registry(tmp_path / "registry.sqlite")
    result = run_philadelphia_demo()
    specs = demo_specs()
    registry.record_research(result, specs, now=WHEN)
    registry.record_research(result, specs, now=WHEN)
    rows = registry.rows()
    assert len(rows) == 4
    traded = next(row for row in rows if row.strategy_id == "phl-probability-055")
    quiet = next(row for row in rows if row.strategy_id == "phl-probability-090")
    rejected = next(row for row in rows if row.strategy_id == "phl-kelly")
    assert traded.state == "backtested"
    assert traded.verdict == "accepted"
    assert traded.ending_equity == "100.600000"
    assert quiet.ending_equity == "100.000000"
    assert rejected.state == "research"
    assert rejected.verdict == "rejected"
    assert "fixed_contracts" in rejected.reason
    registry.close()


def test_version_lineage_and_live_promotion(tmp_path: Path) -> None:
    registry = Registry(tmp_path / "registry.sqlite")
    specs = demo_specs()
    spec = specs[0]
    digest = registry.register(spec)
    with pytest.raises(RegistryError, match="no parent"):
        registry.register(specs[3], parent_hash=digest)
    child = spec.revalidated(version=2)
    with pytest.raises(RegistryError, match="parent"):
        registry.register(child)
    child_hash = registry.register(child, parent_hash=digest)
    assert child_hash != digest
    assert registry.state(child.strategy_id, 2) is LifecycleState.DRAFT
    _walk_to_shadow(registry, spec)
    agent = Actor(kind=ActorKind.AGENT, actor_id="research")
    approval = human_approval("gabe", when=WHEN, note="not enough")
    with pytest.raises(ValueError, match="agent"):
        _transition(registry, spec, LifecycleState.LIVE_SMALL, agent, approval)
    human = Actor(kind=ActorKind.HUMAN, actor_id="gabe")
    _transition(registry, spec, LifecycleState.LIVE_SMALL, human, approval)
    assert registry.state(spec.strategy_id, 1) is LifecycleState.LIVE_SMALL
    registry.close()


def test_empty_and_populated_pages_have_no_order_form(tmp_path: Path) -> None:
    registry = Registry(tmp_path / "registry.sqlite")
    assert "No strategies have been recorded." in render_page(registry)
    registry.record_research(run_philadelphia_demo(), demo_specs(), now=WHEN)
    page = render_page(registry)
    assert "phl-probability-055" in page
    assert "100.60" in page
    assert "cannot submit an order" in page
    assert 'type="submit"' not in page
    assert "<script" not in page
    registry.close()


def test_the_page_is_served_and_post_is_refused(tmp_path: Path) -> None:
    registry = Registry(tmp_path / "registry.sqlite")
    server = open_server(registry)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    address = server.server_address
    connection = http.client.HTTPConnection(str(address[0]), int(address[1]), timeout=5)
    connection.request("GET", "/")
    body = connection.getresponse().read().decode()
    connection.request("POST", "/", body=b"{}")
    posted = connection.getresponse()
    server.shutdown()
    server.server_close()
    registry.close()
    assert "No strategies have been recorded." in body
    assert posted.status == 405


def test_pause_writes_halt_and_post_root_stays_refused(tmp_path: Path) -> None:
    registry = Registry(tmp_path / "registry.sqlite")
    server = open_server(registry, halt_directory=tmp_path)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    address = server.server_address
    connection = http.client.HTTPConnection(str(address[0]), int(address[1]), timeout=5)
    connection.request("GET", "/")
    page = connection.getresponse().read().decode()
    connection.request("POST", "/halt")
    paused = connection.getresponse()
    paused.read()
    connection.request("POST", "/", body=b"{}")
    posted = connection.getresponse()
    server.shutdown()
    server.server_close()
    registry.close()
    assert "Pause new orders" in page
    assert "cannot submit an order" in page
    assert paused.status == 204
    assert (tmp_path / "HALT").read_text(encoding="utf-8") == "pause\n"
    assert posted.status == 405


def test_mlflow_logs_equity_as_text(tmp_path: Path) -> None:
    from mlflow.tracking import MlflowClient

    registry = Registry(tmp_path / "registry.sqlite")
    registry.record_research(run_philadelphia_demo(), demo_specs(), now=WHEN)
    tracking = tmp_path / "mlflow"
    experiment_id = log_rows(registry, tracking)
    client = MlflowClient(tracking_uri=tracking.resolve().as_uri())
    runs = client.search_runs(experiment_ids=[experiment_id])
    equities = {run.data.params["ending_equity"] for run in runs}
    assert "100.600000" in equities
    assert "none" in equities
    registry.close()


def _walk_to_shadow(registry: Registry, spec: StrategySpec) -> None:
    agent = Actor(kind=ActorKind.AGENT, actor_id="research")
    steps = (
        LifecycleState.RESEARCH,
        LifecycleState.BACKTESTED,
        LifecycleState.VALIDATED,
        LifecycleState.PAPER,
        LifecycleState.SHADOW_LIVE,
    )
    for target in steps:
        _transition(registry, spec, target, agent, None)


def _transition(
    registry: Registry,
    spec: StrategySpec,
    target: LifecycleState,
    actor: Actor,
    approval: HumanApproval | None,
) -> None:
    current = registry.state(spec.strategy_id, spec.version)
    registry.apply(
        LifecycleTransition(
            strategy_id=spec.strategy_id,
            strategy_version=spec.version,
            from_state=current,
            to_state=target,
            actor=actor,
            reason="recorded promotion step",
            occurred_at=WHEN,
            approval=approval,
        )
    )
