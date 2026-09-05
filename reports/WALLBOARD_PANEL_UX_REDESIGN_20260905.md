# Kiosk Wallboard Config Panel — Audit, Redesign & Video Update — 2026-09-05

Task: kiểm tra tính năng "trình chiếu" trên Kiosk năng suất nhân viên
(video hướng dẫn chưa thể hiện được), sau đó audit + redesign phần
header/control của khu "Trình chiếu Kiosk" (UI rối, trùng nghĩa theo
screenshot người dùng gửi), và update lại video hướng dẫn cho đúng.

## 1) Behavior thật của 2 nút — đọc code trước khi sửa

| Nút | Trước | Hành vi thật (đã xác nhận qua code + click test sống) |
|---|---|---|
| `#epWbPreview` | "Preview màn trình chiếu" | `window.open('/kiosk/employee-productivity?preview=1&<filter đang chỉnh>', '_blank')` — gọi `/api/reports/employee-productivity` (endpoint xác thực), dùng đúng filter CHƯA lưu trên trang. Không đụng config đã publish. |
| `#epWbPublish` | "Trình chiếu trên Kiosk" (giữ nguyên) | `POST /api/reports/employee-productivity/wallboard-config` — **lưu thật** config, đây chính là cái `GET /kiosk/employee-productivity` (không `?preview`, không cần đăng nhập) sẽ đọc từ `/api/wallboard/employee-productivity` cho TV tại xưởng. |

**Kết luận: không trùng chức năng** — giữ cả 2, chỉ đổi tên nút Preview
thành **"Xem trước"** (loại bỏ từ tiếng Anh lẫn trong UI tiếng Việt),
giữ "Trình chiếu trên Kiosk" (đã mô tả đúng hành vi), thêm dòng chú
thích phân biệt rõ 2 hành động ngay dưới 2 nút.

## 2) Root cause UI rối (đúng như ảnh người dùng gửi)

`.content-panel-actions{display:flex;flex-wrap:wrap}` — 2 checkbox, 4
select, 1 input số và 2 nút tất cả nằm chung MỘT hàng flex-wrap, không
nhóm gì cả. Checkbox "Tự động: đầu tháng → hôm nay" nằm ngay sau tiêu
đề panel (trước cả select đầu tiên); checkbox "Tự động chuyển trang"
nằm cuối hàng 1 trong khi select "Thời gian chuyển trang" liên quan
của nó lại ở hàng 2 — đúng thứ tinh thần "trộn lẫn" người dùng mô tả.

## 3) Redesign — 3 nhóm rõ ràng + hàng hành động riêng

`app/mesflow/web/static/pages/employee-productivity.js` (chỉ đổi HTML,
0 thay đổi data-binding/business logic — giữ nguyên mọi id):
- **KHOẢNG THỜI GIAN**: checkbox tự động đầu-tháng→hôm-nay + dòng chú
  thích khi tắt thì dùng đúng từ/đến ngày ở bộ lọc trên.
- **CẤU HÌNH HIỂN THỊ**: Sắp xếp | Số nhân viên/trang | Số cột | Thời
  gian mỗi trang | Làm mới dữ liệu — 1 lưới field đồng nhất.
- **TỰ ĐỘNG HÓA**: checkbox tự động chuyển trang.
- **Hàng hành động** riêng, có chú thích phân biệt Xem trước/Trình
  chiếu trên Kiosk, nút primary (xanh) rõ ràng.

`app/mesflow/web/static/ui.css`: 3 nhóm dùng `<fieldset>` + `<legend>`,
grid 3 cột ở desktop rộng, 2 cột ở tablet, 1 cột (stack) ở mobile;
mọi input/select/button dùng chung biến `--control-height` (đã có sẵn
trong hệ thống) để cùng chiều cao.

