import { readdirSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { digest } from './pack.mjs';
import { root } from './cli.mjs';
export function verifyBundle(rootDir = root) {
  const dist = join(rootDir, 'frontend/dist'), generated = join(rootDir, 'frontend/src/world-room/generated');
  const pages = readdirSync(generated).filter((f) => f.endsWith('.png'));
  const files = []; function walk(dir) { for (const entry of readdirSync(dir, { withFileTypes: true })) { const p = join(dir, entry.name); if (entry.isDirectory()) walk(p); else files.push(p); } } walk(dist);
  for (const page of pages) {
    const stem = page.slice(0, -4), found = files.filter((p) => new RegExp('/' + stem + '-[A-Za-z0-9_-]+\\.png$').test(p.split('\\').join('/')));
    if (found.length !== 1 || digest(readFileSync(found[0])) !== digest(readFileSync(join(generated, page)))) throw new Error('Missing/mismatched hashed atlas: ' + page);
  }
  for (const file of files) {
    const path = file.split('\\').join('/');
    if (file.endsWith('.js.map')) {
      const map = JSON.parse(readFileSync(file, 'utf8'));
      if (map.sources.some((source) => /(?:^|\/)(?:dev\/RoomSwitcher|world-room\/|docs\/fixtures\/)/.test(source))) throw new Error('Development source leaked into production map');
    }
    if (/art\/(?:export|palette)|meta\.json|maple-master|\.hex$|\.(?:aseprite|psd|kra|sqlite|db|py|ts)$/.test(path)) throw new Error('Source art leaked: ' + path);
    if (file.endsWith('.png') && !pages.some((p) => digest(readFileSync(join(generated, p))) === digest(readFileSync(file)))) throw new Error('Unprocessed PNG in bundle: ' + path);
    if (/\.(?:js|json|map)$/.test(file) && /r1a17-grid-v1|scripted-room-states|SIMULATION - synthetic R1A-17|FIXTURE \/ DEMO DATA|world-preview|fixture-sha256:|world-idle\.json|Development Room view|Current fixture room/.test(readFileSync(file, 'utf8'))) throw new Error('Fixture preview leaked into production');
  }
  return { hashedPages: pages.length, rawSourceFiles: 0, productionPreview: false };
}
if (process.argv[1]?.endsWith('bundle.mjs')) console.log(JSON.stringify(verifyBundle()));
