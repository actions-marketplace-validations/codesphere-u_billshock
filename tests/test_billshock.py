from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "skills" / "billshock" / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import billshock  # noqa: E402

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
CLEAN_APP = FIXTURES_DIR / "clean_app"
RUNAWAY_APP = FIXTURES_DIR / "runaway_app"


def _init_git_repo(root: Path) -> None:
    subprocess.run(["git", "init", "-b", "main"], cwd=root, check=True, capture_output=True, text=True)
    subprocess.run(["git", "config", "user.email", "dev@example.com"], cwd=root, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Dev"], cwd=root, check=True, capture_output=True)


def test_clean_app_scores_perfect_100() -> None:
    report = billshock.run_scan(CLEAN_APP)
    assert report["tool"] == "billshock"
    assert report["score"] == 100
    assert report["grade"] == "SAFE"
    assert report["findings"] == []
    assert report["counts"] == {"critical": 0, "high": 0, "medium": 0, "low": 0}
    assert report["surfaces"]["ai_calls"] >= 1
    assert report["surfaces"]["db_ops"] >= 1
    assert report["surfaces"]["cron_jobs"] >= 2

    rc = billshock.main([str(CLEAN_APP), "--fail-on", "any", "--min-score", "100", "--no-color"])
    assert rc == 0


def test_runaway_app_triggers_all_static_rules() -> None:
    report = billshock.run_scan(RUNAWAY_APP)
    found_rules = {f["rule_id"] for f in report["findings"]}
    expected_rules = {f"BILL{idx:03d}" for idx in range(1, 15)}
    missing = expected_rules - found_rules
    assert not missing, f"Missing expected rules: {sorted(missing)}"
    assert report["grade"] == "BILL SHOCK ALERT"
    assert report["score"] == 0
    assert report["counts"]["critical"] >= 1
    assert report["counts"]["high"] >= 1

    rc = billshock.main([str(RUNAWAY_APP), "--fail-on", "high", "--no-color"])
    assert rc == 1


def test_python_n_plus_one_loop_detected(tmp_path: Path) -> None:
    py_file = tmp_path / "service.py"
    py_file.write_text(
        "def hydrate_users(user_ids, session):\n"
        "    out = []\n"
        "    for uid in user_ids:\n"
        "        out.append(session.execute('SELECT id FROM users WHERE id = :id', {'id': uid}))\n"
        "    return out\n",
        encoding="utf-8",
    )
    report = billshock.run_scan(tmp_path)
    rules = {f["rule_id"] for f in report["findings"]}
    assert "BILL006" in rules


def test_false_positive_guards_hold(tmp_path: Path) -> None:
    (tmp_path / "ui.tsx").write_text(
        "import { useEffect, useRef } from 'react';\n"
        "export function Panel() {\n"
        "  const ref = useRef<HTMLDivElement>(null);\n"
        "  useEffect(() => {\n"
        "    if (ref.current) ref.current.dataset.ok = '1';\n"
        "  });\n"
        "  return <div ref={ref} />;\n"
        "}\n",
        encoding="utf-8",
    )
    (tmp_path / "retry.py").write_text(
        "from functools import lru_cache\n"
        "import httpx\n"
        "from fastapi import APIRouter\n"
        "router = APIRouter()\n"
        "@lru_cache(maxsize=64)\n"
        "def get_pool():\n"
        "    return {'ok': True}\n"
        "def ping_once():\n"
        "    for _ in range(3):\n"
        "        httpx.get('https://status.example.com', timeout=3.0)\n",
        encoding="utf-8",
    )
    report = billshock.run_scan(tmp_path)
    assert report["score"] == 100
    assert report["findings"] == []


def test_suppressions_and_file_skips(tmp_path: Path) -> None:
    # Skipped extensions / oversized / vendor files should not be scanned
    (tmp_path / "bundle.min.js").write_text("setInterval(() => fetch('/x'), 50);\n", encoding="utf-8")
    (tmp_path / "types.d.ts").write_text("declare const maxDuration: number;\n", encoding="utf-8")
    (tmp_path / "huge.ts").write_text("export const x = 1;\n" * 40000, encoding="utf-8")
    (tmp_path / "ignored.ts").write_text("setInterval(() => fetch('/x'), 100);\n", encoding="utf-8")
    (tmp_path / "api").mkdir()
    (tmp_path / "api" / "fetch.ts").write_text(
        "// billshock-ignore: BILL010\n"
        "export async function run() {\n"
        "  return await fetch('https://example.com/slow'); // billshock-ignore: BILL010\n"
        "}\n",
        encoding="utf-8",
    )
    (tmp_path / "api" / "route.ts").write_text(
        "import OpenAI from 'openai';\n"
        "const openai = new OpenAI();\n"
        "export async function POST() {\n"
        "  return openai.chat.completions.create({ model: 'gpt-4o', messages: [] });\n"
        "}\n",
        encoding="utf-8",
    )

    (tmp_path / ".billshockignore").write_text("ignored.ts\n", encoding="utf-8")
    (tmp_path / ".billshock.json").write_text(
        json.dumps({"ignoreRules": ["BILL003"], "ignore_rules": ["BILL005"]}),
        encoding="utf-8",
    )
    report = billshock.run_scan(tmp_path)
    assert report["findings"] == [], f"Unexpected findings: {report['findings']}"
    assert report["score"] == 100


def test_invalid_billshock_json_warns_without_crashing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / ".billshock.json").write_text("{not-valid-json", encoding="utf-8")
    (tmp_path / "ok.py").write_text("def add(a: int, b: int) -> int:\n    return a + b\n", encoding="utf-8")
    report = billshock.run_scan(tmp_path)
    err = capsys.readouterr().err
    assert "warning: ignoring invalid .billshock.json" in err
    assert report["score"] == 100


