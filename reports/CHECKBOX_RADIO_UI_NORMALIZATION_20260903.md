# Checkbox/Radio UI Normalization — 2026-09-03

Stability-first fix, no new features. Priority target: the reported
"Giới hạn đầu vào" vs "NG tiêu hao đầu vào" checkbox size mismatch in the
Template old-editor, then a scoped audit of the same defect class
elsewhere.

## Root cause

`ui.css` had several `<scope> input{width:100%;...}` shorthand rules
written for text/number/select fields (`.template-old-op-row input`,
`.login-card input,.modal input,...`, `.equipment-form input`, etc.).
None of them discriminate on `type`, so a checkbox or radio nested inside
one of these scopes silently inherited the same width/height/padding.

Confirmed live via Playwright + `getComputedStyle` **before** fixing
anything: in the Template old-editor's operation rows, the "Giới hạn đầu
vào" checkbox rendered at **31.14×36px** while its sibling "NG tiêu hao
đầu vào" checkbox — identical markup, no classes on either input —
rendered at **13×36px**. Both inherited the leak; the width differed
because the two checkboxes sit in different flex/grid contexts
(`.template-flow-row` is a 3-column grid holding 4 children, so the
second checkbox's label wraps to its own row and resolves `width:100%`
against a different available width).

The same leak pattern was independently confirmed on two more screens,
proving it's a systemic gap, not one isolated bug:
- Excel-import radio buttons (`Nhập Operation từ Excel` modal) — leaking
  via the generic `.modal input{width:100%}` rule.
- The plain reset-password modal's "Bắt đổi mật khẩu sau khi đăng nhập"
  checkbox — same `.modal input` leak, and additionally no layout at all
  for its `.form-check` wrapper (that class only had page-scoped copies:
  `.po-op-modal .form-check`, `.system-user-modal .form-check` — any
  other screen using the same markup got no gap between checkbox and
  label text).

Several screens already carried one-off patches that didn't agree with
each other: `.po-op-modal .form-check input{width:auto}`,
`.template-old-check input{width:auto}`,
`.session-cross-part-confirm input{width:auto!important}`,
`.rbac-table input{width:18px;height:18px}`. Patching the reported site
alone would have been exactly the "vá cục bộ" (local patch) the task
explicitly said to avoid.

## Fix

`app/mesflow/web/static/ui.css`, two additions:

```css
input[type="checkbox"],input[type="radio"]{
  width:16px!important;height:16px!important;
  min-width:16px!important;min-height:16px!important;
  margin:0!important;padding:0!important;
  flex:none!important;
  accent-color:var(--action-primary,#23658b);
  cursor:pointer;
  vertical-align:middle;
}
input[type="checkbox"]:disabled,input[type="radio"]:disabled{cursor:not-allowed;opacity:.6}

.form-check{display:flex;align-items:center;gap:8px}
.form-check-label{cursor:pointer}
```

- `!important` on the box-model properties is deliberate: it's the only
  way to reliably win over every existing (and future) scoped
  `<selector> input{width:...}` shorthand without hunting down and
  patching each leak site individually, regardless of selector
  specificity or file order.
- 16px matches the size already used by the majority of existing,
  correctly-scoped checkboxes in this file (shift editor, equipment
  form, system-user modal) — chosen to match the dominant existing
  convention, not invent a new one.
- `.form-check` gets one shared base layout rule instead of only living
  as two near-identical page-scoped copies.
- Old scoped overrides (`.po-op-modal .form-check input`,
  `.template-old-check input`, `.session-cross-part-confirm input`,
  `.rbac-table input`) are left in place — now redundant, not
  conflicting — to keep the diff minimal.

## Verified (Playwright + `getComputedStyle`, before/after)

| Screen | Before | After |
|---|---|---|
| Template old-editor, 94 checkboxes across 4 templates | 31.14×36px / 13×36px (mismatched) | **16×16px, uniform, all rows** |
| Excel-import radios | stretched full-width | 16×16px |
| Reset-password modal checkbox | stretched, no gap from label | 16×16px, proper gap |
| RBAC permission matrix (`.rbac-table`) | 18×18px | 16×16px (unified, was the one deliberately-different size) |
| Add Equipment modal ("Đang sử dụng") | already correct | unchanged, still correct |
| Add/Edit User modal ("active", "must change password") | already correct | unchanged, still correct |

Swept at both 1400px desktop and 375px mobile viewports. Also visually
swept Dashboard, Session Management, Exception Center, Employees,
Equipment, Users, Working Calendar, Kiosk Management, and their primary
modals for the same class of defect (table layout, badge/button sizing,
modal overflow, label alignment) — no other checkbox/radio or
comparable-severity layout regressions found. One minor, out-of-scope
cosmetic nit noted below rather than chased.

