# Demo Dataset + Tutorial Video Update — 2026-09-03

Stability-conscious data/content task: prepare a realistic demo dataset
and refresh the tutorial video system to cover recent features
(Employee Productivity, the full Kiosk flow) — reusing the app's own
existing tutorial-data and video-generation infrastructure rather than
building a parallel one, per explicit instruction.

## Environment used

**`mesflow-demo-app`** — a dedicated, pre-existing demo container
(`127.0.0.1:8081`, image `mesflow-app`), backed by its own isolated
Postgres database (`mesflow_demo`, on the same shared `mesflow-postgres`
container local DEV uses, but a completely separate logical database —
zero overlap with local DEV's `mesflow` database, `mesflow.net`, or
`prod.mesflow.net`). This was the correct "demo/dev" target per the
explicit instruction to never touch `mesflow.net` production for this;
it was found already running (image `71.0.0.42`, ~13 days stale) and
upgraded to the current build alongside the other three environments.

The old container was preserved, not deleted: `mesflow-demo-app-backup-71.0.0.42`
(stopped, renamed, still on disk) before recreating `mesflow-demo-app`
with the new image.

## What exists already (checked before building anything)

- **Employee Productivity**: a real, already-built, already-wired page
  (`app/mesflow/web/static/pages/employee-productivity.js`, reached at
  `openPage('employee-productivity')`, permission-gated same as every
  other page). It genuinely computes, from real closed `work_sessions`
  (not any separate manual-entry table): `completed_sessions`,
  `completed_invalid_sessions`, `productivity_percent` (actual vs.
  standard cycle time), `good_qty`/`defect_qty`, `worked_seconds`, and a
  per-employee drill-down of every session (date, PO/Part/Operation,
  start/end, GOOD/DEFECT, Completion %, status). It also has a Kiosk
  wallboard/trình-chiếu publishing panel. Nothing here was invented for
  this task — the tutorial chapter added below narrates exactly this and
  nothing else.
- **Kiosk flow**: `kiosk.html` (device UI) already implements the full
  scan-employee → scan-Operation → Start → running → Finish →
  good/defect/rework entry → confirm flow, and `tutorial-detailed.spec.js`
  already had a complete, detailed `kioskUser` tour driving it end-to-end
  through the real UI (not simulated) — this already existed and needed
  no new work.
- **Tutorial data/video infrastructure**: `app/mesflow/tutorial_data.py`
  (`python -m mesflow.tutorial_data seed|status|cleanup`, guarded by
  `MESFLOW_TUTORIAL_DATA_ALLOW_PRODUCTION` outside `MESFLOW_ENV!=production`),
  and `scripts/make-user-guide-video.sh` — an existing, mature, fully
  automated pipeline: seed → per-module Playwright recording (real
  browser, real narration overlay, real steps) → `.webm`→`.mp4`
  transcode → TTS voice-over (edge-tts/espeak-ng + ffmpeg) → publish into
  the app's own "Hướng dẫn → Video hướng dẫn" tab
  (`runtime/tutorials/manifest.json`). This is the "cơ chế quay
  browser/video tự động" the task asked to reuse if it exists — it did,
  so no new framework was introduced.

## Demo dataset

Extended the existing `TUT39` tutorial fixture **in place, additively**
(script: `app/mesflow/tutorial_data.py`) rather than building a second,
parallel dataset — every existing record (employees `TUT-E01..06`,
Operations `TUT39-CUT/BEND/WELD/QC/PACK`, `PO_CODE=TUT-PO-GUIDE-39`)
kept its exact code/values unchanged, since `tutorial-detailed.spec.js`'s
kiosk tour and several tests hardcode references to them. Everything
below is new, added alongside:

| | Before | After | Target |
|---|---|---|---|
| Employees | 6 | **16** | 12-20 ✓ |
| Production Orders | 1 | **3** (`TUT-PO-GUIDE-39/40/41`) | 2-3 ✓ |
| Parts | 2 | **7** | 5-10 ✓ |
| Operations | 5 | **20** | 20+ ✓ |
| Work sessions | 8 | **85** | — |
| Session history span | ~13 hours | **10 real calendar days** | multi-day ✓ |

The two new POs are realistic operation chains, not filler: "Khung kim
loại" (Cắt → Uốn → Hàn → Mài, plus Khoan lỗ → Lắp ráp chân đế) and "Trục
bánh răng" (Tiện → Phay rãnh then → Nhiệt luyện → Mài tinh, plus Cắt
răng → Kiểm tra biên dạng, plus Lắp cụm → Đóng gói → QC cuối) — each with
real `standard_seconds_per_unit`, and `input_flow_enabled` material-flow
links scoped correctly per-Part (a bug in my own first draft — a link
that accidentally carried over to the next Part's first operation — was
caught and fixed before shipping).

