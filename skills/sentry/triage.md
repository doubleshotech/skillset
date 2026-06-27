# Sentry triage & fix

List the current Sentry errors for a project, fix the ones you are confident
about as **one PR per issue**, and leave everything uncertain for a human. The
deliverable is two things: a set of small PRs, and a written list of the issues
you did **not** touch (with why). Bias hard toward leaving issues alone — a wrong
auto-fix costs more than an unfixed error.

## 0. Before you start

- **Prefer the Sentry MCP server if one is connected** (check `/mcp`; hosted at
  `mcp.sentry.dev`, or self-hosted `@sentry/mcp-server`). Use its issue-list and
  issue-detail tools — **discover the exact tool names and response shapes at
  call time; don't assume them.** Fall back to the REST API (below) only if no
  MCP is available.
- **Auth (REST path).** Needs a read-scoped `SENTRY_AUTH_TOKEN` (`event:read`,
  `project:read`, `org:read`) in the environment — a *real secret*, never
  committed. If it's missing, stop and ask for one; do not invent it.
- **Resolve org + project.** Get the project id from the DSN already in the repo
  (env var, `.env`, `wrangler.toml`, platform dashboard, or CI — see setup.md), or ask.
  Confirm which app you're triaging and which environment (default `production`).

## 1. List issues (ranked, capped)

REST:

```bash
curl -s -H "Authorization: Bearer $SENTRY_AUTH_TOKEN" \
  "https://sentry.io/api/0/projects/<org>/<project>/issues/?query=is:unresolved+environment:production&statsPeriod=14d&sort=freq"
```

Take the **top ~20 by frequency** — state the cap to the user, don't silently
truncate. Per issue keep: `id`, `shortId`, `title`, `culprit`, `count`,
`userCount`, `level`, `lastSeen`, `permalink`, and the `release` tag.

Show the user the ranked list before doing anything else. This is the menu.

## 2. Pull the latest event per candidate

REST:

```bash
curl -s -H "Authorization: Bearer $SENTRY_AUTH_TOKEN" \
  "https://sentry.io/api/0/issues/<issue_id>/events/latest/"
```

From the event, read the exception stack trace, focusing on **`in_app: true`**
frames: `filename`, `function`, `lineno`, `context_line`. Map the top in-app
frame to a real `file:line` in the repo and open it.

## 3. Triage — the confidence gate (the heart of this skill)

Classify each issue **confident** or **uncertain**. When in doubt → uncertain.

**Fix (confident) only if ALL hold:**

- The top in-app frame maps to a real, readable line in this repo.
- The root cause is local and unambiguous — a missing null/undefined guard or
  optional-chain, an unhandled rejection, an unvalidated input, an obvious
  off-by-one — and you can state the before/after and *why* it stops the error.
- The fix is small and behavior-preserving (no product/business judgement).
- **You can write a failing test that reproduces it.** If you can't, it isn't
  confident — move it to uncertain. The reproducing test IS the discriminator.

**Leave (uncertain) if ANY hold:**

- Cause is unclear, or the top frame is in a dependency / not `in_app`.
- A frontend frame is **minified with no source map** — you can't locate it
  confidently. Fix source maps first (setup.md → source maps), then re-triage.
- It needs a product/business decision, or changes behavior in a judgement-y way.
- Infra/flaky: timeouts, rate limits, network blips, third-party outages.
- You can't reproduce it / can't write a failing test.
- `lastSeen` predates the **current deployed release** — likely already fixed;
  don't "fix" a resolved error. Check the `release` tag.

## 4. Fix confident issues — one PR per *fix*

**First group by root cause, not by issue.** Several listed issues can share one
underlying bug — same in-app frame, same fix (e.g. the same missing guard surfacing
on three routes, or one util throwing for many callers). Cluster those into a
single fix; keep genuinely independent issues separate. The unit is **one PR per
fix** — usually one issue, sometimes several. (Conversely, never cram unrelated
fixes into one PR just to reduce PR count — that re-couples the human review.)

Per fix (harness rule: branch first if you're on the default branch):

1. `git switch -c fix/sentry-<shortId>` — use the highest-frequency issue's
   `shortId`, or a short slug if the fix spans several.
2. Make the minimal change. A short comment referencing the Sentry `shortId`(s) is
   fine — but never paste event data (PII) into code.
3. Add the failing-then-passing test from §3 — one per distinct symptom the fix
   covers.
4. Run the app's typecheck + tests (e.g. `pnpm --filter <pkg> typecheck` plus the
   suite) — green before the PR.
5. `gh pr create` with a body containing: the **permalink + `shortId` of every
   issue this fixes**, a **redacted** stack-trace excerpt (no PII), the root cause,
   the fix, and how the test proves it.

**Do not merge. Do not resolve the Sentry issue(s).** The PR is a *proposal* for
human review; the merge + next release is what resolves them. One PR per fix keeps
review and revert independent.

## 5. Report the issues you left

Produce a markdown table (and offer to save it as a file) of every uncertain
issue:

| shortId | title | count / users | why left | what a human needs |
|---|---|---|---|---|

This is half the deliverable — "leave uncertain issues" means **surface** them,
not silently skip them.

## 6. Verify

Per-PR typecheck/tests are green. True verification — the error stops arriving —
only happens after deploy; tie back to setup.md → Verify. Note in each PR that the fix
should be confirmed against the live Sentry issue post-release.

## Gotchas

- **PII on the read path** — pulled events may carry IP / headers / body (older
  events, or projects not configured PII-safe). Never paste raw payloads into
  PRs, commits, or logs. Redact to the frame + message.
- **Minified frames = uncertain** — no source map, no confident fix (setup.md → source maps).
- **Release skew** — an issue may already be fixed; check `lastSeen` vs the
  deployed release before touching it.
- **Read-only token** — listing/reading never needs write scope; keep the token
  read-scoped and uncommitted.
- **Cap and disclose** — triage the top N by frequency and tell the user N;
  don't imply you reviewed everything.
- **PR ≠ merge ≠ resolve** — you open proposals, humans merge, the release
  resolves the Sentry issue. Never auto-resolve.
