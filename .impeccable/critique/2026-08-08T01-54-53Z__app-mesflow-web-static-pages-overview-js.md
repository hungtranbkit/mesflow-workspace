---
target: MESFlow Control Tower / Overview
total_score: 21
max_score: 40
na_heuristics: 
p0_count: 0
p1_count: 4
timestamp: 2026-08-08T01-54-53Z
slug: app-mesflow-web-static-pages-overview-js
---
# MESFlow Control Tower Critique

## Design Health Score

| # | Heuristic | Score | Key Issue |
|---|---|---:|---|
| 1 | Visibility of System Status | 2 | Có loading, empty/error và nhãn LIVE, nhưng thiếu thời điểm cập nhật, trạng thái đang refresh và cảnh báo dữ liệu cũ. |
| 2 | Match System / Real World | 3 | PO, Operation, WIP, session và sản lượng đúng ngôn ngữ xưởng; copy Anh–Việt còn trộn lẫn. |
| 3 | User Control and Freedom | 2 | Có filter và quay lại tất cả PO; thiếu reset thống nhất và pause auto-refresh. |
| 4 | Consistency and Standards | 3 | Panel, badge và progress nhất quán; hàng PO click được nhưng không có affordance chuẩn. |
| 5 | Error Prevention | 2 | Bề mặt chủ yếu read-only; refresh âm thầm và filter tức thời có thể thay đổi ngữ cảnh quyết định. |
| 6 | Recognition Rather Than Recall | 3 | Dữ kiện quyết định được đặt cùng hàng; trạng thái PO đang chọn chưa đủ nổi bật. |
| 7 | Flexibility and Efficiency | 2 | Có search/filter/sort và link trực tiếp; thiếu shortcut, saved view, density và thao tác hàng loạt. |
| 8 | Aesthetic and Minimalist Design | 2 | Có trật tự nhưng hero, 5 control, 5 KPI, bảng PO và ma trận Operation cạnh tranh trong viewport. |
| 9 | Error Recovery | 1 | Lỗi hiện rõ nhưng thiếu chẩn đoán, retry, trạng thái offline và hướng phục hồi. |
| 10 | Help and Documentation | 1 | Thiếu giải thích score ưu tiên, schedule gap, WIP source, rework pool và logic recommendation. |
| **Total** | | **21/40** | **Acceptable — cần cải thiện đáng kể** |

## Design Specificity Verdict

MESFlow có tính đặc thù sản phẩm rõ trong kiến trúc thông tin và chuỗi quyết định PO → Operation → WIP → session → hành động đề xuất. Tuy nhiên, ngôn ngữ thị giác vẫn chỉ được tác giả hóa ở mức vừa: panel trắng bo góc, KPI card, status pill, nút xanh và responsive grid có thể thuộc nhiều dashboard quản trị khác. Bản sắc đang nằm trong dữ liệu và copy nhiều hơn trong composition và interaction model.

Detector tĩnh chạy trên `app/mesflow/web/static/pages/overview.js`, exit code 0 và trả về 0 finding. Không có false positive. Điều này không phủ định các vấn đề UX: detector không đo được việc hàng đợi khẩn cấp nằm dưới fold, auto-refresh làm xáo trộn ngữ cảnh hoặc row click-only. Không có browser automation trong tool surface nên không có visual overlay đáng tin cậy.

## Overall Impression

Bề mặt có nền tảng vận hành đúng: nghiêm túc, giàu ngữ cảnh xưởng và có prioritization. Cơ hội lớn nhất là biến nó từ một dashboard tổng hợp thành một exception inbox có thể tin cậy và xử lý được: urgent queue lên trước, dữ liệu có freshness rõ, row cô đọng và có progressive disclosure.

## What's Working

- Tổ chức theo chuỗi quyết định của quản đốc thay vì chỉ phản chiếu entity database.
- Priority dùng thứ tự, chữ, badge, border và lý do; không phụ thuộc duy nhất vào màu.
- Search, PO filter, urgency filter và sort đều có ý nghĩa vận hành thực tế.

## Priority Issues

### P1 — Hàng đợi cần điều phối bị chôn dưới framing và summary

**Why it matters:** Ở 1366×768, hero, năm control, năm KPI và bảng PO có thể đẩy “Operation cần điều phối” xuống dưới fold.

**Fix:** Đưa critical/warning queue thành block nội dung đầu tiên; nén intro vào page header; chuyển portfolio PO sang cạnh hoặc phía dưới queue.

**Suggested command:** `$impeccable layout`

### P1 — Tương tác chọn PO không accessible

