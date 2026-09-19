# IndexTrace

Google Search Console forensic diagnostic utility and RFC 9309 crawler tracer.

Part of the [WebAudits.pro](https://webaudits.pro) technical intelligence platform.

---

## Quickstart

Install in editable mode and audit crawl and indexation health in seconds:

```bash
# Clone and install
git clone https://github.com/xcalibur73/index-trace.git
cd index-trace
pip install -r requirements.txt
pip install -e .

# Audit target URL
index-trace https://example.com

# Emulate Googlebot smartphone crawler
index-trace https://example.com --ua googlebot-mobile
```

---

## Typical SEO Incident Diagnosed in 10 Seconds

### Incident: Staging Header Leak Dropping Priority Pages from Google Index
- **Symptom:** Google Search Console suddenly flags 85 product URLs under "Excluded by 'noindex' tag" after an edge routing update, with organic traffic dropping. The page source shows `<meta name="robots" content="index, follow">`.
- **Command:**
  ```bash
  index-trace https://example.com/products/flagship --ua googlebot-mobile
  ```
- **Diagnosis Isolated:**
  ```text
  Hop 1: 301 Moved Permanently -> https://example.com/products/flagship/ (38ms)
  Hop 2: 200 OK (210ms)
    - HTML Meta Robots: index, follow [PASS]
    - HTTP Header: X-Robots-Tag: noindex, nofollow [CRITICAL FAILURE]
    - Origin Header Source: Edge worker injected header meant for staging.example.com
    - GSC Root Cause: HTTP header overrides HTML meta tag per Google Search Central specifications.
  ```
- **Recommended Remediation:**
  1. Patch edge proxy configuration to restrict `X-Robots-Tag` injection to `staging.*` hostnames.
  2. Verify removal with `index-trace https://example.com/products/flagship`.
  3. Submit batch re-indexing request via Google Search Console URL Inspection API.

---

## What It Does & Why It Matters

IndexTrace diagnoses why URLs get excluded or dropped from search engine indexes by evaluating multi-layer network, protocol, and directive bottlenecks.

Google Search Console frequently reports high-level, opaque exclusion categories ("Page with redirect", "Blocked by robots.txt", "Soft 404", "Excluded by 'noindex' tag") without revealing the root failure layer.

IndexTrace inspects all layers in a single pass:
- **RFC 9309 robots.txt Resolution:** Identifies the exact rule and line number in `robots.txt` governing a URL using formal longest-match prefix precedence.
- **Sitemap Directive Discovery:** Extracts and audits declared `Sitemap:` URLs with exact line numbers to ensure crawlers can discover site content.
- **Hop-by-Hop Redirect Latency:** Measures cumulative network latency across multi-hop redirect chains and flags protocol downgrades (HTTPS to HTTP).
- **Directive Reconciliation:** Evaluates `<link rel="canonical">`, HTML `<meta name="robots">`, and HTTP `X-Robots-Tag` headers.
- **Soft-404 Detection:** Evaluates HTTP 200 responses against content density and error token heuristics.
- **Root-Cause Synthesis:** Correlates findings to output an actionable Google Search Console diagnosis with ordered remediation steps.

---

## Usage & CLI Options

```bash
# Audit a target URL
index-trace https://webaudits.pro

# Emulate Googlebot smartphone crawler
index-trace https://example.com --ua googlebot-mobile

# Trace deep redirect chains (up to 20 hops) with 15s timeout
index-trace https://example.com --max-hops 20 --timeout 15

# Export machine-readable JSON for CI/CD deployment gates
index-trace https://example.com --output json --save gsc-report.json

# Write a shareable HTML report for a client or teammate
index-trace https://example.com --format html --save index-report.html

# Show full technical evidence after the plain-language result
index-trace https://example.com --audience expert --fix-plan

# Check installed version
index-trace --version
```

---

## Example Output

```text
+-------------------------------------------------------------------------------+
| IndexTrace: Google Search Console Forensic Diagnostic Utility                 |
| Target URL: https://webaudits.pro                                             |
| Crawl & Indexation Score: 100.0/100 (Status: HEALTHY)                         |
| Total Hops: 1 | Cumulative Latency: 312ms | Robots Status: ALLOWED            |
+-------------------------------------------------------------------------------+

Hop-by-Hop Redirect Timeline:
+-----+--------+---------------+------------+------------------------+
| Hop | Status | Response Code | Latency    | Destination URL        |
+-----+--------+---------------+------------+------------------------+
| 1   | 200 OK | Final Target  | 312.4 ms   | https://webaudits.pro/ |
+-----+--------+---------------+------------+------------------------+

Robots.txt Analysis (RFC 9309):
- Crawl Access: ALLOWED
- Evaluated User-Agent: Googlebot
- Matching Rule: Line 4 (Allow: /)
- Origin robots.txt: https://webaudits.pro/robots.txt
- Declared Sitemaps: https://webaudits.pro/sitemap.xml (Line 6)

GSC Diagnostic Verdict: INDEXABLE (Clean 200 OK, zero redirect hops, canonical self-referential)
```

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

- `tracer.py`: Sequentially follows HTTP redirects up to a configurable maximum, capturing status codes, per-hop latency, and protocol changes.
- `robots_matcher.py`: Fetches origin `robots.txt` and implements RFC 9309 longest-match prefix resolution, identifying exact line numbers.
- `directives_inspector.py`: Extracts canonical tags, meta robots directives, and `X-Robots-Tag` headers from the final response.
- `verdict_engine.py`: Correlates findings to classify search engine indexability and generate prioritized developer remediation steps.

---

## Standards & Heuristics

IndexTrace evaluates URLs against official Internet RFCs and project-derived heuristics:

| Metric / Check | Classification | Authority / Basis |
|:---|:---|:---|
| Robots Exclusion Protocol | Internet Standard | IETF RFC 9309 |
| HTTP Status Codes & Redirects | Internet Standard | IETF RFC 9110 |
| Canonical Tag Syntax | Web Standard | RFC 6596 |
| GSC Exclusion Categorization | Search Engine Guidance | Google Search Central Documentation |
| Soft-404 Heuristic Classifier | Project-Derived Heuristic | Content density and error token pattern model |

---

## Limitations

- **Headless JavaScript Rendering:** Focuses on server-level HTTP redirects, headers, and robots directives; client-side `window.location` redirects require headless browser tracing (use `dom-hydrate`).
- **Single-URL Scope:** Designed for deep forensic diagnostics of individual URLs; large-scale multi-thousand URL audits should be orchestrated via batch pipelines.
- **Search Console API:** Analyzes public crawl mechanics and directive parity; it does not connect to authenticated Search Console accounts to query internal click impressions.

---

## Testing & CI

```bash
# Run unit tests
python -m unittest discover -s tests

# Output
# Ran 14 tests in 0.002s
# OK
```

Continuous integration runs automatically across Ubuntu and Windows runners on every commit via GitHub Actions.

---

## License

MIT License. See [LICENSE](LICENSE) for details.
