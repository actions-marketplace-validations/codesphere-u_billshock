---
name: billshock
description: >-
  Deterministic Spend-Safety & Runaway-Cost auditor exposing code that triggers
  overnight cloud, LLM, and database bills—infinite useEffect fetch loops,
  uncapped AI token calls, unauthenticated paid endpoints, N+1/unbounded DB
  scans, missing HTTP timeouts, connection pool leaks, sub-5m crons, and diff
  guardrail removals. Use before deploying AI apps, APIs, webhooks, or workers.
license: MIT
compatibility: Requires Python 3.10+ (stdlib only, zero external packages) and optional git for --diff mode.
metadata:
  author: codesphere-u
  version: "1.0.4"
  repository: https://github.com/codesphere-u/billshock
---

# BillShock — Prevent Overnight Cloud, AI & Database Cost Bombs

Never deploy an AI-powered route, frontend effect loop, database query, or background worker until **BillShock** deterministically verifies every spend surface is bounded, authenticated, rate-limited, and timeout-protected.

## When to Run

- Before deploying Next.js/Vercel, FastAPI, Express, or worker apps using OpenAI, Anthropic, Gemini, Resend, Twilio, Prisma, or Supabase
- After scaffolding React `useEffect` fetch hooks, webhook handlers, or background loops
- In pull requests (`--diff`) to ensure rate limits, `max_tokens`, timeouts, and `LIMIT` guards are never stripped
- Whenever reviewing vibe-coded or rapid-scaffolded SaaS apps for spend safety

## Mandatory Verification Workflow

### 1. Run the Deterministic Audit

Execute the bundled zero-dependency scanner from this skill's directory (for example, `~/.agents/skills/billshock/scripts/billshock.py`, `.agents/skills/billshock/scripts/billshock.py`, or `~/.claude/skills/billshock/scripts/billshock.py`), or via installed `billshock` / `uvx`:

Full repository spend-safety audit (JSON for structured triage):

```bash
python3 ~/.agents/skills/billshock/scripts/billshock.py . --format json
```

Audit repository AND inspect git diff for removed rate/token/timeout guards:

```bash
python3 ~/.agents/skills/billshock/scripts/billshock.py . --diff HEAD --format text
```

For legacy codebases adopting BillShock incrementally, snapshot existing debt first and fail only on regressions:

```bash
python3 ~/.agents/skills/billshock/scripts/billshock.py . --write-baseline .billshock-baseline.json
python3 ~/.agents/skills/billshock/scripts/billshock.py . --diff HEAD --baseline .billshock-baseline.json --fail-on high
```

> Load [references/rules.md](references/rules.md) for exact rule definitions (`BILL001`–`BILL016`) and false-positive guards.

### 2. Triage by Pillar (Highest Blast Radius First)

Inspect every finding in severity order (`CRITICAL` -> `HIGH` -> `MEDIUM`):

1. **`EFFECT_LOOP` (`BILL001`–`BILL002`)**: `useEffect` calling `fetch`/`axios` with no dependency array (fires on every render) and `<1s` client network polling.
2. **`AI_BOMB` (`BILL003`–`BILL005`)**: LLM calls without `max_tokens`/`maxOutputTokens`, paid SDKs invoked inside unbounded loops, and unauthenticated/unthrottled public routes exposing paid AI/email/SMS keys.
3. **`DB_EGRESS` (`BILL006`–`BILL008`)**: N+1 queries inside loops, unbounded `findMany`/`select`/`SELECT *` in HTTP routes, and uncapped `Promise.all(items.map(...))` fan-out.
4. **`RETRY_HANG` (`BILL009`–`BILL011`)**: Unbounded `while True` retry loops, server HTTP calls missing `timeout`/`AbortSignal.timeout`, and long `maxDuration` wrapping uncapped calls.
5. **`LEAK_POOL` (`BILL012`–`BILL013`)**: Creating `new PrismaClient()`/`Pool`/`create_engine()` per handler instead of singletons, and unbounded module-level caches leaking RAM.
6. **`INFRA_CRON` & `DIFF_REGRESSION` (`BILL014`–`BILL016`)**: Sub-5-minute crons (`* * * * *`) in `vercel.json` / workflows, excessive `maxDuration`, or removed `ratelimit`/`max_tokens`/`LIMIT`/`timeout` checks in diffs.

### 3. Remediate Properly (Strict Anti-Bypass Rule)

> **CRITICAL:** Never resolve a BillShock finding with `billshock-ignore` just to turn CI green, or swap an unauthenticated endpoint for a client-side flag. Add real dependency arrays, rate limiters, auth checks, `max_tokens`, `take`/`LIMIT`, timeouts, and singleton DB clients.

Consult [references/remediation.md](references/remediation.md) for copy-pasteable production fixes across Next.js, Upstash Ratelimit, Prisma, OpenAI/Anthropic/AI SDK, FastAPI/SlowAPI, `httpx`, and `vercel.json`.

If an intentional exception genuinely applies (for example, an internal health monitor), attach a rule-scoped inline reason:

```ts
// billshock-ignore: BILL010 - local daemon Unix socket adapter sets transport deadline separately
```

### 4. Re-Verify & Report Receipts

Re-run BillShock after remediation alongside the repo's real test suite:

```bash
python3 ~/.agents/skills/billshock/scripts/billshock.py . --diff HEAD --fail-on high
```

Include in your final report:
- Observed **BillShock Score (`0–100`) and Grade** (`SAFE` / `CAUTION` / `BILL SHOCK ALERT`)
- Every resolved finding (`rule_id` and `file:line`)
- Any justified remaining exceptions
