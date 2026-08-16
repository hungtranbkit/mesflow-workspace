# Build and promote workflow

On the DEV Deploy Agent:

```text
Build & Release → Build Release
→ review image/digest/package
→ Deploy Local
→ verify health/version/browser
→ Promote Production Test (same package/digest)
→ after TEST_PASS + human approval, Promote Production
```

Production and Production Test Agents must run with `MESFLOW_BUILD_ENABLED=false`. They receive image releases and never build source. A changed source requires a new MESFlow version and a new image digest; an existing version is never overwritten.
