#!/usr/bin/env bash
# Install the current Vercel UI/React skills for Codex in the current OS user account.
# No repositories, CI, deployments or production configurations are modified.
set -Eeuo pipefail

if ! command -v node >/dev/null 2>&1 || ! command -v npm >/dev/null 2>&1 || ! command -v npx >/dev/null 2>&1; then
  echo "ERROR: Node.js, npm and npx are required." >&2
  exit 2
fi
if ! command -v codex >/dev/null 2>&1; then
  echo "WARNING: codex binary is not on PATH; skills may be installed but Codex is not verified." >&2
fi

echo "[1/4] Installing official Vercel skills for Codex (global to current user)"
npx --yes skills add vercel-labs/agent-skills --skill vercel-react-best-practices -a codex -g -y
npx --yes skills add vercel-labs/agent-skills --skill vercel-composition-patterns -a codex -g -y
npx --yes skills add vercel-labs/agent-skills --skill web-design-guidelines -a codex -g -y

echo "[2/4] Installing official agent-browser discovery skill"
npx --yes skills add vercel-labs/agent-browser --skill agent-browser -a codex -g -y

echo "[3/4] Adding idempotent shared Codex quality policy"
codex_home="${CODEX_HOME:-$HOME/.codex}"
mkdir -p "$codex_home"
policy="$codex_home/AGENTS.md"
touch "$policy"
if ! grep -Fq 'MESFLOW_VERCEL_SKILLS_START' "$policy"; then
  cat >>"$policy" <<'RULES'

<!-- MESFLOW_VERCEL_SKILLS_START -->
## MESFlow web UI and browser quality gates
For React/Next.js implementation or review, consult installed vercel-react-best-practices and vercel-composition-patterns, and consult web-design-guidelines for UI/UX reviews. These are relevant-task skills, not commands to refactor unrelated non-React systems.
For Next.js, prefer version-matched bundled Next documentation (Next 16.3+ generates AGENTS.md/CLAUDE.md via next dev). The removed next-best-practices standalone skill must not be installed.
Before marking a visible UI change complete: check legibility, information hierarchy, spacing, consistent tokens, normal text contrast >= 4.5:1, large text contrast >= 3:1, meaningful controls/focus indicators contrast >= 3:1; keyboard, focus, accessibility and reduced-motion; and overflow/tap targets at mobile, 1366x768 and 1920x1080.
When a running test build is available, use agent-browser for real browser smoke tests, screenshots, console errors, and changed user flows. For 2.5D/3D/WebGL also assess antialiasing, pixel density, shimmering, texture sharpness, camera motion, frame pacing, asset quality and performance before claiming visual success. Do not invent a passing visual test.
Keep before/after evidence and record failures, blocked checks, performance/UX regressions and limitations. Passing visual checks does not authorize merging or production deployment; require separate approval.
<!-- MESFLOW_VERCEL_SKILLS_END -->
RULES
fi

echo "[4/4] Verifying installed SKILL.md files"
missing=0
for skill in vercel-react-best-practices vercel-composition-patterns web-design-guidelines agent-browser; do
  found=0
  for root in "$HOME/.agents/skills" "$codex_home/skills"; do
    if [ -f "$root/$skill/SKILL.md" ]; then
      echo "PASS $root/$skill/SKILL.md"
      found=1
      break
    fi
  done
  if [ "$found" -eq 0 ]; then
    echo "FAIL $skill SKILL.md not found"
    missing=1
  fi
done
npx --yes skills list -g

if [ "${INSTALL_BROWSER_RUNTIME:-0}" = "1" ]; then
  npm install --global agent-browser
  agent-browser install
  agent-browser --version
else
  echo "NOTE: agent-browser CLI/Chromium runtime not installed here by default."
  echo "For real browser automation: INSTALL_BROWSER_RUNTIME=1 bash scripts/install-codex-vercel-skills.sh"
fi
echo "NOTE: Next.js best practices are version-matched project docs; not a standalone skill."
if [ "$missing" -ne 0 ]; then
  echo "ERROR: One or more required skill files are missing" >&2
  exit 1
fi
echo "OK: Codex skills present for current OS user"
