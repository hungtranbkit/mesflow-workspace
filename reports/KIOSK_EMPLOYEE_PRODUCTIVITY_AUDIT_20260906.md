# Audit: Kiosk Năng suất nhân viên — UI, tutorial coverage, docs — 2026-09-06

Task: kiểm tra lại đầy đủ tính năng "Kiosk năng suất nhân viên" và
coverage của nó trong video hướng dẫn + tài liệu requirement, xác minh
thật qua code/UI/manifest/script/docs, không giả định từ tên chapter.

## 0) Trước audit: chính xác thiếu gì (kết luận nêu trước khi liệt kê chi tiết)

- Video: hành vi "tự động chuyển trang qua nhiều nhân viên" chỉ được
  **kể bằng lời**, chưa bao giờ có bằng chứng thật trong bản ghi — với
  cấu hình mặc định (20 NV/trang) và dữ liệu tutorial (~16 NV/14 ngày),
  `wallboard-employee-productivity.js` không bao giờ bật timer chuyển
  trang (`totalPages<=1`), xác nhận qua đọc code.
- Narration cũ ở tour nói "3 nhóm" trong khi UI thật đã là **2 nhóm**
  từ commit `2595925` (05/09) — lệch do quên cập nhật sau lần regroup.
- 3 trạng thái đặc biệt của wallboard (chưa cấu hình / 0 dữ liệu khớp /
  mất kết nối) đã code đúng nhưng **0 test tự động** nào từng xác nhận,
  dù `MESFLOW_MASTER_REQUIREMENTS(_VI).md` ghi rõ "Lỗi: chưa xác nhận
  N/A" và `tutorial/coverage-matrix.json` lại claim `"empty_state"` đã
  coverage cho feature này — mâu thuẫn cụ thể giữa 2 tài liệu, đã đối
  chiếu bằng cách đọc cả file test lẫn source trước khi kết luận.
- Acceptance criterion cho auto-page-flip trong REQ-KIOSK-004 mơ hồ
  ("chu kỳ tự lật trang cấu hình được") — không đủ cụ thể để QA độc lập
  tự sinh testcase mà không phải tự đọc code.
- Cross-reference "REQ-KIOSK-003 (nhiều-nhân-viên-nối-tiếp)" trong
  REQ-KIOSK-004 dễ đọc nhầm thành cùng một cơ chế — thật ra REQ-KIOSK-003
  là kiosk thao tác thật ngoài xưởng (nhiều công nhân quét thẻ nối
  tiếp), khác hoàn toàn cơ chế auto-flip của wallboard.

**Không có gap nào ở RBAC hay validation** — cả hai đã có 23 test
integration + đã tài liệu hóa đầy đủ, chi tiết ở §3.

## 1) UI thật: 3 màn hình khác nhau, không được nhầm lẫn

| Màn hình | Route | File chính | Auth | Mục đích |
|---|---|---|---|---|
| Kiosk thao tác (operator) | `/kiosk` | `kiosk.html`, `kiosk_v2.py` | thiết bị (device token), không phải user login | Quét thẻ, Start/Finish session tại trạm sản xuất thật |
| Báo cáo Năng suất nhân viên (admin) | `/app?page=employee-productivity` | `static/pages/employee-productivity.js` | user login, quyền `session.view` | Bảng xếp hạng + chi tiết cho quản lý xem/phân tích, có panel cấu hình Kiosk trình chiếu |
| **Kiosk năng suất nhân viên (wallboard)** | `/kiosk/employee-productivity` | `templates/wallboard_employee_productivity.html` + `static/wallboard-employee-productivity.js` | **KHÔNG xác thực** (cố ý — TV treo tường xưởng) | Trình chiếu liên tục, tự làm mới, tự chuyển trang qua nhiều nhân viên |

"Kiosk năng suất nhân viên" mà task hỏi chính là hàng thứ 3 — một
**wallboard/slideshow công khai**, khác hẳn kiosk thao tác (hàng 1,
dùng cho quét thẻ/session) và khác màn quản trị (hàng 2, chỉ có quản lý
đăng nhập mới thấy). 2 nút trên màn quản trị:

| Nút | Hành vi thật (đọc code `employee-productivity.js`) |
|---|---|
| **Xem trước** | `window.open('/kiosk/employee-productivity?preview=1&...', '_blank')` — dùng đúng filter/cấu hình ĐANG CHỈNH, gọi endpoint xác thực `/api/reports/employee-productivity`, KHÔNG lưu gì. |
| **Trình chiếu trên Kiosk** | `POST /api/reports/employee-productivity/wallboard-config` — lưu thật cấu hình; đây chính là cái `/kiosk/employee-productivity` (không `?preview`) đọc qua `/api/wallboard/employee-productivity`. |

