# ESP Kiosk Tutorial UI Report

Generated: 2026-08-12, Asia/Bangkok

## RESULT

PASS for the requested local UI refinement. The previously validated local tutorial build/package/upload/atomic-publish/playback pipeline remains intact. Deploy Agent now exposes a compact, independent ESP Kiosk tutorial card, and MESFlow now has one final `Hướng dẫn` navigation entry with `Hướng dẫn MESFlow` and `ESP Kiosk` sub-tabs.

No production deploy, production restart, `/opt` mutation, database write, firmware change, tutorial regeneration, or tutorial version change was performed.

## DEPLOY AGENT VERSION

`2.15.2-docker-runtime`

## MESFLOW VERSION

`65.8.44.56`

## TUTORIAL VERSION

`5.1.9.2` (unchanged)

## FIRMWARE VERSION

`ESP32-KIOSK-5.1.9-WORKER-QTY-FLOW` (unchanged)

## AGENT CARD

- Independent compact card titled `Video hướng dẫn ESP Kiosk`.
- Visually separated from MESFlow release, QA Center and Agent update areas.
- The main card does not expose a runtime filesystem path.
- Status badge reports `Ready`, `Missing`, or `Invalid` from current VERSION/manifest contract checks.

## CURRENT INFO

The card displays:

- tutorial version;
- full firmware version;
- video count;
- `Âm thanh: Không` for the current silent package;
- formatted publish/update time;
- active/package state;
- current and previous tutorial versions when the retained backup metadata is available.

Local runtime evidence reported current `5.1.9.2`, previous `5.1.9.1`, seven videos and package `ready`.

## UPLOAD UI

- Explicit `Chọn ZIP` control.
- Visible `Upload & Publish` fallback button remains available.
- Existing auto-upload behavior remains.
- Selecting a file updates the live status with filename and size in MB before upload.
- Upload errors remain visible in the status/flash area and do not remove the current package.

## PROGRESS

The Agent UI now exposes these tutorial stages:

`Đang upload -> Đang kiểm tra ZIP -> Đang kiểm tra manifest -> Đang staging -> Đang backup bản cũ -> Đang publish -> Đang xác minh -> Hoàn tất`

The backend now records `validating_manifest` separately. A failed stage records the exception class/message and the card retains the current tutorial.

Local HTTP evidence:

- obsolete/bad ZIP: job `failed`, current tutorial remained `5.1.9.2`;
- valid ZIP: job `success`, package `ready`;
- transitions included `uploading`, `validating`, `validating_manifest`, and `success` for the same-content no-op retry;
- focused atomic publish tests cover staging, backup, publishing and verification for a new version.

## VIEW LINK

- Button: `Mở hướng dẫn ESP Kiosk`.
- Default gateway-relative URL: `/app?guide=esp-kiosk`.
- Optional `WORKSHOP_MES_PUBLIC_URL` supplies an explicit configured public base URL without hard-coding a production domain.
- Browser deep-link verification opened the correct ESP Kiosk sub-tab and showed seven items.

## MESFLOW GUIDE SUBTABS

- Only one top-level navigation entry remains: `Hướng dẫn`, at the end of navigation.
- Removed the separate top-level ESP Kiosk entry.
- The Hướng dẫn screen contains:
  - `Hướng dẫn MESFlow`
  - `ESP Kiosk`
- Default is `Hướng dẫn MESFlow`.
- Both sub-tabs use the same existing tutorial viewing permission; no new permission or upload capability was added to MESFlow.

## ESP KIOSK TAB

- Header: `Hướng dẫn ESP Kiosk`.
- Shows the complete applicable firmware identifier and tutorial version.
- User-facing note: `Video được mô phỏng theo giao diện firmware ESP Kiosk hiện tại.`
- Does not expose framebuffer/generator terminology or technical filenames.
- MESFlow web tutorial items are not rendered inside the ESP Kiosk sub-tab.

## VIDEOS

Exactly seven manifest-driven tutorial entries are shown in the compact left list:

1. Tổng quan ESP Kiosk
2. Khởi động và kết nối
3. Bắt đầu phiên làm việc
4. Kết thúc: chỉ có sản phẩm đạt
5. Kết thúc: có lỗi
6. Các lỗi thường gặp
7. Mất mạng và kết nối lại

