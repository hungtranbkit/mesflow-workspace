# Khôi phục & Hoàn thiện Pipeline 15 Video Hướng Dẫn + Requirement Tiếng Việt — 2026-09-05

Task: sau sự cố mất điện, audit checkpoint (không làm lại mù), hoàn
thiện requirement tiếng Việt self-contained cho QA/QC agent, và hoàn
thiện pipeline 15 video hướng dẫn với dữ liệu realistic, kiosk nhiều
nhân viên, lỗi vận hành thật + cách xử lý.

## 1) Checkpoint sau mất điện — kết luận

**Không mất commit nào ở cả 2 repo.** Nhưng audit phát hiện repo mã
nguồn thật (`mesflow/mesflow`, không phải submodule — một `.git` độc
lập) có commit **muộn hơn 2 tiếng** so với báo cáo cuối cùng bên repo
"reports" ngoài (`2bad6a6`, 19:53:53): 3 commit lúc 20:21–21:55 đã lên
`main` nhưng **chưa từng được build/deploy** — bao gồm chính xác phần
việc task này yêu cầu (multi-employee kiosk demo, auto-close/exclusion
scenario thật, fix regression TUT39-CUT, fix ngày employeeProductivity
video). Đây là điểm mất điện thật, không phải commit mất — code đã có
sẵn, chỉ chưa release.

DEMO (`mesflow-demo-app`) khi audit có **0/15 video** (container không
có volume mount nào — `docker inspect` → `Mounts: []`), do video từng
được `docker cp` thẳng vào container và bị xóa khi container recreate
sang image mới ngày 4/9, **trước cả** loạt commit multi-employee ở
trên — cùng lớp lỗi đã được vá cho PRODTEST ngày 4/9 nhưng chưa áp
dụng cho DEMO.

## 2) Requirement tiếng Việt (Phần B)

- **File**: `mesflow/docs/MESFLOW_MASTER_REQUIREMENTS_VI.md` (2650 dòng)
- **Commit**: `7d99520` (nội dung), merge `a01b891` vào `main`
- **Số lượng**: 63 REQ (51 khối `REQ-*` Phần B + 12 dòng `REQ-UI-*`
  Phần D), 23 BR, 10 NFR — khớp 100% bản gốc tiếng Anh
- Có traceability matrix, testcase schema tiếng Việt (mục 22), giữ
  nguyên toàn bộ SPEC-GAP/OPEN-QUESTION, không tự suy diễn

**Gap phát hiện, chưa sửa (để dành cho task chuẩn hóa QC package kế
tiếp)**: hầu hết "Trigger" path trong tài liệu (cả EN lẫn VI) thiếu
tiền tố `/api` thật của Flask Blueprint (ví dụ tài liệu ghi
`GET /reports/employee-productivity`, route thật là
`GET /api/reports/employee-productivity` — xác nhận qua
`Blueprint(url_prefix='/api')` + gọi API sống). Ảnh hưởng gần như mọi
REQ-* có Trigger dạng route nghiệp vụ.

## 3) Bug thật phát hiện + đã sửa (có test evidence)

| # | Bug | Phát hiện bằng | Fix | Commit |
|---|---|---|---|---|
| 1 | DEMO không có volume mount cho `/data/tutorials` → video mất khi container recreate | `docker inspect` trực tiếp | Tạo `/home/dell/deploy/mesflow-demo/runtime/tutorials`, recreate container với bind mount bền vững (container cũ đổi tên `mesflow-demo-app-backup-71.0.0.221-*`, không xóa) | hạ tầng, không phải commit |
| 2 | Video pipeline login race với autologin: `/login`'s `data-test-auto-login="1"` tự submit + redirect trước khi Playwright kịp `fill('#username')` → 0/15 video quay được | Chạy trực tiếp pipeline, thấy timeout 100% | `tutorial-auth-state.js` điều hướng `/login?noauto=1` thay vì `/login` | `943067d` |
| 3 | `$OUT` (thư mục video sinh ra) không bao giờ được dọn giữa các lần chạy → 4 file từ **11/08/2026** (numbering CŨ, trước khi employeeProductivity được chèn vào slot 10) trộn lẫn với 15 file mới, thành 19 file/trùng số thứ tự khi publish | Chạy trực tiếp pipeline, `ls` thấy 19 file, đối chiếu timestamp | `scripts/make-user-guide-video.sh`: `rm -rf "$WORKSPACE" "$OUT"` thay vì chỉ `$WORKSPACE`; xóa thủ công 4 file rác 11/08 khỏi lần chạy hiện tại trước khi publish | `1c7b84f` |

Cả 2 fix code đều có **regression test riêng** đã verify fail-trước/pass-sau:
- `tests/test_video_pipeline_output_cleanup.py` (mới) — xác nhận fail
  trên bản chưa sửa (test qua `git stash`), pass sau khi sửa.
- `tests/test_tutorial_chapter_count_consistency.py` (đã có sẵn từ
  commit trước điện mất) — PASS 4/4, xác nhận 15 chapter nhất quán ở
  4 nguồn (pipeline script, publish script, narration, coverage-matrix).

