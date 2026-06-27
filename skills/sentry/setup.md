# Sentry setup — diagnose the repo, then wire

Add Sentry to **any** repo. There is no fixed stack here: first **diagnose** what the
repo actually is (frameworks, runtimes, topology, where config lives), then apply the
**universal principles** below using whatever SDK that stack needs. A fully-wired example
(Cloudflare Workers API + Vite/React monorepo) follows — it is the template the
principles point to, *not* an assumption about your repo.

## Read first

- **Confirm the SDK's APIs at call time — they drift.** Sentry's `init` call, integration
  names, and PII-option shapes change across SDK majors and differ per platform. For the
  SDK you select, verify the exact init + integration shapes against the **current Sentry
  docs for that platform** (`sentry.io/platforms/<x>`) or the **Sentry MCP** before
  pasting. A stale API fails silently — events just never arrive.
- **Create your own Sentry projects — never reuse another repo's DSN.** A DSN routes
  events to one project; copying one sends this repo's errors into *that* project. Use
  **one project per app**. (DSNs in the example are `<PLACEHOLDERS>`.)

## Diagnose the repo

Inspect the repo and answer these five questions **per deployable app**. Each answer
feeds a specific setup step, so the diagnosis *is* the plan — don't take a generic
inventory, answer exactly these:

| Question | What it determines |
|---|---|
| **Topology** — how many deployable apps? each server- or client-side? mono/multi-repo, package manager, workspace tool? | **one Sentry project per app**, and which `@sentry/*` family each needs |
| **Framework + runtime + entry point** — backend (Express/Fastify/Hono/NestJS/Next/Remix/Django/Rails/Go…), frontend (React/Vue/Svelte/Angular/SvelteKit…), runtime (Node/Bun/Deno/Workers/Lambda/browser), and where each app boots | the **SDK package** and **where `init` runs** (must be before any app code) |
| **Error swallow points** — does the framework catch errors itself? error middleware, `onError`, route/render/error boundaries, custom try/catch | where to add **`captureException`** so framework-caught errors aren't lost — the highest-value, most framework-specific step |
| **Where per-env config + secrets live** — env vars, `.env`, `wrangler.toml`, platform dashboard, CI secrets | where the **DSN + environment tag** go, per deploy env |
| **Bundler / minification** — is client code minified (Vite/webpack/esbuild/Next/Rollup)? | whether **source maps** are needed for readable stack traces |

Write the answers as a short plan — *app → SDK package → init location → swallow points →
DSN location → source maps (y/n)* — and confirm it with the user before wiring.

For an SDK you don't know cold, get the exact package + init shape from
`sentry.io/platforms`, the Sentry MCP, or `npx @sentry/wizard@latest` (it auto-detects
major JS frameworks — Next, React, Vue, SvelteKit, Remix, Node, etc. — and scaffolds
`init` + source-map upload). **The wizard does NOT add the PII-safe config, dev/test
quota gating, or swallow-point capture below** — those are this skill's value-add and run
*after* it. Use it as a boilerplate accelerator, confirm its current coverage, and don't
treat it as the whole setup.

## Universal principles (apply on every stack)

The SDK and exact syntax change per stack; these don't. The worked example shows each in
real code (the `§` refs point there).

1. **Init at the true entry, before app code** — so Sentry wraps everything: a frontend
   `instrument` module imported first; a server entry wrapped at export. → §3b, §4a–§4b.
2. **Report at swallow points** — a top-level wrapper misses errors the framework
   catches. Add `captureException` at each one the diagnosis found: error middleware /
   `onError` / route + render error boundaries / custom try-catch. The most
   stack-specific step. → §3b, §4c.
