"""Signals and interruption (ADR-0026 §7), as pure rules.

Core classifies what is happening into signals with one of four priorities:

- critical: may interrupt immediately (a serious server problem);
- high: may interrupt and force re-evaluation (severe exhaustion; reserved for
  future real owner messages, e.g. Paolo via Discord);
- normal: waits for the current action to complete (offered to the next decision);
- low: never interrupts (context only).

Greet and Pet are not signals: they stay reactions only (D3, ADR-0026 §7).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from maplegotchi.core.behavior import FORCED_SLEEP_ENERGY, BehaviorInputs
from maplegotchi.core.daytime import require_utc
from maplegotchi.core.priority import RANK, Priority
from maplegotchi.core.state import MapleState

# Server attention at or above this is a serious problem (a failed service,
# disk >= 95 %, temperature >= 85 C: see core/attention.py).
CRITICAL_ATTENTION = 0.8
# Attention worth mentioning to the next decision, but not interrupting for.
NOTABLE_ATTENTION = 0.3
CURIOUS_SIGNAL = 75.0
LONELY_SIGNAL = 30.0
LOW_MOOD_SIGNAL = 35.0


class SignalKind(StrEnum):
    SERVER_PROBLEM = "server_problem"  # critical
    EXHAUSTED = "exhausted"  # high (the forced-sleep rule)
    OWNER_MESSAGE = "owner_message"  # high; produced only by a future chat input
    SERVER_NOTABLE = "server_notable"  # normal
    CURIOUS = "curious"  # normal
    LONELY = "lonely"  # normal
    LOW_MOOD = "low_mood"  # low


SIGNAL_PRIORITY = {
    SignalKind.SERVER_PROBLEM: Priority.CRITICAL,
    SignalKind.EXHAUSTED: Priority.HIGH,
    SignalKind.OWNER_MESSAGE: Priority.HIGH,
    SignalKind.SERVER_NOTABLE: Priority.NORMAL,
    SignalKind.CURIOUS: Priority.NORMAL,
    SignalKind.LONELY: Priority.NORMAL,
    SignalKind.LOW_MOOD: Priority.LOW,
}


@dataclass(frozen=True, slots=True)
class Signal:
    kind: SignalKind

    @property
    def priority(self) -> Priority:
        return SIGNAL_PRIORITY[self.kind]


def classify_signals(
    state: MapleState, now: datetime, inputs: BehaviorInputs
) -> tuple[Signal, ...]:
    """What is going on, most urgent first. Pure; no signal changes state by itself."""
    require_utc(now, "now")
    needs = state.needs
    found: list[Signal] = []
    if inputs.server_attention >= CRITICAL_ATTENTION:
        found.append(Signal(SignalKind.SERVER_PROBLEM))
    elif inputs.server_attention >= NOTABLE_ATTENTION:
        found.append(Signal(SignalKind.SERVER_NOTABLE))
    if needs.energy <= FORCED_SLEEP_ENERGY:
        found.append(Signal(SignalKind.EXHAUSTED))
    if needs.curiosity >= CURIOUS_SIGNAL:
        found.append(Signal(SignalKind.CURIOUS))
    if needs.social < LONELY_SIGNAL:
        found.append(Signal(SignalKind.LONELY))
    if needs.mood < LOW_MOOD_SIGNAL:
        found.append(Signal(SignalKind.LOW_MOOD))
    return tuple(sorted(found, key=lambda s: -RANK[s.priority]))


def interrupts(signal: Signal, current: Priority) -> bool:
    """Whether `signal` interrupts an action that was started with priority `current`.

    - critical interrupts anything except another critical response;
    - high interrupts normal/low actions; exhaustion is the existing hard
      forced-sleep rule and interrupts even a critical response;
    - normal and low never interrupt.
    """
    if signal.kind is SignalKind.EXHAUSTED:
        return True
    if signal.priority is Priority.CRITICAL:
        return current is not Priority.CRITICAL
    if signal.priority is Priority.HIGH:
        return RANK[current] < RANK[Priority.HIGH]
    return False
