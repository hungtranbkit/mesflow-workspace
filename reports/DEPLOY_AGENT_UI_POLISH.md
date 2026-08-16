# Deploy Agent — UI/UX Polish Pass

Date: 2026-08-14
Deploy Agent version: 2.23.9-docker-runtime → 2.23.10-docker-runtime (source tree only; not deployed)
Scope: **UI/UX polish only**, per the task brief — no new major features, no backend business-logic
changes, no database changes, no production mutation. Method: real local DEV Agent instance (isolated
`WORKSHOP_AGENT_HOME`), a second real spawned `agent.py` acting as a registered TEST fleet server (so
Fleet/Incidents pages render real, non-empty data), MESFlow/QA Center pointed at the real read-only
host-exposed health endpoints for a realistic Overview. Real Chromium via Playwright throughout — every
finding and every fix below was verified against the actual rendered page, not assumed from source.

---

## BEFORE AUDIT

Full audit: `reports/DEPLOY_AGENT_UI_AUDIT.md` (19 screens, 1920×1080, captured before any code change).
Headline findings: Fleet/Backup pages unreachable from the persistent sidebar; long technical strings
(40–100 char hashes) printed in full and duplicated; no shared status-badge/button system (4 different
visual treatments for the same "healthy/running" concept); Release & Deploy's pipeline state shown as a
flat wrap of 6 English ALL-CAPS pills instead of a visual pipeline; a stale "Workshop Update Agent"
product name on the login page; a raw backend error code (`MESFLOW_UNAVAILABLE`) surfaced directly in the
UI; English section headings mixed into an otherwise-Vietnamese page; large dead space on several pages.
One claim from the initial screenshot read (Diagnostics/Docker "action column clipped") was investigated
with real DOM measurements and found to be a **false positive** — corrected in the audit doc before any
fix was attempted, per the task's "inspect before editing" instruction.

## DESIGN SYSTEM

Extended `static/css/agent.css` (the one stylesheet already shared by `dashboard.html`/`ops.html`/
`kiosk.html`/`index.html`) with named tokens layered on top of the existing `--ops-*` palette (kept for
backward compatibility, nothing already using them broke):

```
--space-1..6 (4/8/12/16/20/24px)   --radius-sm/md (6/10px)
--surface / --surface-muted        --text-primary/secondary/muted
--status-success/warning/danger/info (aliased to the existing --ops-good/warn/bad/blue values)
```

New shared components added once, reused everywhere:
- `.ops-hash` + `copyHashText()` / `copyHash()` — truncated technical identifier (`abcd1234…ef567890`)
  with a Copy button; the full value always lives in `data-full`, never displayed in full unless copied.
- `.dotstatus` — compact `● text` status indicator (`ok`/`warn`/`crit`/`muted` tones) replacing four
  different ad-hoc status treatments across Docker/Services with one.
