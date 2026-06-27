# skillset

A Claude Code plugin bundling reusable skills, installed from this GitHub repo as a
one-plugin marketplace. **Intentionally versionless** — the `version` field is omitted
from `.claude-plugin/plugin.json`, so Claude Code falls back to the git commit SHA as the
version. Every **pushed** commit is a new version, so with marketplace **auto-update
enabled** (a one-time toggle — see below), skill edits roll out with **no version bumps**.

> A versionless plugin only auto-updates from a git source, and only when the marketplace
> has auto-update on (off by default for third-party marketplaces) — see
> [How auto-update works](#how-auto-update-works). To ship a change: commit **and push**.

## Skills

Skills live under `skills/<name>/SKILL.md` and are auto-discovered — no registration
in `plugin.json` needed. Each is available to Claude by its `description` and invocable
as `/skillset:<name>`.

| Skill | What it does |
|-------|--------------|
| `sentry` | Sentry error monitoring for **any** repo. **setup** — diagnose the repo's stack (frameworks, runtimes, topology, where config lives) and wire Sentry accordingly: SDK init, error swallow-point capture, a PII-safe config (a real leak if skipped), dev/test quota gating, per-env public DSNs, CI; ships a fully worked Cloudflare-Workers + Vite/React example. **triage & fix** — list live errors, fix the confident ones (one PR per root-cause fix), leave uncertain issues for human review. |

## Install

```
/plugin marketplace add doubleshotech/skillset
/plugin install skillset@doubleshot
```

`skillset@doubleshot` is `<plugin>@<marketplace>`: the **plugin** name `skillset` (from
`plugin.json`) and the **marketplace** name `doubleshot` (from `marketplace.json`'s
`name` field — *not* the GitHub owner, which only appears in the `marketplace add` path).
The install persists across sessions and auto-updates on every pushed commit.

### Verify / manage

```
/plugin                            # browse installed plugins and their skills
/plugin marketplace list           # confirm the 'doubleshot' marketplace is registered
/plugin update skillset@doubleshot   # pull the latest commit immediately
```

Once installed, the `sentry` skill is available to Claude automatically (by its
`description`) and invocable as `/skillset:sentry`.

## How auto-update works

Versioning falls back to the git commit SHA (no `version` is declared anywhere), so every
pushed commit is a new version. But Claude Code only auto-pulls new commits when
**auto-update is enabled for the marketplace** — and for a third-party marketplace like
this one it is **off by default**. Enable it once:

- **UI:** `/plugin` → **Marketplaces** → select `doubleshot` → **Enable auto-update**, or
- **`~/.claude/settings.json`** (declarative / portable):

  ```json
  {
    "extraKnownMarketplaces": {
      "doubleshot": {
        "source": { "source": "github", "repo": "doubleshotech/skillset" },
        "autoUpdate": true
      }
    },
    "enabledPlugins": { "skillset@doubleshot": true }
  }
  ```

With auto-update on, **each session start** Claude fetches the marketplace, detects the new
commit SHA, updates the plugin, and prompts `/reload-plugins`. So to ship a change:

```bash
git add -A && git commit -m "tweak sentry triage gate" && git push
```

To pull **immediately** (or any time auto-update is off):

```
/plugin marketplace update doubleshot     # refresh the marketplace clone
/plugin update skillset@doubleshot        # update the installed plugin
```

Version resolution order: `plugin.json` version → `marketplace.json` entry version → **git
commit SHA** (this repo) → `"unknown"` (non-git / npm). The push matters: remote installs
track the **pushed** commit, so an unpushed local commit won't roll out.

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
