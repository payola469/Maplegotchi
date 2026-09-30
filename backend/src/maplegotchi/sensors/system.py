"""psutil-backed host probe (read-only; unprivileged; no subprocess or network).

paolo-core (Linux) is the production target. Elsewhere, metrics that psutil
cannot report honestly are `unavailable` rather than faked: load average is
Linux-only here (psutil emulates it on Windows with a background thread and
early zeros), and temperatures exist only where psutil exposes them.
"""

from __future__ import annotations

import sys

import psutil

from maplegotchi.sensors.interface import MetricUnavailable

# A plain flag (not an inline sys.platform check) so type checkers on any
# platform still analyse both branches.
IS_LINUX: bool = sys.platform.startswith("linux")

# Preferred temperature chips, most representative of the CPU first.
PREFERRED_TEMPERATURE_CHIPS = (
    "coretemp",
    "k10temp",
    "zenpower",
    "cpu_thermal",
    "soc_thermal",
    "acpitz",
)
# Within a chip, the whole-package sensor is the most representative reading.
PACKAGE_LABEL = "Package id 0"


class PsutilHostProbe:
    """CPU usage is the busy share since the previous reading (the heartbeat interval)."""

    source = "psutil"

    def __init__(self) -> None:
        self._last_cpu_times: tuple[float, float] | None = None

    def cpu_percent(self) -> float:
        times = psutil.cpu_times()
        total = float(sum(times))
        idle = float(times.idle) + float(getattr(times, "iowait", 0.0))
        previous, self._last_cpu_times = self._last_cpu_times, (total, idle)
        if previous is None:
            raise MetricUnavailable("warming_up")
        elapsed = total - previous[0]
        if elapsed <= 0:
            raise MetricUnavailable("no_elapsed_cpu_time")
        return (elapsed - (idle - previous[1])) / elapsed * 100.0

    def memory_percent(self) -> float:
        return float(psutil.virtual_memory().percent)

    def disk_percent(self, mount: str) -> float:
        return float(psutil.disk_usage(mount).percent)

    def load_average(self) -> tuple[float, float, float]:
        if not IS_LINUX:
            raise MetricUnavailable("not_supported_on_platform")
        one, five, fifteen = psutil.getloadavg()  # reads /proc/loadavg
        return float(one), float(five), float(fifteen)

    def cpu_count(self) -> int:
        count = psutil.cpu_count(logical=True)
        if not count:
            raise MetricUnavailable("cpu_count_unknown")
        return int(count)

    def temperature_celsius(self) -> float:
        reader = getattr(psutil, "sensors_temperatures", None)
        if reader is None:
            raise MetricUnavailable("not_supported_on_platform")
        chips = reader()
        if not chips:
            raise MetricUnavailable("no_temperature_sensors")
        for name in (*PREFERRED_TEMPERATURE_CHIPS, *sorted(chips)):
            entries = chips.get(name, [])
            package = [float(e.current) for e in entries if e.label == PACKAGE_LABEL]
            if package:  # paolo-core: coretemp "Package id 0" (Stage A survey)
                return package[0]
            readings = [float(entry.current) for entry in entries]
            if readings:
                return max(readings)
        raise MetricUnavailable("no_temperature_sensors")
