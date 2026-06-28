---
name: sentry
description: >-
  Sentry error monitoring for any repo, end to end. (1) SETUP — diagnose the
  repo's stack (frameworks, runtimes, topology, where config lives) and wire
  Sentry accordingly: SDK init, error swallow-point capture, a PII-safe config,
  dev/test quota gating, per-env public DSNs, and CI; includes a fully worked
  example for a Cloudflare-Workers + Vite/React monorepo. (2) TRIAGE & FIX — list
  current Sentry errors, fix the confident ones (one PR per root-cause fix), and
  leave uncertain issues for human review. Use when adding Sentry / error
  tracking / observability to any stack, or when asked to "set up Sentry", "check
  Sentry errors", "fix the Sentry issues", or "triage Sentry".
---

# Sentry

Sentry error monitoring for **any** repo. Pick the workflow, then read that file
**in full** before acting — each is a step-by-step procedure ending in verification.

## Workflows

- **Set up Sentry in a repo** — diagnose the stack, then wire SDK init,
  swallow-point capture, a PII-safe config, dev/test quota gating, per-env public
  DSNs, and CI → follow **[setup.md](setup.md)**.
- **Triage & fix live errors** — list issues, fix the confident ones (one PR per
  root-cause fix), leave the uncertain ones for a human → follow
  **[triage.md](triage.md)**.

## Shared facts (both workflows)

- **DSN vs auth token.** The **DSN** is *public* config (it ships in the client
  bundle) and routes events to one project — it lives wherever per-env config
  does (env vars, `.env`, `wrangler.toml`, the platform dashboard, CI). The
  **auth token** (`SENTRY_AUTH_TOKEN`) is a *real secret* — never commit it.
  Triage *reads* issues (read scopes) and, to mark a handled issue **in progress**,
  *assigns* it, which needs **`event:write`**; a read-only token works only if you
  skip the assignment step.
- **One project per app.** Each deployable app reports to its own Sentry project,
  so issues, quotas, and alerts stay separated.
- **Find the project from the repo.** The project id is embedded in the DSN that
  setup placed in the app's env/config
  (`https://<key>@<org>.ingest.sentry.io/<project_id>`). Use it to resolve which
  Sentry project an app maps to — no extra config needed.
- **Environments.** Events are tagged per deploy env (`uat` / `production` / …).
  Triage one environment at a time; default to `production`.
- **PII.** Setup deliberately strips PII from events, but older events may still
  carry it. Never paste raw event payloads into PRs, commits, or logs.
