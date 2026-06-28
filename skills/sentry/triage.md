# Sentry triage & fix

List the current Sentry errors for a project, fix the ones you are confident
about as **one PR per issue**, and leave everything uncertain for a human. The
deliverable is two things: a set of small PRs, and a written list of the issues
you did **not** touch (with why). Bias hard toward leaving issues alone — a wrong
auto-fix costs more than an unfixed error.

## 0. Before you start

- **Prefer the `sentry` CLI** (the agent CLI at `cli.sentry.dev`): `sentry auth
  login`, then `sentry issue list` and `sentry issue explain <id>`. It
  auto-detects the project from the repo/`.env` and takes `--json`. If it isn't
  installed, fall back to the **Sentry MCP** (`/mcp`; `mcp.sentry.dev` or
  self-hosted `@sentry/mcp-server`), then the **REST API** (below). Confirm exact
  CLI/MCP shapes at call time (`sentry issue --help`); don't assume them.
- **Base URL.** REST examples use `$SENTRY_API_BASE` (default `https://sentry.io`).
  Self-hosted / non-US-region users must point it at their own instance — a token
  is only valid against the instance that issued it.
- **Auth + scope.** `SENTRY_AUTH_TOKEN` is a *real secret* — never commit it; if
  missing, stop and ask. This workflow **writes** (it assigns/un-assigns issues to
  track progress — §1a, §4b), so the token needs **`event:write`** on top of the
  read scopes (`event:read`, `project:read`, `org:read`). With a read-only token,
  skip the assignment dance and dedup via open `fix/sentry-<shortId>` PRs instead.
- **Use a dedicated triage assignee.** "In progress" isn't a native Sentry status,
  so the marker is **assignment**. Set `SENTRY_TRIAGE_ASSIGNEE` to a *dedicated*
  account (its username/`<email>` works in both the `assignedTo` write and the
  `assigned:` search filter; a team works too but searches as `assigned:#<team-slug>`)
  — **not** a regular human — so this workflow's marker stays distinguishable from
  human/auto assignment and §1a only ever un-sticks issues *it* assigned. If unset,
  ask once and export it; **never assign an empty value** (empty *unassigns*).
- **Resolve org + project.** You need the **org slug** (ask or from config) and the
  **numeric `project_id`** from the DSN in the repo
  (`https://<key>@o<org>.ingest.sentry.io/<project_id>` — see setup.md). The list
  endpoint takes the org slug + numeric project id. Confirm which app and which
  environment (default `production`).

## 1. Reconcile stale markers, then list candidates

### 1a. Un-stick dead markers first

