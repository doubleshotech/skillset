# sentry skill — eval harness

Deterministic evals for the **setup** workflow of the `sentry` skill. They measure
whether an agent, given the skill, wires Sentry into a repo correctly — across three
stacks the skill's single worked example does *not* cover (Express, Next.js App Router,
Django).

## Layout

```
evals/
├── grade_repo.py          # static grader → grading.json (grader.md schema)
├── evals.json             # the 3 eval prompts + expectations
└── fixtures/              # pristine, Sentry-less repos to run the skill against
    ├── repo-express/      # Node/Express API
    ├── repo-nextjs/       # Next.js App Router
    └── repo-django/       # Python/Django
```

Each fixture has exactly one **swallow point**: a `try/catch` (or `except`) that catches
an error and returns 500 **without rethrowing**. Sentry's auto-instrumentation can't see
those, so capturing them requires the skill's distinctive swallow-point step — that's the
discriminating assertion.

## Running

1. Copy a fixture somewhere writable and have an agent (with the skill) perform the
   matching prompt from `evals.json` against it, editing in place.
2. Grade the result:

   ```bash
   python3 grade_repo.py --repo <path-to-wired-repo> --stack <express|nextjs|django> \
       --summary <SUMMARY.md|""> --out grading.json
   ```

`grade_repo.py` checks nine principles: SDK installed, init at the true entry,
captureException **inside the swallow catch/except**, all-or-nothing PII-safe config,
DSN-from-env (not hardcoded), dev/test gating in code, NaN sample-rate guard, and that a
diagnosis/plan was produced.

## Grader notes (hardened)

The grader is grep-based but defends against the usual false signals: comments are blanked
before matching (so `// TODO: Sentry.init()` never counts), the swallow check requires the
capture **inside** the catch/except block, a `dataCollection` block only passes if it
disables every PII vector, dev/test gating must be a real Sentry-disabling construct, and
an empty/missing repo fails loudly. Sanity checks: a pristine fixture scores ~1/9 and a
comments-only repo ~1/9; a correctly wired repo scores 9/9.
