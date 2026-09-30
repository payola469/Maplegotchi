#!/bin/sh
# shellcheck disable=SC2016  # checks are test expressions evaluated by check()
# Maple's view of the filesystem, checked from INSIDE the running service's
# mount namespace as maple-svc. Owner-run on paolo-core:
#
#   PID=$(systemctl show -P MainPID maplegotchi)
#   sudo nsenter --target "$PID" --mount \
#        --setuid "$(id -u maple-svc)" --setgid "$(id -g maple-svc)" \
#        -- /bin/sh /opt/maplegotchi/current/deploy/verify/sandbox_probe.sh
#
# Reads only. The single write is a probe file in /data/maple, removed at once.
# (Capabilities, seccomp, and the IP allowlist belong to the service process and
# its cgroup, not to this nsenter shell; check_boundaries.py checks those.)
set -u
failed=0
pass() { echo "[PASS] $*"; }
fail() { echo "[FAIL] $*"; failed=1; }
check() { if eval "$2"; then pass "$1"; else fail "$1"; fi; }

check "running as maple-svc" '[ "$(id -un)" = maple-svc ]'
check "no supplementary groups" '[ "$(id -G)" = "$(id -g)" ]'

probe=/data/maple/.sandbox-probe.$$
if (: > "$probe") 2>/dev/null && rm -f "$probe"; then
    pass "can write /data/maple"
else
    fail "cannot write /data/maple"
fi

for path in /opt/maplegotchi /opt/maplegotchi/current /opt/maplegotchi/current/venv/bin \
            /opt/maplegotchi/python /etc/maplegotchi /etc/maplegotchi/maplegotchi.env \
            /etc/systemd/system /data/monitor /data/monitor/metrics.db /data /usr /var/lib /; do
    check "cannot write $path" "[ ! -w '$path' ]"
done
check "can read metrics.db" '[ -r /data/monitor/metrics.db ]'
check "can read the settings file" '[ -r /etc/maplegotchi/maplegotchi.env ]'

check "/data shows only maple and monitor" \
    '[ "$(ls -A /data | tr "\n" " ")" = "maple monitor " ]'
for sibling in archive atlas backups downloads logs lost+found lycan-watch media monitor-v2 \
               pre-reinstall-backup private raw research-worker sources; do
    check "cannot see /data/$sibling" "[ ! -e '/data/$sibling' ]"
done

check "home directories are out of reach" '[ ! -r /home/paolo ] && [ ! -r /root ]'
for sock in /run/docker.sock /var/run/docker.sock; do
    check "no access to $sock" "[ ! -r '$sock' ] && [ ! -w '$sock' ]"
done
check "other users' processes are invisible" '[ ! -e /proc/1/status ]'
check "system D-Bus socket reachable" '[ -S /run/dbus/system_bus_socket ]'

if [ "$failed" -eq 0 ]; then echo "sandbox_probe: all checks passed"; else echo "sandbox_probe: FAILED"; fi
exit "$failed"
