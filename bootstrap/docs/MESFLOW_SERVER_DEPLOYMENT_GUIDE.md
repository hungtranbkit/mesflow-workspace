# Hướng dẫn triển khai MESFlow — từ máy trống tới server chạy thật

_Phiên bản tài liệu: 1.0.0 — sinh tự động từ `bootstrap/guide_content.py`, không sửa tay file này. Cùng nội dung với trang web `/guide/deployment` trong Bootstrap._

## Kiến trúc triển khai

```
MÁY DEV (workspace nguồn)
  │
  ├─ MESFlow (mesflow/)            source code
  ├─ QA Center (qa-center/)        source code
  ├─ Deploy Agent DEV (:8090)      SERVER_ROLE=DEV, build bật
  │
  │  build một lần → package/image bất biến (version + SHA256 + digest cố định)
  │
  ▼
PRODUCTION TEST (server test riêng, không phải thật)
  ├─ Bootstrap        :8098   (cài & cứu hộ Deploy Agent)
  ├─ Deploy Agent      :8090   SERVER_ROLE=PRODUCTION_TEST, build TẮT
  ├─ PostgreSQL                (container "postgres", do MESFlow compose quản lý)
  ├─ MESFlow (mesflow-app)  :8080
  └─ QA Center         :8095

  │  chỉ đi tiếp sau khi có TEST_PASS + con người bấm duyệt
  ▼
PRODUCTION (server thật, mesflow.net)
  ├─ Bootstrap        :8098
  ├─ Deploy Agent      :8090   SERVER_ROLE=PRODUCTION, build TẮT
  ├─ PostgreSQL
  ├─ MESFlow (mesflow-app)  :8080
  └─ QA Center         :8095
```

**DEV**
: Máy đang sửa code + build package/image. Đây là nơi DUY NHẤT được phép build. SERVER_ROLE=DEV, MESFLOW_BUILD_ENABLED=1, có workspace mount vào Deploy Agent.

**PRODUCTION TEST**
: Server test riêng, gần giống Production nhưng KHÔNG phải Production thật. Dùng để thử đúng artifact (đúng ZIP SHA256 / image digest) sẽ đưa lên Production, không bao giờ build lại ở đây.

**PRODUCTION**
: Máy chạy thật cho người dùng cuối. Chỉ nhận đúng artifact đã có TEST_PASS, và luôn cần con người bấm duyệt tường minh mỗi lần, không có ngoại lệ.

**Bootstrap**
: Dịch vụ độc lập, cổng 8098, không phụ thuộc Docker/MESFlow. Việc duy nhất: dựng máy Ubuntu trống (SSH + Docker) và cài/cứu hộ Deploy Agent. Đây là 'cửa vào' để phục hồi khi mọi thứ khác đã hỏng.

**Deploy Agent**
: Control plane triển khai + vận hành thật sự: build (chỉ trên DEV), upload, deploy --no-build, verify health/schema, rollback, quản lý MESFlow lẫn QA Center. Cổng 8090.


## Vai trò server (SERVER_ROLE) — luôn xác minh, không đoán

Vai trò của một server (DEV / PRODUCTION_TEST / PRODUCTION) KHÔNG được đoán từ hostname hay IP. Nó đến từ đúng một biến môi trường, `SERVER_ROLE`, được Deploy Agent đọc khi khởi động (`deploy-agent/agent.py`: `SERVER_ROLE = os.environ.get("SERVER_ROLE","DEV").strip().upper()`).

Giá trị hợp lệ: `DEV`, `PRODUCTION_TEST`, `PRODUCTION`

| Máy | Compose override | Đặt gì |
|---|---|---|
| DEV local | `docker/compose.dev.override.yml` | SERVER_ROLE=DEV, MESFLOW_BUILD_ENABLED=1, mount workspace vào /workspace/mesflow |
| Production Test | `docker/compose.production-test.override.yml` | SERVER_ROLE=PRODUCTION_TEST, MESFLOW_BUILD_ENABLED=0 |
| Production | `docker/compose.production.override.yml` | SERVER_ROLE=PRODUCTION, MESFLOW_BUILD_ENABLED=0 |
| Máy mới cài qua Bootstrap | `docker/compose.bootstrap.override.yml` | chỉ bind port 127.0.0.1:8090:8090 — KHÔNG tự set vai trò |

Biến này được set bằng cách Deploy Agent chạy `docker compose` với đúng 1 file override khớp vai trò thật của máy, cộng trên nền `compose.linux.yml` (nền này tự mặc định `SERVER_ROLE=PRODUCTION_TEST`, build tắt, nếu không có gì override — mặc định an toàn).

Khi cài mới qua `deploy-agent/installer/install.sh` (kể cả qua Bootstrap → Install Deploy Agent), installer tự dò: nếu biến môi trường `SERVER_ROLE` được set tường minh thì dùng đúng giá trị đó; nếu không, nó chỉ chọn DEV khi máy này thật sự có một workspace checkout hợp lệ (thư mục `deploy-agent/docker/compose.dev.override.yml` tồn tại trong `MESFLOW_WORKSPACE_ROOT` đã resolve) — nếu không tìm thấy, mặc định an toàn là **PRODUCTION_TEST**. Một server Production Test/Production mới toanh không có workspace nên luôn rơi vào PRODUCTION_TEST theo mặc định; phải tự tay chuyển sang PRODUCTION nếu đó thật sự là máy Production (xem lệnh bên dưới).

**Cách kiểm tra:**

**CHẠY TRÊN SERVER**
```bash
curl -fsS http://127.0.0.1:8090/agent/health | python3 -c "import json,sys; d=json.load(sys.stdin); print('SERVER ROLE:', d['server_role'])"
```
> Ví dụ kết quả thật lấy từ một máy DEV: SERVER ROLE: DEV

**CHẠY TRÊN SERVER**
```bash
docker inspect mesflow-deploy-agent --format '{{range .Config.Env}}{{println .}}{{end}}' | grep ^SERVER_ROLE=
```
> Đọc trực tiếp từ container đang chạy, không qua HTTP — dùng khi Deploy Agent không trả lời được /agent/health.

**⚠ KHÔNG BAO GIỜ deploy hay promote bất cứ thứ gì cho tới khi `server_role` hiển thị đúng với ý định thật của bạn. Đã có sự cố thật: cài lại Deploy Agent trên máy DEV qua Bootstrap từng lặng lẽ đổi máy DEV thành PRODUCTION_TEST (mất build + mất mount workspace) vì installer quên thêm compose.dev.override.yml — đã fix, nhưng luôn tự kiểm tra lại sau mỗi lần cài/update, không tin tưởng mù quáng.**


**Nếu vai trò sai — cách sửa:**

**CHẠY TRÊN SERVER**
```bash
cd /opt/mesflow-deploy-agent/docker
```
> Thư mục compose thật trên server.

**CHẠY TRÊN SERVER**
```bash
# DEV local:
docker compose -f compose.linux.yml -f compose.dev.override.yml -f compose.bootstrap.override.yml up -d
```

**CHẠY TRÊN SERVER**
```bash
# Production Test:
docker compose -f compose.linux.yml -f compose.production-test.override.yml up -d
```

**CHẠY TRÊN SERVER**
```bash
# Production:
docker compose -f compose.linux.yml -f compose.production.override.yml up -d
```


## Hành trình triển khai — 12 bước

### 01. Chuẩn bị máy chủ

**MỤC ĐÍCH:** Xác nhận máy Ubuntu mới đủ điều kiện trước khi cài bất cứ thứ gì — hệ điều hành, tài nguyên, giờ hệ thống.

**THỰC HIỆN Ở ĐÂU:** Trên server Ubuntu mới, qua console của nhà cung cấp hạ tầng hoặc một phiên SSH tạm thời ban đầu.

**Xác nhận hệ điều hành**

**CHẠY TRÊN SERVER**
```bash
cat /etc/os-release
```

**CHẠY TRÊN SERVER**
```bash
uname -a
```

**CHẠY TRÊN SERVER**
```bash
hostnamectl
```

> Bootstrap hỗ trợ và đã kiểm thử trên Ubuntu (`install.sh` tự phát hiện `ID=ubuntu` trong `/etc/os-release`; hệ điều hành khác vẫn chạy được nhưng chỉ in cảnh báo, không được kiểm thử chính thức).

