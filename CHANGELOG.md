# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.2.2] - 2026-09-21

### Fixed
- Prevented error page leakage: `inspect_directives` now takes `status_code` and suppresses HTML `<meta name="robots">` parsing when the response is not HTTP 200 OK. This eliminates false positive `noindex` verdicts triggered by Cloudflare, AWS WAF, or server error pages.
- Added explicit GSC synthesis verdicts for HTTP client error responses (401 Unauthorized, 403 Forbidden / WAF block, 410 Gone, 429 Rate Limited, and generic 4xx), evaluated prior to robots and noindex checks.

## [1.2.1] - 2026-09-20

### Changed
- Replaced awkward "human" terminology with professional "summary" and "detailed" detail levels across CLI `--audience` controls (supporting `summary`, `detailed`, `executive`, and `technical`).
- Renamed internal summary reporting module to `summary_report.py` and updated terminal output panels to "Executive Summary".
- Retained `human` and `expert` as seamless backwards-compatibility aliases.

## [1.2.0] - 2026-09-19

### Added
- Human-readable audit summaries with a status, impact, evidence, and recommended fixes.
- `--audience`, `--format html`, and `--fix-plan` CLI controls.
- Self-contained HTML reports with responsive findings and expandable technical evidence.

## [1.1.0] - 2026-09-19

### Added
- Automated `Sitemap:` directive discovery and validation from `robots.txt` matching RFC 9309 and search crawler conventions.
- Line number reporting for discovered sitemap directives in CLI terminal output, Markdown, and JSON.
- Dedicated unit test `test_sitemap_extraction_from_robots` validating directive extraction.

## [1.0.0] - 2026-09-19

### Added
- Initial release of index-trace: Google Search Console forensic triage utility and RFC 9309 crawler tracer.
- CLI entry point with `--output` (terminal, markdown, json) and `--version` flags.
- Standard PEP 621 packaging via `pyproject.toml`.
- GitHub Actions CI matrix workflow for Python 3.10, 3.11, and 3.12.
- Comprehensive automated unit test suite.
- Integration endpoints for the WebAudits.pro technical audit platform.

### Hardened
- Cross-platform Windows terminal encoding safety (`_safe_str` Unicode sanitization).
- Universal test discovery path resilience.
