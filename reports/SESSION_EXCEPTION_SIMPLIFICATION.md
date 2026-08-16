# Session Exception Simplification + Release Retention

Two independent cleanup policies, implemented and verified against real
(non-production) data. No production data mutated; no production deployed.

==================================================================
A. RELEASE RETENTION
==================================================================

## Policy

Keep only the newest `MESFLOW_RELEASE_RETENTION` (default **3**) deployable
application releases under `artifacts/releases/` — current / previous /
previous-2, sorted by build time (`release.json`'s timestamp, the moment a
version was frozen). Configurable via env var on the Deploy Agent:

```
MESFLOW_RELEASE_RETENTION=3
```

An older release is cleaned up **only if all of these are true**, each
checked and named explicitly (`deploy-agent/agent.py:_release_cleanup_blockers`):

- not `CURRENTLY_DEPLOYED` (compared against the real `current_file_version()`)
- not `ACTIVE_DEPLOYMENT_JOB` / `ACTIVE_ROLLBACK_TARGET` (an in-flight
  deploy job's `version`/`from_version`)
- not `ROLLBACK_TARGET_OF_LAST_DEPLOY` (the `from_version` of the most
  recent completed deploy — what a manual rollback would restore)
- not `BEING_PROMOTED` (an active `promote_test_job`)
- not `REFERENCED_BY_ACTIVE_AGENT_UPDATE_JOB`
- not `PROMOTION_IN_PROGRESS` (tracked in `promotion-state.json` but not
  yet both `local_pass` and `test_pass`)

Cleanup removes, per eligible version:

- the release ZIP (`MESFlow_<version>.deploy.zip` + `.sha256`)
- the local staging/bundle copy (`RELEASES_DIR/<version>`, what the Agent
  would deploy locally from — including staging copies whose
  `artifacts/releases` build record is already gone entirely, a real
  situation found live: 8 pre-existing orphaned staging copies going back
  to `65.8.44.24`)
- the corresponding Docker image, via a **targeted** `docker rmi
  mesflow-app:<version>` — never `docker system prune`, verified by test
  (`test_never_calls_docker_system_prune`) and by inspecting every real
  `docker` invocation made during the live run below

**Never removed**: `release.json` / `checksums.txt` / `image-info.json` /
`PROMOTION.json` / `BUILD_REPORT.md` for any version, ever — the
immutable-once build guard (`build-release.sh`) depends on `release.json`
existing forever to refuse a silent rebuild under the same version number.
**Database backups** (`DATA_DIR/mes_backups`) are a completely separate,
untouched mechanism — the cleanup code never references that path.

Cleanup runs **only** right after a verified success: `_record_local_deploy_result()`
when `local_pass` becomes `True`, and `_run_promote_test()` on `TEST_PASS`.
A manual trigger is also exposed (`POST /api/release-manager/cleanup-releases`,
admin-gated) for inspection/re-run, e.g. after lowering the retention value.

## A real bug this caught

`_run_capture()`'s actual return contract is `{"ok","exit_code","stdout",
"stderr"}`. The first draft of the Docker-image cleanup checked
`r.get("returncode")==0` — a key that doesn't exist — so every *successful*
`docker rmi` was silently misreported as an error (with an empty message).
Unit tests initially mocked the same wrong key, so they passed despite the
bug. Caught only by running the real function against the real Docker
daemon (see below); fixed to `r.get("ok")`, and the test mocks were
corrected to the real contract with a comment explaining why, so this
class of bug can't silently regress again.

## Tests

`deploy-agent/tests/test_release_retention_cleanup.py` — 13 tests, all
passing (100/100 across the whole deploy-agent suite, no regressions):
keeps current/previous/previous-2 and removes the rest; configurable
retention; never cleans a currently-deployed release; never cleans an
active rollback target (in-flight job, or the last completed deploy's
`from_version`); never cleans a release being promoted or mid-flight
through the promotion pipeline; only targeted `docker rmi`, never
`system prune`; a `docker rmi` failure is logged, not fatal; orphaned
staging with no build record is cleaned while an active orphan is still
protected; stray temp-upload leftovers older than 1h are removed, a fresh
one is kept; the report is persisted and readable; LOCAL_PASS triggers
cleanup, a failed local deploy does not.

## Real run, on the real DEV Agent (read-only dry-run first, then executed)

Dry-run (`_release_cleanup_candidates()` / `_release_cleanup_blockers()`,
no mutation) confirmed exactly what would happen before anything was
touched. Then executed for real via the actual `_cleanup_old_releases()`
function (run in a disposable container built from the same
`mesflow-deploy-agent:2.19.0` image with only `agent.py` swapped for the
updated source — the live Agent process itself was never restarted or
touched):

```
RELEASES KEPT:    65.8.44.67, 65.8.44.68, 65.8.44.69
RELEASES CLEANED: 65.8.44.64, 65.8.44.65, 65.8.44.66
  -> 3 release ZIPs removed (release.json/checksums.txt/image-info.json kept)
  -> 3 Docker images removed (mesflow-app:65.8.44.{64,65,66})
  -> 226,272,735 bytes freed