**Xác nhận địa chỉ mạng**

**CHẠY TRÊN SERVER**
```bash
hostname -I
```

**Kiểm tra tài nguyên**

**CHẠY TRÊN SERVER**
```bash
free -h
```

**CHẠY TRÊN SERVER**
```bash
df -h
```

**CHẠY TRÊN SERVER**
```bash
lsblk
```

> Cấu hình CPU/RAM/disk tối thiểu — **chưa được quy định chính thức** trong workspace hiện tại; không có tài liệu nào trong `docs/` nêu con số cụ thể. Đừng tin bất kỳ con số nào không trích được từ code/docs thật — ước lượng thực tế theo tải: PostgreSQL + MESFlow + QA Center + Deploy Agent chạy đồng thời trên cùng một máy.

**Kiểm tra giờ hệ thống**

**CHẠY TRÊN SERVER**
```bash
timedatectl
```

> MESFlow kỳ vọng timezone `Asia/Ho_Chi_Minh`. Nếu khác, đặt lại:

**Đặt timezone (nếu cần)**

**CHẠY TRÊN SERVER**
```bash
sudo timedatectl set-timezone Asia/Ho_Chi_Minh
```

**KẾT QUẢ MONG ĐỢI:** `ID=ubuntu` trong /etc/os-release; đủ RAM/disk trống cho khối lượng dự kiến; `Time zone: Asia/Ho_Chi_Minh` trong timedatectl.

**NẾU LỖI THÌ LÀM GÌ:** Không phải Ubuntu → cân nhắc cài lại OS trước khi tiếp tục; Bootstrap chỉ cảnh báo chứ không chặn, nhưng chạy ngoài Ubuntu là chưa được kiểm thử. Sai timezone → chạy lệnh set-timezone ở trên rồi kiểm tra lại.

**TIẾP THEO:** Bước 02 — Kết nối SSH

### 02. Kết nối SSH

**MỤC ĐÍCH:** Thiết lập kết nối SSH ổn định, có alias, từ máy DEV/laptop của bạn tới server mới — mọi bước sau đều cần kết nối này.

**THỰC HIỆN Ở ĐÂU:** Trên máy DEV/laptop của quản trị viên.

**Kết nối trực tiếp lần đầu**

**CHẠY TRÊN MÁY DEV**
```bash
ssh ubuntu@<SERVER_IP>
```

> Thay `ubuntu` bằng user thật trên server, `<SERVER_IP>` bằng IP thật.

**Tạo alias để không phải gõ lại thông tin mỗi lần**

~/.ssh/config

Host mesflow-test
    HostName <SERVER_IP>
    User ubuntu
    IdentityFile ~/.ssh/<key>


**CHẠY TRÊN MÁY DEV**
```bash
mkdir -p ~/.ssh && ${EDITOR:-nano} ~/.ssh/config
```
> Thêm khối cấu hình dưới đây vào cuối file.

**Dùng alias**

**CHẠY TRÊN MÁY DEV**
```bash
ssh mesflow-test
```

> Trong workspace này, alias thật cho server test là `mesflow-test` — xem `../AGENTS.md`.

**Chép file / thư mục qua SSH**

**CHẠY TRÊN MÁY DEV**
```bash
scp -r <thư_mục_local> mesflow-test:/tmp/<đích>
```

**CHẠY TRÊN MÁY DEV**
```bash
rsync -avz <thư_mục_local>/ mesflow-test:/tmp/<đích>/
```

> scp đơn giản cho lần chép đầu; rsync hiệu quả hơn cho lần chép lại (chỉ gửi phần thay đổi).

**KẾT QUẢ MONG ĐỢI:** `ssh mesflow-test` vào thẳng server không hỏi lại thông tin (ngoài passphrase khoá, nếu có).

**NẾU LỖI THÌ LÀM GÌ:** Connection refused/timeout → SSH chưa chạy trên server hoặc firewall/nhà cung cấp chặn cổng 22 — kiểm tra qua console nhà cung cấp. Permission denied → sai user/khoá — xác nhận lại `IdentityFile` và user trong `~/.ssh/config`.

**TIẾP THEO:** Bước 03 — Chép Bootstrap lên server

### 03. Chép Bootstrap lên server

**MỤC ĐÍCH:** Đưa mã nguồn Bootstrap (chưa cài gì cả — chỉ chép file) lên server mới để chuẩn bị chạy installer.

**THỰC HIỆN Ở ĐÂU:** Bắt đầu trên máy DEV, kết thúc trên server.

**Chép thư mục bootstrap/ sang server**

**CHẠY TRÊN MÁY DEV**
```bash
cd ~/workspace/mesflow
```

**CHẠY TRÊN MÁY DEV**
```bash
scp -r bootstrap mesflow-test:/tmp/mesflow-bootstrap
```

> `~/workspace/mesflow/bootstrap` là vị trí nguồn chính thức hiện tại của Bootstrap trong workspace này.

**Vào server và kiểm tra file đã chép**

**CHẠY TRÊN SERVER**
```bash
ssh mesflow-test
```

**CHẠY TRÊN SERVER**
```bash
ls -la /tmp/mesflow-bootstrap
```

**CHẠY TRÊN SERVER**
```bash
cd /tmp/mesflow-bootstrap
```

**KẾT QUẢ MONG ĐỢI:** Thư mục /tmp/mesflow-bootstrap trên server chứa đúng: `install.sh`, `app.py`, `guide_content.py`, `requirements.txt`, `templates/`, `static/`, `README.md`, `VERSION.txt`.

**NẾU LỖI THÌ LÀM GÌ:** Thiếu file (đặc biệt `install.sh` hoặc `app.py`) → chép lại từ đầu, kiểm tra lệnh scp không bị lỗi giữa chừng (hết dung lượng, mất kết nối).

**TIẾP THEO:** Bước 04 — Cài Bootstrap

### 04. Cài Bootstrap

**MỤC ĐÍCH:** Chạy installer để cài đặt môi trường tối thiểu (OpenSSH, Docker Engine + Compose) và khởi động dịch vụ web Bootstrap dưới systemd.

**THỰC HIỆN Ở ĐÂU:** Trên server, trong thư mục vừa chép ở Bước 03.

**Chạy installer**

**CHẠY TRÊN SERVER**
```bash
sudo bash install.sh
```

> **Những gì install.sh thực sự làm** (đọc trực tiếp từ code, không phải suy đoán):

