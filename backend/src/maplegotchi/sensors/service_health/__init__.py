"""Service-health providers behind a provider-independent get_service_health().

Order: existing monitoring DB (read-only), then read-only systemd D-Bus for
gaps only, fake for dev/tests. No subprocess/systemctl fallback. The real
providers are written only after the Phase 3 paolo-core survey. See CLAUDE.md §3.5.
"""