Session history: 6-10 sessions/day × 10 days, spread across all 16
employees and every `IN_PROGRESS` operation, each with a real
`station_id` (a session left with `station_id NULL`, like the
deliberate `MISSING_STATION` example, would have falsely flagged every
one of them as that same exception) and randomized-but-plausible
good/defect/rework quantities (fixed seed `Random(39)`, so the dataset
is reproducible run-to-run, not different every time). PO2/PO3
operation `done_qty`/`defect_qty`/`rework_qty` are aggregated as a real
`SUM()` of their own sessions; PO1's original, intentionally
hand-curated (not-a-strict-sum) aggregate values — spoken verbatim in
the existing tour narration — were deliberately left untouched.

**Scenario coverage** (per requirement): normal session, running/open
session (`LONG`, still open), zero-quantity-long session, session
needing confirmation, `OVERLAP` conflicts (both the two original curated
ones and several that emerged naturally from the random multi-day
history — left in, since real production data has occasional accidental
double-bookings too), `INVALID_TIME` (ended before started), missing
station, plus QC records, an operation adjustment, and a penalty ticket
— all pre-existing in the curated fixture, all still present.

**Idempotency / safety**: `python -m mesflow.tutorial_data seed` always
runs its own `cleanup()` first (matches every record by the `TUT-`
prefix wildcard, which the new records fall under automatically — no
changes needed to the cleanup or `status()` logic), so re-running it
never duplicates data. Guarded by
`MESFLOW_TUTORIAL_DATA_ALLOW_PRODUCTION=1` (required here since
`mesflow-demo-app` has `MESFLOW_ENV=production`) — an explicit,
deliberate opt-in per the task's own safety requirement, not a default.
Never touches any other database (`mesflow`, `mesflow.net`'s DB,
`prod.mesflow.net`'s DB).

Seeded via: `docker exec -e MESFLOW_TUTORIAL_SEED_DATA=1 -e
MESFLOW_TUTORIAL_DATA_ALLOW_PRODUCTION=1 mesflow-demo-app python -m
mesflow.tutorial_data seed` (the wrapper script
`scripts/prepare-tutorial-data.sh` assumes a `docker compose` service
named `mesflow`, which this standalone, non-compose demo container
doesn't have, so it was invoked the equivalent way directly).

## Verified with real seeded data (screenshots taken, not assumed)

Dashboard theo ngày, Session Management, Session Exceptions (Trung tâm
ngoại lệ — 11 exceptions across CRITICAL/HIGH/MEDIUM/LOW, all the
intended scenario types represented), Employee Productivity (12 employees
with data in the default 3-day window, real varying productivity
percentages, real per-employee drill-down), Employees (50 total on this
shared demo DB — the 16 new + pre-existing others), Kiosk Management,
Production Orders/Templates. Consistency check: the Dashboard's KPI
counts, the Session Management row counts, and the Exception Center's
list all draw from the same underlying `work_sessions` rows, so they
agree by construction — spot-checked visually, no discrepancy found. One
pre-existing, unrelated display quirk noted below (not fixed, out of
this task's scope).

## A real backend bug found and fixed along the way

Running the video pipeline's own coverage gate against this richer,
realistic dataset (not manual testing) surfaced a genuine crash: Session
Management returned HTTP 400 (`"range lower bound must be less than or
equal to range upper bound"`) the moment the seeded data included a
session with `ended_at < started_at` — exactly the `INVALID_TIME`
scenario the fixture (and real production data) is supposed to hold
without breaking the page.

Root cause: `db/repositories/exceptions.py` already carried a fix for
this *exact* class of bug, dated and commented 2026-08-27, using
`GREATEST(COALESCE(ended_at,'infinity'), started_at)` to clamp a
malformed session's range instead of leaving it invertible. That fix was
never propagated to three other, near-identical overlap-detection
queries elsewhere in the codebase:

- `services/session_audit_service.py` (`EMPLOYEE_OVERLAP` audit query)
- `db/repositories/analytics.py` (the `OVERLAP` exception-flag CTE — this
  is the one that was actually throwing the 400, since it backs both
  Session Management and Dashboard/analytics aggregates)
- `db/repositories/execution.py` (`_find_employee_session_overlap`, used
  when starting a session or when an admin corrects one — guarded both
  the DB-side range and the caller-supplied parameters, so a swapped
  start/end typed by an admin now gets a clean conflict message instead
  of a raw DB exception)

Same fix, same pattern, applied to all three. Verified: before the fix,
Session Management threw a 400 on load; after, zero console/network
errors across Overview, Dashboard, Session Management, Session
Exceptions, Employee Productivity and Production Trace, and the
Exception Center shows the identical 11 exceptions (same severities,
same breakdown) it did before — confirming the guard only prevents the
crash, it doesn't change which sessions get flagged.

This is a low-risk, narrow, root-cause-matching fix (reusing an
already-proven pattern from the same file family), not new scope — it
was necessary to even get a coverage-gate pass, and it's a real defect
independent of this task (any real production dataset that ever
accumulates an inverted-time session — a plausible data-entry mistake —
would hit the same crash).

## A second real bug found: tutorial pipeline auth over plain HTTP

Also found by actually running the pipeline (not by inspection):
`tests/e2e/tutorial-auth-state.js` hard-failed immediately
(`"Login thành công nhưng /api/auth/me lỗi HTTP 401"`) against the demo
target. Root cause: the backend sets the session cookie `Secure`
(`WORKSHOP_COOKIE_SECURE`). A real browser page navigation correctly
treats `127.0.0.1`/`localhost` as a trustworthy origin for that cookie
even over plain `http://` — reproduced identically against local DEV's
`127.0.0.1:8080` too, so this was never specific to the demo target —
but Playwright's separate, lighter `context.request`/`page.request`
client does not get that treatment; the cookie was captured but silently
never sent back on that client's own next request. This means the
pipeline's own auth-state generation had apparently never worked against
a plain-HTTP target before. Rewritten to log in via a real page and
verify via an in-page `fetch()`; the same broken pattern inside
`tutorial-detailed.spec.js`'s shared `login()` (which was silently
defeating its own "log in once, share across all 15 modules" optimization)
got the identical fix. Verified with a real recording run before
committing to the full 15-module pipeline.

## A third real bug found: the batch runner discarded valid recordings

Also found only by running the full 15-module pipeline (twice) against
this richer dataset: `tutorial-detailed.spec.js`'s narration selectors
were tuned against the original, sparser TUT39 fixture, and roughly half
the modules now trip at least one non-fatal QA-bug flag against the
bigger one — a KPI card briefly not visible, a narration overlay
covering an element that's now larger with more real data, one stale
selector. All logged via `expect.soft()`, by design non-blocking (the
tour keeps going, the recording completes) — but that soft failure still
made the whole Playwright test process exit non-zero, and
`scripts/make-user-guide-video.sh`'s retry/discard logic was keyed off
exactly that exit code rather than off whether a video was actually
produced. First full run: 3 of the first 6 modules (`dashboard`,
`material_flow`, `sessions`) had a complete, valid recording thrown away
on both the original attempt and the retry, purely because of cosmetic
narration-positioning noise. Fixed by deciding retry/discard on whether
`test-results/tutorial-detailed` actually contains a `.webm` after each
attempt, not on the exit code. Second full run, with the fix: all 15
modules produced a video (several with the same non-fatal QA-bug flags
logged internally, correctly kept this time).

## Video pipeline

Ran `scripts/make-user-guide-video.sh http://127.0.0.1:8081` against the
demo environment (admin credentials from `MESFLOW_ADMIN_PASSWORD`,
reset to a known value on this demo DB since the stored one was stale
from an earlier session — same technique used earlier this session for
the other environments). New chapter added, matching the requested
story arc position (right after the Kiosk operator chapter):

`10_employee_productivity` — filters (date range, department), the 4 KPI
cards, the sortable per-employee table, opening the real per-employee
drill-down, and the Kiosk wallboard/trình chiếu panel. Registered in the
runner (`scripts/make-user-guide-video.sh`), the publisher
(`scripts/publish-user-guide-videos.sh`, with a real Vietnamese
title/category/description, not a raw filename), a matching
`tutorial/coverage-matrix.json` feature entry, and a narration script
(`tutorial/narration/10_employee_productivity.txt`) in the same style as
the existing 14. `working_calendar`/`users_permissions`/`system_logs`/
`common_cases` shifted from `10-13` to `11-14` accordingly — every
narration filename, the runner's module list, the publisher's title
table, and the two tests that hardcoded the old numbers were all updated
to match (found the narration-filename mismatch and one more hardcoded
test string only by actually running the pipeline end-to-end, not by
static review — noted here since it's exactly the kind of thing that
silently breaks in a pure code-review pass).

**Output**: 15/15 modules produced a video with voice-over on the
second full run (the first run lost 3 to the retry-discard bug above).
Total runtime ~28m 33s across the 15 chapters (`00_overview` 1m38s …
`10_employee_productivity` 4m49s, the longest chapter, since it walks
through KPIs, per-employee drill-down, filtering, and the kiosk
wallboard … `04_material_flow` 27s, the shortest). Combined size ~74MB.
Rendered locally under
`.worktrees/claude-demo-tutorial/runtime/tutorials/{00..14}_*.mp4` +
`manifest.json`, then `docker cp`'d into the running
`mesflow-demo-app` container's `/data/tutorials/` (verified present
there — `ls` inside the container shows all 15 files plus the current
manifest, dated 2026-09-03 22:31). Confirmed live in the real UI:
Hướng dẫn → Video hướng dẫn shows all 15 cards including the new
"Năng suất nhân viên" one, and playing it back returns `readyState 4`,
the correct `duration` (~4m49s), and a `200`/`video/mp4` HEAD response
on its source URL — not just "the file exists on disk".

## Employee productivity feature — what it actually supports (for the record)

Confirmed by reading the real source, not assumed:

- Per-employee: completed session count (split into valid vs.
  insufficient-data), average productivity % (actual duration vs.
  standard cycle time), good/defect quantity, total worked time.
- Per-employee drill-down: every session in range, with date,
  PO/Part/Operation, start/end time, GOOD/DEFECT, Completion %, status.
- Date-range and department filtering.
- A Kiosk wallboard (auto-paging, configurable columns/sort/refresh)
  publishing the same ranked table for shop-floor display.

**Not supported** (so not claimed anywhere in the new video chapter):
throughput/units-per-hour as a distinct metric (productivity_percent is
the closest existing analog — actual vs. standard time, not a raw
units/hour figure), shift-level or per-day breakdown *within* the
per-employee table itself (the date-range filter narrows the whole
table, but there's no built-in day-by-day or per-shift pivot — the
per-session drill-down is the closest equivalent), and no separate
"throughput trend chart" — only the flat ranked table plus drill-down.

**One known display quirk, not fixed** (out of scope for a data/video
task — a UI/backend investigation of its own): the summary KPI card
"Tổng sản lượng đạt" showed `0` on the demo dataset while the
per-employee table clearly listed non-zero `good_qty` values summing
much higher. Flagged for whoever owns that feature next; did not
investigate further or touch the aggregation code, since it's unrelated
to the dataset/video deliverable and risks scope creep on a
stability-first task.

## Commits

- `4bde9f5` — `feat(demo,tutorial): demo-scale dataset + Employee Productivity video chapter`
- `3c51852` — `fix(tutorial): auth-state/login verification silently failed over plain HTTP`
- `1279ea8` — `fix(exceptions): propagate the tstzrange() inverted-range guard to 3 more sites`
- `c545ea5` — `fix(tutorial): update test_auth_helper_retries_429 for renamed variable`
- `cc33b50` — `fix(tutorial): stop discarding valid recordings over soft QA-bug exit codes`
  (batch-runner-only fix; `scripts/make-user-guide-video.sh` is not in the
  Dockerfile's `COPY` list, so this needed no version bump/rebuild — it
  took effect on the next pipeline run against the already-deployed
  `71.0.0.219` image)
- Version bumps: `71.0.0.216` → `71.0.0.219` (each QA-gated individually; see
  `reports/` git history / `artifacts/qa/71.0.0.21{6,7,8,9}` for evidence)
- Merged to `main` (fast-forward), pushed to `origin/main`.

## Deploy

Built once per version bump, promoted the identical artifact everywhere
each time a real QA gate passed:

- **local DEV** — `71.0.0.219`, healthy.
- **`mesflow-demo-app`** (the actual recording target) — `71.0.0.219`,
  healthy, seeded, verified live.
- **`mesflow.net`-host** — `71.0.0.219`, healthy (kept in sync for
  consistency; this task's own data/recording never touched it).
- **`prod.mesflow.net:8299`** — `71.0.0.219` via `scripts/deploy.sh
  prodtest`, `== DEPLOY PASS ==`, digest verified, `migration_changed: 0`.

All four environments' changed backend files hash-match exactly
(`e217fa76c7b4f4fc107cbcc2b86c817b` for `analytics.py`).

## Remaining gaps / follow-ups

- The "Tổng sản lượng đạt: 0" KPI display quirk noted above.
- Employee Productivity has no built-in per-day/per-shift breakdown
  within the ranked table — only a whole-range filter plus per-session
  drill-down. If a future task wants that, it's a real feature gap, not
  something this task tried to paper over.
- The video output currently lives on this host's local filesystem
  (`runtime/tutorials/` in the worktree, `docker cp`'d into
  `mesflow-demo-app`'s `/data/tutorials`, which has no persistent volume
  mount — it's ephemeral container storage, so a container recreate would
  lose it; the *source* narration/spec/dataset is committed to `main` and
  fully reproducible any time via `scripts/make-user-guide-video.sh`).