1. Phát hiện Ubuntu (chỉ cảnh báo nếu không phải Ubuntu, không chặn).
2. Cài openssh-server nếu chưa có, bật + enable dịch vụ ssh.
3. Cài Docker Engine + Compose plugin từ get.docker.com nếu chưa có Docker; tạo Docker network mesflow-edge nếu chưa tồn tại (Deploy Agent's compose cần network này, khai báo external: true).
4. Tạo /opt/mesflow-bootstrap (code + venv) và /var/lib/mesflow-bootstrap (dữ liệu bền vững: tài khoản admin, log, state) — KHÔNG bao giờ tạo/xoá /var/lib/mesflow-deploy-agent.
5. Vendor một bản sao KHÔNG chỉnh sửa của deploy-agent/updater/updater.py vào agent_updater_core.py, cho khả năng Update/Rollback của Deploy Agent sau này.
6. Tạo virtualenv Python, cài Flask + waitress.
7. Cài & khởi động systemd service mesflow-bootstrap.service (không require docker.service hay bất kỳ unit MESFlow nào — Bootstrap phải sống được cả khi Docker/MESFlow/Deploy Agent đang chết).
8. Poll http://127.0.0.1:8098/health tới 15 lần, mỗi lần cách 1 giây, để xác nhận healthy.
Idempotent: chạy lại install.sh không mất tài khoản admin/log/state đã có.

**Xác nhận dịch vụ đã chạy**

**CHẠY TRÊN SERVER**
```bash
sudo systemctl status mesflow-bootstrap --no-pager
```

**CHẠY TRÊN SERVER**
```bash
curl -fsS http://127.0.0.1:8098/health
```

**CHẠY TRÊN SERVER**
```bash
sudo ss -ltnp | grep ':8098'
```

**KẾT QUẢ MONG ĐỢI:** systemctl status → active (running); curl /health → `{"ok": true, "service": "mesflow-bootstrap", ...}`; ss -ltnp cho thấy có tiến trình lắng nghe cổng 8098.

**NẾU LỖI THÌ LÀM GÌ:** install.sh thoát với lỗi → đọc thông báo ERROR: cụ thể (script dùng `set -Eeuo pipefail`, dừng ngay khi có lỗi). Healthy timeout sau 15 giây → `journalctl -u mesflow-bootstrap -n 100` để xem log khởi động.

**TIẾP THEO:** Bước 05 — Truy cập Bootstrap Web

### 05. Truy cập Bootstrap Web

**MỤC ĐÍCH:** Mở giao diện Bootstrap từ trình duyệt trên laptop của bạn — server không có desktop, nên phải dùng SSH tunnel thay vì mở trình duyệt trực tiếp trên server.

**THỰC HIỆN Ở ĐÂU:** Server không cần desktop environment. Trình duyệt chạy trên laptop; đường nối là SSH tunnel.

**Mở tunnel từ laptop**

**CHẠY TRÊN MÁY DEV**
```bash
ssh -N \
  -L 18098:127.0.0.1:8098 \
  mesflow-test
```
> Giữ terminal này mở — tunnel chỉ sống khi lệnh này còn chạy.

**Mở trình duyệt**

**TRÌNH DUYỆT (TRÊN LAPTOP)**
```bash
http://127.0.0.1:18098/
```

**Vì sao dùng cổng 18098 ở local thay vì 8098?**

Cổng 8098 có thể đã bị chiếm trên chính máy DEV (ví dụ máy DEV cũng đang chạy Bootstrap của riêng nó). Map sang một cổng local khác (18098) tránh xung đột mà không đổi gì trên server.

**Sơ đồ**

Chrome (laptop)
127.0.0.1:18098
      │
      │ SSH tunnel
      ▼
server
127.0.0.1:8098
Bootstrap

**KẾT QUẢ MONG ĐỢI:** Trình duyệt trên laptop mở được trang đăng nhập/setup của Bootstrap tại 127.0.0.1:18098.

**NẾU LỖI THÌ LÀM GÌ:** Trình duyệt không kết nối được → kiểm tra terminal chạy lệnh ssh -N còn sống, chưa bị Ctrl+C. "bind: address already in use" → cổng 18098 trên laptop đã bị chiếm, đổi sang cổng khác (vd 18099) ở cả hai phía lệnh -L VÀ URL trình duyệt.

**TIẾP THEO:** Bước 06 — Xác định vai trò server

### 06. Xác định vai trò server

**MỤC ĐÍCH:** Trước khi đi tiếp, xác nhận tường minh máy này là DEV, PRODUCTION_TEST hay PRODUCTION — không đoán.

**THỰC HIỆN Ở ĐÂU:** Trên server, qua SSH (Deploy Agent chưa cài ở bước này thì mục này sẽ trả về 'chưa cài').

**Kiểm tra (nếu Deploy Agent đã cài)**

**CHẠY TRÊN SERVER**
```bash
curl -fsS http://127.0.0.1:8090/agent/health | python3 -c "import json,sys; d=json.load(sys.stdin); print('SERVER ROLE:', d['server_role'])"
```
> Ví dụ kết quả thật lấy từ một máy DEV: SERVER ROLE: DEV

**CHẠY TRÊN SERVER**
```bash
docker inspect mesflow-deploy-agent --format '{{range .Config.Env}}{{println .}}{{end}}' | grep ^SERVER_ROLE=
```
> Đọc trực tiếp từ container đang chạy, không qua HTTP — dùng khi Deploy Agent không trả lời được /agent/health.

**Nếu Deploy Agent CHƯA cài**

Chưa có gì để kiểm tra — vai trò sẽ được xác lập ở Bước 07 khi cài Deploy Agent. Ghi nhớ trước: vai trò DỰ ĐỊNH của máy này là gì (DEV / PRODUCTION_TEST / PRODUCTION), vì mặc định cài mới cho một máy không có workspace luôn là PRODUCTION_TEST.

**KẾT QUẢ MONG ĐỢI:** Biết chắc và ghi nhớ: SERVER ROLE dự định cho máy này.

**NẾU LỖI THÌ LÀM GÌ:** Xem toàn bộ chi tiết & cách sửa vai trò sai ở phần 'Vai trò server (SERVER_ROLE)' phía trên các bước.

**TIẾP THEO:** Bước 07 — Cài Deploy Agent

### 07. Cài Deploy Agent

**MỤC ĐÍCH:** Build package Deploy Agent trên DEV, đưa lên server qua Bootstrap (hoặc cài trực tiếp qua SSH), rồi xác minh healthy.

**THỰC HIỆN Ở ĐÂU:** Build trên DEV; cài đặt trên server (qua Bootstrap Web hoặc SSH trực tiếp).

**1) Build package trên DEV — Bootstrap KHÔNG tự build Deploy Agent**

**CHẠY TRÊN MÁY DEV**
```bash
cd ~/workspace/mesflow/deploy-agent
```

**CHẠY TRÊN MÁY DEV**
```bash
./package_installer.sh
```
> Mặc định TỰ TĂNG version (scripts/bump-version.sh) rồi đóng gói — mỗi lần chạy ra một package mới, không bao giờ trùng version cũ. Dùng --no-bump để đóng gói đúng VERSION.txt hiện tại, hoặc --to <version> để nhảy tới version cụ thể.

> Kết quả: `artifacts/deploy-agent/MESFlow_Server_Bootstrap_Agent_First_v<VERSION>.zip` — gồm `install.sh` ở gốc + `payload/mesflow-deploy-agent/{agent.py, VERSION.txt, docker/...}`. **Luật bất biến:** một version chỉ được release một lần — không bao giờ tái sử dụng version đã release.

**2A) Cài qua Bootstrap Web (khuyến nghị)**

Bootstrap → Install Deploy Agent → chọn file .zip vừa build → (tuỳ chọn) dán SHA256 để Bootstrap tự đối chiếu → Validate & Install.

Bootstrap sẽ: xác thực cấu trúc ZIP đúng install.sh + payload/mesflow-deploy-agent/{agent.py, VERSION.txt}, đọc VERSION.txt, chặn downgrade trừ khi tick 'Allow downgrade', chạy đúng install.sh của package (y hệt một người vận hành gõ tay qua SSH — Bootstrap không tự cài đặt logic build/rollback riêng), rồi tự poll http://127.0.0.1:8090/agent/health và báo PASS/FAILED.

**2B) Cài trực tiếp qua SSH (cách dự phòng dòng lệnh)**

**CHẠY TRÊN MÁY DEV**
```bash
scp artifacts/deploy-agent/MESFlow_Server_Bootstrap_Agent_First_v<VERSION>.zip mesflow-test:/tmp/
```

**CHẠY TRÊN SERVER**
```bash
cd /tmp && unzip MESFlow_Server_Bootstrap_Agent_First_v<VERSION>.zip
```

**CHẠY TRÊN SERVER**
```bash
cd MESFlow_Server_Bootstrap_Agent_First_v<VERSION>
```

**CHẠY TRÊN SERVER**
```bash
sudo bash install.sh
```

> Đây chính là `deploy-agent/installer/install.sh` thật — không có API upload riêng nào khác ngoài form web ở 2A và chạy trực tiếp script này; đừng bịa ra một API không tồn tại.

**Về /opt/mesflow/.env — điều kiện bắt buộc trước khi cài**

installer từ chối chạy nếu `/opt/mesflow/.env` chưa tồn tại (file này chứa secret, installer không tự tạo hay copy nó). Một người phải tạo/copy file này thủ công lên server TRƯỚC khi cài Deploy Agent.

**KẾT QUẢ MONG ĐỢI:** Kết quả PASS trên Bootstrap (hoặc install.sh in ra JSON health cuối cùng khi cài qua SSH).

