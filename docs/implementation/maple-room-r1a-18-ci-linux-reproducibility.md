# R1A-18 — CI and Linux reproducibility

**STEP 152 reconciliation (2026-10-12): DONE / OWNER ACCEPTED / MERGED.** PR #19 merge `26c4a959322aaab1d38779739cea583be75455ea` verified before R1A-19. Earlier dated pending-CI/publication/status statements below are historical; no new R1A-18 execution or GitHub integration is claimed here.

## STEP 149 design before implementation — 2026-10-12

Baseline `4dc0e095470bcb572aeaebccb7bfa8e624f9b2fe` is the verified PR #18 merge. Clean main fast-forwarded only; isolated worktree `C:/GitHub/Maplegotchi-worktrees/r1a-18-ci-linux-reproducibility`, branch `codex/r1a-18-ci-linux-reproducibility`. R1A15/16/17 and unrelated heads preserved. Local implementation/testing/evidence only; no commit, push, PR, merge, deployment or production access.

### Inventory and gap analysis

Existing CI has backend Ubuntu/Windows (locked uv, Ruff, format, deploy checks, strict mypy, import contracts, full pytest), Ubuntu frontend (frozen pnpm, lint, typecheck, full tests including art, build/bundle guard), Ubuntu ShellCheck and Windows art (asset tests and build). scripts/check.sh also checks discord/brain companions, absent from CI. Exact contract export validation is embedded in backend tests but its standalone exporter is not called by check.sh. Existing art tests include pointer/filter=lfs rejection, missing assets/invalid metadata, source constraints, independent clean rebuild and accepted golden PNG/metadata/index equality. Existing production build verifies hashed atlas bytes, no raw PNG/sidecars or preview JS/maps. Gaps: actual cross-OS output comparison, companion CI coverage and explicit offline simulation/raw-art bundle negatives.

### Proposed CI architecture and artifact trust

Reuse Ubuntu frontend's accepted clean build as Linux atlas producer; retain Windows art job. Each emits an artifact containing actual generated files plus a manifest derived from those bytes, bound to the same github.sha. Add narrow companion Ubuntu matrix for discord/brain. Add an always-evaluated comparison job depending on both producers; fail if either producer failed/skipped, download two named artifacts from this same run, then compare. Read-only contents permission, ordinary pull_request, no secrets, deployment credentials, pull_request_target or downloaded-code execution. Controlled action versions consistent with current v4/v6 policy; artifacts retained one day.

Manifest version1 contains explicit 40-hex revision and sorted relative paths with byte sizes and SHA256. Include EVERY generator output: atlas PNG pages, each JSON metadata, index.ts and budget.json. Expected set derives from validated generated budget/pages plus mandatory index/budget; fail on missing/unexpected/duplicate/unsafe paths, symlinks/nonregular files, malformed manifest or stale self-reported hashes. Comparator rehashes downloaded actual files; textual manifest equality alone is insufficient. No line-ending normalization, timestamps, manual cross-OS pin or generator serialization change. Existing golden checks stay intact.

Local commands will expose manifest production and artifact comparison. check.sh calls manifest validation after production build; unit negatives run through existing asset tests, avoiding duplicate expensive suites. Actual Linux-vs-Windows comparison is CI-only until both artifacts exist. Windows executes native commands individually; the Bash wrapper itself is not claimed run.

### Coverage matrix (all required for R1A-18 acceptance)

