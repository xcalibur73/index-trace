"""
Line-by-line robots.txt collision matcher adhering to RFC 9309 standards.
Pinpoints exact line numbers and conflicting directives blocking GSC indexation.
"""

import re
import urllib.parse
import urllib.request
from typing import Dict, Any, List, Optional, Tuple

def pattern_to_regex(pattern: str) -> re.Pattern:
    # RFC 9309 path matching: * is any sequence of characters, $ is end of path
    escaped = ""
    i = 0
    while i < len(pattern):
        c = pattern[i]
        if c == "*":
            escaped += ".*"
        elif c == "$":
            escaped += "$"
        else:
            escaped += re.escape(c)
        i += 1
    if not pattern.endswith("$"):
        escaped += ".*"
    return re.compile("^" + escaped)

def parse_robots_with_line_numbers(robots_txt: str) -> Dict[str, List[Dict[str, Any]]]:
    records: Dict[str, List[Dict[str, Any]]] = {}
    current_agents: List[str] = []
    in_directives = False

    for line_no, raw_line in enumerate(robots_txt.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        if ":" not in line:
            continue

        key, val = line.split(":", 1)
        key = key.strip().lower()
        val = val.strip()

        if key == "user-agent":
            if in_directives:
                current_agents = []
                in_directives = False
            current_agents.append(val.lower())
        elif key in ["allow", "disallow"]:
            in_directives = True
            for agent in current_agents:
                records.setdefault(agent, []).append({
                    "type": key,
                    "pattern": val,
                    "line_number": line_no
                })

    return records

def match_robots_path(url_path: str, robots_txt: str, target_ua: str = "googlebot") -> Dict[str, Any]:
    if not robots_txt.strip():
        return {
            "status": "ALLOWED",
            "reason": "Robots.txt is empty or missing (default allow)",
            "matching_rule": None,
            "line_number": None,
            "user_agent_applied": target_ua
        }

    records = parse_robots_with_line_numbers(robots_txt)
    ua_lower = target_ua.lower()

    # RFC 9309 precedence: specific User-Agent group first, else fallback to wildcard '*'
    selected_rules: List[Dict[str, Any]] = []
    agent_applied = "*"

    if ua_lower in records:
        selected_rules = records[ua_lower]
        agent_applied = target_ua
    elif "*" in records:
        selected_rules = records["*"]
        agent_applied = "*"
    else:
        return {
            "status": "ALLOWED",
            "reason": "No applicable rules found for User-Agent (default allow)",
            "matching_rule": None,
            "line_number": None,
            "user_agent_applied": target_ua
        }

    # Ensure path begins with /
    path = url_path if url_path.startswith("/") else "/" + url_path

    # Evaluate rules: longest matching pattern wins
    best_rule: Optional[Dict[str, Any]] = None
    best_length = -1

    for rule in selected_rules:
        pattern = rule["pattern"]
        if not pattern:
            # Empty Disallow: means allow everything
            continue

        try:
            regex = pattern_to_regex(pattern)
            if regex.match(path):
                pattern_len = len(pattern)
                if pattern_len > best_length:
                    best_length = pattern_len
                    best_rule = rule
                elif pattern_len == best_length:
                    # RFC 9309: on tie, Allow wins over Disallow
                    if rule["type"] == "allow" and best_rule and best_rule["type"] == "disallow":
                        best_rule = rule
        except Exception:
            continue

    if best_rule is None:
        return {
            "status": "ALLOWED",
            "reason": "Path does not match any disallow directive",
            "matching_rule": None,
            "line_number": None,
            "user_agent_applied": agent_applied
        }

    is_blocked = (best_rule["type"] == "disallow")
    rule_type_upper = best_rule["type"].capitalize()

    return {
        "status": "BLOCKED" if is_blocked else "ALLOWED",
        "reason": f"Matched rule '{rule_type_upper}: {best_rule['pattern']}' at line {best_rule['line_number']}",
        "matching_rule": f"{rule_type_upper}: {best_rule['pattern']}",
        "line_number": best_rule["line_number"],
        "user_agent_applied": agent_applied
    }

def check_url_robots_collision(target_url: str, target_ua: str = "googlebot", timeout: int = 8) -> Dict[str, Any]:
    parsed = urllib.parse.urlparse(target_url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"

    content = ""
    found = False
    try:
        req = urllib.request.Request(robots_url, headers={"User-Agent": "IndexTrace/1.0 (+https://webaudits.pro)"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status == 200:
                content = resp.read().decode("utf-8", errors="replace")
                found = True
    except Exception as e:
        found = False

    path_with_query = parsed.path or "/"
    if parsed.query:
        path_with_query += "?" + parsed.query

    match_result = match_robots_path(path_with_query, content, target_ua=target_ua)

    return {
        "robots_url": robots_url,
        "robots_found": found,
        "path_evaluated": path_with_query,
        "target_user_agent": target_ua,
        "status": match_result["status"],
        "reason": match_result["reason"],
        "matching_rule": match_result["matching_rule"],
        "line_number": match_result["line_number"],
        "user_agent_applied": match_result["user_agent_applied"],
        "raw_content": content
    }
