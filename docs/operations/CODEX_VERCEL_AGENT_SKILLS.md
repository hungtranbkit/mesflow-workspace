# Vercel Agent Skills for Codex — shared MESFlow quality workflow

This is an opt-in, reproducible **host-level installation**, not a Vercel-hosting requirement. It applies to the current Linux/macOS/Windows-with-Bash user after running the installer; committing this repository alone does not install anything on another host.

## Install on each Codex machine

Prerequisites: Node.js, npm/npx, Codex CLI; access to GitHub/npm. Run from the workspace checkout:

```bash
bash scripts/install-codex-vercel-skills.sh
# For actual Chrome-based automated QA as well:
INSTALL_BROWSER_RUNTIME=1 bash scripts/install-codex-vercel-skills.sh
```

Global installation is per **user and per machine**. Run on HP, Dell, m910, Mac separately where needed. Installation is idempotent: the shared block in `~/.codex/AGENTS.md` is appended only once; existing agent rules are preserved.

| Requested capability | Current official package | Scope |
| --- | --- | --- |
| React performance | `vercel-react-best-practices` from `vercel-labs/agent-skills` | React/Next UI |
| Component composition | `vercel-composition-patterns` from `vercel-labs/agent-skills` | React component APIs |
| Web design audit | `web-design-guidelines` from `vercel-labs/agent-skills` | All web UI |
| Browser testing | `agent-browser` from `vercel-labs/agent-browser` | Real-browser QA |
| Next.js conventions | **Bundled version-matched Next docs** | Next.js projects only |

**Important upstream change (Oct 2026):** `next-best-practices` is no longer available as a standalone skill. Next 16.3+ ships version-matched docs and generates AGENTS.md / CLAUDE.md via `next dev`. For older Next.js, inspect the project/version before selecting the documented migration path; never automatically upgrade Next.js.

References:
- https://github.com/vercel-labs/agent-skills
- https://github.com/vercel-labs/agent-browser
- https://github.com/vercel-labs/next-skills

## Definition of done for visual/UI work

1. **Color and clarity**: normal text contrast >= 4.5:1, large text >= 3:1, actionable controls/focus >= 3:1; readable hierarchy, purposeful whitespace, consistent design tokens and typography. Compare screenshots in both light and dark themes when supported.
2. **Layout and interaction**: test at mobile width, desktop 1366x768 and 1920x1080. Check page and modal overflow, sticky headers, long labels, input focus, keyboard navigation, touch.
3. **Functionality and accessibility**: keep user journeys working, form validation, error/empty/loading states, semantic HTML, keyboard and reduced-motion.
4. **Runtime/browser**: after app start, use agent-browser to load, interact, inspect console errors, screenshot before/after and regression flows. The skill is an instruction; runtime needs Chromium installed.
5. **2.5D/3D special gate**: verify camera motion, aliasing/shimmering, pixel ratio/resolution, texture filtering, antialiasing, frame pacing and scene object clarity with real captures. Avoid simply raising devicePixelRatio without measuring frame rate and memory.
6. **Performance/build**: run existing project-specific lint/typecheck/unit/build commands. Compare metrics in the same test environment; do not invent performance numbers.
7. **Evidence and release**: record performed checks with PASS/FAIL/NOT_RUN, screenshots and reproduction steps. A passing UI build is not production approval. Keep original workspace branch/worktree protections.

These gates augment the existing workspace rules, **not** blanket CI automation. Project CI and active QA still require explicit integration before claiming enforcement. React skills should not be applied to Python, WPF, or non-React modules.

## Post-install verification

```bash
npx skills list -g
ls ~/.agents/skills/{vercel-react-best-practices,vercel-composition-patterns,web-design-guidelines,agent-browser}/SKILL.md
agent-browser --version   # only when INSTALL_BROWSER_RUNTIME=1
```

If a host is offline or the Terminal MCP is unavailable, its installation must remain **NOT VERIFIED**; a GitHub commit is not evidence the host has the skill.
