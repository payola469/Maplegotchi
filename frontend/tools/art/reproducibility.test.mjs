import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdirSync, mkdtempSync, readFileSync, readdirSync, rmSync, symlinkSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { digest, json } from './pack.mjs';
import { createManifest, writeArtifact, readArtifact, compareArtifacts, safePath } from './reproducibility.mjs';
const revision = 'a'.repeat(40);
function generated(directory) {
  mkdirSync(directory);
  for (const [name, bytes] of Object.entries({ 'shared-0.png': 'png-shared', 'character-0.png': 'png-character', 'shared-0.json': '{"frames":{}}\n', 'character-0.json': '{}\n', 'index.ts': '// generated\n' })) writeFileSync(join(directory, name), bytes);
  refresh(directory);
}
function refresh(directory) {
  writeFileSync(join(directory, 'budget.json'), json({ frameCount: 193, pages: ['character-0', 'shared-0'].map((name) => ({ name, pngSha256: digest(readFileSync(join(directory, name + '.png'))), metadataSha256: digest(readFileSync(join(directory, name + '.json'))) })), indexSha256: digest(readFileSync(join(directory, 'index.ts'))) }));
}
function sandbox(work) {
  const directory = mkdtempSync(join(tmpdir(), 'maple-compare-'));
  try { const source = join(directory, 'source'); generated(source); work(directory, source); }
  finally { rmSync(directory, { recursive: true, force: true }); }
}
function editManifest(artifact, edit) { const path = join(artifact, 'manifest.json'), value = JSON.parse(readFileSync(path)); edit(value); writeFileSync(path, json(value)); }
test('manifest hashes all six actual files in canonical path order without paths/times', () => sandbox((d, source) => {
  const manifest = createManifest(source, revision);
  assert.equal(manifest.files.length, 6);
  assert.deepEqual(manifest.files.map((f) => f.path), [...readdirSync(source)].sort());
  for (const f of manifest.files) { assert.equal(f.sha256, digest(readFileSync(join(source, f.path)))); assert.equal(f.size, readFileSync(join(source, f.path)).length); }
  assert.ok(!json(manifest).includes(d));
  assert.deepEqual(createManifest(source, revision), manifest);
}));
test('two independently copied actual artifacts compare exactly', () => sandbox((d, source) => {
  const a = join(d, 'windows'), b = join(d, 'linux'); writeArtifact(source, a, revision); writeArtifact(source, b, revision);
  assert.deepEqual(compareArtifacts(a, b), { revision, files: 6, byteIdentical: true, comparedFiles: createManifest(source, revision).files });
}));
for (const file of ['character-0.png', 'character-0.json', 'shared-0.png', 'shared-0.json', 'index.ts', 'budget.json']) {
  test(`missing ${file} fails closed`, () => sandbox((d, source) => { rmSync(join(source, file)); assert.throws(() => createManifest(source, revision), new RegExp(file.replace('.', '\\.'))); }));
}
test('unexpected generated output fails', () => sandbox((d, source) => { writeFileSync(join(source, 'extra.json'), '{}'); assert.throws(() => createManifest(source, revision), /unexpected.*extra.json/); }));
for (const file of ['character-0.png', 'shared-0.json', 'index.ts']) {
  test(`different actual ${file} bytes fail even with truthful updated manifests`, () => sandbox((d, source) => {
    const a = join(d, 'windows'), b = join(d, 'linux'); writeArtifact(source, a, revision);
    writeFileSync(join(source, file), Buffer.concat([readFileSync(join(source, file)), Buffer.from('\r\n')])); refresh(source); writeArtifact(source, b, revision);
    assert.throws(() => compareArtifacts(a, b), new RegExp('byte mismatch:.*' + file.replace('.', '\\.')));
  }));
}
test('stale generated budget hash rejected', () => sandbox((d, source) => { writeFileSync(join(source, 'character-0.png'), 'changed'); assert.throws(() => createManifest(source, revision), /character-0.png: stale/); }));
test('manifest lies about actual bytes rejected', () => sandbox((d, source) => { const a = join(d, 'artifact'); writeArtifact(source, a, revision); editManifest(a, (m) => m.files[0].sha256 = '0'.repeat(64)); assert.throws(() => readArtifact(a), /budget.json: manifest does not match/); }));
test('duplicate manifest path rejected', () => sandbox((d, source) => { const a = join(d, 'artifact'); writeArtifact(source, a, revision); editManifest(a, (m) => m.files.push(m.files[0])); assert.throws(() => readArtifact(a), /Duplicate manifest path/); }));
test('manifest cannot omit required output', () => sandbox((d, source) => { const a = join(d, 'artifact'); writeArtifact(source, a, revision); editManifest(a, (m) => m.files = m.files.filter((f) => f.path !== 'index.ts')); assert.throws(() => readArtifact(a), /missing.*index.ts/); }));
test('noncanonical manifest order rejected', () => sandbox((d, source) => { const a = join(d, 'artifact'); writeArtifact(source, a, revision); editManifest(a, (m) => m.files.reverse()); assert.throws(() => readArtifact(a), /canonical order/); }));
test('different source commit rejected', () => sandbox((d, source) => { const a = join(d, 'windows'), b = join(d, 'linux'); writeArtifact(source, a, revision); writeArtifact(source, b, 'b'.repeat(40)); assert.throws(() => compareArtifacts(a, b), /revisions differ/); }));
test('absent artifact and missing manifest cannot pass', () => sandbox((d) => { assert.throws(() => readArtifact(join(d, 'absent')), /ENOENT/); const a = join(d, 'empty'); mkdirSync(a); assert.throws(() => readArtifact(a), /missing.*manifest.json/); }));
test('nonregular generated entry rejected', () => sandbox((d, source) => { rmSync(join(source, 'index.ts')); mkdirSync(join(source, 'index.ts')); assert.throws(() => createManifest(source, revision), /Nonregular/); }));
test('artifact output never overwrites existing files', () => sandbox((d, source) => { const a = join(d, 'artifact'); writeArtifact(source, a, revision); assert.throws(() => writeArtifact(source, a, revision), /must be empty/); assert.throws(() => writeArtifact(source, source, revision), /outside generated/); }));
for (const path of ['../index.ts', '/index.ts', 'C:/index.ts', 'a\\index.ts', 'a/index.ts', 'index.ts:stream', 'CON.json', 'con.png', 'index.ts ', '.', '']) test(`unsafe path ${JSON.stringify(path)} rejected`, () => assert.throws(() => safePath(path), /Unsafe/));
test('unsafe manifest path rejected before file access', () => sandbox((d, source) => { const a = join(d, 'artifact'); writeArtifact(source, a, revision); editManifest(a, (m) => m.files[0].path = '../secret.json'); assert.throws(() => readArtifact(a), /Unsafe/); }));
test('duplicate budget page rejected', () => sandbox((d, source) => { const p = join(source, 'budget.json'), b = JSON.parse(readFileSync(p)); b.pages.push(b.pages[0]); writeFileSync(p, json(b)); assert.throws(() => createManifest(source, revision), /Duplicate atlas page/); }));
test('malformed hash/schema/revision rejected', () => sandbox((d, source) => { const a = join(d, 'artifact'); writeArtifact(source, a, revision); editManifest(a, (m) => m.files[0].sha256 = 'wrong'); assert.throws(() => readArtifact(a), /Invalid hash/); assert.throws(() => createManifest(source, 'short'), /full lowercase Git SHA/); }));

test('linked generated/artifact directories rejected without following them', () => sandbox((d, source) => {
  const linked = join(d, 'linked'); symlinkSync(source, linked, 'junction');
  assert.throws(() => createManifest(linked, revision), /Nonregular/);
  assert.throws(() => readArtifact(linked), /Nonregular/);
}));
test('unexpected artifact-root payload rejected', () => sandbox((d, source) => { const a = join(d, 'artifact'); writeArtifact(source, a, revision); writeFileSync(join(a, 'extra.json'), '{}'); assert.throws(() => readArtifact(a), /unexpected.*extra.json/); }));
test('budget bytes are compared as authoritative output too', () => sandbox((d, source) => {
  const a = join(d, 'windows'), b = join(d, 'linux'); writeArtifact(source, a, revision);
  const p = join(source, 'budget.json'), report = JSON.parse(readFileSync(p)); report.frameCount++; writeFileSync(p, json(report)); writeArtifact(source, b, revision);
  assert.throws(() => compareArtifacts(a, b), /byte mismatch: budget.json/);
}));
