"""
Unit test suite for IndexTrace components.
Verifies RFC 9309 robots matching, directives parsing, soft-404 heuristics, and GSC synthesis.
"""

import unittest
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from unittest.mock import patch, MagicMock

from index_trace.robots_matcher import (
    pattern_to_regex,
    parse_robots_with_line_numbers,
    match_robots_path,
    extract_sitemaps_from_robots
)
from index_trace.directives_inspector import (
    parse_link_header_canonical,
    inspect_directives
)
from index_trace.soft404_detector import analyze_soft_404
from index_trace.verdict_engine import synthesize_gsc_verdict
from index_trace.tracer import trace_redirects
from index_trace.formatters import export_html_report
from index_trace.summary_report import build_summary_report, build_human_report

class TestRobotsMatcher(unittest.TestCase):
    def test_wildcard_regex_generation(self):
        pat = pattern_to_regex("/private/*")
        self.assertTrue(pat.match("/private/dashboard"))
        self.assertTrue(pat.match("/private/secret.html"))
        self.assertFalse(pat.match("/public/home"))

    def test_line_number_and_agent_precedence(self):
        robots_sample = """# Global directives
User-agent: *
Disallow: /admin/
Allow: /admin/login

# Dedicated Googlebot directives
User-agent: Googlebot
Disallow: /temp/
Disallow: /private/data
Allow: /private/
"""
        records = parse_robots_with_line_numbers(robots_sample)
        self.assertIn("*", records)
        self.assertIn("googlebot", records)

        # Check exact line numbers
        self.assertEqual(records["*"][0]["line_number"], 3)
        self.assertEqual(records["*"][0]["pattern"], "/admin/")
        self.assertEqual(records["*"][1]["line_number"], 4)

        self.assertEqual(records["googlebot"][0]["line_number"], 8)
        self.assertEqual(records["googlebot"][0]["pattern"], "/temp/")

    def test_rfc9309_longest_match_and_allow_precedence(self):
        robots_sample = """User-agent: *
Disallow: /catalog
Allow: /catalog/public
"""
        # /catalog/public matches both, but Allow is longer (15 chars vs 8 chars) -> ALLOWED
        res1 = match_robots_path("/catalog/public/item-123", robots_sample, target_ua="googlebot")
        self.assertEqual(res1["status"], "ALLOWED")
        self.assertEqual(res1["line_number"], 3)

        # /catalog/private matches /catalog only -> BLOCKED
        res2 = match_robots_path("/catalog/private/secret", robots_sample, target_ua="googlebot")
        self.assertEqual(res2["status"], "BLOCKED")
        self.assertEqual(res2["line_number"], 2)

    def test_rfc9309_equal_length_allow_wins(self):
        robots_sample = """User-agent: *
Disallow: /page
Allow: /page
"""
        # When lengths are identical, Allow wins per RFC 9309
        res = match_robots_path("/page", robots_sample, target_ua="googlebot")
        self.assertEqual(res["status"], "ALLOWED")


class TestDirectivesInspector(unittest.TestCase):
    def test_link_header_canonical(self):
        header = '<https://example.com/canonical-page>; rel="canonical"'
        self.assertEqual(parse_link_header_canonical(header), "https://example.com/canonical-page")

        header_single_quote = "<https://example.com/item>; rel='canonical'"
        self.assertEqual(parse_link_header_canonical(header_single_quote), "https://example.com/item")

        self.assertIsNone(parse_link_header_canonical("no canonical here"))

    def test_header_noindex_detection(self):
        headers = {"X-Robots-Tag": "noindex, nofollow"}
        html = "<html><head><title>Test</title></head><body><h1>Hello</h1></body></html>"
        res = inspect_directives("https://example.com/page", headers, html)
        self.assertTrue(res["is_noindex_active"])
        self.assertTrue(res["x_robots_tag"]["has_noindex"])

    def test_meta_googlebot_noindex_detection(self):
        headers = {}
        html = '<html><head><meta name="googlebot" content="noindex, follow"><title>Page</title></head></html>'
        res = inspect_directives("https://example.com/page", headers, html)
        self.assertTrue(res["is_noindex_active"])
        self.assertTrue(res["meta_robots"]["has_noindex"])

    def test_noimageindex_false_positive_suppression(self):
        headers = {"X-Robots-Tag": "noimageindex"}
        html = '<html><head><meta name="robots" content="noimageindex"><title>Page</title></head></html>'
        res = inspect_directives("https://example.com/page", headers, html)
        self.assertFalse(res["is_noindex_active"])
        self.assertFalse(res["x_robots_tag"]["has_noindex"])
        self.assertFalse(res["meta_robots"]["has_noindex"])

    def test_canonical_alignment(self):
        headers = {}
        html_self = '<html><head><link rel="canonical" href="https://example.com/test"/></head></html>'
        res_self = inspect_directives("https://example.com/test", headers, html_self)
        self.assertEqual(res_self["canonical"]["status"], "CLEAN_SELF")

        html_external = '<html><head><link rel="canonical" href="https://example.com/master-page"/></head></html>'
        res_ext = inspect_directives("https://example.com/variant-page", headers, html_external)
        self.assertEqual(res_ext["canonical"]["status"], "EXTERNAL_CANONICAL")


