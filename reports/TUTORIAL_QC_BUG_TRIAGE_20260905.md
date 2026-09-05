# Tutorial QC Bug Triage & Fix — 2026-09-05

Task: xử lý lỗi QC đã báo ở `/app` (14 `TUTORIAL_QA_BUG` phát hiện được
từ lần chạy đầy đủ 15 video hướng dẫn trước đó — file
`reports/TUTORIAL_VIDEO_PIPELINE_RECOVERY_20260905.md` phần log gốc),
chạy test xác nhận, sau đó để một agent độc lập kiểm tra lại.

**Kết luận quan trọng nhất: cả 14 phát hiện đều là lỗi trong chính
script test/tutorial (`tests/e2e/tutorial-detailed.spec.js`), KHÔNG
phải lỗi UI/nghiệp vụ thật của MESFlow.** 0 dòng code ứng dụng
(`app/mesflow/**`) bị đổi. Vì vậy không có bản build/deploy mới nào
cần thiết cho task này — không có `VERSION.txt`/`release.json` mới.

## 1) Bảng triage đầy đủ 14 phát hiện

| step_id | Mã lỗi gốc | Nguyên nhân thật (đọc source xác nhận) | Fix |
|---|---|---|---|
| material-01 | TUTORIAL_SELECTOR_NOT_FOUND | Selector `.toolbar` — trang `production-schedule` dùng `MFUI.filterBar` → class thật `.ui-filter-bar` | Đổi selector |
| material-02 | TUTORIAL_SELECTOR_NOT_FOUND | Selector `.panel, .material-flow, .schedule` không khớp gì — markup thật là `#scheduleBody .gantt-wrap` | Đổi selector |
| material-03 | TUTORIAL_SELECTOR_NOT_FOUND (ban đầu) | Selector `.op-dual-progress, .op-progress-line` chỉ tồn tại ở Dashboard, không có ở trang này | Đổi sang `.gantt-row` → **phát sinh lỗi mới** (xem §2) → sửa tiếp thành `.gantt-label` |
| exceptions-01 | TUTORIAL_SELECTOR_NOT_FOUND | Selector `.panel, .exception-card, table` — class thật của mỗi ngoại lệ là `.ec-card` trong `#ecList` (`exception-center.js`) | Đổi selector |
| exceptions-02 | (đã pass, nhưng dùng `.toolbar` sai giống các trang khác) | `.toolbar` → `.ui-filter-bar` | Đổi selector (phòng ngừa, đồng bộ) |
| employees-01 | (tương tự) | `.toolbar` → `.ui-filter-bar` (`app.js renderEmployees`) | Đổi selector |
| employees-02 | TUTORIAL_OVERLAY_COVERS_TARGET | Selector `.panel, table` khớp đúng `<table>` thật nhưng **toàn bộ bảng** cao hơn viewport → panel chú thích cố định không thể tránh đè lên | Bỏ `.panel` chết (không tồn tại trên trang này), và sửa gốc ở `note()` (xem §3) |
| employees-03 | (tương tự) | `.toolbar` → `.ui-filter-bar` (`qr-print.js`) | Đổi selector |
| logs-01 | (tương tự) | `.toolbar` → `.ui-filter-bar` (`system-logs.js`) | Đổi selector |
| logs-02 | TUTORIAL_OVERLAY_COVERS_TARGET | `.panel, table` khớp đúng `<table>` Action Log, cùng nguyên nhân với employees-02 | Sửa gốc ở `note()` (xem §3) |
| kioskAdmin-03 | TUTORIAL_OVERLAY_COVERS_TARGET | `#kmList` khớp đúng nhưng chứa toàn bộ lưới `.kiosk-card`, cao hơn viewport | Sửa gốc ở `note()` (xem §3) |
| dashboard-07 | TUTORIAL_OVERLAY_COVERS_TARGET | `#sessionTimeline` khớp đúng nhưng chứa toàn bộ `.employee-day-row`, cao hơn viewport | Sửa gốc ở `note()` (xem §3) |
| dashboard-04 | TARGET_NOT_VISIBLE | **Race điều kiện thật** giữa `note()` và bộ đếm tự làm mới 10 giây của Dashboard (`dashboardTimer=setInterval(...,10000)`) — xem §4 | Sửa `note()` tự phục hồi khi bị làm mới giữa chừng |
| dashboard-06 | TARGET_NOT_VISIBLE | Cùng nguyên nhân race với dashboard-04 | Cùng fix §4 |

## 2) Phát hiện phụ khi tự sửa: `display:contents` luôn có rect 0×0