| Check | Local / check.sh command | Proposed CI / OS | Evidence |
|---|---|---|---|
| Backend locked install/static/deploy/imports | uv sync --locked; ruff check/format; mypy; lint-imports | backend / Ubuntu + Windows | command logs |
| Backend full tests, S1–S17, both digest pins, rehearsal/security, exact exports | uv run pytest | backend / Ubuntu + Windows | collected tests and results |
| Frontend frozen install/lint/types | pnpm install --frozen-lockfile; pnpm lint; pnpm typecheck | frontend / Ubuntu | command logs |
| Frontend full tests and asset safety/goldens | pnpm test | frontend / Ubuntu | Vitest + Node totals |
| Windows source safety/goldens | pnpm assets:test | art-windows / Windows | Node results |
| Production build/bundle isolation | pnpm build | frontend Ubuntu + art-windows Windows | actual dist guard |
| Companion locked install/static/tests | same existing uv commands per project | companions matrix / Ubuntu | command logs |
| ShellCheck | existing three script groups | shell / Ubuntu | command logs |
| Actual generated-byte hash manifest | pnpm assets:manifest --revision SHA [--output DIR] | frontend Ubuntu + art-windows Windows | six generated files + manifest |
| Cross-OS comparison | pnpm assets:compare WINDOWS_ARTIFACT LINUX_ARTIFACT; unit negatives via pnpm test | art-compare / Ubuntu | filename-level results, required fail-closed gate |

### Completion and safety

Preserve accepted art/geometry, goldens and both simulation pins. Test canonical order, manifest generation, missing/extra files, PNG/metadata/index mismatches, duplicate/unsafe paths, malformed/stale manifests, wrong revision, and no false success from absent outputs. Preserve explicit LFS pointer/filter guards. Strengthen actual bundle inspection for raw authoring files and test-only simulation fixtures; allowed production source maps retain the existing policy and reject dev sources. No runtime/API/SSE/CSP/Origin/default Room change or production pipeline edit.

Local success earns REVIEW / pending owner acceptance, **17 DONE / 1 REVIEW / 2 TODO = 85%**. Native Ubuntu/Windows CI, actual cross-OS artifact equality, owner acceptance and confirmed merge remain required for DONE; eventual merge yields18/20=90%. No R1A19/20, R1b, performance/soak or B14 work. Linux execution is pending, not inferred from valid YAML. Final results/manifest/reproduction follow after actual local execution.

## STEP 149 final local result — REVIEW / pending owner acceptance

**PASS for local implementation and Windows validation.** R1A-01–17 are DONE / OWNER ACCEPTED / MERGED; R1A-18 is REVIEW, not DONE. Counters: 17 DONE / 1 REVIEW / 2 TODO = 85%. Native Linux execution, GitHub workflow execution and actual Linux-vs-Windows equality remain pending separate integration authorization. No architectural owner decision is needed for this implementation. Acceptance, full required CI evidence and confirmed merge are still required; eventual progress is 18/20 = 90%.

### Final implementation and corrective change

The final workflow expands to eight jobs: backend Ubuntu/Windows, frontend Ubuntu, ShellCheck Ubuntu, art Windows, companions discord/brain Ubuntu, and comparison Ubuntu. Existing unfiltered backend tests preserve S1–S17, Oracle/rehearsal/security, R1A-17's 54 tests (including three complete pinned traces), the original 30-day digest and exact contract export validation. All existing install/static/test/build steps remain. Producer jobs run clean builds at the same github.sha, upload named atlas-linux/atlas-windows artifacts for one day, and the always-evaluated dependent comparison fails closed if either producer failed/skipped. Missing downloads fail the job. Branch-protection settings were not changed or claimed verified.

scripts/check.sh adds only manifest validation after its existing production build; manifest negatives run in the existing asset suite. Companion checks already in the local wrapper now have CI coverage. New package scripts expose assets:manifest and assets:compare; dependencies and lockfiles are unchanged. Native commands were run individually on Windows; the Bash wrapper was not executed.

A real Windows source-safety defect was reproduced before correction: Git returns forward-slash repository roots, while Node's resolved root uses Windows separators. Direct string equality skipped effective Git attributes and could miss .git/info/attributes filter=lfs. A disposable repository regression failed with Missing expected exception before the fix. Comparing resolve(top) with resolve(root) restores the existing git check-attr path. Explicit regular-file checks now cover source files and palette inputs too. The new effective-attributes and palette-directory regressions pass. No art, serialization, golden pin or runtime behavior was changed.

### Fresh Windows validation (STEP 149 only)