**Screenshot before/after** (lưu ở `reports/` phiên làm việc, không
đính kèm vào report này để giữ file nhẹ — xem tool output của phiên):
- 1366×768: before rối 1 hàng; after 3 khối rõ ràng + hàng nút riêng.
- 1920×1080: 3 khối nằm ngang thoải mái, không dồn.
- 390×844: 3 khối xếp dọc, nút "Xem trước"/"Trình chiếu trên Kiosk"
  full-width xếp chồng, không vỡ layout.

## 4) Test evidence

- `tests/e2e/employee-productivity-wallboard.spec.js`: **8/8 PASS**
  (chạy cả trên DEV 127.0.0.1:8080 và DEMO 127.0.0.1:8081) — spec này
  nhắm màn `/kiosk/employee-productivity` công khai, không đụng panel
  quản trị vừa sửa, xác nhận không phá gì ở đó.
- `tests/test_employee_productivity_display_settings.py`: 9/9 PASS
  (logic tính cột/trang thuần JS, không đổi).
- Click test sống (Playwright): "Xem trước" mở đúng URL
  `?preview=1&...`, render 15 thẻ nhân viên thật; "Trình chiếu trên
  Kiosk" POST thành công, `epWbState` cập nhật đúng, dữ liệu thật lên
  `/api/wallboard/employee-productivity` ngay sau đó — không lỗi
  console/JS nào phát sinh.
- Không có spec nào khác từng test cấu trúc HTML nội bộ của panel này
  trước khi sửa — không có gì để "phá" ngoài 2 spec trên.

## 5) Bug thật tìm thấy khi build lại tour video (không phải app bug —
bug trong chính script test)

Khi viết lại đoạn tour để thực sự mở màn "Xem trước" và bấm "Trình
chiếu trên Kiosk" thật (thay vì chỉ mô tả bằng lời như video cũ), phát
hiện 2 lỗi trong `tests/e2e/tutorial-detailed.spec.js`:
1. Locator gộp `'#wbList .wb-card, #wbEmpty'` rồi `.first()` — vì
   `#wbEmpty` nằm TRƯỚC `#wbList` trong HTML, `.first()` luôn trả về
   `#wbEmpty` bất kể có card thật hay không → test luôn kiểm tra nhầm
   phần tử.
2. `page.waitForFunction(...).catch(()=>{})` nuốt lỗi im lặng — nếu
   POST publish chưa xong mà đã điều hướng sang màn công khai thật, sẽ
   thấy trạng thái "chưa cấu hình" giả.

Sửa bằng `page.waitForResponse()` chờ đúng request POST publish hoàn
tất trước, và chờ trực tiếp `.wb-card` thay vì gộp selector. Chạy lại:
**10 bước, 0 bug** (trước khi sửa: phát hiện đúng 1 bug do chính lỗi
test này, không phải lỗi app).

## 6) Video hướng dẫn "Năng suất nhân viên" — cập nhật

Chỉ render lại đúng 1 chapter này (không đụng 14 video còn lại):
- Thêm 2 đoạn thật: mở "Xem trước" (điều hướng cùng trang thay vì tab
  popup — tránh xung đột với cơ chế chọn `.webm` mới nhất của
  `make-user-guide-video.sh` nếu có video riêng của tab popup), rồi
  bấm thật "Trình chiếu trên Kiosk" và mở đúng URL công khai thật
  (`/kiosk/employee-productivity`, không `?preview`) để đối chiếu.
- Thời lượng: 4m49s (gốc) → 4m42s (bản 15-video sáng nay) → **7m21s**
  (bản mới, do thêm nội dung thật).
- Publish vào cả DEMO và PRODTEST, cập nhật `duration` trong
  `manifest.json`. Đã verify qua API thật: **vẫn đúng 15/15**, thứ tự
  00–14 nguyên vẹn, không trùng/thiếu.

## 7) Build & Deploy