Khi thử đổi material-03 sang `.gantt-row` (con trực tiếp của
`.gantt-wrap`, tưởng là đúng), test báo lỗi MỚI:
`TARGET_NOT_VISIBLE,TARGET_OUTSIDE_VIEWPORT,TARGET_COVERED` với
`rect:{x:0,y:0,width:0,height:0}`. Đọc `ui.css` xác nhận:
`.gantt-row{display:contents}` — theo đặc tả CSS, phần tử
`display:contents` **không tự vẽ box nào cả** (chỉ con của nó vẽ), nên
`getBoundingClientRect()` của nó luôn là `0×0`, bất kể có bao nhiêu
Operation đang hiển thị bên trong. Đây không phải race/timing — là một
sự thật CSS tất định, xác nhận bằng cách đọc `ui.css` chứ không đoán.
Sửa bằng cách trỏ vào `.gantt-label` (con thật, có box, đúng nội dung
"`x% · done/planned SP`" — khớp ý narration "so sánh thời gian với sản
phẩm").

## 3) Root cause chung cho 4/14 phát hiện: `note()` không có fallback
chung khi target quá lớn

`note()` có sẵn một cơ chế "thu nhỏ" khi target chiếm >55% diện tích
viewport — nhưng danh sách class con được thử chỉ có
`.quantity-summary,h1,h2,.screen-copy,.status-card` (dành riêng cho
màn Kiosk cũ). Khi trỏ vào bất kỳ danh sách/bảng không phân trang nào
khác (`#sessionTimeline`, `<table>` nhân viên, `#kmList`, `<table>`
Action Log), không class nào trong danh sách đó khớp → toàn bộ khối
(cao hơn viewport) trở thành target → panel chú thích cố định vị trí
trên màn hình **không thể** tránh đè lên một rect cao hơn cả màn hình.

**Fix tận gốc** (`tests/e2e/tutorial-detailed.spec.js`, hàm `note()`):
thêm fallback tổng quát `tr, li, article` (hàng bảng, mục danh sách,
thẻ card) khi danh sách class cũ không khớp — hoạt động cho MỌI trang
tương lai có cùng tình huống, không cần thêm 1 class riêng mỗi lần.

## 4) Root cause dashboard-04/06: race thật với auto-refresh 10 giây

Ban đầu tôi nghi đây chỉ là "flake" một lần vì chạy lại ở tốc độ nén
(để kiểm tra nhanh) không tái hiện được. **Chạy lại đúng ở tốc độ thật
(tutorial.config.json gốc, không chỉnh sửa) thì tái hiện 100% (nhất
quán ở cả 2 lần thử)** — kết luận ban đầu "flake, không cần sửa" là
**sai**, đã tự phát hiện và sửa lại đúng trước khi báo cáo, không báo
cáo kết luận sai cho user.

Nguyên nhân thật: `note()` đánh dấu target bằng `dataset` attribute,
chờ `pause_before_step_ms` (1200ms ở tốc độ thật), rồi mới tìm lại
bằng chính attribute đó để gắn class `.__tutorialFocus`. Dashboard có
`dashboardTimer=setInterval(()=>load(true),10000)` (10 giây) — trong
1200ms chờ đó, một lần làm mới hợp lệ có thể render lại toàn bộ
`#dailyKpis`/`#opTimeProgress`, phá hủy đúng phần tử vừa đánh dấu
trước khi kịp gắn highlight. Đây là hành vi auto-refresh THẬT của app
(đúng, cần thiết cho một dashboard theo dõi thời gian thực), không
phải lỗi UI.

**Fix**: nếu không tìm lại được phần tử theo `dataset` attribute (bị
làm mới đè mất), `note()` tự động chạy lại đúng selector gốc để tìm
phần tử mới thay vì báo lỗi giả `TARGET_NOT_VISIBLE`.

## 5) Bằng chứng test — chạy 2 lần độc lập

**Lần 1 (tốc độ nén, để lặp nhanh khi sửa):** material, exceptions,
employees, logs, kioskAdmin đều pass 0 bug ngay; dashboard cũng pass 0
bug ở tốc độ nén (dẫn tới kết luận tạm sai ở §4).

**Lần 2 (tốc độ THẬT — `tutorial.config.json` gốc, không chỉnh sửa,
đúng nhịp dùng khi render video thật):**

| Module | Bước | Bug |
|---|---|---|
| material | 3 | 0 (sau khi sửa `.gantt-row`→`.gantt-label`) |
| exceptions | 2 | 0 |
| employees | 3 | 0 |
| logs | 2 | 0 |
| kioskAdmin | 4 | 0 |
| dashboard (trước fix §4) | 7 | **2** (dashboard-04, dashboard-06 — tái hiện đúng như báo cáo gốc) |
| dashboard (sau fix §4, chạy lại 3 lần liên tiếp) | 7×3 | **0×3** |

Tất cả chạy trên DEMO (`127.0.0.1:8081`, image `71.0.0.224`) qua
Playwright thật (`tests/e2e/tutorial-detailed.spec.js` +
`playwright.tutorial-detailed.config.js`), không phải log giả định.

## 6) File thay đổi

`mesflow/tests/e2e/tutorial-detailed.spec.js` — 2 commit:
- `47613a8` — 12 selector fix + fallback `tr, li, article` chung cho
  target quá lớn.
- `5f790ba` — fallback tự phục hồi trong `note()` khi target bị
  auto-refresh phá hủy giữa chừng.

Không đổi file nào khác — 0 thay đổi `app/mesflow/**`, `ui.css`,
migration, hay cấu hình deploy. Không cần build/deploy phiên bản mới.

## 7) Bàn giao kiểm tra độc lập

Theo yêu cầu, sau khi tự chạy test xác nhận, task này được bàn giao
cho một agent độc lập (không kế thừa ngữ cảnh phiên làm việc này) để
tự chạy lại các module bị ảnh hưởng và xác nhận độc lập trước khi coi
là hoàn tất — vì đây là thay đổi thuần script test (0 thay đổi code
ứng dụng), không có phiên bản build mới nào để đưa qua pipeline QA
Center (`qa-center/`, vốn gate các bản release ứng dụng, không áp dụng
cho thay đổi này) — nên bước "qa- kiểm tra độc lập" được thực hiện
bằng một agent con độc lập chạy lại chính bộ test trên, xem kết quả ở
mục cuối báo cáo tổng kết gửi user.