**Why it matters:** PO row là `div` có click handler, không có semantics bàn phím; search/select thiếu label liên kết; refresh không được công bố cho assistive tech.

**Fix:** Dùng button/link semantic hoặc row focusable có keyboard activation và focus-visible; thêm label; dùng `aria-live` cho freshness/loading và giữ focus qua rerender.

**Suggested command:** `$impeccable audit`

### P1 — Auto-refresh âm thầm làm giảm niềm tin quyết định

**Why it matters:** Mỗi 15 giây dữ liệu và thứ tự có thể đổi trong khi quản đốc đang đọc, nhưng không có timestamp, diff cue, pause hoặc stale warning.

**Fix:** Hiển thị “Cập nhật lúc…”, phân biệt updating/current/stale, giữ vị trí và focus, đánh dấu record đổi, cho phép pause khi điều tra.

**Suggested command:** `$impeccable harden`

### P1 — Operation row vượt giới hạn working memory

**Why it matters:** Năm cột chứa khoảng 12–16 fact, reason list biến thiên và hai action; breakpoint chỉ xếp dọc chứ không giảm tải.

**Fix:** Tạo triage row cô đọng gồm trạng thái, Operation, rủi ro hạn, progress/WIP exception và một hành động đề xuất; mở rộng để xem score factors, resource và material-flow evidence.

**Suggested command:** `$impeccable distill`

### P2 — Copy pha trộn và score thiếu khả năng giải thích

**Why it matters:** “PRODUCTION OVERVIEW”, “Deadline”, “Session”, “LIVE”, “Pool” và “điểm 87” không giải thích làm giảm độ tin cậy.

**Fix:** Chốt policy thuật ngữ Việt/Anh và giải thích score/freshness ngay trong ngữ cảnh.

**Suggested command:** `$impeccable clarify`

## Cognitive Load

Mức tải nhận thức cao: fail 5/8 tiêu chí — single focus, chunking, one thing at a time, minimal choices và progressive disclosure. Hero có 5 control đồng thời; nhóm KPI có 5 metric; mỗi Operation row có 5 cột và nhiều fact. Grouping, hierarchy cơ bản và co-location dữ kiện quyết định là các điểm đạt.

## Emotional Journey

Mở đầu tạo cảm giác có năng lực và đúng nghiệp vụ. Nhãn “LÀM NGAY / CẦN CHÚ Ý / ĐÚNG TIẾN ĐỘ” đem lại sự yên tâm ban đầu. Niềm tin giảm ở ma trận dày và thời điểm quyết định vì recommendation không có provenance/freshness rõ, còn LIVE hứa nhiều hơn giao diện chứng minh. Hành trình kết thúc bằng điều hướng “Mở PO”, chưa phải resolution: không có assign, acknowledge, snooze hoặc trạng thái đã xử lý.

## Persona Red Flags

- **Alex — power user:** Không có shortcut, saved view, density, bulk acknowledgment hoặc đường “critical only”; auto-refresh có thể reorder khi đang so sánh.
- **Sam — keyboard/screen-reader user:** PO selection click-only; control dựa vào placeholder; refresh/error không được announce; focus có nguy cơ mất sau rerender.
- **Chủ xưởng/giám đốc:** Năm con số cho pulse nhưng thiếu trend, target, shift context, aging và “điều gì vừa thay đổi”.
- **Quản đốc:** Queue phù hợp nhưng đến muộn và không hỗ trợ ownership/closure; “Mở PO” chỉ là navigation, không phải xử lý ngoại lệ.

## Minor Observations

- Search có scope không nhất quán giữa PO rows và Operation rows.
- “Hiện tất cả PO” vẫn xuất hiện khi chưa chọn PO.
- Loading thay toàn bộ nội dung thay vì giữ dữ liệu cũ trong lúc refresh.
- Empty state không nêu filter đang áp dụng hoặc cho reset một chạm.
- Trạng thái PostgreSQL chiếm trust space có giá trị hơn nếu dành cho freshness hoặc ca hiện tại.
- Priority reason list có thể không giới hạn, làm chiều cao row biến động mạnh.

## Questions to Consider

- Nếu quản đốc chỉ có 15 giây lúc giao ca, ba dữ kiện và một hành động nào phải luôn nằm trên fold?
- Đây là “overview” hay thực chất là exception inbox cần ownership và resolution?
- LIVE nghĩa là tự refresh, dữ liệu đủ mới để hành động hay đã xác minh với shop-floor event gần nhất?
- Vì sao quản đốc phải xem đủ năm dimension cho mọi Operation khỏe mạnh trước khi yêu cầu chi tiết?
- Chủ xưởng và quản đốc có nên có default view khác nhau không?
