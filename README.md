# IndexTrace

Google Search Console forensic diagnostic utility and RFC 9309 crawler tracer.

Part of the [WebAudits.pro](https://webaudits.pro) technical intelligence platform.

---

## What it does

IndexTrace is an open-source command-line tool that diagnoses why URLs get excluded or dropped from the Google search index. It inspects:
- Multi-hop redirect chains, measuring per-hop latency, detecting infinite redirect loops, and flagging protocol downgrades (HTTPS to HTTP).
- RFC 9309 robots.txt crawl access rules, pinpointing the exact line number of blocking directives using standard longest-match precedence.
- Server response headers and meta directives (`<link rel="canonical">`, `X-Robots-Tag`, `meta name="robots"`).
- Soft-404 patterns on HTTP 200 responses using content density and error token heuristics.
- Synthesizes a Google Search Console (GSC) exclusion root cause with ordered developer remediation steps.

---

## Why it exists

Google Search Console frequently reports opaque indexing failures:
- "Page with redirect"
- "Discovered - currently not indexed"
- "Crawled - currently not indexed"
- "Soft 404"
- "Excluded by 'noindex' tag"

Diagnosing the true root cause often requires manually reconciling disparate layers: server redirect rules, edge CDN caching headers, RFC 9309 robots.txt precedence, and canonical tag targets. IndexTrace automates this multi-layer audit in a single terminal command or CI pipeline step.

---

## Key features

- **Hop-by-Hop Trace Engine:** Follows redirects sequentially, recording HTTP status codes, latency, headers, and destination targets.
- **RFC 9309 Compliant Matcher:** Implements official IETF RFC 9309 longest-match prefix resolution, identifying the exact rule and line number in robots.txt that governs a URL.
- **Crawler User-Agent Profiles:** Emulates Googlebot Desktop, Googlebot Smartphone, and desktop Chrome user agents.
- **Soft-404 Heuristic Classifier:** Analyzes page word count, text-to-code ratio, and common error strings on HTTP 200 responses to identify false-positive successful responses.
- **Actionable Remediation Output:** Maps findings directly to developer action items with ordered priority.

---

## Architecture

```text
[Input Target URL]
        |
        +---> [HTTP Hop Tracer] ---------> Redirect Chain & Latency Timeline
        |
        +---> [RFC 9309 Engine] ---------> Line-Level Robots.txt Collision Analysis
        |
        +---> [Directives Inspector] ----> Canonical, Meta Robots & X-Robots-Tag Audit
        |
        +---> [Soft-404 Classifier] -----> Content Density & Error Token Detection
        |
        v
[Verdict Synthesis Engine]
        |
        +---> Terminal Report (Rich Table)
        +---> Markdown Document / JSON Pipeline Output
```

IndexTrace executes four diagnostic stages:
1. `tracer.py`: Sequentially follows HTTP redirects up to a configurable maximum (default: 12 hops), capturing status code, hop latency, and SSL protocol changes.
2. `robots_matcher.py`: Fetches origin `robots.txt`, applies RFC 9309 rules with user-agent specificity and longest-path matching, and identifies the exact rule line number.
3. `directives_inspector.py`: Extracts canonical link tags, HTML meta robots tags, and HTTP `X-Robots-Tag` headers from the final hop response.
4. `verdict_engine.py`: Correlates data from all stages to isolate the primary Google Search Console classification and generates prioritized remediation steps.

---

## Installation

### Prerequisites
- Python 3.10 or higher

### Install from Source
```bash
git clone https://github.com/xcalibur73/index-trace.git
cd index-trace
pip install -r requirements.txt
pip install -e .
```

---

## Usage

### Basic CLI Invocation
```bash
# Audit a target URL
index-trace https://webaudits.pro

# Emulate Googlebot smartphone crawler
index-trace https://example.com --ua googlebot-mobile

# Trace long redirect chains (up to 20 hops) with 15s timeout
index-trace https://example.com --max-hops 20 --timeout 15

# Export JSON report for CI/CD pipelines
index-trace https://example.com --output json --save gsc-report.json

# Check installed version
index-trace --version
```

---

## Example output

```text
+-------------------------------------------------------------------------------+
| IndexTrace: Google Search Console Forensic Diagnostic                         |
| Target: https://webaudits.pro                                                 |
| GSC Diagnosis: INDEXABLE                                                      |
| Root Cause: URL satisfies all technical indexability criteria                 |
+-------------------------------------------------------------------------------+

Hop-by-Hop Redirect Chain:
+-----+--------+---------+-----------------------+-----------------------------+
| Hop | Status | Latency | URL                   | Next Location               |
+-----+--------+---------+-----------------------+-----------------------------+
| 1   | 308    | 42 ms   | http://webaudits.pro  | https://webaudits.pro       |
| 2   | 200    | 88 ms   | https://webaudits.pro |                             |
+-----+--------+---------+-----------------------+-----------------------------+

Robots.txt Crawl Collision Analysis (RFC 9309):
- Crawl Access Status: ALLOWED
- Matching Rule: None (Default Allow)
- Evaluated Path: /

Directives & Canonical Tag Alignment:
- Canonical URL: https://webaudits.pro (Self-referential, Clean)
- X-Robots-Tag: None declared
- Meta Robots: index, follow
- Soft-404 Classifier: CLEAN (0.0% probability risk | 1,420 words)
```

---

## Benchmark / methodology

### Empirical GSC Forensic Case Studies
- **Dataset:** Tested across 10 diverse production edge cases including redirect loops, line-level robots.txt disallows, SSL protocol downgrades, and thin soft-404 templates.
- **Command Used:** `python run.py <url> --output json`
- **Tool Version:** IndexTrace v1.0.0
- **Environment:** Windows 11 / Ubuntu 22.04, Python 3.12, unthrottled fiber network.
- **Validation:**
  - Verified exact line-level match on complex robots.txt files (e.g. line 238 on GitHub).
  - Cumulative latency calculation: `sum(hop_latency_ms)` accurately tracks cumulative TTFB overhead.
- **Results:**
  - Detected 100% of tested redirect loops and protocol downgrades.
  - Full case study documentation: [BENCHMARKS.md](BENCHMARKS.md).

---

## Limitations

- **Diagnostic Heuristic:** The GSC Status and Root Cause verdicts are project-derived analytical models based on observed Google indexing behaviors. IndexTrace is not Google software and cannot guarantee whether Google will choose to crawl, render, or index a page.
- **Quality Signal Independence:** Google indexing decisions depend heavily on content quality, query intent, and site-wide domain authority. IndexTrace audits technical and crawlability preconditions only.
- **Dynamic JavaScript Redirects:** Analyzes HTTP and `<meta http-equiv="refresh">` redirects. Does not execute client-side `window.location` JavaScript mutations unless paired with a headless browser runner.

---

## Accuracy / standards

IndexTrace aligns its checks against official web standards and project heuristics:

| Metric / Check | Classification | Authority / Standard |
|:---|:---|:---|
| Robots.txt Precedence | Google / Web Standard | IETF RFC 9309 |
| HTTP Status Codes & Hops | Web Standard | IETF RFC 9110 (HTTP Semantics) |
| Canonical Tag Syntax | Google / Web Standard | RFC 6596 |
| Cumulative Redirect Latency | Web Standard | W3C Navigation Timing Level 2 |
| Soft-404 Probability Score | Project-Derived Heuristic | Content-density & error-string classifier |
| GSC Diagnosis Verdict | Project-Derived Heuristic | Decision tree modeling Search Central docs |

---

## Testing

IndexTrace includes unit tests verifying redirect tracing, RFC 9309 parsing, robots collision resolution, and soft-404 detection:

```bash
# Run unit test suite
python -m unittest discover -s tests

# Test execution output
# Ran 14 tests in 0.002s
# OK
```

Automated CI executes on every push and pull request via GitHub Actions across Linux and Windows environments.

---

## Roadmap

- [x] Initial release with RFC 9309 parser and hop tracer.
- [x] PEP 621 packaging, CLI `--version`, and Windows cp1252 encoding safety.
- [ ] Direct Google Search Console Search Console API inspection integration.
- [ ] Bulk sitemap URL redirect audit mode with concurrency controls.
- [ ] WebAudits.pro continuous indexing monitoring webhooks.

---

## License

MIT License. See [LICENSE](LICENSE) for full details.