class TestSoft404Detector(unittest.TestCase):
    def test_soft404_title_marker(self):
        html = "<html><head><title>404 Not Found - My Store</title></head><body>We could not find the page you requested.</body></html>"
        res = analyze_soft_404(200, html)
        self.assertTrue(res["is_soft_404"])
        self.assertIn("Title tag contains 404 error marker", res["detected_signals"][0])

    def test_clean_rich_page(self):
        html = """<html><head><title>Expert Technical SEO Services</title></head><body>
        <h1>Comprehensive Organic Search Diagnostics</h1>
        <p>""" + ("We optimize web architectures for crawl efficiency, indexing precision, and maximum organic visibility. " * 10) + """</p>
        </body></html>"""
        res = analyze_soft_404(200, html)
        self.assertFalse(res["is_soft_404"])
        self.assertEqual(res["verdict"], "CLEAN")

    def test_non_200_status(self):
        res = analyze_soft_404(404, "<html><body>Not Found</body></html>")
        self.assertFalse(res["is_soft_404"])
        self.assertEqual(res["probability_percent"], 0)


class TestVerdictEngine(unittest.TestCase):
    def test_infinite_loop_verdict(self):
        trace = {
            "start_url": "https://example.com/a",
            "is_loop": True,
            "loop_url": "https://example.com/a",
            "hops": [{"url": "https://example.com/a", "status_code": 301, "location": "https://example.com/a"}]
        }
        verdict = synthesize_gsc_verdict(trace, {"status": "ALLOWED"}, {"is_noindex_active": False}, {"is_soft_404": False})
        self.assertIn("REDIRECT_ERROR (Infinite Loop)", verdict["gsc_status"])
        self.assertEqual(verdict["severity"], "CRITICAL")
        self.assertFalse(verdict["is_indexable"])

    def test_robots_blocked_verdict(self):
        trace = {"start_url": "https://example.com/admin", "final_status_code": 200, "is_loop": False}
        robots = {
            "status": "BLOCKED",
            "matching_rule": "Disallow: /admin/",
            "line_number": 12,
            "robots_url": "https://example.com/robots.txt"
        }
        verdict = synthesize_gsc_verdict(trace, robots, {"is_noindex_active": False}, {"is_soft_404": False})
        self.assertEqual(verdict["gsc_status"], "BLOCKED_BY_ROBOTS_TXT")
        self.assertFalse(verdict["is_indexable"])
        self.assertIn("line 12", verdict["root_cause"])

    def test_clean_indexable_verdict(self):
        trace = {"start_url": "https://example.com/blog", "final_status_code": 200, "is_loop": False, "hops": []}
        robots = {"status": "ALLOWED"}
        directives = {"is_noindex_active": False, "canonical": {"status": "CLEAN_SELF"}}
        soft404 = {"is_soft_404": False}
        verdict = synthesize_gsc_verdict(trace, robots, directives, soft404)
        self.assertEqual(verdict["gsc_status"], "CLEAN_INDEXABLE")
        self.assertTrue(verdict["is_indexable"])
        self.assertEqual(verdict["severity"], "OK")

    def test_sitemap_extraction_from_robots(self):
        sample_robots = """
        User-agent: *
        Disallow: /admin/
        
        Sitemap: https://example.com/sitemap.xml
        Sitemap: https://example.com/sitemap-posts.xml
        """
        sitemaps = extract_sitemaps_from_robots(sample_robots)
        self.assertEqual(len(sitemaps), 2)
        self.assertEqual(sitemaps[0]["url"], "https://example.com/sitemap.xml")
        self.assertEqual(sitemaps[1]["url"], "https://example.com/sitemap-posts.xml")
        self.assertEqual(sitemaps[0]["line_number"], 5)


