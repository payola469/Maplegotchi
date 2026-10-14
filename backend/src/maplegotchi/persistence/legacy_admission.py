"""STEP 225 isolated D01-A boundary; never persisted-state admission or scheduling.

Uses the existing pure projection unchanged. Refusal performs no transition,
random draw, fallback, reroute, clock advance or write. Callers must not install
this as an autonomous retry loop: scheduling/progress after refusal is unresolved.
"""

from datetime import datetime
from typing import Literal

from maplegotchi.core.activities import Activity
from maplegotchi.core.world.legacy_projection import (
    DevelopmentWorld,
    LegacyProjection,
    PointRef,
    Presentation,
    project,
    project_point,
)
from maplegotchi.core.world.movement import Travel

Category = Literal[
    "collapsed_anchor",
    "mid_edge",
    "projection",
    "continuity",
    "pending",
    "unsettled",
    "presentation",
]


class CompatibilityRefusal(ValueError):
    """Fixed category, no private identifiers or payload in exception text."""

    def __init__(self, category: Category) -> None:
        super().__init__(category)


def project_eligible(
    context: DevelopmentWorld,
    destination: PointRef,
    presentation: Presentation,
    now: datetime,
    *,
    travel: Travel | None = None,
    origin: PointRef | None = None,
    from_activity: Activity | None = None,
) -> LegacyProjection:
    """Check one explicit presentation/proposal; never use this to refuse Load.

    Entry/collapsed movements receive stable categories. Every other invariant
    is delegated to the accepted projection; no second Legacy geometry/route.
    Origin semantics must be supplied, never guessed from an ambiguous tile.
    """
    try:
        if travel is not None:
            if travel.entry is not None:
                raise CompatibilityRefusal("mid_edge")
            if origin is not None and from_activity is not None:
                start = project_point(context, origin, from_activity)
                end = project_point(context, destination, presentation.activity)
                if travel.duration_us > 0 and start.id == end.id:
                    raise CompatibilityRefusal("collapsed_anchor")
        return project(
            context,
            destination,
            presentation,
            now,
            travel=travel,
            origin=origin,
            from_activity=from_activity,
        )
    except CompatibilityRefusal:
        raise
    except (ValueError, TypeError, AttributeError):
        raise CompatibilityRefusal("projection") from None