3. **PII-safe by default — all-or-nothing.** Explicitly disable **every** PII vector
   (client IP, cookies, request/response headers, bodies, query params). The trap: a
   *partial* privacy config makes the SDK inherit **permissive** defaults for everything
   you didn't name — a silent leak. Mechanism is per-SDK: `@sentry/cloudflare` uses a
   `dataCollection` block (§3c); most Node/browser SDKs use `sendDefaultPii: false` plus
   a `beforeSend`/`beforeSendLog` scrub. **Whatever the mechanism, the PII-negative check
   under _Verify_ is the real gate.** Non-negotiable for any app carrying auth or personal
   data (especially minors').
4. **DSN is public config, not a secret** — it ships in client bundles anyway, so a plain
   env var keeps deploys automated. But each app needs its **own** project DSN or events
   cross-contaminate. → §3d, §4d, §5.
5. **Guard the sample rate** — `Number(badValue)` → `NaN`, which Sentry treats as invalid
   and silently drops every span. Always `Number.isFinite(rate) ? rate : 1.0`. → §3b, §4a.
6. **Gate dev + tests OFF in code, not config** — a fresh clone must be quiet by default;
   don't rely on nobody setting a DSN locally. DSN → `undefined` in local dev, forced
   empty in tests. → §3b, §4a, §3e, §6.
7. **Tag the environment** per deploy env (`uat`/`production`/…) so issues, quotas, and
   alerts separate. → §3d, §5.
8. **Source maps for minified clients** — without them deployed stack traces are
   unreadable, and triage can't locate frames. → §8.

## Verify (do not skip — the universal gate)

Stack-independent. The PII check backstops a wrong per-SDK privacy config on *any* stack.

1. **Positive path** — in a deployed/staging env, throw a test error in each app → it
   appears in that app's Sentry project with the right `environment` tag.
2. **PII-negative** (the non-negotiable gate) — open that event in Sentry and confirm it
   carries **no** client IP, request/response headers, cookies, body, or query params. If
   any appear, your privacy config is partial — fix it before shipping.
3. **Quiet path** — run each app locally + run the test suite → **zero** new events land
   in any project.

---

## Worked example — Cloudflare Workers API + Vite/React monorepo

A fully-wired stack the principles point to: 1 Hono-on-Cloudflare-Workers API
(`@sentry/cloudflare`) + 2 Vite + React + TanStack Router SPAs (`@sentry/react`) in a
pnpm monorepo, deployed by GitHub Actions → Cloudflare (Workers + Pages). Sections are
modular — lift the one matching your detected stack. Different stack? The SDK package and
`init` call change; the principles and gotchas don't. (Pinned against `@sentry/*`
`^10.62.0`; re-verify the `withSentry(cb, app)` signature, the `dataCollection` shape, and
`tanstackRouterBrowserTracingIntegration` on any major bump — see **Read first**.)

## 1. Prerequisites

1. In Sentry: create/choose an org, then create one project per app. Platforms:
   API → "Cloudflare Workers"; frontends → "React".
2. Copy each project's **DSN** (Settings → Client Keys). A DSN is **public** —
   it ships in the client bundle anyway — so it is config, not a secret. That
   choice keeps deploys fully automated (no `wrangler secret put` / GH secret
   per env). Treat it as public throughout.
3. Note your org slug + each project slug (needed only for source maps, §8).

## 2. Install dependencies

```bash
pnpm --filter <api-pkg>      add @sentry/cloudflare
pnpm --filter <frontend-pkg> add @sentry/react   # repeat per frontend
```

Pin all `@sentry/*` to the **same** version.

## 3. API — Cloudflare Workers (`@sentry/cloudflare`)

### 3a. Declare the env vars

Add to the Worker's `Env` type (these arrive from `wrangler.toml [vars]`):

```ts
export type Env = {
  // ...existing...
  API_URL: string                      // the Worker's own origin; used for the localhost gate
  SENTRY_DSN?: string                  // public; unset → SDK is a no-op
  SENTRY_ENVIRONMENT?: string          // 'uat' | 'production' | 'development'
  SENTRY_TRACES_SAMPLE_RATE?: string   // '0'..'1' as a string; unset → 1.0
}
```

### 3b. Wrap the default export with `withSentry` + report swallow-points

Hono catches thrown handler errors in its own pipeline, so the worker-level
wrapper alone won't see them — report at each point an error would otherwise be
swallowed (Hono's `onError`, plus any handler with its own try/catch, e.g. an
auth handler, and the frontend route-error boundary in §4c).

```ts
import * as Sentry from '@sentry/cloudflare'
import { Hono } from 'hono'

const app = new Hono<AppBindings>()
  // ...routes...

// Worker-level wrapper misses Hono-caught exceptions; report them here.
app.onError((err, c) => {
  Sentry.captureException(err)
  return c.json({ error: 'internal_error' }, 500)
})

export type AppType = typeof app   // keep this BEFORE the wrap so frontends' hc<AppType> still works

export default Sentry.withSentry((env: Env) => {
  // Guard a fat-fingered rate: Number('20%') → NaN, which Sentry treats as an
  // invalid rate and silently drops every span.
  const rate = env.SENTRY_TRACES_SAMPLE_RATE ? Number(env.SENTRY_TRACES_SAMPLE_RATE) : 1.0
  return {
    // Free-plan quota: skip Sentry on local `wrangler dev` (API_URL is
    // localhost there). Deployed envs (uat/prod) send normally. See §6.
    dsn: isLocalApiUrl(env.API_URL) ? undefined : env.SENTRY_DSN,
    environment: env.SENTRY_ENVIRONMENT,
    tracesSampleRate: Number.isFinite(rate) ? rate : 1.0,
    enableLogs: true,            // ships console.* to Sentry Logs — see §8 (log PII)
    dataCollection: PII_SAFE_DATA_COLLECTION,   // ⚠️ MANDATORY — see §3c
  }
}, app)
```