The titles remain sourced from the published manifest; no filename is shown.

## PLAYER

- Master/detail desktop layout: compact scrollable list on the left, one large player on the right.
- Only one `<video>` element exists and is active at a time.
- Selecting each item pauses the current video, changes title, description and source, then loads metadata.
- Selection does not autoplay. Playback starts only through the player controls/user action.
- Aspect ratio is fixed at 16:9 with responsive containment.
- Keyboard focus styles and selected state are visible.

## EMPTY STATE

- Missing manifest: `Chưa có video hướng dẫn ESP Kiosk được publish.`
- Invalid/unavailable manifest: `Không tải được bộ hướng dẫn ESP Kiosk. Vui lòng liên hệ quản trị viên.`
- Browser interception tests verified both states and confirmed raw backend error enums are not shown.

## CACHE

The validated strategy is unchanged:

- manifest/API: `no-cache, max-age=0, must-revalidate`;
- MP4: `public, max-age=31536000, immutable`;
- video URLs: `?v=5.1.9.2`.

Browser assertions for cache headers and versioned URLs remain passing.

## BROWSER TEST

- Dedicated Hướng dẫn/ESP tutorial test: PASS.
- One top-level Hướng dẫn entry and zero top-level ESP tutorial entries verified.
- Both sub-tabs verified.
- Seven ESP entries verified.
- Clicking all seven entries produced seven distinct player sources and updated the displayed title.
- Range request returned `200/206`; actual playback advanced `currentTime > 0`.
- Deep link `/app?guide=esp-kiosk` verified.
- Empty and invalid-manifest states verified.
- Layout overflow assertions passed at `1920x1080`, `1366x768`, and `390x844`.
- Browser page-error collection remained empty.

## REGRESSION

- MESFlow focused tests: `9 passed`.
- Deploy Agent focused tutorial tests, including card render: `3 passed`.
- MESFlow full browser regression before the final additional empty/error assertions: `7 passed`.
- Final dedicated browser test after all changes: `1 passed`.
- Agent image `2.15.2` built successfully.
- Agent actual authenticated local upload: valid package success; bad package failed while current package remained available.
- Existing MESFlow tutorial tab/search remains functional.
- MESFlow release upload, QA upload and ESP tutorial publish backend contracts were not replaced.

## FILES CHANGED

### Deploy Agent

- `deploy-agent/agent.py`
- `deploy-agent/templates/index.html`
- `deploy-agent/tests/test_esp_kiosk_tutorial_publish_v2150.py`
- `deploy-agent/VERSION.txt`
- `deploy-agent/docker/Dockerfile`
- `deploy-agent/docker/compose.linux.yml`
- `deploy-agent/docker/compose.windows.yml`
- `deploy-agent/README.md`
- `deploy-agent/docs/DEPLOY_DOCKER.md`

### MESFlow

- `mesflow/app/mesflow/web/static/app.js`
- `mesflow/app/mesflow/web/static/ui.css`
- `mesflow/app/mesflow/web/templates/app.html`
- `mesflow/tests/e2e/mesflow.spec.js`
- `mesflow/tests/test_v6584452_session_exception_history.py`
- `mesflow/tests/test_v6584453_exception_data_source.py`
- `mesflow/tests/test_v6584454_esp_kiosk_tutorial.py`
- `mesflow/VERSION.txt`
- `mesflow/app/mesflow/__init__.py`
- `mesflow/release.json`
- `mesflow/compose.yml`

Existing unrelated workspace-only Session Exception changes were preserved.

## MIGRATION

NO. No database/schema change.

## PRODUCTION ACTION REQUIRED

YES, after human review/approval only:

1. Deploy MESFlow `65.8.44.56` and Deploy Agent `2.15.2-docker-runtime` through the approved release process.
2. Verify the configured/gateway-relative `Mở hướng dẫn ESP Kiosk` link in the production gateway topology.
3. No tutorial ZIP upload is required solely for this UI change; tutorial `5.1.9.2` remains valid.

No production action was performed during this task.