| | Trước | Sau |
|---|---|---|
| Image | `71.0.0.222` | **`71.0.0.223`** (commit `e32c37c`) |
| Digest | — | `sha256:2c9f10bf8f2898e13d76be2ba0aa710fa54d3d242f61ba165fb9bb8ad61c7eb3` |
| Smoke test | — | PASS, `migration_head` không đổi |
| DEMO | 71.0.0.222 | **71.0.0.223**, container recreate qua script riêng, mount `/data/tutorials` giữ nguyên, container cũ đổi tên backup (không xóa) |
| PRODTEST | 71.0.0.222 | **71.0.0.223** qua `scripts/deploy.sh` — health PASS, digest khớp, cron reconcile/log-retention verified present |
| DEV (`mesflow-app`) | không đổi | **không đụng** — ngoài phạm vi lỗi lần này |

## 8) Việc chưa làm / còn tồn đọng

- Không chụp lại screenshot UI mới trực tiếp trên PRODTEST qua trình
  duyệt: mật khẩu admin lưu trong biến môi trường của PRODTEST đã lệch
  so với DB thật (vấn đề đã ghi nhận từ trước, không phải mới) — thay
  vào đó verify bằng version/digest khớp 100% với DEMO (cùng image,
  cùng byte code).
- Không chạy được `pytest tests/` đầy đủ trên máy host của phiên này
  (thiếu `psycopg`, thiếu Postgres thật trong shell của tôi) — đây là
  giới hạn môi trường ad-hoc từ trước, không phải do thay đổi lần này
  (thay đổi lần này 0 dòng Python). Test liên quan trực tiếp
  (Playwright wallboard spec + tutorial module) đã chạy PASS đầy đủ.

## 9) Iteration 2 — Regroup theo spec tinh gọn hơn (cùng ngày, tiếp nối §1-8)

Sau khi iteration 1 (3 nhóm: Khoảng thời gian / Cấu hình hiển thị / Tự
động hóa) lên PRODTEST, người dùng yêu cầu tinh gọn thêm: gộp lại đúng
**2 nhóm**, đưa cả 2 checkbox tự động hóa (đầu-tháng→hôm-nay VÀ tự động
chuyển trang) vào chung một nhóm "Tự động hóa" trên cùng một hàng, còn
nhóm "Cấu hình hiển thị" chỉ giữ 3 trường thuần hiển thị (Sắp xếp / Số
nhân viên mỗi trang / Số cột) — không lẫn field liên quan tới auto-flip
nữa.

**Không đổi hành vi/logic** — chỉ tổ chức lại HTML/CSS, 0 id đổi, 0
event handler đổi, 0 dòng Python đổi:

| Nhóm | Trước (iteration 1) | Sau (iteration 2) |
|---|---|---|
| Cấu hình hiển thị | Sắp xếp, Số NV/trang, Số cột, Thời gian mỗi trang, Làm mới dữ liệu (5 field lẫn cả auto-flip) | **Chỉ còn 3 field thuần hiển thị**: Sắp xếp, Số NV/trang, Số cột |
| Tự động hóa | chỉ 1 checkbox "Tự động chuyển trang", đứng riêng | **Cả 2 checkbox** ("Tự động đầu-tháng→hôm-nay" + "Tự động chuyển trang") trên cùng 1 hàng (`.wallboard-toggle-row`), rồi tới field-grid (Thời gian mỗi trang, Làm mới dữ liệu), rồi dòng chú thích (chuyển từ nhóm "Khoảng thời gian" cũ sang đây vì cùng ngữ cảnh auto-flip) |
| Khoảng thời gian | 1 nhóm riêng | **Xoá nhóm riêng** — checkbox đầu-tháng→hôm-nay dồn qua nhóm Tự động hóa, không còn 3 nhóm mà đúng 2 |

File đổi: `app/mesflow/web/static/pages/employee-productivity.js` (cấu
trúc HTML panel) + `app/mesflow/web/static/ui.css` (grid 2 cột thay vì
3 cột, thêm `.wallboard-toggle-row`, xoá breakpoint 1180px không còn
cần với 2 nhóm). Commit `2595925`.

