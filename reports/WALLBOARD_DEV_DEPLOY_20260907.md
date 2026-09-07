# Kiosk Wallboard Redesign — Deploy + Test đầy đủ trên DEV — 2026-09-07

Task: triển khai bản redesign wallboard (đã PASS ở DEMO+PRODTEST) lên
DEV, không tạo thay đổi UI mới, rồi test tương tác thật trên DEV.

## 0) Version DEV — trước/sau

| | Trước | Sau |
|---|---|---|
| Version | `71.0.0.219` | **`71.0.0.225`** |
| Commit | `unknown` (image cũ không nhúng commit) | `6c452e5d7991` |
| Digest | `mesflow-app@sha256:b5e5b2caf8a38b1fbc9814a7f7e40446e2b44e21b39cbd290fdc50f2ae807be1` | `127.0.0.1:5000/mesflow-app@sha256:993dabf5b48adf5dd5bf9537e435ea03e2efc2b9278f799ab81644f5768c40f9` |
| migration_head | `0043_super_admin_role` | `0043_super_admin_role` (không đổi — 219→225 không thêm migration mới) |
| server_role | `DEV` | `DEV` (không đổi) |
| Container | `mesflow-app` tại `/opt/mesflow` | không đổi tên/vị trí, chỉ đổi image |

**Ghi chú quan trọng về "target DEV"**: `scripts/deploy.sh` (dùng cho
DEMO qua cơ chế riêng, và PRODTEST) **chỉ hỗ trợ 2 target**:
`prodtest` và `production` — không có target `dev`. Đọc
`scripts/deploy_lib.sh` xác nhận: `/opt/mesflow` (container `mesflow-app`,
đúng chỗ DEV đang chạy) **chính là host từng bị coi nhầm là
"production"** trước sự cố an toàn ngày 25-08-2026 — từ đó `production`
target đã bị khoá cứng, chỉ chạy khi có file cấu hình xác thực riêng
trỏ tới host KHÁC máy này (`scripts/production-target.env`, chưa tồn
tại), để không bao giờ lặp lại nhầm lẫn đó. Vì vậy DEV không nằm trong
phạm vi script tự động — đã **tự tay thực hiện đúng các bước an toàn
giống hệt `scripts/deploy.sh`** (pull đúng digest, chạy migrate bằng
đúng image mới, chỉ recreate container app — không đụng `postgres`,
health-check, xác nhận version/commit/migration/digest) thay vì bỏ qua
bước nào.

## 1) Deploy — các bước thực hiện

1. `docker pull 127.0.0.1:5000/mesflow-app@sha256:993dabf5...` — kéo
   đúng digest đã build/push/smoke-test PASS cho DEMO+PRODTEST hôm nay
   (`release/mesflow-71.0.0.225.json`).
2. Chạy migration bằng đúng image mới, cùng `DATABASE_URL` thật của
   `/opt/mesflow` (`docker run --rm --network mesflow_network ... alembic upgrade head`)
   — không có gì để migrate (đã ở `0043_super_admin_role` từ trước).
3. Cập nhật `MESFLOW_IMAGE` trong `/opt/mesflow/.env` thành đúng digest
   trên, `docker compose --env-file .env up -d --no-deps mesflow` (chỉ
   recreate app, không đụng `postgres`/`certs`/volume nào khác).
4. Health-check: `docker inspect --format='{{.State.Health.Status}}' mesflow-app` → `healthy` sau 4 lần thử (~8s).
5. Ghi `/opt/mesflow/deploy-state.json` để có bằng chứng lịch sử deploy,
   cùng định dạng `scripts/deploy.sh` dùng cho prodtest.

**Không sửa bất kỳ file mã nguồn nào** — đúng yêu cầu "không tạo thay
đổi UI mới", chỉ deploy image đã build sẵn từ commit `9e7c1a7`/`6c452e5`.

## 2) Smoke/health check — kết quả

| Kiểm tra | Endpoint/lệnh | Kết quả |
|---|---|---|
| Container healthy | `docker inspect ... .State.Health.Status` | **PASS** — `healthy` |
| API ready | `GET http://127.0.0.1:8080/api/system/ready` | **PASS** — `ok:true, status:ready` |
| Version đúng | cùng endpoint trên | **PASS** — `71.0.0.225` |
| Commit đúng | cùng endpoint trên | **PASS** — `6c452e5d7991` |
| Migration head không đổi ngoài ý muốn | cùng endpoint trên | **PASS** — `0043_super_admin_role`, không đổi |
| Digest đang chạy khớp digest kỳ vọng | `docker image inspect ... RepoDigests` | **PASS** — khớp 100% |
| server_role không đổi | cùng endpoint trên | **PASS** — vẫn `DEV` |

