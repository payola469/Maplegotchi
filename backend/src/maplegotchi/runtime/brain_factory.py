"""Runtime assembly for Maple's Brain implementation."""

from __future__ import annotations

from maplegotchi.brain.director import Director
from maplegotchi.brain.interface import Brain
from maplegotchi.brain.rule_brain import RuleBrain
from maplegotchi.config import BrainMode, DirectorMode, Settings
from maplegotchi.runtime.external_brain import ExternalHttpBrain
from maplegotchi.runtime.external_director import ExternalHttpDirector


def build_brain(settings: Settings) -> Brain:
    if settings.brain is BrainMode.RULE:
        return RuleBrain()

    if settings.brain is BrainMode.ANTIGRAVITY:
        return ExternalHttpBrain(base_url=settings.brain_url)

    raise ValueError(f"unsupported brain mode: {settings.brain}")


def build_director(settings: Settings) -> Director | None:
    """The configured Director, or None for core's rule direction (ADR-0026 §2)."""
    if settings.director is DirectorMode.RULE:
        return None
    if settings.director is DirectorMode.ANTIGRAVITY:
        return ExternalHttpDirector(
            base_url=settings.brain_url, timeout_seconds=settings.director_timeout_seconds
        )
    raise ValueError(f"unsupported director mode: {settings.director}")
