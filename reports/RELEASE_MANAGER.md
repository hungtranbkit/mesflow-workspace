# Release Manager

## Result

The DEV Deploy Agent now exposes a Build & Release Manager card. It reads the configured MESFlow workspace, invokes only `mesflow/scripts/build-release.sh`, and displays the immutable image/digest/package metadata. Build state is persisted in the Agent state store.

`Deploy Local` uses the latest successful release and calls the existing image-release deploy path; it does not rebuild source. Production Test and Production promotion controls remain disabled until remote target configuration and promotion gates are implemented. Production was not mutated.

## Current implementation

- DEV role: `SERVER_ROLE=DEV` (default), `MESFLOW_BUILD_ENABLED=true`.
- Test/Production roles can set `MESFLOW_BUILD_ENABLED=false` and use receive/deploy-only behavior.
- Source path: `MESFLOW_SOURCE_DIR`, default `~/workspace/mesflow/mesflow`.
- Same release package/digest is the promotion identity; no overwrite of built artifacts is performed by the Manager.
- Legacy source ZIP UI remains for transition and is not the recommended image flow.

## Evidence

- Agent test runtime: `2.16.9-docker-runtime`.
- Build endpoint and local deploy endpoint added.
- Template parse and Python compile passed.
- Focused tests: 6 passed.
- The immutable local release previously built is `65.8.44.65`, digest `sha256:0c439f75840b149dcdc51d8164bcd20ee9695ed1636491543fb05a52b289a6e1`.
- No Production Test or Production deployment was executed.
