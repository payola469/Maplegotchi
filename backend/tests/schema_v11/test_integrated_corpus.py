"""Input-manifest checks only; these do not assert full simulation execution."""

from datetime import timedelta

from tests.schema_v11.integrated_corpus import DAYS, REQUIRED_CASES, START, TICK, TICKS, corpus


def test_candidate_retains_thirty_days_and_repeatable_inputs_without_pin() -> None:
    first = corpus()
    assert first == corpus()
    assert len(first) == 2 and first[0].seed_hex != first[1].seed_hex
    for case in first:
        assert len(case.at) == TICKS == 8640
        assert case.at[0] == START + TICK
        assert case.at[-1] == START + timedelta(days=DAYS)
        assert all(b - a == TICK for a, b in zip((START, *case.at[:-1]), case.at, strict=True))
        assert all(0 < cut < TICKS for cut in case.restart_after)
        assert tuple(sorted(set(case.restart_after))) == case.restart_after
        assert case.required_cases == REQUIRED_CASES
        assert {"critical_mid_edge", "high_mid_edge", "read_unavailable_reconnect"} <= set(
            case.required_cases
        )
        assert case.status == "candidate_not_acceptance_evidence"
