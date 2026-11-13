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
