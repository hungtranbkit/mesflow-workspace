# Kiosk Wallboard Panel — Redesign 3 nhóm theo chức năng — 2026-09-07

Task: thiết kế lại khu vực "Trình chiếu Kiosk" theo screenshot user gửi
(layout dàn ngang, khó đọc; nghi ngờ 2 nút trùng chức năng).

## 0) Phát hiện quan trọng trước khi sửa: user đang xem DEV, không phải
DEMO/PRODTEST

Audit code xác nhận `app/mesflow/web/static/pages/employee-productivity.js`
(nguồn Git, đã deploy DEMO+PRODTEST từ 05-09) đã có layout nhóm rõ ràng
và nút tên "Xem trước" (không phải "Preview màn trình chiếu"). Nhưng
DEV (`mesflow-app`, `127.0.0.1:8080`) vẫn chạy `71.0.0.219` — **chưa
bao giờ nhận bản redesign nào từ 05-09** (đúng theo phạm vi đã ghi rõ ở
báo cáo 05-09: "DEV — không đụng — ngoài phạm vi lỗi lần này"). Xác
nhận sống bằng script: DEV hiện vẫn hiện đúng "Preview màn trình chiếu"
/ "Trình chiếu trên Kiosk" và **0 nhóm cấu hình** (layout dàn hàng cũ
trước 05-09) — khớp chính xác với ảnh user mô tả. Đây là nguyên nhân
thật của sự nhầm lẫn "2 nút trùng nghĩa": tên cũ "Preview màn trình
chiếu" nghe rất giống "Trình chiếu trên Kiosk" (cùng chữ "trình
chiếu"), trong khi tên mới "Xem trước" (đã đổi từ 05-09, nhưng chưa lên
DEV) tách bạch rõ hơn nhiều.

## 1) Audit route/action của 2 nút — xác nhận KHÔNG trùng chức năng

| Nút | Route/action thật | Đặc điểm |
|---|---|---|
| `#epWbPreview` ("Xem trước") | `window.open('/kiosk/employee-productivity?preview=1&...', '_blank')` | Mở TAB MỚI, dùng filter ĐANG CHỈNH (chưa lưu), gọi endpoint xác thực `/api/reports/employee-productivity` — không đụng gì tới cấu hình đã publish |
| `#epWbPublish` ("Trình chiếu trên Kiosk") | `POST /api/reports/employee-productivity/wallboard-config` | LƯU THẬT cấu hình — đây chính là cái màn công khai `/kiosk/employee-productivity` (không cần đăng nhập) đọc qua `/api/wallboard/employee-productivity` |

Khác nhau về: HTTP method (GET đọc vs POST ghi), phạm vi tác động (ephemeral/tab riêng vs persistent/công khai toàn xưởng), và đối tượng dữ liệu (filter tạm vs config đã lưu). **Kết luận: không trùng route/chức năng → giữ nguyên 2 nút theo đúng điều kiện task đã đặt ra, không gộp.** Đã siết lại câu giải thích khác biệt ngay trong UI (`wallboard-actions-hint`) thay vì gộp.

## 2) Redesign: 3 nhóm theo ĐÚNG chức năng (không theo loại control)

| Nhóm | Field |
|---|---|
| **Dữ liệu hiển thị** | Tự động dùng đầu tháng→hôm nay · Sắp xếp · Số nhân viên/trang · Số cột hiển thị |
| **Chuyển trang** | Tự động chuyển trang · Thời gian chuyển trang |
| **Làm mới dữ liệu** | Làm mới mỗi (giây) |

Grid desktop: 2 hàng — "Dữ liệu hiển thị" (nặng nhất, 1 checkbox + 3
select) chiếm trọn hàng 1; "Chuyển trang" + "Làm mới dữ liệu" (nhẹ hơn
nhiều) chia đôi hàng 2. Dưới 900px: xếp dọc 1 cột. Mỗi checkbox nằm
đúng trong nhóm dùng nó (trước đây "Tự động hóa" gộp 2 checkbox không
liên quan trực tiếp vào 1 hàng).

CTA (`Xem trước` / `Trình chiếu trên Kiosk`) đặt riêng hẳn 1 hàng dưới
cùng 3 nhóm, không chen giữa select nào.

## 3) Dòng trạng thái — rút gọn đúng yêu cầu

Chuyển vào `content-panel-head` làm subtitle dưới tiêu đề "Trình chiếu
Kiosk" (giống mọi content-panel khác trong app), thay vì khối callout
riêng. Nội dung rút gọn từ liệt kê lại MỌI field (sort/số người/số
cột/tự động/refresh — 150-200+ ký tự) xuống chỉ còn phạm vi ngày thật
sự áp dụng (vì "đầu tháng→hôm nay" là lựa chọn động, không tự hiện ra
giá trị cụ thể như các field khác) + lần cập nhật cuối/người cập nhật:

- Trước: `Đang public: Đầu tháng → hôm nay (tự động) · Sort: Năng suất giảm dần · 20 người/trang · Tự động · Tự động chuyển trang mỗi 10s · Refresh dữ liệu: 20s · Cập nhật lần cuối: ... · Người cập nhật: admin` (~180 ký tự)
- Sau: `Đang trình chiếu: Đầu tháng → hôm nay (tự động) · Cập nhật lần cuối 20:47 06-09 bởi admin` (89 ký tự, đo thật qua Playwright)