Assignment is this workflow's "in progress" marker, and §1b's `is:unassigned`
filter hides **every** assigned issue — so without this step an issue whose fix
never landed stays hidden *forever* (Sentry keeps the assignee across
resolve→regress, so even a regression won't resurface it). List the issues *this
workflow* assigned and release the dead ones:

```bash
curl -s -f -H "Authorization: Bearer $SENTRY_AUTH_TOKEN" \
  "$SENTRY_API_BASE/api/0/organizations/<org>/issues/?project=<project_id>&query=is:unresolved+assigned:$SENTRY_TRIAGE_ASSIGNEE&statsPeriod=90d"
```

For each, find its `fix/sentry-<shortId>` PR (`gh pr list --state all --search
fix/sentry-<shortId>`). **Un-assign** (return it to triage) if the fix is dead —
the PR was **closed unmerged**, or the issue is now **Regressed** (`is:regressed`,
i.e. the fix shipped but didn't hold). Leave it assigned only while its PR is still
**open** (genuinely in progress). Un-assigning is an empty `assignedTo` on the
issue's **numeric `id`**:

```bash
curl -s -f -X PUT -H "Authorization: Bearer $SENTRY_AUTH_TOKEN" \
  -H "Content-Type: application/json" -d '{"assignedTo": ""}' \
  "$SENTRY_API_BASE/api/0/issues/<numeric_id>/"
```

### 1b. List candidates (ranked, capped, unassigned only)

Filter **`is:unresolved is:unassigned`** so issues still in progress (1a) drop out
— this is what stops a rerun re-triaging errors you've already PR'd.

CLI (preferred):

```bash
sentry issue list --query "is:unresolved is:unassigned environment:production" \
  --sort freq --json      # confirm exact flag names with `sentry issue list --help`
```

REST (fallback) — org endpoint takes the numeric `project_id` from §0:

```bash
curl -s -f -H "Authorization: Bearer $SENTRY_AUTH_TOKEN" \
  "$SENTRY_API_BASE/api/0/organizations/<org>/issues/?project=<project_id>&query=is:unresolved+is:unassigned+environment:production&statsPeriod=14d&sort=freq"
```

Take the **top ~20 by frequency** — state the cap to the user, don't silently
truncate. Per issue keep the numeric **`id`** (required for every REST write
below — *not* the `shortId`), plus `shortId`, `title`, `culprit`, `count`,
`userCount`, `level`, `lastSeen`, `permalink`, and the `release` tag.

Show the user the ranked list before doing anything else. This is the menu.

## 2. Pull the latest event per candidate

CLI (preferred) — `sentry issue explain <shortId>` analyzes the stack trace,
related events, and your codebase. Use REST for the raw event payload (the numeric
**`id`** from §1, not the shortId):

```bash
sentry issue explain <shortId>          # add --json for structured output
# REST fallback:
curl -s -f -H "Authorization: Bearer $SENTRY_AUTH_TOKEN" \
  "$SENTRY_API_BASE/api/0/issues/<numeric_id>/events/latest/"
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

0. **Skip if already in flight.** `gh pr list --state open --search
   fix/sentry-<shortId>` — if an open PR already covers this issue, don't open a
   second. Belt-and-suspenders with §1b's `is:unassigned` filter, in case a prior
   run's assign (§4b) failed and left the issue unassigned.
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

**Do not merge. Do not *resolve* the Sentry issue(s).** The PR is a *proposal* for
human review; the merge + next release is what resolves them. One PR per fix keeps
review and revert independent.

### 4b. Mark the fixed issues "in progress" (so reruns skip them)

Sentry has no "in progress" status, so **assign** the issues you opened a PR for —
that's the marker, and §1b's `is:unassigned` filter makes the next run skip them.
Assign **only after** the PR exists, **only** issues you actually fixed (leave
uncertain ones unassigned so a human meets them in §5), and **every** issue a
grouped fix covers — loop over each numeric `id`, not just the branch's shortId, or
the rest get re-triaged into a duplicate PR.

`assignedTo` accepts a username, `<email>`, `user:<id>`, or `team:<id>` and needs
an **`event:write`** token (§0). Guard the value and the response — an empty
`assignedTo` *unassigns*, and a swallowed failure (e.g. a read-only token → 403)
would break the dedup invisibly:

```bash
# CLI may expose an assign command in newer builds — check `sentry issue --help`.
[ -n "$SENTRY_TRIAGE_ASSIGNEE" ] || { echo "set SENTRY_TRIAGE_ASSIGNEE first"; exit 1; }
for id in <numeric_id> ...; do      # every issue in the fix, by numeric id
  curl -s -f -X PUT -H "Authorization: Bearer $SENTRY_AUTH_TOKEN" \
    -H "Content-Type: application/json" \
    -d "{\"assignedTo\": \"$SENTRY_TRIAGE_ASSIGNEE\"}" \
    "$SENTRY_API_BASE/api/0/issues/$id/" \
    || echo "WARN: assign failed for $id — it will be re-triaged next run"
done
```

Still **don't `resolve`** here — resolution belongs to the merge + release. If the
fix doesn't hold the issue regresses; **§1a** is what brings a regressed or
abandoned issue back into triage (assignment alone would hide it forever).

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
- **Token scope** — listing/reading needs only read scope, but the assignment
  step (§4b) needs **`event:write`**. Keep the token uncommitted either way. With a
  read-only token, skip §4b and dedup another way (an open `fix/sentry-<shortId>`
  PR already marks the issue handled).
- **Assign ≠ resolve** — "in progress" isn't a real Sentry state, so you *assign*
  to mark work in flight and the `is:unassigned` filter (§1b) keeps reruns from
  re-triaging it. Resolution still belongs to the merge + release. Never
  auto-resolve.
- **Assignment is a marker, not a status — it needs reconciling.** It's one-way
  unless you un-stick it: a closed-unmerged PR, or a **regression** (Sentry keeps
  the assignee across resolve→regress), would otherwise hide the issue from triage
  forever. **§1a** un-assigns those each run; never skip it, or failed/abandoned
  fixes silently vanish from both the fix list and the §5 report.
- **`is:unassigned` can't tell whose marker it is** — Sentry auto-assignment
  (Ownership Rules / suspect commits) or a human assigning-to-investigate also
  removes an issue from the candidate list *and* the §5 report. Use a **dedicated**
  triage assignee (§0) so §1a only touches your own markers; if the project
  auto-assigns, note to the user that pre-assigned issues won't be triaged.
- **Cap and disclose** — triage the top N by frequency and tell the user N;
  don't imply you reviewed everything. Uncertain issues stay unassigned and
  accumulate, so over time they can crowd genuinely new, lower-frequency errors
  below the cap — periodically clear the uncertain backlog (§5) so it doesn't
  starve new issues.
- **PR ≠ merge ≠ resolve** — you open proposals, humans merge, the release
  resolves the Sentry issue. Never auto-resolve.