| Gate | Actual result |
|---|---|
| Backend locked install, full pytest | 3896 PASS / 21 SKIPPED, 226.00 seconds |
| Windows skips | 18 Bash-unavailable deployment integration; 1 POSIX/non-root permission; 2 file-symlink privilege |
| Backend/deploy Ruff and format | PASS, 244 backend files / 7 deploy files |
| Strict mypy / import boundaries / exact exporter | PASS, 242 typed files; 10 import contracts; tests.api.world_contract_export executed |
| Frontend frozen install, ESLint, TypeScript | PASS; final production build reruns tsc |
| Final frontend suite | 586 PASS across 25 files, no skips |
| Final asset suite | 118 PASS, no skips (69 existing + 38 reproducibility + 9 bundle + 2 source-safety cases) |
| Companions | discord 22 PASS (0.34s); brain 28 PASS (1.78s); locked installs, Ruff/format and strict mypy PASS |
| Production build and actual bundle guard | PASS; 2 approved hashed pages, 0 raw source files, productionPreview=false |
| ShellCheck | All three existing groups PASS, version 0.11.0 |
| Workflow static validation | actionlint 1.7.12 PASS; embedded ShellCheck disabled, separate ShellCheck above executed |

Environment: Windows, Python 3.12.10, uv 0.13.0, Node 24.20.0, pnpm 12.3.4. Final command logs are ignored local evidence under var/r1a18-backend.log, var/r1a18-final-frontend.log and var/r1a18-final-build.log. Earlier intermediate asset totals are superseded by 118. No backend code changed after its full run; the last correction affected frontend build tooling only and final frontend tests/build reran afterward.

Workflow validator came from the official rhysd/actionlint v1.7.12 Windows AMD64 release, verified against its published archive SHA256 6e7241b51e6817ea6a047693d8e6fed13b31819c9a0dd6c5a726e1592d22f6e9. It reports Go1.26.1/windows/amd64. It is ignored local tooling, not a new project dependency. Valid YAML/expressions/action inputs/dependencies do not establish actual CI success.

### Actual output manifest and comparison evidence

Two independent Windows builds produced byte-identical six-file artifacts at var/atlas-windows-local and var/atlas-windows-independent; CLI comparison passed after rehashing actual copied bytes. This is Windows-vs-Windows evidence ONLY. Final generated outputs also match that first artifact after the source-safety fix. 193 frames, two atlas pages, accepted goldens unchanged. Static RGBA8 bytes 1572864, runtime texture bytes 4194304, resident upper bound 5767168; these are existing atlas accounting, not new performance acceptance.

Manifest version 1, revision 4dc0e095470bcb572aeaebccb7bfa8e624f9b2fe. manifest.json SHA256: 65b93dc81bafd511476a847e9d3f7a9a62b36dbbfd4707c21d2450c49dd663b5. Paths are sorted, relative and flat; no timestamps, absolute machine paths or line-ending normalization. Manifest bytes and actual generated files are uploaded together, but equality is established by rehashing files, not trusting declared hashes.

| Generated file | Bytes | Actual SHA256 |
|---|---:|---|
| budget.json | 820 | `6936e71f2bd5028ab19d9dd3e3caf708740919239ec7cb6763666504ca3f16d6` |
| character-0.json | 57499 | `8776fdc50db20fd91246c05cef63c306c32af1a75129b44d0d043860e66ee6ee` |
| character-0.png | 1049236 | `630070036d3fdc838d782d6f7be8ced0f309ce864b6705110fc5cbba5154e669` |
| index.ts | 113233 | `5ee8f05364b6a9f42c1a75d4ee2b2b219dbc5648d636413241115491a060e833` |
| shared-0.json | 29058 | `1b50a5a357501708bf5fc90cec4da8c994ae47aaa24d61c1ce2ca9bb4c708192` |
| shared-0.png | 525420 | `ec634d545d1af7dc4a1c53fe6c92462f4da820b0ff4cefc5b2c30077c36f77a3` |

The comparator validates the exact schema, revision, file set, sorted order, sizes, hashes and existing budget hashes. It rejects missing/unexpected/duplicate/unsafe paths, traversal/absolute/drive/ADS/reserved names, symlink/junction/nonregular files, malformed or lying manifests, stale budget hashes and revision mismatch. Tests include all six missing outputs and genuine PNG/metadata/index mismatches with internally truthful regenerated manifests. A real CLI missing-artifact invocation exited nonzero. No downloaded code is executed, no generator outputs are normalized or repinned, and an absent artifact cannot yield PASS.

