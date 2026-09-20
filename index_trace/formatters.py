"""
Terminal and Markdown formatters for IndexTrace audits.
"""

import html
from typing import Dict, Any

from .summary_report import build_summary_report

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.text import Text
    HAS_RICH = True
except ImportError:
    HAS_RICH = False


def _safe_str(text: Any) -> str:
    if not isinstance(text, str):
        text = str(text or "")
    text = (
        text.replace("\u2192", "->")
        .replace("\u2190", "<-")
        .replace("\u2194", "<->")
        .replace("\u2022", "*")
        .replace("\u2019", "'")
        .replace("\u2018", "'")
        .replace("\u201c", '"')
        .replace("\u201d", '"')
        .replace("\u2014", "-")
        .replace("\u2013", "-")
    )
    return text.encode("ascii", errors="replace").decode("ascii")


def _print_executive_summary(report: Dict[str, Any], fix_plan: bool) -> None:
    if HAS_RICH:
        color = {"Pass": "green", "Needs attention": "yellow", "Critical": "red"}[report["status"]]
        content = Text()
        content.append(f"{report['status']}: ", style=f"bold {color}")
        content.append(report["summary"])
        console = Console()
        console.print(Panel(content, title="Executive Summary", border_style=color))
        if report["findings"]:
            finding = report["findings"][0]
            title = "Fix plan" if fix_plan else "Recommended fix"
            console.print(Panel(_safe_str(finding["recommended_fix"]), title=title, border_style=color))
        return

    print(f"\n{report['status']}: {report['summary']}")
    if fix_plan:
        for finding in report["findings"]:
            print(f"- {finding['recommended_fix']}")

_print_human_summary = _print_executive_summary


