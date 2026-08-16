# MESFlow Industrial UI Standard v1

This standard applies to MESFlow web/admin UI.

Reference model:
- IBM Carbon: enterprise structure, dense data, filters, tables, status
- Ant Design: practical admin/forms/data workflows
- Impeccable-style visual discipline: hierarchy, typography, spacing, visual polish, avoid AI-generic UI
- Nielsen heuristics: clear workflow, feedback, error prevention, recovery
- WCAG 2.2: accessibility, contrast, keyboard/focus, labels, non-color-only states
- MESFlow industrial rules: Full HD first, high information density, fast scanning, sticky production context, Vietnamese terminology, minimal clicks

These are references, not templates. MESFlow keeps its own design language.

## Product context
MESFlow is an industrial production-management application, not a marketing site. Optimize for supervisors, QA, admins, production support, and managers.

## Primary viewport
Primary: 1920x1080. Also verify 1600x900, 1366x768, 1024x768, 390x844.

## Global layout
- Avoid giant SaaS cards and useless whitespace.
- Prefer compact information-rich sections.
- Keep page headers moderate in height.
- Keep important production context visible.
- Use sticky filters/context when useful.
- Long lists should scroll in their own region where practical.
- Avoid horizontal scrolling for normal workflows.

## Information hierarchy
Clearly distinguish page identity, production context, primary action, critical status, main data, metadata, secondary actions, diagnostics.

## Typography
Use a consistent scale for page title, section title, list/card title, body, labels, helper/meta, KPI, badge/status. Do not shrink text just to fit overcrowded layouts.

## Spacing
Prefer a small consistent scale such as 4/8/12/16/20/24/32. Dense does not mean cramped.

## Surfaces / rows
Do not turn every section into a floating card. Use borders/background/spacing selectively. Selected, hover, focus and warning states must be obvious.

## Tables
Use tables for true comparison. Avoid them when too many columns, deep per-row actions, or lost context make them hard to use. Prefer master/detail for complex review flows.

## Master/detail
Preferred for Session Exceptions, complex Session review, and operational workflows needing many details/actions. Master is compact/searchable/scrollable; detail is contextual and sticky on desktop when useful.

## Forms
Explicit labels, clear required fields, nearby helper/error text, obvious primary action, separated dangerous actions, internal modal scrolling when needed.

## Filters
Compact, context-preserving, low-height, with obvious reset/clear behavior where useful.

## Semantic status
Use consistent success/running/info/warning/error/critical/neutral/disabled semantics. Important state must include text/icon/label, not color alone.

## Progress
Time progress and product/output progress must be visually distinct by color, label, icon, fill treatment, or numeric context.

## Navigation
Predictable grouping, obvious current page, Help/Tutorial at the end.

## Vietnamese terminology
Prefer user-facing Vietnamese. Examples: Session -> Phiên làm việc; Production Order -> Lệnh sản xuất; Template -> Mẫu quy trình; Material Flow -> Dòng vật tư. Do not rename backend/API enums only for localization.

## Session Exception screen
Treat it as an actionable queue, not a report table: Nhận xử lý -> Mở đúng Session -> Kiểm tra bằng chứng -> Sửa dữ liệu thật nếu cần -> Lưu/tính lại -> Quay lại -> Hoàn tất/Bỏ qua có lý do. User must immediately know lỗi gì, Session nào, nhân viên nào, công đoạn nào, phải làm gì tiếp theo.

## Nielsen-style checks
Every major flow should answer: What state am I in? What just happened? What can I do next? Can I recover? What happens if I leave? Is this destructive?

## WCAG 2.2 quality gate
At minimum verify readable contrast, visible focus, keyboard-operable controls where practical, form labels, meaningful button text, non-color-only status, reasonable hit areas, modal focus/escape behavior, zoom/text scaling.

## Anti-patterns
Avoid AI-generic dashboards, oversized rounded cards everywhere, excessive shadows/gradients/emoji/badges/colors, huge whitespace, microscopic text, wide tables requiring horizontal scroll, overlapping sticky elements, duplicate CSS patterns, and business-logic changes disguised as UX work.

## Screenshot audit
For global work, capture major screens at 1920x1080 and responsive samples at 1366x768 and 390x844 for important screens.

## Audit before refactor
1. inventory screens/components
2. document problems
3. identify shared patterns
4. propose batches
5. refactor common tokens/components
6. refactor screens in batches
7. screenshot audit
8. focused regression

## Recommended batches
Batch 1: design tokens, typography, navigation, common cards/panels/forms/status.
Batch 2: Dashboard, Lệnh sản xuất, Mẫu quy trình, Dòng vật tư.
Batch 3: Phiên làm việc, Phiên làm việc bất thường, Nhân viên, Kiosk Admin.
Batch 4: Lịch làm việc, Người dùng/quyền, Logs, Tutorial, responsive sweep.

## Evidence required
A UI change is not complete just because it builds. Verify syntax, focused tests, browser render, console, overflow, interaction flow, responsive screenshots, and no accidental API/business logic changes.

## Reporting
Global UI work must produce `reports/UI_AUDIT.md` and `reports/UI_REFACTOR_REPORT.md` with screens reviewed, issues found, global/per-screen changes, components consolidated, responsive results, console results, tests, files changed, version, migration, known issues, not verified, production action required.
