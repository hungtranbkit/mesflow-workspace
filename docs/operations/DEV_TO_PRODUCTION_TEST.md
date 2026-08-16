# DEV to Production Test

DEV uses `SERVER_ROLE=DEV`, `MESFLOW_BUILD_ENABLED=true`, and builds with `mesflow/scripts/build-release.sh`. **Deploy Local** must use the frozen release ZIP and image-release handler with `--no-build`. Only after local health/version/browser verification is `LOCAL_PASS` valid.

The Production Test Agent runs with `SERVER_ROLE=PRODUCTION_TEST` and `MESFLOW_BUILD_ENABLED=false`. Promotion must verify the exact frozen ZIP SHA and image digest before remote deploy. Production is not part of this task.
