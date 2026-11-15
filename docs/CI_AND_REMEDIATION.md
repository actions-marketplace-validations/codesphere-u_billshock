# CI Integration, Baselines & Remediation Guide

## GitHub Actions (`codesphere-u/billshock@v1`)

Add a pull-request gate that checks both full repository spend surfaces and removed guardrails (`BILL015`, `BILL016`), uploading native SARIF 2.1.0 annotations to the GitHub Security tab:

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
          path: .
          diff: origin/${{ github.base_ref }}
          fail-on: high
          min-score: "80"
          sarif-file: billshock.sarif

      - uses: github/codeql-action/upload-sarif@v3
        if: always()
        with:
          sarif_file: billshock.sarif
```

## Outputs Available Downstream

- `steps.<id>.outputs.score` — Integer score (`0–100`)
- `steps.<id>.outputs.grade` — `SAFE`, `CAUTION`, or `BILL SHOCK ALERT`
- `steps.<id>.outputs.critical-count` — Number of critical findings
- `steps.<id>.outputs.sarif-file` — Generated SARIF 2.1.0 file path

## Remediation Reference

See [`skills/billshock/references/remediation.md`](../skills/billshock/references/remediation.md) and the interactive website docs at https://codesphere-u.github.io/billshock/docs.html.
