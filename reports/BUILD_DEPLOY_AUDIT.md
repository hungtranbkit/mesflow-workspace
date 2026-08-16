# Build/deploy audit

## Existing path

- MESFlow `compose.yml` used `build: context: .` and a mutable image tag.
- Deploy Agent extracted uploaded source ZIPs, staged the tree, ran `docker compose config`, then ran `docker compose build mesflow` on the target host.
- Migration-head validation also ran through the staged Compose project.
- QA Center currently has its own Docker/source deployment path and was not changed in this phase.

## New path

- `mesflow/scripts/build-release.sh` builds the image in the workspace, saves an image bundle, writes digest metadata, checksums and a source-free release ZIP.
- Image releases are identified by `release.json.type=mesflow-image-release` and `image_digest`.
- Deploy Agent loads/pulls and verifies the digest, uses `MESFLOW_IMAGE=image@digest`, validates Compose and never builds the image in image mode.
- Legacy source ZIP remains available for transition and rollback.

No production system was modified.
