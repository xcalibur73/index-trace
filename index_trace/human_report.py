"""Human-readable report data for IndexTrace audits."""

from typing import Any


def build_human_report(
    trace_data: dict[str, Any],
    robots_data: dict[str, Any],
    directives_data: dict[str, Any],
    soft404_data: dict[str, Any],
    verdict_data: dict[str, Any],
) -> dict[str, Any]:
    """Translate an indexability verdict into a status and actionable finding."""
    severity = verdict_data.get("severity", "OK")
    status = {"OK": "Pass", "WARNING": "Needs attention", "CRITICAL": "Critical"}.get(
        severity, "Needs attention"
    )
    root_cause = verdict_data.get("root_cause", "No root cause was returned.")
    remediation = verdict_data.get("remediation", [])
    details = [
        f"Final HTTP status: {trace_data.get('final_status_code', 'unknown')}",
        f"Redirect hops: {trace_data.get('total_hops', 0)}",
        f"Robots access: {robots_data.get('status', 'unknown')}",
    ]
    if directives_data.get("is_noindex_active"):
        details.append("A noindex directive is active")
    if soft404_data.get("is_soft_404"):
        details.append(f"Soft-404 risk: {soft404_data.get('probability_percent', 0)}%")

    return {
        "status": status,
        "summary": root_cause,
        "findings": [{
            "severity": status,
            "title": verdict_data.get("gsc_status", "Indexability check"),
            "impact": "Search engines may not index the intended URL until this condition is resolved.",
            "evidence": "; ".join(details) + ".",
            "recommended_fix": " ".join(remediation) or "No remediation steps were returned.",
        }],
    }
