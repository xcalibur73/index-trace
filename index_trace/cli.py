"""
Command-line interface and diagnostic orchestrator for IndexTrace.
Triage Google Search Console indexing defects and crawler collisions.
"""

import sys
import json
import argparse
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from index_trace import __version__
from index_trace.tracer import trace_redirects, USER_AGENTS
from index_trace.robots_matcher import check_url_robots_collision
from index_trace.directives_inspector import inspect_directives
from index_trace.soft404_detector import analyze_soft_404
from index_trace.verdict_engine import synthesize_gsc_verdict
from index_trace.formatters import export_html_report, export_markdown_report, print_terminal_report

CLOUD_TOOL_URL = "https://webaudits.pro/tools/index-trace"

def run_audit(
    url: str,
    user_agent: str = "googlebot",
    timeout: int = 10,
    max_hops: int = 12
) -> Dict[str, Any]:
    """
    Executes a forensic indexing diagnostic for a given URL.
    Traces redirect hops, evaluates RFC 9309 robots collisions,
    audits canonical and meta directives, and runs soft-404 heuristics.
    """
    # 1. Hop-by-hop HTTP redirect trace
    trace_data = trace_redirects(
        start_url=url,
        user_agent=user_agent,
        max_hops=max_hops,
        timeout=timeout
    )

    final_url = trace_data.get("final_url", url)
    final_status = trace_data.get("final_status_code", 0)

    # 2. Robots.txt collision analysis (RFC 9309)
    robots_data = check_url_robots_collision(
        target_url=final_url,
        target_ua=user_agent,
        timeout=timeout
    )

    # 3. Directives and soft-404 inspection
    final_resp = trace_data.get("final_response")
    if final_resp is not None:
        headers = dict(final_resp.headers)
        html_text = final_resp.text
    else:
        headers = {}
        html_text = ""

    directives_data = inspect_directives(
        final_url=final_url,
        response_headers=headers,
        html_content=html_text,
        status_code=final_status
    )

    soft404_data = analyze_soft_404(
        status_code=final_status,
        html_content=html_text
    )

    # 4. GSC diagnostic synthesis and remediation plan
    verdict_data = synthesize_gsc_verdict(
        trace_data=trace_data,
        robots_data=robots_data,
        directives_data=directives_data,
        soft404_data=soft404_data
    )

    # Clean non-serializable response object for serialization
    trace_clean = dict(trace_data)
    trace_clean.pop("final_response", None)

    return {
        "tool": "IndexTrace",
        "version": __version__,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "start_url": url,
        "final_url": final_url,
        "user_agent": user_agent,
        "trace": trace_clean,
        "robots": robots_data,
        "directives": directives_data,
        "soft404": soft404_data,
        "verdict": verdict_data,
        "cloud_url": CLOUD_TOOL_URL
    }

def main(args: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="index-trace",
        description="IndexTrace: Google Search Console Indexing Diagnostic and Crawler Collision Tracer"
    )
    parser.add_argument("url", nargs="?", help="Target URL to triage for indexing issues")
    parser.add_argument(
        "--ua",
        choices=["googlebot", "googlebot-mobile", "chrome"],
        default="googlebot",
        help="Simulated crawler User-Agent profile (default: googlebot)"
    )
    parser.add_argument(
        "--output", "--format",
        choices=["terminal", "markdown", "json", "html"],
        default="terminal",
        help="Report output format (default: terminal)"
    )
    parser.add_argument(
        "--audience",
        choices=["summary", "detailed", "executive", "technical", "human", "expert"],
        default="summary",
        help="Report detail level: summary (default) or detailed"
    )
    parser.add_argument(
        "--fix-plan",
        action="store_true",
        help="Emphasize recommended fixes in terminal output"
    )
    parser.add_argument(
        "--save",
        type=str,
        default=None,
        help="Optional file path to save report (e.g. report.md, audit.json)"
    )
    parser.add_argument(
        "--cloud",
        action="store_true",
        help="Show link to WebAudits.pro cloud diagnostic suite"
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=10,
        help="HTTP request timeout in seconds (default: 10)"
    )
    parser.add_argument(
        "--max-hops",
        type=int,
        default=12,
        help="Maximum redirect hops to trace (default: 12)"
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"IndexTrace v{__version__}"
    )

    parsed = parser.parse_args(args)

    if parsed.cloud and not parsed.url:
        print(f"\nIndexTrace Cloud Diagnostic Suite: {CLOUD_TOOL_URL}\n")
        return 0

    if not parsed.url:
        parser.print_help()
        return 0

    target_url = parsed.url
    if not target_url.startswith("http://") and not target_url.startswith("https://"):
        target_url = "https://" + target_url

    try:
        report = run_audit(
            url=target_url,
            user_agent=parsed.ua,
            timeout=parsed.timeout,
            max_hops=parsed.max_hops
        )
    except Exception as e:
        sys.stderr.write(f"Error during IndexTrace audit: {e}\n")
        return 1

    trace_data = report["trace"]
    robots_data = report["robots"]
    directives_data = report["directives"]
    soft404_data = report["soft404"]
    verdict_data = report["verdict"]

    # Handle output
    if parsed.output == "json":
        output_str = json.dumps(report, indent=2)
        print(output_str)
    elif parsed.output == "markdown":
        output_str = export_markdown_report(
            trace_data, robots_data, directives_data, soft404_data, verdict_data
        )
        print(output_str)
    elif parsed.output == "html":
        output_str = export_html_report(
            trace_data, robots_data, directives_data, soft404_data, verdict_data
        )
        print(output_str)
    else:
        output_str = None
        print_terminal_report(
            trace_data,
            robots_data,
            directives_data,
            soft404_data,
            verdict_data,
            audience=parsed.audience,
            fix_plan=parsed.fix_plan,
        )

    if parsed.cloud:
        print(f"\nWebAudits.pro Cloud Inspection: {CLOUD_TOOL_URL}")

    # Handle file save
    if parsed.save:
        save_path = parsed.save
        if save_path.endswith(".json"):
            content_to_save = json.dumps(report, indent=2)
        elif save_path.endswith(".md"):
            content_to_save = export_markdown_report(
                trace_data, robots_data, directives_data, soft404_data, verdict_data
            )
        elif save_path.endswith(".html"):
            content_to_save = export_html_report(
                trace_data, robots_data, directives_data, soft404_data, verdict_data
            )
        else:
            if output_str:
                content_to_save = output_str
            else:
                content_to_save = export_markdown_report(
                    trace_data, robots_data, directives_data, soft404_data, verdict_data
                )

        with open(save_path, "w", encoding="utf-8") as f:
            f.write(content_to_save)
        print(f"\nReport saved successfully to: {save_path}")

    return 0

if __name__ == "__main__":
    sys.exit(main())
