#!/usr/bin/env python3
"""
Deterministic grader for the Sentry-skill evals.

Inspects the repo a run produced (outputs/repo/) and checks the skill's
distinctive principles by static inspection. Emits grading.json in the
grader.md schema (expectations[] with text/passed/evidence + summary).

Hardened against the failure modes a grep grader is prone to:
- COMMENTS are blanked before matching (so `// TODO: Sentry.init()` never counts
  as real wiring), preserving line numbers for evidence.
- the swallow-point check requires capture INSIDE the catch/except block.
- PII via `dataCollection` must disable EVERY vector (a partial/empty block is a
  leak, not a pass).
- dev/test gating requires a real DSN-disabling construct, not a stray token.
- DSN-from-env and dependency checks understand common real-world idioms.

Usage:
  python grade_repo.py --repo <dir> --stack <express|nextjs|django> \
      --summary <SUMMARY.md|""> --out <grading.json>
"""
import argparse
import json
import re
import sys
from pathlib import Path

SKIP_DIRS = {"node_modules", ".git", ".next", "__pycache__", "dist", "build", ".venv", "venv"}
TEXT_EXT = {".js", ".ts", ".tsx", ".jsx", ".mjs", ".cjs", ".json", ".py", ".toml",
            ".yml", ".yaml", ".env", ".md", ".txt", ".cfg", ".ini", ""}
JS_EXT = {".js", ".ts", ".tsx", ".jsx", ".mjs", ".cjs"}


# ---- comment stripping (preserves line count / numbers) ---------------------
def _blank_line_comment(line: str, marker: str) -> str:
    """Blank a // or # line-comment, but only when it starts OUTSIDE a string
    (so URLs like https:// inside quotes survive)."""
    in_str = None
    i, n = 0, len(line)
    while i < n:
        c = line[i]
        if in_str:
            if c == "\\":
                i += 2
                continue
            if c == in_str:
                in_str = None
            i += 1
            continue
        if c in ("'", '"', "`"):
            in_str = c
            i += 1
            continue
        if line.startswith(marker, i):
            return line[:i] + " " * (n - i)
        i += 1
    return line


def strip_comments(text: str, ext: str) -> str:
    if ext == ".py":
        return "\n".join(_blank_line_comment(l, "#") for l in text.split("\n"))
    if ext in JS_EXT:
        # blank block comments first, preserving newlines
        text = re.sub(r"/\*.*?\*/",
                      lambda m: re.sub(r"[^\n]", " ", m.group(0)),
                      text, flags=re.S)
        return "\n".join(_blank_line_comment(l, "//") for l in text.split("\n"))
    return text  # json has no comments; toml/yaml parsed elsewhere


def load_repo(repo: Path):
    """Return (raw_files, code_files). code_files excludes README/.env prose and
    has comments blanked out."""
    raw = {}
    for p in sorted(repo.rglob("*")):
        if not p.is_file():
            continue
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        if p.suffix not in TEXT_EXT and not p.name.startswith("."):
            continue
        try:
            raw[str(p.relative_to(repo))] = p.read_text(encoding="utf-8", errors="replace")
        except Exception:
            pass
    code = {}
    for k, v in raw.items():
        name = Path(k).name
        if k.endswith(".md") or k.endswith(".txt") or name.startswith(".env"):
            continue
        code[k] = strip_comments(v, Path(k).suffix)
    return raw, code


def find(files, pattern, flags=re.I):
    rx = re.compile(pattern, flags)
    for rel, txt in files.items():
        for i, line in enumerate(txt.splitlines(), 1):
            if rx.search(line):
                return f"{rel}:{i}: {line.strip()[:160]}"
    return None


def find_in(files, name_substr, pattern, flags=re.I):
    rx = re.compile(pattern, flags)
    for rel, txt in files.items():
        if name_substr not in rel:
            continue
        for i, line in enumerate(txt.splitlines(), 1):
            if rx.search(line):
                return f"{rel}:{i}: {line.strip()[:160]}"
    return None


