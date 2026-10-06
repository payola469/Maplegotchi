"""Running the configured provider command, safely (ADR-0033 §2).

argv list, never a shell; the prompt on stdin; stdout is the answer; an empty
scratch working directory; a minimal environment; killed at its timeout; output
size-capped. Errors are reported as ProviderError and become "no answer" for Maple.
"""

from __future__ import annotations

import os
import subprocess  # the companion's job (ADR-0025): Maplegotchi itself never runs commands
import tempfile
from collections.abc import Callable, Mapping

from maple_brain.config import BrainSettings, ProviderKind

# Only what a CLI typically needs; HOME is the service's private state directory.
_PASSED_ENV = ("PATH", "HOME", "LANG", "LC_ALL", "XDG_CONFIG_HOME", "XDG_CACHE_HOME",
               "XDG_DATA_HOME", "XDG_STATE_HOME")  # fmt: skip


class ProviderError(RuntimeError):
    pass


Provider = Callable[[str, float], str | None]


def command_provider(settings: BrainSettings, environ: Mapping[str, str] | None = None) -> Provider:
    source = dict(os.environ if environ is None else environ)
    env = {k: source[k] for k in _PASSED_ENV if k in source}
    argv = [a.replace("{model}", settings.model) for a in settings.command]

    def run(prompt: str, timeout: float) -> str | None:
        with tempfile.TemporaryDirectory(prefix="maple-brain-") as scratch:
            try:
                done = subprocess.run(  # noqa: S603 - fixed argv from reviewed config, no shell
                    argv,
                    input=prompt.encode("utf-8"),
                    capture_output=True,
                    cwd=scratch,
                    env=env,
                    timeout=timeout,
                    check=False,
                )
            except subprocess.TimeoutExpired as exc:
                raise ProviderError("provider timed out") from exc
            except OSError as exc:
                raise ProviderError(f"provider could not start: {exc}") from exc
        if done.returncode != 0:
            raise ProviderError(f"provider exited with {done.returncode}")
        out = done.stdout[: settings.max_output_bytes].decode("utf-8", errors="replace").strip()
        return out or None

    return run


def none_provider(prompt: str, timeout: float) -> str | None:
    return None


def build_provider(settings: BrainSettings) -> Provider:
    if settings.provider is ProviderKind.COMMAND:
        return command_provider(settings)
    return none_provider