Orphaned local staging (RELEASES_DIR entries with no artifacts/releases
build record at all -- predate this policy):
  65.8.44.{24,26,27,30,33,37,48,62}
  -> 8 staging directories + 8 Docker images removed
  -> 54,289,838 bytes freed

TOTAL FREED: ~280 MB (release ZIPs + staging + 11 Docker images)
ERRORS: 0 (after the returncode/ok fix above)
```

Verified afterward, all real:

- `mesflow-app` (running 65.8.44.69) container `StartedAt` unchanged —
  never restarted.
- `mesflow-postgres` container `StartedAt` unchanged — never restarted.
- `DATA_DIR/mes_backups` entry count unchanged (27) — never touched.
- `65.8.44.67/68/69` release ZIPs and their `release.json`/`checksums.txt`
  still present and byte-identical.
- Idempotent re-run immediately after: `removed=0, errors=0` — nothing
  left to do, no false errors on the now-absent images.

**Observation, explicitly not acted on**: 13 further `mesflow-app:*`
Docker image tags (`.28,.29,.34,.38,.40,.41,.43,.44,.45,.47,.51,.52,.57`,
~333MB each, ~4.3GB total) exist with **no** corresponding
`artifacts/releases` or `RELEASES_DIR` record of any kind — they predate
this retention policy's tracking and this task's scope ("keep only 3
*deployable application releases*" refers to tracked releases, not a
blind Docker-tag sweep). Removing them would require a different,
riskier mechanism with none of the named safety checks above (no
`release.json` to check contamination/rollback/promotion state against).
Left untouched; flagged here for a possible future, explicitly-scoped
follow-up.

==================================================================
B. SESSION EXCEPTION REDESIGN
==================================================================

## READ-ONLY AUDIT FIRST (before any rule changes)

Ran the **original, unmodified** `session_exceptions()` against the real
DEV database, read-only (`inbox_only=False`, no writes):

```
TOTAL EXCEPTIONS: 26        UNIQUE SESSIONS: 25
QA_TEST (old label TEST_DATA): 20
TUTORIAL (old label TEST_DATA): 4        (2 detected only after the
                                           IN_PROGRESS-ordering fix below
                                           surfaced them correctly)