Full pytest regression suite (relevant subset + the isolated QA sandbox's
full suite) and the repo's own `tests/e2e/template-ui.spec.js` (the
Playwright spec that directly exercises this screen at three required
viewports) — both pass; see evidence below.

## Deploy

Built once, promoted the same artifact everywhere (no rebuilds per
target):

- **local DEV** (`127.0.0.1:8080`) — `71.0.0.213`, healthy.
- **`mesflow.net`-host** ("production test") — `71.0.0.213`, healthy,
  verified live via HTTPS with a real login + Playwright check (94
  checkboxes, uniformly 16×16px).
- **`prod.mesflow.net:8299`** — `71.0.0.213` via `scripts/deploy.sh
  prodtest 71.0.0.213` (Architecture A: pull-by-digest, migration
  container, app-only recreate, scheduler cron reverify) — `== DEPLOY
  PASS ==`, digest verified, `migration_changed: 0`.

All three environments' running `ui.css` now hash-match exactly
(`dc455b3e7ca09acf9d39776dc5d2dd53`).

## Test evidence

- `scripts/release-local-qa.sh` (real QA gate, isolated sandbox on port
  18280): `version-verify` PASS, `preflight` PASS, `build` PASS, `test`
  PASS (824 pytest cases across static/behavioral/integration suites +
  84/88 Playwright e2e specs, including `template-ui.spec.js`),
  `deploy-local` PASS, `smoke` PASS, `status` PASS. Overall
  `QA_STATUS=PASS`, `FAILED_STEP=none`. Evidence submitted to Deploy
  Agent (`local.status` flipped to `PASS`, run
  `release-local-qa-71.0.0.213-8d9c3bb1`).
- One pre-existing, unrelated pytest failure noted and excluded from the
  above: `test_runtime_versions_all_match_658448` fails only because a
  stray `mesflow` package from the separate `mesflow-kiosk-runtime-v2`
  repo shadows this one on this host's default Python path — an
  environment artifact, not something this change touched or caused.
- `scripts/deploy.sh prodtest 71.0.0.213`: `== DEPLOY PASS ==`, health
  check green, digest match, `migration_changed: 0`.

## Process note (worktree + relative-path scripts)

`scripts/build-release.sh`, `scripts/release-local-qa.sh`, and
`scripts/release-build.sh` all resolve their output directories
(`artifacts/releases/`, `artifacts/qa/`, `release/`) relative to their
own script location (`$ROOT/../artifacts`, `$REPO_ROOT/release`). Run
from a task worktree (`.worktrees/claude-checkbox-ui-audit/`, per the
mandatory Agent Worktree & Branch Isolation Standard) rather than the
canonical `mesflow/` checkout, this resolves to a sibling directory
*outside* any tracked repo instead of the canonical location the Deploy
Agent reads from — a `deploy-local` trigger silently redeployed the
previously-built `71.0.0.212` instead of the just-built `71.0.0.213`
until the artifact directories were copied into the canonical location
by hand. `artifacts/` and `release/` are both gitignored build output
(not source), so copying between them carries no branch-isolation risk —
but this is worth fixing in the tooling itself (make these paths
worktree-aware, or document the copy step) rather than re-discovering it
on every worktree-based release. Not fixed in this pass — out of scope,
flagged for a follow-up task.

## Remaining risks / known minor items

- `.modal-note{margin-top:-8px}` (a deliberate negative margin to tuck a
  helper note under a text input) now reads slightly cramped when it
  directly follows a `.form-check` row (only currently true on the
  reset-password modal). Cosmetic, not functional; a one-line
  `.form-check + .modal-note{margin-top:8px}` fix was drafted, tested,
  then deliberately left out of this release to avoid a second
  build/QA/promote cycle for a non-functional nit. Left for a future
  pass.
- The systemic "generic `input` selector leaking onto checkboxes"
  pattern is now neutralized by the new `!important` base rule for every
  *current* case, but any brand-new page written with the same
  `<scope> input{width:100%}` shorthand habit will still produce an
  oversized checkbox visually (masked by the new rule's `!important`
  win, so it self-heals) — the underlying authoring habit itself wasn't
  changed. Not fixed here: would mean touching many unrelated selectors
  for a purely preventive, low-probability-of-recurrence benefit, which
  is scope creep on a stability-first task.

## Commits (part 1)

- `60e8605` — `fix(ui): canonical checkbox/radio sizing, shared layer not page hacks`
- `6466cfd` — `chore: bump version to 71.0.0.213 for checkbox/radio UI fix`
- Merged to `main` (fast-forward, `3af5a92..6466cfd`), pushed to `origin/main`.

---

## Part 2 — 2026-09-03, requirement 3 follow-up ("audit the rest")

