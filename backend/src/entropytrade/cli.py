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