def print_terminal_report(
    trace_data: Dict[str, Any],
    robots_data: Dict[str, Any],
    directives_data: Dict[str, Any],
    soft404_data: Dict[str, Any],
    verdict_data: Dict[str, Any],
    audience: str = "summary",
    fix_plan: bool = False,
):
    summary_report = build_summary_report(
        trace_data, robots_data, directives_data, soft404_data, verdict_data
    )
    _print_executive_summary(summary_report, fix_plan)
    if audience in ("summary", "executive", "human"):
        return

    if not HAS_RICH:
        print(f"\n=== IndexTrace GSC Diagnosis: {trace_data.get('start_url')} ===")
        print(f"GSC Status: {verdict_data.get('gsc_status')}")
        print(f"Root Cause: {verdict_data.get('root_cause')}")
        print(f"Total Hops: {trace_data.get('total_hops')} | Final Status: {trace_data.get('final_status_code')}")
        print("\nRemediation:")
        for r in verdict_data.get("remediation", []):
            print(f"- {r}")
        return

    console = Console()
    status = verdict_data.get("gsc_status", "UNKNOWN")
    severity = verdict_data.get("severity", "OK")
    status_color = "green" if severity == "OK" else ("yellow" if severity == "WARNING" else "red")

    # Header Panel
    header = Text()
    header.append("IndexTrace: Google Search Console Forensic Diagnostic\n", style="bold cyan")
    header.append(f"Target: {_safe_str(trace_data.get('start_url'))}\n", style="bold white")
    header.append(f"GSC Diagnosis: {status}\n", style=f"bold {status_color}")
    header.append(f"Root Cause: {_safe_str(verdict_data.get('root_cause'))}", style="dim")

    console.print(Panel(header, border_style=status_color))

    # 1. Hop-by-Hop Redirect Tracer Table
    hop_table = Table(title="Hop-by-Hop Redirect Chain", show_header=True, header_style="bold blue")
    hop_table.add_column("Hop", style="dim", width=4)
    hop_table.add_column("Status", style="bold")
    hop_table.add_column("Latency", style="dim")
    hop_table.add_column("URL", style="white")
    hop_table.add_column("Next Location", style="cyan")

    for h in trace_data.get("hops", []):
        sc = h["status_code"]
        sc_color = "green" if sc == 200 else ("yellow" if 300 <= sc < 400 else "red")
        loc_str = _safe_str(h["location"] or "")
        hop_table.add_row(
            str(h["hop"]),
            f"[{sc_color}]{sc}[/{sc_color}]",
            f"{h['latency_ms']} ms",
            _safe_str(h["url"]),
            loc_str
        )

    console.print(hop_table)

    # 2. Robots.txt Collision & Crawl Permissions Table
    rob_table = Table(title="Robots.txt Crawl Collision Analysis (RFC 9309)", show_header=True, header_style="bold magenta")
    rob_table.add_column("Field", style="white", width=22)
    rob_table.add_column("Evaluated Value", style="bold")

    st_color = "green" if robots_data.get("status") == "ALLOWED" else "red"
    rob_table.add_row("Crawl Access Status", f"[{st_color}]{robots_data.get('status')}[/{st_color}]")
    rob_table.add_row("Evaluated User-Agent", robots_data.get("user_agent_applied", "*"))
    rob_table.add_row("Evaluated Path", robots_data.get("path_evaluated", "/"))

    match_rule = robots_data.get("matching_rule") or "None (Default Allow)"
    line_no = f"Line {robots_data.get('line_number')}" if robots_data.get("line_number") else "N/A"
    rob_table.add_row("Matching Directive", f"{match_rule} ({line_no})")
    rob_table.add_row("Robots.txt File Location", robots_data.get("robots_url", "N/A"))

    sitemaps = robots_data.get("sitemaps", [])
    if sitemaps:
        s_summary = ", ".join(f"{s['url']} (Line {s['line_number']})" for s in sitemaps[:2])
        if len(sitemaps) > 2:
            s_summary += f" +{len(sitemaps) - 2} more"
        rob_table.add_row("Declared Sitemaps", f"[green]{_safe_str(s_summary)}[/green]")
    else:
        rob_table.add_row("Declared Sitemaps", "[yellow]None declared in robots.txt[/yellow]")

    console.print(rob_table)

    # 3. Directives & Canonical Alignment Table
    dir_table = Table(title="Directives & Canonical Tag Integrity", show_header=True, header_style="bold yellow")
    dir_table.add_column("Directive Check", style="white", width=24)
    dir_table.add_column("State", style="bold")
    dir_table.add_column("Details", style="dim")

    x_rob = directives_data.get("x_robots_tag", {})
    dir_table.add_row(
        "X-Robots-Tag (Header)",
        "[red]NOINDEX[/red]" if x_rob.get("has_noindex") else "[green]INDEXABLE[/green]",
        x_rob.get("raw") or "(Header not present)"
    )

    m_rob = directives_data.get("meta_robots", {})
    dir_table.add_row(
        "Meta Robots (HTML)",
        "[red]NOINDEX[/red]" if m_rob.get("has_noindex") else "[green]INDEXABLE[/green]",
        m_rob.get("robots_content") or "(Meta tag empty or absent)"
    )

    canon = directives_data.get("canonical", {})
    c_status = canon.get("status", "CLEAN_SELF")
    c_color = "green" if c_status == "CLEAN_SELF" else "yellow"
    dir_table.add_row(
        "Canonical Tag Alignment",
        f"[{c_color}]{c_status}[/{c_color}]",
        canon.get("effective_url") or "(No canonical declared)"
    )

    if soft404_data.get("status_code", 200) == 200:
        s_verdict = soft404_data.get("verdict", "CLEAN")
        s_color = "green" if s_verdict == "CLEAN" else "red"
        dir_table.add_row(
            "Soft-404 Classifier",
            f"[{s_color}]{s_verdict}[/{s_color}]",
            f"{soft404_data.get('probability_percent')}% risk | {soft404_data.get('word_count')} words"
        )

    console.print(dir_table)

    # 4. Engineering Remediation Panel
    rem_text = Text()
    for i, r in enumerate(verdict_data.get("remediation", []), 1):
        rem_text.append(f"{i}. {_safe_str(r)}\n", style="bold white")

    console.print(Panel(rem_text, title="Step-by-Step Engineering Remediation", border_style="yellow"))

def export_markdown_report(
    trace_data: Dict[str, Any],
    robots_data: Dict[str, Any],
    directives_data: Dict[str, Any],
    soft404_data: Dict[str, Any],
    verdict_data: Dict[str, Any]
) -> str:
    md = []
    md.append(f"# IndexTrace GSC Forensic Audit: {trace_data.get('start_url')}\n")
    md.append(f"**GSC Status**: `{verdict_data.get('gsc_status')}`  ")
    md.append(f"**Root Cause**: {verdict_data.get('root_cause')}  ")
    md.append(f"**Total Hops**: {trace_data.get('total_hops')} | **Final Status**: `{trace_data.get('final_status_code')}`\n")

    md.append("## 1. Hop-by-Hop Redirect Chain\n")
    md.append("| Hop | Status | Latency | URL | Next Location |")
    md.append("|:---:|:---:|:---:|:---|:---|")
    for h in trace_data.get("hops", []):
        md.append(f"| {h['hop']} | `{h['status_code']}` | {h['latency_ms']} ms | {h['url']} | {h['location'] or '-'} |")

    md.append("\n## 2. Robots.txt Collision Analysis\n")
    md.append(f"- **Crawl Status**: **{robots_data.get('status')}**")
    md.append(f"- **Matching Rule**: `{robots_data.get('matching_rule') or 'None'}` (Line {robots_data.get('line_number') or 'N/A'})")
    md.append(f"- **User-Agent Applied**: `{robots_data.get('user_agent_applied')}`")
    md.append(f"- **Evaluated Path**: `{robots_data.get('path_evaluated')}`")

    md.append("\n## 3. Directives & Canonical Tag Alignment\n")
    canon = directives_data.get("canonical", {})
    md.append(f"- **Canonical URL**: `{canon.get('effective_url') or 'None'}` ({canon.get('status')})")
    md.append(f"- **X-Robots-Tag**: `{directives_data.get('x_robots_tag', {}).get('raw') or 'None'}`")
    md.append(f"- **Meta Robots**: `{directives_data.get('meta_robots', {}).get('robots_content') or 'None'}`")
    md.append(f"- **Soft-404 Risk**: **{soft404_data.get('verdict')}** ({soft404_data.get('probability_percent')}%)")

    md.append("\n## 4. Engineering Remediation Steps\n")
    for i, r in enumerate(verdict_data.get("remediation", []), 1):
        md.append(f"{i}. {r}")

    return "\n".join(md)


