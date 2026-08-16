# MESFlow image release contract

MESFlow releases are built once in the workspace and promoted by digest. The release ZIP contains `release.json`, `PROMOTION.json`, `compose.yml`, checksums and a Docker image bundle; it contains no application source.

```text
./mesflow/scripts/build-release.sh
→ local Deploy Agent
→ verify health/version/browser
→ freeze digest
→ same release ZIP to Production Test Agent
```

Registry distribution may replace the bundle when `MESFLOW_IMAGE_REPOSITORY` and registry credentials are configured. The Agent validates `type=mesflow-image-release`, loads/pulls the image, verifies the declared digest, and runs Compose with `MESFLOW_IMAGE=image@digest`. It never runs `docker compose build` for image releases.