Cấu hình hiển thị/tự động hóa (đã audit và regroup ở task trước, không
đổi lại lần này): sắp xếp, số nhân viên/trang (10/12/16/20/24/30), số
cột (auto/1/2/3), tự động dùng "đầu tháng→hôm nay", **tự động chuyển
trang** + chu kỳ (5/10/15/30 giây), làm mới dữ liệu (giây).

## 2) Wallboard công khai — cơ chế multi-employee thật (đọc
`wallboard-employee-productivity.js`)

- Mỗi trang hiển thị `employees_per_page` thẻ nhân viên (`.wb-card`)
  dạng lưới 1–3 cột.
- Khi tổng nhân viên có dữ liệu > `employees_per_page`: **tự động** gọi
  `setInterval` chuyển sang trang kế tiếp mỗi `auto_page_flip_seconds`
  giây — đây chính là hành vi "trình chiếu qua nhiều nhân viên" thật.
- Khi tổng nhân viên ≤ `employees_per_page` (ví dụ mặc định 20 nhân
  viên/trang mà xưởng chỉ có 16 người có dữ liệu): timer **không bật**
  — tất cả hiện trên 1 trang, không có gì để chuyển. Đây là hành vi
  ĐÚNG theo thiết kế, không phải bug, nhưng có nghĩa: nếu quay video
  bằng đúng cấu hình mặc định + dữ liệu tutorial hiện có, sẽ **không
  bao giờ** thấy auto-flip xảy ra trong bản ghi (xem §4, đây chính là
  gap đã tìm thấy và sửa).
- Nhân viên nghỉ việc: KHÔNG có badge/trạng thái riêng — do dùng chung
  công thức REQ-PROD-001 (chỉ hiện nhân viên có session `CLOSED` trong
  khoảng đang xem, JOIN với `work_sessions`), một người đã nghỉ nhưng
  có lịch sử làm việc trong khoảng đang xem vẫn xuất hiện đúng dữ liệu
  lịch sử của họ — đúng thiết kế, không phải thiếu tính năng.
- 3 trạng thái đặc biệt (chưa cấu hình / 0 dữ liệu khớp / mất kết nối):
  đã code đúng từ trước, chi tiết bảng coverage §5.

## 3) RBAC — đã tài liệu hóa đầy đủ, xác nhận qua test thật

| Hành động | Ai được phép | Nguồn xác nhận |
|---|---|---|
| Xem trạng thái cấu hình hiện tại (`GET wallboard-config`) | Mọi role có `session.view` (cả 6 role) | `@login_required`, `REQ-PROD-001` |
| Publish cấu hình (`POST wallboard-config`, tức "Trình chiếu trên Kiosk") | **Chỉ admin, manager** | `@roles_required('admin','manager')`, `test_publish_forbidden_for_viewer_role` (403 xác nhận cụ thể cho viewer) |
| Xem dữ liệu wallboard công khai + trang `/kiosk/employee-productivity` | **Không cần đăng nhập** (cố ý, TV xưởng) | `test_public_wallboard_data_requires_no_auth` |

23 test integration (`tests/integration/test_employee_productivity_wallboard.py`)
đã cover đầy đủ 7 case validate publish (fixed-mode-thiếu-ngày,
from-sau-to, sort-không-xác-định, page-size/employees_per_page/columns/
auto_page_flip_seconds ngoài khoảng hợp lệ) + persist + RBAC — không có
gap nào ở phần này, không cần thêm gì.

## 4) Tutorial video — trước/sau