def export_html_report(
    trace_data: Dict[str, Any],
    robots_data: Dict[str, Any],
    directives_data: Dict[str, Any],
    soft404_data: Dict[str, Any],
    verdict_data: Dict[str, Any],
) -> str:
    """Return a self-contained HTML report with executive findings."""
    report = build_summary_report(
        trace_data, robots_data, directives_data, soft404_data, verdict_data
    )
    finding = report["findings"][0]
    status_class = report["status"].lower().replace(" ", "-")
    hop_rows = "".join(
        f"<tr><td>{html.escape(str(hop.get('hop')))}</td><td>{html.escape(str(hop.get('status_code')))}</td>"
        f"<td>{html.escape(str(hop.get('latency_ms')))} ms</td><td>{html.escape(str(hop.get('url')))}</td></tr>"
        for hop in trace_data.get("hops", [])
    ) or "<tr><td colspan='4'>No redirect hops recorded.</td></tr>"
    return f"""<!doctype html>
<html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width, initial-scale=1'>
<title>IndexTrace report</title><style>
:root {{ color-scheme:light; --ink:#20201e; --muted:#716c64; --line:#ddd7ce; --paper:#f7f4ee; --panel:#fff; --accent:#b76345; --good:#216e4e; --warn:#9a6700; --bad:#b42318; }}
* {{ box-sizing:border-box; }} body {{ margin:0; background:var(--paper); color:var(--ink); font:16px/1.55 Georgia,serif; }} main {{ width:min(920px,calc(100% - 32px)); margin:48px auto; }} h1,h2 {{ line-height:1.15; }} .eyebrow,.severity {{ margin:0; font:700 12px/1.2 Arial,sans-serif; letter-spacing:.08em; text-transform:uppercase; }} .status {{ border-left:6px solid var(--accent); padding:24px; background:var(--panel); }} .pass {{ border-color:var(--good); }} .needs-attention {{ border-color:var(--warn); }} .critical {{ border-color:var(--bad); }} .finding,details {{ margin-top:16px; padding:20px 24px; background:var(--panel); border:1px solid var(--line); }} .severity.pass {{ color:var(--good); }} .severity.needs-attention {{ color:var(--warn); }} .severity.critical {{ color:var(--bad); }} table {{ width:100%; border-collapse:collapse; margin-top:12px; font-family:Arial,sans-serif; font-size:14px; }} th,td {{ padding:12px; border-bottom:1px solid var(--line); text-align:left; vertical-align:top; overflow-wrap:anywhere; }} summary {{ cursor:pointer; font-weight:700; }} @media (max-width:600px) {{ main {{ width:min(100% - 24px,920px); margin:24px auto; }} .status,.finding,details {{ padding:18px; }} }}
</style></head><body><main>
<p class='eyebrow'>IndexTrace report</p><h1>{html.escape(str(trace_data.get('start_url')))}</h1>
<section class='status {status_class}'><p class='severity {status_class}'>{html.escape(report['status'])}</p><p>{html.escape(report['summary'])}</p></section>
<section class='finding'><p class='severity {status_class}'>{html.escape(finding['severity'])}</p><h2>{html.escape(finding['title'])}</h2><p><strong>Why it matters:</strong> {html.escape(finding['impact'])}</p><p><strong>Evidence:</strong> {html.escape(finding['evidence'])}</p><p><strong>Recommended fix:</strong> {html.escape(finding['recommended_fix'])}</p></section>
<details><summary>Technical evidence</summary><p>Robots access: {html.escape(str(robots_data.get('status')))}. Matching rule: {html.escape(str(robots_data.get('matching_rule') or 'None'))}. Canonical status: {html.escape(str(directives_data.get('canonical', {}).get('status')))}.</p><table><thead><tr><th>Hop</th><th>Status</th><th>Latency</th><th>URL</th></tr></thead><tbody>{hop_rows}</tbody></table></details>
</main></body></html>"""
