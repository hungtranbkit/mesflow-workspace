# mesflow.net — xác định backend thật + deploy 71.0.0.226 — 2026-09-07

Task: user xác nhận `mesflow.net` là môi trường TEST (chưa có
production thật), yêu cầu hỗ trợ deploy bản sửa mới nhất lên đó, chạy
smoke + functional test, và sửa mapping/guard nếu pipeline đang gán
nhầm target này là production.

## 1) Xác định backend thật của mesflow.net — RESOLVED

Nhiều phiên làm việc trước (`docs/DEPLOY_ARCHITECTURE_A.md`, 25-08 →
04-09) đã cố xác định mesflow.net trỏ vào đâu nhưng luôn thất bại/mâu
thuẫn — lý do gốc: **mọi lần trước đều giả định mesflow.net phải là
"production"**, nên chỉ thử đúng 1 lead duy nhất tên có chữ "prod"
(`kimex@ssh-prod.mesflow.net`, chưa từng xác minh được). Xác nhận hôm
nay của user (mesflow.net = TEST, chưa có production thật) mở ra đúng
hướng: `~/.ssh/config` sẵn có alias **`mesflow-test`** (khác hẳn cái đã
thử trước đây), chưa từng được thử vì cái tên "test" không khớp giả
định "phải là production".

**Bằng chứng xác nhận (mạnh nhất có thể — nhân quả, không chỉ trùng khớp thụ động):**
- SSH vào `mesflow-test`: `docker ps` + `curl 127.0.0.1:8080/api/system/ready`
  cho kết quả **giống hệt** `https://mesflow.net/api/system/ready`
  (cùng version `71.0.0.219`, cùng `commit:"unknown"`, cùng
  `server_role: PRODUCTION_TEST`, cùng `migration_head`) — trước khi
  đụng vào bất cứ gì.
- **Deploy thật** `71.0.0.226` lên đúng host đó → `curl
  https://mesflow.net/api/system/ready` từ bên ngoài **ngay lập tức**
  đổi sang đúng version/commit vừa deploy. Đây là kiểm chứng nhân quả
  thật sự (đổi X, quan sát X đổi công khai), mạnh hơn hẳn phép so khớp
  version thụ động đã từng gây kết luận sai ở lần điều tra 02-09.

## 2) Quyền truy cập — phát hiện & giải quyết

- Tài khoản SSH mặc định dùng cho bảo trì hàng ngày trên host đó
  (`~/mesflow-ops` — backup DB, log-retention) **không có sudo**
  (`sudo is not in the sudoers file` — xác nhận dứt khoát, không phải
  do sai mật khẩu).
- Deploy Agent riêng của host đó (port 8090, chỉ nội bộ) yêu cầu đăng
  nhập riêng, không có sẵn thông tin.
- Sau khi hỏi lại user, xác nhận: **tài khoản `ubuntu` trên chính host
  đó có sudo không cần mật khẩu** (`sudo -n true` thành công) — đây là
  đường chính thức để deploy.
- **Không đoán/thử mật khẩu ngoài những gì user cung cấp trực tiếp** —
  chỉ thử đúng các giá trị user đưa ra (kể cả khi sai, chỉ 1 lần/giá
  trị, không lặp).

## 3) Deploy thật — các bước

Do registry local (`127.0.0.1:5000`) của máy này **không thể reach**
từ một host thật sự khác (khác hẳn `prodtest`, vốn SSH vào chính
`127.0.0.1`) — dùng đúng cơ chế **bundle** mà chính `release.json` của
host đó đã khai báo từ trước (`"distribution": "bundle"`):

1. `docker save` image `71.0.0.226` thành file `.tar` (76MB).
2. Truyền qua SFTP, xác nhận **checksum SHA-256 khớp 100%** hai đầu.
3. `sudo docker load` trên remote — xác nhận Image ID khớp đúng digest
   đã build.
4. Chạy migration bằng đúng image mới, đúng `DATABASE_URL` thật (đọc
   qua `sudo`, chỉ giữ trong bộ nhớ script lúc chạy, **không in ra bất
   kỳ đâu**, không lưu vào report này) — kết quả: không có gì để
   migrate (đã đúng `migration_head` từ trước).
5. Cập nhật `MESFLOW_IMAGE` trong `.env`, `sudo docker compose up -d
   --no-deps mesflow` (chỉ recreate app, không đụng DB/nginx).
6. Health-check: healthy ngay lần thử đầu.
7. Xác nhận qua **URL công khai thật** `https://mesflow.net` — không
   chỉ nội bộ.
8. Chạy đầy đủ bộ test tương tác thật (Playwright) nhắm thẳng
   `https://mesflow.net`, đăng nhập bằng đúng mật khẩu admin thật của
   host đó (đọc qua `sudo`, dùng trong bộ nhớ, xoá file tạm ngay sau
   khi test xong).
9. Dọn dẹp: xoá file `.tar` tạm trên remote, ghi `deploy-state.json`
   để có bằng chứng lịch sử deploy (cùng định dạng các target khác).

## 4) Test evidence trên chính `https://mesflow.net` — 14/14 PASS

