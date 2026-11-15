from __future__ import annotations

import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
WEBSITE_DIR = REPO_ROOT / "website"

HTML_PAGES = ("index.html", "studio.html", "proof.html", "docs.html", "rules.html")


def test_website_pages_structure_brand_and_cache_busting() -> None:
    css = (WEBSITE_DIR / "styles.css").read_text(encoding="utf-8")
    js = (WEBSITE_DIR / "app.js").read_text(encoding="utf-8")

    assert "[hidden]" in css
    assert "display: none !important" in css
    assert "#8ce071" in css
    assert "#fde047" in css
    assert "#fffdf2" in css
    assert "normalizeCleanUrl" in js

    for filename in HTML_PAGES:
        html = (WEBSITE_DIR / filename).read_text(encoding="utf-8")
        assert 'styles.css?v=1.1.0"' in html, f"{filename} missing cache-busted CSS link"
        assert 'app.js?v=1.1.0"' in html, f"{filename} missing cache-busted JS link"
        assert 'data-analytics="plausible"' in html, f"{filename} missing analytics attribute"
        assert 'width="196" height="36"' in html, f"{filename} missing wordmark dimensions"
        assert "[hidden] { display: none !important; }" in html
        # Ensure zero pink accents
        for pink in ("#ec4899", "#f472b6", "#db2777", "#ff69b4"):
            assert pink not in html.lower()


def test_index_schema_and_social_metadata() -> None:
    index_html = (WEBSITE_DIR / "index.html").read_text(encoding="utf-8")
    assert "og:title" in index_html
    assert "og:description" in index_html
    assert "og:image" in index_html
    assert "twitter:card" in index_html

    match = re.search(
        r'<script type="application/ld\+json">(.*?)</script>',
        index_html,
        flags=re.DOTALL,
    )
    assert match is not None
    data = json.loads(match.group(1))
    types = {item.get("@type") for item in data["@graph"]}
    assert {"Organization", "WebSite", "SoftwareApplication", "FAQPage"} <= types


def test_geo_seo_and_repo_docs_exist() -> None:
    required = [
        REPO_ROOT / "llms.txt",
        REPO_ROOT / "llms-full.txt",
        REPO_ROOT / "docs" / "GETTING_STARTED.md",
        REPO_ROOT / "docs" / "CI_AND_REMEDIATION.md",
        REPO_ROOT / ".github" / "workflows" / "pages.yml",
        WEBSITE_DIR / "llms.txt",
        WEBSITE_DIR / "llms-full.txt",
        WEBSITE_DIR / "robots.txt",
        WEBSITE_DIR / "sitemap.xml",
        WEBSITE_DIR / "favicon.svg",
        WEBSITE_DIR / "og-image.svg",
        WEBSITE_DIR / "manifest.webmanifest",
    ]
    for path in required:
        assert path.is_file(), f"Missing artifact: {path}"

    robots = (WEBSITE_DIR / "robots.txt").read_text(encoding="utf-8")
    for bot in ("OAI-SearchBot", "GPTBot", "ClaudeBot", "PerplexityBot", "Google-Extended"):
        assert bot in robots

    sitemap = (WEBSITE_DIR / "sitemap.xml").read_text(encoding="utf-8")
    for page in HTML_PAGES:
        target = "" if page == "index.html" else page
        assert f"https://codesphere-u.github.io/billshock/{target}" in sitemap