Continued the same audit across the rest of the main UI (Dashboard,
Session Management, Exception Center, PO/Part/Operation CRUD, employee/
admin, key modals), desktop + mobile, per the original task's requirement
3. Found one new, more severe bug of the same "shared-layer value not
updated everywhere" shape, and fixed it and its siblings.

### Root cause

`.app-sidebar` sits at `z-index:80` (raised there deliberately at some
earlier point). The generic `.modal-backdrop` class — used by *every*
simple modal built via `box.className='modal-backdrop'` in `app.js`
(employee, equipment, user, PO, template, operation, Excel-import,
reset-password...) — was still at `z-index:40`, from before the sidebar's
z-index was raised. Any modal wide enough that its centered position
reaches under the sidebar's width gets the sidebar visually painted over
its left portion, since the sidebar wins the stacking order.

Confirmed live via Playwright: `getBoundingClientRect()` showed the
Employee add/edit modal correctly centered at `left:175px` (well within
the 272px sidebar), while the rendered screenshot showed every label on
that side truncated — e.g. "Mã nhân viên" rendering as "ân viên", "Ngày
sinh" as "sinh". A real, reachable bug in a core CRUD workflow (Danh mục
→ Nhân viên → Thêm/Sửa nhân viên), more severe in practice than the part-1
checkbox-size bug: here the FORM LABELS THEMSELVES were unreadable.

### Fix

`.modal-backdrop`'s z-index now reads `var(--ui-z-modal, 1100)` — the
same token the newer `.ui-modal-root` component already uses for this
exact purpose, instead of inventing another arbitrary number. Two more
instances of the identical pattern, found by grepping every full-viewport
`z-index` in the file:

- `#seModal` (an older Exception Center form's own id-selector override,
  `z-index:50`) — an id selector always wins over the class rule
  regardless of value, so the class fix alone would not have reached it.
  Same token applied. **Caveat**: while auditing this, found that the
  screen it belongs to (`session-exceptions.js` / `renderSessionExceptions`)
  is superseded, legacy code — the actually-live Exception Center is
  `exception-center.js`, which uses `.ec-drawer-shell` (already correctly
  at `z-index:1200`, no bug there). This fix is therefore harmless but not
  confirmed to address a live-reachable defect.
- `.drawer-backdrop` (Session Detail drawer, `z-index:45`) — also below
  the sidebar. Not independently visually reproduced (right-aligned,
  720px wide, so it only reaches under the sidebar in a narrow
  ~900–990px viewport-width band most manual testing skips), but the fix
  is free, so applied defensively. Uses `var(--ui-z-drawer, 1000)` — the
  token's own established role one tier below modals.

### Verified

- Employee add/edit modal (1050px) and Employee report modal (1180px,
  reached via the per-row "Báo cáo" button) — both re-render fully
  correctly (every label visible, proper centering) at 1400px desktop and
  375px mobile, on local DEV and confirmed again live on `mesflow.net`
  after promotion.
- Re-swept Equipment/Add-User/PO-Operation modals — no regression from
  the z-index change (all already cleared the sidebar by virtue of being
  narrower, so visually unchanged, but confirmed still correct).
- Full pytest regression suite + `tests/e2e/*.spec.js` (88 Playwright
  specs) in the isolated QA sandbox: `QA_STATUS=PASS`, `FAILED_STEP=none`,
  7/7 checks green. One transient e2e navigation-interrupt error in a
  dashboard timeline spec self-resolved on the built-in retry (`retries:1`
  in `playwright.config.js`); did not affect the overall `TEST PASS`.

### Deploy

Same build-once-promote-everywhere flow as part 1, next version:

- **local DEV** — `71.0.0.214`, healthy.
- **`mesflow.net`-host** — `71.0.0.214`, healthy, live-verified via HTTPS
  (Employee modal renders correctly).
- **`prod.mesflow.net:8299`** — `71.0.0.214` via `scripts/deploy.sh
  prodtest 71.0.0.214` — `== DEPLOY PASS ==`, digest verified,
  `migration_changed: 0`.

All three environments' `ui.css` hash-match exactly
(`c3c8c3270145b3e9cb7fe873afd80787`).

### Scope note

Did not find further clear, low-risk issues in this pass across Dashboard,
Session Management (no session data currently loaded on any environment,
so the Session edit drawer/modal itself — already at the correctly-high
`z-index:1200` — could not be exercised end-to-end with real data), the
PO create/edit/operation modals, or the Add Equipment/User modals — all
rendered correctly, consistent with the design system's own extensive
prior audit history already documented inline in `ui.css` (a "UI Template
Standard v1/v2" section with several other real bugs already found and
fixed live in earlier work: input/button height ties, `[hidden]` on
`.btn`, toolbar control-height unification). Stopped here rather than
continue searching without a concrete lead, per the task's own
"không refactor rộng nếu không cần" instruction.

### Commits (part 2)

