# Build/deploy redesign

The target is `BUILD ONCE — PROMOTE SAME IMAGE DIGEST`. The first implementation supports both registry metadata and a portable Docker bundle. Runtime persistent `.env`, PostgreSQL and tutorial mounts remain outside the image. The Agent still keeps the existing application backup and health verification path.

Local build evidence: MESFlow `65.8.44.65`, image digest `sha256:0c439f75840b149dcdc51d8164bcd20ee9695ed1636491543fb05a52b289a6e1`, bundle `artifacts/releases/65.8.44.65/MESFlow_65.8.44.65.deploy.zip`. Compose interpolation with `MESFLOW_IMAGE=image@digest` passed. A real local Agent cutover was not run because this workspace has no configured local Agent target; Production Test and Production were not mutated.

Local end-to-end image deployment requires a running local Agent configured with Docker access; it was not run against Production in this task. The release builder and image-release validation are covered by syntax/contract tests below.