HISTORY_ONLY: 2
ACTION_REQUIRED / CONFIRMATION under the OLD code: 0
```

By exception_code: OPEN_TOO_LONG 21, OVERLAP 2, MISSING_STATION 1,
ZERO_QTY_LONG 1, INVALID_TIME 1. By workflow_status: NEW 22, IN_PROGRESS 2,
RESOLVED 1, IGNORED 1.

**Per-item detail for every row that was, or could plausibly become,
ACTION_REQUIRED / CONFIRMATION** (none existed under the old rules, but
these are the rows nearest that boundary and are exactly what the new
rules had to get right):

- **Session #76** — INVALID_TIME — employee Phạm Thu Dung (TUT-E04,
  Tutorial fixture), operation "QC — Tutorial", PO `TUT-PO-GUIDE-39`.
  `ended_at` before `started_at`. **Source: TUTORIAL_DEMO** (employee_no
  matches `TUT-%`). Impact: none — it is the built-in tutorial's own demo
  data, has an `IN_PROGRESS` review row seeded by the tutorial flow itself.
  Recommended action: none for a manager; visible only in
  History/Test filter.
- **Session #77** — OPEN_TOO_LONG — employee Nguyễn Văn An (TUT-E01,
  Tutorial fixture), operation "Chấn — Tutorial", PO `TUT-PO-GUIDE-39`,
  open since before this audit. **Source: TUTORIAL_DEMO**. Same as above:
  tutorial fixture, no real impact, hidden from the normal Inbox.
- Sessions #72 (ZERO_QTY_LONG) and #73 (MISSING_STATION) — both Tutorial
  fixtures, already `RESOLVED`/`IGNORED` by the tutorial's own scripted
  flow (`resolved_by: admin`, real note/resolution recorded) — correctly
  History-only, not active work.

**A real bug this audit caught**: sessions #76/#77 initially reappeared
under my *first* draft of the new rules with classification
`ACTION_REQUIRED`, because the "keep work a human already claimed
(`IN_PROGRESS`) visible" rule was checked *before* the QA/Tutorial source
check. Since the tutorial's own demo flow seeds an `IN_PROGRESS` review
row as part of its walkthrough, that made Tutorial fixture data leak into
the real manager Inbox — a direct violation of "QA and Tutorial exceptions
do not appear in normal manager Inbox by default." Fixed by reordering
`classify()` so source filtering is checked first, unconditionally, ahead
of every other rule except an actual human `RESOLVED`/`IGNORED` (which
must stay source-agnostic, since History shows everything with source as
a column). Verified against the real data above (`DEFAULT INBOX count: 0`
after the fix) and covered by the QA-hidden-from-Inbox tests.

No production data was mutated during the audit; `auto_ignore_session_exceptions()`
was run against DEV-only data as part of implementing/verifying the
feature (see AGENTS.md: DEV data mutation is allowed, production is not),
and found 0 matches in this dataset (no trivial-overlap mistakes currently
present) — it only ever *adds* an audit-trailed review row, never deletes
anything.

## AUTO_IGNORE RULES (deterministic, tested)

Only one rule, and only the one directly grounded in the task's own
example concept — no invented conditions:

- **Trivial overlap** (`exception_code=OVERLAP`): auto-ignored when either
  side of the overlapping pair has **zero total quantity** (good+defect+
  rework = 0) **and** lasted **under 5 minutes**. This is exactly
  "wrong_scan AND no production mutation occurred AND subsequent valid
  action happened" — a mis-scan that opened/overlapped a session for a
  couple of minutes with no output before the real session continued.
  Real overlaps with actual output or real duration stay `ACTION_REQUIRED`.
  Implementation: `overlap_flags` computes `secondary_evidence` for this
  in SQL from the two sessions' own quantity/duration; `classify()` maps
  it to `USER_MISTAKE`; `auto_ignore_session_exceptions()` (idempotent,
  `ON CONFLICT DO NOTHING`) writes a real `session_exception_reviews` row:
  `workflow_status=IGNORED, resolution=AUTO_IGNORED,
  resolved_by=system:auto_ignore`, with a deterministic Vietnamese note,
  called on every Inbox read.

**Evaluated and deliberately NOT auto-ignored** (per "do not guess" — no
deterministic, non-speculative self-correction signal exists for these in
the actual code/data):

- Wrong employee/operation scan corrected immediately, invalid QR then
  valid scan, cancelled accidental action before session creation: these
  never create a `work_sessions` row at all (the detector only ever reads
  `FROM work_sessions`), so by construction they can never become an
  exception in the first place — nothing to auto-ignore because nothing
  is ever detected. Verified by test
  (`test_accidental_action_with_no_session_created_produces_no_exception`).
- `ZERO_QTY_LONG` (temp zero/input mistake): the trigger condition itself
  requires 4+ hours closed with zero output — not "immediate," so no safe
  auto-ignore rule exists; stays `CONFIRMATION`.
- `MISSING_STATION` / uncorrected `INVALID_TIME`: the task explicitly
  lists "unresolved missing station" and "invalid time not corrected" as
  `ACTION_REQUIRED`. A case that *does* get corrected already naturally
  stops being detected (`is_active=false` → `AUTO_RECOVERED`/history) —
  no separate rule needed or invented.

## ACTION REQUIRED RULES

- `INVALID_TIME`, `MISSING_STATION`: unconditionally `ACTION_REQUIRED`
  while still detected (the task's own examples: "invalid time not
  corrected," "unresolved missing station").
- `OVERLAP`: `ACTION_REQUIRED` unless it matches the trivial-mistake
  auto-ignore rule above ("overlap affecting working time").
- `OPEN_TOO_LONG`: `ACTION_REQUIRED` only when the employee has **no**
  later activity at all (`secondary_evidence=false` — a real, evidenced
  computation: `EXISTS` a later `work_sessions` row for the same employee)
  — a genuinely orphaned session, matching the task's own example
  verbatim.
- An item already claimed (`workflow_status=IN_PROGRESS`) stays visible
  and actionable regardless of source-of-truth drift, so a reviewer is
  never stranded mid-review — except QA/Tutorial fixtures, which are
  filtered out unconditionally (see the bug fix above).

## CONFIRMATION RULES

- `ZERO_QTY_LONG`: always `CONFIRMATION` — strong evidence (4+ hours
  closed, zero output) but unsafe to auto-correct quantity/time without a
  human.
- `OPEN_TOO_LONG` **with** later same-employee activity
  (`secondary_evidence=true`): `CONFIRMATION`, not `ACTION_REQUIRED` —
  matches the task's own literal example ("Session may have been
  forgotten open") exactly: the employee clearly moved on to other work,
  so it's very likely just an unclosed session, but the true finish
  time/quantity aren't known, so nothing is auto-changed.

## DEDUPLICATION / REAPPEARANCE (the core detector fix)

Root cause found in the existing SQL: the occurrence-fingerprint bump
logic minted a brand-new, unreviewed fingerprint on **every** read once
any completed review existed — regardless of whether the underlying
session had actually changed again. Since a fresh fingerprint has no
matching review, it defaulted to `workflow_status=NEW`, so an
ignored/resolved item reappeared as brand-new manager work on the very
next page load.

Fix (`detected` CTE in `session_exceptions()`): only mint a new occurrence
fingerprint when `work_sessions.updated_at` is genuinely **after** the
completed review's `resolved_at` — real evidence the session row was
touched again since. Otherwise reuse the completed review's own exact
fingerprint, so it keeps resolving to its true RESOLVED/IGNORED state.
Verified this matches every real mutation path in the app
(`execution.py`'s `finish_session` / `adjust_session` / `update_session`
all explicitly stamp `updated_at=CURRENT_TIMESTAMP`) — so a genuine
correction always re-triggers correctly, while an untouched, already-
reviewed session never resurfaces.

- **Same condition, unchanged, already acknowledged** → does not
  reappear: tested directly
  (`test_ignored_condition_does_not_reappear_when_unchanged`, re-reads the
  Inbox 3× after an IGNORE with the underlying station still missing —
  stays out of the Inbox every time, stays `IGNORED` in History with the
  *same* fingerprint).
- **Genuinely changed/new condition** → a new occurrence appears, the old
  one stays resolved: preserved and re-verified
  (`test_missing_station_history_and_repeat_occurrence`).

## UI

The existing "Session cần xử lý" page (`session-exceptions.js`) already
implemented the required 3-tab structure exactly as specified —
`[ Cần xử lý ] [ Cần xác nhận ] [ Lịch sử ]`, default tab never shows all
anomalies, per-item card already answers Who (employee)/What
(`exception_message`, human-readable Vietnamese)/What's affected
(operation, PO, part)/What to do (`[Xử lý] [Bỏ qua] [Chi tiết]` via the
detail panel's guidance + action buttons), with technical codes
(`OPEN_TOO_LONG` etc.) shown as a secondary badge, not the headline. No
rewrite needed; targeted changes only:

- History's resolution text now distinguishes `AUTO_IGNORED` ("Tự động bỏ
  qua (không ảnh hưởng dữ liệu)", resolved-by shown as "Hệ thống (tự
  động)") from a manual `Bỏ qua có lý do`, so a manager can tell the two
  apart at a glance.
- `QA_TEST`/`TUTORIAL` filter dropdown (already present) continues to
  work against the new, split classification values.

## HISTORY

Backed by the existing `session_exception_reviews` table + the existing
History tab/filters (date, employee, PO, exception type, result, handler)
— already showed employee/PO/operation/session/exception
type/message/source/detected_at/resolved_at/resolved_by/resolution.
`AUTO_IGNORED` items now appear there with a clearly distinct label
(above), `resolved_by='system:auto_ignore'`.

## SOURCE FILTERING

`classify()` now returns `QA_TEST` / `TUTORIAL` (split out of the old
merged `TEST_DATA`) unconditionally ahead of every other rule (see the
bug fix above) — never appears in `view=inbox` (`inbox_only=True`, the
default), always available via `view=all`/`view=history` and the existing
data-source filter dropdown. Never deleted.

## IGNORE DOES NOT DELETE

Unchanged existing guarantee, re-verified: `update_session_exception_reviews()`
only ever `INSERT ... ON CONFLICT DO UPDATE`s a review row; the detected
exception evidence itself (`work_sessions`, `kiosk_events`) is never
touched or deleted by either a manual Ignore or the new
`auto_ignore_session_exceptions()`.

## TESTS

`tests/integration/test_session_exception_workflow.py` — 11 tests, all
passing:

- wrong scan corrected (trivial overlap) → `AUTO_IGNORED`, history only
  (`test_trivial_overlap_wrong_scan_is_auto_ignored_and_history_only`)
- accidental action, no session created → nothing detected at all
  (`test_accidental_action_with_no_session_created_produces_no_exception`)
- real orphan OPEN session → `ACTION_REQUIRED`
  (`test_real_orphan_open_session_is_action_required`)
- ambiguous forgotten finish → `CONFIRMATION`
  (`test_ambiguous_forgotten_finish_is_confirmation`)
- QA exception → hidden from normal Inbox, visible via `view=all`
  (`test_qa_missing_station_is_detected_and_traceable`,
  `test_open_too_long_stays_in_progress_after_session_is_closed`)
- Ignore → disappears from Inbox, remains in History
  (`test_ignore_requires_reason_and_remains_history`,
  `test_missing_station_history_and_repeat_occurrence`)
- Resolved → remains in History (same tests)
- Same ignored condition → does not reappear
  (`test_ignored_condition_does_not_reappear_when_unchanged`)
- Changed/new occurrence → appears again, old stays resolved
  (`test_missing_station_history_and_repeat_occurrence`)

Plus the 2 existing regression guards
(`tests/test_session_exception_regressions.py`) and 255 other pre-existing
unit tests, all still passing — no regressions. ("Invalid QR then valid
scan" maps to the same trivial-overlap mechanism above, since neither the
invalid attempt nor the correction leaves a distinguishable session-level
signal beyond "short, zero-output, superseded by a valid action" — see
the AUTO_IGNORE section for why this wasn't split into a separate,
speculative rule.)

==================================================================
RESULT
==================================================================

```
OLD ACTIVE COUNT: 0
NEW ACTION_REQUIRED: 0
NEW CONFIRMATION: 0
AUTO_IGNORED: 0 (0 rows in the real dataset currently match the trivial-
                 overlap rule; mechanism verified live via
                 auto_ignore_session_exceptions() and by dedicated test)
