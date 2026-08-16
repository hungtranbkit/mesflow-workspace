# ESP Kiosk Tutorial Pipeline Audit

Audit date: 2026-08-12 (Asia/Bangkok)

## Reconciliation

- MESFlow deployed `65.8.44.52`; workspace `65.8.44.53` contains reviewed, uncommitted Session Exception work. No `/opt` source was imported over it.
- Deploy Agent deployed `2.13.1-docker-runtime`; workspace `2.14.1-docker-runtime` is newer and contains the current upload/deploy reliability work. No `/opt` source was imported over it.
- Reconcile reports: `RECONCILE_mesflow_20260812_124748.md` and `RECONCILE_deploy_agent_20260812_124748.md`.

## Current generator/package

- Firmware source and live framebuffer agree on `ESP32-KIOSK-5.1.9-WORKER-QTY-FLOW`.
- Seven silent MP4 files exist and fresh-capture provenance is available.
- The generator currently creates a video-oriented manifest but no independent tutorial version, package contract, `VERSION.txt`, or reusable ZIP packaging command.
- Existing manifest fields do not yet match the requested publish contract.

## Current Deploy Agent

- MESFlow and QA uploads have separate routes/forms; MES upload already has visible manual fallback and staged job status.
- Existing “tutorial rebuild” is for MESFlow web tutorial generation, not ESP Kiosk tutorial ZIP publishing.
- There is no ESP tutorial upload endpoint, strict manifest/MP4 allowlist, independent tutorial version state, atomic runtime swap, bounded backup policy, or ESP tutorial job stages.
- Container bind-mounts `/opt/mesflow`, so the desired runtime publish path can be reached without modifying source files.

## Current MESFlow

- Existing `Hướng dẫn sử dụng` page dynamically reads `/data/tutorials/manifest.json` and streams authenticated files.
- There is no separate ESP Kiosk navigation/page or API namespace.
- Runtime tutorials are already bind-mounted read-only into the app, making restart-free publication feasible.
- No database table or migration is needed.

## Proposed contract

- Tutorial version: `5.1.9.1`, independent of firmware/MESFlow/Agent versions.
- ZIP root: exactly `esp-kiosk-tutorial/` containing `VERSION.txt`, `manifest.json`, and the seven allowlisted MP4 files.
- Deploy Agent publishes atomically to `${TARGET_HOME}/runtime/tutorials/esp-kiosk`, with one bounded previous-version backup under `runtime/tutorials/backups/`.
- MESFlow reads `runtime/tutorials/esp-kiosk/manifest.json` on every authenticated request and streams only manifest-listed MP4 files from `videos/`.

## Security and failure model

- Reject zip-slip, absolute/traversal paths, symlinks/special files, extra roots/files, malformed JSON, mismatched versions/types, duplicate names, missing/empty MP4, and changed content under an already-published version.
- Stage outside the live directory; construct a publish tree; rename current to backup and temp to current; restore current if verification fails.
- No tutorial file is executed. No database write is involved.

## Version changes required

- MESFlow code change: bump `65.8.44.53` → `65.8.44.54`.
- Deploy Agent change: bump `2.14.1-docker-runtime` → `2.15.0-docker-runtime`.
- Firmware source unchanged: no firmware version bump.
- Tutorial package: new independent version `5.1.9.1`.

Migration required: **NO**  
Production mutation during task: **NO**