# ---- per-stack config ------------------------------------------------------
STACKS = {
    "express": {
        "init": r"Sentry\.init\(",
        "swallow_file": "routes/users.js", "swallow_fn": r"captureException", "lang": "js",
        "pii_false": r"sendDefaultPii\s*:\s*false", "pii_true": r"sendDefaultPii\s*:\s*true",
        "dsn_env": (r"process\.env\s*[.\[]\s*['\"`]?[A-Z_]*SENTRY_DSN"
                    r"|const\s*\{[^}]*\bSENTRY_DSN\b[^}]*\}\s*=\s*process\.env"),
        "rate_key": r"tracesSampleRate",
        "rate_parse": r"tracesSampleRate\s*[:=]\s*(Number\s*\(|parseFloat\s*\(|\+)|(Number|parseFloat)\s*\([^)]*RATE|\+\s*process\.env\.[A-Z_]*RATE",
        "finite": r"Number\.isFinite",
    },
    "nextjs": {
        "init": r"Sentry\.init\(",
        "swallow_file": "api/widgets/route.ts", "swallow_fn": r"captureException", "lang": "js",
        "pii_false": r"sendDefaultPii\s*:\s*false", "pii_true": r"sendDefaultPii\s*:\s*true",
        "dsn_env": (r"(process\.env\s*[.\[]\s*['\"`]?[A-Z_]*SENTRY_DSN|NEXT_PUBLIC_SENTRY_DSN"
                    r"|const\s*\{[^}]*SENTRY_DSN[^}]*\}\s*=\s*process\.env)"),
        "rate_key": r"tracesSampleRate",
        "rate_parse": r"tracesSampleRate\s*[:=]\s*(Number\s*\(|parseFloat\s*\(|\+)|(Number|parseFloat)\s*\([^)]*RATE|\+\s*process\.env\.[A-Z_]*RATE",
        "finite": r"Number\.isFinite",
    },
    "django": {
        "init": r"sentry_sdk\.init\(",
        "swallow_file": "widgets/views.py", "swallow_fn": r"capture_exception", "lang": "py",
        "pii_false": r"send_default_pii\s*=\s*False", "pii_true": r"send_default_pii\s*=\s*True",
        "dsn_env": (r"os\.environ\s*(\.get\(|\[)\s*['\"][A-Z_]*SENTRY_DSN"
                    r"|getenv\(\s*['\"][A-Z_]*SENTRY_DSN"
                    r"|\benv(?:iron)?(?:\.str)?\(\s*['\"][A-Z_]*SENTRY_DSN"
                    r"|\bconfig\(\s*['\"][A-Z_]*SENTRY_DSN"),
        "rate_key": r"traces_sample_rate",
        "rate_parse": r"traces_sample_rate\s*=\s*float\s*\(|float\s*\([^)]*RATE|float\s*\([^)]*SAMPLE",
        "finite": r"isfinite|math\.isfinite",
    },
}

# real DSN literal: key@host/projectid. Placeholders (with < >) never match.
HARDCODED_DSN = r"https://[0-9a-fA-F]{16,}@[\w.-]+/\d+"

PII_VECTORS = [r"userInfo\s*:\s*false", r"cookies\s*:\s*false", r"httpHeaders",
               r"httpBodies", r"queryParams\s*:\s*false"]


def captured_at_swallow(code, swallow_file, fn, lang):
    """Require the capture call INSIDE the catch/except block, not just in the file."""
    for rel, txt in code.items():
        if swallow_file not in rel:
            continue
        lines = txt.split("\n")
        for i, l in enumerate(lines):
            if lang == "py":
                if re.search(r"\bexcept\b", l):
                    base = len(l) - len(l.lstrip())
                    body, j = [], i + 1
                    while j < len(lines):
                        lj = lines[j]
                        if lj.strip() == "":
                            body.append(lj); j += 1; continue
                        if (len(lj) - len(lj.lstrip())) <= base:
                            break
                        body.append(lj); j += 1
                    if re.search(fn, "\n".join(body)):
                        return f"{rel}:{i+1}: {fn} inside except block"
            else:
                if re.search(r"\bcatch\b", l):
                    block = "\n".join(lines[i:i + 15])
                    if re.search(fn, block):
                        return f"{rel}:{i+1}: {fn} inside catch block"
    return None


def pii_safe(code, cfg):
    """Returns (passed, evidence). dataCollection must disable EVERY vector."""
    leak = find(code, cfg["pii_true"])
    if leak:
        return False, f"LEAK: PII explicitly ENABLED -> {leak}"
    ev = find(code, cfg["pii_false"])
    if ev:
        return True, ev
    # accept a COMPLETE dataCollection block (all vectors disabled) only
    dc = find(code, r"dataCollection\s*[:=]")
    if dc:
        whole = "\n".join(code.values())
        missing = [v for v in PII_VECTORS if not re.search(v, whole, re.I)]
        if not missing:
            return True, f"complete dataCollection block -> {dc}"
        return False, f"PARTIAL dataCollection (leak): missing {missing} -> {dc}"
    return False, "no explicit PII-safe setting found (skill requires explicitly disabling PII)"


