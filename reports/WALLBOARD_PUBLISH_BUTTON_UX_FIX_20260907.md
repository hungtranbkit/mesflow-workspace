# "Trình chiếu trên Kiosk" — audit UX "bấm không thấy tác dụng" — 2026-09-07

Task: user báo bấm nút "Trình chiếu trên Kiosk" không thấy tác dụng gì.

## 1) Xác nhận handler/API/route thật (đọc code trước khi kết luận)

`app/mesflow/web/static/pages/employee-productivity.js`, handler
`#epWbPublish.onclick`:

```
POST /api/reports/employee-productivity/wallboard-config
```

→ lưu cấu hình thật vào `app_settings`, chính là cái
`GET /api/wallboard/employee-productivity` (màn hình công khai
`/kiosk/employee-productivity`, không cần đăng nhập) đọc mỗi lần làm
mới. **Backend hoạt động đúng** — đã tự xác nhận lại bằng test số liệu
thật nhiều lần trong phiên làm việc trước (DEMO/PRODTEST/DEV, xem các
report `WALLBOARD_3GROUP_REDESIGN_20260907.md` và
`WALLBOARD_DEV_DEPLOY_20260907.md`): mỗi lần publish, Kiosk công khai
đều phản ánh đúng cấu hình mới ngay lập tức.

**Kết luận: đây là vấn đề UX/feedback, không phải bug backend** — đúng
như user đã dự đoán trong yêu cầu, và đúng ưu tiên "không đổi backend
semantics" — route, payload, và ý nghĩa cấu hình đã lưu **không đổi**.

## 2) Nguyên nhân thật khiến user thấy "không có tác dụng"

Đọc chính xác những gì handler cũ làm khi bấm:
1. Disable nút (không đổi chữ, không có spinner).
2. Gọi API, đợi phản hồi.
3. Đổi 1 dòng subtitle nhỏ phía trên form (đã rút gọn từ task trước,
   càng ít chữ càng dễ bị lướt qua).
4. Hiện `toast()` — đọc `core/api.js`: **tự ẩn sau đúng 2.2 giây**
   (`setTimeout(()=>t.classList.remove('show'),2200)`), không có màu
   sắc phân biệt thành công/lỗi (tham số thứ 2 `'danger'` code cũ
   truyền vào bị bỏ qua hoàn toàn — `toast(msg)` chỉ nhận 1 tham số,
   phát hiện phụ, không sửa trong task này vì ngoài phạm vi feedback
   thành công đang audit).
5. **Không điều hướng đi đâu cả** — ở lại đúng trang quản trị.

Tên nút cũ "Trình chiếu trên Kiosk" tự nó gợi ý hành động "trình chiếu"
(mở màn hình) trong khi hành vi thật chỉ là "lưu cấu hình" — đúng gốc
rễ gây hiểu nhầm user đã chỉ ra.

## 3) Fix — chỉ UX/feedback, giữ nguyên toàn bộ backend

| | Trước | Sau |
|---|---|---|
| Tên nút | "Trình chiếu trên Kiosk" | **"Áp dụng lên Kiosk"** |
| Khi đang xử lý | chỉ disable, chữ không đổi | disable + đổi chữ thành **"Đang áp dụng..."**, khôi phục chữ gốc khi xong |
| Toast thành công | "Đã trình chiếu lên Kiosk." | **"Đã cập nhật cấu hình Kiosk."** (đúng với hành động thật) |
| Cách xem kết quả | phải tự nhớ/gõ URL Kiosk | **Link mới "Mở màn hình Kiosk ↗"** ngay cạnh 2 nút, `<a href="/kiosk/employee-productivity" target="_blank">` — bấm là thấy ngay |
| Nút "Xem trước" | không đổi | **không đổi** (vẫn preview riêng, không lưu) |
| Route/payload backend | `POST wallboard-config` | **không đổi 1 dòng nào** |

