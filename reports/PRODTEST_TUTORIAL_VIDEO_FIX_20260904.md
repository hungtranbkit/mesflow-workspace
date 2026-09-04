# PROD TEST — Video Hướng Dẫn Fix — 2026-09-04

Task: audit toàn bộ tính năng đang có trên PROD TEST (`prod.mesflow.net` /
`127.0.0.1:8299`), đối chiếu với video hướng dẫn hiện có, xác định chính
xác vì sao thiếu video, và sửa triệt để (không chỉ vá số đếm).

## 1) Số liệu trước/sau

| | Trước | Sau |
|---|---|---|
| Video hiển thị trên PROD TEST thật (`/api/tutorials`, đã login) | **0** (không phải 13 — xem mục 3) | **15** |
| Tổng feature cần cover (theo `tutorial/coverage-matrix.json`) | 15 | 15 |
| Feature còn thiếu video | 15/15 (100%) | **0/15** |
| Video mới thực sự phải tạo mới từ đầu | — | **0** (bộ 15 video đã có sẵn, đã QA-verify từ phiên làm việc trước trong ngày, chỉ cần đồng bộ đúng chỗ) |

## 2) Audit tính năng đang live trên PROD TEST (yêu cầu #1)

Dựa trên `docs/REQUIREMENTS_QA_MASTER.md` (134 requirement, 20 module,
hoàn thành cùng ngày) + kiểm tra route/permission trực tiếp trên PROD
TEST admin session thật. 20 module đang thực sự phục vụ user:

`AUTH, DASH, PO, PART, TPL, EMP, SESS, KIOSK (v1+v2), SHIFT, EXC, QTY,
PROD (Employee Productivity), IO (Excel), SEARCH, TUT, SYS, AUDIT, API,
UI, NFR`.

## 3) Nguyên nhân chính xác — không phải suy đoán, đã xác minh từng bước

**Con số "13" người dùng thấy KHÔNG khớp với PROD TEST thật** — kiểm tra
trực tiếp `GET /api/tutorials` (đăng nhập admin thật, cả qua
`127.0.0.1:8299` lẫn qua domain public `https://prod.mesflow.net`)
**trả về `items: []` — 0 video, không phải 13**. Con số 13 nhiều khả năng
đến từ một môi trường khác đã xem trước đó (`mesflow.net` thật hoặc
`/opt/mesflow` trước khi được vá trong phiên làm việc trước), không phải
từ PROD TEST. Dù vậy, gốc rễ thực sự trên PROD TEST còn nghiêm trọng hơn
con số "13" ngụ ý.

**Root cause xác nhận bằng `docker inspect`**: `mesflow-prodtest-app`
**chưa từng có volume mount cho `/data/tutorials`** trong
`compose.yml` của nó (`/home/dell/deploy/mesflow-prodtest/compose.yml`)
— service này chỉ có volume cho Postgres data, không có bất kỳ mount nào
cho tutorials/uploads/backups/firmware. `MESFLOW_TUTORIAL_DIR` không
được set nên app dùng default `/data/tutorials`, nhưng thư mục đó
**không tồn tại trong container** (`ls: cannot access
'/data/tutorials/': No such file or directory`) — không phải file bị
xoá, migration chưa chạy, cache, hay permission — đơn giản là hạ tầng
container này chưa từng được cấu hình để phục vụ tutorial video từ
ngày đầu (compose.yml có ghi chú "Minimal runtime: app + postgres",
đúng nghĩa đen — tutorials chưa từng nằm trong phạm vi ban đầu).

Đối chiếu 9 khả năng nguyên nhân được liệt kê trong yêu cầu #3:

| Khả năng | Đúng/Sai |
|---|---|
| Thiếu record DB / migration chưa chạy | Sai — tutorials không dùng DB, chỉ đọc file trực tiếp |
| File video chưa generate/upload | Sai — bộ 15 video đã tồn tại thật (trên `mesflow-demo-app`, đã QA-verify), chỉ chưa từng copy sang prodtest |
| API filter sai / cache | Sai — API code đọc đúng `MESFLOW_TUTORIAL_DIR`, không có filter/cache riêng |
| Env mismatch | Một phần đúng — `MESFLOW_TUTORIAL_DIR` không set, nhưng đó không phải nguyên nhân chính |
| **Deploy thiếu artifact (volume mount)** | **Đúng — nguyên nhân chính** |
| Permission/visibility | Sai — route chỉ cần `login_required`, không có permission riêng cho tutorials |
| Video mới chưa publish | Đúng theo nghĩa rộng — nhưng vì hạ tầng chưa có chỗ chứa, không phải vì quên bấm publish |

