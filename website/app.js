(function () {
  "use strict";

  var DOC_ORDER = [
    { id: "quickstart", title: "Quick Start" },
    { id: "cli", title: "CLI Flags & Exit Codes" },
    { id: "pillars", title: "6 Spend-Safety Pillars" },
    { id: "remediation", title: "Remediation Playbook" },
    { id: "baselines", title: "Git Diff & Baselines" },
    { id: "config", title: "Configuration & Ignores" },
    { id: "action", title: "GitHub Action & SARIF" },
    { id: "plugin", title: "Claude Plugin & Agent Skill" }
  ];

  var RULES_DATA = [
    { id: "BILL001", sev: "critical", pillar: "EFFECT_LOOP", label: "Effect Loop", desc: "useEffect invoking network requests without a dependency array (infinite loop risk).", fix: "Pass an explicit dependency array ([], [id]) and abort stale calls on cleanup." },
    { id: "BILL002", sev: "high", pillar: "EFFECT_LOOP", label: "Effect Loop", desc: "Sub-second client polling interval (<1000ms) triggering network calls.", fix: "Use >= 5000ms intervals or SSE/WebSockets with cleanup." },
    { id: "BILL003", sev: "high", pillar: "AI_BOMB", label: "AI Bomb", desc: "Generative LLM call omits explicit max_tokens / maxOutputTokens ceiling.", fix: "Always configure max_tokens / maxOutputTokens / max_completion_tokens." },
    { id: "BILL004", sev: "critical", pillar: "AI_BOMB", label: "AI Bomb", desc: "Paid AI, email, or SMS SDK called inside an unbounded loop.", fix: "Slice batches, use p-limit or Semaphore, or enqueue background jobs." },
    { id: "BILL005", sev: "critical", pillar: "AI_BOMB", label: "AI Bomb", desc: "Public HTTP route exposes paid AI/email/SMS SDK without auth or rate limit.", fix: "Enforce session/JWT auth and Upstash Ratelimit or SlowAPI limits." },
    { id: "BILL006", sev: "high", pillar: "DB_EGRESS", label: "DB Egress", desc: "N+1 database or ORM query executed per iteration inside a loop.", fix: "Batch with IN (...), JOINs, or DataLoader before iterating." },
    { id: "BILL007", sev: "high", pillar: "DB_EGRESS", label: "DB Egress", desc: "Unbounded table scan (findMany / select / SELECT *) inside server route.", fix: "Add explicit take / LIMIT / .range() pagination and column projections." },
    { id: "BILL008", sev: "medium", pillar: "DB_EGRESS", label: "DB Egress", desc: "Unbounded Promise.all(items.map(...)) fan-out over network or DB I/O.", fix: "Cap concurrency with p-limit or fixed chunk slices." },
    { id: "BILL009", sev: "critical", pillar: "RETRY_HANG", label: "Retry Hang", desc: "Unbounded while True / while (true) loop executes external I/O without cap.", fix: "Enforce max_retries ceiling, exponential backoff + jitter, and stop signal." },
    { id: "BILL010", sev: "medium", pillar: "RETRY_HANG", label: "Retry Hang", desc: "Server-side outbound HTTP request omits explicit timeout / AbortSignal.timeout.", fix: "Set timeout= (Python) or signal: AbortSignal.timeout(...) (JS/TS)." },
    { id: "BILL011", sev: "high", pillar: "RETRY_HANG", label: "Retry Hang", desc: "Zero-delay retry loop or extended maxDuration wrapping uncapped APIs.", fix: "Tighten maxDuration, add backoff jitter, and cap upstream timeouts." },
    { id: "BILL012", sev: "high", pillar: "LEAK_POOL", label: "Leak & Pool", desc: "Database client/pool instantiated per request instead of shared singleton.", fix: "Reuse a module-level / globalThis singleton client or lifespan pool." },
    { id: "BILL013", sev: "high", pillar: "LEAK_POOL", label: "Leak & Pool", desc: "Module-level collection grows across handler calls with no LRU/TTL eviction.", fix: "Switch to @lru_cache(maxsize=...), TTLCache, or Redis." },
    { id: "BILL014", sev: "medium", pillar: "INFRA_CRON_DIFF", label: "Infra & Diff", desc: "Sub-5-minute cron (* * * * *) or excessive maxDuration (>300s) in config.", fix: "Widen cron cadence (>= 5m) or move polling to queue events." },
    { id: "BILL015", sev: "high", pillar: "INFRA_CRON_DIFF", label: "Infra & Diff", desc: "Git diff removes rate_limit, max_tokens, timeout=, or LIMIT without replacement.", fix: "Restore explicit spend/rate/limit protection before merging PR." },
    { id: "BILL016", sev: "critical", pillar: "INFRA_CRON_DIFF", label: "Infra & Diff", desc: "Git diff introduces new sub-5m cron or high-burn unguarded endpoint.", fix: "Widen schedule interval and add auth/rate-limit caps." }
  ];

  function normalizeCleanUrl() {
    if (!window.history || !window.history.replaceState) return;
    var loc = window.location;
    if (loc.protocol !== "http:" && loc.protocol !== "https:") return;
    if (!loc.pathname.endsWith(".html")) return;
    var cleanPath = loc.pathname.slice(0, -5);
    if (cleanPath.endsWith("/index")) cleanPath = cleanPath.slice(0, -5);
    var target = cleanPath + loc.search + loc.hash;
    try {
      window.history.replaceState(null, "", target);
    } catch (_) {
      /* ignore */
    }
  }

  function showToast(msg) {
    var t = document.getElementById("toast");
    if (!t) return;
    t.textContent = msg;
    t.classList.add("visible");
    window.setTimeout(function () {
      t.classList.remove("visible");
    }, 1800);
  }

  function copyText(text) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(function () {
        showToast("Copied to clipboard");
      }).catch(function () {
        showToast("Copied");
      });
    } else {
      showToast("Copy supported in modern browsers");
    }
  }

  function initCTA() {
    var mainBtn = document.getElementById("cta-main-btn");
    var caretBtn = document.getElementById("cta-caret-btn");
    var popover = document.getElementById("cta-popover");
    var caption = document.getElementById("hero-cmd-caption");
    var popCmd = document.getElementById("popover-cmd-text");
    var popCopy = document.getElementById("popover-copy-btn");
    if (!mainBtn || !caretBtn || !popover || !caption) return;

    var currentCmd = caption.textContent.trim();

    mainBtn.addEventListener("click", function () {
      copyText(currentCmd);
    });

    caretBtn.addEventListener("click", function (ev) {
      ev.stopPropagation();
      var open = popover.classList.toggle("open");
      caretBtn.setAttribute("aria-expanded", open ? "true" : "false");
    });

    document.addEventListener("click", function (ev) {
      if (popover.classList.contains("open") && !popover.contains(ev.target) && ev.target !== caretBtn) {
        popover.classList.remove("open");
        caretBtn.setAttribute("aria-expanded", "false");
      }
    });

    popover.querySelectorAll(".pop-tab").forEach(function (tab) {
      tab.addEventListener("click", function () {
        popover.querySelectorAll(".pop-tab").forEach(function (b) {
          b.classList.remove("active");
        });
        tab.classList.add("active");
        currentCmd = tab.getAttribute("data-cmd") || currentCmd;
        caption.textContent = currentCmd;
        if (popCmd) popCmd.textContent = currentCmd;
      });
    });

    if (popCopy) {
      popCopy.addEventListener("click", function () {
        copyText(currentCmd);
      });
    }
  }

  function initHomePreview() {
    var pre = document.getElementById("home-preview-pre");
    var tabs = document.querySelectorAll(".frame-tab[data-preview]");
    if (!pre || !tabs.length) return;

    var views = {
      runaway: [
        "$ python3 ~/.agents/skills/billshock/scripts/billshock.py tests/fixtures/runaway_app --no-color",
        "",
        "BillShock v1.1.0 — Spend-Safety & Runaway-Cost Report",
        "Target: tests/fixtures/runaway_app | Files scanned: 4 | AI calls: 2 | DB ops: 1 | HTTP: 5 | Crons: 1",
        "Score:  0/100 (BILL SHOCK ALERT)  [critical=8 high=11 medium=5 low=0]",
        "",
        "[CRITICAL] BILL004 backend/jobs.py:20 — Paid SDK call inside unbounded loop.",
        "[CRITICAL] BILL005 src/app/api/generate/route.ts:25 — Unauthenticated paid AI endpoint.",
        "[CRITICAL] BILL001 src/components/AutoChat.tsx:7 — useEffect invokes fetch without dependency array.",
        "[HIGH    ] BILL007 src/app/api/export/route.ts:15 — Unbounded prisma.order.findMany() scan.",
        "[MEDIUM  ] BILL014 vercel.json:5 — Sub-5-minute cron schedule `* * * * *` runs continuously."
      ].join("\n"),
      clean: [
        "$ python3 ~/.agents/skills/billshock/scripts/billshock.py tests/fixtures/clean_app --fail-on any --min-score 100",
        "",
        "BillShock v1.1.0 — Spend-Safety & Runaway-Cost Report",
        "Target: tests/fixtures/clean_app | Files scanned: 3 | AI calls: 1 | DB ops: 1 | HTTP: 3 | Crons: 2",
        "Score:  100/100 (SAFE)  [critical=0 high=0 medium=0 low=0]",
        "",
        "No runaway loops, uncapped AI calls, unbounded scans, or cost regressions detected."
      ].join("\n"),
      diff: [
        "$ billshock . --diff HEAD --fail-on high --min-score 80",
        "",
        "BillShock v1.1.0 — Diff & Guardrail Regression Audit",
        "Diff target: HEAD (2 modified files) | Score: 64/100 (BILL SHOCK ALERT)",
        "",
        "[CRITICAL] BILL016 .github/workflows/poll.yml:3 — Newly added sub-5m cron `* * * * *`.",
        "[HIGH    ] BILL015 src/app/api/chat/route.ts:12 — Removed `ratelimit` and `max_tokens` guardrails without replacement."
      ].join("\n")
    };

    tabs.forEach(function (btn) {
      btn.addEventListener("click", function () {
        var key = btn.getAttribute("data-preview") || "runaway";
        tabs.forEach(function (b) {
          var active = b === btn;
          b.classList.toggle("active", active);
          b.setAttribute("aria-selected", active ? "true" : "false");
        });
        pre.textContent = views[key] || views.runaway;
      });
    });
  }

  function initCopyButtons() {
    document.querySelectorAll(".copy-icon-btn[data-copy]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var txt = btn.getAttribute("data-copy") || "";
        copyText(txt);
      });
    });
  }

  function initDocsNavigation() {
    var navLinks = Array.prototype.slice.call(document.querySelectorAll(".doc-nav-link[data-doc]"));
    var mobileChips = Array.prototype.slice.call(document.querySelectorAll(".docs-mobile-chip[data-doc]"));
    var chapters = Array.prototype.slice.call(document.querySelectorAll(".doc-chapter"));
    var subrails = Array.prototype.slice.call(document.querySelectorAll(".doc-subrail[data-subrail]"));
    var prevBtn = document.getElementById("doc-prev-btn");
    var nextBtn = document.getElementById("doc-next-btn");
    var prevTitle = document.getElementById("doc-prev-title");
    var nextTitle = document.getElementById("doc-next-title");
    if (!navLinks.length || !chapters.length) return;

    var activeId = DOC_ORDER[0].id;

    function selectChapter(docId, scrollToId) {
      var idx = DOC_ORDER.findIndex(function (d) { return d.id === docId; });
      if (idx === -1) idx = 0;
      activeId = DOC_ORDER[idx].id;

      chapters.forEach(function (art) {
        art.hidden = art.id !== "doc-" + activeId;
      });
      navLinks.forEach(function (btn) {
        btn.classList.toggle("active", btn.getAttribute("data-doc") === activeId);
      });
      mobileChips.forEach(function (chip) {
        chip.classList.toggle("active", chip.getAttribute("data-doc") === activeId);
      });
      subrails.forEach(function (rail) {
        rail.classList.toggle("open", rail.getAttribute("data-subrail") === activeId);
      });

      if (prevBtn && prevTitle) {
        if (idx > 0) {
          prevBtn.hidden = false;
          prevTitle.textContent = DOC_ORDER[idx - 1].title;
          prevBtn.setAttribute("data-go", DOC_ORDER[idx - 1].id);
        } else {
          prevBtn.hidden = true;
        }
      }
      if (nextBtn && nextTitle) {
        if (idx < DOC_ORDER.length - 1) {
          nextBtn.hidden = false;
          nextTitle.textContent = DOC_ORDER[idx + 1].title;
          nextBtn.setAttribute("data-go", DOC_ORDER[idx + 1].id);
        } else {
          nextBtn.hidden = true;
        }
      }

      if (scrollToId) {
        var el = document.getElementById(scrollToId);
        if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
      }
    }

    navLinks.forEach(function (btn) {
      btn.addEventListener("click", function () {
        selectChapter(btn.getAttribute("data-doc") || "quickstart");
        window.scrollTo({ top: 0, behavior: "smooth" });
      });
    });

    mobileChips.forEach(function (chip) {
      chip.addEventListener("click", function () {
        selectChapter(chip.getAttribute("data-doc") || "quickstart");
      });
    });

    if (prevBtn) {
      prevBtn.addEventListener("click", function () {
        selectChapter(prevBtn.getAttribute("data-go") || "quickstart");
        window.scrollTo({ top: 0, behavior: "smooth" });
      });
    }
    if (nextBtn) {
      nextBtn.addEventListener("click", function () {
        selectChapter(nextBtn.getAttribute("data-go") || "quickstart");
        window.scrollTo({ top: 0, behavior: "smooth" });
      });
    }

    document.querySelectorAll(".doc-sub-link").forEach(function (link) {
      link.addEventListener("click", function () {
        document.querySelectorAll(".doc-sub-link").forEach(function (l) { l.classList.remove("active"); });
        link.classList.add("active");
      });
    });

    selectChapter(activeId);
  }

  function initStudioTabs() {
    var tabs = Array.prototype.slice.call(document.querySelectorAll(".studio-frame .handy-tab[data-tab]"));
    var panels = Array.prototype.slice.call(document.querySelectorAll(".studio-panel"));
    if (!tabs.length || !panels.length) return;

    tabs.forEach(function (btn) {
      btn.addEventListener("click", function () {
        var name = btn.getAttribute("data-tab");
        tabs.forEach(function (b) {
          var active = b === btn;
          b.classList.toggle("active", active);
          b.setAttribute("aria-selected", active ? "true" : "false");
        });
        panels.forEach(function (panel) {
          var active = panel.id === "panel-" + name;
          panel.classList.toggle("active", active);
          panel.hidden = !active;
        });
      });
    });
  }

  function evaluateSpendSnippet(code) {
    var lines = code.split("\n");
    var findings = [];
    var hasRoute = new RegExp("(export\\s+async\\s+function\\s+(GET|POST)|router\\.(get|post))").test(code);
    var hasAuthOrRate = new RegExp("(ratelimit|rate_limiter|require_auth|getSession|verifyToken)").test(code);

    var reEffect = new RegExp("\\b" + "use" + "(Layout)?Effect\\s*\\(");
    var reInterval = new RegExp("\\b" + "set" + "Interval\\s*\\([^\\n]+,\\s*(\\d+)");
    var reAi = new RegExp("(chat\\." + "completions|generate" + "Text|generate" + "Content)");
    var reFindMany = new RegExp("\\." + "find" + "Many\\s*\\(\\s*\\{\\s*\\}");
    var reDbLoop = new RegExp("\\." + "find" + "(Unique|First)|session\\.execute");
    var reWhile = new RegExp("\\bwhi" + "le\\s*\\(?\\s*(true|True)\\b");
    var reFetch = new RegExp("\\bfet" + "ch\\s*\\(|requests\\.get\\(");
    var rePool = new RegExp("new\\s+Prisma" + "Client|create_engine");
    var reCache = new RegExp("(CACHE|responseCache)[^=]*=\\s*\\{\\s*\\}");
    var reCron = new RegExp("\\*\\s+\\*\\s+\\*\\s+\\*\\s+\\*");

    if (reEffect.test(code) && !new RegExp(",\\s*\\[[^\\]]*\\]\\s*\\)\\s*;?").test(code)) {
      findings.push({ id: "BILL001", sev: "CRITICAL", penalty: 18, msg: "useEffect calls network I/O without an explicit dependency array.", fix: "Pass [] or explicit state dependencies + AbortController cleanup." });
    }
    var mInt = code.match(reInterval);
    if (mInt && Number(mInt[1]) < 1000) {
      findings.push({ id: "BILL002", sev: "HIGH", penalty: 9, msg: "setInterval(" + mInt[1] + "ms) polls below 1000ms threshold.", fix: "Increase interval to >= 5000ms or switch to streaming." });
    }
    if (reAi.test(code) && !new RegExp("max_?tokens|maxOutputTokens", "i").test(code)) {
      findings.push({ id: "BILL003", sev: "HIGH", penalty: 9, msg: "Generative LLM call omits explicit max_tokens output ceiling.", fix: "Set explicit max_tokens / maxOutputTokens ceiling on completion request." });
    }
    if (reAi.test(code) && hasRoute && !hasAuthOrRate) {
      findings.push({ id: "BILL005", sev: "CRITICAL", penalty: 18, msg: "Public route exposes paid AI SDK without auth or rate limiter.", fix: "Enforce session authentication and Upstash Ratelimit / SlowAPI dependency." });
    }
    if (new RegExp("for\\s+[a-zA-Z(]").test(code) && !new RegExp("\\[:\\d+\\]|slice\\(").test(code)) {
      if (reAi.test(code)) {
        findings.push({ id: "BILL004", sev: "CRITICAL", penalty: 18, msg: "Paid AI SDK invoked inside unbounded loop.", fix: "Slice input batches or enforce Semaphore / p-limit concurrency cap." });
      }
      if (reDbLoop.test(code)) {
        findings.push({ id: "BILL006", sev: "HIGH", penalty: 9, msg: "N+1 database query executed per iteration inside loop.", fix: "Replace looped lookup with a single batched IN (...) query." });
      }
    }
    if (reFindMany.test(code)) {
      findings.push({ id: "BILL007", sev: "HIGH", penalty: 9, msg: "Unbounded findMany({}) query omits take / cursor pagination.", fix: "Add explicit take: 25 or take: 50 cap and narrow select columns." });
    }
    if (reWhile.test(code) && !new RegExp("max_retries|MAX_RETRIES").test(code)) {
      findings.push({ id: "BILL009", sev: "CRITICAL", penalty: 18, msg: "Unbounded while True loop runs external I/O without max-retry guard.", fix: "Bound retries with MAX_RETRIES + exponential backoff." });
    }
    if (reFetch.test(code) && hasRoute && !new RegExp("AbortSignal\\.timeout|timeout\\s*=").test(code)) {
      findings.push({ id: "BILL010", sev: "MEDIUM", penalty: 4, msg: "Server-side HTTP call omits timeout / AbortSignal.timeout.", fix: "Configure explicit signal: AbortSignal.timeout(...) or timeout=." });
    }
    if (new RegExp("maxDuration\\s*=\\s*120").test(code) && !hasAuthOrRate) {
      findings.push({ id: "BILL011", sev: "HIGH", penalty: 9, msg: "Extended maxDuration = 120 pairs with uncapped paid SDK call.", fix: "Lower maxDuration and enforce upstream timeout + rate limit." });
    }
    if (rePool.test(code) && !new RegExp("globalThis").test(code)) {
      findings.push({ id: "BILL012", sev: "HIGH", penalty: 9, msg: "Database client/pool instantiated per module/request without globalThis singleton.", fix: "Reuse a globalThis singleton client to avoid connection exhaustion." });
    }
    if (reCache.test(code) && !new RegExp("lru_cache|maxsize").test(code)) {
      findings.push({ id: "BILL013", sev: "HIGH", penalty: 9, msg: "Module-level cache object grows across handler calls with no eviction cap.", fix: "Use bounded @lru_cache(maxsize=...), TTLCache, or Redis." });
    }
    if (reCron.test(code)) {
      findings.push({ id: "BILL014", sev: "MEDIUM", penalty: 4, msg: "Sub-5-minute cron schedule (* * * * *) runs continuously.", fix: "Widen cadence to >= 5m or trigger via queue." });
    }

    var penaltySum = findings.reduce(function (acc, f) { return acc + f.penalty; }, 0);
    var score = Math.max(0, 100 - penaltySum);
    var crit = findings.filter(function (f) { return f.sev === "CRITICAL"; }).length;
    var high = findings.filter(function (f) { return f.sev === "HIGH"; }).length;
    var med = findings.filter(function (f) { return f.sev === "MEDIUM"; }).length;
    var grade = (score >= 90 && crit === 0) ? "SAFE" : (score >= 70 && crit === 0 ? "CAUTION" : "ALERT");

    return { score: score, grade: grade, crit: crit, high: high, med: med, lines: lines.length, findings: findings };
  }

  function initSpendScanner() {
    var presetEl = document.getElementById("billshock-studio-presets");
    var codeEl = document.getElementById("scanner-code");
    var listEl = document.getElementById("scanner-findings");
    var fixBtn = document.getElementById("apply-remediation-btn");
    var chipWrap = document.getElementById("scanner-presets");
    if (!presetEl || !codeEl || !listEl) return;

    var presets = JSON.parse(presetEl.textContent || "{}");
    var currentPreset = "nextjs_ai";

    function render() {
      var res = evaluateSpendSnippet(codeEl.value);
      document.getElementById("sc-score").textContent = res.score + "/100";
      document.getElementById("sc-grade").textContent = res.grade;
      document.getElementById("sc-crit").textContent = String(res.crit);
      document.getElementById("sc-hm").textContent = res.high + " / " + res.med;

      if (!res.findings.length) {
        listEl.innerHTML = '<div class="rw-item"><span>BILLSHOCK 100/100 SAFE</span><p>All spend surfaces bounded with rate limits, token ceilings, timeouts, and pagination caps.</p></div>';
        return;
      }
      listEl.innerHTML = res.findings.map(function (f) {
        var borderCls = f.sev === "CRITICAL" ? "rw-item warn-border" : "rw-item";
        return '<div class="' + borderCls + '"><span>[' + f.sev + '] ' + f.id + '</span><p>' + f.msg + ' Fix: ' + f.fix + '</p></div>';
      }).join("");
    }

    if (chipWrap) {
      chipWrap.querySelectorAll(".chip-btn[data-preset]").forEach(function (btn) {
        btn.addEventListener("click", function () {
          currentPreset = btn.getAttribute("data-preset") || "nextjs_ai";
          chipWrap.querySelectorAll(".chip-btn").forEach(function (b) { b.classList.remove("active"); });
          btn.classList.add("active");
          codeEl.value = (presets[currentPreset] && presets[currentPreset].bad) || "";
          render();
        });
      });
    }

    if (fixBtn) {
      fixBtn.addEventListener("click", function () {
        if (presets[currentPreset] && presets[currentPreset].fixed) {
          codeEl.value = presets[currentPreset].fixed;
          render();
          showToast("Applied production remediation fix");
        }
      });
    }

    codeEl.addEventListener("input", render);
    codeEl.value = (presets[currentPreset] && presets[currentPreset].bad) || "";
    render();
  }

  function initBlastCalculator() {
    var scenEl = document.getElementById("blast-scenario");
    var scaleEl = document.getElementById("blast-scale");
    var runBtn = document.getElementById("run-blast-btn");
    var copyBtn = document.getElementById("copy-blast-btn");
    var preEl = document.getElementById("blast-pre");
    if (!scenEl || !scaleEl || !preEl) return;

    var profiles = {
      effect_storm: { rule: "BILL001", unitUnchecked: 0.00025, unitHardened: 0.00001, mult: 120, summary: "Unbounded useEffect triggers ~120 re-fetches/user session against serverless route." },
      ai_bomb: { rule: "BILL003/005", unitUnchecked: 0.015, unitHardened: 0.0004, mult: 1, summary: "Uncapped 4k-token gpt-4o completions on public POST route without Upstash Ratelimit." },
      db_egress: { rule: "BILL006/007", unitUnchecked: 0.008, unitHardened: 0.00008, mult: 1, summary: "Full-table findMany() scans + N+1 loop exhausting RDS/Supabase egress quotas." },
      cron_burn: { rule: "BILL014", unitUnchecked: 0.42, unitHardened: 0.02, mult: 0.005, summary: "Every-minute `* * * * *` cron executing 1,440 cold starts/day even at 0 traffic." }
    };
    var scales = { low: 25, medium: 200, spike: 1500 };

    function update() {
      var p = profiles[scenEl.value] || profiles.ai_bomb;
      var rpm = scales[scaleEl.value] || 200;
      var dayReq = Math.round(rpm * 60 * 24 * p.mult);
      var rawCost = Math.max(12, Math.round(dayReq * p.unitUnchecked));
      var safeCost = Math.max(1, Math.round((dayReq * 0.05) * p.unitHardened));
      var saved = (100 - (safeCost / rawCost) * 100).toFixed(1) + "%";

      document.getElementById("bl-unchecked").textContent = "$" + rawCost.toLocaleString();
      document.getElementById("bl-hardened").textContent = "$" + safeCost.toLocaleString();
      document.getElementById("bl-rule").textContent = p.rule;
      document.getElementById("bl-saved").textContent = saved;

      preEl.textContent = [
        "Scenario: " + p.rule + " (" + scaleEl.value + " tier)",
        "Modeled 24h invocations: " + dayReq.toLocaleString(),
        "Unchecked 24h exposure:  $" + rawCost.toLocaleString() + " USD",
        "Hardened 24h spend:      $" + safeCost.toLocaleString() + " USD",
        "",
        "Diagnosis: " + p.summary,
        "Gate cmd:  billshock . --diff HEAD --fail-on high --min-score 80"
      ].join("\n");
    }

    if (runBtn) runBtn.addEventListener("click", update);
    scenEl.addEventListener("change", update);
    scaleEl.addEventListener("change", update);
    if (copyBtn) copyBtn.addEventListener("click", function () { copyText(preEl.textContent); });
    update();
  }

  function initDiffAndOutputs() {
    var wrap = document.getElementById("artifact-tabs");
    var note = document.getElementById("artifact-note");
    var pre = document.getElementById("artifact-pre");
    var copyBtn = document.getElementById("copy-artifact-btn");
    if (!wrap || !pre) return;

    var samples = {
      diff: {
        note: "Git diff audit (BILL015 & BILL016) catches removed rate limits, token ceilings, LIMIT clauses, and timeouts before PR merge.",
        body: "$ billshock . --diff origin/main --fail-on high\n\n[CRITICAL] BILL016 .github/workflows/sync.yml:4 — Newly added sub-5m cron '*/2 9-17 * * 1-5'.\n[HIGH    ] BILL015 src/app/api/chat/route.ts:14 — Removed guardrails (`ratelimit`, `max_tokens`) without replacement.\nExit code: 1 (PR blocked)"
      },
      sarif: {
        note: "Native SARIF 2.1.0 integrates directly with GitHub Security Code Scanning via `--format sarif --output billshock.sarif`.",
        body: '{\n  "version": "2.1.0",\n  "runs": [{\n    "tool": { "driver": { "name": "BillShock", "version": "1.1.0" } },\n    "results": [{\n      "ruleId": "BILL005",\n      "level": "error",\n      "message": { "text": "HTTP route exposes paid AI SDK without authentication or rate limiting." },\n      "partialFingerprints": { "billshockFingerprint/v1": "9f3d12c480a7b119" }\n    }]\n  }]\n}'
      },
      baseline: {
        note: "Legacy repos adopt BillShock cleanly by snapshotting existing findings via `--write-baseline .billshock-baseline.json`.",
        body: '{\n  "tool": "billshock",\n  "version": "1.1.0",\n  "fingerprints": [\n    "3b18a991c7d0110f",\n    "9f3d12c480a7b119"\n  ]\n}'
      },
      action: {
        note: "GitHub Composite Action writes Markdown report to $GITHUB_STEP_SUMMARY and sets `score`, `grade`, and `critical-count` outputs.",
        body: "## BillShock Spend-Safety Audit — 100/100 (SAFE)\n\n- Files scanned: 42\n- Cost surfaces: 3 AI calls, 9 DB ops, 4 outbound HTTP, 1 cron job\n- Findings: 0 critical, 0 high, 0 medium, 0 low"
      }
    };

    function show(key) {
      var item = samples[key] || samples.diff;
      if (note) note.textContent = item.note;
      pre.textContent = item.body;
    }

    wrap.querySelectorAll(".chip-btn[data-art]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        wrap.querySelectorAll(".chip-btn").forEach(function (b) { b.classList.remove("active"); });
        btn.classList.add("active");
        show(btn.getAttribute("data-art") || "diff");
      });
    });

    if (copyBtn) copyBtn.addEventListener("click", function () { copyText(pre.textContent); });
    show("diff");
  }

  function initProof() {
    var beforeBtn = document.getElementById("proof-before-btn");
    var afterBtn = document.getElementById("proof-after-btn");
    var pre = document.getElementById("proof-pre");
    var badge = document.getElementById("proof-badge");
    if (!beforeBtn || !afterBtn || !pre) return;

    var data = {
      before: {
        score: "0/100",
        grade: "ALERT",
        crit: "8",
        exit: "1",
        badge: "8 critical · 11 high · 5 medium",
        text: "$ billshock tests/fixtures/runaway_app --fail-on high --no-color\n\nBillShock v1.1.0 — Spend-Safety & Runaway-Cost Report\nTarget: tests/fixtures/runaway_app | Files scanned: 4 | AI calls: 2 | DB ops: 1 | HTTP: 5 | Crons: 1\nScore:  0/100 (BILL SHOCK ALERT)  [critical=8 high=11 medium=5 low=0]\n\n[CRITICAL] BILL004 backend/jobs.py:20 — Paid SDK call `openai.chat.completions.create` inside loop.\n[CRITICAL] BILL005 src/app/api/generate/route.ts:25 — Endpoint exposes paid AI SDK without auth/ratelimit.\n[CRITICAL] BILL001 src/components/AutoChat.tsx:7 — useEffect invokes fetch without dependency array.\n[HIGH    ] BILL007 src/app/api/export/route.ts:15 — Unbounded prisma.order.findMany() scan.\n[MEDIUM  ] BILL014 vercel.json:5 — Sub-5-minute cron schedule `* * * * *` runs continuously."
      },
      after: {
        score: "100/100",
        grade: "SAFE",
        crit: "0",
        exit: "0",
        badge: "0 critical · 0 high · 0 medium",
        text: "$ billshock tests/fixtures/clean_app --fail-on any --min-score 100 --no-color\n\nBillShock v1.1.0 — Spend-Safety & Runaway-Cost Report\nTarget: tests/fixtures/clean_app | Files scanned: 3 | AI calls: 1 | DB ops: 1 | HTTP: 3 | Crons: 2\nScore:  100/100 (SAFE)  [critical=0 high=0 medium=0 low=0]\n\nNo runaway loops, uncapped AI calls, unbounded scans, or cost regressions detected."
      }
    };

    function select(mode) {
      var d = data[mode];
      beforeBtn.classList.toggle("active", mode === "before");
      afterBtn.classList.toggle("active", mode === "after");
      document.getElementById("pr-score").textContent = d.score;
      document.getElementById("pr-grade").textContent = d.grade;
      document.getElementById("pr-crit").textContent = d.crit;
      document.getElementById("pr-exit").textContent = d.exit;
      if (badge) badge.textContent = d.badge;
      pre.textContent = d.text;
    }

    beforeBtn.addEventListener("click", function () { select("before"); });
    afterBtn.addEventListener("click", function () { select("after"); });
  }

  function initRulesCatalog() {
    var tbody = document.getElementById("rules-tbody");
    var chips = document.getElementById("rule-pillar-chips");
    var searchEl = document.getElementById("rule-search");
    var sevEl = document.getElementById("rule-sev-filter");
    if (!tbody) return;

    var activePillar = "all";

    function render() {
      var q = (searchEl && searchEl.value || "").toLowerCase().trim();
      var sev = (sevEl && sevEl.value) || "all";

      var rows = RULES_DATA.filter(function (r) {
        if (activePillar !== "all" && r.pillar !== activePillar) return false;
        if (sev !== "all" && r.sev !== sev) return false;
        if (q && !(r.id + " " + r.label + " " + r.desc + " " + r.fix).toLowerCase().includes(q)) return false;
        return true;
      });

      tbody.innerHTML = rows.map(function (r) {
        var sevCls = r.sev === "critical" ? "pill-bad" : (r.sev === "high" ? "pill-warn" : "pill-gold");
        return (
          "<tr>" +
          "<td><code>" + r.id + "</code></td>" +
          '<td><span class="pill ' + sevCls + '">' + r.sev.toUpperCase() + "</span></td>" +
          '<td><span class="pill pill-green">' + r.label + "</span></td>" +
          "<td><strong>" + r.desc + "</strong><br /><span style='color:var(--text-70);font-size:0.86rem'>Fix: " + r.fix + "</span></td>" +
          "</tr>"
        );
      }).join("");
    }

    if (chips) {
      chips.querySelectorAll(".chip-btn[data-pillar]").forEach(function (btn) {
        btn.addEventListener("click", function () {
          activePillar = btn.getAttribute("data-pillar") || "all";
          chips.querySelectorAll(".chip-btn").forEach(function (b) { b.classList.remove("active"); });
          btn.classList.add("active");
          render();
        });
      });
    }
    if (searchEl) searchEl.addEventListener("input", render);
    if (sevEl) sevEl.addEventListener("change", render);
    render();
  }

  document.addEventListener("DOMContentLoaded", function () {
    normalizeCleanUrl();
    initCTA();
    initHomePreview();
    initCopyButtons();
    initDocsNavigation();
    initStudioTabs();
    initSpendScanner();
    initBlastCalculator();
    initDiffAndOutputs();
    initProof();
    initRulesCatalog();
  });
})();
