"""Pure aggregate saved-layout validation; resource loading stays outside core."""

from __future__ import annotations

from dataclasses import dataclass

from maplegotchi.core.activities import Activity
from maplegotchi.core.room import InteractionPoint
from maplegotchi.core.world.catalog import (
    Catalog,
    ObjectInstance,
    ObjectType,
    SlotStatus,
    build_catalog_layout,
    identifier,
    immutable_tuple,
    unique,
)
from maplegotchi.core.world.coordinates import GRID_HEIGHT, GRID_WIDTH, Tile, require_integer
from maplegotchi.core.world.geometry import derive_structure
from maplegotchi.core.world.layout import WorldLayout
from maplegotchi.core.world.legacy_projection import DevelopmentWorld, PointRef, project_point
from maplegotchi.core.world.lighting import LightingZone, derive_lighting
from maplegotchi.core.world.model import Door, Region
from maplegotchi.core.world.resolution import (
    ResolutionSnapshot,
    requirement_for,
    validate_activity_coverage,
)
from maplegotchi.core.world.topology import derive_topology
from maplegotchi.core.world.validation import validate_regions
from maplegotchi.core.world.walkability import derive_walkability, validate_safe_layout


@dataclass(frozen=True, slots=True)
class ArtGeometry:
    """Caller extracts these records from the accepted, separately validated art manifest."""

    art_id: str
    geometry_version: int
    orientations: tuple[str, ...]

    def __post_init__(self) -> None:
        identifier(self.art_id)
        require_integer(self.geometry_version, "geometry version")
        immutable_tuple(self.orientations, str)
        unique(self.orientations)
        if self.geometry_version <= 0 or not self.orientations:
            raise ValueError("invalid art geometry record")


@dataclass(frozen=True, slots=True)
class LayoutCandidate:
    """Immutable domain inputs, not an untrusted JSON parser or a production loader."""

    regions: tuple[Region, ...]
    doors: tuple[Door, ...]
    zones: tuple[LightingZone, ...]
    types: tuple[ObjectType, ...]
    instances: tuple[ObjectInstance, ...]
    art: tuple[ArtGeometry, ...]
    legacy_targets: tuple[InteractionPoint, ...]
    maple: Tile
    grid_width: int = GRID_WIDTH
    grid_height: int = GRID_HEIGHT

    def __post_init__(self) -> None:
        for values, kind in (
            (self.regions, Region),
            (self.doors, Door),
            (self.zones, LightingZone),
            (self.types, ObjectType),
            (self.instances, ObjectInstance),
            (self.art, ArtGeometry),
            (self.legacy_targets, InteractionPoint),
        ):
            immutable_tuple(values, kind)
        if not isinstance(self.maple, Tile):
            raise ValueError("Maple position must be a Tile")


@dataclass(frozen=True, slots=True)
class ValidationError:
    code: str
    location: tuple[str, ...]
    message: str


@dataclass(frozen=True, slots=True)
class ValidationResult:
    errors: tuple[ValidationError, ...]

    @property
    def valid(self) -> bool:
        return not self.errors


_RULE_MESSAGES = (
    "Use a 44 x 26 grid with contained, non-overlapping regions.",
    "Bands, side walls and south cutaway must follow L8.",
    "Doors must join adjacent north/south floors through one band.",
    "Open doors must connect every open room.",
    "Closed floors and passages must remain inaccessible.",
    "Floor footprints must stay in their host room without blocking overlap.",
    "Wall mounts require plain bands; windows require exterior north bands.",
    "Approaches must be reachable with only declared same-instance reuse.",
    "Every required activity needs a reachable usable provider.",
    "Keep K1-K3 clear and preserve dynamic K4 connectivity.",
    "Hook slots cannot permit Maple placement; slots cannot block walking.",
    "Lighting zones must partition all cells exactly once.",
    "Maple and the central idle fallback must be in the safe open component.",
    "Every projected legacy target must exist and permit its activity.",
    "Writing and Computer Desk capabilities must preserve disjoint Option A.",
    "Initial furniture must remain owner-controlled.",
    "Types, orientations, states and art geometry versions must agree.",
)


# Multi-rule builders retain their accepted fail-fast exceptions. Only documented
# S-prefixed messages are adapted; details are never returned to the caller.
def _rule(error: ValueError, default: str) -> str:
    prefix = str(error).split(":", 1)[0].split("/", 1)[0].split(" ", 1)[0]
    return prefix if prefix in tuple(f"S{i}" for i in range(1, 18)) else default


