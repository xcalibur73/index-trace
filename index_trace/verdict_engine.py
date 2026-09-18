"""
Google Search Console Diagnostic Synthesis & Remediation Engine.
"""

from typing import Dict, Any, List

def synthesize_gsc_verdict(
    trace_data: Dict[str, Any],
    robots_data: Dict[str, Any],
    directives_data: Dict[str, Any],
    soft404_data: Dict[str, Any]
) -> Dict[str, Any]:
    hops = trace_data.get("hops", [])
    final_status = trace_data.get("final_status_code", 0)
    is_loop = trace_data.get("is_loop", False)
    is_excessive_hops = trace_data.get("is_excessive_hops", False)
    has_mixed_protocol = trace_data.get("has_mixed_protocol", False)

    is_robots_blocked = (robots_data.get("status") == "BLOCKED")
    is_noindex = directives_data.get("is_noindex_active", False)
    canonical_status = directives_data.get("canonical", {}).get("status", "CLEAN_SELF")
    canonical_target = directives_data.get("canonical", {}).get("effective_url")
    is_soft404 = soft404_data.get("is_soft_404", False)

    # 1. Redirect Errors
    if is_loop:
        return {
            "gsc_status": "REDIRECT_ERROR (Infinite Loop)",
            "severity": "CRITICAL",
            "is_indexable": False,
            "root_cause": f"Infinite redirect loop detected: URL '{trace_data.get('loop_url')}' was visited multiple times in the chain.",
            "remediation": [
                "Audit web server rewrite rules (Nginx/Apache/.htaccess) for circular rewrite conditions.",
                "Verify trailing-slash rules and ensure HTTPS enforcement does not loop back to HTTP.",
                "Clear reverse proxy / CDN edge cache rules that may be caching outdated Location headers."
            ]
        }

    if is_excessive_hops:
        return {
            "gsc_status": "REDIRECT_ERROR (Excessive Hops)",
            "severity": "WARNING",
            "is_indexable": True if final_status == 200 and not is_noindex and not is_robots_blocked else False,
            "root_cause": f"Redirect chain contains {trace_data.get('total_hops')} hops. Googlebot typically abandons crawling chains exceeding 3-5 hops.",
            "remediation": [
                f"Collapse intermediate redirect hops so initial URL '{trace_data.get('start_url')}' points directly to '{trace_data.get('final_url')}'.",
                "Ensure protocol (HTTP -> HTTPS) and host (non-www -> www) normalization occur in a single 301 response."
            ]
        }

    # 2. Server Errors (5xx)
    if 500 <= final_status < 600:
        return {
            "gsc_status": "SERVER_ERROR (5xx)",
            "severity": "CRITICAL",
            "is_indexable": False,
            "root_cause": f"Server returned HTTP {final_status} gateway or backend error at final destination.",
            "remediation": [
                "Inspect web application backend logs and PHP-FPM / Node.js error stacks for unhandled exceptions.",
                "Verify upstream reverse proxy timeouts (e.g. Nginx proxy_read_timeout) if receiving 502/504 errors.",
                "Check server resource utilization (CPU, memory exhaustion) causing dropped crawler requests."
            ]
        }

    # 3. Client Errors (4xx)
    if final_status == 404:
        return {
            "gsc_status": "NOT_FOUND (404)",
            "severity": "CRITICAL",
            "is_indexable": False,
            "root_cause": f"Destination URL returned HTTP 404 Not Found.",
            "remediation": [
                "If the page was permanently moved, deploy a permanent 301 redirect to the closest relevant replacement URL.",
                "If intentionally deleted, return HTTP 410 Gone to signal immediate de-indexation to search engines.",
                "Update internal site navigation and XML sitemaps to purge the broken link."
            ]
        }

    # 4. Robots.txt Blocked
    if is_robots_blocked:
        return {
            "gsc_status": "BLOCKED_BY_ROBOTS_TXT",
            "severity": "CRITICAL",
            "is_indexable": False,
            "root_cause": f"Blocked from search crawling by rule '{robots_data.get('matching_rule')}' at line {robots_data.get('line_number')} in robots.txt.",
            "remediation": [
                f"Remove or narrow the disallow pattern '{robots_data.get('matching_rule')}' in '{robots_data.get('robots_url')}'.",
                "If using a CMS plugin (e.g. WordPress Yoast / Rank Math), check dynamic robots.txt configuration settings.",
                "Note: Blocking a page in robots.txt does NOT prevent it from being indexed if external backlinks exist (use 'noindex' instead if de-indexation is desired)."
            ]
        }

    # 5. Noindex Directive
    if is_noindex:
        where = []
        if directives_data.get("x_robots_tag", {}).get("has_noindex"):
            where.append("HTTP Header 'X-Robots-Tag: noindex'")
        if directives_data.get("meta_robots", {}).get("has_noindex"):
            where.append("HTML '<meta name=\"robots\" content=\"noindex\">'")
        where_str = " and ".join(where)

        return {
            "gsc_status": "EXCLUDED_BY_NOINDEX",
            "severity": "CRITICAL",
            "is_indexable": False,
            "root_cause": f"Explicit noindex directive detected in: {where_str}.",
            "remediation": [
                f"Remove the 'noindex' directive from {where_str} if this page should rank in search results.",
                "Check deployment pipeline and staging environment variables that may have inadvertently deployed production with staging noindex flags."
            ]
        }

    # 6. Soft 404
    if is_soft404:
        return {
            "gsc_status": "SOFT_404_DETECTED",
            "severity": "CRITICAL",
            "is_indexable": False,
            "root_cause": f"Server returns HTTP 200 OK, but page content matches 404 error patterns ({soft404_data.get('probability_percent')}% confidence).",
            "remediation": [
                "Configure web server to return a genuine HTTP 404 or 410 status code instead of rendering an error template with HTTP 200.",
                "If the page has genuine content, expand the body copy beyond thin placeholder snippets (currently {soft404_data.get('word_count')} words)."
            ]
        }

    # 7. Canonical Discrepancy
    if canonical_status == "EXTERNAL_CANONICAL":
        return {
            "gsc_status": "ALTERNATE_PAGE_WITH_PROPER_CANONICAL",
            "severity": "WARNING",
            "is_indexable": False,
            "root_cause": f"Page declares an external canonical pointing to: '{canonical_target}'. This URL will pass indexation equity to the canonical destination.",
            "remediation": [
                "Verify if this page is intended to be canonical. If it should be indexed independently, update canonical to point to itself.",
                "If this is a duplicate or variant (e.g. tracking parameters or pagination), maintain the current canonical configuration."
            ]
        }

    if canonical_status == "MISSING":
        return {
            "gsc_status": "INDEXABLE_WITH_WARNING (Missing Canonical)",
            "severity": "WARNING",
            "is_indexable": True,
            "root_cause": "Page returns HTTP 200 OK and is indexable, but no self-referential canonical tag is declared.",
            "remediation": [
                f"Add a self-referential '<link rel=\"canonical\" href=\"{trace_data.get('final_url')}\">' in the HTML head to prevent duplicate parameter indexing."
            ]
        }

    # 8. Clean Indexable
    return {
        "gsc_status": "CLEAN_INDEXABLE",
        "severity": "OK",
        "is_indexable": True,
        "root_cause": "Page returns clean HTTP 200 OK, self-canonicalized, allowed in robots.txt, and free of noindex tags.",
        "remediation": [
            "No technical indexing barriers detected. Page is fully eligible for Google search indexation."
        ]
    }
