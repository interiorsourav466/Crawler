from __future__ import annotations


def analyze_seo(data: dict[str, object]) -> dict[str, object]:
    headings = data["headings"]
    images = data["images"]
    issues: list[dict[str, str]] = []

    title = str(data["title"])
    description = str(data["meta_description"])
    h1s = headings["h1"]
    if not title:
        issues.append(_issue("missing_title", "critical", "Missing title", "Add a unique, descriptive title."))
    elif len(title) > 60:
        issues.append(_issue("long_title", "warning", "Title is longer than 60 characters", "Keep the title concise."))
    if not description:
        issues.append(_issue("missing_meta_description", "critical", "Missing meta description", "Add a useful meta description."))
    elif len(description) > 160:
        issues.append(_issue("long_meta_description", "warning", "Meta description is longer than 160 characters", "Keep it within the recommended length."))
    if not h1s:
        issues.append(_issue("missing_h1", "critical", "Missing H1", "Add one descriptive H1 heading."))
    elif len(h1s) > 1:
        issues.append(_issue("multiple_h1", "warning", "Multiple H1 headings", "Use one primary H1 heading."))
    if not data["canonical"]:
        issues.append(_issue("missing_canonical", "warning", "Missing canonical URL", "Add a canonical link when appropriate."))
    missing_alt = sum(not str(image["alt"]).strip() for image in images)
    if missing_alt:
        issues.append(_issue("missing_image_alt", "warning", f"{missing_alt} image(s) missing alt text", "Add meaningful alt text or an empty alt for decorative images."))
    if int(data["word_count"]) < MIN_WORD_COUNT:
        issues.append(_issue("thin_content", "warning", "Low visible word count", "Review whether the page provides enough useful content."))

    deductions = sum(5 if issue["severity"] == "critical" else 2 for issue in issues)
    score = max(0, 100 - deductions)
    return {"issues": issues, "score": score, "missing_alt": missing_alt}


def _issue(issue_type: str, severity: str, message: str, recommendation: str) -> dict[str, str]:
    return {"issue_type": issue_type, "severity": severity, "message": message, "recommendation": recommendation}


MIN_WORD_COUNT = 100
