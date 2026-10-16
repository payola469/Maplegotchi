"""Tracked child only: fixed CLI operation, private parent stdin capability.

No arbitrary path CLI. Parent creates an empty fresh root and passes its inode
identity over a pipe. Parent-owned audit/worker tracking is the accidental-path
boundary, not a sandbox against malicious Python constructing its own harness.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import NoReturn

from maplegotchi.storage.canonical_v11 import load
from tests.schema_v11 import owned_store as store
from tests.schema_v11.canonical_binding import OwnedBinding, image_of
from tests.schema_v11.conversion_fixture import _fresh, admit_v10, opened
from tests.schema_v11.conversion_mapping import mapped
from tests.schema_v11.converter import convert
from tests.schema_v11.restart_worker import canonical, digest

AT = datetime(2026, 10, 15, tzinfo=UTC)


def main() -> int:
    if len(sys.argv) != 2 or sys.argv[1] not in {
        "writer",
        "reader",
        "before_commit",
        "during_commit",
        "after_commit",
    }:
        return 2
    raw = sys.stdin.buffer.read(4097)
    if len(raw) > 4096:
        return 2
    packet = json.loads(raw)
    if set(packet) != {"root", "identity", "parent", "point", "travel", "variant", "nonce"}:
        return 2
    if packet["parent"] != os.getppid() or len(packet["nonce"]) != 64:
        return 2
    secret = os.environ.pop("MAPLEGOTCHI_STEP230_HANDOFF", "")
    if len(secret) != 64:
        return 3
    claimed = packet.pop("nonce")
    expected_nonce = hmac.new(
        bytes.fromhex(secret), json.dumps(packet, sort_keys=True).encode(), hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(claimed, expected_nonce):
        raise ValueError("invalid current-execution handoff")
    packet["nonce"] = claimed
    scope = store.OwnedRoot(Path(packet["root"]), tuple(packet["identity"]))
    scope._root()
    operation = sys.argv[1]
    if operation != "reader":
        handle = _fresh(scope, packet["point"], packet["travel"], packet["variant"], False)

        def interrupt(phase: str) -> None:
            if phase == operation:
                os._exit(73)

        def commit_loss() -> NoReturn:
            os._exit(73)

        convert(
            handle,
            AT,
            inject=interrupt,
            commit_progress=commit_loss if operation == "during_commit" else None,
        )
    with opened(scope, "source.db") as source:
        before = admit_v10(source)
        from maplegotchi.storage.repositories import LifeRepository

        expected, catalogs, contexts = mapped(before, LifeRepository(source).load().state, AT)
    for name in ("owner.db", "automatic.db"):
        with opened(scope, name) as copy:
            if store.exact(admit_v10(copy)) != store.exact(before):
                return 3
    with opened(scope, "target.db") as target:
        version = target.execute("PRAGMA user_version").fetchone()[0]
        if version == 10:
            if store.exact(admit_v10(target)) != store.exact(before):
                return 3
        elif version == 11:
            port = OwnedBinding(scope, "target.db", catalogs, contexts)
            recovered = image_of(load(port, schema_version=11))
            if store.exact(recovered) != store.exact(expected):
                return 3
        else:
            return 3
    print(
        canonical(
            dict(
                pid=os.getpid(),
                version=version,
                digest=digest(expected if version == 11 else before),
                nonce=packet["nonce"],
            )
        )
    )
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        print(canonical(dict(error="refused")))
        sys.exit(3)