- `.ops-bar` — thin resource-usage bar (CPU/RAM/Disk), tone-colored at ≥75%/≥90%.
- `.ops-pipeline` / `.ops-pipeline-stage` — the BUILD→LOCAL→TEST→PRODUCTION connected-stage visual.
- `.btn` / `.btn-primary` / `.btn-danger` — base button chrome for pages that had none of their own
  (`dashboard.html`, `kiosk.html`); `ops.html`/`index.html` keep their own already-adequate button CSS
  untouched (see "CSS duplication removed" below for what was and wasn't consolidated).
- `.ops-empty-row` — consistent empty-table-row styling.

## SIDEBAR

Real gap found and fixed: **Servers/Fleet and Backup/DB/Storage existed only inside `ops.html`'s own
internal tab strip — the persistent left sidebar had no link to either**, so a user landing on Overview or
Release & Deploy had no visible path to them. Added both to `_operations_shell_start.html` (Servers/Fleet
under VẬN HÀNH, Backup/DB/Storage under HỆ THỐNG), so the sidebar and the internal tab strip now agree.
No other sidebar structure changed — active-state highlighting, grouping, and icon-free text-row style
were already consistent and are preserved.

## HEADER

Already compact and correct (role/version/connection-status/logout on the right, page title on the left)
— no changes made; confirmed via the "before" audit as one of the pages needing no work.

## OVERVIEW

- Added `.ops-bar` resource bars under CPU/RAM/Disk (previously bare percentages with no visual scale).
- Filled the ~450px dead space below the fold with two new compact panels — **Fleet · Servers đã đăng ký**
  and **Backup / Database** — both driven by the *existing* `/api/fleet/summary` and `/api/ops/storage`
  APIs (no new backend logic), each linking through to its full page. This simultaneously fixes the
  sidebar-navigation gap for users who land on Overview first.

## RELEASE & DEPLOY

The heaviest page, given the most work per the task's explicit "make this the visual center" instruction:

- **New BUILD→LOCAL→TEST→PRODUCTION pipeline visual** (`.ops-pipeline`), replacing the flat text list
  (`Build: PASS` / `Local: NOT_TESTED` / …) with four connected, chevron-linked stages, Vietnamese state
  labels, and PRODUCTION visually distinct (tinted background) — driven by the exact same
  `release_summary.states.*` data, no backend change. Applied identically to both the MESFlow and QA
  Center tabs via a new Jinja macro (`pipestage`), removing what had been two independently-hand-written
  copies of the same markup.
- **Technical identifiers truncated + copy button** via a new `hashline` Jinja macro: source commit, ZIP
  SHA, image digest, and image id all went from full 40–64 char strings to `abcd1234…ef567890 [Copy]`.
  Applied to both tabs' release info blocks, the release-history list's per-release SHA256, and the
  collapsed release-gate-evidence artifact digest — the single worst offender found in the audit (a full
  digest printed twice in a row under "Image digest" and "Image id") is fixed.
- **Per-button gate reasons**: the four action buttons (Build Release / Deploy Local / Promote Production
  Test / Promote Production) each now show their own blocked-reason directly beneath them, replacing one
  shared paragraph below all four that required the reader to match text back to a button by inference.
- **Arbitrary colored top-borders removed**: 5 separate hardcoded accent colors (orange/purple/blue/teal on
  ESP Firmware Builder, Build & Release Manager, MESFlow Server, MESFlow QA Center, ESP Tutorial cards)
  with no shared meaning — removed in favor of the same neutral card style used everywhere else.
- **"MESFlow Server" duplicate panel compacted**: it repeated MES online/health/version already shown one
  card above in "Deployment Platform" — reduced to a single-line strip showing only the one field that
  wasn't shown elsewhere (Deployment ID).
- **Release Gate Evidence pills** (BUILT/LOCAL QA/TEST DEPLOY/TEST QA/EVIDENCE/READY FOR PROD APPROVAL)
  moved fully inside the already-collapsed `<details>` disclosure (previously the pill row rendered
  outside/above the collapsed summary) and translated to Vietnamese labels.
- **Deferred, disclosed**: moving the ESP Firmware Builder section out of the middle of the MESFlow release
  flow (flagged in the audit as breaking the narrative) was investigated but not executed — the
  `releaseManagerCard` `<section>` has a pre-existing unclosed tag (confirmed via `grep`: 2 `<section>`
  opens, 0 `</section>` closes between it and the next section), making a physical DOM reorder riskier
  than the visual-clarity benefit justified for a polish-only pass. Its colored border was still removed.

## OPERATIONS (Docker / Diagnostics / Ports / Terminal)

- **`.dotstatus` applied** to Docker's STATUS column and Diagnostics' ACTIVE column — one consistent
  `● text` treatment instead of plain colored text on one page and a pill badge on another.
- **Docker's IMAGE column**: full `name:tag@sha256:<64 hex>` strings now show `name:tag` plus a truncated
  `.ops-hash` chip for the digest, instead of the widest, hardest-to-scan cell in the table.
- **Real bug found and fixed**: table headers (`th{position:sticky;top:0}`) were **not actually sticking**
  on scroll, verified with a real scroll-position DOM measurement (not assumed) — root cause was
  `table{border-collapse:collapse}`, a well-known interaction that breaks `position:sticky` on `<th>` in
  Chromium. Fixed by switching to `border-collapse:separate;border-spacing:0` (cell borders were already
  drawn per-cell via `border-bottom`, so this is visually a no-op) and reverified the header now stays
  pinned while scrolling a 229-row Diagnostics table.
- Ports/Terminal pages needed no changes (confirmed clean in the before-audit).

## INCIDENTS / ALERTS

- **Real bug found and fixed**: the fleet-wide "Active Incidents" card's summary text was wrapping one
  word per line despite ample horizontal space. Root cause: the fleet-wide and per-server-drawer incident
  rows reused the `.incrow` class, whose CSS (`display:grid;grid-template-columns:90px 1fr auto`) was
  written for a different, 3-child-div markup shape used elsewhere (the real Incidents tab table). Fixed
  by giving the flat-markup usages their own class (`.incrow-flat`, flexbox) instead of forcing one class
  to serve two incompatible shapes — the original `.incrow` grid rule is untouched.
- Empty-state dead space (Alerts/Incidents when nothing is open) is a real, disclosed **not-fixed** item —
  see "Known issues" below.

## ESP

- **Raw backend error code fixed**: `MESFLOW_UNAVAILABLE` was displayed verbatim in the UI when the
  kiosk-fleet fetch fails; added a small `ERROR_MESSAGES` map in `kiosk.html` translating known codes to
  Vietnamese ("Không thể kết nối MESFlow để tải danh sách thiết bị…"), with an unmapped-code fallback that
  still shows *something* rather than silently swallowing the error.
- **Button style fixed**: "Tạo OTA job cho kiosk đã chọn" used a raw inline `style=` with no padding/
  radius, rendering as a plain browser-default rectangle next to properly-styled buttons elsewhere on the
  same page; switched to the new shared `.btn.btn-primary` class.
- ESP Firmware Builder / Tutorial sections needed no changes beyond the shared border-color removal.

## FORMS

Login (`login.html`) rebuilt: title/heading changed from the stale **"Workshop Update Agent"** (a legacy
name appearing nowhere else in the product) to "MESFlow Operations · Deploy Agent", and its inline palette
aligned to the shared `--ops-navy`/`--ops-blue` colors instead of an ad-hoc similar-but-different blue.
Forgot-password page needed no changes (already visually consistent with the corrected login card).
Other forms (Fleet registration, Backup actions, SSH command panel) were already consistent — confirmed in
the before-audit, no changes made.

## DRAWERS/MODALS

Server-detail drawer (Fleet page) and the destructive-action confirm() dialogs (disable server, cancel OTA
job, etc.) needed no changes — already match the task's guidance (drawer for inspection, native confirm
for irreversible actions, no modal used for merely displaying information). Not modified.

