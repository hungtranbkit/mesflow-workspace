# GitHub Open Issues Triage — hungtranbkit/mesflow — 2026-09-06

Xác nhận repo qua `git remote -v` + `gh repo view`: **`hungtranbkit/mesflow`**
(remote `origin`, không phải `mesflow-workspace`). `gh issue list --state
open` (và đối chiếu `gh api repos/.../issues --paginate`, loại PR):
**đúng 1 issue đang OPEN**, không có issue nào khác bị lọc mất bởi
label. 3 issue đã closed trong repo (không nằm trong phạm vi audit này
— chỉ audit OPEN theo đúng yêu cầu).

## Bảng triage

| # | Title | Severity | Reported-by/source | Repro | Expected | Actual | Requirement ID | Module/file nghi ngờ | Classification | Evidence | Owner đề xuất | Fix approach | Risk | Test cần chạy |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **#9** | [QC][HIGH][DEV] Edited value on /app persists after reload | high (label) | AI QC Agent (autonomous, container `ai-qc-agent-*`), tạo lại từ `mesflow-workspace#2` | Điền `#ovSearch`, chọn 4 combobox lọc (`#ovPoFilter/#ovRepair/#ovPriority/#ovSort`) trên `/app` (Overview), reload trang | `value_persisted` — giá trị vẫn còn sau reload | Giá trị mất sau reload | Không có REQ nào trong `MESFLOW_MASTER_REQUIREMENTS(_VI).md` yêu cầu filter Overview phải persist qua reload; Overview thậm chí chưa có REQ-OVERVIEW-* block riêng (gap tài liệu nhỏ, không phải nguyên nhân bug) | `app/mesflow/web/static/pages/overview.js` (`renderOverview`, filter bar `#ovSearch/#ovPoFilter/#ovRepair/#ovPriority/#ovSort`) | **QC_TEST_BUG** | Xem §1 bên dưới — đọc trực tiếp `bug.json` gốc của AI QC Agent (docker volume `ai-qc-agent_qc_artifacts`): `"reproducibility":{"attempts":3,"failures":0,"status":"CANNOT_REPRODUCE","label":"0/3"}` — **chính QC Agent, ở lần phát hiện gốc, đã không tái hiện được 0/3 lần**; đọc source `overview.js` xác nhận KHÔNG có bất kỳ cơ chế `localStorage`/`sessionStorage`/URL-param nào lưu filter — mọi filter chỉ tồn tại trong bộ nhớ DOM, reset về mặc định mỗi lần `content.innerHTML=` render lại (đúng như MỌI trang khác trong MESFlow: dashboard reset về "hôm nay", employee-productivity reset về "đầu tháng→hôm nay", production-schedule không giữ PO filter — đây là pattern nhất quán toàn app, không phải hành vi cục bộ của riêng Overview); tự tái hiện sống trên DEV (`127.0.0.1:8080`) xác nhận: filter reset về rỗng sau reload — **đúng như code, đúng như mọi trang khác, không phải bug** | `qa-` (chủ sở hữu duy nhất được đóng issue theo đúng quy ước ghi trong chính issue) | Không sửa app. Đề xuất: (a) sửa lại `expected_checks` trong test case `e1dbc0c36e79` — bỏ giả định "form edit phải persist" cho các trang filter/report thuần đọc; (b) nếu QC Agent dùng chung 1 template "fill→reload→expect persisted" cho MỌI trang có `<select>`/`<input>`, cần loại trừ các trang không có nút "Lưu"/"Submit" tường minh (chỉ có "Làm mới" = reload data, không phải save) | Thấp (không đổi app) | Test hiện có xác nhận qua ad-hoc Playwright script (xem §2) + đọc `bug.json`; không cần thêm test mới vì hành vi đúng theo thiết kế |

**Không có issue P0.** #9 là issue duy nhất, severity ghi "high" nhưng
sau audit là **false-positive từ chính test case**, không phải bug
nghiêm trọng thật.

## 1) Bằng chứng: đọc trực tiếp artifact gốc của AI QC Agent

`docker inspect ai-qc-agent-backend` → volume `ai-qc-agent_qc_artifacts`
mount tại `/artifacts`. Đọc qua `docker exec ai-qc-agent-backend cat
/artifacts/a92cc274c41246a983c90022b287c12a/bugs/BUG-837020efe25c1b41/bug.json`:

```json
"reproducibility": {
  "attempts": 3,
  "failures": 0,
  "status": "CANNOT_REPRODUCE",
  "label": "0/3"
}
```

Đây là dữ liệu do chính AI QC Agent ghi lại ở **lần phát hiện gốc**
(trước khi filed issue) — 3 lần thử tái hiện lại chính kịch bản, **0
lần** tái hiện được lỗi ban đầu ghi nhận. Bug vẫn được file (có thể do
policy "file cả bug flaky" của QC Agent), nhưng bản thân bằng chứng nội
bộ đã cho thấy đây không phải lỗi tái lập ổn định.

2 lần "QC RETEST FAILED" sau đó trong comment GitHub cũng không nhất
quán với nhau:
- Lần 1: `BLOCKED` — không định vị được combobox (`role+name didn't
  match exactly one element`) — đây là **lỗi hạ tầng test/selector**,
  không phải hành vi app.
