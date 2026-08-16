# Environment Drift

Captured 2026-08-13 (Asia/Bangkok) after DEV local image deployment.

| Item | DEV LOCAL | PRODUCTION TEST | Severity | Expected | Action |
|---|---|---|---|---|---|
| Server role | `DEV` | `PRODUCTION_TEST` | EXPECTED DIFFERENCE | Roles differ by design | None |
| Build enabled | `true` | `false` | EXPECTED DIFFERENCE | Only DEV builds source | None |
| Source mount | `/workspace/mesflow/mesflow` readable | No source build required; configured path is not mounted | EXPECTED DIFFERENCE | Test receives image releases | None |
| Agent version | `2.16.10-docker-runtime` | `2.16.10-docker-runtime` | PASS | Compatible behavior | None |
| MESFlow version | `65.8.44.65` | `65.8.44.64` | WARNING | Test has not received the new artifact | Promote only after credentials/URL and explicit request |
| Docker image digest | `sha256:0c439f...` | Current test digest not changed | WARNING | Must match after promotion | Do not claim TEST_PASS |
| PostgreSQL major | 17 | 17 | PASS | Same major | None |
| Agent health | healthy | healthy | PASS | Both Agents reachable locally | None |
| QA service | healthy | unavailable in current test runtime | WARNING | QA is separate/optional for this setup | Investigate before QA promotion |

No Production target was mutated. Production Test was only configured to receive image releases; no release was promoted.