Production atlas files are assets/character-0-BaduxT1u.png (1049236 bytes) and assets/shared-0-LxlzOm8s.png (525420 bytes), matching approved processed bytes. Guards retain raw PNG/sidecar/dev-source rejection and additionally reject authoring/database/Python/TypeScript files and R1A-17 fixture/simulation signatures in JS/JSON/maps. Nine new bundle negatives/positive-source-map-policy tests pass. Production source maps remain permitted only under the accepted exclusion policy. Existing E24 LFS pointer and filter=lfs, E13 missing-frame and E1 invalid-sidecar regressions pass in the same asset suite. Linux/Windows producer jobs execute these asset checks; actual new CI runs are pending.

Preserved pins: R1A-17 grid b3287b3d13ed406fc98ecc5be58494e9f3ac9df7fc4b0a70cedb6e85ad5500d3; original 30-day 458d6cb4035329a008105f8f2055d5f35b61cc1f537df3e04eabfcfe52d25917. Fresh full backend tests pass both. No validator, geometry, Oracle, runtime frontend/backend, API/SSE, CSP/Origin, schema, default Room or artwork edits.

### Reproduction and pending acceptance

From frontend after frozen install, run pnpm test and pnpm build. Then pnpm assets:manifest --revision <full-checkout-SHA> --output ../var/<new-empty-artifact-directory>. Compare two freshly generated artifacts with pnpm assets:compare <windows-artifact> <linux-artifact>. The CLI refuses to overwrite a populated artifact directory. CI uses github.sha for both producers. Actual native Linux execution and cross-OS byte equality cannot be substituted by the local Windows comparison or actionlint result.

No fresh browser/DPR/physical-device/GPU/performance/soak testing is claimed. Prior accepted browser evidence remains historical. Windows skips require native CI coverage; Bash-wrapper execution is pending Linux/Git Bash. No production credentials/access or paolo-core changes. No R1A-19/20, R1b or B14 work. No commit, staging, push, PR, merge or deployment performed in STEP 149. The authorized clean-main fast-forward reconciled the already merged PR18 only.

### Exact changed-file manifest

Sixteen paths: nine build/CI/tool/test files and seven documentation files. Ignored build outputs, environments, downloaded validator and var evidence are not change-set contents.

- `.github/workflows/ci.yml`
- `CLAUDE.md`
- `docs/architecture.md`
- `docs/deployment.md`
- `docs/implementation/maple-room-r1a-18-ci-linux-reproducibility.md`
- `docs/implementation/maple-room-r1a-checklist.md`
- `docs/implementation/maple-room-r1a-plan.md`
- `docs/implementation/maple-room-r1a-worklog.md`
- `frontend/package.json`
- `frontend/tools/art/bundle.mjs`
- `frontend/tools/art/bundle.test.mjs`
- `frontend/tools/art/pipeline.test.mjs`
- `frontend/tools/art/reproducibility.mjs`
- `frontend/tools/art/reproducibility.test.mjs`
- `frontend/tools/art/validate.mjs`
- `scripts/check.sh`

STEP149 final integrity PASS: exact16 Git-derived changed paths, 107 resolved local Markdown links, LF throughout, matching17 DONE/1 REVIEW/2 TODO counters and git diff --check. Complete149554-byte pre-STEP149 worklog prefix retained; baseline Git blob b5be64f21d4d63b18d0730ce3e71ef15ef9126d3. Main and R1A15/16/17 worktrees clean at verified heads; unrelated branch heads preserved. Active HEAD remains4dc0e095470bcb572aeaebccb7bfa8e624f9b2fe and staging is empty. Stop after local QA/evidence.

## STEP 150 — owner acceptance and GitHub Integration preparation

