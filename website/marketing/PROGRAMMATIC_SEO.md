# BillShock Programmatic SEO & Topic Cluster Plan

## Core Search & AI Answer Clusters

1. **React & Next.js Infinite Loop Detection**: `BILL001`, `BILL002` — catching `useEffect` without dependency arrays and sub-second polling before Vercel function bills spike.
2. **AI Token Cap & Rate Limit Auditing**: `BILL003`–`BILL005` — enforcing `max_tokens`, Upstash Ratelimit / SlowAPI, and authenticated POST routes for OpenAI, Anthropic, Gemini, and Vercel AI SDK.
3. **Database Egress & Pool Exhaustion Prevention**: `BILL006`, `BILL007`, `BILL012` — detecting Prisma N+1 queries, unpaginated `findMany()`, and per-handler connection instantiation.
4. **Pull Request Diff Guardrails in CI**: `BILL015`, `BILL016` — preventing engineers or coding agents from deleting rate limits, timeouts, or `LIMIT` clauses in GitHub pull requests with native SARIF 2.1.0 annotations.
