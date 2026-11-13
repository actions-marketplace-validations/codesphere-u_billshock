# Changelog

All notable changes to **BillShock** are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-11-14

### Added
- **BillShock Agent Skill (`BILL001`–`BILL016`)**: Zero-dependency Python 3.10+ spend-safety and runaway-cost analyzer covering JS/TS, React/Next.js, Python (AST + FastAPI/SQLAlchemy/Django), `vercel.json`, and `.github/workflows` schedules.
- **6 Cost-Safety Pillars**:
  - `EFFECT_LOOP` (`BILL001`–`BILL002`): Unbounded `useEffect` network invocations and sub-second polling intervals.
  - `AI_BOMB` (`BILL003`–`BILL005`): Uncapped LLM completions missing `max_tokens`/`maxOutputTokens`, paid SDKs inside loops, and public endpoints exposing paid SDKs without auth or rate limits.
  - `DB_EGRESS` (`BILL006`–`BILL008`): N+1 ORM/SQL queries inside loops, unbounded handler table scans, and uncapped `Promise.all(items.map(...))` fan-outs.
  - `RETRY_HANG` (`BILL009`–`BILL011`): Infinite retry loops without attempt/shutdown bounds, server HTTP calls missing timeouts, and long serverless `maxDuration` wrapping uncapped paid SDKs.
  - `LEAK_POOL` (`BILL012`–`BILL013`): Per-request DB client/engine instantiation without singleton reuse and unbounded module-level cache growth.
  - `INFRA_CRON` & `DIFF_REGRESSION` (`BILL014`–`BILL016`): Aggressive sub-5-minute crons, oversized function durations, and `--diff` / `--staged` checks catching deleted rate/token/limit guards.
- **Output & Automation**: Text, Markdown, JSON, and SARIF 2.1.0 outputs, `.billshockignore` / `.billshock.json` / inline `billshock-ignore:` suppressions, `--write-baseline` / `--baseline` fingerprinting, Docker image, and GitHub Action (`codesphere-u/billshock@v1`).
