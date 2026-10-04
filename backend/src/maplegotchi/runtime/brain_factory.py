"""Runtime assembly for Maple's Brain implementation."""

from __future__ import annotations

from maplegotchi.brain.interface import Brain
from maplegotchi.brain.rule_brain import RuleBrain
from maplegotchi.config import BrainMode, Settings
from maplegotchi.runtime.external_brain import ExternalHttpBrain


def build_brain(settings: Settings) -> Brain:
    if settings.brain is BrainMode.RULE:
        return RuleBrain()

    if settings.brain is BrainMode.ANTIGRAVITY:
        return ExternalHttpBrain(base_url=settings.brain_url)

    raise ValueError(f"unsupported brain mode: {settings.brain}")