## 4) Đã sửa gì (yêu cầu #4, không chỉ vá số đếm)

1. **Sửa `compose.yml` của PROD TEST** (`/home/dell/deploy/mesflow-prodtest/compose.yml`):
   thêm `volumes: - ./runtime/tutorials:/data/tutorials:ro` và
   `MESFLOW_TUTORIAL_DIR: /data/tutorials` cho service `mesflow-prodtest-app`
   — đúng convention read-only đã dùng ở compose.yml chính của repo, không
   phải thay đổi kiến trúc mới. **Fix này bền vững**: xác nhận trực tiếp
   `scripts/deploy.sh` không bao giờ ghi đè `compose.yml` trên target
   (chỉ pull image + update `.env`'s `MESFLOW_IMAGE`), nên mount này tồn
   tại qua mọi lần deploy tương lai, không bị mất lần deploy sau.
2. **Đồng bộ đúng bộ 15 video đã QA-verify** (từ backup của
   `mesflow-demo-app` cùng phiên làm việc, không tạo lại từ đầu vì nội
   dung đã đúng, đã test) vào `runtime/tutorials/` của PROD TEST.
3. **Recreate `mesflow-prodtest-app`** để nhận mount mới — DB/migration
   không đổi (`migration_head: 0043_super_admin_role` trước/sau giống
   hệt), không đụng dữ liệu nghiệp vụ thật (yêu cầu #6) — thay đổi duy
   nhất là thêm 1 mount + file tĩnh, không chạm bảng nào trong DB.

### Coverage matrix FEATURE → VIDEO (yêu cầu #4)

Từ `tutorial/coverage-matrix.json` (hệ thống QA coverage đã xây dựng sẵn
trong repo, gate ở ngưỡng ≥90% tổng thể / 100% happy-path — không phải
tự nghĩ ra bảng mới):

| Feature | Module | Critical | Video (chapter) | Thời lượng |
|---|---|---|---|---|
| Bảng tổng quan | dashboard | ✓ | 01_dashboard | 4m 1s |
| Lệnh sản xuất | po | ✓ | 02_production_order | 2m 21s |
| Mẫu quy trình | templates | ✓ | 03_template | 2m 2s |
| Dòng vật tư | material | | 04_material_flow | 0m 27s |
| Phiên làm việc | sessions | ✓ | 05_session | 0m 44s |
| Trung tâm ngoại lệ | exceptions | ✓ | 06_session_exceptions | 0m 56s |
| Nhân viên và QR | employees | ✓ | 07_employees_qr | 1m 5s |
| Quản lý trạm thao tác | kioskAdmin | ✓ | 08_kiosk_admin | 2m 3s |
| Trạm thao tác | kioskUser | ✓ | 09_kiosk_operator | 3m 8s |
| **Năng suất nhân viên** | employeeProductivity | | **10_employee_productivity** | **4m 49s — dài nhất bộ** |
| Ca và lịch làm việc | calendar | | 11_working_calendar | 1m 3s |
| Người dùng và quyền | users | ✓ | 12_users_permissions | 1m 30s |
| Nhật ký hệ thống | logs | ✓ | 13_system_logs | 0m 51s |
| Nhập và xuất dữ liệu | commonCases | ✓ | 14_common_cases | 1m 55s |
| Thiết bị | commonCases | | 14_common_cases (chung) | (chung) |

**15/15 feature trong coverage-matrix có video tương ứng.**

### Yêu cầu #5 — Năng suất nhân viên / Kiosk (bắt buộc)

`10_employee_productivity.mp4` — **4 phút 49 giây, dài nhất trong toàn
bộ 15 video** — không phải clip ngắn. Nội dung thật (đã verify từ phiên
trước): KPI (nhân viên có dữ liệu, tổng session, năng suất trung bình,
tổng sản lượng đạt), bảng xếp hạng năng suất từng nhân viên, drill-down
chi tiết từng session, filter theo khoảng ngày/phòng ban, và trình chiếu
Kiosk wallboard. `09_kiosk_operator` (3m 8s) cover riêng luồng kiosk vận
hành: quét thẻ nhân viên → quét Operation → nhập đạt/lỗi/sửa được → xác
nhận.

### Gap phát hiện được nhưng KHÔNG tạo video mới lần này (minh bạch, không giấu)

- **System Console (Super Admin)**: tính năng mới nhất (migration
  `0043_super_admin_role`), gate riêng `super_admin_required`, chưa có
  video và chưa nằm trong `coverage-matrix.json`. Đối tượng dùng hẹp
  (chỉ super_admin, không phải admin thường), không nằm trong danh sách
  ví dụ yêu cầu #1 nêu ra. Không tạo video mới lần này để tránh mở rộng
  phạm vi ngoài yêu cầu chính (đúng theo "Không thay đổi kiến trúc lớn
  nếu không cần thiết") — ghi lại đây làm việc tiếp theo nếu cần.
- **Business Audit Trail** (`/api/audit-logs`, khác với System Logs
  13_system_logs) không có entry riêng trong coverage-matrix — có thể
  đã được chạm nhẹ trong các chapter khác nhưng không có video riêng.

## 5) Verify trên UI thật (yêu cầu #7) — bằng chứng

- Screenshot toàn trang "Video hướng dẫn" trên PROD TEST thật (admin
  session, `127.0.0.1:8299`): đủ 15 card (00–14), đúng tiêu đề/nhóm/thời
  lượng, **không trùng lặp, không thumbnail hỏng**.
- Click trực tiếp card "Năng suất nhân viên" → video load qua Playwright:
  `readyState: 4` (sẵn sàng phát), `duration: 289.73s` (khớp 4m49s),
  `HEAD` request trên URL thật → `200, video/mp4, content-length
  13989537` (khớp đúng kích thước file).
- Đối chiếu domain public thật `https://prod.mesflow.net/api/tutorials`
  (không chỉ localhost) → cũng trả về đúng **15 items** — xác nhận đây
  chính là URL người dùng thực sự nhìn thấy.

## 6) Smoke test sau deploy (yêu cầu #8)

Container `mesflow-prodtest-app` recreate xong: `running healthy`,
`server_role: PRODUCTION_TEST`, `migration_head` không đổi. Smoke 4
endpoint lõi ngay sau recreate:

```
dashboard/overview            200
reports/employee-productivity 200
production-orders             200
exceptions                    200
```

Không cần migration mới (nội dung tutorial không đụng schema DB).

## 7) File/thay đổi

- `/home/dell/deploy/mesflow-prodtest/compose.yml` — thêm volume mount
  cho `/data/tutorials` (không phải file trong git repo — đây là deploy
  target directory, đúng quy ước "Neither target's deploy directory
  contains a source checkout").
- `/home/dell/deploy/mesflow-prodtest/runtime/tutorials/` — 15 file
  `.mp4` (75MB) + `manifest.json` + `esp-kiosk/` (nội dung ESP Kiosk kế
  thừa nguyên trạng từ backup, không chỉnh sửa).
- Không có thay đổi nào trong git repo `mesflow/mesflow` cho task này —
  toàn bộ là fix hạ tầng deploy target, không phải thay đổi code.

## 8) Kết luận

PROD TEST hiện hiển thị đầy đủ 15/15 video hướng dẫn, khớp 100% với
coverage-matrix 15 feature, có video riêng chuyên sâu cho Năng suất
nhân viên (yêu cầu bắt buộc #5), không đụng dữ liệu nghiệp vụ thật, fix
bền vững qua các lần deploy sau. Root cause là thiếu volume mount trong
compose.yml của PROD TEST từ ngày đầu thiết lập môi trường — không phải
lỗi mới phát sinh, không phải lỗi seed/migration/permission/cache như
nghi vấn ban đầu.