`isLocalApiUrl` (put it next to `Env`, reuse it for any other localhost gate):

```ts
export function isLocalApiUrl(apiUrl: string | undefined): boolean {
  return (
    !!apiUrl &&
    (apiUrl.startsWith('http://localhost') || apiUrl.startsWith('http://127.0.0.1'))
  )
}
```

### 3c. ⚠️ MANDATORY — PII-safe `dataCollection`

**This is the most important, least obvious step. Skipping it leaks PII.**
Supplying **any** `dataCollection` object flips Sentry's base from its
privacy-safe set to **permissive DEFAULTS**. A *partial* object then silently
inherits permissive values — e.g. adding a custom header deny-list drops the
built-in client-IP filter and ships `CF-Connecting-IP` on every event. An API
that carries auth credentials or any personal data (and especially minors' data)
must disable **every** vector explicitly:

```ts
// Disable every collection vector explicitly. A partial object inherits
// permissive defaults — this is all-or-nothing.
const PII_SAFE_DATA_COLLECTION = {
  userInfo: false,                              // client IP
  cookies: false,                               // session tokens
  httpHeaders: { request: false, response: false }, // IP / auth headers
  httpBodies: [],                               // passwords, payloads
  queryParams: false,                           // reset / invite tokens
}
```

Do not reintroduce a partial `dataCollection` later. **Verify it under _Verify_, above.**

### 3d. `wrangler.toml` — DSN + environment per deploy env

```toml
[vars]                       # default / UAT
API_URL = "https://<your-uat-api-host>"
# DSN is public (also ships in frontend bundles) → plain var, not a secret.
SENTRY_DSN = "<YOUR_API_DSN>"
SENTRY_ENVIRONMENT = "uat"

[env.production.vars]
API_URL = "https://<your-prod-api-host>"
SENTRY_DSN = "<YOUR_API_DSN>"      # same project; only the env tag differs
SENTRY_ENVIRONMENT = "production"
```

Local dev (`wrangler dev`) reads `[vars]`, so the §3b localhost gate is what
keeps dev quiet — you don't need a separate dev DSN. (If you want belt-and-
suspenders, an empty `SENTRY_DSN=` line in `.dev.vars` overrides `[vars]`.)

### 3e. Force Sentry off in tests

If tests load `wrangler.toml [vars]` (e.g. vitest + miniflare), the live DSN
leaks test errors into your project on every run. Override it:

```ts
// vitest.config.ts → miniflare bindings
SENTRY_DSN: '',   // Sentry is a no-op without a DSN
```

**Check (§3):** `pnpm --filter <api-pkg> typecheck` is clean; tests pass.

## 4. Frontends — Vite + React + TanStack Router (`@sentry/react`)

### 4a. `src/instrument.ts` (imported FIRST in `main.tsx`)

```ts
import * as Sentry from '@sentry/react'
import { router } from './router'   // router instance for the tracing integration

const rawRate = import.meta.env.VITE_SENTRY_TRACES_SAMPLE_RATE
  ? Number(import.meta.env.VITE_SENTRY_TRACES_SAMPLE_RATE)
  : 1.0
const tracesSampleRate = Number.isFinite(rawRate) ? rawRate : 1.0   // NaN guard, as in §3b

Sentry.init({
  // Free-plan quota: import.meta.env.PROD is false under the `vite` dev server
  // and true for ANY `vite build` (uat + prod). So dev never sends; deployed
  // builds do. See §6.
  dsn: import.meta.env.PROD ? import.meta.env.VITE_SENTRY_DSN : undefined,
  environment: import.meta.env.VITE_SENTRY_ENVIRONMENT ?? import.meta.env.MODE,
  integrations: [
    Sentry.tanstackRouterBrowserTracingIntegration(router),
    Sentry.replayIntegration({ maskAllText: true, blockAllMedia: true }), // privacy-safe replay
  ],
  tracesSampleRate,
  replaysSessionSampleRate: 0.1,   // sample replays for cost…
  replaysOnErrorSampleRate: 1.0,   // …but always capture an errored session
  enableLogs: true,
})
```

