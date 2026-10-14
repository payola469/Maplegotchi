"""Pure canonical capture/reconstruction, independent of Legacy MapleState (D01).

Accepts previously validated canonical context, never untrusted JSON or a live
MapleState. Capture checks the redundant derived values rather than silently
repairing a forged/replaced CanonicalLife. All original SQL text is retained.
"""

from maplegotchi.persistence.layout_keys import project_layout_keys
from maplegotchi.persistence.life_record import (
    CanonicalLife,
    CanonicalLifeRecord,
    V11LifeError,
    life_fields,
    reconstruct_life,
)
from maplegotchi.persistence.revision_snapshot import LayoutSnapshotProof


def capture_life(life: CanonicalLife) -> CanonicalLife:
    """Return a fully revalidated immutable canonical value, without time/RNG/IO.

    This boundary does not project a running Legacy MapleState. Layout context
    and Travel must already have passed their admission boundaries.
    """
    if type(life) is not CanonicalLife:
        raise V11LifeError("type")
    if type(life.record) is not CanonicalLifeRecord or type(life.layout) is not LayoutSnapshotProof:
        raise V11LifeError("fields")
    try:
        keys = project_layout_keys(life.layout.active.layout, life.record.layout_revision)
    except (AttributeError, StopIteration, TypeError, ValueError):
        raise V11LifeError("layout") from None
    restored = reconstruct_life(
        life_fields(life.record),
        identity_row=life.identity_row,
        births=life.births,
        ledger_rows=life.ledger_rows,
        goal_rows=life.goal_rows,
        decisions=life.decisions,
        layout=life.layout,
        keys=keys,
        travel=life.travel,
    )
    if restored != life:
        raise V11LifeError("fields")
    return restored