Video liên quan: `10_employee_productivity.mp4` (chapter thứ 10/15,
tên "Năng suất nhân viên" — không có chapter riêng tên "Kiosk năng
suất nhân viên", tính năng này là PHẦN CUỐI của chapter báo cáo, đúng
như `REQ-KIOSK-004` đã ghi "P0 — đây chính là chủ đề chương video
hướng dẫn bắt buộc").

| | Trước audit | Sau audit |
|---|---|---|
| Mở đúng UI Xem trước (`?preview=1`) | ✔ đã có từ trước | không đổi |
| Mở đúng UI Kiosk công khai thật (không `?preview`) | ✔ đã có từ trước | không đổi |
| Narration mô tả đúng số nhóm cấu hình | ✗ nói "3 nhóm", UI thật là 2 (lệch từ 05/09) | ✔ sửa đúng "2 nhóm" |
| **Bằng chứng thật auto-chuyển-trang qua nhiều nhân viên** | ✗ chỉ kể bằng lời, không có trong bản ghi (totalPages luôn ≤1 với cấu hình/dữ liệu mặc định) | ✔ chọn 10 NV/trang + 5s/trang **trên chính UI thật**, chờ đúng 1 chu kỳ, xác nhận `#wbPageIndicator` đổi giá trị — cả ở Xem trước lẫn Kiosk công khai thật, rồi khôi phục lại 20/10s để không để lại cấu hình "demo" trên Kiosk thật |
| Thời lượng | 7m 23s | **9m 9s** |

Test evidence (Playwright thật, không phải log giả định):
- `MODULE=employeeProductivity`, tốc độ thật (`tutorial.config.json`
  gốc, không chỉnh sửa), chống DEMO `127.0.0.1:8081`: **12 bước, 0
  bug**, `TUTORIAL_QA_REPORT status=passed`.
- Xác nhận riêng bước "Đã tự chuyển sang trang khác" **passed** — nghĩa
  là `#wbPageIndicator` đổi giá trị thật giữa lúc chờ, không phải giả
  định.
- Sau khi chạy xong, đọc lại cấu hình publish thật trên DEMO qua API:
  `employees_per_page=20, auto_page_flip_seconds=10` — xác nhận bước
  khôi phục hoạt động đúng, không để lại tác dụng phụ "demo" trên Kiosk
  công khai thật.

Publish: video mới copy vào cả
`/home/dell/deploy/mesflow-demo/runtime/tutorials/` và
`/home/dell/deploy/mesflow-prodtest/runtime/tutorials/`,
`manifest.json` cập nhật duration; verify qua `GET /api/tutorials`
(có đăng nhập) trên cả 2 môi trường: **đúng 15/15**, thứ tự 00–14
nguyên vẹn.

Không đổi bất kỳ file `app/mesflow/**` nào — toàn bộ sửa lần này nằm ở
`tests/e2e/tutorial-detailed.spec.js` (script tour) — nên **không cần
build/deploy version mới**, không qua QA gate release (đúng theo mục 7
của yêu cầu: chỉ áp dụng khi sửa app).

## 5) Bảng COVERAGE

| Feature | UI route/component | Requirement IDs | Tutorial chapter | Test coverage | Verdict |
|---|---|---|---|---|---|
| Wallboard công khai — số liệu khớp báo cáo xác thực | `/kiosk/employee-productivity` → `/api/wallboard/employee-productivity` | REQ-KIOSK-004 | 10_employee_productivity (Xem trước + Kiosk thật) | `REQ-KIOSK-004` executable (docs/qc), 23 integration test, 8 Playwright test gốc | **COVERED** |
| Auto-chuyển-trang qua nhiều nhân viên | `.wb-list`/`#wbPageIndicator`, `state.pageTimer` | REQ-KIOSK-004 (mục Luồng chính, đã làm rõ) | 10_employee_productivity — **đã sửa lần này**, có bằng chứng thật (`#wbPageIndicator` đổi giá trị) | Playwright `employee-productivity-wallboard.spec.js` ("auto flip uses the configured interval...", "page flip pauses on interaction...") + video giờ có bằng chứng thật | **COVERED** (trước audit: PARTIAL — có test unit/mock nhưng video chưa chứng minh) |
| Cấu hình hiển thị (sort/số NV/trang/số cột) | `.wallboard-group` (2 nhóm) | REQ-PROD-002 | 10_employee_productivity | `test_publish_rejects_invalid_*` (4 case), Playwright cột/AUTO-column | **COVERED** |
| "Xem trước" vs "Trình chiếu trên Kiosk" — 2 hành vi khác nhau | `#epWbPreview`, `#epWbPublish` | REQ-PROD-002 (Ranh giới), REQ-KIOSK-004 (Ranh giới) | 10_employee_productivity | `test_case5_preview_style_report_call_does_not_mutate_published_config` | **COVERED** |
| RBAC publish (chỉ admin/manager) | `POST wallboard-config` | REQ-PROD-002 | không diễn giải bằng lời trong video (chỉ demo với admin) | `test_publish_forbidden_for_viewer_role` | **COVERED** (test), **PARTIAL** (video — không demo case bị từ chối, chấp nhận được vì đây là happy-path tutorial, không phải video RBAC) |
| Trạng thái chưa cấu hình (`configured=false`) | `#wbEmpty` | REQ-KIOSK-004 (Lỗi/trạng thái đặc biệt — **mới bổ sung**) | không có trong video (không hợp lý để demo — sẽ phải hủy publish thật) | **Mới thêm**: `tests/e2e/employee-productivity-wallboard.spec.js` — "never-published wallboard shows..." | **COVERED** (trước audit: MISSING test, dù đã code đúng) |
| Trạng thái 0 dữ liệu khớp bộ lọc | `#wbEmpty` | REQ-KIOSK-004 (mới bổ sung) | không có trong video | **Mới thêm**: "...zero matching employees shows the empty-data message..." | **COVERED** (trước: MISSING) |
| Trạng thái mất kết nối khi đang trình chiếu | `#wbConnState` | REQ-KIOSK-004 (mới bổ sung) | không có trong video | **Mới thêm**: "...failed refresh shows a connection-lost banner..." | **COVERED** (trước: MISSING) |
| Nhân viên nghỉ việc / dữ liệu bất thường | (không có UI riêng — dùng chung công thức REQ-PROD-001) | REQ-PROD-001 (Ranh giới), REQ-KIOSK-004 (mới ghi rõ: đúng thiết kế) | Không đề cập trực tiếp trong video (đã có card "Lưu ý khi đọc năng suất" nói chung về session không hợp lệ) | `REQ-PROD-001-EMPTY` executable + test | **COVERED** (là hành vi đúng theo thiết kế, không phải thiếu, đã ghi rõ trong doc lần này để tránh hiểu nhầm là gap) |
| Nhầm lẫn REQ-KIOSK-003 vs REQ-KIOSK-004 khi đọc doc | — | REQ-KIOSK-004 (mục Liên quan — **đã sửa**) | N/A (vấn đề tài liệu, không phải UI) | N/A | **FIXED** (doc-only) |

## 6) File đã sửa + commit hash

Repo `mesflow` (`app` — inner):
- `tests/e2e/employee-productivity-wallboard.spec.js` — +3 test (not-configured/empty-data/connection-lost).
- `tests/e2e/tutorial-detailed.spec.js` — sửa narration "3 nhóm"→"2 nhóm", thêm minh họa auto-page-flip thật + khôi phục cấu hình.
- `docs/MESFLOW_MASTER_REQUIREMENTS_VI.md`, `docs/MESFLOW_MASTER_REQUIREMENTS.md` — làm rõ REQ-KIOSK-004 (Lỗi/trạng thái đặc biệt, Luồng chính, Liên quan).
- `docs/qc/MESFLOW_QC_EXECUTABLE_REQUIREMENTS.md` — thêm `REQ-KIOSK-004-STATES`.

Commit: `786a447` (test), `a4ebc92` (docs) — đã merge `--ff-only` vào
`main`, đã push `origin/main`. Không có commit nào ở repo `app` liên
quan tới thay đổi ứng dụng thật (0 file `app/mesflow/**` bị đổi).

## 7) SPEC-GAP / OPEN QUESTION còn lại (không đoán, ghi rõ để theo dõi)

- **SPEC-GAP-001 — ĐÃ ĐÓNG (2026-09-06, cùng ngày)**: theo yêu cầu
  người dùng, đã thêm cảnh RBAC-403 thật vào chapter 12 "Người dùng &
  phân quyền" (không phải chapter Kiosk năng suất — đúng và hợp lý hơn
  vì đây là chủ đề chung của RBAC, không riêng wallboard). Chuyển thật
  sang role Viewer (`test_auto_login`, đã bật trên DEMO, tự tắt/cảnh báo
  trên production), chứng minh cả 2 lớp: (1) mục "Người dùng" biến mất
  khỏi menu + mở thẳng vẫn bị chặn "Không có quyền truy cập"; (2) gọi
  thẳng `/api/users` bỏ qua UI vẫn nhận `403`. Cả 3 điểm đều có
  **assertion cứng** (`expect(...).toHaveCount(0)`, `.toContainText(...)`,
  `.toBe(403)`), không chỉ hiển thị chữ trong video — nếu quyền
  `users.view` từng bị cấp nhầm cho Viewer trong tương lai, chính video
  test này sẽ FAIL, không chỉ đổi lời thoại. `users.view`/`users.manage`
  xác nhận là cặp quyền DUY NHẤT chỉ admin có (grep
  `app/mesflow/db/repositories/rbac.py`), nên đây là ví dụ 403 "sạch"
  nhất có thể minh họa bằng đúng role "Viewer: chỉ xem" chapter đã giới
  thiệu. Commit `f77b9bd`. Video `12_users_permissions.mp4`: 1m30s →
  **2m28s**, verify lại 15/15 trên cả DEMO và PRODTEST sau publish.
- **SPEC-GAP-002**: chưa xác nhận độc lập biến môi trường chính xác
  đứng sau `idle_timeout_minutes`/`kiosk_idle_timeout_minutes` ở
  `session_timing` trong `RBAC_MAP.yaml` — không liên quan trực tiếp
  tới audit lần này (đã ghi từ trước, không phải phát hiện mới), nêu
  lại để không bị quên khi có phiên audit RBAC toàn diện sau này.

## 8) Không nằm trong phạm vi audit này

Không đụng `mesflow.net` (origin thật chưa xác định, theo đúng ràng
buộc). Không thêm feature mới ngoài phạm vi kiosk năng suất/tutorial/
docs. Không đổi số lượng 15 chapter — vẫn giữ nguyên chapter 10 duy
nhất, chỉ làm video đó dài hơn và đúng hơn.
