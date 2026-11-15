# Getting Started with BillShock (`v1.1.0`)

BillShock is a deterministic, zero-dependency static spend-safety scanner written cleanly in Python 3.10+ standard library.

## 1. Install Method Overview

### Option A: AI Agent Skill (`skills.sh` / Antigravity / Cursor / Codex / Claude)

```bash
npx skills add codesphere-u/billshock
```

Global install runs cleanly from inside any repository:

```bash
python3 ~/.agents/skills/billshock/scripts/billshock.py . --diff HEAD --fail-on high --min-score 80
```

Project-local install runs from `.agents`:

```bash
python3 .agents/skills/billshock/scripts/billshock.py . --diff HEAD --fail-on high --min-score 80
```

### Option B: Claude Code Plugin

```text
/plugin install billshock --marketplace codesphere-u/billshock
```

### Option C: Zero-Install `uvx` or Global CLI

```bash
uvx --from git+https://github.com/codesphere-u/billshock@v1 billshock . --diff HEAD
```

```bash
uv tool install git+https://github.com/codesphere-u/billshock@v1
```

## 2. Broad Directory Safety Check

By default, BillShock refuses scanning `$HOME` (`~`) or filesystem root (`/`) so accidental invocations inside a parent directory cannot traverse unrelated system caches or user directories. Pass `--allow-home` only when auditing a broad folder intentionally.

## 3. Incremental Adoption on Existing Codebases

Snapshot legacy findings once:

```bash
billshock . --write-baseline .billshock-baseline.json
```

Fail CI only when new spend regressions appear:

```bash
billshock . --baseline .billshock-baseline.json --diff origin/main --fail-on high
```