**Test evidence (lặp lại đầy đủ, không chỉ tin iteration 1 còn đúng):**
- Screenshot 3 viewport: `regroup_1366x768.png` (2 khối cạnh nhau, đủ
  chỗ), `regroup_1920x1080.png` (2 khối rộng rãi), `regroup_390x844.png`
  + `regroup_390_scrolled.png` (2 khối xếp dọc, 2 checkbox trên cùng 1
  hàng vẫn đọc được ở mobile nhờ `flex-wrap`, không vỡ).
- Interaction test sống (Playwright, `test_all_controls.js`): đổi từng
  select/checkbox trong nhóm mới, xác nhận state cập nhật đúng, "Xem
  trước" vẫn mở đúng URL với filter hiện tại, "Trình chiếu trên Kiosk"
  vẫn POST + cập nhật `epWbState` đúng như iteration 1 — 0 hành vi đổi.
- Tour video (`tutorial-detailed.spec.js`, module `employeeProductivity`,
  không sửa lại script vì regroup không đổi selector nào tour dùng):
  chạy full tốc độ thật — **10 bước, 0 bug** (`ep-v224-render`).

**Build & Deploy (nối bảng §7):**

| | Trước | Sau |
|---|---|---|
| Image | `71.0.0.223` | **`71.0.0.224`** (commit `2595925`) |
| Digest | `sha256:2c9f...c7eb3` | `sha256:4d8bbbf5c4a607cc67788834341cabae2323146b3db71750c172db353db3ecc2` |
| Smoke test | — | PASS, `migration_head` không đổi (`0043_super_admin_role`) |
| DEMO | 71.0.0.223 | **71.0.0.224**, container recreate qua `recreate-demo.sh`, mount tutorials giữ nguyên |
| PRODTEST | 71.0.0.223 | **71.0.0.224** qua `scripts/deploy.sh prodtest 71.0.0.224` — `DEPLOY PASS`, health OK, digest khớp, migration không đổi, cron reconcile/log-retention verified present |
| `release.json` | version field lệch (`223` trong khi build đã `224`) | đồng bộ lại `224` (commit `03688da`, qua worktree `agent/claude/release-json-sync-224`) |

**Video chapter 10 (Năng suất nhân viên) — cập nhật lại lần 2:**
Chỉ render lại đúng chapter này, không đụng 14 video còn lại. Nội dung
tour không đổi so với iteration 1 (regroup không ảnh hưởng luồng demo
Xem trước / Trình chiếu thật), chỉ re-render vì UI panel đổi diện mạo.
Thời lượng: 7m21s (iteration 1) → **7m23s** (iteration 2, chênh lệch
nhỏ do timing TTS, không do nội dung đổi). Publish lại vào cả DEMO
(`127.0.0.1:8081`) và PRODTEST (`127.0.0.1:8299`), verify qua API thật
(`GET /api/tutorials`, có đăng nhập) trên cả hai: **đúng 15/15**, thứ
tự 00–14 nguyên vẹn.

**Lưu ý vận hành phát hiện lại trong lần deploy này:** mật khẩu admin
PRODTEST tiếp tục lệch khỏi giá trị dùng để verify trước đó
(`Admin@123456`) — do `mesflow.cli reset-admin` chỉ đồng bộ DB **theo**
biến môi trường container tại thời điểm chạy (`MESFLOW_ADMIN_PASSWORD`
trong container, hiện là `ProdTestOnly_257091ae3a71`), nó không ghi cố
định "Admin@123456" — nên sau lần container recreate 224 phải chạy lại
`reset-admin` và dùng đúng mật khẩu theo biến môi trường hiện tại để
verify API. Đây không phải lỗi mới, chỉ là hệ quả tất yếu của cách
`reset-admin` hoạt động (đồng bộ DB theo env, không phải hằng số).
