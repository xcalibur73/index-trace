"""Backwards-compatibility shim for summary_report."""

from .summary_report import build_summary_report, build_human_report

__all__ = ["build_summary_report", "build_human_report"]