Owner accepts STEP 149 local implementation and Windows evidence. REVIEW / OWNER ACCEPTED / MERGE PENDING; 17 DONE / 1 REVIEW / 2 TODO = 85%. Final review, fresh checks, commit, normal push, PR into v0.2-development and actual CI/artifact inspection authorized. No merge, deployment, production access or later-workstream authorization. Existing worktree retained; remote base remains exactly4dc0e095470bcb572aeaebccb7bfa8e624f9b2fe. No reset/rebase/history rewriting or baseline-branch/Mac-only-history modification.

Final changed-file/security review preserves the exact16-path manifest above. Ordinary pull_request, contents:read, no production environments/secrets/write permissions/downloaded-code execution. Same-run named artifacts, same github.sha, locked producer installs and deterministic approved builds retained; comparison always evaluates and rejects failed/skipped producers. Exact generated output set remains six files. No unexpected art/generated/runtime/security/dependency/geometry/pin changes. Binding SPEC/ADR, R1A14 pipeline, R1A15 isolation, R1A16 validator and R1A17 simulation contracts remain authoritative; dated implementation restrictions yield to current owner authorization.

STEP150 review refinement: comparison success now prints comparedFiles (each verified relative filename,size,SHA256) in addition to revision/count/byteIdentical. This closes the required filename-level CI-log evidence gap without changing equality criteria or expected outputs. The exact-result regression checks these values. No serialization, hashes, artwork or policy relaxation.

STEP150 fresh precommit Windows gates: backend3896 PASS/21 expected skips in230.35s (18 Bash unavailable,1 POSIX/non-root,2 symlink privileges). Frontend586/25files and final assets118 PASS;discord22 in0.30s/brain28 in1.75s PASS. Locked installs,Ruff/format244backend+7deploy,strict mypy242,10 kept import contracts,exact OpenAPI/TypeScript/five fixture exports,ESLint,TypeScript,actual production build/guard,actionlint1.7.12 and separate ShellCheck groups PASS. Bash wrapper not executed. Final118 asset run occurred after per-file output refinement;fresh manifest/CLI comparison rehashes six actual files matching accepted goldens. Both simulation pins preserved by full pytest. STEP149 results above remain historical.

STEP150 precommit integrity PASS: exact16 reviewed Git-derived paths,108 resolving local links,LF,counters17 DONE/1 REVIEW/2 TODO and git diff --check. Complete152687-byte pre-STEP150 and149554-byte baseline worklog prefixes preserved. Main/R1A15/16/17 clean at verified heads;unrelated branches and accidentally advanced baseline branch unchanged. No generated/log/temp/secrets/credentials included. Stage only reviewed manifest. Commit/normal push/PR and actual native CI next;CI success not preclaimed. No merge/deployment/production activity.

### STEP 150 actual CI failure and narrow corrective review

Initial PR19 run38216578913 on head8a9d01dee2b4db579b0951785b5477034801213c (synthetic PR merge3b574d9d73dce92245c91d49cd3b1908ef9994a9) passed Ubuntu frontend, ShellCheck and both companions, but Windows art job114702621259 failed the effective Git-info-attributes regression. Comparison job114702847979 correctly ran and failed closed at the successful-producers prerequisite; no cross-OS PASS was claimed. Ubuntu uploaded atlas-linux artifact11732138920; no Windows artifact existed.

The same failure was reproduced locally with a Windows 8.3 short-path alias: path.resolve preserves aliases while Git reports the expanded long path. Added explicit Windows-only short-path regression failed before correction (Missing expected exception). Canonical filesystem identity via realpathSync.native on both roots now enters git check-attr correctly; the new regression passes. This extends STEP149 separator normalization to real filesystem aliases without weakening LFS or archive rules. Source art/goldens/runtime/pins remain untouched. The Windows-specific case is conditional, not a skipped Linux test: Windows assets119, Linux assets118 expected after this addition. Follow-up commit and native CI are required; final actual results belong in PR/final report.

STEP150 corrective validation PASS: final Windows assets119 (no skips),frontend586/25files,ESLint,TypeScript and actual production build/guard. Explicit short-path negative failed before canonical-path correction and now passes. Backend/companions/static/shell results above remain fresh STEP150 evidence;no backend/workflow changes followed those runs. Follow-up native CI required.