- `f7ee593` — `fix(ui): modal-backdrop z-index below sidebar, real content clipping`
- `5d0f4af` — `chore: bump version to 71.0.0.214 for modal-backdrop z-index fix`
- Merged to `main` (fast-forward, `6466cfd..5d0f4af`), pushed to `origin/main`.

---

## Part 3 — 2026-09-03, Dashboard + remaining-screens sweep, plus one user-requested field change

### Audit sweep

Swept every remaining page not yet individually checked: Dashboard theo
ngày, Production Trace, Nhật ký nghiệp vụ (business audit trail), Trạm
kiosk, Nhật ký ứng dụng (system logs), Báo cáo năng suất nhân viên, In
tem QR, Ca làm việc (working calendar), Production Schedule (Gantt &
Material Flow), Hướng dẫn (tutorials), and all 6 `super_admin`-only
System Console pages (Tổng quan hệ thống, Lỗi hệ thống, Nhật ký, Dịch vụ,
Chẩn đoán, Nhật ký quản trị) — desktop + mobile where applicable, using
both the `admin` and `superadmin` accounts (the System Console pages
correctly return "Không có quyền truy cập" for a plain `admin`, since
they're gated to `super_admin` — confirmed this is intentional RBAC, not
a bug, by re-testing with `superadmin`).

No further checkbox/radio, input-height, button-sizing, table-layout,
badge/banner-spacing, modal-overflow, or icon-scaling defects found.
Every one of these screens already matches the design system's existing
"UI Template Standard" conventions.

One minor, cosmetic-only observation, not fixed (below the bar for a
stability-first low-risk fix — touches the shared `openPage()` early-
return path used by every page, higher blast radius than its value):
navigating to a page you lack permission for leaves the previous page's
header title/subtitle in place instead of resetting it, since the
access-denied branch in `openPage()` returns before any page's own
render function (which is what normally sets the header text) runs. Only
visible to a user who already can't do anything on that screen anyway.

### User-requested field change (not a stability-audit finding)

Mid-audit, the user asked what "NG tiêu hao đầu vào" means, then asked to
hide it since the behavior is implicitly always expected — no need to
expose it as a toggle. This field (`defects_consume_input`) appeared as a
checkbox in two places, both removed:

- `poOperationModal` (PO's "Sửa/Thêm Operation" form) — "Sản phẩm lỗi
  cũng tiêu hao đầu vào" checkbox removed; its submit payload now
  hardcodes `defects_consume_input:true` instead of reading a checkbox
  that no longer exists.
- `oldOperationRow` (Template old-editor's per-operation row) — "NG tiêu
  hao đầu vào" checkbox removed; the now-dead `data-consume-defects`
  query and its `onchange` handler removed from `bindOldEditorEvents`
  (would otherwise throw on a null element). New operations added via
  "+ Thêm Operation" already defaulted to `true` and are unchanged.

Both read-only *displays* of this field (material-flow.js's relation
card, and the PO detail page's flow-card in app.js) were left as-is —
they show actual historical state, not a setting, so still correct.
Existing template/operation data that already has `defects_consume_input:
false` stored is left untouched by the Template editor path (no bulk
data migration was asked for); it can just no longer be edited back to
`false` through either screen.

Side effect: `.template-flow-row` now renders exactly 3 items against
its 3 explicit grid columns (was 4 items sharing 3 columns, with the 4th
wrapping to its own row) — incidentally resolves the earlier-noted grid/
column mismatch from the checkbox-sizing investigation in part 1, as a
bonus of removing the 4th item rather than a deliberate layout fix.

Verified live: checkbox absent from both forms on local DEV and
`mesflow.net` after promotion, no console errors, sibling controls
("Giới hạn đầu vào" OP-nguồn select enable/disable) still work, Template
save still works. Backend/API untouched — pure frontend-form change.

### Deploy

- **local DEV** — `71.0.0.215`, healthy.
- **`mesflow.net`-host** — `71.0.0.215`, healthy, live-verified (checkbox
  confirmed absent from the real Template editor).
- **`prod.mesflow.net:8299`** — `71.0.0.215` via `scripts/deploy.sh
  prodtest 71.0.0.215` — `== DEPLOY PASS ==`, digest verified,
  `migration_changed: 0`.

All three environments' `app.js` hash-match exactly
(`c4e646c3a58e611b9238ec194b78da62`). Full pytest regression suite + 88
Playwright e2e specs in the isolated QA sandbox: `QA_STATUS=PASS`,
`FAILED_STEP=none`, 7/7 checks green.

### Commits (part 3)

- `41c88a7` — `feat(operations): remove 'NG tiêu hao đầu vào' toggle, always true now`
- `4bde9f5` — `chore: bump version to 71.0.0.215 for NG-consume-input toggle removal`
- Merged to `main` (fast-forward, `5d0f4af..4bde9f5`), pushed to `origin/main`.
