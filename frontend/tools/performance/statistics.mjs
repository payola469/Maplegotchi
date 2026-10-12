// Nearest-rank percentiles; keep raw timings, including slow outliers.
export function percentile(values, fraction) {
  if (!values.length || !Number.isFinite(fraction) || fraction <= 0 || fraction > 1 || values.some((x) => !Number.isFinite(x) || x < 0)) throw new Error('Invalid timing samples');
  return [...values].sort((a, b) => a - b)[Math.ceil(fraction * values.length) - 1];
}
export function distribution(values) {
  return { count: values.length, min: Math.min(...values), median: percentile(values, .5), p95: percentile(values, .95), p99: percentile(values, .99), max: Math.max(...values) };
}
export function budgets(rows) {
  return { drawCalls: rows.length > 0 && rows.every((r) => r.draws.count > 0 && r.draws.max > 0 && r.draws.max <= 40), desktopCpu: rows.some((r) => r.environment === 'desktop') && rows.filter((r) => r.environment === 'desktop').every((r) => r.renderMs.p95 <= 4), phoneCpu: rows.some((r) => r.environment === 'phone-emulated-4x') && rows.filter((r) => r.environment === 'phone-emulated-4x').every((r) => r.renderMs.p95 <= 8) };
}

// Include every live default framebuffer, including Pixi's retained 1x1 test context.
export function residency(contexts) {
  return contexts.reduce((total, c) => total + (c.lost ? 0 : c.allocations.reduce((n, a) => n + a.bytes, 0) + c.width * c.height * 16), 0);
}
export function framePacing(windows) {
  return windows.length >= 2 && windows.every((w) => w.intervals.length > 0 && w.intervals.every((ms) => Number.isFinite(ms) && ms >= 0 && ms <= 33) && w.intervals.reduce((a, b) => a + b, 0) >= 60000);
}