HISTORY: 2 (session #72 RESOLVED, session #73 IGNORED -- both pre-existing,
            untouched by this task)
[QA_TEST: 20, TUTORIAL: 4 -- correctly hidden from the default Inbox]

AUTO_IGNORE RULES:
  - OVERLAP + zero quantity on either side + <5 min duration -> AUTO_IGNORED

ACTION REQUIRED RULES:
  - INVALID_TIME, MISSING_STATION: always, while still detected
  - OVERLAP: always, unless it matches the AUTO_IGNORE rule
  - OPEN_TOO_LONG: only when the employee has no later activity at all
    (genuine orphan)
  - Anything already claimed (IN_PROGRESS) stays visible until finished,
    except QA/Tutorial fixtures (source filtering wins)

CONFIRMATION RULES:
  - ZERO_QTY_LONG: always
  - OPEN_TOO_LONG: when the employee has later activity (likely forgot to
    close, but unsafe to auto-correct)

UI: existing 3-tab "Session cần xử lý" page already matched the spec;
    added AUTO_IGNORED-vs-manual-IGNORED distinction in History text.
HISTORY: existing session_exception_reviews-backed History tab/filters;
    now also carries AUTO_IGNORED entries with resolved_by=system:auto_ignore.
DEDUPLICATION: fixed the occurrence-fingerprint bump to require real
    evidence (work_sessions.updated_at after the review's resolved_at)
    instead of bumping unconditionally on every read; verified against
    both the "must not reappear" and "must still detect a genuine repeat"
    cases.

RELEASE RETENTION: MESFLOW_RELEASE_RETENTION=3 (configurable)
RELEASES KEPT: 65.8.44.67, 65.8.44.68, 65.8.44.69
RELEASES CLEANED: 65.8.44.64, 65.8.44.65, 65.8.44.66
  (+ 8 pre-existing orphaned local staging copies/images with no build
  record at all, 65.8.44.{24,26,27,30,33,37,48,62})
  ~280 MB freed, 11 Docker images removed via targeted `docker rmi`,
  0 `docker system prune` calls, 0 errors, database backups untouched
  (27 entries before and after)

PRODUCTION DATA MUTATED: NO
PRODUCTION DEPLOYED: NO
```

## NEED_USER / follow-ups (not blocking)

- This report reflects **code changes verified on DEV** (real DEV
  Postgres data, real Docker daemon, real release artifacts) — no new
  MESFlow or Deploy Agent version was built/packaged/deployed as part of
  this task, since the task did not ask for a new release and explicitly
  requires `PRODUCTION DEPLOYED: NO`. If this work should ship as an
  actual new release, that's a natural next step (`VERSION.txt` bump +
  `scripts/build-release.sh` + the existing Build Once/Promote Same
  Artifact flow already in place).
- The ~4.3GB of untracked, pre-existing `mesflow-app:*` Docker images
  (listed above) are outside this policy's scope by design; flagged for a
  possible separate, explicitly-scoped follow-up if wanted.