**Phát hiện, không sửa (ngoài phạm vi, chỉ ghi nhận)**: `mesflow.net`
công khai thật đi qua Cloudflare, báo `server_role: PRODUCTION_TEST`,
`version: 71.0.0.219`, `commit: "unknown"` — **không khớp** với bất kỳ
container nào đang chạy trên máy này (`mesflow-app` cục bộ có cùng
version nhưng `SERVER_ROLE=DEV`, commit khác "unknown"). Ngược lại
`prod.mesflow.net` xác nhận khớp **chính xác từng byte commit**
(`a06c3a3a03b1`) với `mesflow-prodtest-app` vừa deploy. Kết luận: nguồn
gốc thật của `mesflow.net` là một hệ thống không xác định được từ máy
này — đúng như OPEN-QUESTION-001 đã cảnh báo trước, không giả định,
không đụng vào.

## 4) Dataset realistic (đã seed lại DEMO + PRODTEST, verify qua API thật)

Seed qua `python -m mesflow.tutorial_data seed` (idempotent, prefix
`TUT-`, guard `MESFLOW_TUTORIAL_DATA_ALLOW_PRODUCTION=1`) — 24 scenario
tag, gồm đúng các case bắt buộc:
`realistic_productivity_distribution_85pct_mean`,
`realistic_4to8h_session_durations`,
`auto_closed_unconfirmed_from_history`, `corrected_after_auto_close`,
`excluded_from_reports_duplicate_scan`, cộng 19 tag khác (overlap,
invalid_time, zero_qty_long, missing_station, exception ×3, offline ×2,
qc ×2, penalty, system_error_log, v.v.)

**Số liệu thật lấy từ `GET /api/reports/employee-productivity` trên
DEMO** (14 ngày, 16 nhân viên, 3 PO):

| Chỉ số | Giá trị |
|---|---|
| Năng suất trung bình (mean) | **85.44%** |
| Median | 86.75% |
| Min / Max | 64.63% / 95.91% (phân bố tự nhiên, không đồng đều) |
| Thời lượng session trung bình/nhân viên | 5.28h – 6.97h (mean 6.21h) — đúng khoảng 4-8h |
| Session hoàn thành | 158 (156 hợp lệ + 2 invalid) |
| Tổng sản lượng đạt / lỗi | 87,041 / 5,257 (~5.7% NG) |

Cùng dataset (164 session, 16 nhân viên, 3 PO, 20 Operation) đã seed
riêng biệt trên **cả DEMO lẫn PRODTEST** (2 database hoàn toàn tách
biệt — `mesflow_demo` và `mesflow_prodtest`).

## 5) Kiosk nhiều nhân viên + lỗi vận hành thật (chương video)

Đã có sẵn trong commit `1076803` (trước điện mất, chưa từng release):
- **`09_kiosk_operator` (7m36s, dài nhất bộ)**: quét A→start→finish,
  rồi **B quét vào ngay khi session của A còn mở, rồi C** — chứng minh
  1 kiosk vật lý phục vụ tuần tự nhiều công nhân, mỗi lượt quét chỉ
  resolve đúng session của chính người đó (đúng REQ-KIOSK-003).
- **`05_session`**: 2 kịch bản lỗi thật + xử lý trên UI, dùng API thật
  không giả lập: (1) "quên kết thúc ca → hệ thống tự đóng →
  `quantity_confirmed=false`" hiện trong drawer, sửa qua
  `POST /supervisor/sessions/<id>/adjust`, mở lại xem badge đã hết; (2)
  "quét trùng → loại khỏi báo cáo, không xóa dữ liệu"
  (`excluded_from_reports=true`, giữ nguyên lịch sử/audit).
- **`10_employee_productivity` (4m43s)**: KPI, bảng xếp hạng, drill-down
  từng session, filter, kiosk wallboard.

## 6) 15 video — danh sách chính xác (đã publish DEMO + PRODTEST)

| # | ID | Tiêu đề | Thời lượng | Kích thước |
|---|---|---|---|---|
| 00 | overview | Tổng quan MESFlow | 1m38s | 3.6M |
| 01 | dashboard | Tổng quan sản xuất theo ngày | 4m07s | 8.4M |
| 02 | production_order | Lệnh sản xuất | 2m20s | 6.2M |
| 03 | template | Mẫu quy trình | 2m00s | 4.7M |
| 04 | material_flow | Dòng vật tư | 0m34s | 1.4M |
| 05 | session | Phiên làm việc | 1m40s | 4.1M |
| 06 | session_exceptions | Phiên làm việc bất thường | 0m56s | 2.4M |
| 07 | employees_qr | Nhân viên & QR | 1m05s | 3.1M |
| 08 | kiosk_admin | Quản lý trạm thao tác | 2m10s | 7.6M |
| 09 | kiosk_operator | Trạm thao tác cho công nhân | **7m36s (dài nhất)** | 8.0M |
| 10 | employee_productivity | **Năng suất nhân viên** | 4m43s | 14M (nặng nhất) |
| 11 | working_calendar | Lịch làm việc | 1m03s | 1.5M |
| 12 | users_permissions | Người dùng & phân quyền | 1m31s | 3.7M |
| 13 | system_logs | Nhật ký hệ thống | 0m51s | 2.6M |
| 14 | common_cases | Tình huống & lưu ý | 1m55s | 5.8M |