def validate_layout(candidate: LayoutCandidate) -> ValidationResult:
    """S1-S17, prevention only; independent failures accumulate, prerequisites gate stages.

    Locations identify input sections or stable object/reference IDs. Error order
    is numeric S-rule then location. Typed domain constructors own malformed JSON.
    No recovery is used to accept an unsafe candidate, and nothing is activated.
    """
    errors: list[ValidationError] = []

    def fail(code: str, *location: str) -> None:
        errors.append(ValidationError(code, location, _RULE_MESSAGES[int(code[1:]) - 1]))

    try:
        validate_regions(
            candidate.regions, grid_width=candidate.grid_width, grid_height=candidate.grid_height
        )
    except ValueError:
        fail("S1", "regions")

    catalog: Catalog | None = None
    try:
        catalog = Catalog(candidate.types)
    except ValueError as error:
        fail(_rule(error, "S17"), "types")

    art_ids = tuple(record.art_id for record in candidate.art)
    if len(set(art_ids)) != len(art_ids):
        fail("S17", "art", "duplicate")
    for item in sorted(candidate.types, key=lambda item: item.id):
        if item.art_id is not None:
            record = next(
                (record for record in candidate.art if record.art_id == item.art_id), None
            )
            if (
                record is None
                or record.geometry_version != item.geometry_version
                or any(
                    orientation.value not in record.orientations
                    for orientation in item.orientations
                )
            ):
                fail("S17", "art", item.id)
        for slot in item.slots:
            if slot.status is not SlotStatus.ACTIVE and slot.maple_may_place:
                fail("S11", "types", item.id, slot.id)
    for host in sorted(candidate.instances, key=lambda host: host.id):
        host_type = next((item for item in candidate.types if item.id == host.type_id), None)
        if (
            host_type is None
            or host.orientation not in host_type.orientations
            or host.state not in host_type.states
        ):
            fail("S17", "instances", host.id)
        if host_type is not None:
            for policy in host.slot_policies:
                policy_slot = next(
                    (slot for slot in host_type.slots if slot.id == policy.slot), None
                )
                if (
                    policy_slot is not None
                    and policy_slot.status is not SlotStatus.ACTIVE
                    and policy.maple_may_place
                ):
                    fail("S11", "instances", host.id, policy.slot)

    structure = None
    topology = None
    lighting = None
    if not any(error.code == "S1" for error in errors):
        try:
            structure = derive_structure(candidate.regions)
        except ValueError as error:
            fail(_rule(error, "S2"), "regions")
    if structure is not None:
        try:
            topology = derive_topology(candidate.regions, candidate.doors)
        except ValueError as error:
            fail(_rule(error, "S3"), "doors")
    if topology is not None:
        try:
            lighting = derive_lighting(candidate.regions, candidate.doors, candidate.zones)
        except ValueError:
            fail("S12", "zones")
    if (
        structure is not None
        and topology is not None
        and lighting is not None
        and catalog is not None
    ):
        world = WorldLayout(candidate.regions, candidate.doors, structure, topology, lighting)
        house = None
        if not any(error.code in ("S11", "S17") for error in errors):
            try:
                house = build_catalog_layout(catalog, candidate.instances, world)
            except ValueError as error:
                fail(_rule(error, "S6"), "instances")
        if house is not None:
            mask = None
            try:
                mask = derive_walkability(world, house)
            except ValueError as error:
                fail(_rule(error, "S5"), "doors")
            if mask is not None:
                reachable = next(
                    (set(part) for part in mask.components if mask.safe_tile in part), set()
                )
                for point in house.points:
                    if Tile(point.template.approach.x, point.template.approach.y) not in reachable:
                        fail("S8", "points", point.instance_id, point.template.id)
                for bound_slot in house.slots:
                    if (
                        Tile(bound_slot.template.approach.x, bound_slot.template.approach.y)
                        not in reachable
                    ):
                        fail("S8", "slots", bound_slot.instance_id, bound_slot.template.id)
                safe = True
                try:
                    validate_safe_layout(world, house, candidate.maple)
                except ValueError as error:
                    fail(_rule(error, "S10"), "walkability")
                    safe = False
                if safe:
                    snapshot = ResolutionSnapshot(world, house)
                    try:
                        validate_activity_coverage(snapshot)
                    except ValueError:
                        fail("S9", "activities")
                    # Reuse the projection mapping; explicit targets cross-check the
                    # supplied compatibility contract without a second mapping table.
                    context = DevelopmentWorld(world, house)
                    for activity in Activity:
                        from_map = tuple(
                            point
                            for point in house.points
                            if any(
                                set(group) <= set(point.template.provides)
                                for group in requirement_for(activity).alternatives
                            )
                        )
                        for point in from_map:
                            reference = PointRef(point.instance_id, point.template.id)
                            try:
                                projected = project_point(context, reference, activity)
                                target = next(
                                    (
                                        target
                                        for target in candidate.legacy_targets
                                        if target.id == projected.id
                                    ),
                                    None,
                                )
                                if target is None or activity not in target.allowed_actions:
                                    fail("S14", "legacy_targets", projected.id, activity.value)
                            except (ValueError, KeyError):
                                fail(
                                    "S14",
                                    "points",
                                    reference.instance_id,
                                    reference.point_id,
                                    activity.value,
                                )
    return ValidationResult(
        tuple(sorted(set(errors), key=lambda error: (int(error.code[1:]), error.location)))
    )
