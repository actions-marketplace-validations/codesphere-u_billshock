# BillShock Multi-Channel Launch Playbook (`v1.1.0`)

## Target Channels & Developer Communities

1. **GitHub Actions & Security Ecosystem**: Publish `codesphere-u/billshock@v1` workflow templates and native SARIF 2.1.0 integration snippets for Next.js + OpenAI + Prisma teams.
2. **skills.sh & Agentic IDE Ecosystem**: Highlight one-command install (`npx skills add codesphere-u/billshock` and `/plugin install billshock --marketplace codesphere-u/billshock`) with deterministic exit codes for Cursor, Claude Code, Codex, and Antigravity.
3. **FinOps & Indie Maker Showcases**: Share real before/after fixture breakdowns (`0/100 BILL SHOCK ALERT` -> `100/100 SAFE`) demonstrating how static PR gates stop `useEffect` storms and missing `max_tokens` caps before production deploys.

## Launch Checklist

- Verify `billshock.py . --fail-on any --min-score 100` and `pytest -v` pass with zero warnings.
- Confirm GitHub Pages live at `https://codesphere-u.github.io/billshock/`.
- Verify `llms.txt`, `sitemap.xml`, `robots.txt`, and `og-image.svg` return HTTP 200 on live Pages.
- Publish GitHub Release `v1.1.0` with updated Action and SARIF examples.
