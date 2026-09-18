"""
HTTP Header and HTML Meta Directives Inspector for GSC Indexing.
"""

import re
import urllib.parse
from typing import Dict, Any, List, Optional
from bs4 import BeautifulSoup

def parse_link_header_canonical(link_header: Optional[str]) -> Optional[str]:
    if not link_header:
        return None
    # Matches <https://example.com/page>; rel="canonical"
    match = re.search(r'<([^>]+)>;\s*rel=["\']?canonical["\']?', link_header, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return None

def inspect_directives(final_url: str, response_headers: Dict[str, Any], html_content: str) -> Dict[str, Any]:
    # 1. HTTP Headers
    x_robots_raw = response_headers.get("X-Robots-Tag", "")
    header_noindex = "noindex" in x_robots_raw.lower()
    header_nofollow = "nofollow" in x_robots_raw.lower()
    header_none = "none" in x_robots_raw.lower()
    header_canonical = parse_link_header_canonical(response_headers.get("Link"))

    # 2. HTML Meta Tags
    soup = BeautifulSoup(html_content, "html.parser")
    
    meta_robots_el = soup.find("meta", attrs={"name": lambda x: x and x.lower() == "robots"})
    meta_googlebot_el = soup.find("meta", attrs={"name": lambda x: x and x.lower() == "googlebot"})
    
    meta_robots_content = meta_robots_el.get("content", "").strip() if meta_robots_el else ""
    meta_googlebot_content = meta_googlebot_el.get("content", "").strip() if meta_googlebot_el else ""

    meta_noindex = (
        "noindex" in meta_robots_content.lower() or 
        "noindex" in meta_googlebot_content.lower() or
        "none" in meta_robots_content.lower()
    )
    meta_nofollow = (
        "nofollow" in meta_robots_content.lower() or
        "nofollow" in meta_googlebot_content.lower()
    )

    # 3. HTML Canonical
    html_canonical_el = soup.find("link", attrs={"rel": lambda x: x and "canonical" in [r.lower() for r in (x if isinstance(x, list) else [x])]})
    html_canonical = html_canonical_el.get("href", "").strip() if html_canonical_el else None

    # Resolve relative canonical if necessary
    resolved_html_canonical = urllib.parse.urljoin(final_url, html_canonical) if html_canonical else None
    resolved_header_canonical = urllib.parse.urljoin(final_url, header_canonical) if header_canonical else None

    effective_canonical = resolved_header_canonical or resolved_html_canonical

    # 4. Canonical Alignment Analysis
    canonical_status = "CLEAN_SELF"
    canonical_reason = "Canonical URL matches destination URL"

    if not effective_canonical:
        canonical_status = "MISSING"
        canonical_reason = "No canonical URL declared in HTTP header or HTML head"
    else:
        # Normalize for trailing slash and query comparison
        def norm(u: str) -> str:
            p = urllib.parse.urlparse(u)
            path = p.path.rstrip("/") or "/"
            return f"{p.scheme}://{p.netloc}{path}{('?' + p.query) if p.query else ''}"

        if norm(effective_canonical) != norm(final_url):
            canonical_status = "EXTERNAL_CANONICAL"
            canonical_reason = f"Canonical points away to: {effective_canonical}"

    # Check relative canonical warning
    is_relative_canonical = bool(html_canonical and not html_canonical.startswith("http://") and not html_canonical.startswith("https://"))

    # Conflict check between Header and HTML
    has_canonical_conflict = bool(
        resolved_header_canonical and resolved_html_canonical and
        resolved_header_canonical != resolved_html_canonical
    )

    is_noindex_active = header_noindex or meta_noindex or header_none

    return {
        "is_noindex_active": is_noindex_active,
        "x_robots_tag": {
            "present": bool(x_robots_raw),
            "raw": x_robots_raw,
            "has_noindex": header_noindex,
            "has_nofollow": header_nofollow
        },
        "meta_robots": {
            "present": bool(meta_robots_el or meta_googlebot_el),
            "robots_content": meta_robots_content,
            "googlebot_content": meta_googlebot_content,
            "has_noindex": meta_noindex,
            "has_nofollow": meta_nofollow
        },
        "canonical": {
            "effective_url": effective_canonical,
            "html_canonical": html_canonical,
            "header_canonical": header_canonical,
            "is_relative": is_relative_canonical,
            "has_conflict": has_canonical_conflict,
            "status": canonical_status,
            "reason": canonical_reason
        }
    }