## 3) Test tương tác thật trên màn "Trình chiếu Kiosk" — DEV

**Dữ liệu DEV trước khi test**: 27 nhân viên, **0 Production Order, 0
Session đã kết thúc bao giờ** (kiểm tra toàn thời gian, không chỉ 30
ngày gần nhất) — Kiosk/báo cáo năng suất sẽ chỉ hiện đúng trạng thái
"Chưa có dữ liệu năng suất" nếu không seed gì. Theo đúng mục 4 của yêu
cầu, đã seed tối thiểu, an toàn, có ghi chú rõ:

- `POST /api/templates/demo/seed` — dùng đúng cơ chế "Nạp dữ liệu mẫu"
  có sẵn trong app (admin-only, đã tồn tại từ trước, không phải code
  mới tôi viết).
- `POST /api/templates/3/instantiate` — tạo 1 PO test, mã
  **`CLAUDE-WB-TEST-01`** (đặt tên rõ ràng, dễ nhận diện/loại trừ), từ
  template demo có sẵn `DEMO-E10-FULL`. 15 Part, 47 Operation tạo ra
  theo đúng cấu trúc template — không đụng PO/Part/Operation thật nào.
- `POST /api/production-orders/22/start` — Start PO (bắt buộc để tạo
  Session được).
- `POST /api/kiosk-web/start` + `/finish/<id>` — dùng đúng API Kiosk
  v1 thật (không phải insert thẳng DB), tạo 2 Session **CLOSED** thật
  cho 2 nhân viên có sẵn (NV001, NV002) trên 1 Operation, đủ để có dữ
  liệu năng suất thật cho việc kiểm tra UI.
- **Sau khi test xong**: đã gọi `POST /api/supervisor/sessions/<id>/exclude`
  (cơ chế loại-khỏi-báo-cáo có sẵn, không xoá) cho cả 2 Session vừa
  tạo — báo cáo năng suất trên DEV đã **về lại đúng trạng thái ban đầu
  (0 nhân viên có dữ liệu)**, xác nhận qua API sau khi exclude.
  - **Giới hạn cần ghi rõ**: PO `CLAUDE-WB-TEST-01` cùng 47 Operation/15
    Part vẫn còn tồn tại trong DB (không xoá được) — thử
    `DELETE /api/production-orders/22/force` bị từ chối với
    `FORCE_DELETE_DISABLED` (`MESFLOW_ENABLE_FORCE_DELETE_PO=0`, đúng
    cấu hình an toàn production, **không tự ý bật lại** để xoá cho
    bằng được). Không ảnh hưởng dữ liệu thật nào khác, không xuất hiện
    trong bất kỳ báo cáo/Kiosk nào (2 Session nguồn đã bị loại khỏi báo
    cáo); nếu muốn dọn triệt để, cần một quyết định riêng bật tạm
    `MESFLOW_ENABLE_FORCE_DELETE_PO=1` — **không tự làm trong task
    này**.

### Bảng PASS/FAIL từng mục (13/13 PASS)