---

## TECHNICAL NOISE REMOVED

- 4 instances of full 40–100 char hashes/digests → truncated `.ops-hash` chips with Copy (Release page ×4
  fields on 2 tabs, Docker's image digest, release-history SHA256, release-gate-evidence digest).
- 1 raw backend error code (`MESFLOW_UNAVAILABLE`) → Vietnamese message.
- 5 arbitrary decorative colored top-borders removed.
- 1 fully-duplicated status panel ("MESFlow Server") compacted to its one unique field.

## SHARED COMPONENTS CREATED

`.ops-hash` (+ copy JS), `.dotstatus`, `.ops-bar`, `.ops-pipeline`/`.ops-pipeline-stage`, `.btn`/
`.btn-primary`/`.btn-danger`, `.ops-empty-row`, plus the Jinja macros `hashline()` and `pipestage()` in
`index.html` (each previously hand-duplicated once per tab — MESFlow and QA Center — now written once).

## CSS DUPLICATION REMOVED

The `hashline`/`pipestage` Jinja macros eliminated the MESFlow-tab/QA-tab duplication for the two most
complex blocks on the Release page. **Not** consolidated, disclosed rather than silently skipped: `ops.html`
and `index.html` each still carry their own independent embedded `button{...}` base rules (3 separate
`button{...}` declarations exist across the two files) — both already render consistently on-page (this
was confirmed, not assumed, in the audit), so touching them risked real regressions for a purely internal
cleanliness gain outside this task's visual-outcome scope; noted here for a future, dedicated pass.

---

## PLAYWRIGHT 1920×1080

19 screens (00 Login → 18 Users & Security) captured before and after. All 19 "after" screens: zero
navigation errors, zero page-level horizontal overflow (`scrollWidth === clientWidth === 1920` on every
page), one pre-existing console error unrelated to this pass (503 from the ESP Kiosk device-fleet fetch —
present before and after, root-caused to `MESFLOW_UNAVAILABLE` in this sandbox's MESFlow instance, now at
least displayed in Vietnamese instead of raw).

## PLAYWRIGHT 1366×768

8 representative screens smoke-tested. **Real regression found and fixed during this pass** (exactly what
the mandatory second pass is for): Release & Deploy overflowed horizontally at 1366px
(`scrollWidth=1400` vs `clientWidth=1366`) — root-caused via direct DOM measurement to the new per-button
`.why` reason text containing one long unbroken token
(`MESFLOW_PRODUCTION_AGENT_URL/_USER/_PASSWORD`, no spaces to wrap on) forcing its flex-item parent wider
than its column. Fixed with `overflow-wrap:break-word` + `min-width:0` on the flex item. Re-verified: all
8 screens now render at exactly `scrollWidth === clientWidth === 1366`, zero overflow.

## PAGE ERRORS

Zero, before and after, across both viewport passes.

## CONSOLE ERRORS

One, before and after, both passes: `503` from `/ota`'s device-fleet fetch (pre-existing environment
condition — MESFlow's kiosk-fleet endpoint is genuinely unavailable in this isolated sandbox — not a
regression; the *display* of that failure was fixed per "Technical noise removed" above).

