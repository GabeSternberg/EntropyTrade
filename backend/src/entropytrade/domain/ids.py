"""Identifiers and deterministic content hashes.

Client-generated UUIDs make writes idempotent (an intent or order can be retried without being
duplicated). Content hashes give immutable identities to strategy specs, rule texts, configs and
dataset manifests: equal content always hashes equal, any change produces a new hash.
"""

import hashlib
import json
from collections.abc import Mapping
from datetime import date, datetime, timedelta
from decimal import Decimal
from enum import Enum
from pathlib import PurePath
from typing import Annotated
from uuid import UUID, uuid4

from pydantic import AfterValidator, BaseModel

from entropytrade.domain.numeric import canonical_decimal_str
from entropytrade.domain.time import ensure_utc

HASH_PREFIX = "sha256:"


def new_id() -> UUID:
    return uuid4()


def _check_content_hash(value: str) -> str:
    digest = value.removeprefix(HASH_PREFIX)
    if not value.startswith(HASH_PREFIX) or len(digest) != 64:
        raise ValueError("content hash must look like 'sha256:<64 hex chars>'")
    int(digest, 16)
    return value


ContentHash = Annotated[str, AfterValidator(_check_content_hash)]


def _canonical(value: object) -> object:
    if value is None or isinstance(value, bool | int | str):
        return value
    if isinstance(value, float):
        raise TypeError("floats are not allowed in hashed content; use Decimal")
    if isinstance(value, Decimal):
        return canonical_decimal_str(value)
    if isinstance(value, datetime):
        return ensure_utc(value).isoformat()
    if isinstance(value, timedelta):
        seconds = (
            Decimal(value.days) * 86_400
            + Decimal(value.seconds)
            + Decimal(value.microseconds) / Decimal(1_000_000)
        )
        return canonical_decimal_str(seconds)
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Enum):
        return _canonical(value.value)
    if isinstance(value, UUID | PurePath):
        return str(value)
    if isinstance(value, BaseModel):
        return _canonical(value.model_dump(mode="python"))
    if isinstance(value, Mapping):
        out: dict[str, object] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise TypeError(f"mapping keys must be str for hashing, got {type(key).__name__}")
            out[key] = _canonical(item)
        return out
    if isinstance(value, frozenset | set):
        return sorted((_canonical(item) for item in value), key=_sort_key)
    if isinstance(value, list | tuple):
        return [_canonical(item) for item in value]
    raise TypeError(f"cannot canonicalise {type(value).__name__}")


def _sort_key(item: object) -> str:
    return json.dumps(item, sort_keys=True, separators=(",", ":"))


def canonical_json(value: object) -> str:
    """Deterministic JSON: sorted keys, no whitespace, scale-independent decimals, UTC times."""
    return json.dumps(_canonical(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def content_hash(value: object) -> str:
    """``sha256:<hex>`` of :func:`canonical_json`."""
    digest = hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()
    return f"{HASH_PREFIX}{digest}"
