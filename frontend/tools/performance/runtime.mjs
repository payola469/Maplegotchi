// Resolve optional local tooling without adding application dependencies.
import { createRequire } from 'node:module';
const require = createRequire(import.meta.url);
export function browserRuntime(args = process.argv.slice(2)) {
  const arg = (name, fallback) => args.includes(name) ? args[args.indexOf(name) + 1] : fallback;
  const moduleName = arg('--playwright', process.env.R1A19_PLAYWRIGHT ?? 'playwright');
  const { chromium } = require(moduleName);
  const version = require(require.resolve(`${moduleName}/package.json`)).version;
  const executablePath = arg('--chrome', process.env.R1A19_CHROME);
  return { chromium, version, launch: { headless: true, ...(executablePath ? { executablePath } : { channel: 'chrome' }) } };
}