class TestSummaryReport(unittest.TestCase):
    def test_summary_report_translates_robots_block(self):
        report = build_summary_report(
            {"final_status_code": 200, "total_hops": 0},
            {"status": "BLOCKED"},
            {"is_noindex_active": False},
            {"is_soft_404": False},
            {
                "severity": "CRITICAL",
                "gsc_status": "BLOCKED_BY_ROBOTS_TXT",
                "root_cause": "Blocked by a robots.txt rule.",
                "remediation": ["Narrow the blocking rule."],
            },
        )

        self.assertEqual(report["status"], "Critical")
        self.assertEqual(report["findings"][0]["recommended_fix"], "Narrow the blocking rule.")
        # Ensure backward compatibility alias functions identically
        alias_report = build_human_report(
            {"final_status_code": 200, "total_hops": 0},
            {"status": "BLOCKED"},
            {"is_noindex_active": False},
            {"is_soft_404": False},
            {
                "severity": "CRITICAL",
                "gsc_status": "BLOCKED_BY_ROBOTS_TXT",
                "root_cause": "Blocked by a robots.txt rule.",
                "remediation": ["Narrow the blocking rule."],
            },
        )
        self.assertEqual(alias_report["status"], "Critical")

    def test_html_report_contains_fix_and_trace(self):
        report = export_html_report(
            {"start_url": "https://example.com", "final_status_code": 200, "total_hops": 1, "hops": []},
            {"status": "ALLOWED", "matching_rule": None},
            {"canonical": {"status": "CLEAN_SELF"}, "is_noindex_active": False},
            {"is_soft_404": False},
            {
                "severity": "OK",
                "gsc_status": "CLEAN_INDEXABLE",
                "root_cause": "No indexing barriers found.",
                "remediation": ["No action required."],
            },
        )

        self.assertIn("Recommended fix", report)
        self.assertIn("Technical evidence", report)
        self.assertIn("No action required.", report)

    def test_error_page_html_noindex_suppressed_on_non_200(self):
        # Cloudflare / WAF 403 error page with meta robots noindex
        headers = {"Server": "cloudflare"}
        error_html = '<html><head><meta name="robots" content="noindex, nofollow"><title>403 Forbidden</title></head><body>Access Denied</body></html>'
        
        # When status_code is 403, error page HTML meta must NOT activate is_noindex_active
        res_403 = inspect_directives("https://example.com/blocked", headers, error_html, status_code=403)
        self.assertFalse(res_403["is_noindex_active"])
        self.assertEqual(res_403["canonical"]["status"], "NON_200_RESPONSE")

        # When status_code is 200, meta robots IS processed
        res_200 = inspect_directives("https://example.com/blocked", headers, error_html, status_code=200)
        self.assertTrue(res_200["is_noindex_active"])

    def test_client_error_verdicts(self):
        # 403 Forbidden / WAF block
        trace_403 = {"start_url": "https://example.com/api", "final_status_code": 403, "is_loop": False}
        verdict_403 = synthesize_gsc_verdict(trace_403, {"status": "ALLOWED"}, {"is_noindex_active": True}, {"is_soft_404": False})
        self.assertEqual(verdict_403["gsc_status"], "ACCESS_FORBIDDEN (403)")
        self.assertEqual(verdict_403["severity"], "CRITICAL")
        self.assertFalse(verdict_403["is_indexable"])

        # 401 Unauthorized
        trace_401 = {"start_url": "https://example.com/admin", "final_status_code": 401, "is_loop": False}
        verdict_401 = synthesize_gsc_verdict(trace_401, {"status": "ALLOWED"}, {"is_noindex_active": False}, {"is_soft_404": False})
        self.assertEqual(verdict_401["gsc_status"], "UNAUTHORIZED (401)")
        self.assertFalse(verdict_401["is_indexable"])

        # 410 Gone
        trace_410 = {"start_url": "https://example.com/old", "final_status_code": 410, "is_loop": False}
        verdict_410 = synthesize_gsc_verdict(trace_410, {"status": "ALLOWED"}, {"is_noindex_active": False}, {"is_soft_404": False})
        self.assertEqual(verdict_410["gsc_status"], "GONE (410)")
        self.assertFalse(verdict_410["is_indexable"])

        # 429 Rate Limited
        trace_429 = {"start_url": "https://example.com/feed", "final_status_code": 429, "is_loop": False}
        verdict_429 = synthesize_gsc_verdict(trace_429, {"status": "ALLOWED"}, {"is_noindex_active": False}, {"is_soft_404": False})
        self.assertEqual(verdict_429["gsc_status"], "RATE_LIMITED (429)")
        self.assertFalse(verdict_429["is_indexable"])


if __name__ == "__main__":
    unittest.main()
