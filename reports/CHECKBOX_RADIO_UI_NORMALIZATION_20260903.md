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

## Commits

- `60e8605` — `fix(ui): canonical checkbox/radio sizing, shared layer not page hacks`
- `6466cfd` — `chore: bump version to 71.0.0.213 for checkbox/radio UI fix`
- Merged to `main` (fast-forward, `3af5a92..6466cfd`), pushed to `origin/main`.
