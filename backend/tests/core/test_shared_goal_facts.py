"""288 frozen Legacy goal/task/action vectors from the accepted pre-extraction core.

This is a shared-rule regression reference, not an integrated simulation pin.
"""


def test_legacy_goal_task_rule_vectors_unchanged() -> None:
    import hashlib
    import json
    from datetime import timedelta

    from maplegotchi.core.activities import Activity
    from maplegotchi.core.behavior import BehaviorInputs
    from maplegotchi.core.direction import DecisionTrigger, decide
    from tests.core.support import PARAMS, at_local, make_state, needs

    rows = []
    for activity in Activity:
        for energy in (5.0, 20.0, 80.0):
            for hour in (4, 12, 23):
                now = at_local(hour)
                for n in range(4):
                    s = make_state(
                        at=now - timedelta(minutes=30),
                        activity=activity,
                        state_needs=needs(energy=energy),
                        seed=f"{n:064x}",
                        until=timedelta(minutes=30),
                    )
                    r = decide(s, now, DecisionTrigger.ACTION_COMPLETED, BehaviorInputs(), PARAMS)
                    p = r.plan
                    g = r.state.goal
                    t = r.state.task
                    rows.append(
                        [
                            p.goal_op.value,
                            p.action.value,
                            p.duration.total_seconds(),
                            p.goal_type.value if p.goal_type else None,
                            p.horizon.total_seconds() if p.horizon else None,
                            [t.tool.value, t.target, t.title, t.category] if t else None,
                            g.id if g else None,
                            r.state.goal_counter,
                            r.state.rng.decision_counter,
                            r.state.action_id,
                            r.state.activity_started_at.isoformat(),
                            r.state.activity_until.isoformat(),
                            [repr(e) for e in r.events],
                        ]
                    )
    assert hashlib.sha256(
        json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest() == ("c25efe50df62ad3a516f08f15c5901666489169bcd632b85aa6217be81b2511a")