## 4) Bug thật phát hiện khi tự test lại (không phải giả định)

Đổi chữ "Đang public" → "Đang trình chiếu" làm lộ một bug ẩn từ trước
trong `tests/e2e/tutorial-detailed.spec.js`: `page.waitForFunction(fn,
{timeout:10000})` — chữ ký thật của Playwright là
`waitForFunction(pageFunction, arg, options)`, nên `{timeout:10000}`
bị hiểu nhầm thành `arg` (tham số truyền vào hàm), KHÔNG PHẢI
`options` — timeout 10 giây chưa bao giờ thật sự có hiệu lực. Bug này
"ngủ yên" từ trước vì điều kiện chờ ("Đang public") luôn đúng gần như
ngay lập tức; đổi chữ khiến điều kiện không bao giờ đúng nữa → treo tới
đúng 20 phút (module timeout) mới bị Playwright tự kill. Xác nhận qua
`playwright-core`'s `.d.ts` thật, không đoán. Sửa cả 2 chỗ dùng đúng
pattern `waitForFunction(fn, undefined, {timeout:...})` và cập nhật lại
chuỗi cần chờ.

## 5) Test evidence

- Playwright thật (không chỉ đọc source): set field qua UI thật, "Xem
  trước" mở đúng URL với tham số sống, không đổi config đã publish;
  "Trình chiếu trên Kiosk" publish thành công (200), Kiosk công khai
  thật phản ánh ngay (10 thẻ/trang sau khi set employees_per_page=10).
- Screenshot 3 viewport (DEMO, sau khi patch): `1920x1080.png`,
  `1366x768.png`, `390x844.png` — cả 3 đều **0px tràn ngang**
  (`document.documentElement.scrollWidth - clientWidth`), label thẳng
  hàng, checkbox liền label, CTA tách riêng.
- Tutorial module `employeeProductivity` (tốc độ thật, không rút gọn):
  **lần 1: FAIL** (đúng bug §4, treo 20 phút) → sửa → **lần 2: PASS**,
  12 bước, 0 bug, 9.2 phút — bao gồm cả bằng chứng thật auto-chuyển-trang
  (đã có từ audit 06-09, không đổi lại lần này).
- Sau mỗi lần test, đọc lại config qua API xác nhận khôi phục đúng
  `employees_per_page=20, auto_page_flip_seconds=10` trên DEMO — không
  để lại cấu hình demo trên Kiosk công khai thật.

## 6) File đã sửa + commit

Repo `mesflow` (app):
- `app/mesflow/web/static/pages/employee-productivity.js` — HTML 3
  nhóm mới, `wbStateText()` rút gọn.
- `app/mesflow/web/static/ui.css` — grid 2 hàng, dọn CSS chết
  (`.wallboard-toggle-row` không còn dùng).
- `tests/e2e/tutorial-detailed.spec.js` — narration cập nhật đúng 3
  nhóm mới + sửa bug `waitForFunction` §4.
- `VERSION.txt` → `71.0.0.225`.

Commit: `9e7c1a7` (redesign chính) + `6c452e5` (sync `release.json`).
Đã push `main` cả 2 repo (`mesflow`, `mesflow-workspace`).

## 7) Build & Deploy

| | Trước | Sau |
|---|---|---|
| Image | `71.0.0.224` | **`71.0.0.225`** (commit `6c452e5`) |
| Digest | `sha256:4d8bbbf5...` | `sha256:993dabf5b48adf5dd5bf9537e435ea03e2efc2b9278f799ab81644f5768c40f9` |
| Smoke test | — | PASS, `migration_head` không đổi (`0043_super_admin_role`) |
| DEMO | 71.0.0.224 | **71.0.0.225**, recreate qua `recreate-demo.sh`, mount tutorials giữ nguyên, container cũ đổi tên backup |
| PRODTEST | 71.0.0.224 | **71.0.0.225** qua `scripts/deploy.sh` — `DEPLOY PASS` |
| Video chapter 10 | 9m9s | **9m10s** (nội dung không đổi nhiều — chỉ layout/narration nhóm), publish + verify 15/15 trên cả DEMO/PRODTEST |
| DEV (`mesflow-app`, 71.0.0.219) | không đổi | **vẫn không đổi** — xem §8 |

## 8) Việc chưa làm / cần xác nhận thêm

- **DEV vẫn chưa nhận bản redesign nào** (kể cả bản 05-09 lẫn bản hôm
  nay) — đây chính là nơi user đang xem khi báo cáo layout rối. Nếu
  muốn DEV cũng hiển thị đúng bản mới, cần một lần deploy riêng cho
  DEV (ngoài phạm vi mặc định của pipeline hiện tại, vốn chỉ target
  DEMO/PRODTEST). **Không tự làm trong task này** vì chưa có yêu cầu
  rõ ràng mở rộng phạm vi sang DEV — đề xuất xác nhận với user trước
  khi đụng vào DEV.
- `mesflow.net` vẫn ngoài phạm vi (origin thật chưa xác định) — không đụng.
