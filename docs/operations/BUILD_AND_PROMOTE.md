# Build Once, Promote Same Artifact

Consolidates `BUILD_AND_DEPLOY.md`, `BUILD_PROMOTE_WORKFLOW.md`,
`IMAGE_RELEASE_CONTRACT.md` and `DEV_TO_PRODUCTION_TEST.md` into one
authoritative flow. Those files remain for historical detail; this is the
one to follow.

## Flow

```
WORKSPACE
   │  scripts/build-release.sh  (or ./scripts/build-release.sh from repo root)
   ▼
immutable Docker image  (mesflow-app:<version>, tagged AND content-addressed by digest)
   │
   ▼
release ZIP under artifacts/releases/<version>/
   │  freezes: version, source_commit, package sha256 (checksums.txt),
   │           image_digest, expected_schema_revision (release.json)
   ▼
DEPLOY LOCAL          scripts/deploy-local.sh  (or Release Manager "Deploy Local" button)
   │  --no-build, deploys the exact image by digest
   ▼
LOCAL_PASS            health + /api/system/ready + schema check + browser smoke
   │
   ▼
PROMOTE SAME ARTIFACT  scripts/promote-test.sh
   │  uploads the SAME zip (sha256 verified client-side before upload),
   │  target Agent deploys --no-build
   ▼
PRODUCTION TEST
   │
   ▼
TEST_PASS             health + schema + browser smoke on the test host
   │
   ▼
PROMOTE SAME ARTIFACT  (Release Manager "Promote Production" — human click only)
   │
   ▼
PRODUCTION            requires explicit human approval every time
```

**Never rebuild between environments.** The image built on DEV is the exact
byte-for-byte image (verified by digest) that reaches Production Test and
Production. If a rebuild happens between environments, that's a different
artifact and the promotion chain is broken — do not paper over it by
approving anyway.

## Server roles

| Role | `SERVER_ROLE` | `MESFLOW_BUILD_ENABLED` | Needs source/toolchain? |
|---|---|---|---|
| DEV | `DEV` | `true` | Yes — workspace bind-mounted, builds images |
| Production Test | `PRODUCTION_TEST` | `false` | No — receives artifacts only |
| Production | `PRODUCTION` | `false` | No — receives artifacts only |

Production Test and Production must never require MESFlow source, a
compiler/build toolchain, Node build environment, Arduino CLI, or a
frontend source tree. If a promote step tries to build on those hosts,
that is a bug — stop and report it, don't work around it.

## Release metadata that must always be present

Every release under `artifacts/releases/<version>/` carries `release.json`
with: `version`, `source_commit`, `built_at`, `image`, `image_digest`,
`package_sha256` (also in `checksums.txt`), `expected_schema_revision`. Do
not infer schema from the app version string — read the actual applied
Alembic revision from the running database and compare it to
`expected_schema_revision`. `PROMOTION.json` tracks the promotion history:
`BUILT → LOCAL_PASS → TEST_PASS → PRODUCTION_PASS`.

## Release Manager UI/API (deploy-agent, Agent v2.17.1+)

| Button | Endpoint | Effect |
|---|---|---|
| Build Release | `POST /api/release-manager/build` | Runs `scripts/build-release.sh` on DEV. Rejects if `MESFLOW_BUILD_ENABLED=0`. |
| Deploy Local | `POST /api/release-manager/deploy-local` | `--no-build` deploy of the latest (or requested) built version. Refuses contaminated releases. |
| Promote Production Test | `POST /api/release-manager/promote-test` | Requires LOCAL_PASS for the exact version; refuses contaminated releases; requires `MESFLOW_PRODUCTION_TEST_AGENT_URL`/`_USER`/`_PASSWORD` configured on this Agent; uploads the same ZIP, triggers `--no-build` on the target, polls to completion, records TEST_PASS. |
| Promote Production | `POST /api/release-manager/promote-production` | Re-verifies the full gate on every call (LOCAL_PASS + TEST_PASS + zip sha + image digest + schema PASS + not contaminated). Returns 403 unless `MESFLOW_PRODUCTION_PROMOTE_ENABLED=1` is set on this Agent **and** the request body has `{"confirm": true}`. Even then, returns 501 — this Agent build does not execute a production deploy. Wiring only. |

