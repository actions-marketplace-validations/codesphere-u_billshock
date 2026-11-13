# BillShock Remediation Patterns

Use these drop-in fixes instead of adding suppressions.

## `BILL001`: Infinite `useEffect` Fetch Loop

**Before (burns thousands of API requests):**
```tsx
useEffect(() => {
  fetch("/api/chat", { method: "POST", body: JSON.stringify({ prompt }) });
});
```

**After:**
```tsx
useEffect(() => {
  const controller = new AbortController();
  void fetch("/api/stats", { signal: controller.signal });
  return () => controller.abort();
}, [orgId]);
```

## `BILL003` + `BILL005` + `BILL010`: Public Uncapped LLM Endpoint

**After (Next.js App Router with auth, rate limit, `max_tokens`, and timeout):**
```ts
import { Ratelimit } from "@upstash/ratelimit";
import { Redis } from "@upstash/redis";
import OpenAI from "openai";

const openai = new OpenAI({ apiKey: process.env.OPENAI_API_KEY });
const ratelimit = new Ratelimit({
  redis: Redis.fromEnv(),
  limiter: Ratelimit.slidingWindow(10, "1 m"),
});

export async function POST(request: Request) {
  const ip = request.headers.get("x-forwarded-for") ?? "anonymous";
  const { success } = await ratelimit.limit(ip);
  if (!success) return Response.json({ error: "Too many requests" }, { status: 429 });

  const { prompt } = (await request.json()) as { prompt: string };
  const completion = await openai.chat.completions.create(
    {
      model: "gpt-4o-mini",
      max_tokens: 512,
      messages: [{ role: "user", content: prompt.slice(0, 2000) }],
    },
    { signal: AbortSignal.timeout(15_000) }
  );
  return Response.json({ text: completion.choices[0]?.message.content ?? "" });
}
```

## `BILL006` + `BILL007` + `BILL012`: Singleton Prisma + Paginated Batch Query

```ts
import { PrismaClient } from "@prisma/client";

const globalForPrisma = globalThis as unknown as { prisma?: PrismaClient };
export const prisma = globalForPrisma.prisma ?? new PrismaClient();
if (process.env.NODE_ENV !== "production") globalForPrisma.prisma = prisma;

export async function GET(request: Request) {
  const cursor = new URL(request.url).searchParams.get("cursor");
  const rows = await prisma.order.findMany({
    take: 50,
    ...(cursor ? { cursor: { id: cursor }, skip: 1 } : {}),
    select: { id: true, status: true, createdAt: true },
  });
  return Response.json({ orders: rows });
}
```

## `BILL004` + `BILL009` + `BILL010` + `BILL013`: Bounded Python Worker & LRU Cache

```python
from functools import lru_cache
import time
import httpx

MAX_RETRIES = 3

@lru_cache(maxsize=256)
def get_settings_cached(tenant_id: str) -> dict[str, str]:
    resp = httpx.get(f"https://api.example.com/tenants/{tenant_id}", timeout=5.0)
    resp.raise_for_status()
    return resp.json()

def poll_once() -> None:
    for attempt in range(MAX_RETRIES):
        try:
            res = httpx.get("https://api.example.com/health", timeout=5.0)
            res.raise_for_status()
            return
        except httpx.HTTPError:
            if attempt == MAX_RETRIES - 1:
                raise
            time.sleep(2**attempt)
```
