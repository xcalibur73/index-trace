# IndexTrace

Google Search Console Indexing Emergency & RFC 9309 Crawler Collision Tracer

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python: 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![Status: Production](https://img.shields.io/badge/status-production-success.svg)](#)
[![Cloud Engine: WebAudits.pro](https://img.shields.io/badge/cloud-webaudits.pro-orange.svg)](https://webaudits.pro/tools/index-trace)

IndexTrace is a command-line utility and Python diagnostic engine built for technical SEO leads and web infrastructure engineers. It isolates the exact root causes behind Google Search Console indexing dropouts:
- Infinite redirect loops, multi-hop latency bloat, and protocol downgrades.
- Line-by-line RFC 9309 robots.txt collisions pinpointing the exact offending line number.
- Header vs meta tag directive conflicts (`X-Robots-Tag: noindex` vs HTML head).
- Heuristic soft-404 classification on HTTP 200 responses.
- Deterministic GSC verdict synthesis paired with concrete engineering remediation steps.

---

## The Engineering Problem

Google Search Console reports indexing errors with high-level summaries: "Blocked by robots.txt", "Redirect error", "Excluded by noindex tag", or "Soft 404". These status codes do not explain:
1. Which specific line in a 400-line `robots.txt` file matched and blocked the crawler.
2. Which intermediate redirect hop leaked equity, stripped parameters, or caused an SSL protocol downgrade.
3. Whether an edge CDN header injected an unexpected `X-Robots-Tag: noindex` invisible in view-source HTML.
4. Why an HTTP 200 OK page was flagged as a soft-404 by Googlebot rendering algorithms.

IndexTrace executes automated traceroute-style audits from the crawler perspective, synthesizing low-level HTTP headers, AST directives, and RFC 9309 path rules into an actionable verdict.

---

## Architecture Overview

```
                        [ Target URL / Route ]
                                  │
          ┌───────────────────────┼───────────────────────┐
          ▼                       ▼                       ▼
   [ Hop-by-Hop Tracer ]   [ RFC 9309 Matcher ]   [ Directives Inspector ]
    - Multi-hop latencies   - Longest match rule    - X-Robots-Tag header
    - Loop detection        - Exact line numbers    - HTML meta robots
    - Protocol downgrades   - Allow vs Disallow     - Canonical alignment
          │                       │                       │
          └───────────────────────┼───────────────────────┘
                                  ▼
                     [ Soft-404 Heuristic Engine ]
                      - Title error marker check
                      - Thin content word counts
                      - Heading & phrase scoring
                                  ▼
                      [ GSC Verdict Synthesizer ]
                      - Deterministic status mapping
                      - Step-by-step engineering fixes
```

### 1. Hop-by-Hop Redirect Tracer (`tracer.py`)
Follows redirect chains hop by hop without losing intermediate state. Tracks per-hop DNS/TLS response latency, detects infinite loops, flags temporary redirects (302/307) that fail to pass indexing signals, and warns on HTTPS to HTTP protocol downgrades.

### 2. RFC 9309 Line-by-Line Matcher (`robots_matcher.py`)
Parses `robots.txt` line by line preserving line numbers. Implements standard crawler precedence:
- Specific crawler tokens (`Googlebot`) take priority over global wildcards (`*`).
- Pattern matching supports wildcards (`*`) and end-of-path anchors (`$`).
- Longest matching pattern wins.
- On equal pattern length, `Allow` takes precedence over `Disallow`.
- Identifies the exact rule and line number causing search engine blocking.

### 3. Directives & Canonical Inspector (`directives_inspector.py`)
Checks both HTTP transport headers and HTML document head. Detects conflicts where an edge proxy sends `X-Robots-Tag: noindex` while the HTML meta tags allow indexing. Validates self-referential canonical tags, flags relative canonical URLs, and alerts when cross-domain canonicals pass indexing equity elsewhere.

### 4. Soft-404 Heuristic Classifier (`soft404_detector.py`)
Inspects HTTP 200 OK responses for soft-404 patterns. Evaluates title error tags, primary heading text, thin body copy (under 25 or 60 words), and common error strings that trigger Google Search Console soft-404 classification.

### 5. GSC Verdict Synthesizer (`verdict_engine.py`)
Collates signals from all subsystems and maps them directly to Search Console indexing states (`CLEAN_INDEXABLE`, `BLOCKED_BY_ROBOTS_TXT`, `EXCLUDED_BY_NOINDEX`, `REDIRECT_ERROR`, `SOFT_404_DETECTED`, `SERVER_ERROR_5XX`). Provides ordered engineering instructions for site owners and DevOps engineers.

---

## Installation

```bash
git clone https://github.com/xcalibur73/index-trace.git
cd index-trace
pip install -r requirements.txt
```

Or install in editable mode:
```bash
pip install -e .
```

---

## Quick Start

### Basic Diagnostic Audit
```bash
python run.py https://webaudits.pro
```

### Simulate Googlebot Mobile
```bash
python run.py https://example.com/product-page --ua googlebot-mobile
```

### Export Markdown Audit Report
```bash
python run.py https://example.com/login --output markdown --save audit_report.md
```

### Export Machine-Readable JSON for CI/CD Pipelines
```bash
python run.py https://example.com/checkout --output json --save audit.json
```

---

## Live Audit Example

Diagnosing a blocked internal path on GitHub (`https://github.com/search`):

```bash
python run.py https://github.com/search
```

Terminal output:
```
+-----------------------------------------------------------------------------+
| IndexTrace: Google Search Console Forensic Diagnostic                       |
| Target: https://github.com/search                                           |
| GSC Diagnosis: BLOCKED_BY_ROBOTS_TXT                                        |
| Root Cause: Blocked from search crawling by rule 'Disallow: /search$' at    |
| line 238 in robots.txt.                                                     |
+-----------------------------------------------------------------------------+
                       Hop-by-Hop Redirect Chain                        
+----------------------------------------------------------------------+
| Hop  | Status | Latency  | URL                       | Next Location |
|------+--------+----------+---------------------------+---------------|
| 1    | 200    | 514.5 ms | https://github.com/search |               |
+----------------------------------------------------------------------+
      Robots.txt Crawl Collision Analysis (RFC 9309)      
+--------------------------------------------------------+
| Field                  | Evaluated Value               |
|------------------------+-------------------------------|
| Crawl Access Status    | BLOCKED                       |
| Evaluated User-Agent   | *                             |
| Evaluated Path         | /search                       |
| Matching Directive     | Disallow: /search$ (Line 238) |
| Robots.txt File        | https://github.com/robots.txt |
| Location               |                               |
+--------------------------------------------------------+
                Directives & Canonical Tag Integrity                 
+-------------------------------------------------------------------+
| Directive Check          | State     | Details                    |
|--------------------------+-----------+----------------------------|
| X-Robots-Tag (Header)    | INDEXABLE | (Header not present)       |
| Meta Robots (HTML)       | INDEXABLE | (Meta tag empty or absent) |
| Canonical Tag Alignment  | MISSING   | (No canonical declared)    |
| Soft-404 Classifier      | CLEAN     | 0% risk | 62 words         |
+-------------------------------------------------------------------+
+------------------- Step-by-Step Engineering Remediation --------------------+
| 1. Remove or narrow the disallow pattern 'Disallow: /search$' in            |
| 'https://github.com/robots.txt'.                                            |
| 2. If using a CMS plugin (e.g. WordPress Yoast / Rank Math), check dynamic  |
| robots.txt configuration settings.                                          |
| 3. Note: Blocking a page in robots.txt does NOT prevent it from being       |
| indexed if external backlinks exist (use 'noindex' instead if de-indexation |
| is desired).                                                                |
+-----------------------------------------------------------------------------+
```

---

## Empirical Benchmarks & Case Studies

IndexTrace has been benchmarked against real-world crawl architectures and RFC 9309 rule collision scenarios. Detailed empirical telemetry: [BENCHMARKS.md](BENCHMARKS.md).

Key empirical findings:
- RFC 9309 rule collisions: Isolated exact line-level disallows (e.g. `Disallow: /search$` at line 238 on `github.com/robots.txt`) within 300+ line production configurations.
- Redirect latency accumulation: Multi-hop redirect chains (such as 4-hop 302 sequences) introduce over 4,100ms of cumulative network connection delay, triggering crawler dropouts.
- Protocol penalty: Internal links using legacy HTTP protocols incur an avoidable 110ms+ latency penalty per crawl request.
- Soft-404 heuristics: Successfully detects HTTP 200 OK responses with depleted product catalogs or empty search results using title/heading signals and thin-content thresholds before GSC de-indexing occurs.

---

## Test Suite

IndexTrace includes unit tests covering line numbering accuracy, RFC 9309 longest matching rules, header parsing, soft-404 heuristics, and verdict synthesis:

```bash
python -m unittest discover -s tests -p "test_*.py"
```

Result:
```
..............
----------------------------------------------------------------------
Ran 14 tests in 0.002s

OK
```

---

## Author & Attribution

Maintained by [@xcalibur73](https://github.com/xcalibur73), creator of [WebAudits.pro](https://webaudits.pro).

Part of a technical SEO engineering tooling trio:
1. [dom-hydrate](https://github.com/xcalibur73/dom-hydrate): Headless Chromium SSR vs CSR DOM diff engine.
2. [citation-pulse](https://github.com/xcalibur73/citation-pulse): GEO and AI search citability benchmark engine.
3. [index-trace](https://github.com/xcalibur73/index-trace): Search Console emergency triage and crawler collision tracer.

Licensed under the [MIT License](LICENSE).