def gated(code):
    """Dev/test gating that is a REAL Sentry-disabling construct (handles inline
    AND helper-abstracted forms), without firing on stray tokens."""
    strong = [
        # an `enabled:` flag computed from env / DSN / test (incl. helper calls)
        r"enabled\s*[:=][^\n]*(NODE_ENV|nodeEnv|import\.meta\.env\.PROD|\bPROD\b"
        r"|process\.env|\bDEBUG\b|isLocal|Boolean\(|!==?\s*['\"]test|sentryEnabled|sentry_enabled)",
        r"[!=]==?\s*['\"]test['\"]",                     # NODE_ENV !== 'test' / mode === 'test'
        r"SENTRY_DSN\s*[:=]\s*(''|\"\"|None)\b",          # forced-empty DSN (tests/config)
        r"\bisLocal[A-Za-z]*\b|isLocalOrTest|isLocalApiUrl",
        r"test[^\n]*\bin\b[^\n]*sys\.argv|sys\.argv[^\n]*test",  # django test detection
    ]
    for pat in strong:
        ev = find(code, pat)
        if ev:
            return ev
    # DSN conditionally disabled — inline (`dsn: x ? env : undefined`,
    # `dsn || undefined`) or via a resolver that returns undefined/'' for dev.
    rx_dsnref = re.compile(r"SENTRY_DSN|resolveDsn|\bdsn\b", re.I)
    rx_disable = re.compile(r"\b(undefined|null|None)\b|''|\"\"")
    rx_cond = re.compile(r"\?|\|\|")
    for rel, txt in code.items():
        for i, line in enumerate(txt.splitlines(), 1):
            if rx_dsnref.search(line) and rx_disable.search(line) and rx_cond.search(line):
                return f"{rel}:{i}: conditional DSN -> {line.strip()[:120]}"
    # init guarded by a DEBUG/DSN conditional WITHIN 20 lines above the init call
    for rel, txt in code.items():
        lines = txt.split("\n")
        for i, l in enumerate(lines):
            if re.search(r"Sentry\.init\(|sentry_sdk\.init\(", l):
                window = "\n".join(lines[max(0, i - 20):i + 1])
                if re.search(r"if\s+not\s+DEBUG|if\s+DEBUG|if\s+settings\.DEBUG"
                             r"|if\s+(not\s+)?SENTRY_DSN\b", window):
                    return f"{rel}:{i+1}: init gated by nearby DEBUG/DSN conditional"
    return None


def dep_present(raw, stack):
    if stack in ("express", "nextjs"):
        pkg = raw.get("package.json")
        if pkg:
            try:
                j = json.loads(pkg)
                deps = {**j.get("dependencies", {}), **j.get("devDependencies", {})}
                for k in deps:
                    if k.startswith("@sentry/"):
                        return f"package.json dependencies: {k}@{deps[k]}"
            except json.JSONDecodeError:
                pass
        return None
    # django: requirements.txt, then pyproject/Pipfile, non-comment lines only
    for name in ("requirements.txt", "pyproject.toml", "Pipfile", "setup.py", "setup.cfg"):
        t = raw.get(name, "")
        for ln in t.splitlines():
            s = ln.strip()
            if s and not s.startswith("#") and re.search(r"sentry[-_]sdk", s, re.I):
                return f"{name}: {s[:80]}"
    return None


