"""Append-only weather vintages on the R1 recorder's raw receipt journal and durability."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from entropytrade.data.schema import Location, Observation
from entropytrade.domain.ids import content_hash
from entropytrade.domain.time import ensure_utc, utc_now
from entropytrade.storage.recorder import Recorder
from entropytrade.weather.forecast import ForecastVintage, parse_forecast


class ForecastArchive(Recorder):
    def __init__(self, path: Path, *, read_only: bool = False) -> None:
        super().__init__(path, read_only=read_only)
        if not read_only:
            self._db.executescript("""
                CREATE TABLE IF NOT EXISTS forecast_vintages (
                vintage_id TEXT PRIMARY KEY, first_seen TEXT NOT NULL, first_receipt TEXT NOT NULL,
                ingested_at TEXT NOT NULL, data_kind TEXT NOT NULL, payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS forecast_sightings (
                receipt_id TEXT PRIMARY KEY, vintage_id TEXT REFERENCES forecast_vintages);
                CREATE TABLE IF NOT EXISTS forecast_failures (
                receipt_id TEXT PRIMARY KEY, reason TEXT NOT NULL);
            """)
            self._db.commit()

    def capture(
        self,
        *,
        body: bytes,
        url: str,
        status: int,
        received_at: datetime,
        provider: str,
        location: Location,
        data_kind: str = "real",
    ) -> str | None:
        if data_kind not in {"real", "synthetic", "fixture"}:
            raise ValueError("invalid weather data kind")
        at = ensure_utc(received_at)
        receipt = self.record_http(path=url, status=status, body=body, received_at=at)
        try:
            if status != 200:
                raise ValueError(f"http_{status}")
            vintage = parse_forecast(body, provider=provider, location=location)
            if not vintage.points or (
                vintage.published_at is not None and vintage.published_at > at
            ):
                raise ValueError("empty forecast or provider timestamp after receipt")
        except (ValueError, KeyError, TypeError, ArithmeticError) as exc:
            with self._db:
                self._db.execute(
                    "INSERT INTO forecast_failures VALUES (?, ?)", (receipt, type(exc).__name__)
                )
            return None
        identity = content_hash({"vintage": vintage.identity(), "data_kind": data_kind})
        with self._db:
            # A late import cannot rewrite a first-seen time backwards.
            self._db.execute(
                "INSERT OR IGNORE INTO forecast_vintages VALUES (?, ?, ?, ?, ?, ?)",
                (
                    identity,
                    at.isoformat(),
                    receipt,
                    utc_now().isoformat(),
                    data_kind,
                    vintage.model_dump_json(),
                ),
            )
            self._db.execute("INSERT INTO forecast_sightings VALUES (?, ?)", (receipt, identity))
        return identity

    def observations(self, *, data_kind: str = "real") -> list[Observation]:
        result: list[Observation] = []
        for row in self._db.execute(
            "SELECT * FROM forecast_vintages WHERE data_kind=? ORDER BY first_seen, vintage_id",
            (data_kind,),
        ):
            vintage = ForecastVintage.model_validate_json(row["payload"])
            available = datetime.fromisoformat(row["first_seen"])
            result.extend(
                Observation(
                    source_id=vintage.provider,
                    model=vintage.model,
                    entity_id=vintage.location_id,
                    variable="temperature_f",
                    value=point.value,
                    unit="degF",
                    valid_on=point.valid_at.date(),
                    valid_at=point.valid_at,
                    issued_at=vintage.issued_at,
                    published_at=vintage.published_at,
                    available_at=available,
                    received_at=available,
                    ingested_at=datetime.fromisoformat(row["ingested_at"]),
                    revision_id=row["vintage_id"],
                    timing_basis="received",
                    evidence="first retained collector receipt; initialization not inferred",
                    raw_ref=f"weather-receipt:{row['first_receipt']}",
                    raw_hash=self._body_hash(row["first_receipt"]),
                )
                for point in vintage.points
            )
        return result

    def _body_hash(self, receipt: str) -> str:
        row = self._db.execute(
            "SELECT body_hash FROM http_receipts WHERE receipt_id=?", (receipt,)
        ).fetchone()
        if row is None:
            raise ValueError("weather vintage has no raw receipt")
        return str(row[0])

    def snapshot(self, *, data_kind: str = "real") -> tuple[list[Observation], dict[str, Any]]:
        self._db.execute("BEGIN")
        try:
            observations = self.observations(data_kind=data_kind)
            coverage = []
            for provider, location in sorted({(o.source_id, o.entity_id) for o in observations}):
                selected = [
                    o for o in observations if (o.source_id, o.entity_id) == (provider, location)
                ]
                receipts = self._db.execute(
                    "SELECT MAX(h.received_at) FROM forecast_sightings s "
                    "JOIN http_receipts h USING(receipt_id) "
                    "JOIN forecast_vintages v USING(vintage_id) "
                    "WHERE json_extract(v.payload, '$.provider')=? "
                    "AND json_extract(v.payload, '$.location_id')=? AND v.data_kind=?",
                    (provider, location, data_kind),
                ).fetchone()[0]
                coverage.append(
                    {
                        "provider": provider,
                        "location": location,
                        "hourly_points": len(selected),
                        "first_seen": min(
                            o.available_at.isoformat() for o in selected if o.available_at
                        ),
                        "last_successful_receipt": receipts,
                        "valid_from": min(o.valid_at.isoformat() for o in selected if o.valid_at),
                        "valid_through": max(
                            o.valid_at.isoformat() for o in selected if o.valid_at
                        ),
                    }
                )
            summary = {
                "coverage": coverage,
                "vintages": self._db.execute(
                    "SELECT COUNT(*) FROM forecast_vintages WHERE data_kind=?", (data_kind,)
                ).fetchone()[0],
                "receipts": self.count("http_receipts"),
                "data_kind": data_kind,
                "failures": self._db.execute("SELECT COUNT(*) FROM forecast_failures").fetchone()[
                    0
                ],
                "snapshot_hash": content_hash([o.model_dump(mode="json") for o in observations]),
            }
        finally:
            self._db.rollback()
        return observations, summary

    def receipt_ledger(self) -> list[dict[str, Any]]:
        """Every HTTP receipt with its exact body and what it produced (vintage or failure).

        This is all the archive holds beyond the parsed vintages, which are reproducible
        from the bodies; it lets a capture retain provenance without keeping the database.
        """
        rows = self._db.execute(
            "SELECT h.receipt_id, h.path, h.status, h.body_hash, h.received_at, h.ingested_at, "
            "b.body, s.vintage_id, f.reason FROM http_receipts h "
            "JOIN bodies b USING(body_hash) "
            "LEFT JOIN forecast_sightings s USING(receipt_id) "
            "LEFT JOIN forecast_failures f USING(receipt_id) "
            "ORDER BY h.received_at, h.receipt_id"
        ).fetchall()
        return [
            {
                "receipt_id": row[0],
                "url": row[1],
                "status": row[2],
                "body_hash": row[3],
                "received_at": row[4],
                "ingested_at": row[5],
                "body": row[6],
                "vintage_id": row[7],
                "failure": row[8],
            }
            for row in rows
        ]

    def export(self, destination: Path) -> None:
        observations, summary = self.snapshot()
        destination.mkdir(parents=True, exist_ok=False)
        from entropytrade.data.sources import file_hash

        exported: list[Observation] = []
        raw_dir = destination / "raw"
        raw_dir.mkdir()
        for observation in observations:
            receipt = observation.raw_ref.split(":", 1)[1]
            path = raw_dir / (receipt + ".json")
            if not path.exists():
                body = self._db.execute(
                    "SELECT b.body FROM http_receipts h JOIN bodies b USING(body_hash) "
                    "WHERE receipt_id=?",
                    (receipt,),
                ).fetchone()
                if body is None:
                    raise ValueError("export raw receipt is missing")
                path.write_text(body[0], encoding="utf-8")
            exported.append(
                observation.revalidated(
                    raw_ref=path.relative_to(destination).as_posix(), raw_hash=file_hash(path)
                )
            )
        (destination / "observations.jsonl").write_text(
            "".join(o.model_dump_json() + "\n" for o in exported), encoding="utf-8"
        )
        (destination / "manifest.json").write_text(json.dumps(summary, sort_keys=True, indent=2))
