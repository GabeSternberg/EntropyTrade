"""Local data commands. None has an order interface or a trading-credential fallback."""

import argparse
import asyncio
import fcntl
import json
import os
import signal
from pathlib import Path

import pyarrow.parquet as pq  # type: ignore[import-untyped]

from entropytrade import __version__
from entropytrade.collector.service import CollectorConfig, check_space, collect, ingest_message
from entropytrade.data.acquire import acquire
from entropytrade.data.dataset import build_dataset
from entropytrade.data.schema import DatasetConfig
from entropytrade.domain.enums import KalshiEnvironment
from entropytrade.domain.modes import DEFAULT_TRADING_MODE
from entropytrade.domain.time import utc_now
from entropytrade.exchange.feed import CollectorFeed
from entropytrade.exchange.kalshi.gateway import KalshiGateway
from entropytrade.exchange.kalshi.socket import stream_factory
from entropytrade.exchange.kalshi.transport import RawCapture
from entropytrade.storage.recorder import Recorder


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="EntropyTrade read-only data tools")
    commands = parser.add_subparsers(dest="command")
    collector = commands.add_parser("collect", help="continuous read-only Kalshi data collector")
    collector.add_argument("--config", type=Path, required=True)
    collector.add_argument("--db", type=Path, required=True)
    collector.add_argument("--environment", choices=["demo", "production"], default="demo")
    collector.add_argument("--seconds", type=int)
    collector.add_argument("--replay-wire", type=Path, help="offline wire JSONL; marked as replay")
    health = commands.add_parser("health")
    health.add_argument("--db", type=Path, required=True)
    bitcoin = commands.add_parser(
        "bitcoin-history", help="retained Bitcoin receipts to protected binary model experiments"
    )
    bitcoin.add_argument("--capture", type=Path, action="append", default=[])
    bitcoin.add_argument("--previous", type=Path, action="append", default=[])
    bitcoin.add_argument(
        "--no-fetch", action="store_true", help="verify retained receipts without new network reads"
    )
    bitcoin.add_argument("--output", type=Path, required=True)
    bitcoin.add_argument("--prompt", default="Test scaled_moneyness > 0")
    dataset = commands.add_parser("dataset", help="build a versioned daily-high Parquet dataset")
    dataset.add_argument("--config", type=Path, required=True)
    dataset.add_argument("--source", type=Path, action="append", required=True)
    dataset.add_argument("--output", type=Path, required=True)
    dataset.add_argument(
        "--fetch", type=Path, help="acquire public SDK evidence into a NEW directory"
    )
    dataset.add_argument("--recorder", type=Path)
    inspect = commands.add_parser("inspect")
    inspect.add_argument("dataset", type=Path)
    inspect.add_argument("--day", required=True)
    inspect.add_argument("--limit", type=int, default=10)
    weather = commands.add_parser("weather-collect", help="append-only forward weather archive")
    weather.add_argument("--config", type=Path, required=True)
    weather.add_argument("--db", type=Path, required=True)
    weather.add_argument("--once", action="store_true")
    weather.add_argument("--seconds", type=int)
    export = commands.add_parser("weather-export", help="export retained receipts and observations")
    export.add_argument("--db", type=Path, required=True)
    export.add_argument("--output", type=Path, required=True)
    features = commands.add_parser(
        "features", help="versioned point-in-time weather feature matrix"
    )
    features.add_argument("--dataset", type=Path, required=True)
    features.add_argument("--archive", type=Path, action="append", default=[])
    features.add_argument("--output", type=Path, required=True)
    model = commands.add_parser("model", help="grouped temporal probability modeling")
    model.add_argument("--features", type=Path, required=True)
    model.add_argument("--output", type=Path, required=True)
    model.add_argument("--registry", type=Path, required=True)
    model.add_argument("--tracking", type=Path, required=True)
    model.add_argument("--config", type=Path)
    demo = commands.add_parser("model-demo", help="explicitly synthetic complete pipeline proof")
    demo.add_argument("--output", type=Path, required=True)
    demo.add_argument("--days", type=int, default=300)
    research = commands.add_parser(
        "research", help="bounded read-only agent research; no backtest execution"
    )
    research.add_argument("--prompt", required=True)
    research.add_argument("--config", type=Path, required=True)
    research.add_argument("--provider", choices=["openai", "anthropic"])
    research.add_argument("--model")
    research.add_argument("--enable-provider", action="store_true")
    research.add_argument("--offline", action="store_true")
    research.add_argument("--registry", type=Path, required=True)
    research.add_argument("--output", type=Path, required=True)
    integrated = commands.add_parser(
        "research-and-test", help="prompt to deterministic protected strategy experiments"
    )
    integrated.add_argument("--prompt", required=True)
    integrated.add_argument("--config", type=Path)
    integrated.add_argument("--experiment-config", type=Path)
    integrated.add_argument("--output", type=Path, required=True)
    integrated.add_argument("--registry", type=Path, required=True)
    integrated.add_argument("--tracking", type=Path, required=True)
    integrated.add_argument("--provider", choices=["openai", "anthropic"])
    integrated.add_argument("--model")
    integrated.add_argument("--enable-provider", action="store_true")
    integrated.add_argument("--offline", action="store_true")
    integrated.add_argument("--synthetic", action="store_true")
    integrated.add_argument("--days", type=int, default=240)
    integrated.add_argument("--research-run", type=Path)
    integrated.add_argument("--json", action="store_true", help="include full structured results")
    return parser