def grade(repo: Path, stack: str, summary_text: str):
    raw, code = load_repo(repo)
    cfg = STACKS[stack]
    exp = []

    def add(text, passed, evidence):
        exp.append({"text": text, "passed": bool(passed), "evidence": evidence or "not found"})

    # 1. SDK dependency (parsed, non-comment)
    ev = dep_present(raw, stack)
    dep_file = "package.json" if stack in ("express", "nextjs") else "requirements.txt"
    add(f"Sentry SDK dependency added to {dep_file}", ev is not None, ev)

    # 2. SDK initialized (real code)
    ev = find(code, cfg["init"])
    add("Sentry SDK is initialized (init call present)", ev is not None, ev)

    # 3. init at true entry / before app code
    if stack == "express":
        instr_imp = find(code, r"(require\(|import\s+)['\"]\.[^'\"]*(instrument|sentry)")
        instr_has_init = any(re.search(r"(instrument|sentry)", k, re.I) and "Sentry.init(" in v
                             for k, v in code.items() if k != "src/index.js")
        before = False
        for rel, txt in code.items():
            if "express()" in txt and "Sentry.init(" in txt and \
               txt.index("Sentry.init(") < txt.index("express()"):
                before = True
        passed = (bool(instr_imp) and instr_has_init) or before
        ev = (instr_imp if (instr_imp and instr_has_init) else
              (find(code, cfg["init"]) if before else None))
        add("Sentry init runs before app code (instrument module imported first w/ init, or init precedes express())",
            passed, ev or "init not before express() and no instrument module (with init) imported first")
    elif stack == "nextjs":
        ev = (find_in(code, "instrumentation", cfg["init"]) or
              find_in(code, "sentry.server.config", cfg["init"]) or
              find_in(code, "sentry.client.config", cfg["init"]) or
              find_in(code, "sentry.edge.config", cfg["init"]) or
              find_in(code, "instrumentation-client", cfg["init"]))
        add("Sentry init lives in Next instrumentation/config files (loaded before app code)",
            ev is not None, ev)
    else:  # django: settings.py OR a settings/ package module
        ev = find_in(code, "settings", cfg["init"])
        add("Sentry init lives in settings (loaded at startup, before requests)",
            ev is not None, ev)

    # 4. captureException INSIDE the swallow catch/except (THE discriminator)
    ev = captured_at_swallow(code, cfg["swallow_file"], cfg["swallow_fn"], cfg["lang"])
    add(f"captureException added at the swallow point ({cfg['swallow_file']} catch/except block)",
        ev is not None, ev)

    # 5. PII-safe (complete config; partial/empty dataCollection is a leak)
    passed, ev = pii_safe(code, cfg)
    add("PII-safe config (PII vectors disabled; sendDefaultPii not enabled)", passed, ev)

    # 6. DSN from env, not hardcoded
    env_ref = find(code, cfg["dsn_env"])
    hard = find(code, HARDCODED_DSN, flags=0)
    add("DSN sourced from env/config (not a hardcoded ingest URL)",
        (env_ref is not None) and (hard is None),
        f"HARDCODED DSN -> {hard}" if hard else env_ref)

    # 7. dev/test gated off in code
    ev = gated(code)
    add("Dev/test environments gated off in code (DSN disabled locally / in tests)",
        ev is not None, ev)

    # 8. NaN sample-rate guard (only meaningful if a rate is parsed from env)
    finite = find(code, cfg["finite"])
    parse = find(code, cfg["rate_parse"])
    rate = find(code, cfg["rate_key"])
    if finite:
        add("Sample rate guarded against NaN (or set to a literal)", True, finite)
    elif parse:
        add("Sample rate guarded against NaN (or set to a literal)", False,
            f"rate parsed from env without a finite guard -> {parse}")
    elif rate:
        add("Sample rate guarded against NaN (or set to a literal)", True,
            f"literal/constant rate (no env parse) -> {rate}")
    else:
        add("Sample rate guarded against NaN (or set to a literal)", True,
            "no env-parsed sample rate present (not applicable)")

    # 9. process: a diagnosis/plan was produced (word-boundary keywords)
    plan_ev = None
    if summary_text:
        low = summary_text.lower()
        keys = [r"\bswallow", r"\bdsn\b", r"\binit", r"\bplan\b", r"\bdiagnos"]
        hits = sum(1 for k in keys if re.search(k, low))
        if hits >= 3:
            plan_ev = f"SUMMARY.md mentions diagnosis/plan ({hits}/5 plan keywords present)"
    add("A diagnosis/plan was produced before wiring (app -> SDK -> init -> swallow points -> DSN)",
        plan_ev is not None, plan_ev)

    passed = sum(1 for e in exp if e["passed"])
    total = len(exp)
    return {
        "expectations": exp,
        "summary": {
            "passed": passed, "failed": total - passed, "total": total,
            "pass_rate": round(passed / total, 4) if total else 0.0,
        },
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True, type=Path)
    ap.add_argument("--stack", required=True, choices=list(STACKS))
    ap.add_argument("--summary", default="")
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()

    if not args.repo.is_dir():
        print(f"ERROR: --repo is not a directory: {args.repo}", file=sys.stderr)
        sys.exit(2)

    summary_text = ""
    if args.summary and Path(args.summary).is_file():
        summary_text = Path(args.summary).read_text(encoding="utf-8", errors="replace")

    raw, _ = load_repo(args.repo)
    if not raw:
        print(f"ERROR: no readable files under {args.repo} — refusing to emit a grade",
              file=sys.stderr)
        sys.exit(2)

    result = grade(args.repo, args.stack, summary_text)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2))
    print(f"{args.stack}: {result['summary']['passed']}/{result['summary']['total']} "
          f"({result['summary']['pass_rate']}) -> {args.out}")
    for e in result["expectations"]:
        print(f"  [{'PASS' if e['passed'] else 'FAIL'}] {e['text']}")
        print(f"         {e['evidence']}")


if __name__ == "__main__":
    main()
