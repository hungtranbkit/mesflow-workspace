# Build once, promote the same image

1. Build from the MESFlow workspace: `./mesflow/scripts/build-release.sh`.
2. Upload the generated `artifacts/releases/<version>/MESFlow_<version>.deploy.zip` to a local Deploy Agent.
3. Validate health, version, schema and browser behavior locally.
4. Freeze the package SHA256 and image digest.
5. Promote that exact package to Production Test. Do not rebuild on the server.
6. Production requires human approval and is not performed by this workflow.

Source ZIP remains available as a legacy transition path and is labelled as server-side build mode.