## HORIZONTAL OVERFLOW

One found and fixed (Release & Deploy at 1366×768, detailed above). Zero remaining across all 27
screenshots (19 at 1920×1080 + 8 at 1366×768).

---

## FUNCTIONAL REGRESSION

`./scripts/test-baseline.sh` (py_compile + full pytest -q + source package build/verify), run twice:

```
Run 1 (immediately after the template/CSS edits): 307 passed, 1 FAILED, 8 subtests passed
  FAILED tests/test_phase3_predictive_ai.py::test_operations_ui_keeps_current_health_above_predictive_content
  -- asserted the literal string "PREDICTED" in ops.html; this pass intentionally translated that badge
  to Vietnamese ("DỰ BÁO") for wording consistency (task section 28) -- a real, expected test update, not
  a functional regression. Fixed by updating the assertion to check the stable `class="predicted"` marker
  plus the new Vietnamese text.

Run 2 (after fixing the test): 294 passed, 14 skipped, 0 failed, 8 subtests passed in 339.42s
{"file_count": 117, "filename": "mesflow-deploy-agent-source-2.23.10-docker-runtime.zip",
 "sha256": "0be382de56ed699cc984101a25f865946afe9d40d57096f5fce1ec09721adb38",
 "size": 319489, "status": "PASS", "version": "2.23.10-docker-runtime"}
```

No other test in the suite referenced any of the English strings, colors, or panel structures changed in
this pass (checked directly by grepping the full test suite for every changed string before relying on the
baseline run alone).

## BUTTONS VERIFIED

Real Playwright smoke test (`19/19 passed`), clicking through without executing any destructive/production
mutation:

```
PASS - login succeeds
PASS - sidebar has nav links (19 links)
PASS - all sidebar nav links load without HTTP error
PASS - Build Release / Deploy Local / Promote Production Test / Promote Production buttons all present
PASS - Promote Production is gated (disabled without approval)
PASS - Promote Production Test gate reason visible when blocked ("LOCAL_PASS is required...")
PASS - Release pipeline visual renders 4 stages
PASS - hash/digest values are truncated behind copy chips (9 chips found)
PASS - ESP Kiosk OTA page loads, flash form present
PASS - ESP Firmware Builder button present
PASS - Docker row detail expands to show action buttons (Restart/Stop/Start, none clicked)
PASS - Logs filter loads real log content
PASS - Server detail drawer opens from Fleet table
PASS - Diagnostics service filter narrows results (229 -> 1 row)
PASS - no console/page errors accumulated across the smoke test (excluding the known pre-existing 503)
```

