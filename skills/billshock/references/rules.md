# BillShock Rule Reference (`BILL001`–`BILL016`)

BillShock computes a deterministic **Spend-Safety Score (`0–100`)** by deducting:
- `CRITICAL`: `-18` points (any critical finding caps grade below `SAFE`)
- `HIGH`: `-9` points
- `MEDIUM`: `-4` points
- `LOW`: `-1` point

Grades: `90–100` with `0 CRITICAL` = **SAFE** | `70–89` = **CAUTION** | `<70` = **BILL SHOCK ALERT**.

---

## Pillar 1: `EFFECT_LOOP` — Client Infinite API & Render Storms

| Rule | Severity | What It Catches | False-Positive Guards |
| :--- | :--- | :--- | :--- |
| `BILL001` | Critical | `useEffect` / `useLayoutEffect` calling `fetch`/`axios`/network helpers without a dependency array | Balanced paren/arg parsing verifies 1-arg form AND skips pure DOM/focus/title effects |
| `BILL002` | High | `setInterval(..., ms)` below `1000ms` calling network endpoints | Ignores `>= 1000ms` intervals and animation/clock intervals without network I/O |

## Pillar 2: `AI_BOMB` — Uncapped LLM, Email & SMS Exposure

| Rule | Severity | What It Catches | False-Positive Guards |
| :--- | :--- | :--- | :--- |
| `BILL003` | High | OpenAI, Anthropic, Gemini, LiteLLM, or Vercel AI SDK generation calls missing `max_tokens` / `maxOutputTokens` | Recognizes `max_tokens`, `max_output_tokens`, `maxOutputTokens`, `max_completion_tokens`, spread `...opts`, and `**kwargs` |
| `BILL004` | Critical | Paid AI, Resend, SendGrid, Twilio, or Replicate SDK calls inside loops | Exempts small constant retry loops (`range(3)`, `< 5`) and loops guarded by `pLimit`, `Semaphore`, `.slice(0, ...)`, or `chunk` |
| `BILL005` | Critical | Public HTTP endpoints invoking paid AI/email/SMS APIs with neither auth nor rate limiting | Recognizes session/JWT/webhook auth checks (`getSession`, `Depends`, `stripe-signature`, `x-api-key`) and limiters (`Ratelimit`, `SlowAPI`, `quota`) |

## Pillar 3: `DB_EGRESS` — N+1 Storms & Unbounded Database Scans

| Rule | Severity | What It Catches | False-Positive Guards |
| :--- | :--- | :--- | :--- |
| `BILL006` | High | ORM / SQL queries executed inside `for` / `while` / `.map` loops | Skips small `<= 5` constant loops and chunked batch helpers (`chunk`, `BATCH_SIZE`) |
| `BILL007` | High | `findMany()`, `supabase.select()`, `.objects.all()`, or `SELECT * FROM` in routes without pagination/limits | Applies only inside server route files/handlers and allows `take`, `limit`, `range`, `single`, `cursor`, `count`, `WHERE id =` |
| `BILL008` | Medium | `Promise.all(items.map(...))` executing network/AI/DB work concurrently without limits | Ignores fixed tuple literals `Promise.all([a(), b()])` and `pLimit`/`chunk`/`.slice` bounded pipelines |

## Pillar 4: `RETRY_HANG` — Infinite Loops, Timeouts & Amplification

| Rule | Severity | What It Catches | False-Positive Guards |
| :--- | :--- | :--- | :--- |
| `BILL009` | Critical | Unbounded `while True:` / `while (true)` executing external/DB calls without retry limits or termination signals | Allows bounded counters (`attempt`, `max_retries`) and daemon signal flags (`stop_event`, `shutdown`) |
| `BILL010` | Medium | Server-side `requests`, `httpx`, `urllib`, or outbound `fetch()` missing `timeout` / `AbortSignal.timeout` | Skips browser UI relative `/api/...` calls and tests; recognizes `timeout=`, `signal:`, `AbortSignal` |
| `BILL011` | High | Vercel/Next.js `maxDuration >= 60` wrapping uncapped paid calls with no timeout or rate limit | Fires only when extended duration pairs with unguarded paid SDK calls |

## Pillar 5: `LEAK_POOL` — Connection Pool Exhaustion & Memory Leaks

| Rule | Severity | What It Catches | False-Positive Guards |
| :--- | :--- | :--- | :--- |
| `BILL012` | High | `new PrismaClient()`, `new Pool()`, `createClient()`, or `create_engine()` created inside request handlers | Allows `globalThis` / `global.` singleton patterns and `lru_cache` factories |
| `BILL013` | High | Module-level empty `{}`/`[]`/`Map`/`Set` mutated in request handlers with no eviction or cap | Allows caches bounded via `lru_cache`, `maxsize`, `maxSize`, `TTLCache`, `deque(maxlen=...)`, `.clear()`, or size eviction |

## Pillar 6: `INFRA_CRON` & `DIFF_REGRESSION`

| Rule | Severity | What It Catches | False-Positive Guards |
| :--- | :--- | :--- | :--- |
| `BILL014` | Medium | Sub-5-minute crons (`* * * * *`, `*/1..*/4 * * * *`) in `vercel.json` or GitHub workflows, or `maxDuration > 300` | Allows `>= 5m` crons (`*/15 * * * *`, `0 * * * *`, `0 0 * * *`) |
| `BILL015` | High | Git diff (`--diff` / `--staged`) removing `ratelimit`, `max_tokens`, `timeout=`, `take:`, or `LIMIT` without replacement | Counts added vs removed guards per modified file and ignores docs/tests |
| `BILL016` | Critical | Git diff introducing new sub-5-minute cron schedules (`* * * * *`) | Inspects added `+` lines in non-doc files only |

---

## Configuration & Suppressions

- **Inline:** `// billshock-ignore: BILL010 - unix socket deadline set at transport layer` (or `# billshock-ignore: BILL010 - ...`)
- **`.billshockignore`:** Gitignore-style excluded directories and globs
- **`.billshock.json`:**
  ```json
  {
    "exclude": ["scripts/oneoff"],
    "ignoreRules": ["BILL010"]
  }
  ```