LOCAL_PASS is computed after every image-release deploy from real evidence,
not the deploy job's return code: the running container's exact **image
id** (not tag) must match the frozen release, the applied Alembic head
(`/api/system/ready`'s `migration_head` — never the `schema_version` field,
which is an app-defined label that happens to look like a version string;
see AGENTS.md) must equal the release's `schema_revision`, and an HTTP
smoke check against `/login` must succeed. All three are visible in the UI
under Pipeline status, with the exact reason shown whenever a button is
disabled.

## Immutable release protection (fixed)

`65.8.44.65` was contaminated: two different builds were produced under the
same version number before this guard existed (`docker images` showed the
tag pointing at a different digest than what was actually running — see
`reports/RELEASE_MANAGER_BUILD_ONCE.md` for the full incident). It is marked
permanently via `artifacts/releases/65.8.44.65/CONTAMINATED.json` (a new
file — the frozen `release.json`/`checksums.txt`/deploy ZIP were never
touched) and is refused by Deploy Local / Promote Test / Promote Production.
It was never rebuilt; the next version is `65.8.44.66`.

`mesflow/scripts/build-release.sh` now enforces, before doing anything else:

1. **A version may be built only once.** If
   `artifacts/releases/<version>/release.json` already exists, the build is
   refused (`VERSION_ALREADY_RELEASED`) — a rebuild requires bumping
   `VERSION.txt`.
2. **The Docker tag may not silently move.** The build always lands in a
   disposable local tag first; if `mesflow-app:<version>` already exists
   and its image id differs from what was just built, the build is refused
   (`IMAGE_TAG_CONTAMINATED`) rather than retagging over it.
3. `release.json` / `PROMOTION.json` / `checksums.txt` / the deploy ZIP /
   `image-info.json` are only ever written into a version's directory once,
   as a consequence of (1) — they are never overwritten.

The Deploy Agent adds a second, independent layer: `_release_contamination()`
checks both an explicit `CONTAMINATED.json` marker and, live, whether the
Docker tag recorded in a release's `release.json` still points at the
frozen image id — so tag drift is caught automatically even without a
marker, for any future version. A contaminated release is refused by Deploy
Local and Promote Test regardless of what the UI shows.

Promotion identifies a release by **version + source_commit + ZIP SHA256 +
image id/digest**, never by Docker tag alone — see `_artifact_for_release()`
and `_record_local_deploy_result()` in `deploy-agent/agent.py`.

## Retention (enforced)

Implemented in `deploy-agent/agent.py` (`_cleanup_old_releases()` and
related `_release_cleanup_*` helpers) — see
`reports/SESSION_EXCEPTION_SIMPLIFICATION.md` ("RELEASE RETENTION") for the
full writeup and a real, live run.

Keeps the newest `MESFLOW_RELEASE_RETENTION` releases (default **3**:
current + previous + previous-2), configurable via env var. An older
release is cleaned only if it is not currently deployed, not an active
rollback target (an in-flight deploy's `from_version`, or the last
completed deploy's `from_version`), not part of an active deployment, not
being promoted, and not referenced by an active job — every check is
named explicitly in `_release_cleanup_blockers()`. Cleanup removes the
release ZIP, the local staging/bundle copy, and the corresponding Docker
image via a **targeted** `docker rmi <exact tag>` — never `docker system
prune`. `release.json` / `checksums.txt` / `image-info.json` /
`PROMOTION.json` are kept forever (the immutable-once build guard depends
on `release.json` existing). Database backups
(`DATA_DIR/mes_backups`) are a separate, untouched mechanism.

Runs automatically only right after a verified success — `LOCAL_PASS` or
`TEST_PASS` — never on a failed or unverified deploy/promotion. A manual
trigger is also available: `POST /api/release-manager/cleanup-releases`
(admin-gated), e.g. to re-run after lowering the retention value; `GET`
returns the last report. Covered by 13 tests in
`deploy-agent/tests/test_release_retention_cleanup.py`.
