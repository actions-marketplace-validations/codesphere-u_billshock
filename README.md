# BillShock — Runaway-Cost & Spend-Safety Auditor

[![CI](https://github.com/codesphere-u/billshock/actions/workflows/ci.yml/badge.svg)](https://github.com/codesphere-u/billshock/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](pyproject.toml)

**AI coding agents make features work on localhost—and quietly ship \$10,000 cloud bills to production.**  
**BillShock** is a deterministic, zero-dependency Agent Skill & CI gate that audits JavaScript/TypeScript, React/Next.js, Python (FastAPI/SQLAlchemy/Django), `vercel.json`, and GitHub Actions schedules for infinite request loops, uncapped AI token bombs, N+1 DB egress, hung serverless retries, connection-pool leaks, and cost guardrail regressions before you deploy.

---

## Why BillShock?

| Threat | What Agents Ship | Production Consequence | BillShock Rule |
| :--- | :--- | :--- | :--- |
| **React Effect Storm** | `useEffect(() => fetch(...))` with no dependency array | Thousands of requests per browser session | `BILL001`, `BILL002` |
| **Unbounded AI Token Bomb** | `openai.chat.completions.create(...)` with no `max_tokens` inside public POST routes or loops | Single abused endpoint drains monthly LLM credits | `BILL003`–`BILL005` |
| **DB Egress Explosion** | `prisma.order.findMany()` with no `take`, looped DB lookups, unbounded `Promise.all(map)` | Full-table egress spikes & RDS connection exhaustion | `BILL006`–`BILL008` |
| **Hung Retries & Pools** | `while (true)` polling, timeout-free server `fetch`, per-request `new PrismaClient()` | Serverless concurrency saturation & OOM crashes | `BILL009`–`BILL013` |
| **Cron Burn & Diff Regressions** | `* * * * *` crons or deleting `ratelimit` / `max_tokens` / `LIMIT` in a PR | Runaway scheduled invocations & silent security regressions | `BILL014`–`BILL016` |

---

## Quick Start

### 1. Install as an AI Agent Skill ([skills.sh](https://skills.sh) / Claude / Cursor / Codex / Antigravity)

```bash
npx skills add codesphere-u/billshock
```

### 2. Zero-Dependency CLI (`python3` stdlib only, Python 3.10+)

```bash
# Audit current repo
python3 skills/billshock/scripts/billshock.py .

# Audit local repo AND uncommitted git diff cost regressions
python3 skills/billshock/scripts/billshock.py . --diff HEAD --fail-on high --min-score 80

# Emit SARIF 2.1.0 for GitHub Code Scanning
python3 skills/billshock/scripts/billshock.py . --format sarif --output billshock.sarif
```

### 3. Run Ephemerally via `uvx`

```bash
uvx --from git+https://github.com/codesphere-u/billshock@v1.0.0 billshock . --diff HEAD
```

### 4. GitHub Actions CI Gate (`codesphere-u/billshock@v1`)

```yaml
name: BillShock Spend-Safety Gate
on: [pull_request]

permissions:
  contents: read
  security-events: write

jobs:
  billshock:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - uses: codesphere-u/billshock@v1
        with:
          target: .
          diff-ref: origin/${{ github.base_ref }}
          fail-on: high
          min-score: "80"
          upload-sarif: "true"
```

---

## Live Fixture Output

### Runaway App (`tests/fixtures/runaway_app`)

```text
BillShock v1.0.0 — Spend-Safety & Runaway-Cost Report
Target: /Users/darka/.gemini/antigravity/scratch/billshock/tests/fixtures/runaway_app | Files scanned: 4 | AI calls: 2 | DB ops: 1 | HTTP: 5 | Crons: 1
Score:  0/100 (BILL SHOCK ALERT)  [critical=8 high=11 medium=5 low=0]

[CRITICAL] BILL004 backend/jobs.py:20 — Paid SDK call `openai.chat.completions.create` invoked inside unbounded loop.
    code: res = openai.chat.completions.create(
    fix:  Slice input batches, enforce concurrency limits (`p-limit` / `Semaphore`), or move work to a bounded queue.
[CRITICAL] BILL005 backend/jobs.py:20 — Endpoint `run_batch` exposes paid API `openai.chat.completions.create` without auth or rate limiting.
    code: res = openai.chat.completions.create(
    fix:  Enforce session authentication and IP/user rate limiting (e.g., Upstash Ratelimit / SlowAPI) before paid SDK calls.
[CRITICAL] BILL009 backend/jobs.py:31 — Unbounded `while True:` executes external calls without max-retry or shutdown guard.
    code: while True:
    fix:  Enforce a strict `max_retries` ceiling, exponential backoff with jitter, and explicit loop exit conditions.
...
[MEDIUM  ] BILL014 vercel.json:5 — Sub-5-minute cron schedule `* * * * *` runs continuously in production.
    code: "schedule": "* * * * *"
    fix:  Widen cron cadence (`>= 5m`), use queue triggers instead of polling crons, and keep serverless timeouts tight.
```

### Hardened App (`tests/fixtures/clean_app`)

```text
BillShock v1.0.0 — Spend-Safety & Runaway-Cost Report
Target: /Users/darka/.gemini/antigravity/scratch/billshock/tests/fixtures/clean_app | Files scanned: 3 | AI calls: 1 | DB ops: 1 | HTTP: 3 | Crons: 2
Score:  100/100 (SAFE)  [critical=0 high=0 medium=0 low=0]

No runaway loops, uncapped AI calls, unbounded scans, or cost regressions detected.
```

---

## The 6 Cost-Safety Pillars (`BILL001`–`BILL016`)

| Pillar | Rules | What Is Audited |
| :--- | :--- | :--- |
| **`EFFECT_LOOP`** | `BILL001`–`BILL002` | `useEffect`/`useLayoutEffect` calling network I/O without dependency array; sub-1s `setInterval` polling |
| **`AI_BOMB`** | `BILL003`–`BILL005` | Missing `max_tokens`/`maxOutputTokens`; paid AI/email/SMS calls inside loops; unauthenticated/unthrottled paid endpoints |
| **`DB_EGRESS`** | `BILL006`–`BILL008` | N+1 ORM/SQL queries inside loops; unbounded `findMany`/`select`/`SELECT * FROM` scans in routes; uncapped `Promise.all(map)` |
| **`RETRY_HANG`** | `BILL009`–`BILL011` | Infinite `while True`/`while (true)` external-call loops; timeout-free `fetch`/`requests`/`httpx`; long `maxDuration` wrapping uncapped APIs |
| **`LEAK_POOL`** | `BILL012`–`BILL013` | Per-request `PrismaClient`/`Pool`/`create_engine` creation; unbounded module-level `{}`/`[]`/`Map`/`Set` mutated in handlers |
| **`INFRA_CRON` / `DIFF`** | `BILL014`–`BILL016` | Sub-5-minute crons or `maxDuration > 300`; `--diff`/`--staged` removing `ratelimit`/`max_tokens`/`LIMIT`/`timeout=` guards |

Full rule specifications live in [`skills/billshock/references/rules.md`](skills/billshock/references/rules.md), and copy-paste production fixes live in [`skills/billshock/references/remediation.md`](skills/billshock/references/remediation.md).

---

## Configuration & Baselines

- **`.billshockignore`**: Standard glob patterns (for example `legacy/**` or `scripts/*.ts`).
- **`.billshock.json`**:
  ```json
  {
    "exclude": ["legacy/**"],
    "ignoreRules": ["BILL010"]
  }
  ```
- **Inline suppressions**: Add `// billshock-ignore: BILL010` or `# billshock-ignore: BILL013` on the finding line or immediately preceding line.
- **Baselines** (adopt cleanly on legacy repos without blocking unrelated fixes):
  ```bash
  python3 skills/billshock/scripts/billshock.py . --write-baseline .billshock-baseline.json
  python3 skills/billshock/scripts/billshock.py . --baseline .billshock-baseline.json --fail-on high
  ```

---

## Architecture & Repository Layout

```text
billshock/
├── .claude-plugin/
│   ├── marketplace.json
│   └── plugin.json
├── skills/billshock/
│   ├── SKILL.md
│   ├── assets/baseline.example.json
│   ├── references/
│   │   ├── rules.md
│   │   └── remediation.md
│   └── scripts/billshock.py
├── tests/
│   ├── fixtures/{clean_app,runaway_app}/
│   └── test_billshock.py
├── action.yml
├── Dockerfile
└── pyproject.toml
```

---

## Development

```bash
uv venv .venv && uv pip install --python .venv/bin/python -e ".[dev]" pip-audit
.venv/bin/ruff check .
.venv/bin/mypy
.venv/bin/pytest -v
.venv/bin/pip-audit --skip-editable
```

---

## License

MIT — see [LICENSE](LICENSE).