- Lần 2: `FAIL` — đúng triệu chứng gốc (giá trị mất sau reload).

## 2) Tự tái hiện sống trên DEV (`127.0.0.1:8080`, an toàn — chỉ đọc,
không phá hoại)

Script Playwright ad-hoc, đúng y hệt các bước trong `steps.json` gốc:

```
login (admin) -> /app -> openPage('overview') -> chờ load() xong
fill #ovSearch = 'QC_TEST_REPRO_CHECK'
select #ovPoFilter = giá trị non-empty đầu tiên (nếu có)
select #ovRepair = 'defect', #ovPriority = 'CRITICAL', #ovSort = 'repair_qty'
reload()
đọc lại giá trị 5 field trên
```

Kết quả thật:
```
PO options available: [ 'Tất cả PO' ]        <- DEV hiện KHÔNG có PO nào (dataset rỗng)
Before reload: ovSearch= QC_TEST_REPRO_CHECK
After reload: ovSearch=
After reload: ovPoFilter=
After reload: ovRepair=
```

Xác nhận: filter reset về rỗng sau reload — **đúng như quan sát gốc của
QC Agent**, nhưng đây **là hành vi đúng theo thiết kế** (không có code
nào từng lưu các giá trị này, ở bất kỳ trang nào trong toàn bộ MESFlow
đã đọc qua nhiều audit trong dự án này). Phát hiện phụ: DEV hiện có
**0 Production Order** — đây là dữ liệu môi trường (DATA_ISSUE nhẹ,
không phải bug code), giải thích một phần vì sao chiến lược chọn
`__first_non_empty__` của QC Agent không ổn định giữa các lần chạy
(không có option non-empty nào để chọn khi DEV rỗng dữ liệu).

## 3) Hành động đã thực hiện

- **Không sửa app** (đúng theo phân loại QC_TEST_BUG — không có lỗi
  code cần sửa).
- Đã **comment trên issue #9** (không tự đóng — issue tự ghi rõ "QC là
  bên duy nhất được đóng issue này (sau khi retest PASS)") với đầy đủ
  bằng chứng: trích `bug.json` gốc (`CANNOT_REPRODUCE 0/3`), kết quả
  tái hiện sống trên DEV, và đề xuất sửa lại test case thay vì tiếp tục
  retest app.
- Không có commit code nào trong task này (0 app fix cần thiết).

## 4) SPEC-GAP phụ phát hiện (không thuộc issue #9, ghi lại để không
quên)

- **SPEC-GAP-003**: trang "Tổng quan sản xuất" (Overview,
  `overview.view`, trang đích sau đăng nhập) chưa có REQ-OVERVIEW-*
  block riêng trong `MESFLOW_MASTER_REQUIREMENTS(_VI).md` — chỉ được
  nhắc tên trong bảng RBAC §3. Không phải nguyên nhân của issue #9,
  nhưng là gap tài liệu độc lập nên ghi lại. **Không tự thêm REQ mới
  trong task này** để tránh lấn phạm vi "audit GitHub issues" — chờ xác
  nhận có cần làm riêng không.
- Dữ liệu DEV hiện có 0 Production Order — nên xác nhận đây có phải
  trạng thái mong muốn của môi trường DEV hay cần seed lại dữ liệu mẫu;
  không tự seed trong task này (ngoài phạm vi, và DEV có thể đang được
  dùng cho mục đích khác).

## 5) Output tổng kết (theo đúng format yêu cầu)

- **Tổng số open issues**: 1 (issue #9).
- **Phân loại**: REAL_APP_BUG: 0 · QC_TEST_BUG: 1 (#9) · SPEC_GAP: 0
  (issue-level; có 1 SPEC-GAP phụ §4 không gắn với issue nào) ·
  DATA_ISSUE: 0 (issue-level; 1 quan sát phụ về DEV rỗng PO, không
  phải issue riêng) · ENV_INFRA_ISSUE: 0 · ALREADY_FIXED: 0 ·
  DUPLICATE: 0.
- **P0/P1 list**: không có P0. #9 gắn nhãn `severity-high` nhưng sau
  audit xác định là false-positive từ test case, không phải bug ứng
  dụng nghiêm trọng thật.
- **Issue đã fix trong task này**: không có (0 app code fix — đúng
  theo phân loại QC_TEST_BUG, không sửa app).
- **Commit hashes**: không có commit code nào cho task này (chỉ có
  report này).
- **Test evidence**: bug.json gốc của AI QC Agent (`CANNOT_REPRODUCE
  0/3`), script Playwright tái hiện sống trên DEV (kết quả ở §2).
- **Issue còn blocked / cần gì để unblock**: #9 vẫn OPEN chờ `qa-`
  (chủ QC Agent) xác nhận và tự đóng theo đúng quy ước ghi trong chính
  issue — cần: (a) qa- xác nhận lại đây là false-positive dựa trên
  bằng chứng đã comment, (b) sửa test case `e1dbc0c36e79` để không còn
  giả định filter/report phải persist qua reload, sau đó tự đóng issue
  sau khi retest bằng test case đã sửa cho kết quả PASS/N-A phù hợp.
