"""
Soft-404 Heuristic Classifier for Google Search Console Diagnosis.
"""

import re
from typing import Dict, Any, List
from bs4 import BeautifulSoup

SOFT_404_TITLE_PATTERNS = [
    re.compile(r"\b(404|not found|page not found|error 404|nothing found|does not exist)\b", re.IGNORECASE)
]

SOFT_404_BODY_PATTERNS = [
    re.compile(r"\b(the page you (are looking for|requested) (could not be found|does not exist|is not available))\b", re.IGNORECASE),
    re.compile(r"\b(page (you requested )?not found)\b", re.IGNORECASE),
    re.compile(r"\b(oops! That page can['’]t be found)\b", re.IGNORECASE),
    re.compile(r"\b(we couldn['’]t find (that|the) page)\b", re.IGNORECASE),
    re.compile(r"\b(this content is no longer available)\b", re.IGNORECASE),
    re.compile(r"\b(no (products|articles|posts|results) found)\b", re.IGNORECASE),
    re.compile(r"\b(error 404: page not found)\b", re.IGNORECASE)
]

def analyze_soft_404(status_code: int, html_content: str) -> Dict[str, Any]:
    if status_code != 200:
        return {
            "status_code": status_code,
            "is_soft_404": False,
            "probability_percent": 0,
            "verdict": "NOT_APPLICABLE (Non-200 Status)",
            "detected_signals": []
        }

    soup = BeautifulSoup(html_content, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header", "noscript", "svg"]):
        tag.decompose()

    signals: List[str] = []
    score = 0

    # 1. Title Tag Check
    title_el = soup.find("title")
    title_text = title_el.text.strip() if title_el else ""
    for pat in SOFT_404_TITLE_PATTERNS:
        if pat.search(title_text):
            score += 45
            signals.append(f"Title tag contains 404 error marker: '{title_text}'")
            break

    # 2. Heading Tags Check (H1 / H2)
    headings_text = " ".join([h.get_text() for h in soup.find_all(["h1", "h2"])])
    for pat in SOFT_404_BODY_PATTERNS:
        match = pat.search(headings_text)
        if match:
            score += 40
            signals.append(f"Primary heading contains error phrase: '{match.group(0)}'")
            break

    # 3. Body Text Content & Word Count
    body_text = soup.get_text()
    words = body_text.split()
    word_count = len(words)

    if word_count < 25:
        score += 35
        signals.append(f"Extremely thin content ({word_count} total words)")
    elif word_count < 60:
        score += 20
        signals.append(f"Very thin content ({word_count} total words)")

    # 4. Body Phrase Search
    if not any("heading contains" in s for s in signals):
        for pat in SOFT_404_BODY_PATTERNS:
            match = pat.search(body_text)
            if match:
                score += 30
                signals.append(f"Body copy contains error phrase: '{match.group(0)}'")
                break

    score = min(100, score)

    if score >= 70:
        verdict = "CONFIRMED_SOFT_404"
    elif score >= 35:
        verdict = "SUSPECTED_SOFT_404"
    else:
        verdict = "CLEAN"

    return {
        "status_code": status_code,
        "is_soft_404": (score >= 50),
        "probability_percent": score,
        "verdict": verdict,
        "word_count": word_count,
        "title": title_text,
        "detected_signals": signals
    }