def test_git_diff_and_staged_regressions(tmp_path: Path) -> None:
    _init_git_repo(tmp_path)
    route = tmp_path / "src" / "app" / "api" / "chat" / "route.ts"
    route.parent.mkdir(parents=True)
    route.write_text(
        "import OpenAI from 'openai';\n"
        "import { Ratelimit } from '@upstash/ratelimit';\n"
        "const openai = new OpenAI();\n"
        "const ratelimit = {} as Ratelimit;\n"
        "export async function POST(req: Request) {\n"
        "  await ratelimit.limit('ip');\n"
        "  return openai.chat.completions.create({\n"
        "    model: 'gpt-4o',\n"
        "    max_tokens: 400,\n"
        "    messages: [],\n"
        "  });\n"
        "}\n",
        encoding="utf-8",
    )
    wf = tmp_path / ".github" / "workflows" / "poll.yml"
    wf.parent.mkdir(parents=True)
    wf.write_text("name: Poll\non:\n  schedule:\n    - cron: '0 * * * *'\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=tmp_path, check=True, capture_output=True)

    # Remove cost guardrails and introduce an aggressive every-minute cron
    route.write_text(
        "import OpenAI from 'openai';\n"
        "const openai = new OpenAI();\n"
        "export async function POST() {\n"
        "  return openai.chat.completions.create({\n"
        "    model: 'gpt-4o',\n"
        "    messages: [],\n"
        "  });\n"
        "}\n",
        encoding="utf-8",
    )
    wf.write_text("name: Poll\non:\n  schedule:\n    - cron: '* * * * *'\n", encoding="utf-8")

    diff_report = billshock.run_scan(tmp_path, diff_ref="HEAD", with_diff=True)
    diff_rules = {f["rule_id"] for f in diff_report["findings"]}
    assert "BILL015" in diff_rules
    assert "BILL016" in diff_rules
    assert diff_report["diff_audit"]["ran"] is True

    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)
    staged_report = billshock.run_scan(tmp_path, with_diff=True, staged=True)
    staged_rules = {f["rule_id"] for f in staged_report["findings"]}
    assert "BILL015" in staged_rules
    assert "BILL016" in staged_rules
    assert staged_report["diff_audit"]["ref"] == "--staged"


def test_baseline_suppression_workflow(tmp_path: Path) -> None:
    app_file = tmp_path / "client.ts"
    app_file.write_text("export function start() { setInterval(() => fetch('/ping'), 200); }\n", encoding="utf-8")
    baseline = tmp_path / "nested" / "baseline.json"

    rc_write = billshock.main([str(tmp_path), "--write-baseline", str(baseline), "--fail-on", "none"])
    assert rc_write == 0
    assert baseline.is_file()

    rc_baselined = billshock.main([str(tmp_path), "--baseline", str(baseline), "--fail-on", "any"])
    assert rc_baselined == 0

    # Adding a second finding breaks through the baseline
    (tmp_path / "second.py").write_text(
        "import requests\ndef loop():\n    while True:\n        requests.get('https://x.test')\n",
        encoding="utf-8",
    )
    rc_new = billshock.main([str(tmp_path), "--baseline", str(baseline), "--fail-on", "high"])
    assert rc_new == 1