### 4b. `src/main.tsx` — import instrument first, hook React errors

```ts
import './instrument'   // MUST be the first import so init runs before render
import ReactDOM from 'react-dom/client'
import { reactErrorHandler } from '@sentry/react'
// ...

ReactDOM.createRoot(document.getElementById('root')!, {
  onUncaughtError: reactErrorHandler(),
  onCaughtError: reactErrorHandler(),
  onRecoverableError: reactErrorHandler(),
}).render(/* ...RouterProvider... */)
```

### 4c. Router error boundary — report before it's swallowed

TanStack Router's `errorComponent` catches route/loader/render errors before
they reach `reactErrorHandler`. Capture in an effect (not render) so a
re-render can't double-send:

```tsx
function RouteError({ error }: ErrorComponentProps) {
  useEffect(() => { Sentry.captureException(error) }, [error])
  return /* your fallback UI */
}
const rootRoute = createRootRoute({ component: AppShell, errorComponent: RouteError })
```

### 4d. Frontend env vars

- **Dev:** a per-app `.env.local` with `VITE_SENTRY_DSN=` left **blank** (SDK
  no-op). Keep `VITE_SENTRY_DSN` OUT of a shared root `.env.local` or all apps
  would report under one project.
- **Deployed:** injected at build time by CI per app/env (§5).

**Check (§4):** `pnpm --filter <frontend-pkg> typecheck` is clean; `vite build`
inlines `PROD=true` (so the `: undefined` branch is dropped and the DSN
survives — grep the built bundle for your DSN to confirm).

## 5. CI / deploy (GitHub Actions)

Frontend DSNs are baked at **build** time. Pass them as `env:` on the build
step, per app and per environment (no GH secrets needed — public DSNs):

```yaml
- name: Build <app> bundle
  env:
    VITE_SENTRY_DSN: <YOUR_FRONTEND_DSN>     # the app's own project DSN
    VITE_SENTRY_ENVIRONMENT: uat             # 'production' in the prod job
  run: pnpm --filter <frontend-pkg> build
```

The API needs nothing extra in CI — its DSN/env are in `wrangler.toml` (§3d) and
ship with `wrangler deploy`. Typical trigger model: merge to `main` → UAT;
push to a `prod` branch → production.

## 6. Local dev + tests stay silent (free-plan quota)

Three gates, all in code (not config), so a fresh clone is quiet by default:

| Surface | Gate |
|---|---|
| API `wrangler dev` | `dsn: isLocalApiUrl(env.API_URL) ? undefined : …` (§3b) |
| Frontend `vite` dev | `dsn: import.meta.env.PROD ? … : undefined` (§4a) |
| Tests | `SENTRY_DSN: ''` in test bindings (§3e) |

**Known limitation:** the API gate keys off `API_URL`. Running a bare
`wrangler dev` that doesn't set `API_URL` to localhost (so it falls back to the
deployed `[vars]` host) defeats the gate and sends dev events. Keep your dev
script injecting a localhost `API_URL`.

## 8. Optional follow-ups (don't block a hands-off run)

- **Source maps** (deployed stack traces are minified without them): add
  `@sentry/vite-plugin` to each frontend's `vite.config`, and a
  `SENTRY_AUTH_TOKEN` (real secret — write-scoped) + org/project slugs in CI.
  Gitignore `.env.sentry-build-plugin`.
- **Log PII:** `enableLogs: true` ships `console.*` (including error objects
  that may carry emails) to Sentry Logs. If that matters, add a `beforeSendLog`
  scrub.

## 9. Gotchas quick-reference

- **`dataCollection` is all-or-nothing** — any object → permissive base; a
  partial one silently leaks IP/PII (§3c). The single biggest trap. (Per-SDK:
  Node/browser equivalents are `sendDefaultPii: false` + `beforeSend`.)
- **DSN is public** → config, not a secret; keeps deploys automated. But each
  app/repo needs its **own** project DSN or events cross-contaminate.
- **NaN trace rate** — `Number(badValue)` is NaN → Sentry drops every span.
  Always `Number.isFinite(rate) ? rate : 1.0`.
- **Free-plan quota** — gate dev + tests off in code (§6), not by hoping nobody
  sets a DSN locally.
- **One project per app** — separate API / frontend issues, quotas, alerts.
- **Report at swallow-points** — wrappers miss framework-caught errors; add
  `captureException` at `onError`, custom try/catch blocks, and route error
  boundaries.
- **Version drift** — re-verify `withSentry` signature, `dataCollection` shape,
  and the router integration name on any `@sentry/*` major bump (see **Read first**).
