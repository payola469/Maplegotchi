import { test } from 'node:test';
import assert from 'node:assert/strict';
import { cpSync, mkdirSync, mkdtempSync, rmSync, writeFileSync, readdirSync } from 'node:fs';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { build, root } from './cli.mjs';
import { verifyBundle } from './bundle.mjs';
function fixture(check) {
  const dir = mkdtempSync(join(tmpdir(), 'maple-bundle-'));
  try {
    for (const path of ['art', 'backend/src/maplegotchi/world_catalog', '.gitattributes']) cpSync(join(root, path), join(dir, path), { recursive: true });
    const generated = join(dir, 'frontend/src/world-room/generated'), dist = join(dir, 'frontend/dist/assets'); build(dir, generated); mkdirSync(dist, { recursive: true });
    for (const name of readdirSync(generated).filter((n) => n.endsWith('.png'))) cpSync(join(generated, name), join(dist, name.replace('.png', '-testHASH.png')));
    check(dir, dist);
  } finally { rmSync(dir, { recursive: true, force: true }); }
}
test('bundle allows only matching processed hashed atlas pages', () => fixture((d) => assert.deepEqual(verifyBundle(d), { hashedPages: 2, rawSourceFiles: 0, productionPreview: false })));
test('bundle rejects source sidecars', () => fixture((d, out) => { writeFileSync(join(out, 'furniture.meta.json'), '{}'); assert.throws(() => verifyBundle(d), /Source art leaked/); }));
test('bundle rejects unprocessed raw PNG bytes', () => fixture((d, out) => { writeFileSync(join(out, 'raw.png'), 'foreign'); assert.throws(() => verifyBundle(d), /Unprocessed PNG/); }));
test('bundle rejects leaked fixture entry', () => fixture((d, out) => { writeFileSync(join(out, 'preview.js'), 'FIXTURE / DEMO DATA'); assert.throws(() => verifyBundle(d), /Fixture preview leaked/); }));