**NẾU LỖI THÌ LÀM GÌ:** 'Missing persistent /opt/mesflow/.env' → tạo file đó trước, xem ghi chú ở trên. VERSION_ALREADY_RELEASED khi build → tăng version rồi build lại, không bao giờ ép ghi đè. Health không lên sau 15 lần poll → installer tự rollback về image cũ (nếu có) — kiểm tra `docker logs mesflow-deploy-agent`.

**TIẾP THEO:** Bước 08 — Kiểm tra Docker/services

### 08. Kiểm tra Docker/services

**MỤC ĐÍCH:** Xác minh Deploy Agent thật sự khoẻ mạnh và đọc đúng các trường quan trọng trong health trước khi deploy bất cứ ứng dụng nào lên đây.

**THỰC HIỆN Ở ĐÂU:** Trên server.

**Health đầy đủ**

**CHẠY TRÊN SERVER**
```bash
curl -fsS http://127.0.0.1:8090/agent/health | python3 -m json.tool
```

**Container & cổng**

**CHẠY TRÊN SERVER**
```bash
docker ps --filter name=mesflow-deploy-agent
```

**CHẠY TRÊN SERVER**
```bash
sudo ss -ltnp | grep ':8090'
```

**Các trường quan trọng trong health (ví dụ thật, lấy từ một máy DEV)**

agent_version   "2.24.8-docker-runtime"
server_role     "DEV"                    ← xác nhận đúng ý định (Bước 06)
build_enabled   true                        ← DEV: true, Test/Production: false
deploy_enabled  true
mes.docker.available   true
mes.docker.healthy     true
mes.online             true
qa.online              true

**KẾT QUẢ MONG ĐỢI:** ok: true, server_role đúng ý định, docker ps thấy container mesflow-deploy-agent đang Up.

**NẾU LỖI THÌ LÀM GÌ:** ok: false hoặc curl connection refused → xem mục 'Sự cố thường gặp — DEPLOY AGENT OFFLINE' phía dưới.

**TIẾP THEO:** Bước 09 — Deploy MESFlow

### 09. Deploy MESFlow

**MỤC ĐÍCH:** Build MỘT LẦN trên DEV, deploy local để lấy LOCAL_PASS, promote đúng artifact đó (cùng SHA/digest) sang Production Test, lấy TEST_PASS, rồi mới cân nhắc Production — không bao giờ build lại giữa các môi trường.

**THỰC HIỆN Ở ĐÂU:** Build trên DEV. Promote/deploy thao tác qua Deploy Agent Web (SSH tunnel cổng 18090) trên từng máy đích.

**Thứ tự triển khai cho một server hoàn toàn mới**

1. Bootstrap  (Bước 04)
2. Deploy Agent  (Bước 07)
3. PostgreSQL — do compose của MESFlow tự tạo khi deploy, KHÔNG cần khởi tạo tay
4. MESFlow (mesflow-app)
5. nginx/gateway — nếu compose hiện tại của bạn có bao gồm; kiểm tra trực tiếp compose đang dùng trên máy đó, đừng giả định
6. QA Center (Bước 10)

PostgreSQL không cần thao tác thủ công riêng: nó nằm trong compose mà Deploy Agent triển khai cùng MESFlow (thấy trong health thật: mes.docker.container_ids.postgres, mes.docker.service_health.postgres).

**A. Build Release trên DEV**

Deploy Agent Web (DEV) → Release & Deploy → Build Release. Chạy scripts/build-release.sh, tạo image bất biến mesflow-app:<version> (gắn tag VÀ định danh bằng digest) + ZIP dưới artifacts/releases/<version>/, đóng băng: version, source_commit, package sha256 (checksums.txt), image_digest, expected_schema_revision (release.json). Bị chặn nếu MESFLOW_BUILD_ENABLED=0 (không phải máy DEV) — đúng như thiết kế.

**B. Deploy Local (trên chính DEV) → LOCAL_PASS**

Release & Deploy → Deploy Local. Deploy --no-build đúng image vừa build (theo digest, không phải theo tag). LOCAL_PASS được tính từ bằng chứng thật, không phải return code: image id đang chạy phải khớp release đã đóng băng, Alembic head thật (/api/system/ready → migration_head) phải khớp expected_schema_revision, và một smoke check HTTP tới /login phải thành công.

**C. Promote Production Test → TEST_PASS**

Release & Deploy → Promote Production Test.

TRƯỚC KHI bấm: xác nhận health của Production Test (Bước 08 lặp lại trên máy Test) VÀ server_role của Production Test PHẢI đúng PRODUCTION_TEST.

**CHẠY TRÊN SERVER**
```bash
curl -fsS http://127.0.0.1:8090/agent/health | grep -o '"server_role":"[^"]*"'
```
> Chạy trên máy Production Test — kết quả bắt buộc: "server_role":"PRODUCTION_TEST"

Cần LOCAL_PASS cho đúng version + Agent DEV đã cấu hình MESFLOW_PRODUCTION_TEST_AGENT_URL/_USER/_PASSWORD. Deploy Agent upload đúng ZIP đã LOCAL_PASS, kích hoạt --no-build trên máy đích, poll tới khi xong, ghi nhận TEST_PASS.

**⚠ NGỪNG NGAY nếu vai trò máy đích không khớp**

Nếu curl ở trên KHÔNG trả về đúng PRODUCTION_TEST cho máy Production Test — DỪNG LẠI. Không upload, không deploy. Sửa vai trò trước (phần 'Vai trò server' → mục fix), xác minh lại, rồi mới tiếp tục.

**D. Production Deploy — CẦN PHÊ DUYỆT NGƯỜI, MỖI LẦN**

Release & Deploy → Promote Production. Endpoint này tự kiểm tra lại toàn bộ điều kiện mỗi lần gọi (LOCAL_PASS + TEST_PASS + đúng zip sha + đúng image digest + schema PASS + không bị contaminated), trả về 403 trừ khi Agent được bật MESFLOW_PRODUCTION_PROMOTE_ENABLED=1 VÀ request có {"confirm": true} tường minh — và ngay cả khi đủ điều kiện, endpoint này trong bản Agent hiện tại chỉ trả về 501 (chưa thật sự thực thi deploy Production — mới dừng ở phần đấu dây/kiểm tra điều kiện). Không có đường tắt tự động nào deploy Production.

**KẾT QUẢ MONG ĐỢI:** Pipeline status trên Deploy Agent Web hiện đúng chuỗi: BUILT → LOCAL_PASS → TEST_PASS, với lý do rõ ràng bất cứ khi nào một nút bị mờ.

**NẾU LỖI THÌ LÀM GÌ:** LOCAL_PASS bị BLOCKED với lý do QA_RUNNER_UNAVAILABLE → không phải bug, chỉ là QA Center tạm thời không resolve được trên mạng Docker — đợi QA Center khoẻ lại rồi bấm lại Deploy Local (idempotent). 'No release has been built yet' dù artifacts/releases/<version> có thật trên máy → kiểm tra lại mount workspace + server_role=DEV (Bước 06).

**TIẾP THEO:** Bước 10 — Deploy QA Center

### 10. Deploy QA Center

**MỤC ĐÍCH:** QA Center là một release ĐỘC LẬP với MESFlow — build riêng, version riêng, nhưng deploy qua cùng Deploy Agent với luồng tương tự.

**THỰC HIỆN Ở ĐÂU:** Build trên DEV (trong chính QA Center hoặc trong Deploy Agent); deploy qua Deploy Agent Web.

**Sửa file nào trước khi build version mới**

qa-center/current/VERSION — version nguồn.
qa-center/current/agent.py — APP_VERSION PHẢI khớp CHÍNH XÁC với VERSION, nếu không build bị chặn VERSION_MISMATCH.

**Hai nơi có thể bấm Build — cùng ra một kết quả**

1. Trong chính QA Center: trang Release Package (chỉ hiện khi chạy trực tiếp từ workspace, không có trong image đã đóng gói) → Build Release ZIP → chạy nền, poll trạng thái → Download ZIP để tự tay upload lên Deploy Agent.
2. Trong Deploy Agent: tab QA Center → Build Release (POST /api/qa-release-manager/build) — gọi đúng qa-center/scripts/build-release.sh, không phải bản build riêng.

**Kết quả build**

