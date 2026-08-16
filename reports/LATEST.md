# Latest report

**2026-08-15 — ProjectFlow standardization**
Scan: [`PROJECTFLOW_STANDARDIZATION_ASSESSMENT.md`](PROJECTFLOW_STANDARDIZATION_ASSESSMENT.md)
Execution/evidence: [`PROJECTFLOW_EXECUTION_STANDARD.md`](PROJECTFLOW_EXECUTION_STANDARD.md)
Reference: [`docs/PROJECTFLOW_INTEGRATION.md`](../docs/PROJECTFLOW_INTEGRATION.md)

Summary: added `WORKSPACE.yaml` + `PROJECT.yaml` for `mesflow-app`,
`deploy-agent`, `qa-center`, `esp-kiosk`. MESFlow App's full local pipeline
(preflight → build → deploy-local → smoke → status → logs → test →
clean-restart) was actually executed against a newly built `71.0.0.5`
artifact, deployed into a new isolated sandbox
(`mesflow/compose.projectflow-local.yml`) that never touched the live
`mesflow-app`/`mesflow-postgres`/`mesflow-qa-center`/`mesflow-deploy-agent`/
`mesflow-nginx` containers already running on this host. Test run surfaced
and fixed one pre-existing test-infra defect (`Dockerfile.test` missing
`COPY gateway ./gateway`); 240/294 tests then passed, with 54 pre-existing
legacy version/UI-snapshot failures reported, not fixed (out of scope).
Production was not touched, deployed, or SSH'd into at any point.
