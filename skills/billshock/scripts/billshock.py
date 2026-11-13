#!/usr/bin/env python3
"""BillShock — Deterministic Spend-Safety & Runaway-Cost Auditor.

Zero-dependency Python 3.10+ scanner exposing runaway loops, uncapped AI token
calls, unauthenticated paid endpoints, N+1/unbounded DB egress, missing HTTP
timeouts, connection pool/memory leaks, aggressive cloud crons, and PR diff
cost-guardrail regressions across JavaScript/TypeScript/JSX/Python projects.
"""

from __future__ import annotations

import argparse
import ast
import fnmatch
import hashlib
import json
import os
import re
import subprocess
import sys
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

VERSION = "1.0.0"
MAX_FILE_BYTES = 512 * 1024

SKIP_FILE_SUFFIXES = (
    ".min.js",
    ".min.mjs",
    ".min.cjs",
    ".bundle.js",
    ".d.ts",
    ".d.mts",
    ".d.cts",
)

EXCLUDED_DIRS = {
    ".git",
    "node_modules",
    ".next",
    "dist",
    "build",
    "out",
    "coverage",
    ".venv",
    "venv",
    "env",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".turbo",
    ".cache",
    ".tox",
    ".eggs",
    "target",
    "vendor",
    ".audit-venv",
    "storybook-static",
}

TEST_OR_FIXTURE_SEGMENTS = {
    "test",
    "tests",
    "__tests__",
    "spec",
    "specs",
    "__mocks__",
    "mocks",
    "mock",
    "fixture",
    "fixtures",
    "stories",
    "storybook",
    "e2e",
    "playwright",
    "cypress",
    "benchmark",
    "benchmarks",
    "eval",
    "evals",
    "example",
    "examples",
    "sample",
    "samples",
    "seed",
    "seeds",
    "migrations",
    "docs",
    "doc",
}

TEST_FILE_RE = re.compile(
    r"(^test_.*\.py$|_test\.py$|^conftest\.py$|"
    r"\.(test|spec|stories|fixture|mock)\.[^.]+$|"
    r"^seed\.[^.]+$)",
    re.IGNORECASE,
)