artifacts/qa-center/releases/<version>/QACenter_<version>.deploy.zip, kèm manifest.json (version, source commit, previous release, changed files, diff stat, artifact SHA256), CHANGELOG.md, checksums.txt, BUILD_REPORT.md.

**Deploy**

Trong Deploy Agent, sau build có thể Deploy Local / Promote Production Test ngay — bám sát luồng của MESFlow. Deploy Agent nhận QA ZIP qua POST /qa-release/upload, verify checksum + image digest, rồi POST /qa-release/deploy/<version> mới thật sự deploy — không có bước nào tự động deploy chỉ vì đã upload.

**Luật bất biến version — giống hệt MESFlow**

Nếu build báo VERSION_ALREADY_RELEASED: version đó đã đóng băng, không sửa được — tăng qa-center/current/VERSION (và APP_VERSION khớp theo) rồi build lại. Không bao giờ ghi đè metadata release đã đóng băng.

**KẾT QUẢ MONG ĐỢI:** QA Center container chạy khoẻ, /agent/health của Deploy Agent báo qa.online: true.

**NẾU LỖI THÌ LÀM GÌ:** VERSION_MISMATCH → đồng bộ lại VERSION và APP_VERSION cho khớp tuyệt đối rồi build lại.

**TIẾP THEO:** Bước 11 — Kiểm tra sau deploy

### 11. Kiểm tra sau deploy

**MỤC ĐÍCH:** Xác nhận toàn bộ hệ thống thật sự hoạt động, không chỉ dừng ở 'lệnh deploy chạy xong không lỗi'.

**THỰC HIỆN Ở ĐÂU:** Trên server vừa deploy, và trình duyệt qua SSH tunnel để kiểm tra ứng dụng.

**Containers & dịch vụ**

**CHẠY TRÊN SERVER**
```bash
docker ps
```

**CHẠY TRÊN SERVER**
```bash
curl -fsS http://127.0.0.1:8090/agent/health | python3 -m json.tool
```

**Health từng thành phần (đọc trong JSON /agent/health ở trên)**

mes.online, mes.docker.healthy, mes.health_payload.status
mes.health_payload.postgres_version, mes.docker.service_health.postgres
qa.online, qa.payload.ok

**Log khi cần soi kỹ hơn**

**CHẠY TRÊN SERVER**
```bash
docker logs --tail=200 mesflow-deploy-agent
```

**CHẠY TRÊN SERVER**
```bash
docker logs --tail=200 <container_mesflow_hoặc_qa>
```

**Kiểm tra ứng dụng qua trình duyệt (qua tunnel Bước 05/15)**

Đăng nhập → Dashboard → tạo/xem một Production Order → mở một Session → (nếu áp dụng) kiosk → QA Center. Đây là bước xác nhận thật sự bằng mắt, không chỉ dựa vào health JSON.

**KẾT QUẢ MONG ĐỢI:** Mọi container Up, mes.health_payload.status = healthy, đăng nhập + các trang chính mở được không lỗi.

**NẾU LỖI THÌ LÀM GÌ:** Xem mục 'Sự cố thường gặp' và 'Recovery flow' phía dưới — đi theo đúng thứ tự chẩn đoán, không nhảy cóc.

**TIẾP THEO:** Bước 12 — Recovery / xử lý lỗi (khi có sự cố)

### 12. Recovery / xử lý lỗi

**MỤC ĐÍCH:** Khi có sự cố, đi theo đúng cây quyết định thay vì đoán mò — mỗi câu trả lời NO dẫn tới đúng hành động kế tiếp.

**THỰC HIỆN Ở ĐÂU:** Tuỳ tầng gặp sự cố — bắt đầu luôn từ SSH.

**Xem chi tiết đầy đủ ở hai mục cuối trang**

'Sự cố thường gặp' (triệu chứng → nguyên nhân → cách xử lý) và 'Cây quyết định phục hồi' (theo từng câu hỏi Có/Không) được trình bày riêng bên dưới trang này để dễ tra cứu lại sau, không lặp lại ở đây.

**KẾT QUẢ MONG ĐỢI:** Xác định đúng tầng đang lỗi và hành động đúng cho tầng đó, không đoán mò/không chạy lệnh phá huỷ dữ liệu.

**NẾU LỖI THÌ LÀM GÌ:** Nếu không chắc chắn nguyên nhân → DỪNG LẠI, không chạy lệnh phá huỷ (không prune, không xoá volume, không DROP/TRUNCATE) — ghi lại triệu chứng thật và log liên quan trước khi thử bất cứ hành động sửa nào.

**TIẾP THEO:** Hoàn tất — quay lại Checklist trạng thái cuối trang để xác nhận đầy đủ.


## Sự cố thường gặp

### PORT ĐÃ BỊ CHIẾM (port already in use)

**Triệu chứng:**
```
docker start mesflow-app
→ failed to bind 127.0.0.1:8080: address already in use
```

**Chẩn đoán:**

**CHẠY TRÊN SERVER**
```bash
sudo ss -ltnp | grep ':8080'
```

**CHẠY TRÊN SERVER**
```bash
docker ps --format 'table {{.Names}}\t{{.Ports}}\t{{.Status}}'
```

**Xử lý:** Xác định tiến trình/container nào đang giữ cổng đó trước khi làm bất cứ gì — có thể là một container cũ chưa dừng hẳn, hoặc một dịch vụ khác trên máy. Dừng đúng cái đang giữ cổng sai, không đoán mò.

### CONTAINER BỊ DỪNG

**Triệu chứng:**
```
docker ps -a  → container ở trạng thái Exited
```

**Chẩn đoán:**

**CHẠY TRÊN SERVER**
```bash
docker ps -a
```

**Xử lý:** Bootstrap → Docker (nút Start cho mesflow-deploy-agent), hoặc trong Deploy Agent Web → trang Services/Dịch vụ tương ứng để Start container đó. Không tự ý docker rm rồi tạo lại thủ công.

### HẾT DUNG LƯỢNG ĐĨA

**Triệu chứng:**
```
df -h cho thấy /  gần đầy hoặc đầy
```

**Chẩn đoán:**

**CHẠY TRÊN SERVER**
```bash
df -h
```

**CHẠY TRÊN SERVER**
```bash
docker system df
```

**Xử lý:** KHÔNG tự động chạy prune phá huỷ (docker system prune -a, docker volume prune...). Xem release retention: Deploy Agent tự dọn release cũ (giữ mặc định 3 bản gần nhất) sau mỗi LOCAL_PASS/TEST_PASS thành công, có thể kích hoạt thủ công qua POST /api/release-manager/cleanup-releases. Với dữ liệu khác (log, backup...), xác nhận với người có thẩm quyền trước khi xoá.

### RAM CAO

**Triệu chứng:**
```
free -h cho thấy RAM khả dụng thấp
```

**Chẩn đoán:**

**CHẠY TRÊN SERVER**
```bash
free -h
```

**CHẠY TRÊN SERVER**
```bash
docker stats --no-stream
```

**Xử lý:** Xác định container nào chiếm nhiều nhất qua docker stats trước khi hành động — đừng restart hàng loạt. Nếu là rò rỉ bộ nhớ nghi vấn, thu log rồi báo cáo thay vì tự khởi động lại Production.

### DEPLOY AGENT OFFLINE

**Triệu chứng:**
```
curl http://127.0.0.1:8090/agent/health → connection refused
```

**Chẩn đoán:**

**CHẠY TRÊN SERVER**
```bash
docker ps --filter name=mesflow-deploy-agent
```

**CHẠY TRÊN SERVER**
```bash
docker logs --tail=200 mesflow-deploy-agent
```

**Xử lý:** Bootstrap Overview đã tự phát hiện tình trạng này (badge 'Deploy Agent Stopped'/'Unhealthy'/'Not Installed') và hiện đúng nút hành động: Start/Restart, hoặc Install Deploy Agent nếu chưa từng cài. Nếu vẫn không lên, dùng Bootstrap → Install Deploy Agent để reinstall/update package.

### QUÊN MẬT KHẨU (Bootstrap / Deploy Agent / MESFlow)

**Triệu chứng:**
```
Không đăng nhập được vào Bootstrap Web, Deploy Agent Web, hoặc ứng dụng MESFlow.
```