| # | Kiểm tra | Kết quả |
|---|---|---|
| 1 | Đăng nhập admin thật thành công | PASS (200) |
| 2 | 0px tràn ngang ở 1920×1080 | PASS |
| 3 | Đúng 3 nhóm cấu hình (Dữ liệu hiển thị/Chuyển trang/Làm mới dữ liệu) | PASS |
| 4 | Nút đổi tên đúng "Áp dụng lên Kiosk" | PASS |
| 5 | Link mới "Mở màn hình Kiosk" tồn tại | PASS |
| 6 | Href link đúng `/kiosk/employee-productivity` | PASS |
| 7 | "Xem trước" mở đúng URL preview thật | PASS — `https://mesflow.net/kiosk/employee-productivity?preview=1&...` |
| 8 | "Xem trước" không làm thay đổi config đã publish | PASS |
| 9 | "Áp dụng lên Kiosk" POST trả về 200 | PASS |
| 10 | Toast hiện đúng chữ mới | PASS — "Đã cập nhật cấu hình Kiosk." |
| 11 | Dòng trạng thái cập nhật đúng | PASS |
| 12 | Bấm "Mở màn hình Kiosk" mở đúng tab mới, đúng URL công khai thật | PASS — `https://mesflow.net/kiosk/employee-productivity` |
| 13 | Màn Kiosk công khai tải được (dữ liệu hoặc đúng trạng thái rỗng) | PASS — 0 thẻ (dữ liệu hiện tại trên host này không có session khớp khoảng ngày, đúng trạng thái rỗng đã test trước đó, không phải lỗi) |
| 14 | Màn Kiosk công khai tải được **không cần đăng nhập** (context trình duyệt mới, không cookie) | PASS (200) |

## 5) Version trước/sau

| | Trước | Sau |
|---|---|---|
| Version (public, `https://mesflow.net/api/system/ready`) | `71.0.0.219` | **`71.0.0.226`** |
| Commit | `unknown` | `e4ddfc2369cb` |
| Digest | `mesflow-app@sha256:b5e5b2caf8...` | `127.0.0.1:5000/mesflow-app@sha256:48603e931bae...` |
| migration_head | `0043_super_admin_role` | `0043_super_admin_role` (không đổi) |
| server_role | `PRODUCTION_TEST` | `PRODUCTION_TEST` (không đổi — đúng, đây là TEST) |

## 6) Sửa mapping/guard — theo đúng yêu cầu, không làm yếu bảo vệ
production tương lai

- **Không sửa/không nới `scripts/deploy.sh production`** — target này
  giữ nguyên đóng băng từ 25-08, vẫn từ chối chạy nếu thiếu
  `scripts/production-target.env` thật. Đây chính là điều user yêu cầu
  giữ nguyên ("không làm giảm bảo vệ cho production tương lai").
- **Thêm script MỚI riêng**: `scripts/deploy-remote-test.sh` — không
  tái dùng `deploy_lib.sh`'s `target_config()` chung với prodtest/
  production vì cơ chế thật sự khác nhau đủ nhiều (bundle-transfer
  thay vì registry-pull, cần sudo-prefix mọi lệnh do tài khoản kết nối
  không có sudo mặc định, `SERVER_ROLE=PRODUCTION_TEST` cứng thay vì
  cấu hình được) — làm rõ trong chính comment code tại sao không dùng
  chung logic với `production`.
- **File cấu hình thật** `scripts/remote-test-target.env` (gitignored,
  đã thêm vào `.gitignore`) — không commit IP/host thật vào repo công
  khai (`gh repo view` xác nhận repo `hungtranbkit/mesflow` là
  **PUBLIC**). File `.example` chỉ chứa placeholder.
- **Cập nhật tài liệu**: `docs/DEPLOY_ARCHITECTURE_A.md` (thêm mục
  "RESOLVED, 2026-09-07" đầy đủ bằng chứng, không xoá lịch sử điều tra
  cũ), `docs/qc/SAFETY.yaml` (mesflow.net giờ khớp đúng class
  `prodtest` sẵn có qua chính cơ chế kiểm tra `server_role` động của
  file, không cần đổi logic — chỉ sửa ghi chú tĩnh đã lỗi thời).

## 7) Giới hạn / việc chưa làm

- **Xác thực SSH tới `mesflow-test` hiện dùng mật khẩu** (không có SSH
  key riêng cho tài khoản `ubuntu`) — script `deploy-remote-test.sh`
  dùng `ssh`/`scp` thường, sẽ cần nhập mật khẩu tương tác nếu chạy lại
  (không lưu mật khẩu ở đâu, kể cả trong `remote-test-target.env`).
  Nếu muốn tự động hoá hoàn toàn, cần thêm SSH key riêng vào
  `authorized_keys` của `ubuntu` trên host đó — **không tự làm** vì đây
  là thay đổi hạ tầng ngoài phạm vi task hôm nay.
- `release.json`/`PROMOTION.json` trên host `mesflow-test` vẫn còn trỏ
  version cũ (`71.0.0.208`) — đã lỗi thời **từ trước khi tôi chạm vào**
  (không phải do lần deploy này), không sửa vì các file này thuộc quản
  lý của chính Deploy Agent riêng của host đó, không muốn làm rối logic
  nội bộ của hệ thống đó khi chưa hiểu rõ nó đọc/ghi các file này thế
  nào. Đã ghi `deploy-state.json` riêng làm bằng chứng chính xác cho
  lần deploy này.
- Không đụng Deploy Agent (port 8090) hay QA Center (port 8095) riêng
  của host đó — ngoài phạm vi yêu cầu.

## 8) File đã sửa + commit

Repo `mesflow`:
- `scripts/deploy-remote-test.sh` (mới) — script deploy riêng cho
  target này.
- `scripts/remote-test-target.env.example` (mới) — template, chỉ
  placeholder.
- `scripts/deploy_lib.sh` — thêm comment làm rõ ranh giới với
  `production`, không đổi logic `production`.
- `docs/DEPLOY_ARCHITECTURE_A.md` — thêm mục RESOLVED.
- `docs/qc/SAFETY.yaml` — cập nhật ghi chú đã lỗi thời.
- `.gitignore` — thêm `scripts/remote-test-target.env`.

Commit: `ea3243c`. Đã push `main`.