JS_EXTENSIONS = {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"}
UI_EXTENSIONS = {".jsx", ".tsx", ".vue", ".svelte"}
PY_EXTENSIONS = {".py"}
CODE_EXTENSIONS = JS_EXTENSIONS | PY_EXTENSIONS | {".vue", ".svelte"}

RULE_META: dict[str, dict[str, str]] = {
    "BILL001": {
        "pillar": "EFFECT_LOOP",
        "severity": "critical",
        "title": "Unbounded `useEffect` invoking network I/O without dependency array",
        "help": "Pass an explicit dependency array (`[]` or stable primitives) and abort stale requests on cleanup.",
    },
    "BILL002": {
        "pillar": "EFFECT_LOOP",
        "severity": "high",
        "title": "Sub-second client polling interval invoking network requests",
        "help": "Increase polling intervals (>= 5000ms), use SSE/WebSockets, and clear intervals with AbortController.",
    },
    "BILL003": {
        "pillar": "AI_BOMB",
        "severity": "high",
        "title": "Generative LLM API call omits explicit output token ceiling",
        "help": "Set an explicit `max_tokens` / `maxOutputTokens` / `max_completion_tokens` ceiling on every model call.",
    },
    "BILL004": {
        "pillar": "AI_BOMB",
        "severity": "critical",
        "title": "Paid AI, email, or SMS API called inside unbounded loop",
        "help": "Slice input batches, enforce concurrency limits (`p-limit` / `Semaphore`), or move work to a bounded queue.",
    },
    "BILL005": {
        "pillar": "AI_BOMB",
        "severity": "critical",
        "title": "Public HTTP endpoint exposes paid AI/email/SMS API without auth or rate limit",
        "help": "Enforce session authentication and IP/user rate limiting (e.g., Upstash Ratelimit / SlowAPI) before paid SDK calls.",
    },
    "BILL006": {
        "pillar": "DB_EGRESS",
        "severity": "high",
        "title": "N+1 database/ORM query executed inside loop",
        "help": "Replace looped per-item lookups with a single batched `IN (...)` query, JOIN, or DataLoader.",
    },
    "BILL007": {
        "pillar": "DB_EGRESS",
        "severity": "high",
        "title": "Unbounded database table scan in HTTP endpoint without limit/pagination",
        "help": "Add explicit `take` / `LIMIT` / `.range()` pagination and narrow column projections on route queries.",
    },
    "BILL008": {
        "pillar": "DB_EGRESS",
        "severity": "medium",
        "title": "Unbounded `Promise.all(...map())` fan-out over network or DB calls",
        "help": "Bound concurrency with `p-limit`, fixed chunk sizes, or worker queues to prevent connection/rate exhaustion.",
    },
    "BILL009": {
        "pillar": "RETRY_HANG",
        "severity": "critical",
        "title": "Unbounded `while` retry/poll loop without max attempts or termination guard",
        "help": "Enforce a strict `max_retries` ceiling, exponential backoff with jitter, and explicit loop exit conditions.",
    },
    "BILL010": {
        "pillar": "RETRY_HANG",
        "severity": "medium",
        "title": "Server-side outbound HTTP request omits explicit timeout",
        "help": "Set `timeout=` (requests/httpx) or `AbortSignal.timeout(...)` so hung upstreams cannot burn serverless compute.",
    },
    "BILL011": {
        "pillar": "RETRY_HANG",
        "severity": "high",
        "title": "Zero-delay retry loop or extended `maxDuration` wrapping uncapped calls",
        "help": "Add exponential backoff + jitter between retries and cap external calls inside long serverless durations.",
    },
    "BILL012": {
        "pillar": "LEAK_POOL",
        "severity": "high",
        "title": "Database/pool client instantiated inside runtime request handler",
        "help": "Reuse a module-level / `globalThis` singleton DB client or lifespan connection pool to avoid exhausting connections.",
    },
    "BILL013": {
        "pillar": "LEAK_POOL",
        "severity": "high",
        "title": "Unbounded module-level cache or collection mutated in runtime handlers",
        "help": "Use bounded LRU/TTL storage (`@lru_cache(maxsize=...)` or explicit size eviction) or external Redis caching.",
    },
    "BILL014": {
        "pillar": "INFRA_CRON",
        "severity": "medium",
        "title": "High-frequency cloud/workflow cron schedule or excessive function duration",
        "help": "Widen cron cadence (`>= 5m`), use queue triggers instead of polling crons, and keep serverless timeouts tight.",
    },
    "BILL015": {
        "pillar": "DIFF_REGRESSION",
        "severity": "high",
        "title": "Removed spend/rate guardrail (`rate_limit`, `max_tokens`, `timeout`, `LIMIT`) in diff",
        "help": "Restore explicit rate limits, token ceilings, timeouts, or pagination caps before merging.",
    },
    "BILL016": {
        "pillar": "DIFF_REGRESSION",
        "severity": "critical",
        "title": "Newly introduced sub-5m cron or high-burn guardrail regression in diff",
        "help": "Verify cron cadence, authentication, and spend ceilings on newly added cost-bearing paths.",
    },
}

SEVERITY_ORDER = {"critical": 4, "high": 3, "medium": 2, "low": 1}
SEVERITY_PENALTY = {"critical": 18, "high": 9, "medium": 4, "low": 1}

INLINE_IGNORE_RE = re.compile(r"billshock-ignore\s*:\s*([A-Z0-9,\s_-]+)", re.IGNORECASE)

AUTH_GUARD_RE = re.compile(
    r"\b("
    r"getSession|getServerSession|currentUser|auth\(|requireAuth|authenticate|"
    r"verifyToken|verifyJwt|decodeToken|HTTPBearer|APIKeyHeader|"
    r"get_current_user|constructEvent|stripe-signature|x-hub-signature|"
    r"x-api-key|api_key|apiKey|authorization|webhook"
    r")\b",
    re.IGNORECASE,
)

RATE_LIMIT_RE = re.compile(
    r"\b("
    r"ratelimit|Ratelimit|rate_limit|rateLimiter|limiter|SlowAPI|"
    r"throttle|Throttle|quota|credits|upstash/ratelimit"
    r")\b",
    re.IGNORECASE,
)

BOUND_GUARD_RE = re.compile(
    r"\b("
    r"pLimit|p_limit|pMap|Semaphore|BoundedSemaphore|chunk|chunked|batches|batchSize|"
    r"BATCH_SIZE|slice\s*\(\s*0\s*,"
    r")\b"
)

RETRY_COUNTER_RE = re.compile(
    r"\b(attempt|attempts|retry|retries|max_retries|maxRetries|max_attempts|maxAttempts|"
    r"stop_event|shutdown|closing)\b|signal\.aborted|controller\.signal"
)

EVICTION_GUARD_RE = re.compile(
    r"\b("
    r"lru_cache|maxsize|maxSize|MAX_SIZE|MAX_ITEMS|MAX_CACHE|TTLCache|deque|"
    r"evict|popitem|\.pop\(|\.shift\(|\.clear\(|len\([^)]+\)\s*>|\.size\s*>"
    r")\b"
)

SERVERLESS_HANDLER_FILE_RE = re.compile(
    r"((?:^|/)route\.[tj]sx?$|(?:^|/)pages/api/|api/|routes/|controllers/|views\.py$|endpoints\.py$)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Finding:
    rule_id: str
    pillar: str
    severity: str
    file: str
    line: int
    title: str
    message: str
    snippet: str
    help: str
    fingerprint: str


@dataclass
class ScanConfig:
    exclude_globs: list[str] = field(default_factory=list)
    ignore_rules: set[str] = field(default_factory=set)


@dataclass
class MetricsCounter:
    ai_calls: int = 0
    db_ops: int = 0
    outbound_http: int = 0
    cron_jobs: int = 0


def line_number_at(text: str, offset: int) -> int:
    return text.count("\n", 0, max(0, offset)) + 1


def line_text_at(raw_lines: list[str], line_no: int) -> str:
    if 1 <= line_no <= len(raw_lines):
        return raw_lines[line_no - 1]
    return ""


def make_fingerprint(rule_id: str, rel_path: str, snippet: str) -> str:
    basis = f"{rule_id}|{rel_path}|{snippet.strip()}"
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()[:16]


def is_line_ignored(raw_lines: list[str], line_no: int, rule_id: str) -> bool:
    for check_ln in (line_no, line_no - 1):
        txt = line_text_at(raw_lines, check_ln)
        m = INLINE_IGNORE_RE.search(txt)
        if m:
            tokens = {t.strip().upper() for t in re.split(r"[,\s]+", m.group(1)) if t.strip()}
            if "ALL" in tokens or rule_id.upper() in tokens:
                return True
    return False


def add_finding(
    findings: list[Finding],
    cfg: ScanConfig,
    raw_lines: list[str],
    rule_id: str,
    rel_path: str,
    line_no: int,
    message: str,
    *,
    snippet: str | None = None,
) -> None:
    if rule_id in cfg.ignore_rules:
        return
    if is_line_ignored(raw_lines, line_no, rule_id):
        return
    meta = RULE_META[rule_id]
    snip = (snippet if snippet is not None else line_text_at(raw_lines, line_no)).strip()
    if len(snip) > 140:
        snip = snip[:137] + "..."
    findings.append(
        Finding(
            rule_id=rule_id,
            pillar=meta["pillar"],
            severity=meta["severity"],
            file=rel_path,
            line=line_no,
            title=meta["title"],
            message=message,
            snippet=snip,
            help=meta["help"],
            fingerprint=make_fingerprint(rule_id, rel_path, snip),
        )
    )


def load_config(root: Path) -> ScanConfig:
    cfg = ScanConfig()
    ignore_file = root / ".billshockignore"
    if ignore_file.is_file():
        for raw in ignore_file.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = raw.strip()
            if line and not line.startswith("#"):
                cfg.exclude_globs.append(line.rstrip("/"))
    cfg_file = root / ".billshock.json"
    if cfg_file.is_file():
        try:
            data = json.loads(cfg_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            print(f"billshock: warning: ignoring invalid .billshock.json ({exc})", file=sys.stderr)
            return cfg
        if isinstance(data, dict):
            for pat in data.get("exclude", []) or []:
                cfg.exclude_globs.append(str(pat).rstrip("/"))
            for key in ("ignoreRules", "ignore_rules"):
                for rule in data.get(key, []) or []:
                    cfg.ignore_rules.add(str(rule).upper())
    return cfg


def is_excluded(rel_path: str, cfg: ScanConfig) -> bool:
    parts = Path(rel_path).parts
    if any(p in EXCLUDED_DIRS for p in parts):
        return True
    for pattern in cfg.exclude_globs:
        if fnmatch.fnmatch(rel_path, pattern) or rel_path == pattern or rel_path.startswith(pattern + "/"):
            return True
    return False


def is_test_or_fixture_path(rel_path: str) -> bool:
    p = Path(rel_path)
    if any(seg.lower() in TEST_OR_FIXTURE_SEGMENTS for seg in p.parts[:-1]):
        return True
    return bool(TEST_FILE_RE.search(p.name))


def mask_js_comments(source: str) -> str:
    """Replace JS/TS/JSX line and block comments with spaces while preserving line numbers."""
    out: list[str] = []
    n = len(source)
    i = 0
    state = "code"
    quote = ""
    while i < n:
        ch = source[i]
        nxt = source[i + 1] if i + 1 < n else ""
        if state == "code":
            if ch == "/" and nxt == "/":
                out.append("  ")
                i += 2
                state = "line_comment"
                continue
            if ch == "/" and nxt == "*":
                out.append("  ")
                i += 2
                state = "block_comment"
                continue
            if ch in ("'", '"', "`"):
                quote = ch
                out.append(ch)
                i += 1
                state = "string"
                continue
            out.append(ch)
            i += 1
        elif state == "line_comment":
            if ch == "\n":
                out.append("\n")
                state = "code"
            else:
                out.append(" ")
            i += 1
        elif state == "block_comment":
            if ch == "*" and nxt == "/":
                out.append("  ")
                i += 2
                state = "code"
            else:
                out.append("\n" if ch == "\n" else " ")
            i += 1
        else:
            if ch == "\\":
                out.append(ch)
                if i + 1 < n:
                    out.append(nxt)
                    i += 2
                else:
                    i += 1
                continue
            if ch == quote:
                out.append(ch)
                state = "code"
            else:
                out.append(ch)
            i += 1
    return "".join(out)


def extract_balanced_span(text: str, open_idx: int, open_ch: str = "(", close_ch: str = ")") -> tuple[str, int]:
    """Return contents inside matching delimiters and end index (after close_ch), or ('', open_idx)."""
    n = len(text)
    if open_idx >= n or text[open_idx] != open_ch:
        return "", open_idx
    depth = 0
    quote = ""
    i = open_idx
    while i < n:
        ch = text[i]
        if quote:
            if ch == "\\":
                i += 2
                continue
            if ch == quote:
                quote = ""
        else:
            if ch in ("'", '"', "`"):
                quote = ch
            elif ch == open_ch:
                depth += 1
            elif ch == close_ch:
                depth -= 1
                if depth == 0:
                    return text[open_idx + 1 : i], i + 1
        i += 1
    return "", open_idx


def split_top_level_args(inner: str) -> list[str]:
    """Split comma-separated call arguments without splitting inside nested (), {}, [], or strings."""
    args: list[str] = []
    buf: list[str] = []
    depth_paren = 0
    depth_brace = 0
    depth_bracket = 0
    quote = ""
    i = 0
    n = len(inner)
    while i < n:
        ch = inner[i]
        if quote:
            buf.append(ch)
            if ch == "\\":
                if i + 1 < n:
                    buf.append(inner[i + 1])
                    i += 2
                    continue
            elif ch == quote:
                quote = ""
        else:
            if ch in ("'", '"', "`"):
                quote = ch
                buf.append(ch)
            elif ch == "(":
                depth_paren += 1
                buf.append(ch)
            elif ch == ")":
                depth_paren = max(0, depth_paren - 1)
                buf.append(ch)
            elif ch == "{":
                depth_brace += 1
                buf.append(ch)
            elif ch == "}":
                depth_brace = max(0, depth_brace - 1)
                buf.append(ch)
            elif ch == "[":
                depth_bracket += 1
                buf.append(ch)
            elif ch == "]":
                depth_bracket = max(0, depth_bracket - 1)
                buf.append(ch)
            elif ch == "," and depth_paren == 0 and depth_brace == 0 and depth_bracket == 0:
                item = "".join(buf).strip()
                if item:
                    args.append(item)
                buf = []
                i += 1
                continue
            else:
                buf.append(ch)
        i += 1
    tail = "".join(buf).strip()
    if tail:
        args.append(tail)
    return args


# ---------------------------------------------------------------------------
# JS / TS / JSX / TSX Scanner
# ---------------------------------------------------------------------------

JS_USE_EFFECT_RE = re.compile(r"\buse(?:Layout)?Effect\s*\(")
JS_SET_INTERVAL_RE = re.compile(r"\b(?:window\.)?setInterval\s*\(")
JS_AI_CALL_RE = re.compile(
    r"(?:\b(?:chat\.completions|responses|messages|beta\.threads\.runs)\.create|"
    r"\bgenerateText|\bstreamText|\bgenerateObject|\bstreamObject|"
    r"\.generateContent(?:Stream)?)\s*\("
)
JS_PAID_SDK_RE = re.compile(
    r"(?:\b(?:chat\.completions|responses|messages|images)\.create|"
    r"\bgenerateText|\bstreamText|\bgenerateObject|\bstreamObject|"
    r"\.generateContent(?:Stream)?|\bembed(?:Many)?\b|"
    r"\bresend\.emails\.send\b|\bsgMail\.send\b|\btwilio[^\n;]{0,60}\.messages\.create\b|"
    r"\breplicate\.run\b)"
)
JS_DB_OP_RE = re.compile(
    r"(?:\bprisma\.\w+\.(?:findUnique|findFirst|findMany|count|aggregate|queryRaw)\b|"
    r"\bsupabase\.from\([^)]+\)\.(?:select|rpc)\b|"
    r"\b(?:db|pool|client)\.query\s*\()"
)
JS_UNBOUNDED_SCAN_RE = re.compile(
    r"(?:\bprisma\.(\w+)\.(findMany)\s*\(|\bsupabase\.from\([^)]+\)\.(select)\s*\()"
)
JS_LOOP_START_RE = re.compile(
    r"(?:\bfor\s*(?:await\s*)?\([^)]*\)\s*\{|"
    r"\.(?:map|forEach|flatMap)\s*\(\s*(?:async\s*)?(?:\([^)]*\)|[A-Za-z_$][\w$]*)\s*=>\s*\{)"
)
JS_PROMISE_ALL_MAP_RE = re.compile(r"\bPromise\.(?:all|allSettled)\s*\(\s*[A-Za-z_$][\w$.?]*\.map\s*\(")
JS_WHILE_TRUE_RE = re.compile(r"\bwhile\s*\(\s*true\s*\)\s*\{")
JS_FETCH_CALL_RE = re.compile(r"(?<![.\w$])\bfetch\s*\(")
JS_AXIOS_CALL_RE = re.compile(r"\baxios(?:\.(?:get|post|put|patch|delete|request))?\s*\(")
JS_DB_CLIENT_NEW_RE = re.compile(r"\bnew\s+(?:PrismaClient|Pool|Client)\s*\(|\bcreateClient\s*\(")
JS_ROUTE_HANDLER_RE = re.compile(
    r"(?:\bexport\s+(?:async\s+)?function\s+(?:GET|POST|PUT|PATCH|DELETE)\b|"
    r"\b(?:app|router)\.(?:get|post|put|patch|delete|all)\s*\()"
)
JS_MAX_DURATION_RE = re.compile(r"\bexport\s+const\s+maxDuration\s*=\s*(\d+)")
JS_MODULE_CACHE_RE = re.compile(
    r"^(?:const|let)\s+([A-Za-z_$][\w$]*)\s*(?::[^=]+)?=\s*(?:\{\s*\}|\[\s*\]|new\s+(?:Map|Set)\s*\(\s*\))",
    re.MULTILINE,
)

NET_CALL_SIGNAL_RE = re.compile(r"\b(fetch|axios|trpc|queryClient|mutate|invalidateQueries)\b|/api/")
TOKEN_CEIL_RE = re.compile(r"\b(max_tokens|maxOutputTokens|max_output_tokens|max_completion_tokens|maxTokens)\b")
DB_LIMIT_GUARD_RE = re.compile(
    r"\b(take|limit|range|single|maybeSingle|cursor|count|where\s*:\s*\{\s*(?:id|[a-zA-Z]+Id))\b"
)
TIMEOUT_OPT_RE = re.compile(r"\b(signal|timeout|AbortSignal)\b")


def is_server_route_js(rel_path: str, masked: str) -> bool:
    if SERVERLESS_HANDLER_FILE_RE.search(rel_path):
        return True
    return bool(JS_ROUTE_HANDLER_RE.search(masked))


def scan_js_ts_file(
    rel_path: str,
    raw_text: str,
    cfg: ScanConfig,
    is_test: bool,
    findings: list[Finding],
    metrics: MetricsCounter,
) -> None:
    if is_test:
        return

    raw_lines = raw_text.splitlines()
    masked = mask_js_comments(raw_text)
    server_route = is_server_route_js(rel_path, masked)

    # BILL001: useEffect calling network I/O without dependency array
    for m in JS_USE_EFFECT_RE.finditer(masked):
        open_idx = m.end() - 1
        inner, _ = extract_balanced_span(masked, open_idx, "(", ")")
        if not inner:
            continue
        args = split_top_level_args(inner)
        if len(args) == 1 and NET_CALL_SIGNAL_RE.search(args[0]):
            ln = line_number_at(masked, m.start())
            add_finding(
                findings,
                cfg,
                raw_lines,
                "BILL001",
                rel_path,
                ln,
                "`useEffect` performs network requests without a dependency array (infinite loop risk).",
            )

    # BILL002: Sub-second setInterval polling network calls
    for m in JS_SET_INTERVAL_RE.finditer(masked):
        inner, _ = extract_balanced_span(masked, m.end() - 1, "(", ")")
        if not inner:
            continue
        args = split_top_level_args(inner)
        if len(args) >= 2 and NET_CALL_SIGNAL_RE.search(args[0]):
            delay_m = re.fullmatch(r"\d+", args[1].strip())
            if delay_m and int(delay_m.group(0)) < 1000:
                ln = line_number_at(masked, m.start())
                add_finding(
                    findings,
                    cfg,
                    raw_lines,
                    "BILL002",
                    rel_path,
                    ln,
                    f"`setInterval(..., {delay_m.group(0)})` polls network endpoints below 1s.",
                )

    # BILL003: Uncapped LLM calls
    has_paid_sdk = bool(JS_PAID_SDK_RE.search(masked))
    for m in JS_AI_CALL_RE.finditer(masked):
        metrics.ai_calls += 1
        inner, _ = extract_balanced_span(masked, m.end() - 1, "(", ")")
        if inner and not TOKEN_CEIL_RE.search(inner) and "..." not in inner:
            ln = line_number_at(masked, m.start())
            add_finding(
                findings,
                cfg,
                raw_lines,
                "BILL003",
                rel_path,
                ln,
                "Generative AI call omits `max_tokens` / `maxOutputTokens` output ceiling.",
            )

    # BILL005: Public HTTP route invoking paid AI/email/SMS without auth or rate limit
    if (
        server_route
        and has_paid_sdk
        and not AUTH_GUARD_RE.search(masked)
        and not RATE_LIMIT_RE.search(masked)
    ):
        paid_m = JS_PAID_SDK_RE.search(masked)
        ln = line_number_at(masked, paid_m.start()) if paid_m else 1
        add_finding(
            findings,
            cfg,
            raw_lines,
            "BILL005",
            rel_path,
            ln,
            "HTTP route exposes paid AI/email/SMS SDK call without authentication or rate limiting.",
        )

    # Loop-scoped checks: BILL004 (paid SDK in loop), BILL006 (N+1 DB query in loop)
    for m in JS_LOOP_START_RE.finditer(masked):
        header = m.group(0)
        brace_idx = masked.find("{", m.start())
        if brace_idx == -1:
            continue
        body, _ = extract_balanced_span(masked, brace_idx, "{", "}")
        if not body:
            continue
        # Skip small bounded retry loops `for (let i = 0; i < 3; i++)`
        retry_m = re.search(r"<\s*(\d+)", header)
        if retry_m and int(retry_m.group(1)) <= 5:
            continue
        ctx_before = masked[max(0, m.start() - 120) : m.start()]
        if BOUND_GUARD_RE.search(ctx_before) or BOUND_GUARD_RE.search(body):
            continue
        ln = line_number_at(masked, m.start())
        if JS_PAID_SDK_RE.search(body):
            add_finding(
                findings,
                cfg,
                raw_lines,
                "BILL004",
                rel_path,
                ln,
                "Paid AI/email/SMS API invoked inside unbounded loop without batch slice or concurrency cap.",
            )
        elif JS_DB_OP_RE.search(body):
            add_finding(
                findings,
                cfg,
                raw_lines,
                "BILL006",
                rel_path,
                ln,
                "N+1 database query executed inside loop; batch with `IN (...)` or a single query.",
            )

    # BILL007: Unbounded DB table scan inside server routes
    for m in JS_UNBOUNDED_SCAN_RE.finditer(masked):
        metrics.db_ops += 1
        if not server_route:
            continue
        inner, end_idx = extract_balanced_span(masked, m.end() - 1, "(", ")")
        tail_chain = masked[end_idx : end_idx + 120]
        if not DB_LIMIT_GUARD_RE.search(inner) and not DB_LIMIT_GUARD_RE.search(tail_chain):
            ln = line_number_at(masked, m.start())
            add_finding(
                findings,
                cfg,
                raw_lines,
                "BILL007",
                rel_path,
                ln,
                "Unbounded ORM query (`findMany` / `select`) inside HTTP handler without `take` / `limit`.",
            )

    # BILL008: Unbounded Promise.all(items.map(...))
    for m in JS_PROMISE_ALL_MAP_RE.finditer(masked):
        inner, _ = extract_balanced_span(masked, m.start() + masked[m.start() :].find("("), "(", ")")
        if not inner:
            continue
        ctx_before = masked[max(0, m.start() - 160) : m.start()]
        if BOUND_GUARD_RE.search(ctx_before) or BOUND_GUARD_RE.search(inner):
            continue
        if NET_CALL_SIGNAL_RE.search(inner) or JS_PAID_SDK_RE.search(inner) or JS_DB_OP_RE.search(inner):
            ln = line_number_at(masked, m.start())
            add_finding(
                findings,
                cfg,
                raw_lines,
                "BILL008",
                rel_path,
                ln,
                "Unbounded `Promise.all(items.map(...))` fires parallel network/DB calls without concurrency cap.",
            )

    # BILL009: Infinite while (true) loop
    for m in JS_WHILE_TRUE_RE.finditer(masked):
        brace_idx = masked.find("{", m.start())
        body, _ = extract_balanced_span(masked, brace_idx, "{", "}")
        if (
            body
            and (NET_CALL_SIGNAL_RE.search(body) or JS_PAID_SDK_RE.search(body) or JS_DB_OP_RE.search(body))
            and not RETRY_COUNTER_RE.search(body)
        ):
            ln = line_number_at(masked, m.start())
            add_finding(
                findings,
                cfg,
                raw_lines,
                "BILL009",
                rel_path,
                ln,
                "Unbounded `while (true)` executes external calls without max-attempt or shutdown bound.",
            )

    # BILL010 & BILL011: Server-side fetch/axios missing timeout + excessive maxDuration
    if server_route or Path(rel_path).suffix.lower() in {".ts", ".js", ".mjs", ".cjs"}:
        is_ui_component = "/components/" in rel_path.lower() or rel_path.lower().endswith((".tsx", ".jsx", ".vue", ".svelte"))
        for m in JS_FETCH_CALL_RE.finditer(masked):
            inner, _ = extract_balanced_span(masked, m.end() - 1, "(", ")")
            if not inner:
                continue
            args = split_top_level_args(inner)
            url_arg = args[0] if args else ""
            # Ignore client UI relative /api calls
            if is_ui_component and re.search(r"""^['"`]/""", url_arg.strip()):
                continue
            if re.search(r"""^['"`]/api/""", url_arg.strip()):
                continue
            metrics.outbound_http += 1
            opts_arg = args[1] if len(args) >= 2 else ""
            if (not opts_arg or not TIMEOUT_OPT_RE.search(opts_arg)) and (server_route or "http" in url_arg):
                ln = line_number_at(masked, m.start())
                add_finding(
                    findings,
                    cfg,
                    raw_lines,
                    "BILL010",
                    rel_path,
                    ln,
                    "Server-side `fetch()` omits `signal: AbortSignal.timeout(...)` timeout.",
                )

    dur_m = JS_MAX_DURATION_RE.search(masked)
    if (
        dur_m
        and int(dur_m.group(1)) >= 60
        and has_paid_sdk
        and not RATE_LIMIT_RE.search(masked)
        and not TIMEOUT_OPT_RE.search(masked)
    ):
        ln = line_number_at(masked, dur_m.start())
        add_finding(
            findings,
            cfg,
            raw_lines,
            "BILL011",
            rel_path,
            ln,
            f"Extended `maxDuration = {dur_m.group(1)}` pairs with uncapped paid SDK call and no timeout/rate-limit.",
        )

    # BILL012: DB/pool client instantiated inside route handler without singleton cache
    if server_route:
        for m in JS_DB_CLIENT_NEW_RE.finditer(masked):
            ln = line_number_at(masked, m.start())
            if "globalThis" not in masked and "global." not in masked:
                add_finding(
                    findings,
                    cfg,
                    raw_lines,
                    "BILL012",
                    rel_path,
                    ln,
                    "Database client/pool constructed in route module without `globalThis` singleton reuse.",
                )

    # BILL013: Unbounded module-level Map/Set/array/cache mutated in route handlers
    if server_route:
        for m in JS_MODULE_CACHE_RE.finditer(masked):
            ident = m.group(1)
            mut_re = re.compile(rf"\b{re.escape(ident)}\s*(?:\.push\(|\.set\(|\.add\(|\[[^]]+\]\s*=)")
            if mut_re.search(masked) and not EVICTION_GUARD_RE.search(masked):
                ln = line_number_at(masked, m.start())
                add_finding(
                    findings,
                    cfg,
                    raw_lines,
                    "BILL013",
                    rel_path,
                    ln,
                    f"Module-level collection `{ident}` grows in handlers without max-size or TTL eviction.",
                )


# ---------------------------------------------------------------------------
# Python AST Scanner
# ---------------------------------------------------------------------------

PY_AI_CALL_NAMES = {
    "completions.create",
    "responses.create",
    "messages.create",
    "generate_content",
    "generate_content_async",
    "litellm.completion",
    "litellm.acompletion",
}

PY_PAID_KEYWORDS = (
    "completions.create",
    "responses.create",
    "messages.create",
    "generate_content",
    "litellm.completion",
    "emails.send",
    "sendgrid",
    "twilio",
    "replicate.run",
)

PY_HTTP_NO_TIMEOUT_NAMES = {
    "requests.get",
    "requests.post",
    "requests.put",
    "requests.patch",
    "requests.delete",
    "requests.request",
    "httpx.get",
    "httpx.post",
    "httpx.put",
    "httpx.patch",
    "httpx.delete",
    "httpx.request",
    "urllib.request.urlopen",
}

PY_DB_METHODS = {"execute", "scalars", "get", "query", "all", "fetchall", "first", "one"}
PY_UNBOUNDED_SCAN_PATTERNS = (".objects.all", "SELECT * FROM")


def _unparse_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = _unparse_name(node.value)
        return f"{prefix}.{node.attr}" if prefix else node.attr
    return ""


def _call_has_kw(node: ast.Call, names: set[str]) -> bool:
    for kw in node.keywords:
        if kw.arg is None:
            return True  # **kwargs spread passed dynamically
        if kw.arg in names:
            return True
    return False


def _is_small_constant_loop(node: ast.For | ast.AsyncFor) -> bool:
    it = node.iter
    if (
        isinstance(it, ast.Call)
        and _unparse_name(it.func) == "range"
        and len(it.args) == 1
        and isinstance(it.args[0], ast.Constant)
        and isinstance(it.args[0].value, int)
        and it.args[0].value <= 5
    ):
        return True
    if isinstance(it, (ast.List, ast.Tuple)) and len(it.elts) <= 5:
        return True
    return isinstance(it, ast.Subscript) and isinstance(it.slice, ast.Slice) and it.slice.upper is not None


def _is_route_decorated(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    for dec in fn.decorator_list:
        name = _unparse_name(dec.func) if isinstance(dec, ast.Call) else _unparse_name(dec)
        if any(name.endswith(sfx) for sfx in (".get", ".post", ".put", ".patch", ".delete", ".route", ".api_route")):
            return True
    return False


def _fn_uses_auth_dependency(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    src = ast.unparse(fn) if hasattr(ast, "unparse") else ""
    return bool(AUTH_GUARD_RE.search(src) or RATE_LIMIT_RE.search(src))


def scan_python_file(
    rel_path: str,
    raw_text: str,
    cfg: ScanConfig,
    is_test: bool,
    findings: list[Finding],
    metrics: MetricsCounter,
) -> None:
    if is_test:
        return

    raw_lines = raw_text.splitlines()
    try:
        tree = ast.parse(raw_text, filename=rel_path)
    except SyntaxError:
        return

    has_route_file = bool(
        SERVERLESS_HANDLER_FILE_RE.search(rel_path)
        or any(
            isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and _is_route_decorated(n)
            for n in ast.walk(tree)
        )
    )

    # Track module-level mutable collections for BILL013
    module_collections: dict[str, int] = {}
    for top in tree.body:
        target_name: str | None = None
        val_node: ast.expr | None = None
        if isinstance(top, ast.Assign) and len(top.targets) == 1 and isinstance(top.targets[0], ast.Name):
            target_name = top.targets[0].id
            val_node = top.value
        elif isinstance(top, ast.AnnAssign) and isinstance(top.target, ast.Name):
            target_name = top.target.id
            val_node = top.value
        if target_name is not None and val_node is not None and (
            (isinstance(val_node, ast.Dict) and len(val_node.keys) == 0)
            or (isinstance(val_node, (ast.List, ast.Set)) and len(val_node.elts) == 0)
        ):
            module_collections[target_name] = top.lineno

    # Walk calls globally for BILL003 (uncapped AI) & BILL010 (HTTP missing timeout)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fn_name = _unparse_name(node.func)
        if any(fn_name.endswith(sfx) for sfx in PY_AI_CALL_NAMES):
            metrics.ai_calls += 1
            if not _call_has_kw(node, {"max_tokens", "max_output_tokens", "max_completion_tokens", "generation_config"}):
                add_finding(
                    findings,
                    cfg,
                    raw_lines,
                    "BILL003",
                    rel_path,
                    node.lineno,
                    f"AI call `{fn_name}` omits `max_tokens` / `max_output_tokens` ceiling.",
                )
        elif fn_name in PY_HTTP_NO_TIMEOUT_NAMES:
            metrics.outbound_http += 1
            if not _call_has_kw(node, {"timeout"}):
                add_finding(
                    findings,
                    cfg,
                    raw_lines,
                    "BILL010",
                    rel_path,
                    node.lineno,
                    f"HTTP call `{fn_name}` omits explicit `timeout=` parameter.",
                )

    # Loop checks: BILL004 (AI/paid API in loop), BILL006 (N+1 DB query), BILL009 (while True)
    for node in ast.walk(tree):
        if isinstance(node, (ast.For, ast.AsyncFor)):
            if _is_small_constant_loop(node):
                continue
            loop_src = ast.get_source_segment(raw_text, node) or ""
            if BOUND_GUARD_RE.search(loop_src):
                continue
            for sub in ast.walk(node):
                if isinstance(sub, ast.Call):
                    sub_name = _unparse_name(sub.func)
                    if any(k in sub_name for k in PY_PAID_KEYWORDS):
                        add_finding(
                            findings,
                            cfg,
                            raw_lines,
                            "BILL004",
                            rel_path,
                            sub.lineno,
                            f"Paid SDK call `{sub_name}` invoked inside unbounded loop.",
                        )
                        break
                    if (
                        sub_name.split(".")[-1] in PY_DB_METHODS
                        and any(tok in sub_name.lower() for tok in ("session", "db", "cursor", "conn", "objects", "prisma", "supabase"))
                    ):
                        metrics.db_ops += 1
                        add_finding(
                            findings,
                            cfg,
                            raw_lines,
                            "BILL006",
                            rel_path,
                            sub.lineno,
                            f"N+1 DB query `{sub_name}` invoked inside loop.",
                        )
                        break

        elif (
            isinstance(node, ast.While)
            and isinstance(node.test, ast.Constant)
            and node.test.value is True
        ):
            while_src = ast.get_source_segment(raw_text, node) or ""
            has_ext = any(
                isinstance(sub, ast.Call)
                and (
                    any(k in _unparse_name(sub.func) for k in PY_PAID_KEYWORDS)
                    or _unparse_name(sub.func) in PY_HTTP_NO_TIMEOUT_NAMES
                    or _unparse_name(sub.func).split(".")[-1] in PY_DB_METHODS
                )
                for sub in ast.walk(node)
            )
            if has_ext and not RETRY_COUNTER_RE.search(while_src):
                add_finding(
                    findings,
                    cfg,
                    raw_lines,
                    "BILL009",
                    rel_path,
                    node.lineno,
                    "Unbounded `while True:` executes external calls without max-retry or shutdown guard.",
                )

    # Function-level checks: BILL005 (public paid route), BILL007 (unbounded scan), BILL012 (pool in handler), BILL013 (cache mutation)
    for fn in ast.walk(tree):
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        is_endpoint = _is_route_decorated(fn)
        fn_src = ast.get_source_segment(raw_text, fn) or ""
        calls = [n for n in ast.walk(fn) if isinstance(n, ast.Call)]

        if is_endpoint and not _fn_uses_auth_dependency(fn) and not AUTH_GUARD_RE.search(raw_text) and not RATE_LIMIT_RE.search(raw_text):
            for c in calls:
                cname = _unparse_name(c.func)
                if any(k in cname for k in PY_PAID_KEYWORDS):
                    add_finding(
                        findings,
                        cfg,
                        raw_lines,
                        "BILL005",
                        rel_path,
                        c.lineno,
                        f"Endpoint `{fn.name}` exposes paid API `{cname}` without auth or rate limiting.",
                    )
                    break

        if (is_endpoint or has_route_file) and any(p in fn_src for p in PY_UNBOUNDED_SCAN_PATTERNS) and not re.search(
            r"\b(?:limit|LIMIT|paginate|page_size)\b|\[:\s*\d+\]", fn_src
        ):
            add_finding(
                findings,
                cfg,
                raw_lines,
                "BILL007",
                rel_path,
                fn.lineno,
                f"Endpoint `{fn.name}` executes unbounded query without `LIMIT` or slice.",
            )

        if is_endpoint:
            for c in calls:
                cname = _unparse_name(c.func)
                if cname in {"create_engine", "sqlalchemy.create_engine", "psycopg2.connect", "sqlite3.connect"} and "lru_cache" not in raw_text:
                    add_finding(
                        findings,
                        cfg,
                        raw_lines,
                        "BILL012",
                        rel_path,
                        c.lineno,
                        f"Database client/engine `{cname}` created inside endpoint `{fn.name}` instead of module singleton.",
                    )

        if (is_endpoint or has_route_file) and module_collections and not EVICTION_GUARD_RE.search(raw_text):
            for col_name, col_ln in module_collections.items():
                if re.search(rf"\b{re.escape(col_name)}\s*(?:\.append\(|\.add\(|\[[^]]+\]\s*=)", fn_src):
                    add_finding(
                        findings,
                        cfg,
                        raw_lines,
                        "BILL013",
                        rel_path,
                        col_ln,
                        f"Module-level collection `{col_name}` grows inside handlers without eviction/maxsize.",
                    )


# ---------------------------------------------------------------------------
# Cloud / Workflow Config Scanner (BILL014)
# ---------------------------------------------------------------------------

CRON_RE = re.compile(r"""['"]?\s*([*/0-9,-]+)\s+([*/0-9,-]+)\s+([*/0-9,-]+)\s+([*/0-9,-]+)\s+([*/0-9,-]+)['"]?""")


def is_aggressive_cron(expr: str) -> bool:
    parts = expr.strip().split()
    if len(parts) != 5:
        return False
    minute = parts[0]
    if minute == "*":
        return True
    m_step = re.fullmatch(r"\*/(\d+)", minute)
    return bool(m_step and int(m_step.group(1)) < 5)


def scan_infra_configs(
    root: Path,
    cfg: ScanConfig,
    findings: list[Finding],
    metrics: MetricsCounter,
) -> None:
    vercel_json = root / "vercel.json"
    if vercel_json.is_file() and not is_excluded("vercel.json", cfg):
        txt = vercel_json.read_text(encoding="utf-8", errors="ignore")
        raw_lines = txt.splitlines()
        try:
            data = json.loads(txt)
        except json.JSONDecodeError:
            data = {}
        if isinstance(data, dict):
            for cron in list(data.get("crons") or []) + list(data.get("schedules") or []):
                if not isinstance(cron, dict):
                    continue
                sched = str(cron.get("schedule", ""))
                metrics.cron_jobs += 1
                if is_aggressive_cron(sched):
                    ln = next((i + 1 for i, line_s in enumerate(raw_lines) if sched in line_s), 1)
                    add_finding(
                        findings,
                        cfg,
                        raw_lines,
                        "BILL014",
                        "vercel.json",
                        ln,
                        f"Sub-5-minute cron schedule `{sched}` runs continuously in production.",
                    )
            funcs = data.get("functions")
            if isinstance(funcs, dict):
                for fn_pat, fn_cfg in funcs.items():
                    if isinstance(fn_cfg, dict) and isinstance(fn_cfg.get("maxDuration"), int) and fn_cfg["maxDuration"] > 300:
                        ln = next((i + 1 for i, line_s in enumerate(raw_lines) if str(fn_pat) in line_s), 1)
                        add_finding(
                            findings,
                            cfg,
                            raw_lines,
                            "BILL014",
                            "vercel.json",
                            ln,
                            f"Function config `{fn_pat}` allocates excessive `maxDuration: {fn_cfg['maxDuration']}`.",
                        )

    wf_dir = root / ".github" / "workflows"
    if wf_dir.is_dir():
        for wf in sorted(wf_dir.glob("*.y*ml")):
            rel = wf.relative_to(root).as_posix()
            if is_excluded(rel, cfg):
                continue
            txt = wf.read_text(encoding="utf-8", errors="ignore")
            raw_lines = txt.splitlines()
            for ln, line in enumerate(raw_lines, 1):
                if "cron:" in line:
                    m = CRON_RE.search(line.split("cron:", 1)[1])
                    if m:
                        expr = " ".join(m.groups())
                        metrics.cron_jobs += 1
                        if is_aggressive_cron(expr):
                            add_finding(
                                findings,
                                cfg,
                                raw_lines,
                                "BILL014",
                                rel,
                                ln,
                                f"Workflow cron `{expr}` executes every <5 minutes on GitHub Actions.",
                            )


# ---------------------------------------------------------------------------
# Git Diff Cost-Regression Guard (BILL015, BILL016)
# ---------------------------------------------------------------------------

DIFF_GUARD_RE = re.compile(
    r"\b("
    r"ratelimit|Ratelimit|rate_limit|rateLimiter|SlowAPI|"
    r"max_tokens|maxOutputTokens|max_output_tokens|max_completion_tokens|"
    r"AbortSignal\.timeout|timeout=|take:|LIMIT\b"
    r")"
)
DIFF_CRON_MIN_RE = re.compile(r"""(?:cron|schedule)["']?\s*:\s*["'](\*(?:/[1-4])?(?:\s+\*){4})["']""")


def scan_git_diff(
    root: Path,
    diff_ref: str | None,
    staged: bool,
    cfg: ScanConfig,
    findings: list[Finding],
) -> dict[str, Any]:
    in_repo = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "--is-inside-work-tree"],
        text=True,
        capture_output=True,
    )
    if in_repo.returncode != 0:
        return {"ran": False, "error": "not inside a git repository"}

    cmd = ["git", "-C", str(root), "diff", "--unified=0", "--no-color"]
    if staged:
        cmd.append("--staged")
    elif diff_ref:
        cmd.append(diff_ref)
    else:
        cmd.append("HEAD")

    proc = subprocess.run(cmd, text=True, capture_output=True)
    if proc.returncode != 0:
        return {"ran": False, "error": proc.stderr.strip()}

    cur_file = ""
    cur_line = 0
    in_hunk = False
    removed_guards: dict[str, list[tuple[int, str]]] = defaultdict(list)
    added_guards: dict[str, int] = defaultdict(int)

    for line in proc.stdout.splitlines():
        if line.startswith("+++ b/"):
            cur_file = line[6:]
            cur_line = 0
            in_hunk = False
        elif line.startswith("@@ "):
            m = re.search(r"\+(\d+)", line)
            cur_line = int(m.group(1)) if m else 1
            in_hunk = True
        elif in_hunk and cur_file:
            if cur_file.lower().endswith((".md", ".rst", ".txt")) or cur_file == "skills/billshock/scripts/billshock.py":
                if line.startswith("+") and not line.startswith("+++"):
                    cur_line += 1
                continue
            if is_test_or_fixture_path(cur_file):
                if line.startswith("+") and not line.startswith("+++"):
                    cur_line += 1
                continue
            if line.startswith("+") and not line.startswith("+++"):
                content = line[1:]
                if "billshock-ignore" not in content:
                    if DIFF_GUARD_RE.search(content):
                        added_guards[cur_file] += 1
                    m_cron = DIFF_CRON_MIN_RE.search(content)
                    if m_cron:
                        add_finding(
                            findings,
                            cfg,
                            [""],
                            "BILL016",
                            cur_file,
                            max(1, cur_line),
                            f"Diff introduces aggressive cron `{m_cron.group(1)}` triggering high cloud volume.",
                            snippet=content.strip(),
                        )
                cur_line += 1
            elif line.startswith("-") and not line.startswith("---"):
                content = line[1:]
                m_rm = DIFF_GUARD_RE.search(content)
                if m_rm:
                    removed_guards[cur_file].append((max(1, cur_line), content.strip()))

    for path_key, rms in removed_guards.items():
        if len(rms) > added_guards.get(path_key, 0):
            first_ln, first_snip = rms[0]
            add_finding(
                findings,
                cfg,
                [""],
                "BILL015",
                path_key,
                first_ln,
                f"Removed {len(rms)} cost/rate guardrail(s) (only {added_guards.get(path_key, 0)} added back).",
                snippet=first_snip,
            )

    return {"ran": True, "ref": "--staged" if staged else (diff_ref or "HEAD")}


# ---------------------------------------------------------------------------
# Baseline, Reporting & CLI
# ---------------------------------------------------------------------------


def load_baseline(path: Path | None) -> set[str]:
    if path is None or not path.is_file():
        return set()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict) and isinstance(data.get("fingerprints"), list):
            return {str(x) for x in data["fingerprints"]}
        if isinstance(data, list):
            return {str(x) for x in data}
    except Exception:
        return set()
    return set()


def save_baseline(path: Path, findings: list[Finding]) -> None:
    payload = {
        "tool": "billshock",
        "version": VERSION,
        "count": len(findings),
        "fingerprints": sorted({f.fingerprint for f in findings}),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def build_report(
    target: Path,
    findings: list[Finding],
    files_scanned: int,
    metrics: MetricsCounter,
    diff_summary: dict[str, Any] | None,
) -> dict[str, Any]:
    deduped: list[Finding] = []
    seen_fp: set[str] = set()
    for f in findings:
        if f.fingerprint not in seen_fp:
            seen_fp.add(f.fingerprint)
            deduped.append(f)

    deduped.sort(key=lambda x: (-SEVERITY_ORDER.get(x.severity, 0), x.file, x.line, x.rule_id))

    counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    pillar_counts: dict[str, int] = defaultdict(int)
    penalty = 0
    for f in deduped:
        counts[f.severity] = counts.get(f.severity, 0) + 1
        pillar_counts[f.pillar] += 1
        penalty += SEVERITY_PENALTY.get(f.severity, 2)

    score = max(0, 100 - penalty)
    if counts["critical"] > 0 and score >= 90:
        score = 89
    grade = "SAFE" if (score >= 90 and counts["critical"] == 0) else ("CAUTION" if score >= 70 else "BILL SHOCK ALERT")

    return {
        "tool": "billshock",
        "version": VERSION,
        "target": str(target),
        "score": score,
        "grade": grade,
        "files_scanned": files_scanned,
        "counts": counts,
        "pillars": dict(sorted(pillar_counts.items())),
        "surfaces": {
            "ai_calls": metrics.ai_calls,
            "db_ops": metrics.db_ops,
            "outbound_http": metrics.outbound_http,
            "cron_jobs": metrics.cron_jobs,
        },
        "diff_audit": diff_summary,
        "findings": [asdict(f) for f in deduped],
    }


def format_text(report: dict[str, Any], use_color: bool) -> str:
    c_reset = "\033[0m" if use_color else ""
    c_red = "\033[31m" if use_color else ""
    c_yel = "\033[33m" if use_color else ""
    c_grn = "\033[32m" if use_color else ""
    c_dim = "\033[2m" if use_color else ""

    grade = report["grade"]
    gcol = c_grn if grade == "SAFE" else (c_yel if grade == "CAUTION" else c_red)
    surf = report["surfaces"]
    cnt = report["counts"]

    lines = [
        f"BillShock v{report['version']} — Spend-Safety & Runaway-Cost Report",
        (
            f"Target: {report['target']} | Files scanned: {report['files_scanned']} | "
            f"AI calls: {surf['ai_calls']} | DB ops: {surf['db_ops']} | "
            f"HTTP: {surf['outbound_http']} | Crons: {surf['cron_jobs']}"
        ),
        (
            f"Score:  {gcol}{report['score']}/100 ({grade}){c_reset}  "
            f"[critical={cnt['critical']} high={cnt['high']} medium={cnt['medium']} low={cnt['low']}]"
        ),
        "",
    ]

    if not report["findings"]:
        lines.append(f"{c_grn}No runaway loops, uncapped AI calls, unbounded scans, or cost regressions detected.{c_reset}")
        return "\n".join(lines)

    for f in report["findings"]:
        sev = f["severity"].upper()
        scol = c_red if sev in {"CRITICAL", "HIGH"} else c_yel
        lines.append(f"{scol}[{sev:<8}]{c_reset} {f['rule_id']} {f['file']}:{f['line']} — {f['message']}")
        if f["snippet"]:
            lines.append(f"    {c_dim}code: {f['snippet']}{c_reset}")
        lines.append(f"    fix:  {f['help']}")
    return "\n".join(lines)


def format_markdown(report: dict[str, Any]) -> str:
    cnt = report["counts"]
    surf = report["surfaces"]
    lines = [
        f"## BillShock Spend-Safety Audit — **{report['score']}/100 ({report['grade']})**",
        "",
        f"- **Files scanned:** {report['files_scanned']}",
        f"- **Cost surfaces:** {surf['ai_calls']} AI calls, {surf['db_ops']} DB ops, {surf['outbound_http']} outbound HTTP, {surf['cron_jobs']} cron jobs",
        f"- **Findings:** {cnt['critical']} critical, {cnt['high']} high, {cnt['medium']} medium, {cnt['low']} low",
        "",
    ]
    if not report["findings"]:
        lines.append("All inspected runtime paths passed without runaway loops, uncapped AI calls, or unbounded scans.")
        return "\n".join(lines)

    lines.extend([
        "| Severity | Rule | Location | Finding |",
        "| :--- | :--- | :--- | :--- |",
    ])
    for f in report["findings"]:
        loc = f"`{f['file']}:{f['line']}`"
        msg = f["message"].replace("|", "\\|")
        lines.append(f"| `{f['severity'].upper()}` | `{f['rule_id']}` | {loc} | {msg} |")
    return "\n".join(lines)


def format_sarif(report: dict[str, Any]) -> str:
    rules_arr = [
        {
            "id": rid,
            "shortDescription": {"text": meta["title"]},
            "help": {"text": meta["help"]},
            "properties": {"pillar": meta["pillar"], "severity": meta["severity"]},
        }
        for rid, meta in RULE_META.items()
    ]
    sev_to_level = {"critical": "error", "high": "error", "medium": "warning", "low": "note"}
    results = [
        {
            "ruleId": f["rule_id"],
            "level": sev_to_level.get(f["severity"], "warning"),
            "message": {"text": f["message"]},
            "locations": [
                {
                    "physicalLocation": {
                        "artifactLocation": {"uri": f["file"]},
                        "region": {"startLine": max(1, int(f["line"]))},
                    }
                }
            ],
            "partialFingerprints": {"billshockFingerprint/v1": f["fingerprint"]},
        }
        for f in report["findings"]
    ]
    sarif = {
        "$schema": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "BillShock",
                        "version": VERSION,
                        "informationUri": "https://github.com/codesphere-u/billshock",
                        "rules": rules_arr,
                    }
                },
                "results": results,
            }
        ],
    }
    return json.dumps(sarif, indent=2)