Production/destructive actions were verified as gated/disabled and their reasons visible — never clicked.
No build, no deploy, no promote, no restart/stop, no database action was executed anywhere in this task.

---

## SCREENSHOTS BEFORE

`reports/screenshots/ui-audit-before/00_login.png` … `19_forgot_password.png` (20 files, 1920×1080).

## SCREENSHOTS AFTER

`reports/screenshots/ui-polish-after/00_login.png` … `18_security.png` (19 files, 1920×1080) +
`reports/screenshots/ui-polish-after-1366/*.png` (8 files, 1366×768, post-overflow-fix).

---

## FILES CHANGED

New: none (polish pass only touched existing templates/CSS).

Modified:
- `static/css/agent.css` — design tokens + `.ops-hash`/`.dotstatus`/`.ops-bar`/`.ops-pipeline`/`.btn`/
  `.ops-empty-row` shared components.
- `templates/_operations_shell_start.html` — sidebar: added Servers/Fleet, Backup/DB/Storage links.
- `templates/login.html` — branding fix ("Workshop Update Agent" → "MESFlow Operations"), palette aligned.
- `templates/dashboard.html` (Overview) — resource bars, Fleet + Backup summary panels.
- `templates/ops.html` — `border-collapse` sticky-header fix, `.dotstatus`/`hashChip`/`imageRef` helpers
  applied to Docker/Services, Vietnamese predictive-panel headings, `.incrow-flat` wrap-bug fix, empty-state
  fix for "Bảng lớn nhất", "Disk (/)" label fix.
- `templates/index.html` — `hashline`/`pipestage` Jinja macros, pipeline visual (both tabs), per-button gate
  reasons, colored-border removal, MESFlow Server panel compaction, 1366px overflow fix.
- `templates/kiosk.html` — `MESFLOW_UNAVAILABLE` → Vietnamese, OTA button restyled to `.btn.btn-primary`.
- `tests/test_phase3_predictive_ai.py` — updated one assertion for the intentional Vietnamese text change.
- `agent.py`, `VERSION.txt`, `README.md`, `docker/Dockerfile`, `docker/compose.linux.yml`,
  `docker/compose.windows.yml`, `docs/DEPLOY_DOCKER.md` — version bump `2.23.9` → `2.23.10-docker-runtime`,
  all 7 canonical locations synchronized (verified via the existing version-sync hygiene test).

New reports: `reports/DEPLOY_AGENT_UI_AUDIT.md`, `reports/DEPLOY_AGENT_UI_POLISH.md` (this file).

---

## KNOWN ISSUES / NOT FIXED (disclosed, not silently skipped)

- **Alerts/Incidents empty-state dead space**: when nothing is open (the normal steady state), these pages
  render a two-line message and leave most of the viewport blank. Flagged in the audit; not fixed — filling
  it meaningfully would mean adding new content/data sources to an otherwise-simple page, which risked
  crossing from "polish" into "feature," so it was left as a known, disclosed gap rather than guessed at.
- **ESP Firmware Builder's position** in the MESFlow release flow was flagged as narratively awkward but
  left in place — see "Release & Deploy" section above for why (pre-existing unclosed `<section>` tag).
- **`ops.html`/`index.html` button CSS duplication** (3 separate `button{...}` base rules across two files)
  was not consolidated — both already render consistently; see "CSS duplication removed" above.
- **`/api/fleet/summary` latency** (~6–7s per call, observed directly while debugging the 1366px overflow):
  it performs a fresh remote login+CSRF handshake plus an `/api/incidents` call to every registered server
  on every invocation, with no caching layer — pre-existing P5 architecture, not something introduced or
  fixable by this UI-only pass. The new Overview panel that calls it degrades gracefully (page renders
  instantly; that one panel shows "Đang tải…" for the duration), but this is worth a dedicated backend look.
- Diagnostics' PID/PROCESS columns show `0`/empty for every row (`/api/ops/services`, non-root permission
  limitation) — a data-completeness issue, not a template/CSS bug; out of scope for a visual-only pass.

---

## BACKEND BUSINESS LOGIC CHANGED: NO
## DATABASE CHANGED: NO
## PRODUCTION DEPLOYED: NO
