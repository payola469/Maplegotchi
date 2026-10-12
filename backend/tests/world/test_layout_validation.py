"""Aggregate S1-S17 acceptance, precise negative corpus and ordering properties."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from random import Random

import pytest

from maplegotchi.core.activities import Activity
from maplegotchi.core.world.coordinates import Tile
from maplegotchi.core.world.layout_validation import LayoutCandidate, validate_layout
from maplegotchi.core.world.model import Rect
from tests.world.oracle import Oracle
from tests.world.validation_corpus import canonical_candidate, mutate

RULES = tuple(f"S{i}" for i in range(1, 18))


@pytest.fixture(scope="module")
def candidate() -> LayoutCandidate:
    return canonical_candidate()


@pytest.mark.parametrize("rule", RULES)
def test_each_rule_positive(candidate: LayoutCandidate, rule: str) -> None:
    result = validate_layout(candidate)
    assert result.valid and not any(error.code == rule for error in result.errors)


@pytest.mark.parametrize("rule", RULES)
def test_named_negative_corpus(candidate: LayoutCandidate, rule: str) -> None:
    original = repr(candidate)
    changed = mutate(candidate, rule)
    result = validate_layout(changed)
    assert not result.valid
    assert rule in {error.code for error in result.errors}, result
    assert all(
        error.location and error.message and "secret" not in error.message
        for error in result.errors
    )
    assert validate_layout(changed) == result
    assert repr(candidate) == original


def test_canonical_matches_oracle(candidate: LayoutCandidate, spec_oracle: Oracle) -> None:
    assert len(candidate.regions) == len(spec_oracle.table(1).rows) == 8
    assert len(candidate.doors) == len(spec_oracle.table(2).rows) == 7
    assert len(candidate.instances) == len(spec_oracle.table(3).rows) == 28
    assert validate_layout(candidate).valid


def test_multiple_errors_stable_under_input_permutations(candidate: LayoutCandidate) -> None:
    changed = mutate(mutate(mutate(candidate, "S1"), "S15"), "S17")
    expected = validate_layout(changed)
    assert {"S1", "S15", "S17"} <= {error.code for error in expected.errors}
    rng = Random(143)  # noqa: S311 - fixed test corpus, not cryptography
    for _ in range(20):
        types = list(changed.types)
        art = list(changed.art)
        instances = list(changed.instances)
        rng.shuffle(types)
        rng.shuffle(art)
        rng.shuffle(instances)
        assert (
            validate_layout(
                replace(changed, types=tuple(types), art=tuple(art), instances=tuple(instances))
            )
            == expected
        )
    assert expected.errors == tuple(
        sorted(expected.errors, key=lambda error: (int(error.code[1:]), error.location))
    )
    with pytest.raises(FrozenInstanceError):
        expected.errors = ()  # type: ignore[misc]


def test_region_overlap(candidate: LayoutCandidate) -> None:
    rooms = tuple(
        replace(room, floor=Rect(1, 3, 10, 7)) if room.id == "bedroom" else room
        for room in candidate.regions
    )
    assert "S1" in {
        error.code for error in validate_layout(replace(candidate, regions=rooms)).errors
    }


def test_invalid_maple_and_legacy_actions(candidate: LayoutCandidate) -> None:
    assert "S13" in {
        error.code for error in validate_layout(replace(candidate, maple=Tile(1, 20))).errors
    }
    targets = tuple(
        replace(point, allowed_actions=(Activity.IDLE,)) if point.id == "bed.side" else point
        for point in candidate.legacy_targets
    )
    assert "S14" in {
        error.code for error in validate_layout(replace(candidate, legacy_targets=targets)).errors
    }


def test_unknown_type_and_manifest_missing(candidate: LayoutCandidate) -> None:
    hosts = (replace(candidate.instances[0], type_id="unknown.type"), *candidate.instances[1:])
    assert "S17" in {
        error.code for error in validate_layout(replace(candidate, instances=hosts)).errors
    }
    assert "S17" in {error.code for error in validate_layout(replace(candidate, art=())).errors}


@pytest.mark.parametrize("activity", tuple(Activity))
def test_removing_last_activity_provider(candidate: LayoutCandidate, activity: Activity) -> None:
    from maplegotchi.core.world.catalog import Capability
    from maplegotchi.core.world.resolution import requirement_for

    requirement = requirement_for(activity)
    if activity in (Activity.IDLE, Activity.WALK):
        # Retain the declared fallback point geometry, remove its open-floor capability.
        types = tuple(
            replace(
                item,
                capabilities=(Capability.PLANT,),
                points=tuple(replace(point, provides=(Capability.PLANT,)) for point in item.points),
            )
            if item.id == "marker.idle_spot"
            else item
            for item in candidate.types
        )
        changed = replace(candidate, types=types)
    else:
        provider_types = {
            item.id
            for item in candidate.types
            if any(
                set(group) <= set(point.provides)
                for group in requirement.alternatives
                for point in item.points
            )
        }
        changed = replace(
            candidate,
            instances=tuple(
                host for host in candidate.instances if host.type_id not in provider_types
            ),
        )
    assert "S9" in {error.code for error in validate_layout(changed).errors}


def test_unreachable_approach_gets_s8(candidate: LayoutCandidate) -> None:
    hosts = tuple(
        replace(host, origin=Tile(3, 4), room_id="bedroom") if host.id == "lamp.living" else host
        for host in candidate.instances
    )
    assert "S8" in {
        error.code for error in validate_layout(replace(candidate, instances=hosts)).errors
    }


def test_all_corpus_ordering_and_canonical_permutation(candidate: LayoutCandidate) -> None:
    for changed in (candidate, *(mutate(candidate, rule) for rule in RULES)):
        reordered = replace(
            changed,
            regions=tuple(reversed(changed.regions)),
            doors=tuple(reversed(changed.doors)),
            zones=tuple(reversed(changed.zones)),
            types=tuple(reversed(changed.types)),
            instances=tuple(reversed(changed.instances)),
            art=tuple(reversed(changed.art)),
            legacy_targets=tuple(reversed(changed.legacy_targets)),
        )
        assert validate_layout(reordered) == validate_layout(changed)
