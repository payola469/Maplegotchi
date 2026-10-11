# Maple Room source art

Original neutral programmer placeholders only; no external artwork. Appearance, palette and 12×6 face overlays are provisional, not final production art.

- `export/<kind>/<asset-id>/`: plain Git PNG sheets/static frames and one `<asset-id>.meta.json` sidecar. No LFS, symlinks or export-ignore.
- `palette/maple-master.hex`: lowercase RGB palette used by validation.
- Source ownership/anchor rules: [art contract](../docs/architecture/maple-art-production-contract.md).

From `frontend`, run `pnpm assets:build` or `pnpm assets:test`. Normal build/test/dev/typecheck regenerate automatically. Generated PNG pages, Pixi JSON, budget JSON and TypeScript index belong in ignored `frontend/src/world-room/generated`; only hashed processed pages and required metadata belong in the runtime bundle. Never place raw source assets under `public`.

`node tools/art/make-placeholders.mjs` is explicit source authoring and refuses an existing `art/export`; builds never run it or silently fix invalid assets. Sidecar extensions and complete evidence are documented in the [R1A-14 plan](../docs/implementation/maple-room-r1a-14-asset-pipeline.md). Final art must pass the same validator. Native Windows reproduction is pending.