## 4) Test evidence — cả 3 môi trường

Playwright thật (không phải đọc source suông), sau khi deploy `71.0.0.226`:

| Kiểm tra | DEV (8080) | DEMO (8081) | PRODTEST (8299) |
|---|---|---|---|
| Nhãn nút lúc chờ | Áp dụng lên Kiosk | Áp dụng lên Kiosk | Áp dụng lên Kiosk |
| Link "Mở màn hình Kiosk" tồn tại, đúng href | ✔ | ✔ | ✔ |
| POST publish trả về | 200 | 200 | 200 |
| Toast thật hiện đúng chữ | "Đã cập nhật cấu hình Kiosk." | (giống) | (giống) |
| Nút khôi phục đúng chữ sau khi xong | ✔ | ✔ | ✔ |
| Dòng trạng thái cập nhật đúng | ✔ | ✔ | ✔ |
| Bấm "Mở màn hình Kiosk" mở đúng tab mới, đúng URL công khai | ✔ | ✔ | ✔ |
| Kiosk công khai phản ánh đúng dữ liệu | 0 thẻ — **đúng**, DEV không có dữ liệu năng suất thật (xem báo cáo DEV trước đó) | 15 thẻ | 15 thẻ |

Tutorial module `employeeProductivity` chạy lại tốc độ thật trên DEMO
sau khi sửa: **13 bước** (tăng 1 so với 12 trước, bước mới highlight
link "Mở màn hình Kiosk"), **0 bug**, `status=passed` (10.0 phút).

## 5) Build & Deploy

| | Trước | Sau |
|---|---|---|
| Image | `71.0.0.225` | **`71.0.0.226`** (commit `e4ddfc2`) |
| Digest | — | `sha256:48603e931baef54fcab8363a82c39e0ee4b675c1921f03452dcbd5a43c654f31` |
| Smoke test | — | PASS, migration không đổi |
| DEV | 71.0.0.225 | **71.0.0.226** — DEPLOY PASS (cùng cơ chế thủ công an toàn đã dùng lần trước) |
| DEMO | 71.0.0.225 | **71.0.0.226** — recreate qua script, healthy |
| PRODTEST | 71.0.0.225 | **71.0.0.226** — `scripts/deploy.sh` DEPLOY PASS |

Cấu hình wallboard-config trên cả 3 môi trường xác nhận vẫn ở giá trị
mặc định hợp lý (`employees_per_page=20, auto_page_flip_seconds=10,
columns=auto, sort=productivity_desc`) sau khi test — không để lại
trạng thái "demo" nào.

## 6) File đã sửa + commit

Repo `mesflow`:
- `app/mesflow/web/static/pages/employee-productivity.js` — đổi tên
  nút, thêm trạng thái đang xử lý, toast rõ nghĩa hơn, thêm link "Mở
  màn hình Kiosk".
- `app/mesflow/web/static/ui.css` — style cho link mới (reset link
  mặc định, căn giữa cùng chiều cao control).
- `tests/e2e/tutorial-detailed.spec.js` — narration cập nhật đúng tên
  nút mới, thêm bước highlight link mới.
- `VERSION.txt` → `71.0.0.226`.

Commit: `e4ddfc2` (fix chính) + `fe05207` (sync `release.json`). Đã
push `main` cả 2 repo.

## 7) Không nằm trong phạm vi lần sửa này

- Toast không phân biệt màu thành công/lỗi (tham số `'danger'` bị bỏ
  qua từ trước) — phát hiện phụ, ghi lại nhưng không sửa vì đây là vấn
  đề khác (styling lỗi, không phải "bấm không thấy tác dụng" khi
  THÀNH CÔNG mà user đang hỏi).
- Không đổi bất kỳ logic RBAC, validation, hay cấu trúc `wallboard-config`
  nào — đúng yêu cầu "ưu tiên không thay đổi backend semantics".