**Tổng: 15/15, 34 phút 9 giây, 76MB.** Không trùng, không thiếu, có
chương "Năng suất nhân viên" riêng như yêu cầu.

## 7) QA gate (từ chính pipeline, không tự chấm)

```
feature_count=15 covered=15 missing=0
happy_path_percent=100  critical_exception_percent=100
functional_check_percent=100  ui_check_percent=100
exception_percent=93  recovery_percent=93  overall_percent=91
gate: happy_path=PASS critical_exceptions=PASS overall=PASS
      selectors=PASS functional=PASS
```
Vài cảnh báo non-fatal (`TARGET_NOT_VISIBLE`,
`TUTORIAL_OVERLAY_COVERS_TARGET`) trên 2 bước ở chương dashboard — cùng
loại hiện tượng đã ghi nhận lần trước với dataset lớn hơn (KPI card
định vị khác do dữ liệu phong phú hơn), không chặn quay, không phải
lỗi chức năng — để nguyên, không mở rộng phạm vi sửa UI.

## 8) Kết quả build/deploy

| | Trước | Sau |
|---|---|---|
| Image | `mesflow-app:71.0.0.221` | `mesflow-app:71.0.0.222` (commit `a06c3a3a03b1`) |
| Digest | — | `sha256:66104f9c3fb3ec0e99f2306261feaeed991d201fdf76fa537b6b2f081689405f` |
| Smoke test | — | PASS (`ok:true`, `migration_head` không đổi `0043_super_admin_role`) |
| DEMO | 0/15 video, image .221, không mount | **15/15 video, image .222, mount bền vững** |
| PRODTEST | 15/15 video (bộ cũ, trước multi-employee fix), image .221 | **15/15 video (bộ mới), image .222**, deploy qua `scripts/deploy.sh` (health PASS, digest khớp, cron reconcile/log-retention verified present) |
| DEV (`mesflow-app`/`mesflow.net` local) | 15/15, .219 | Không đụng — đã ổn định sẵn, không nằm trong phạm vi lỗi lần này |

## 9) Test results

- `test_tutorial_chapter_count_consistency.py`: 4/4 PASS
- `test_video_pipeline_output_cleanup.py` (mới): 1/1 PASS (đã verify fail trên bản trước fix)
- `test_v6584439_tutorial_dataset.py`: 8/9 PASS, 1 fail do môi trường chạy pytest cục bộ của tôi trỏ nhầm gói `mesflow` từ checkout khác trong `$PYTHONPATH` (không phải lỗi code — không tái hiện trong container)
- Release smoke test (`scripts/release-build.sh`): PASS

## 10) Commit hash (repo `mesflow/mesflow`, nhánh `main`)

```
1c7b84f fix(tutorial): clean $OUT before recording -- stale runs corrupted the 15-chapter manifest
943067d fix(tutorial): video pipeline login races autologin's auto-submit on targets with MESFLOW_TEST_AUTO_LOGIN=1
a06c3a3 chore: bump version to 71.0.0.222 for tutorial multi-employee/exclusion dataset + VI requirements
a01b891 merge: MESFLOW_MASTER_REQUIREMENTS_VI.md -- self-contained Vietnamese requirements doc
7d99520 docs: MESFLOW_MASTER_REQUIREMENTS_VI.md -- self-contained Vietnamese requirements for QA/QC agent
```
Mỗi commit qua worktree/branch riêng (`agent/claude/*`) theo đúng
`AGENTS.md`, merge fast-forward/`--no-ff` vào `main`, worktree đã dọn
sau khi merge.

## 11) Rủi ro / việc còn tồn đọng

1. **`mesflow.net` công khai thật chưa xác định được nguồn gốc** (mục
   3) — cần xác nhận bằng kênh khác (DNS/hạ tầng ngoài máy này), không
   tự suy đoán thêm.
2. **Route `/api` prefix thiếu trong tài liệu requirement** (mục 2) —
   để sửa trong task chuẩn hóa QC package kế tiếp (đã hàng đợi).
3. **Đăng nhập admin thật trên PRODTEST bằng `MESFLOW_ADMIN_PASSWORD`
   hiện tại thất bại** (`INVALID_CREDENTIALS`) — mật khẩu DB có thể đã
   bị đổi tay ở phiên trước, không khớp env var; chưa sửa (không tự ý
   reset mật khẩu môi trường dùng chung khi chưa chắc chắn) — đã verify
   15/15 video ở mức file+manifest+container thay vì qua API có login.
4. **DEV (`mesflow-app`) vẫn ở `.219`**, chưa lên `.222` — không có
   lỗi cần sửa ở đó nên không đụng, nhưng để lệch version giữa 3 môi
   trường; cân nhắc đồng bộ ở lượt sau nếu muốn 1 nguồn phiên bản duy nhất.
5. 2 cảnh báo non-fatal QA (mục 7) chưa sửa — không chặn, không ảnh
   hưởng nội dung video.