| # | Mục kiểm tra | URL/endpoint | Kết quả |
|---|---|---|---|
| 1 | Layout 1920×1080: 0px tràn ngang | `/app?page=employee-productivity` | **PASS** (0px) |
| 2 | Layout 1920×1080: đúng 3 nhóm | cùng trên | **PASS** — `["Dữ liệu hiển thị","Chuyển trang","Làm mới dữ liệu"]` |
| 3 | Layout 1366×768: 0px tràn ngang | cùng trên | **PASS** (0px) |
| 4 | Layout 1366×768: đúng 3 nhóm | cùng trên | **PASS** |
| 5 | Layout 390×844 (mobile): 0px tràn ngang | cùng trên | **PASS** (0px) |
| 6 | Layout 390×844: đúng 3 nhóm | cùng trên | **PASS** |
| 7 | "Xem trước" mở đúng URL preview | click `#epWbPreview` → tab mới | **PASS** — `/kiosk/employee-productivity?preview=1&from=...&to=...&sort=...&employees_per_page=20&columns=auto&auto_page_flip=1&auto_page_flip_seconds=10&refresh=20` |
| 8 | "Xem trước" hiện đúng thẻ nhân viên thật (không chỉ trạng thái rỗng) | tab preview trên | **PASS** — 2 thẻ |
| 9 | "Xem trước" KHÔNG làm thay đổi config đã publish | so sánh `GET wallboard-config` trước/sau | **PASS** — giống hệt nhau |
| 10 | "Trình chiếu trên Kiosk" POST thành công | `POST /api/reports/employee-productivity/wallboard-config` | **PASS** — HTTP 200 |
| 11 | Dòng trạng thái cập nhật đúng | `#epWbState` sau publish | **PASS** — `"Đang trình chiếu: Đầu tháng → hôm nay (tự động) · Cập nhật lần cuối 08:59 07-09 bởi admin"` |
| 12 | Kiosk công khai thật (không đăng nhập) phản ánh đúng config vừa lưu | `GET /kiosk/employee-productivity` (context trình duyệt mới, không cookie) | **PASS** — 2 thẻ hiển thị |
| 13 | Kiosk công khai hiện đúng đúng 2 nhân viên vừa seed | cùng trên, đọc tên trên thẻ | **PASS** — `["Huỳnh Thị Mơ","Lê Văn Lý"]` |

Screenshot bằng chứng (Playwright thật, không dàn dựng): 3 file theo
viewport, lưu trong phiên làm việc — `dev-wb-shots-1920x1080.png`,
`dev-wb-shots-1366x768.png`, `dev-wb-shots-390x844.png`. Ảnh 1920×1080
cho thấy rõ sidebar hiện đúng `v71.0.0.225`, layout 3 nhóm khớp
DEMO/PRODTEST, và bảng "Năng suất theo nhân viên" hiện đúng 2 nhân
viên vừa seed với số liệu thật.

## 4) Lỗi còn lại / giới hạn

- **Không có lỗi UI/chức năng nào phát sinh** — 13/13 mục PASS, hành vi
  giống hệt DEMO/PRODTEST đã xác nhận trước đó (đúng như kỳ vọng vì
  cùng 1 image/digest).
- **PO test `CLAUDE-WB-TEST-01`** (id=22) vẫn còn trong DB DEV, ở trạng
  thái `IN_PROGRESS`, không xuất hiện trong báo cáo/Kiosk (2 Session đã
  bị loại khỏi báo cáo) — xem §3 để dọn triệt để nếu cần (yêu cầu bật
  tạm `MESFLOW_ENABLE_FORCE_DELETE_PO=1`, ngoài phạm vi tự quyết của
  task này).
- **DEV không nằm trong `scripts/deploy.sh`** — lần deploy này thực
  hiện thủ công đúng theo cùng cơ chế an toàn của script, nhưng **không
  tự động lặp lại được** ở lần deploy kế tiếp trừ khi có script riêng
  cho target này. Đề xuất: nếu muốn DEV được deploy thường xuyên và tự
  động như DEMO/PRODTEST, cần quyết định thêm 1 target chính thức
  (không phải viết lại từ đầu, phần lớn logic của `deploy.sh` áp dụng
  được ngay, chỉ cần thêm case `dev` vào `target_config()` — **không tự
  thêm trong task này** vì đây là quyết định vượt phạm vi UI redesign
  ban đầu).
- Scheduler cron (reconcile-exceptions/reconcile-shift-sessions/log-retention)
  **chưa từng được cài cho `/opt/mesflow`** — không phải lỗi phát sinh
  từ lần deploy này (đã vậy từ trước), chỉ ghi lại rõ trong
  `deploy-state.json` (`scheduler_cron_verified: false`) để không lẫn
  với deploy PRODTEST (nơi việc này bắt buộc PASS).

## 5) File thay đổi

**Không có file mã nguồn nào thay đổi trong task này** — đúng yêu cầu
"không tạo thay đổi UI mới". Chỉ có:
- `/opt/mesflow/.env` — `MESFLOW_IMAGE` cập nhật sang digest 225 (không
  phải file trong git, là cấu hình runtime tại chỗ, đúng cách
  `scripts/deploy.sh` cũng làm cho prodtest).
- `/opt/mesflow/deploy-state.json` — bản ghi lịch sử deploy mới (không
  phải file trong git).
- Repo `mesflow-workspace`: file report này.