def run_scan(
    target: Path,
    *,
    diff_ref: str | None = None,
    with_diff: bool = False,
    staged: bool = False,
    ignore_rules: Iterable[str] = (),
    baseline_path: Path | None = None,
) -> dict[str, Any]:
    root = target.resolve()
    cfg = load_config(root)
    cfg.ignore_rules.update(r.upper() for r in ignore_rules)

    findings: list[Finding] = []
    metrics = MetricsCounter()
    files_scanned = 0

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in EXCLUDED_DIRS)
        for fname in sorted(filenames):
            if fname.lower().endswith(SKIP_FILE_SUFFIXES):
                continue
            fpath = Path(dirpath) / fname
            if fpath.suffix.lower() not in CODE_EXTENSIONS:
                continue
            try:
                if fpath.stat().st_size > MAX_FILE_BYTES:
                    continue
            except OSError:
                continue
            rel_path = fpath.relative_to(root).as_posix()
            if is_excluded(rel_path, cfg):
                continue
            if rel_path == "skills/billshock/scripts/billshock.py":
                continue
            try:
                raw_text = fpath.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue

            files_scanned += 1
            test_flag = is_test_or_fixture_path(rel_path)

            if fpath.suffix.lower() in PY_EXTENSIONS:
                scan_python_file(rel_path, raw_text, cfg, test_flag, findings, metrics)
            else:
                scan_js_ts_file(rel_path, raw_text, cfg, test_flag, findings, metrics)

    scan_infra_configs(root, cfg, findings, metrics)

    diff_summary = None
    if with_diff or staged or diff_ref is not None:
        diff_summary = scan_git_diff(root, diff_ref, staged, cfg, findings)

    if baseline_path is not None:
        known = load_baseline(baseline_path)
        if known:
            findings = [f for f in findings if f.fingerprint not in known]

    return build_report(root, findings, files_scanned, metrics, diff_summary)