**Xử lý:** Xem mục riêng '**Khôi phục truy cập / Quên mật khẩu**' ngay bên dưới trang này — mỗi hệ thống có cơ chế khôi phục khác nhau, trình bày đầy đủ theo từng bước ở đó thay vì lặp lại ở đây.

### LỆNH `reset-admin` BÁO "unknown command"

**Triệu chứng:**
```
docker exec mesflow-app python -m mesflow.cli reset-admin
→ unknown command
```

**Chẩn đoán:**

**CHẠY TRÊN SERVER MESFLOW**
```bash
docker exec mesflow-app grep -o "funcs={[^}]*}" /app/mesflow/cli.py
```
> Đọc thẳng danh sách lệnh CLI thật đang có trong image đang chạy — đã xác minh trực tiếp trên một host DEV thật lúc viết mục này, kết quả chỉ có: wait-db, seed-admin, seed-default-users, reset-admin, verify-schema, record-deployment, run-predictive.

**Xử lý:** KHÔNG đoán/thử một subcommand khác. Chỉ dùng đúng tên lệnh xuất hiện trong kết quả grep ở trên — danh sách lệnh CÓ THỂ khác nhau giữa các version MESFlow, nên luôn kiểm tra lại trên chính host đang thao tác thay vì tin vào tài liệu cũ (kể cả trang này) mà không xác minh. Nếu `reset-admin` không xuất hiện, image đang chạy là một bản MESFlow khác/cũ hơn những gì trang này mô tả — dừng lại và xác nhận version trước khi tiếp tục, đừng thử lệnh khác 'cho chắc'.

### mesflow-app KHÔNG CHẠY (docker exec không vào được)

**Triệu chứng:**
```
docker exec mesflow-app ...
→ Error: No such container: mesflow-app
```

**Chẩn đoán:**

**CHẠY TRÊN SERVER MESFLOW**
```bash
docker ps -a --filter name=mesflow-app
```
> Xem trạng thái thật: không tồn tại, Exited, hay Restarting.

**Xử lý:** Nếu container tồn tại nhưng đang dừng: khởi động lại đúng container đó qua Deploy Agent (Docker/Services) trước, rồi mới thử lại `reset-admin` — `docker exec` chỉ hoạt động trên container đang chạy. KHÔNG tự ý `docker compose down -v` hay tạo lại database chỉ vì không exec được — đó là hai việc không liên quan tới nhau, và lệnh `-v` xoá volume dữ liệu thật.

### BOOTSTRAP OFFLINE

**Triệu chứng:**
```
curl http://127.0.0.1:8098/health không phản hồi
```

**Chẩn đoán:**

**CHẠY TRÊN SERVER**
```bash
sudo systemctl status mesflow-bootstrap
```

**Xử lý:** Bootstrap chạy dưới systemd, độc lập với Docker — nếu service không active:

**CHẠY TRÊN SERVER**
```bash
sudo systemctl restart mesflow-bootstrap
```

**CHẠY TRÊN SERVER**
```bash
journalctl -u mesflow-bootstrap -n 100 --no-pager
```


## Quên mật khẩu / Mất quyền truy cập

### Bootstrap

**Nếu quên:** Chạy script reset cục bộ ngay trên server — không có, và sẽ không có, đường web nào để tự reset (nếu bạn còn đăng nhập được vào Bootstrap Web thì bạn vốn không cần script này; xem `bootstrap/AGENTS.md`: đây là quyết định thiết kế cố định, không phải thiếu sót).

**Cần quyền gì:** SSH vào server + quyền `sudo`/root (đúng quyền `install.sh` đã yêu cầu, không hơn).

**Lệnh / URL chính xác:**

**CHẠY TRÊN MÁY DEV**
```bash
ssh mesflow-test
```

**CHẠY TRÊN SERVER**
```bash
sudo /opt/mesflow-bootstrap/bin/reset-admin-password
```
> Hỏi mật khẩu mới hai lần (không hiện lên màn hình), có thể đổi cả username bằng `--username <tên_mới>`. Chỉ ghi đè đúng hai trường `admin_username`/`admin_password_hash` trong `state.json` — mọi thứ khác (secret_key, agent_updater_token, setup_complete, ...) giữ nguyên.

**Kết quả mong đợi:** In ra `OK: đã đặt lại mật khẩu cho '<username>'.` Không cần restart `mesflow-bootstrap` — route `/login` đọc lại `state.json` ở mỗi lần đăng nhập, nên mật khẩu mới có hiệu lực ngay.

**Không được làm:** KHÔNG tự tay sửa `admin_password_hash` trong `state.json` bằng tay (hash sai định dạng sẽ khoá tài khoản hẳn). KHÔNG mở cổng 8098 ra Internet chỉ để 'dễ' truy cập khôi phục.

**Cách xác nhận đã khôi phục:**

**TRÌNH DUYỆT (TRÊN LAPTOP)**
```bash
http://127.0.0.1:18098/login
```
> Đăng nhập thử ngay bằng mật khẩu vừa đặt (qua tunnel Bước 05).

**CHẠY TRÊN SERVER**
```bash
sudo tail -5 /var/lib/mesflow-bootstrap/logs/audit.log
```
> Dòng mới nhất phải có `admin_password_reset`.

### Deploy Agent

**Nếu quên:** Còn giữ Recovery Code (in trong `FIRST_LOGIN.txt` lúc cài lần đầu, hoặc đã lưu riêng) → dùng trang Forgot Password ngay trong Deploy Agent Web. Mất luôn Recovery Code → dùng `/agent/local-reset`, chỉ hoạt động khi request tới TỪ chính localhost của server (qua SSH tunnel) — không thể gọi từ Internet dù có biết URL.

**Cần quyền gì:** SSH vào server để mở tunnel tới loopback (127.0.0.1:8090) — server không có desktop/trình duyệt, trình duyệt luôn chạy trên laptop, tunnel là đường duy nhất để trình duyệt đó 'trông giống' đang đứng trên chính server.

**Lệnh / URL chính xác:**

**CHẠY TRÊN MÁY DEV**
```bash
ssh -N -L 18090:127.0.0.1:8090 mesflow-test
```
> Giữ terminal này mở.

**TRÌNH DUYỆT (TRÊN LAPTOP)**
```bash
http://127.0.0.1:18090/agent/forgot-password
```
> Nếu còn Recovery Code: nhập Recovery Code + mật khẩu mới.

**TRÌNH DUYỆT (TRÊN LAPTOP)**
```bash
http://127.0.0.1:18090/agent/local-reset
```
> Nếu KHÔNG còn Recovery Code: chỉ cần mật khẩu mới (route tự nhận diện request đến từ loopback của chính server, không hỏi Recovery Code).

**Kết quả mong đợi:** Thông báo 'Đã đặt lại mật khẩu. Hãy đăng nhập lại.' (Forgot Password) hoặc 'Đã đặt lại mật khẩu từ máy chủ. Hãy đăng nhập.' (local-reset). File `FIRST_LOGIN.txt` (nếu còn) bị xoá.

**Không được làm:** KHÔNG bao giờ bind Deploy Agent ra `0.0.0.0:8090` để tránh phải mở tunnel — luôn giữ `127.0.0.1:8090` (xem mục Kiểm tra bảo mật). KHÔNG tự sửa `config/agent.json` bằng tay.

**Cách xác nhận đã khôi phục:**

**CHẠY TRÊN SERVER**
```bash
docker logs mesflow-deploy-agent --tail=50 | grep 'Administrator password reset'
```
> Xác nhận Agent đã thật sự ghi nhận việc đổi mật khẩu.

**TRÌNH DUYỆT (TRÊN LAPTOP)**
```bash
http://127.0.0.1:18090/agent/
```
> Đăng nhập thử bằng mật khẩu mới.

### MESFlow

**Nếu quên:** Có **hai tình huống khác nhau** — đừng dùng nhầm cách của tình huống này cho tình huống kia:

**A. Quên mật khẩu một user THƯỜNG** (manager/supervisor/operator/viewer, hoặc admin khác vẫn còn đăng nhập được) → dùng ngay màn hình **Người dùng hệ thống** trong MESFlow, KHÔNG cần SSH.

