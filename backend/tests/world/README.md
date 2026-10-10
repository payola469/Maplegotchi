# R1A-01 test infrastructure

`oracle.py` reads the approved Final Design Spec T1–T7 and its T6 walk matrix.
`approved_tables.json` is the reviewed, version-controlled expectation: 8 regions,
7 doors, 28 instances, 17 points, 12 slots, 7 resolution rows, 10 legacy rows and
the 7×7 walk matrix. All fields, row ordering, provisional values and symbolic
expressions are retained as strings; no geometry or routing algorithm is supplied.
T7 has a composite `(activity, new_points)` key because `idle|walk` repeats.

The snapshot was transcribed from the approved spec at the R1A-01 starting baseline.
Review spec/ADR changes before deliberately editing it; never regenerate it merely
to silence a mismatch. Parsing and approval are separate: `parse_spec()` reads
structure, `require_approved()` rejects any different cell/header/order/row count,
and `load_spec()` does both. The frozen `Oracle` / `Table` tuples can later be
compared with implementation output. They are test inputs, never runtime geometry.
The oracle protects the approved text, not the correctness of future algorithms or
all S1–S17 rules; those implementations belong to later workstreams.

## Determinism and fixtures

- `spec_oracle` is an immutable approved expectation. Build changed copies with
  `dataclasses.replace`; never edit the shared expectation or source spec in a test.
- Property approach: exhaustive cell mutation plus stdlib `Random(101)` seeded
  ordering, under the project's Python 3.12 requirement. No new dependency or
  production RNG use. Seeds are explicit test inputs, not live identity seeds.
  Every T1–T7 cell and all 49 walk lengths are exercised; failures identify the
  table, and pytest identifies the parametrized case. Extend deterministic corpora
  with future domain invariants rather than importing an implementation as oracle.
- Reuse `tests/core/support.py`, explicit UTC/fake clocks and synthetic state;
  `test_simulation.py` remains the legacy 30-day regression reference. Its pinned
  digest is unchanged. Never substitute a production database or identity.
- `scratch_root` is a per-test pytest `tmp_path` child (0700 requested on Unix;
  Windows access is governed by ACLs). `scratch_database` exclusively creates a
  new file, opens only that URI in `mode=rw`, and closes the connection in `finally`.
  It does not read `MAPLE_DATA_DIR`, apply migrations automatically, or birth a life.
  The harness test applies existing v10 migrations to scratch storage only.
- Evidence artifacts are scratch-only, exclusively created and limited to a check
  category and pass/fail counts. Never capture rows, prompts, identity values,
  seeds/fingerprints, response bodies or environment variables. Keep commands,
  commit, platform/tool versions and outcome summaries in the worklog; no blanket
  stdout capture. Pytest owns temporary-directory retention/cleanup; the fixture
  does not recursively delete paths. Use a fresh `--basetemp` for each invocation:
  pytest may delete an existing basetemp, so never point it at retained evidence,
  a database directory or production data.

## Boundaries and CI

`core/world` and `world_catalog` contain docstring-only package markers. There is
no world behavior, loader or catalog content. Three import-linter contracts in
`backend/pyproject.toml` enforce pure world dependencies, runtime-only catalog
loading and no runtime dependency on `tests`. The existing seven contracts remain.
`tests/world/contracts.py` additionally resolves relative/from-parent imports,
applies existing pure-core API rules and an import allowlist to world code, rejects
Python behavior in the catalog, and rejects runtime test imports or literal
references to the spec/oracle files. These static checks prevent accidental
coupling; they are not a security sandbox against obfuscated/dynamic access.
Wheel packaging includes only `src/maplegotchi`; the oracle is outside it.

Normal pytest discovery and the existing CI `pytest` / `lint-imports` commands
enforce these rules without a new CI workflow. Tests exercise the actual configured
`ForbiddenContract` on clean and planted import graphs (including indirect catalog
imports), plus AST positive and negative cases. Run focused checks from `backend`:

```text
uv run pytest tests/world
uv run ruff check tests/world src/maplegotchi/core/world src/maplegotchi/world_catalog
uv run ruff format --check tests/world src/maplegotchi/core/world src/maplegotchi/world_catalog
uv run mypy --platform linux --follow-imports=silent tests/world src/maplegotchi/core/world src/maplegotchi/world_catalog
uv run lint-imports
```

Local Windows execution details and actual results are in the R1A-01 baseline and
worklog. Local checks do not prove a GitHub CI run or Linux execution. No production
access or full release-gate rerun is needed to validate this test-only infrastructure.