async def _collect(args: argparse.Namespace, store: Recorder) -> None:
    config = CollectorConfig.model_validate_json(args.config.read_text(encoding="utf-8"))
    if args.replay_wire is not None:
        feed = CollectorFeed()
        session = store.start_session(utc_now(), mode="replay")
        feed.note_reconnect(utc_now())
        try:
            with args.replay_wire.open(encoding="utf-8") as wire:
                for ordinal, line in enumerate(wire, 1):
                    if ingest_message(store, feed, session=session, ordinal=ordinal, raw=line):
                        store.end_session(session, utc_now(), "replay_integrity_restart")
                        feed.note_disconnect(utc_now())
                        session = store.start_session(utc_now(), mode="replay")
                        feed.note_reconnect(utc_now())
        finally:
            feed.note_disconnect(utc_now())
            store.save_health(feed.health(utc_now()).model_dump_json(), utc_now())
            store.end_session(session, utc_now(), "replay_finished")
        print(json.dumps(store.health_summary(), sort_keys=True))
        return
    key_id = os.environ.get("ENTROPYTRADE_READ_KEY_ID")
    key_file = os.environ.get("ENTROPYTRADE_READ_KEY_PATH")
    if not key_id or not key_file:
        raise ValueError(
            "set ENTROPYTRADE_READ_KEY_ID and ENTROPYTRADE_READ_KEY_PATH to a read-only key"
        )
    key_path = Path(key_file).expanduser()
    if key_path.stat().st_mode & 0o077:
        raise ValueError("read key file must have private permissions (chmod 600)")
    environment = KalshiEnvironment(args.environment)

    def capture(raw: RawCapture) -> None:
        check_space(store.path, config.max_bytes)
        store.record_http(
            path=raw.path, status=raw.status, body=raw.body, received_at=raw.received_at
        )

    gateway = KalshiGateway(
        environment=environment,
        key_id=key_id,
        private_key_pem=key_path.read_text(encoding="utf-8"),
        capture=capture,
        wait_for_budget=True,
    )
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for name in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(name, stop.set)
    timer = None if args.seconds is None else loop.call_later(args.seconds, stop.set)
    try:
        await gateway.require_read_scope(key_id)
        await gateway.get_api_limits()
        await gateway.get_endpoint_costs()
        await collect(
            gateway=gateway,
            store=store,
            config=config,
            stream_factory=stream_factory(
                key_id=key_id, key_path=key_path, environment=environment
            ),
            stop=stop,
            emit=print,
        )
    finally:
        if timer is not None:
            timer.cancel()
        for name in (signal.SIGINT, signal.SIGTERM):
            loop.remove_signal_handler(name)
        await gateway.aclose()


