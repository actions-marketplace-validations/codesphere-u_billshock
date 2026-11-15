# Changelog

All notable changes to **BillShock** are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] - 2026-11-14

### Added
- **Handy-Inspired Multi-Page Spend-Safety Website (`website/`)**: Launched 5 dedicated pages ([`index.html`](website/index.html), [`studio.html`](website/studio.html), [`proof.html`](website/proof.html), [`docs.html`](website/docs.html), [`rules.html`](website/rules.html)) styled in Spend-Shield Spring Green (`#8ce071`) and Volt Meter Gold (`#fde047`) on Warm Ivory Paper (`#fffdf2`) with a custom Spend-Breaker Wattmeter Shield mascot and outlined `billshock` vector wordmark.
- **Interactive Browser Workbench (`website/studio.html`)**: Live `BILL001`–`BILL014` spend scanner with one-click remediation fixes, 24h cloud blast-radius cost simulator, and interactive `--diff HEAD` / SARIF 2.1.0 / baseline artifact viewer.
- **Repository Docs, GEO/SEO & GitHub Pages**: Added [`docs/GETTING_STARTED.md`](docs/GETTING_STARTED.md), [`docs/CI_AND_REMEDIATION.md`](docs/CI_AND_REMEDIATION.md), Schema.org `@graph` JSON-LD, OpenGraph/Twitter SVG card, [`llms.txt`](llms.txt), [`llms-full.txt`](llms-full.txt), [`sitemap.xml`](website/sitemap.xml), [`robots.txt`](website/robots.txt), [`.github/workflows/pages.yml`](.github/workflows/pages.yml), and [`tests/test_website_and_docs.py`](tests/test_website_and_docs.py).

## [1.0.4] - 2026-11-14

### Fixed
- **macOS Zsh Copy-Paste Safety & Global Skill Paths**: Remove `#` comments from shell code blocks in `README.md` and `SKILL.md` so pasting multi-line blocks in macOS `zsh` (`INTERACTIVE_COMMENTS` off by default) never triggers `zsh: command not found: #`. Document `~/.agents/skills/billshock/scripts/billshock.py` (global `npx skills add` default) alongside `.agents/skills/billshock/scripts/billshock.py` and global `billshock` CLI installation.
- **Broad Root Guard (`--allow-home`) & Hidden Directory Filtering**: Refuse accidentally scanning `$HOME` (`~`) or `/` unless `--allow-home` is specified, skip dot-directories (`.local`, `.vscode`, `.config`, `.cache`, etc.) plus `site-packages`, `dist-packages`, `Library`, and `AppData` during directory walks while keeping `.github/workflows` infra checks active, and silence Python `SyntaxWarning` noise when AST-parsing legacy files.
- **Zero Real-World False Positives Across `BILL003`/`BILL004`/`BILL006`/`BILL007`/`BILL009`/`BILL012`**:
  - Require exact separator boundaries in Python paid/AI/DB call checks (`generate_contents`, `generate_content_config_dict.items`, and `self._interceptor.pre_generate_content` no longer trigger `BILL003`/`BILL004`).
  - Tighten Python DB receiver matching so `dict.get()`, `connection.get()`, `all_queues_in_db_dict.get()`, `self._continuous_sessions.get()`, and `while True: q.get()` no longer trigger `BILL006` or `BILL009`.
  - Exempt Next.js `@supabase/ssr` / `@supabase/supabase-js` HTTP `createClient()` calls from `BILL012` while still catching unpooled `new PrismaClient()`, `new Pool()`, and `redis`/`libsql` `createClient({ ... })`, and recognize Supabase `head` / `count` queries plus longer `.eq().order().limit()` chains for `BILL007`.

## [1.0.3] - 2026-11-14

### Improved
- Exclude installed agent directories (`.agents`, `.claude`, `.cursor`, `.codex`, `.gemini`) and any `*/skills/billshock/scripts/billshock.py` path from repository scans so local `npx skills add` installs leave file metrics clean.
- Add `.claude-plugin/icon.png` (512x512 PNG), `marketplace.json` description, and Claude Code `/plugin install billshock --marketplace codesphere-u/billshock` instructions alongside `uv tool install`, `pip install`, `uvx`, and `curl | python3` one-liners in `README.md`.

## [1.0.2] - 2026-11-14

### Hardened
- Recover cleanly on unescaped single-line apostrophes inside JSX/TSX text (for example `<p>We're ready</p>`) so React strings never corrupt downstream comment/brace scanning.
- Wire server-side `axios` timeout detection (`BILL010`) with exemption for `axios.create({ timeout })` and variable `fetch(url, init)` objects when `AbortSignal.timeout`/`signal` is configured.
- Prevent unverified `/webhook` routes from bypassing `BILL005` unless cryptographic signature/auth verification is present.
- Exempt Django `Paginator`, `.iterator()`, `.count()`, and `.exists()` from `BILL007`, and avoid duplicate `BILL007` reports from nested Python closures.
- Skip YAML/code comments in workflow cron scans (`BILL014`) and git diffs (`BILL015`/`BILL016`), generalize `BILL016` cron detection to non-`*` time ranges (such as `*/2 9-17 * * 1-5`), skip symlinks in `run_scan`, tighten `BILL008` string-array false positives, add `.dockerignore`, and sync `SKILL.md` metadata version.

## [1.0.1] - 2026-11-14

### Fixed
- Align `README.md` GitHub Actions workflow inputs (`path`, `diff`, `fail-on`, `min-score`, `sarif-file`) and SARIF upload snippet cleanly with `action.yml`.
- Add test guard asserting `README.md` workflow input examples never drift from `action.yml`.

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
