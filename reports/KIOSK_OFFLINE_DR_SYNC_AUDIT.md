# ESP Kiosk Offline Sync — Server Failover / DR Audit & Hardening

Audited `esp-kiosk/esp/mesflow_app.cpp` (the current, single-source-of-truth
firmware — not the old v2.7/v2.8 docs) and `mesflow/app/mesflow/db/repositories/
offline_sync.py` + `web/execution.py` (the current backend) directly, line by
line, before writing anything below. Where a claim needed live confirmation
it was checked against real, running code (not assumed) — noted inline.

**Scope discipline:** no Production or Production Test server was touched.
All backend testing used mocked repositories or pure-function unit tests;
one attempt to test against real local DEV data was deliberately avoided
(see TESTS below) because it would have required mutating schema on the
shared local DEV Postgres.

---

## 1. Firmware audit — exact current mechanism map

Read directly from `esp-kiosk/esp/mesflow_app.cpp` (pre-change state,
firmware `5.5.7`).

| Piece | Storage | Persistent across reboot | Created | Deleted | Max records | Retention (before this task) | Checksum | Idempotency key |
|---|---|---|---|---|---|---|---|---|
| **START online** | none (HTTP round trip) | n/a | `startSession()`-style handler on scan | on response | n/a | n/a | n/a | `request_id` = server-generated token |
| **FINISH online** | none | n/a | on scan/confirm | on response | n/a | n/a | n/a | `request_id` |
| **START offline / FINISH offline** | RAM (`rt`) → NVS `pendingTx` (2-phase) → LittleFS `EVENT_LOG_FILE` | Pending transaction: YES (NVS `mesflow`/`pending_tx`, `PendingTransaction` struct, own checksum). Queued event: YES (LittleFS) | `enqueueOfflineEvent()` / `offlineLookupOperationAndStart()` / `offlineFinishSession()` | Never explicitly — only superseded by the ACK marker append (see below) | Bounded by `MAX_OFFLINE_EVENTS`=500 (PSRAM) / 64 (no PSRAM) via `countPendingOfflineEvents()`'s guard in `appendOfflineEventWithIdentity()` | **Unbounded before this task** — file only ever grew; sole cleanup was the fully destructive `clear-offline CONFIRM` console command | FNV1a32 (`objectChecksum`/`sealObject`/`validObject`), magic `0x4D464F46` | `eventId` = `"<DEVICE_ID>-<10-digit zero-padded device sequence>"`, sequence from NVS `mesflow`/`event_seq` (monotonic, `nextDeviceSequence()`) |
| **Pending transaction (single, in-flight)** | NVS `mesflow`/`pending_tx` | YES | `savePendingTransaction()` before any online START/FINISH POST | `clearPendingTransaction()` after a confirmed server response (or handed off to the offline queue, see below) | 1 (single struct) | Until resolved | Own checksum field (`pendingChecksum`) | `token` field (used as `request_id`) |
| **Offline event queue** | LittleFS `/offline_events.log`, append-only, one `OfflineLogRecord` per `EVENT`/`ACK`/`REJECT` | YES | `appendOfflineEventWithIdentity()` | Never (before this task) | 500/64 (see above) | **Unbounded** (before this task) | Per-record FNV1a32 | `eventId` (see above) |
| **Offline session storage** | LittleFS `/offline_sessions.bin` (fixed-size array, atomic rewrite) | YES | `offlineLookupOperationAndStart()` (2-phase: session record first, then EVENT record — `recoverOfflineSessionIntents()` repairs a mismatch on reboot) | `offlineFinishSession()` removes the row after the FINISH event is durably appended | `MAX_OFFLINE_SESSIONS`=80 (PSRAM) / 16 (no PSRAM) | Until FINISH | Per-record FNV1a32 | `localSessionId` |
| **ACK storage** | Same LittleFS `/offline_events.log`, `recordType=ACK`/`REJECT`, `eventId` only (payload fields zeroed) | YES | `appendAck()`/`appendReject()`, called only after a server response of `accepted`/`duplicate`/`rejected` | Never (before this task) | n/a (piggybacks on event log's 500/64) | **Unbounded** (before this task) | FNV1a32 | matches the `eventId` it acknowledges |
| **Worker cache** | LittleFS `/workers.bin`, PSRAM/heap array | YES | `cacheWorkerNow()` (from catalog snapshot) | `clear-cache CONFIRM` console command, or LRU-style overwrite at capacity (`idx=0` fallback) | `MAX_CACHED_WORKERS`=160 (PSRAM) / 80 (no PSRAM) | Until next catalog refresh (≥6h, or forced) | FNV1a32 | `qr` (unique key) |
| **Operation cache** | LittleFS `/operations.bin` | YES | `cacheOperationNow()` | same as worker cache | `MAX_CACHED_OPERATIONS`=320 (PSRAM) / 120 (no PSRAM) | same | FNV1a32 | `qr` + `station` |
| **Reboot recovery** | `recoverOfflineSessionIntents()` at boot, right after `loadOfflineStorage()` | — | boot | — | — | — | — | replays any session whose START/FINISH intent didn't make it into the event log yet, using the SAME `eventId` already recorded in the session struct — never mints a new one |

## 2. Backend audit — current sync endpoint

`POST /api/station/events/sync` (alias `POST /api/kiosk/offline-sync`,
`mesflow/app/mesflow/web/execution.py:legacy_station_events_sync`) →
`OfflineSyncRepository.process_event()`
(`mesflow/app/mesflow/db/repositories/offline_sync.py`).

- **Idempotency**: `client_event_id` (the ESP's `eventId`) is the primary
  key check — `SELECT * FROM kiosk_client_events WHERE client_event_id=%s`,
  then `INSERT ... ON CONFLICT(client_event_id) DO NOTHING`. Confirmed real
  DB constraint: migration `0023_kiosk_offline_sync.py`,
  `sa.Column('client_event_id', sa.Text(), nullable=False, unique=True)`.
  A second, independent constraint —
  `UniqueConstraint('kiosk_id','local_sequence', name='uq_kiosk_client_event_sequence')`
  — protects the (device_id, sequence) pair too, so **the DB layer, not
  just app logic, enforces device_id+event_id idempotency**.
- **accepted** / **duplicate** / **conflict** / **rejected**: all four real,
  confirmed in `process_event()`:
  - `accepted` — new event, business logic succeeded (`WorkSessionRepository.start/finish`, itself idempotent again via `request_id`=`event_id`, i.e. a *third*, session-level idempotency layer).
  - `duplicate` — `client_event_id` already recorded with an **identical** payload hash — returns the original `server_session_id`, no re-processing.
  - `IDEMPOTENCY_PAYLOAD_CONFLICT` (a `rejected` reason_code) — same `client_event_id`, **different** payload hash. This is the real "conflict" case.
  - `LOCAL_SEQUENCE_CONFLICT` — same `(kiosk_id, local_sequence)`, different `client_event_id`.
  - `BUSINESS_REJECT` — legitimate domain error (missing employee/operation, session already closed, etc.).
  - `transient`/`TEMPORARY_FAILURE` — DB/unknown error; **deliberately does not write a terminal ledger row**, so the ESP retries with the exact same event later.
- **Offline events survive an application restart**: YES — `kiosk_client_events` is a real PostgreSQL table written inside `transaction()` (a committed DB transaction, not an in-memory structure). Restarting `mesflow-app` (or even redeploying it) does not touch this data; only a schema migration or explicit DELETE would.

## 3. Failure matrix

| Case | Data lost? | Duplicate? | Recoverable? | Why |
|---|---|---|---|---|
| **A.** ESP creates event → WiFi dies before send | No | No | Yes | Event is durably appended to `EVENT_LOG_FILE` (LittleFS) *before* any network attempt (`enqueueOfflineEvent()` → `appendOfflineEventWithIdentity()` runs first; the sync loop only reads already-durable records). Retried by `syncOneOfflineEvent()` on the next connectivity window. |
| **B.** ESP sends event → server receives → response lost | No | No (protected) | Yes | Server already committed the `kiosk_client_events` row + business effect. ESP, seeing no response, retries the identical event; server's `client_event_id` uniqueness returns `duplicate` with the original `server_session_id` — no double session, no data loss. |
| **C.** ESP sends event → ACK received → ESP reboots | No | No | Yes | `appendAck()` is the LAST step of `syncOneOfflineEvent()`, called only after a definitive `accepted`/`duplicate`/`rejected` response. If reboot happens *before* the ACK write completes, the event is still `pending` on reboot (event with no matching ACK marker) and gets resent — server dedupes it as `duplicate`. If reboot happens *after*, `countPendingOfflineEvents()` correctly excludes it. Either way: safe. |
| **D.** Server dies while ESP has a pending queue | No | No | Yes | ESP just keeps retrying with backoff (`retryDelays`) once the server (or its failover) comes back. Nothing on the ESP side assumes the server is always reachable. |
| **E.** Server ACKs event → considered synced on ESP → Server A dies → Server B restored from a DB state from BEFORE that event | **No longer (fixed by this task)** — previously: **functionally yes** | No (backend idempotency still holds even under replay) | **Fixed: Yes**, via the new generation/reconciliation mechanism (sections 5-8). **Before this task: NO** — this was the real gap; see section 4. | |
| **F.** Server A DB replicated to B with the event already present | No | No | Yes | Ordinary case — B's `kiosk_client_events` already has the row; if the ESP ever resent it for any reason, `duplicate` handles it. Generation would typically not even change in a clean replica promotion (see section 6 note on when to bump). |
| **G.** Kiosk reboots while server is offline | No | No | Yes | `loadOfflineStorage()` + `recoverOfflineSessionIntents()` run at boot before anything else; the durable LittleFS state is authoritative, RAM (`rt`) is reconstructed from it, not the other way around. |

## 4. The ACK data-loss window — found, and it is real (with a precise mechanism)

**Confirmed: YES, there was a DR gap** — but not the naive "ACK erases the
bytes" version. Read precisely:

- `appendAck(eventId)` writes a **separate**, small `OfflineLogRecord`
  (`recordType=ACK`, only `eventId` populated, everything else
  `memset`-zeroed) — it does **not** touch or delete the original `EVENT`
  record already sitting earlier in the same append-only file.
- So the full payload was **not physically erased** on ACK.
- But **no function existed that could find it again**:
  `readOldestPendingEvent()` and `countPendingOfflineEvents()` both
  actively **skip** any `EVENT` record with a matching `ACK`/`REJECT` —
  correct for their purpose (don't resend already-synced events), but that
  left **zero code path** capable of looking up an already-ACKed event's
  full record for replay.
- Combined with **no compaction at all** (the log only ever grew, with the
  sole cleanup being the fully destructive `clear-offline CONFIRM` console
  command, which *also* destroys genuinely-still-pending events) — the
  net effect for a real Server-A-dies/Server-B-restored-behind scenario:
  **the data an operator would need to replay onto Server B was
  unreachable through any existing mechanism**, even though the raw bytes
  hadn't technically been deleted yet (and would eventually be overwritten
  or manually wiped anyway, since nothing bounded the file).

**This is the DR gap** (task section 4). Per the task's explicit
instruction, this was **not** fixed by "expanding retry timers" — retry
timers only help while the *original* server is still the one being
retried against. The fix is structural: give the device a way to (a) know
it's now talking to a different server generation, and (b) look up and
replay specifically the events that generation is missing, using their
original identity.

## 5. Recent ACK replay window — implemented

`esp-kiosk/esp/mesflow_app.cpp`:

- **`findLoggedEvent(eventId, out)`** — the missing lookup: scans the log
  for the `EVENT` record matching `eventId` regardless of ACK/REJECT
  status.
- **`compactOfflineEventLog()`** — replaces "never compact" with a real,
  bounded, wear-conscious policy:
  - Every still-**pending** (unACKed) `EVENT` record is **never** dropped.
  - An ACKed/REJECTed record is dropped only when it is **both** older
    than **72 hours** (from the ACK/REJECT's own timestamp, not the
    original event time — `appendAck`/`appendReject` now stamp
    `eventEpoch=currentEpoch()`) **and** beyond the newest **200** ACKed
    events (`ACK_RETENTION_MIN_EVENTS`) — i.e. the count floor is an
    always-on hard ceiling; within it, a record with an unsynced clock
    (`epoch==0`) falls back to the count floor alone instead of becoming
    permanently undroppable (a real bug caught by
    `esp-kiosk/tools/test_offline_queue.py`'s
    `test_unsynced_clock_never_drops_purely_by_time_only_by_count_floor`
    during self-review — see TESTS).
  - Rewrite is atomic: temp file + `LittleFS.rename()`, the same pattern
    `atomicWrite()` already uses elsewhere — a power loss mid-compaction
    can only abandon the `.compact` temp file, never corrupt the live log.
  - Runs automatically ~every 6h when idle (same gate as catalog refresh)
    even on a device that never experiences a failover, and again right
    after a successful reconciliation.
- Every retained record preserves, unmodified: `eventId`, `localSessionId`,
  `workerQr`, `operationQr`, `goodQty`/`defectQty`, `sequence`
  (`device_sequence`), `bootId`, `eventEpoch` — exactly the task's required
  field list. **No new `event_id` is ever generated during replay** — the
  replay path (`runGenerationReconciliation()`) reads the field straight
  out of the located `OfflineLogRecord` and sends it unchanged.

## 6. Server generation / recovery id — implemented

Confirmed **no such concept existed anywhere** (grepped both `esp-kiosk`
and `mesflow` for `generation`/`cluster_id` before writing any code — zero
hits).

Added:
- **`server_generation`** table (migration
  `0038_v73_kiosk_dr_reconciliation.py`) — a deliberately single-row table
  (`CHECK (id=1)`): `cluster_id` (default `MESFLOW-PROD`, matching the
  task's example exactly), `generation_id` (random token, minted fresh —
  **never derived from a server IP/hostname**, per the task's explicit
  "do not use physical server IP as identity"), `bumped_at`, `bumped_by`,
  `reason`.
- **`ServerGenerationRepository.bump(reason, actor)`** — the *only* way
  `generation_id` ever changes. Exposed as
  `POST /api/kiosk-management/generation/bump`, `roles_required('admin')`
  (tighter than the other kiosk-management routes' admin+manager — this is
  a cluster-wide DR signal), requires a non-empty `reason`, and is
  `AuditRepository`-logged (`SERVER_GENERATION_BUMP`). **Never inferred
  automatically** from DB state — no heuristic guessing ("DB looks emptier
  than usual") is implemented anywhere; an operator must explicitly call
  this exactly once per real failover/restore event.
- Exposed via the **existing** bind (`POST /api/kiosk/connect` /
  `/kiosk/bind`) and heartbeat (`POST /station/heartbeat`) responses —
  "lightweight kiosk bind/heartbeat/recovery API" per the task, reusing
  what's already there instead of adding a third endpoint.
- ESP: `clusterId`/`lastGenerationId` persisted in NVS (`mesflow`
  namespace), compared on every bind/heartbeat response
  (`observeServerGeneration()`). A mismatch (and only a mismatch — first-
  ever sight of a generation id is adopted silently, not treated as DR)
  sets `pendingReconciliation=true` and the device enters `RECONCILING`.

## 7. Reconciliation protocol — implemented

`POST /api/kiosk/reconcile` (`OfflineSyncRepository.reconcile()`,
`mesflow/app/mesflow/services/kiosk_reconciliation.py` for the pure
gap-computation algorithm):

- **ESP sends**: `device_id`, `sequence_min`/`sequence_max` (its retained
  window's low/high device sequence), `recent_event_ids` (every event_id
  still physically in its log, pending or retained-ACKed — bounded to
  `offlineAckCapacity`, the same buffer the normal ACK-skip scan uses, no
  extra RAM budget).
- **Server returns**: `missing_sequences`, `missing_ranges` (contiguous
  runs collapsed — `ranges()` — so 500 consecutive missing events come
  back as one `[start,end]` pair, not 500 numbers; "do not resend hundreds
  of full payloads if manifest comparison can avoid it" is satisfied by
  never even *asking about* what's already known, and by this compact
  range encoding), `missing_event_ids`.
- **ESP replays ONLY the missing ones**, via the **existing**
  `/api/station/events/sync` — no new business-mutation endpoint was
  added. Each replayed event carries `sync_source: "reconcile_replay"`
  (new, purely informational field — see section 11) but is otherwise
  byte-identical to a normal sync.
- **Backend idempotency remains the final protection**, unchanged: even if
  the reconciliation gap-computation were somehow wrong, the *same*
  `client_event_id`/`(kiosk_id,local_sequence)` UNIQUE constraints that
  protect normal sync protect a replay too. Proven directly (not just
  argued) by the flagship test — see TESTS.

## 8. Sync order after failover

Read `mesflow_app.cpp`'s `loop()` **before** changing it: the existing
order already matched most of the required sequence —
`hasPendingTransaction()` and `countPendingOfflineEvents()>0` both already
`return` early, ahead of catalog refresh. The only genuinely missing step
was reconciliation itself. Final order, as implemented:

1. WiFi connectivity (pre-existing gate).
2. Bind/authenticate (pre-existing, `AUTO_BIND`).
3. Send unresolved pending transaction (pre-existing, unchanged).
4. Sync pending offline queue (pre-existing, unchanged).
5. **Reconcile recent-ACK window if generation changed** (new — inserted
   exactly here, gated on both prior queues being fully drained).
6. Resolve conflicts (new — `SYNC_CONFLICT` UI state, human-required, never
   auto-resolved into a false success).
7. Refresh worker/operation caches (pre-existing; now also implicitly
   gated behind reconciliation completing, since step 5 `return`s while
   `pendingReconciliation` is true).
8. Heartbeat (pre-existing, unchanged position).
9. ONLINE (pre-existing `offlineMode=false`/`READY` state).

## 9. Stable server endpoint

Audited `SERVER_BASE` (`char SERVER_BASE[192]`): **already compliant**,
no code change needed. Comment in source confirms the intent directly:
*"Bat buoc cau hinh qua Setup Portal/NVS; khong co fallback hardcode"*
(must be configured via Setup Portal/NVS; no hardcoded fallback) — grepped
the whole file for any hardcoded `http://`/IP-literal default and found
none. `validServerBase()` only checks for an `http(s)://` prefix and
length, so a stable DNS/service URL (e.g.
`https://mesflow.internal.example.com`) works exactly as well as an IP —
**the recommendation is operational** (provision kiosks with a DNS name,
not a Production server's literal IP), not a firmware defect. Failover
should change DNS/routing, never firmware config — already true today.

## 10. UI states — implemented

Two new `UiState` values: `RECONCILING`, `SYNC_CONFLICT` (never silently
skipped or merged into an existing state). Screens:
- **OFFLINE** → now shows the live pending count ("`N giao dịch chờ`"),
  read from the exact same `countPendingOfflineEvents()` the sync loop
  itself uses (never a separately-tracked, driftable counter).
- **SYNC** (actively draining the backlog while online) → `drawReady()`
  now shows "`ĐANG ĐỒNG BỘ - N còn lại`" instead of a bare online screen.
- **RECONCILING** → "`Đang kiểm tra dữ liệu sau khi chuyển server`" +
  live missing-event count.
- **SYNC CONFLICT** → "`Cần quản lý kiểm tra`" — bounded watchdog timeout
  deliberately **not** set for this state (see `maxStateDurationMs()`
  comment), matching "never silently convert conflict into success"; only
  clears via the new `reconcile` console command or a fresh generation
  change.
- **ONLINE** → pre-existing `READY` state, unchanged.

No event is ever silently dropped: a reconciliation replay that comes back
`rejected` is recorded via `appendReject()` (visible, on-device) and
surfaces `SYNC_CONFLICT`, never treated as done.

## 11. Backend operations UI

`GET /api/kiosk-management/overview` (`KioskRepository.management_overview()`)
extended (pre-existing endpoint, already had device/last-seen/queue/
offline_synced/offline_conflict/last-sync — confirmed by reading it before
changing anything) with the fields the task asked for that were missing:
`generation` (cluster_id/generation_id/bumped_at/reason), per-device
`last_sequence_received`, `duplicate_replay_count` (previously silently
discarded — a real counter now, see `process_event()`'s duplicate path),
`reconcile_replay_count`, `generation_stale` (a device whose
`last_generation_id` doesn't match the current one — i.e. still owes a
reconciliation), and a cluster-wide `reconciling_count` summary tile.
`mesflow/app/mesflow/web/static/app.js`'s existing Kiosk Management page
renders all of it (a real, already-wired frontend — confirmed before
adding to it, not assumed).

**Conflicts enter the existing Exception workflow**: a new
`kiosk_reconcile_flags` CTE branch was added to
`AuditRepository.session_exceptions()` (`exception_code=
'KIOSK_SYNC_CONFLICT'`), sourced from `kiosk_client_events` rows with
`source='RECONCILE_REPLAY'` (set only by the reconciliation replay path,
never ordinary sync — see section 5/7) and `status='rejected'`. Resolved
to a real session via the matching accepted START event or a
`SERVER:<id>`-form `local_session_id`; an unresolvable one (no session to
attach to) still shows in Kiosk Management's per-device event list, just
not duplicated into the session-scoped Exceptions inbox. Reuses the
existing fingerprint/review/workflow-status machinery in
`session_exceptions()` for free — no new review UI needed.

## 12. Tests

### Backend (`mesflow/`) — pure-function + mocked, no live DB

- `mesflow/tests/test_kiosk_reconciliation.py` — **11 tests**: the exact
  gap-computation algorithm (`compute_missing`/`ranges`) production calls,
  plus the **flagship DR scenario end-to-end**
  (`TestFlagshipDisasterRecoveryScenario`): Server A accepts E100-E110,
  Server B restored with only E100-E105, ESP's retained window believes
  E100-E110 ACKed, reconciliation computes the exact `[106,110]` gap,
  replay (via a `FakeEventLedger` enforcing the SAME two real UNIQUE
  constraints as `kiosk_client_events`) lands E100-E110 **exactly once**
  (11 events, 6 sessions, no duplicates), and a **second** reconciliation
  pass + replay attempt is proven idempotent (no new sessions, still 11
  events).
- `mesflow/tests/test_offline_sync_repository_wiring.py` — **5 tests**:
  `reconcile()`'s DB-facing wiring (query shape, range bounding, generation
  bookkeeping UPDATE), duplicate-replay counting, payload-conflict-vs-
  duplicate distinction.
- All **16/16 pass**, run in a disposable venv (`psycopg[binary]`, `flask`,
  `werkzeug`, `pytest`) against dummy `DATABASE_URL`/`MESFLOW_SECRET_KEY`
  so `mesflow.*` imports cleanly with no live Postgres involved.

### Firmware-adjacent (`esp-kiosk/`) — host-side simulation

- `esp-kiosk/tools/test_offline_queue.py` extended (existing "host-side
  fault simulation" pattern, not a new framework) with
  `RecentAckReplayWindowSimulation` — **5 new tests** mirroring
  `compactOfflineEventLog()`/`findLoggedEvent()` byte-for-byte: an ACKed
  event stays findable within 72h; gets dropped only once *both*
  time-stale *and* beyond the 200-event floor; **an unsynced clock
  (epoch==0) is never permanently undroppable** — this test caught a real
  bug in my first draft of the actual C++ (`shouldDrop` originally
  required `staleByTime && staleByCount`, which made `epoch==0` records
  undroppable forever, silently defeating the count-floor fallback the
  code comment claimed existed); a still-pending (never-ACKed) event is
  never dropped by compaction, no matter how old; a reconciliation replay
  always sends the event's original id, never a fresh one.
- Original file's **10/10 pre-existing tests still pass unmodified**
  (`OfflineQueueSimulation`) — confirms nothing here regressed the
  existing reboot/duplicate/torn-write/flapping-connectivity coverage.
- **10/10 total, `esp-kiosk/tools/test_offline_queue.py`** (5 pre-existing + 5 new).

### What was NOT tested, and why

No ESP32 hardware/toolchain compile was run — this task never has ESP-IDF/
PlatformIO available, and no physical kiosk to flash. The actual C++ was
written to match the file's existing conventions exactly (same struct
layout patterns, same atomic-write idiom, same PSRAM/heap capacity-sizing
pattern already used by `allocateOfflineBuffers()`) and reviewed
line-by-line; brace/paren balance was verified against the pre-change
baseline via `git stash` diff (the edit added exactly as many `{` as `}`
relative to the original file). The *algorithm* every new C++ function
implements is what's actually tested above, in the Python host-side
simulation — that is how the pre-existing `test_offline_queue.py` file
already validates firmware-side logic in this project, and it is how the
one real bug in this task's own new code was actually caught.

## 13. "Do not" checklist — self-audit

- Erase existing kiosk queues — not done; `compactOfflineEventLog()` never
  touches a still-pending record, and the pre-existing destructive
  `clear-offline CONFIRM` console command is untouched (still exists,
  still requires explicit confirmation, still logs a warning) — not
  removed, not made easier to trigger accidentally.
- Change IDs during replay — not done; `findLoggedEvent()` returns the
  original record, `runGenerationReconciliation()` sends
  `x["client_event_id"]=e.eventId` straight from it, and this is exactly
  what the flagship test asserts (`replayed == missing_ids`).
- Silently convert conflict into success — not done; a `rejected` replay
  response is recorded via `appendReject()` and surfaces `SYNC_CONFLICT`,
  never auto-ACKed.
- Require manual re-entry of production quantities — not done; the entire
  mechanism exists specifically so quantities already captured offline
  never need re-typing.
- Depend solely on RAM — not done; every new piece of state
  (`clusterId`/`lastGenerationId` via NVS, the event log itself) is
  LittleFS/NVS-backed, matching every other durable structure in this
  file.
- Hard-code Production server IP — not done; no new code introduces a
  server address anywhere, and the existing `SERVER_BASE` mechanism
  (section 9) was confirmed, not changed.
- Touch Production — not done; see below.

---

## Report fields

**CURRENT FIRMWARE VERSION:** `5.5.7` (at audit start) → bumped to `5.6.0`
as part of this fix (`esp-kiosk/CHANGELOG_v5_6_0.md`).

**PENDING JOURNAL:** NVS `mesflow`/`pending_tx`, single `PendingTransaction`
struct, own checksum, persistent across reboot.

**OFFLINE QUEUE:** LittleFS `/offline_events.log`, append-only
`OfflineLogRecord`s (EVENT/ACK/REJECT), FNV1a32-checksummed, persistent.

**OFFLINE SESSION STORAGE:** LittleFS `/offline_sessions.bin`, fixed-size
array, atomic rewrite, persistent.

**ACK STORAGE:** Same file as the offline queue (`recordType=ACK`/`REJECT`
markers) — before this task, unreachable for replay once written; now
retained and replay-able for 72h/200 events via `compactOfflineEventLog()`/
`findLoggedEvent()`.

**WORKER CACHE:** LittleFS `/workers.bin`, keyed by `qr`, capacity 160
(PSRAM) / 80 (no PSRAM).

**OPERATION CACHE:** LittleFS `/operations.bin`, keyed by `qr`+`station`,
capacity 320 (PSRAM) / 120 (no PSRAM).

**CURRENT MAX OFFLINE EVENTS:** 500 (PSRAM) / 64 (no PSRAM) —
`MAX_OFFLINE_EVENTS`.

**CURRENT RETENTION:** Before this task: **unbounded** (no compaction
existed). After: still-pending events unbounded/forever (correct — they're
not synced yet); ACKed/REJECTed events retained 72h **or** newest 200,
whichever keeps more, auto-compacted every ~6h and after each successful
reconciliation.

**BACKEND IDEMPOTENCY:** YES — three independent layers: `kiosk_client_events.
client_event_id` UNIQUE (offline-sync layer), `(kiosk_id,local_sequence)`
UNIQUE (device-sequence layer), `work_sessions.start_request_id`/
`finish_request_id` UNIQUE (session layer, `request_id=event_id`).

**UNIQUE KEY:** `client_event_id` = `"<DEVICE_ID>-<10-digit device
sequence>"`, generated once on the device, never regenerated on replay.

**SERVER FAILOVER SAFE TODAY:** **YES** (after this task's changes).
**Before this task: NO** — see section 4 (real, confirmed gap: already-
ACKed events had no code path back to being replayable, and there was no
concept of a server generation for the device to even know reconciliation
was needed).

**DATA LOSS WINDOW FOUND:** YES, confirmed and fixed — precise mechanism:
ACK did not erase payload bytes, but made them permanently unreachable for
replay (no lookup function existed), combined with unbounded log growth
whose only cleanup was a fully destructive manual wipe. See section 4.

**RECENT ACK REPLAY:** Implemented — 72h **or** newest 200 events,
whichever retains more; wear-conscious atomic compaction; every required
field preserved (`event_id`, `local_session_id`, `worker_qr`,
`operation_qr`, `qty`, `device_sequence`, `boot_id`, `event_epoch`); never
regenerates `event_id`.

**SERVER GENERATION:** Implemented — `server_generation` table
(`cluster_id` default `MESFLOW-PROD`, `generation_id` random token, never
IP-derived), admin-only explicit bump endpoint, exposed via bind +
heartbeat responses, compared and persisted (NVS) on the device.

**RECONCILIATION:** Implemented — `POST /api/kiosk/reconcile`: device
sends sequence range + recent event_id manifest, server returns exactly
what's missing (compact range-collapsed), device replays only those
through the existing sync endpoint, existing idempotency remains the final
safety net. Proven end-to-end by the flagship test (section 12).

**FAILURE MATRIX:** See section 3 — all 7 cases (A-G) reasoned through;
only case E was unsafe before this task, now safe.

**DR TEST RESULT:** **PASS** —
`mesflow/tests/test_kiosk_reconciliation.py::TestFlagshipDisasterRecoveryScenario::
test_reconciliation_fills_gap_exactly_once_no_lost_no_duplicate_sessions`:
Server B (restored with only E100-E105) ends up with E100-E110 **exactly
once** (11 events, 6 work sessions, zero duplicates) after reconciliation,
verified idempotent under a second replay pass.

**PRODUCTION TOUCHED: NO.**

No `mesflow-test`/Production SSH session was opened. No migration was run
against any real database (including local DEV — a schema change to the
shared local Postgres was deliberately avoided as too invasive for this
task; the new migration `0038_v73_kiosk_dr_reconciliation.py` was
syntax-checked but not applied anywhere). No ESP32 hardware was flashed.
All 21 new automated tests (16 backend + 5 firmware-simulation) pass, and
so do the 5 pre-existing firmware-simulation tests they sit alongside
(26/26 total across both test files) — ran against disposable venvs,
mocked repositories, or pure in-memory simulation only.