def should_fail(findings: list[dict[str, Any]], score: int, fail_on: str, min_score: int | None) -> bool:
    if min_score is not None and score < min_score:
        return True
    if fail_on == "none":
        return False
    threshold = 1 if fail_on == "any" else SEVERITY_ORDER[fail_on]
    return any(SEVERITY_ORDER.get(f["severity"], 0) >= threshold for f in findings)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="billshock",
        description="Expose runaway loops, uncapped AI token bombs, N+1 DB egress & cost regressions.",
    )
    p.add_argument("target", nargs="?", default=".", help="Repository directory to scan (default: .)")
    p.add_argument("--format", choices=["text", "markdown", "json", "sarif"], default="text")
    p.add_argument("--diff", nargs="?", const="", default=None, metavar="REF", help="Also audit git diff (default: HEAD)")
    p.add_argument("--staged", action="store_true", help="Audit staged git diff")
    p.add_argument(
        "--fail-on",
        choices=["critical", "high", "medium", "low", "any", "none"],
        default="high",
        help="Minimum severity triggering exit code 1 (default: high)",
    )
    p.add_argument("--min-score", type=int, default=None, help="Fail if score drops below this threshold (0-100)")
    p.add_argument("--ignore-rule", action="append", default=[], help="Ignore specific rule ID (repeatable)")
    p.add_argument("--baseline", type=Path, default=None, help="Suppress findings matching baseline JSON fingerprints")
    p.add_argument("--write-baseline", type=Path, default=None, help="Write current findings baseline JSON and exit 0")
    p.add_argument("--output", type=Path, default=None, help="Write report output to file as well as stdout")
    p.add_argument("--no-color", action="store_true", help="Disable ANSI color in text output")
    p.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    target = Path(args.target)
    if not target.is_dir():
        print(f"billshock: target directory does not exist: {target}", file=sys.stderr)
        return 2
    if args.min_score is not None and not 0 <= args.min_score <= 100:
        print(f"billshock: --min-score must be between 0 and 100, got {args.min_score}", file=sys.stderr)
        return 2

    report = run_scan(
        target,
        diff_ref=args.diff or None,
        with_diff=args.diff is not None,
        staged=args.staged,
        ignore_rules=args.ignore_rule,
        baseline_path=args.baseline,
    )

    diff_info = report.get("diff_audit")
    if isinstance(diff_info, dict) and diff_info.get("ran") is False and diff_info.get("error"):
        print(f"billshock: warning: git diff audit skipped ({diff_info['error']})", file=sys.stderr)

    if args.write_baseline is not None:
        reconstructed = [Finding(**f) for f in report["findings"]]
        save_baseline(args.write_baseline, reconstructed)
        print(f"Wrote baseline with {len(reconstructed)} fingerprints to {args.write_baseline}")
        return 0

    if args.format == "json":
        rendered = json.dumps(report, indent=2)
    elif args.format == "markdown":
        rendered = format_markdown(report)
    elif args.format == "sarif":
        rendered = format_sarif(report)
    else:
        use_color = not args.no_color and sys.stdout.isatty() and os.environ.get("NO_COLOR") is None
        rendered = format_text(report, use_color=use_color)

    print(rendered)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")

    return 1 if should_fail(report["findings"], report["score"], args.fail_on, args.min_score) else 0


if __name__ == "__main__":
    raise SystemExit(main())