**B. Mất/quên đúng mật khẩu admin CUỐI CÙNG** (không còn ai đăng nhập được) → phải SSH vào server và chạy CLI `reset-admin` — đây là lệnh DUY NHẤT hiện có trong image MESFlow đang chạy cho tình huống này. (Mã nguồn workspace hiện có thêm một hàm `reset_password()` an toàn hơn cho user thường, nhưng NÓ CHƯA nằm trong bất kỳ bản MESFlow nào đã build/deploy — xác nhận trực tiếp trên container đang chạy: `grep -o "funcs={[^}]*}" /app/mesflow/cli.py` bên trong container không liệt kê `reset-password`. Đừng dùng lệnh đó cho tới khi nó thật sự có trong một bản đã deploy.)

**Cần quyền gì:** Tình huống A: chỉ cần một tài khoản còn đăng nhập được với quyền `users.manage` (thường là admin) — không cần SSH. Tình huống B: SSH vào server + quyền chạy `docker exec` trên host đó (không cần quyền PostgreSQL trực tiếp).

**Lệnh / URL chính xác:**

**CHẠY TRÊN MÁY DEV**
```bash
ssh <server>
```
> Bước A — kết nối tới server đang chạy MESFlow từ laptop.

**CHẠY TRÊN SERVER MESFLOW**
```bash
docker ps --filter name=mesflow-app
```
> Bước B — xác nhận container mesflow-app đang chạy trước khi exec vào.

**CHẠY TRÊN SERVER MESFLOW**
```bash
docker exec mesflow-app python -c 'from mesflow.core.config import settings; print(settings.admin_username)'
```
> Bước C — xác nhận đúng username admin đang cấu hình, KHÔNG lộ mật khẩu.

**CHẠY TRÊN SERVER MESFLOW**
```bash
read -s -p "Mật khẩu admin mới: " NEWPASS
echo
```
> Bước D — đọc mật khẩu mới vào biến shell, không hiện lên màn hình, không nằm trong lịch sử lệnh.

**CHẠY TRÊN SERVER MESFLOW**
```bash
docker exec \
  -e MESFLOW_ADMIN_PASSWORD="$NEWPASS" \
  mesflow-app \
  python -m mesflow.cli reset-admin
```
> Bước E — thực hiện reset thật. `-e MESFLOW_ADMIN_PASSWORD="$NEWPASS"` chỉ set biến môi trường cho đúng tiến trình exec này, không ghi đè environment gốc của container.

**CHẠY TRÊN SERVER MESFLOW**
```bash
unset NEWPASS
```
> Bước F — xoá biến shell ngay sau khi dùng xong.

**Kết quả mong đợi:** `[SEED] Administrator password reset for <username>; id=<id>`. Không cần restart PostgreSQL, không cần restart `mesflow-app` — lệnh chạy ngay bên trong tiến trình container đang sống, ghi thẳng xuống DB qua UPDATE. Chỉ đúng một hàng (`settings.admin_username`) bị đổi; role/quyền của các user khác không bị đụng tới. `reset-admin` (theo đúng code hiện tại) LUÔN gán lại `role='admin'` và `active=true` cho tài khoản đó mỗi lần chạy — đúng ý nghĩa 'khôi phục tài khoản admin', không phải sự cố.

**Không được làm:** KHÔNG gõ mật khẩu thẳng vào dòng lệnh, ví dụ `docker exec -e MESFLOW_ADMIN_PASSWORD=MySecret123 ...` — giá trị đó nằm luôn trong lịch sử shell (`~/.bash_history`) và trong danh sách tiến trình lúc đang chạy. Luôn theo đúng thứ tự `read -s` → biến shell → `docker exec` → `unset` ở trên. KHÔNG bao giờ in mật khẩu ra màn hình/log. KHÔNG ghi mật khẩu khôi phục vào repo, README, hay `.env` — trừ khi bạn CHỦ ĐỘNG đang đổi luôn nguồn secret bền vững (xem cảnh báo `MESFLOW_ADMIN_PASSWORD` bên dưới). KHÔNG dùng `reset-admin` cho bảo trì tài khoản thông thường (đổi mật khẩu cho manager/supervisor/operator/viewer) — dùng màn hình Người dùng hệ thống cho việc đó, `reset-admin` chỉ dành riêng cho đúng một tài khoản admin cố định. KHÔNG bao giờ UPDATE trực tiếp cột `password_hash` bằng SQL tay.

**Cách xác nhận đã khôi phục:**

**TRÌNH DUYỆT (TRÊN LAPTOP)**
```bash
https://<mesflow-url>/login
```
> Đăng nhập thử ngay bằng mật khẩu mới.

Riêng Deploy Agent có một điểm dễ gây nhầm: nếu biến môi trường `MESFLOW_AGENT_ADMIN_PASSWORD` đang được set (trong `deploy-agent/docker/.env` hoặc shell env lúc chạy `docker compose up`), thì MỖI LẦN container được tạo lại (update, rollback, recreate) sẽ tự động ghi ĐÈ `password_hash` về đúng giá trị của biến đó — âm thầm huỷ tác dụng của một lần reset qua local-reset/forgot-password trước đó (`ensure_config()` trong `deploy-agent/agent.py` chạy lại mỗi lần tiến trình khởi động). Mặc định biến này để trống (không set) nên hành vi này không xảy ra trên một máy cài mặc định — nhưng nếu bạn CÓ set nó, hãy coi nó là nguồn sự thật (canonical secret source): sau khi reset xong, cập nhật lại (hoặc bỏ hẳn) `MESFLOW_AGENT_ADMIN_PASSWORD` để khớp, nếu không lần recreate kế tiếp sẽ đưa mật khẩu cũ quay lại.

**Dự phòng dòng lệnh cho Deploy Agent** — nếu vì lý do nào đó không dùng được cả hai route web ở trên: `deploy-agent/reset_password.py` (script Python độc lập, cần `werkzeug`) ghi thẳng vào `config/agent.json`. Lưu ý mặc định `--home` của script này trỏ tới đường dẫn Windows (`C:\WorkshopManagementAgent`, cho biến thể cài trên Windows) — với server Linux/Docker đang mô tả trong hướng dẫn này, phải trỏ đúng thư mục dữ liệu thật bằng `--home /var/lib/mesflow-deploy-agent`. Cách an toàn nhất để chạy đúng phiên bản Python có sẵn `werkzeug` là qua chính venv của Agent nếu cài kiểu legacy (non-Docker); với bản Docker hiện tại, ưu tiên `/agent/local-reset` ở trên trước — nó không cần dừng container hay cài thêm gì.

Riêng MESFlow cũng có một điểm dễ gây nhầm tương tự Deploy Agent, nhưng khác cơ chế: đọc `mesflow/compose.yml` xác nhận service `mesflow-app` dùng `env_file: [.env]` — nghĩa là TOÀN BỘ nội dung `/opt/mesflow/.env`, bao gồm cả `MESFLOW_ADMIN_PASSWORD` nếu có, được nạp vào container mỗi lần khởi động. Đọc `scripts/docker-entrypoint.sh` xác nhận entrypoint gọi `seed-admin` ở MỖI lần khởi động container — nhưng `seed_admin()` tự kiểm tra `repo.count()==0` trước, nên nó chỉ tạo admin ở lần khởi động ĐẦU TIÊN (chưa có user nào); một lần restart/recreate container BÌNH THƯỜNG SAU NÀY KHÔNG tự động ghi đè lại mật khẩu admin đã reset — đã xác minh trực tiếp trong code, không suy đoán. Rủi ro thật nằm ở chỗ khác: nếu sau này có ai (hoặc một script khác) chạy lại `reset-admin` mà KHÔNG tự tay truyền `-e MESFLOW_ADMIN_PASSWORD=...`, lệnh đó sẽ âm thầm dùng đúng giá trị đang nằm trong `/opt/mesflow/.env` lúc đó (qua `env_file`) — có thể là một mật khẩu cũ/yếu bạn tưởng đã thay. Nguồn sự thật bền vững (canonical secret source) là `/opt/mesflow/.env`'s `MESFLOW_ADMIN_PASSWORD`/`MESFLOW_ADMIN_USERNAME` — nếu bạn muốn mật khẩu vừa reset cũng là giá trị mà lần `reset-admin` kế tiếp sẽ dùng, cập nhật luôn file đó (0600, chỉ root đọc được), đừng chỉ đổi qua `-e` một lần rồi quên.


