# IndexTrace: Crawl Diagnostics & Case Studies

Forensic case studies evaluating RFC 9309 robots collisions, multi-hop redirect latency accumulation, and soft-404 detection gathered during testing.

---

## Benchmark Methodology

- **Dataset:** 12 production domain endpoints representing e-commerce, developer docs, and media platforms (`github.com`, `httpbin.org`, `webaudits.pro`, etc.).
- **Sampling Method:** Deterministic direct HTTP GET requests and robots.txt extraction simulating standard search bot requests.
- **Date:** 2026-09-19
- **Tool Version:** IndexTrace v1.1.0
- **Environment:** Windows 11 / Ubuntu 22.04 LTS, Python 3.10+, 1Gbps fiber connection.
- **Command:** `index-trace <url> --ua googlebot-mobile --output json`
- **Raw Observations:** Per-hop HTTP response headers (`Location`, `X-Robots-Tag`, `Content-Length`), TLS handshake latency, RFC 9309 rule match index.
- **Calculation Method:** Cumulative redirect latency = $\sum_{i=1}^{n} \text{latency}(hop_i)$; RFC 9309 precedence = longest-matching path prefix rule wins.
- **Result:** Line-level identification of robots.txt directives, isolation of intermediate redirect latency, and directive collision classification.
- **Limitations:** Live DNS propagation delays and geographic CDN edge routing can produce varied latency numbers across testing locations.

---

## Case Study 1: RFC 9309 Line-Level Robots Collision

### Target URL
`https://github.com/search`

### Google Search Console Symptom
"Blocked by robots.txt" (GSC coverage report does not indicate which rule or line number caused the block).

### IndexTrace Diagnostic Telemetry
```text
Crawl Access Status: BLOCKED
Evaluated User-Agent: *
Evaluated Path: /search
Matching Directive: Disallow: /search$ (Line 238)
Robots.txt Location: https://github.com/robots.txt
```

### Engineering Observation
The trailing end-of-path anchor `$` in `Disallow: /search$` blocks the exact path `/search` while allowing search query paths like `/search?q=test` if matching other rules. IndexTrace isolated the exact line number (238) within a 300+ line production `robots.txt` file, eliminating manual rule auditing.

---

## Case Study 2: Multi-Hop Redirect Latency Accumulation

### Target URL
`https://httpbin.org/redirect/3`

### Google Search Console Symptom
"Redirect error" or crawl budget exhaustion on deep category hierarchies.

### IndexTrace Diagnostic Telemetry
```text
Hop 1: 302 Found       1,086.6 ms   https://httpbin.org/redirect/3      -> /relative-redirect/2
Hop 2: 302 Found       1,009.8 ms   https://httpbin.org/relative-.../2  -> /relative-redirect/1
Hop 3: 302 Found       1,045.0 ms   https://httpbin.org/relative-.../1  -> /get
Hop 4: 200 OK          1,054.8 ms   https://httpbin.org/get

Total Hops: 4 | Cumulative Network Latency: 4,196.2 ms
GSC Verdict: REDIRECT_ERROR (Excessive Hops)
```

### Engineering Observation
Each intermediate 302 redirect hop adds over 1,000ms of latency, requiring search crawlers to allocate 4.2 seconds of network connection time to retrieve a single document. Googlebot typically abandons chains exceeding 3 to 5 hops. Remediation requires collapsing intermediate hops into a direct 301 redirect from the initial URL to the final destination.

---

## Case Study 3: Protocol Normalization Hop Penalty

### Target URL
`http://github.com`

### IndexTrace Diagnostic Telemetry
```text
Hop 1: 301 Moved Permanently   112.6 ms   http://github.com    -> https://github.com/
Hop 2: 200 OK                  240.2 ms   https://github.com/

Total Hops: 2 | Cumulative Network Latency: 352.8 ms
GSC Verdict: INDEXABLE (Clean 2-hop HTTPS upgrade)
```

### Engineering Observation
Standard HTTP to HTTPS redirection executed cleanly in a single hop with 112ms overhead. Server returned proper HSTS headers and self-referential canonical on the HTTPS destination URL.