def main() -> None:
    args = _parser().parse_args()
    if args.command is None:
        print(f"entropytrade {__version__} (default trading mode: {DEFAULT_TRADING_MODE.value})")
    elif args.command == "bitcoin-history":
        from datetime import date

        from entropytrade.agents.evidence import EvidenceConfig
        from entropytrade.experiments.data import AdapterRegistry
        from entropytrade.experiments.workflow import research_and_test
        from entropytrade.families.bitcoin_history import build_history, history_data
        from entropytrade.families.bitcoin_models import MODELS, BitcoinPredictions

        args.output.mkdir(parents=True, exist_ok=False)
        data = asyncio.run(
            build_history(
                args.output / "history",
                args.capture,
                previous=args.previous,
                fetch=not args.no_fetch,
            )
        )
        boundary = min(
            (s.target_date for s in data.samples if s.event_id in data.protected_events),
            default=date.max,
        )
        bitcoin_config = EvidenceConfig(
            root=args.output.resolve(),
            features="history",
            holdout_start=boundary,
            model_families=MODELS,
        )
        config_path = args.output / "evidence.json"
        config_path.write_text(bitcoin_config.model_dump_json(indent=2))
        adapters = AdapterRegistry()
        adapters.register(
            "bitcoin", history_data, BitcoinPredictions(data, args.output / "workflow/models")
        )
        result = research_and_test(
            prompt=args.prompt,
            evidence_config=config_path,
            output=args.output / "workflow",
            registry=args.output / "registry.sqlite",
            tracking=args.output / "mlflow",
            adapters=adapters,
            market_family="bitcoin",
            offline=True,
            local_templates=True,
        )
        print(
            json.dumps({"history": data.provenance, "experiment": result}, sort_keys=True, indent=2)
        )
    elif args.command == "research-and-test":
        from entropytrade.agents.provider import ResearchProviderConfig
        from entropytrade.experiments.engine import ExperimentConfig
        from entropytrade.experiments.workflow import research_and_test

        selected = (
            None
            if args.offline or args.research_run
            else ResearchProviderConfig(provider=args.provider, model_name=args.model)
        )
        result = research_and_test(
            prompt=args.prompt,
            evidence_config=args.config,
            output=args.output,
            registry=args.registry,
            tracking=args.tracking,
            provider=selected,
            offline=args.offline,
            enable_provider=args.enable_provider,
            synthetic=args.synthetic,
            days=args.days,
            research_run=args.research_run,
            experiment_config=None
            if args.experiment_config is None
            else ExperimentConfig.model_validate_json(args.experiment_config.read_text()),
        )
        if result.get("report_path"):
            print(Path(result["report_path"]).read_text())
        summary = (
            result
            if args.json
            else {
                key: result[key]
                for key in ("experiment_id", "research_run", "report_path", "research_artifact")
                if key in result
            }
        )
        print(json.dumps(summary, sort_keys=True, indent=2))
        if result.get("status") == "RESEARCH_FAILED":
            raise SystemExit(
                "Research failed; configure the research key and explicit provider opt-in."
            )
    elif args.command == "research":
        from entropytrade.agents.evidence import EvidenceConfig, ResearchEvidence, previous_research
        from entropytrade.agents.pipeline import run_research
        from entropytrade.agents.provider import ResearchProviderConfig

        if not args.offline and (not args.provider or not args.model):
            raise ValueError(
                "select --provider and --model, set ENTROPYTRADE_RESEARCH_API_KEY, "
                "and pass --enable-provider"
            )
        evidence = ResearchEvidence(
            EvidenceConfig.model_validate_json(args.config.read_text()),
            history=previous_research(args.registry),
        )
        result = asyncio.run(
            run_research(
                prompt=args.prompt,
                evidence=evidence,
                provider=None
                if args.offline
                else ResearchProviderConfig(provider=args.provider, model_name=args.model),
                registry_path=args.registry,
                output=args.output,
                offline=args.offline,
                enable_provider=args.enable_provider,
            )
        )
        print(result["report"])
        print(
            json.dumps(
                {
                    "run_id": result["run_id"],
                    "status": result["status"],
                    "artifact_path": str(args.output / result["run_id"]),
                }
            )
        )
        if result["status"] == "failed":
            raise SystemExit(
                "Research failed; inspect the run. For live use set "
                "ENTROPYTRADE_RESEARCH_API_KEY and opt in explicitly."
            )
    elif args.command == "collect":
        args.db.parent.mkdir(parents=True, exist_ok=True)
        with Path(str(args.db) + ".lock").open("a", encoding="utf-8") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            store = Recorder(args.db)
            try:
                store.bind_environment("replay" if args.replay_wire else args.environment)
                asyncio.run(_collect(args, store))
            finally:
                store.close()
    elif args.command == "health":
        # Reporting must not migrate or create a missing database.
        if not args.db.is_file():
            raise ValueError("recording does not exist")
        store = Recorder(args.db, read_only=True)
        try:
            print(json.dumps(store.health_summary(), sort_keys=True))
        finally:
            store.close()
    elif args.command == "dataset":
        config = DatasetConfig.model_validate_json(args.config.read_text(encoding="utf-8"))
        sources = list(args.source)
        if args.fetch is not None:
            asyncio.run(acquire(args.fetch, config))
            sources.append(args.fetch)
        print(
            json.dumps(
                build_dataset(
                    config=config, sources=sources, output=args.output, recorder=args.recorder
                ),
                sort_keys=True,
                indent=2,
            )
        )
    elif args.command == "weather-collect":
        from entropytrade.storage.forecast_archive import ForecastArchive
        from entropytrade.weather.collection import WeatherConfig, poll_weather

        weather_config = WeatherConfig.model_validate_json(args.config.read_text())
        args.db.parent.mkdir(parents=True, exist_ok=True)
        with Path(str(args.db) + ".lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            archive = ForecastArchive(args.db)

            async def run_weather() -> None:
                stop = asyncio.Event()
                loop = asyncio.get_running_loop()
                for sig in (signal.SIGINT, signal.SIGTERM):
                    loop.add_signal_handler(sig, stop.set)
                timer = None if args.seconds is None else loop.call_later(args.seconds, stop.set)
                try:
                    await poll_weather(
                        config=weather_config,
                        archive=archive,
                        stop=stop,
                        once=args.once,
                        emit=print,
                    )
                finally:
                    if timer is not None:
                        timer.cancel()
                    for sig in (signal.SIGINT, signal.SIGTERM):
                        loop.remove_signal_handler(sig)

            try:
                asyncio.run(run_weather())
                print(json.dumps(archive.snapshot()[1], sort_keys=True))
            finally:
                archive.close()
    elif args.command == "weather-export":
        from entropytrade.storage.forecast_archive import ForecastArchive

        archive = ForecastArchive(args.db, read_only=True)
        try:
            archive.export(args.output)
        finally:
            archive.close()
    elif args.command == "features":
        from entropytrade.features.pipeline import build_features

        print(
            json.dumps(
                build_features(dataset=args.dataset, archives=args.archive, output=args.output),
                sort_keys=True,
                indent=2,
            )
        )
    elif args.command == "model":
        from entropytrade.ml.experiment import ModelingConfig, run_modeling

        model_config = (
            ModelingConfig()
            if args.config is None
            else ModelingConfig.model_validate_json(args.config.read_text())
        )
        args.registry.parent.mkdir(parents=True, exist_ok=True)
        print(
            json.dumps(
                run_modeling(
                    features=args.features,
                    output=args.output,
                    registry_path=args.registry,
                    tracking=args.tracking,
                    config=model_config,
                ),
                sort_keys=True,
                indent=2,
            )
        )
    elif args.command == "model-demo":
        from entropytrade.features.pipeline import build_features
        from entropytrade.ml.experiment import ModelingConfig, run_modeling
        from entropytrade.ml.synthetic import synthetic_dataset

        dataset = synthetic_dataset(args.output / "synthetic-dataset", days=args.days)
        features = build_features(
            dataset=dataset, archives=[], output=args.output / "features", data_kind="synthetic"
        )
        feature_dir = args.output / "features" / features["feature_version"].removeprefix("sha256:")
        print(
            json.dumps(
                run_modeling(
                    features=feature_dir,
                    output=args.output / "models",
                    registry_path=args.output / "registry.sqlite",
                    tracking=args.output / "mlflow",
                    config=ModelingConfig(evaluate_holdout=True),
                    data_kind="synthetic",
                ),
                sort_keys=True,
                indent=2,
            )
        )
    elif args.command == "inspect":
        table = pq.read_table(
            args.dataset / "rows.parquet", filters=[("target_date", "=", args.day)]
        )
        columns = [
            "market_ticker",
            "decision_time",
            "contract_existed_at_decision",
            "rules_known_at_decision",
            "features_json",
            "execution_fidelity",
            "outcome",
        ]
        print(json.dumps(table.select(columns).slice(0, args.limit).to_pylist(), indent=2))
