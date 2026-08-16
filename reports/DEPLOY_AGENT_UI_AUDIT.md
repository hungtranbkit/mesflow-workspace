# Deploy Agent — UI Audit (before polish)

Date: 2026-08-14
Method: real local DEV Agent instance (isolated `WORKSHOP_AGENT_HOME`, port 18700), a second real throwaway
`agent.py` process registered as a TEST fleet server (port 18701, so Fleet/Incidents pages show real,
non-empty data), MESFlow/QA Center pointed at the real read-only host-exposed health endpoints
(`127.0.0.1:8080`/`127.0.0.1:8095`) for realistic Overview data. Real Chromium via Playwright, 1920×1080,
full-page screenshots. 19 screens captured under `reports/screenshots/ui-audit-before/`. Zero navigation
errors; one console error (`503` on `/ota`'s device-fleet fetch, see ESP Kiosk section below); zero
page-level horizontal overflow on any of the 19 screens (`scrollWidth == clientWidth == 1920` everywhere).

This audit is descriptive only — no code was changed while producing it, per the task's "inspect before
editing" requirement.

---

## Screens reviewed

00 Login · 01 Overview · 02 System Health · 03 Alerts · 04 Incidents · 05 System Logs · 06 Diagnostics
(Services) · 07 Docker · 08 Network/Ports · 09 Backup/DB/Storage · 10 Terminal/SSH · 11 Servers/Fleet ·
12 Release & Deploy (+ 13 Deploy History / 14 Agent Update / 16 ESP Firmware / 17 ESP Tutorial /
18 Users & Security — all six are anchor-scroll sections of the **same** `/releases` page; a full-page
screenshot captures all of them regardless of which anchor is requested, confirmed by diffing) · 15 ESP
Kiosk Fleet/OTA · 19 Forgot password.

---

## Cross-cutting findings (appear on multiple pages)

1. **Two parallel, partially-overlapping navigation systems.** The persistent left sidebar
   (`_operations_shell_start.html`) links to `Sức khỏe hệ thống / Cảnh báo / Sự cố / Chẩn đoán / Docker /
   Services / Network & Ports / Terminal`, but `ops.html` itself *also* renders its own internal tab strip
   (`Tổng quan · Servers/Fleet · Cảnh báo · Sự cố · Chẩn đoán · Docker · Ports · Backup/DB/Storage · Nhật
   ký hệ thống · Command/SSH`) at the top of every `/ops` page. **Servers/Fleet and Backup/DB/Storage exist
   only in the internal tab strip — they have no sidebar entry at all**, so a user landing on Overview or
   Release & Deploy has no visible path to the Fleet or Backup pages except by first opening a different
   `/ops` view and noticing the extra tabs. This is a real discoverability gap, not just a style
   inconsistency.
2. **Long technical strings shown in full, repeatedly**, most severely on Release & Deploy: full 40-char
   git commit hash, full 64-char ZIP sha256, and the **same** full image digest string printed twice in a
   row under two different labels ("Image digest" and "Image id"). Docker's table also prints a full
   `mesflow-app:71.0.0.4@sha256:<64 hex chars>` image reference inline in a normal-width column. None of
   these are truncated, copy-buttoned, or collapsed — a direct violation of the "technical identifiers"
   guidance (task section 12).
3. **No single status-badge component.** Overview/Health use a pill badge (`ops-badge`); Docker's STATUS
   column is plain text ("Up 3 hours (healthy)"); Fleet uses a differently-styled pill; Diagnostics/Services
   use plain colored text ("active"/"inactive") with no pill at all. Four different visual treatments for
   the same semantic concept (running/healthy vs. not) across four pages.
4. **Raw/English backend strings leak into Vietnamese UI**: `MESFLOW_UNAVAILABLE` is displayed verbatim on
   the ESP Kiosk page when the fleet-device fetch fails (no Vietnamese fallback message); System Health's
   predictive panels are titled in English ("Predictive Insights", "Disk forecast", "PostgreSQL growth",
   "Recurring Problems", "Suggested remediation") while every surrounding label is Vietnamese.
5. **Uneven information density / large dead space.** Alerts and Incidents (when empty, which is the
   normal steady state) render a two-line message and then ~800px of blank page — nothing wrong
   structurally, just no attempt to make the empty state feel intentional/complete rather than "unfinished."
   Overview similarly has a solid ~450px empty band below its four content panels.
6. **Inconsistent empty-state handling inside tables.** Some empty tables show a helpful full-width message
   row ("Chưa có backup nào. Bấm..."), others (Release & Deploy's "Bảng lớn nhất") show nothing at all under
   the header row — looks broken rather than "no data yet."
7. **Resource metrics are numbers only, no visual scale.** CPU/RAM/Disk are shown as a bare percentage with
   no bar/gauge anywhere (Overview's "Server" panel, Health's KPI cards) — harder to eyeball severity at a
   glance than the bar-chart style the task explicitly asks for.

## Per-page findings

**00 Login** — Title and `<h1>` both read **"Workshop Update Agent"** — a stale/legacy product name that
appears nowhere else in the product (every other page says "MESFlow Operations" / "MESFlow Deploy Agent").
This is the very first thing a user sees and it names the wrong product. `login.html` is also entirely
unstyled by the shared shell (its own inline `<style>` block, different visual language from the rest of
the app) — acceptable for a minimal auth screen, but the branding mismatch is a real bug.

**01 Overview** — Good bones: four compact status panels (not giant cards), a clean two-column
incidents/activity split. Problems: large empty band below the fold (§5 above); CPU/RAM/Disk numbers with
no bar; no path to Fleet/Backup pages from here (§1).

**02 System Health** — `DISK /` label reads awkwardly (mount path concatenated directly onto the label with
no separator/formatting). Five stacked forecast/insight panels ("Predictive Insights" through "Suggested
remediation") are almost entirely single-line empty-state placeholders in this environment but still
consume ~500px of vertical space each in English headings (§4). Real duplication: MESFlow/QA
online-status line here repeats what Overview already showed.

**03 Alerts** — Functionally fine (clear empty state text), but ~800px of dead space below it (§5).

**04 Incidents** — Well-formed table (LOẠI/MỨC ĐỘ/DỊCH VỤ/TRẠNG THÁI/BẮT ĐẦU/LẦN CUỐI/SỐ LẦN), sensible
single-row empty state. Same dead-space issue below.

**05 System Logs** — Already close to the target console style (dark monospace panel, source/lines
selector + "Đọc log" button). No severity/time-range filter (spec asks for one) — treated as a possible
future enhancement, not required for this polish pass since adding new filter *logic* would cross into
"feature," not "polish."

**06 Diagnostics (Services)** — 228-row table. The "ĐIỀU KHIỂN" (action) column text ("Thao tác nâng cao")
*appeared* clipped in the initial full-page screenshot's downscaled rendering — verified directly via
Playwright's computed layout (`getBoundingClientRect` on the `<summary>`, its `<td>`, `.tablewrap`, `.card`
and `.ops-content`, plus a pixel-level crop) and this is **not** an actual bug: every box ends well inside
its parent (`summary.right=1869` vs `wrap.right=1878` vs `content.right=1920`) and the crop shows the full
text rendering correctly. Recorded here only so this isn't independently "discovered" and mis-fixed later.
No sticky table header despite 228 rows requiring significant scroll — a real, lower-priority nice-to-have.

**07 Docker** — STATUS column is plain text, not the pill badge used elsewhere (§3). `mesflow-app`'s IMAGE
column shows the full `image:version@sha256:<64 hex>` string inline (§2) — by far the widest,
hardest-to-scan cell in the table.

**08 Network/Ports** — Clean, simple table. PID is `0` and PROCESS is empty for every single row — almost
certainly a permissions issue (reading `/proc/<pid>` ownership without root), not a template/CSS bug;
flagged for awareness but out of scope for a visual-only pass.

**09 Backup/DB/Storage** — One of the best-composed pages already: two-column PostgreSQL/Storage summary,
a clean Storage category table, PostgreSQL Backups / Retention / Restore Drill / Audit trail all as proper
tables with real column headers. Two issues: the "PostgreSQL Center" panel (short error message) and the
"Storage" panel next to it (full category table) end up very different heights, look unbalanced side by
side; "Bảng lớn nhất" (largest tables) is the one empty table on this page with **no** empty-state message
row (§6).

**10 Terminal/SSH** — Well-composed: clear permission-scope warning banner, quick-command chips, two
console panels. No problems found beyond generic component consistency (button/input sizing — see Design
System section).

**11 Servers/Fleet** — Real bug: the fleet-wide "Active Incidents" card's summary text ("— QA Center
unreachable") wraps one word per line in a narrow inner container despite abundant horizontal space
available in the card — looks broken, not just tight. Otherwise a strong page (KPI summary row, registration
form, server table all consistent).

**12–18 Release & Deploy (single long page, ~3250px tall at 1920 width)** — The most important page per
the task brief, and currently the weakest:
- The **pipeline state** is shown as a flat wrapping row of seven ALL-CAPS English pill labels
  (`BUILT: PASS`, `LOCAL QA: NOT_RUN`, `TEST DEPLOY: NOT_DEPLOYED`, `TEST QA: NOT_RUN`,
  `EVIDENCE: INCOMPLETE`, `READY FOR PROD APPROVAL: LOCAL_FAILED`) — accurate information, but reads as a
  debug/log dump, not the BUILD→LOCAL→TEST→PRODUCTION visual flow the task asks to make "the visual
  center" of the page.
- **Full 40-char commit hash, full 64-char ZIP SHA, and the full image digest printed twice in a row**
  (§2) — the single worst instance of raw-technical-string noise in the whole app.
- **"MESFlow Server" panel duplicates** what "Deployment Platform"'s first card already shows two rows
  above it (version, health).
- **"ESP Firmware Builder" is sandwiched between "MESFlow Server" and "Build & Release Manager"** — an
  unrelated device-firmware concern interrupting the MESFlow release flow narrative.
- Each of the ~7 stacked section cards has its own **arbitrary colored top border** (blue, orange, purple,
  green, purple again) with no legend or consistent meaning — reads as decoration, not signal.
- Disabled-button reasons ("Build blocked: …", "Promote Test blocked: …", "Promote Production blocked: …")
  are stacked in one shared paragraph below all four action buttons, not attached to the specific button
  each reason explains.
- The "Users & Security" sidebar link lands on a bare `<span>` anchor with no heading of its own — it
  happens to sit just above the one real control there (Đổi mật khẩu Agent / change agent password), but
  there's no section title confirming the user landed in the right place.
- The whole page is roughly 3× the 1080 viewport height even before scrolling to the QA Center section —
  a direct conflict with "less scrolling, more meaningful data."

**15 ESP Kiosk (Fleet/OTA)** — Fleet summary cards are permanently stuck at `--`/`--`/`--` with "Đang tải
thiết bị…" (loading…) in this environment, and the OTA release panel displays the **raw backend error code
`MESFLOW_UNAVAILABLE`** directly in the UI with no Vietnamese explanation (§4) — this is also the source of
the one console error captured (`503` on the underlying fetch). The "Tạo OTA job cho kiosk đã chọn" button
is visually a plain rectangle, inconsistent with the rounded button style used everywhere else.

**19 Forgot password** — Clean, consistent with the login card style. No issues found.

---

## Screenshots

`reports/screenshots/ui-audit-before/00_login.png` … `19_forgot_password.png` (19 files, 1920×1080,
full-page).
