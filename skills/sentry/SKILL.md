---
name: sentry
description: >-
  Sentry error monitoring end to end for a pnpm monorepo (Hono on Cloudflare
  Workers API + Vite/React TanStack Router frontends, deployed via GitHub
  Actions). Two workflows: (1) SETUP — wire Sentry SDKs, a PII-safe data block,
  free-plan quota gating, per-env public DSNs, and CI into a repo. (2) TRIAGE &
  FIX — list current Sentry errors, fix the confident ones (one PR per
  root-cause fix), and leave uncertain issues for human review. Use when adding
  Sentry / error
  tracking / observability, or when asked to "set up Sentry", "check Sentry
  errors", "fix the Sentry issues", or "triage Sentry".
---

# Sentry

Sentry for a pnpm monorepo (Hono-on-Cloudflare-Workers API + Vite/React/
TanStack-Router frontends, GitHub Actions deploy). Pick the workflow, then read
that file **in full** before acting — each is a step-by-step procedure ending in
verification.

## Workflows

- **Set up Sentry in a repo** — SDK wiring, PII-safe `dataCollection`, free-plan
  quota gating, per-env public DSNs, CI → follow **[setup.md](setup.md)**.
- **Triage & fix live errors** — list issues, fix the confident ones (one PR per
  root-cause fix), leave the uncertain ones for a human → follow
  **[triage.md](triage.md)**.

## Shared facts (both workflows)

- **DSN vs auth token.** The **DSN** is *public* config (it ships in the client
  bundle) and routes events to one project — it lives in `wrangler.toml`/env.
  The **auth token** (`SENTRY_AUTH_TOKEN`) is a *real secret*, read-scoped, used
  only to *query* issues during triage — never commit it.
- **One project per app.** API and each frontend report to their own Sentry
  project, so issues, quotas, and alerts stay separated.
- **Find the project from the repo.** The project id is embedded in the DSN that
  setup placed in `wrangler.toml`/CI
  (`https://<key>@<org>.ingest.sentry.io/<project_id>`). Use it to resolve which
  Sentry project an app maps to — no extra config needed.
- **Environments.** Events are tagged `uat` / `production` (see setup.md §3d).
  Triage one environment at a time; default to `production`.
- **PII.** Setup deliberately strips PII from events, but older events may still
  carry it. Never paste raw event payloads into PRs, commits, or logs.
