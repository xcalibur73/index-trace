"""
Hop-by-hop HTTP redirect tracer and protocol inspector.
"""

import time
import urllib.parse
from typing import Dict, Any, List, Optional
import requests

USER_AGENTS = {
    "googlebot": "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
    "googlebot-mobile": "Mozilla/5.0 (Linux; Android 6.0.1; Nexus 5X Build/MMB29P) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Mobile Safari/537.36 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
    "chrome": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
}

def trace_redirects(start_url: str, user_agent: str = "googlebot", max_hops: int = 12, timeout: int = 10) -> Dict[str, Any]:
    ua = USER_AGENTS.get(user_agent.lower(), user_agent)
    headers = {
        "User-Agent": ua,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9"
    }

    current_url = start_url
    visited_urls = set()
    hops: List[Dict[str, Any]] = []
    is_loop = False
    loop_url = None
    has_mixed_protocol = False
    temp_redirects_count = 0
    final_response = None
    error_message = None

    for hop_idx in range(1, max_hops + 1):
        if current_url in visited_urls:
            is_loop = True
            loop_url = current_url
            break

        visited_urls.add(current_url)
        parsed = urllib.parse.urlparse(current_url)

        start_time = time.perf_counter()
        try:
            resp = requests.get(current_url, headers=headers, timeout=timeout, allow_redirects=False)
            latency_ms = round((time.perf_counter() - start_time) * 1000, 1)
        except requests.RequestException as e:
            error_message = str(e)
            hops.append({
                "hop": hop_idx,
                "url": current_url,
                "status_code": 0,
                "latency_ms": round((time.perf_counter() - start_time) * 1000, 1),
                "error": error_message,
                "protocol": parsed.scheme
            })
            break

        location = resp.headers.get("Location")
        x_robots = resp.headers.get("X-Robots-Tag")
        content_type = resp.headers.get("Content-Type", "")
        server = resp.headers.get("Server", "Unknown")

        hop_info = {
            "hop": hop_idx,
            "url": current_url,
            "status_code": resp.status_code,
            "latency_ms": latency_ms,
            "protocol": parsed.scheme,
            "location": location,
            "x_robots_tag": x_robots,
            "content_type": content_type,
            "server": server
        }
        hops.append(hop_info)

        if resp.status_code in [302, 307]:
            temp_redirects_count += 1

        if 300 <= resp.status_code < 400 and location:
            next_url = urllib.parse.urljoin(current_url, location)
            next_parsed = urllib.parse.urlparse(next_url)

            # Check HTTPS -> HTTP protocol downgrade
            if parsed.scheme == "https" and next_parsed.scheme == "http":
                has_mixed_protocol = True

            current_url = next_url
        else:
            final_response = resp
            break

    total_hops = len(hops)
    final_hop = hops[-1] if hops else None
    final_url = final_hop["url"] if final_hop else current_url
    final_status = final_hop["status_code"] if final_hop else 0

    return {
        "start_url": start_url,
        "final_url": final_url,
        "final_status_code": final_status,
        "total_hops": total_hops,
        "hops": hops,
        "is_loop": is_loop,
        "loop_url": loop_url,
        "has_mixed_protocol": has_mixed_protocol,
        "temporary_redirects_count": temp_redirects_count,
        "is_excessive_hops": total_hops > 3,
        "error": error_message,
        "final_response": final_response
    }