**Ma trận truy cập khẩn cấp**

| Quên gì | Cần gì | Cách khôi phục |
|---|---|---|
| Mật khẩu user MESFlow thường (không phải admin) | Một tài khoản MESFlow admin còn đăng nhập được | Người dùng hệ thống → chọn user → Reset mật khẩu |
| Mật khẩu admin MESFlow (mất/quên đúng tài khoản admin cuối cùng) | SSH vào server MESFlow | docker exec ... mesflow-app python -m mesflow.cli reset-admin |
| Mật khẩu Deploy Agent | SSH (tunnel tới loopback) hoặc còn Recovery Code | /agent/local-reset · /agent/forgot-password · reset_password.py (dự phòng) |
| Mật khẩu Bootstrap | SSH vào server | Script reset cục bộ (bin/reset-admin-password) |


⚠ Mất luôn SSH → không cơ chế reset nào ở trên giúp được (Bootstrap/Deploy Agent/MESFlow đều yêu cầu SSH trước tiên) → phải dùng console/recovery access của nhà cung cấp hạ tầng (cloud console, out-of-band KVM, ...), không phải vấn đề phần mềm MESFlow.


**Cảnh báo bảo mật**

- ⚠ Không bao giờ mở public các cổng quản trị (8098 Bootstrap, 8090 Deploy Agent, cổng đăng nhập MESFlow) ra Internet chỉ để 'dễ' khôi phục — luôn đi qua SSH tunnel như hướng dẫn ở trên.
- ⚠ Không bao giờ xoá file/DB xác thực (state.json, config/agent.json, bảng users) để 'reset cho nhanh'.
- ⚠ Không bao giờ tự tay sửa password_hash trong bất kỳ file hay bảng nào — luôn dùng đúng script/CLI đã kiểm chứng ở trên, chúng tự lo đúng định dạng hash + audit log.
- ⚠ Không bao giờ tắt xác thực toàn cục (bypass đăng nhập) để né việc quên mật khẩu.
- ⚠ Không dùng chung một mật khẩu admin cho cả Bootstrap, Deploy Agent và MESFlow — lộ một nơi thì mất cả ba.

## Cây quyết định phục hồi

Đi từ trên xuống, dừng lại ở câu đầu tiên trả lời KHÔNG:

- **SSH kết nối được vào server không?**
  - Không → Vấn đề hạ tầng/nhà cung cấp/mạng — kiểm tra qua console nhà cung cấp, không phải lỗi phần mềm MESFlow.
  - Có → đi tiếp câu hỏi kế tiếp
- **Bootstrap healthy? (curl 127.0.0.1:8098/health)**
  - Không → sudo systemctl restart mesflow-bootstrap  →  kiểm tra lại
  - Có → đi tiếp câu hỏi kế tiếp
- **Deploy Agent healthy? (curl 127.0.0.1:8090/agent/health)**
  - Không → Bootstrap → Start/Restart/Reinstall Deploy Agent (Overview hoặc Install Deploy Agent)
  - Có → đi tiếp câu hỏi kế tiếp
- **Docker khả dụng? (docker ps chạy được, docker info không lỗi)**
  - Không → Kiểm tra dịch vụ Docker: sudo systemctl status docker — không tự ý cài lại Docker khi chưa rõ nguyên nhân
  - Có → đi tiếp câu hỏi kế tiếp
- **PostgreSQL healthy? (trong /agent/health: mes.docker.service_health.postgres)**
  - Không → Chẩn đoán bằng docker logs vào container postgres — TUYỆT ĐỐI KHÔNG tự ý tạo lại database
  - Có → đi tiếp câu hỏi kế tiếp
- **MESFlow đang chạy? (mes.online: true)**
  - Không → Start lại hoặc redeploy đúng bản đã biết là tốt (known-good release) qua Deploy Agent — không build mới giữa chừng
  - Có → đi tiếp câu hỏi kế tiếp
- **nginx/gateway healthy? (nếu compose của bạn có thành phần này)**
  - Không → Restart/kiểm tra cấu hình gateway — đây là thao tác cần phê duyệt người theo AGENTS.md (nginx cutover/reload ảnh hưởng production)
  - Có → đi tiếp câu hỏi kế tiếp

## Checklist trạng thái

### Chung

- [ ] SSH kết nối được (Bước 02)
- [ ] SERVER ROLE đã xác minh đúng ý định (Bước 06)
- [ ] Bootstrap healthy (curl :8098/health)
- [ ] Bootstrap chỉ bind localhost (ss -ltnp cho thấy 127.0.0.1:8098, không phải 0.0.0.0:8098)
- [ ] Docker healthy (docker ps chạy được, không lỗi)
- [ ] Deploy Agent healthy (curl :8090/agent/health → ok: true)
- [ ] Deploy Agent đúng vai trò (server_role khớp máy)
- [ ] PostgreSQL healthy (mes.docker.service_health.postgres = healthy)
- [ ] MESFlow đã deploy (mes.online: true)
- [ ] QA Center đã deploy (qa.online: true)
- [ ] MESFlow health PASS (mes.health_payload.status = healthy)
- [ ] QA health PASS (qa.payload.ok = true)
- [ ] Bằng chứng Test đã ghi nhận (LOCAL_PASS + TEST_PASS hiển thị trên Deploy Agent Web)

### Riêng cho Production

- [ ] Backup đã xác minh (Deploy Agent → Backup / DB / Storage — có bản backup gần nhất, verification_status ổn)
- [ ] TEST_PASS đã đạt cho đúng version định deploy
- [ ] server_role của máy đích = PRODUCTION (đã tự kiểm tra, không suy đoán)
- [ ] Artifact SHA/digest đã đối chiếu khớp giữa bản đã LOCAL_PASS/TEST_PASS và bản sắp deploy
- [ ] Có phê duyệt người tường minh cho lần deploy Production này (không dựa vào các lần trước)

## Thuật ngữ

**Artifact**
: Gói kết quả build đã đóng băng (ZIP + metadata: version, SHA256, digest) — thứ duy nhất được phép đi qua Test rồi Production, không bao giờ build lại giữa chừng.

**Image**
: Docker image — bản đóng gói ứng dụng thành lớp filesystem bất biến, chạy được bằng container.

**Container**
: Một tiến trình đang chạy từ một image, cô lập với host và các container khác.

**Docker Compose**
: Công cụ mô tả và khởi chạy nhiều container liên quan (service) bằng một hoặc nhiều file YAML.

**Bootstrap**
: Dịch vụ web độc lập, cổng 8098, dựng máy Ubuntu trống và cài/cứu hộ Deploy Agent.

**Deploy Agent**
: Control plane build/deploy/vận hành thật sự cho MESFlow và QA Center, cổng 8090.

**Production Test**
: Server test riêng, gần giống Production, dùng để thử artifact trước khi lên thật.

**Production**
: Máy chạy thật cho người dùng cuối, luôn cần phê duyệt người mỗi lần deploy.

**Release**
: Một version đã build xong, đóng băng metadata dưới artifacts/releases/<version>/.

**Promote**
: Đưa ĐÚNG artifact đã pass ở môi trường trước sang môi trường kế tiếp, không build lại.

**Rollback**
: Khôi phục lại phiên bản/image trước đó khi phiên bản mới không healthy.

**Health check**
: Kiểm tra tự động xem một dịch vụ có đang hoạt động đúng không, qua endpoint /health.

**SHA256**
: Hàm băm mật mã dùng để xác minh một file không bị thay đổi/hỏng khi truyền/lưu trữ.

**Digest**
: Định danh bất biến của một Docker image, tính từ nội dung — đáng tin hơn tag (tag có thể bị dời).

**Schema migration**
: Thay đổi cấu trúc database (Alembic) — luôn cần kiểm tra migration_head khớp kỳ vọng.

**SSH tunnel**
: Đường hầm mã hoá qua SSH, cho phép mở một cổng nội bộ của server ra máy laptop mà không public cổng đó ra Internet.

