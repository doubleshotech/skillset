# skillset

A Claude Code plugin bundling reusable skills, installed from this GitHub repo as a
one-plugin marketplace. **Intentionally versionless** — the `version` field is omitted
from `.claude-plugin/plugin.json`, so Claude Code falls back to the git commit SHA as the
version. Every **pushed** commit is a new version and is re-fetched, so skill edits roll
out automatically with **no version bumps**.

> A versionless plugin only auto-updates from a git source — see
> [How auto-update works](#how-auto-update-works). To ship a change you commit **and
> push**; installs pick it up on the next session (or `/plugin update` now).

## Skills

Skills live under `skills/<name>/SKILL.md` and are auto-discovered — no registration
in `plugin.json` needed. Each is available to Claude by its `description` and invocable
as `/skillset:<name>`.

| Skill | What it does |
|-------|--------------|
| `sentry` | Sentry error monitoring end to end for a pnpm monorepo (Hono-on-Cloudflare-Workers API + Vite/React/TanStack-Router frontends, GitHub Actions deploy). Two workflows: **setup** — SDK wiring, a PII-safe `dataCollection` block (a real leak if skipped), free-plan quota gating, per-env public DSNs, CI; **triage & fix** — list live errors, fix the confident ones (one PR per root-cause fix), leave uncertain issues for human review. |

## Install

```
/plugin marketplace add doubleshotech/skillset
/plugin install skillset@skillset
```

`skillset@skillset` is `<plugin>@<marketplace>` — both are `skillset` here (the plugin
name from `plugin.json`, the marketplace name from `marketplace.json`). The install
persists across sessions and auto-updates on every pushed commit.

### Verify / manage

```
/plugin                            # browse installed plugins and their skills
/plugin marketplace list           # confirm the 'skillset' marketplace is registered
/plugin update skillset@skillset   # pull the latest commit immediately
```

Once installed, the `sentry` skill is available to Claude automatically (by its
`description`) and invocable as `/skillset:sentry`.

## How auto-update works

The "no version → auto-update" behavior is exact. Claude Code resolves a plugin's
version in this order:

1. `version` in `.claude-plugin/plugin.json` — **omitted here**
2. `version` in the `marketplace.json` entry — **omitted here**
3. **git commit SHA** ← this repo lands here
4. `"unknown"` (non-git directories / npm sources)

Neither file declares a version, so **the commit SHA *is* the version** and every pushed
commit is a new version. To ship a change:

```bash
git add -A && git commit -m "tweak sentry triage gate" && git push
```

- **At session start**, Claude compares the cached SHA against the remote's latest
  commit; if they differ it re-fetches the plugin — the automatic path.
- **Mid-session**, `/plugin update skillset@skillset` forces that check immediately.

The push matters: remote installs track the **pushed** commit, so an unpushed local
commit won't roll out.

## Adding a skill

```bash
mkdir -p skills/<new-skill>
$EDITOR skills/<new-skill>/SKILL.md
```

`SKILL.md` frontmatter — `description` is what Claude reads to decide when to invoke,
so make it specific about *what it does and when to use it*:

```markdown
---
name: <new-skill>
description: <what it does + the triggers/phrasing that should invoke it>
---

# <new-skill>
...procedure...
```

Then commit and push — installs pick it up next session (or `/plugin update` now).