def test_cli_outputs_sarif_markdown_json_and_errors(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # --version raises SystemExit(0)
    with pytest.raises(SystemExit) as exc:
        billshock.main(["--version"])
    assert exc.value.code == 0
    assert billshock.VERSION in capsys.readouterr().out

    # Invalid target exits 2
    assert billshock.main([str(tmp_path / "does-not-exist")]) == 2

    # Out-of-range --min-score exits 2
    assert billshock.main([str(CLEAN_APP), "--min-score", "150"]) == 2

    # --diff on non-git dir warns cleanly without failing
    non_git = tmp_path / "non_git"
    non_git.mkdir()
    (non_git / "ok.py").write_text("x = 1\n", encoding="utf-8")
    rc = billshock.main([str(non_git), "--diff", "HEAD"])
    assert rc == 0
    assert "not inside a git repository" in capsys.readouterr().err

    # JSON output to nested path
    json_out = tmp_path / "out" / "sub" / "report.json"
    assert billshock.main([str(RUNAWAY_APP), "--format", "json", "--output", str(json_out), "--fail-on", "none"]) == 0
    parsed_json = json.loads(json_out.read_text(encoding="utf-8"))
    assert parsed_json["grade"] == "BILL SHOCK ALERT"

    # Markdown output
    md_out = tmp_path / "out" / "report.md"
    assert billshock.main([str(RUNAWAY_APP), "--format", "markdown", "--output", str(md_out), "--fail-on", "none"]) == 0
    assert "BillShock Spend-Safety Audit" in md_out.read_text(encoding="utf-8")

    # SARIF 2.1.0 output
    sarif_out = tmp_path / "out" / "billshock.sarif"
    assert billshock.main([str(RUNAWAY_APP), "--format", "sarif", "--output", str(sarif_out), "--fail-on", "none"]) == 0
    sarif = json.loads(sarif_out.read_text(encoding="utf-8"))
    assert sarif["version"] == "2.1.0"
    assert len(sarif["runs"][0]["tool"]["driver"]["rules"]) == 16
    assert len(sarif["runs"][0]["results"]) >= 14


def test_skill_docs_and_manifests_consistent() -> None:
    skill_md = (REPO_ROOT / "skills" / "billshock" / "SKILL.md").read_text(encoding="utf-8")
    rules_md = (REPO_ROOT / "skills" / "billshock" / "references" / "rules.md").read_text(encoding="utf-8")
    pyproject = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    plugin_json = json.loads((REPO_ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    marketplace_json = json.loads((REPO_ROOT / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))

    assert f'version = "{billshock.VERSION}"' in pyproject
    assert f'version: "{billshock.VERSION}"' in skill_md
    assert plugin_json["version"] == billshock.VERSION
    assert marketplace_json["plugins"][0]["version"] == billshock.VERSION
    assert "billshock.py" in skill_md

    for idx in range(1, 17):
        rid = f"BILL{idx:03d}"
        assert rid in rules_md, f"{rid} missing from references/rules.md"
        assert rid in billshock.RULE_META

    # Ensure rule table count matches RULE_META
    found_ids = set(re.findall(r"BILL\d{3}", rules_md))
    assert found_ids == set(billshock.RULE_META.keys())

    # Ensure README action workflow snippet matches real action.yml inputs
    readme_md = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    action_yml = (REPO_ROOT / "action.yml").read_text(encoding="utf-8")
    for expected_key in ("path:", "diff:", "fail-on:", "min-score:", "sarif-file:"):
        assert expected_key in readme_md
        assert expected_key.rstrip(":") in action_yml
    for stale_key in ("diff-ref:", "upload-sarif:"):
        assert stale_key not in readme_md


def test_production_edge_cases_and_precision(tmp_path: Path) -> None:
    # 1. JSX apostrophes should never corrupt subsequent TSX effect/interval parsing
    (tmp_path / "Panel.tsx").write_text(
        "import { useEffect } from 'react';\n"
        "export function Panel() {\n"
        "  const note = <p>We're ready and it's cached.</p>;\n"
        "  useEffect(() => {\n"
        "    fetch('/api/ok');\n"
        "  }, []);\n"
        "  return <div>{note}</div>;\n"
        "}\n",
        encoding="utf-8",
    )

    # 2. Pure string Promise.all(map) URL builder and variable fetch init with AbortSignal.timeout
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "routes.ts").write_text(
        "export const formatUrls = (ids: string[]) => Promise.all(ids.map((id) => `/api/items/${id}`));\n",
        encoding="utf-8",
    )
    (tmp_path / "src" / "api").mkdir()
    (tmp_path / "src" / "api" / "proxy.ts").write_text(
        "export async function GET() {\n"
        "  const init = { signal: AbortSignal.timeout(4000) };\n"
        "  return await fetch('https://upstream.example.com/data', init);\n"
        "}\n",
        encoding="utf-8",
    )

    # 3. Axios without timeout on server route triggers BILL010, but axios.create({ timeout }) passes
    (tmp_path / "src" / "api" / "axios-bad.ts").write_text(
        "import axios from 'axios';\n"
        "export async function GET() {\n"
        "  return await axios.get('https://slow.example.com/items');\n"
        "}\n",
        encoding="utf-8",
    )
    (tmp_path / "src" / "api" / "axios-good.ts").write_text(
        "import axios from 'axios';\n"
        "const client = axios.create({ timeout: 3000 });\n"
        "export async function GET() {\n"
        "  return await client.get('https://fast.example.com/items');\n"
        "}\n",
        encoding="utf-8",
    )

    # 4. Unverified webhook endpoint MUST still trigger BILL005
    (tmp_path / "webhook.py").write_text(
        "import openai\n"
        "from fastapi import APIRouter\n"
        "router = APIRouter()\n"
        "@router.post('/webhook')\n"
        "def receive_webhook(payload: dict):\n"
        "    return openai.chat.completions.create(model='gpt-4o', max_tokens=100, messages=[])\n",
        encoding="utf-8",
    )

    # 5. Commented workflow cron should NOT trigger BILL014
    wf_dir = tmp_path / ".github" / "workflows"
    wf_dir.mkdir(parents=True)
    (wf_dir / "commented.yml").write_text(
        "name: Manual\non:\n  workflow_dispatch:\n#  schedule:\n#    - cron: '* * * * *'\n",
        encoding="utf-8",
    )

    # 6. Django Paginator + nested closure in Python route: Paginator is safe, and nested closures don't duplicate
    (tmp_path / "views.py").write_text(
        "from django.core.paginator import Paginator\n"
        "def list_paginated(request):\n"
        "    return Paginator(Order.objects.all(), 50)\n",
        encoding="utf-8",
    )

    # 7. Symlinked files outside or pointing locally are skipped safely
    real_bad = tmp_path / "ignored_target.txt"
    real_bad.write_text("x", encoding="utf-8")
    (tmp_path / "link.py").symlink_to(real_bad)

    report = billshock.run_scan(tmp_path)
    by_file = {(f["rule_id"], f["file"]) for f in report["findings"]}

    assert ("BILL010", "src/api/axios-bad.ts") in by_file
    assert ("BILL005", "webhook.py") in by_file
    assert len(report["findings"]) == 2, f"Unexpected findings: {report['findings']}"


def test_diff_ignores_comments_and_catches_business_hours_sub5m_cron(tmp_path: Path) -> None:
    _init_git_repo(tmp_path)
    wf = tmp_path / ".github" / "workflows" / "sync.yml"
    wf.parent.mkdir(parents=True)
    wf.write_text("name: Sync\non:\n  workflow_dispatch:\n", encoding="utf-8")
    code = tmp_path / "app.ts"
    code.write_text("export const ok = true;\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=tmp_path, check=True, capture_output=True)

    # Adding comments containing removed words shouldn't false-positive, while */2 9-17 * * 1-5 triggers BILL016
    code.write_text("export const ok = true;\n// removed max_tokens and timeout= in comment\n", encoding="utf-8")
    wf.write_text("name: Sync\non:\n  schedule:\n    - cron: '*/2 9-17 * * 1-5'\n", encoding="utf-8")

    report = billshock.run_scan(tmp_path, diff_ref="HEAD", with_diff=True)
    rules = [f["rule_id"] for f in report["findings"]]
    assert "BILL015" not in rules
    assert "BILL016" in rules


def test_installed_agent_skill_directories_are_skipped(tmp_path: Path) -> None:
    (tmp_path / ".agents" / "skills" / "billshock" / "scripts").mkdir(parents=True)
    (tmp_path / ".agents" / "skills" / "billshock" / "scripts" / "billshock.py").write_text("x = 1\n", encoding="utf-8")
    (tmp_path / ".claude" / "plugins").mkdir(parents=True)
    (tmp_path / ".claude" / "plugins" / "helper.py").write_text("import requests\nrequests.get('https://x.test')\n", encoding="utf-8")

    report = billshock.run_scan(tmp_path)
    assert report["files_scanned"] == 0
    assert report["findings"] == []
    assert report["score"] == 100
