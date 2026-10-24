from __future__ import annotations

import json
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup

from app.crawler.url_normalizer import normalize_url


def parse_html(html: str, page_url: str, allowed_hostname: str) -> dict[str, object]:
    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    description_tag = soup.find("meta", attrs={"name": lambda value: value and value.lower() == "description"})
    description = description_tag.get("content", "").strip() if description_tag else ""
    headings = {
        level: [heading.get_text(" ", strip=True) for heading in soup.find_all(level)]
        for level in ("h1", "h2", "h3")
    }
    canonical_tag = soup.find("link", rel=lambda value: value and "canonical" in value)
    canonical = (
        normalize_url(urljoin(page_url, canonical_tag.get("href", "")), page_url)
        if canonical_tag and canonical_tag.get("href")
        else ""
    )

    links: list[dict[str, object]] = []
    for link in soup.find_all("a", href=True):
        target = normalize_url(urljoin(page_url, link["href"]), page_url)
        if urlsplit(target).scheme not in {"http", "https"}:
            continue
        rel = [str(value).lower() for value in link.get("rel", [])]
        links.append(
            {
                "target_url": target,
                "anchor_text": link.get_text(" ", strip=True),
                "rel": rel,
                "is_internal": urlsplit(target).hostname == allowed_hostname,
            }
        )

    images = [
        {"url": normalize_url(urljoin(page_url, image["src"]), page_url), "alt": image.get("alt", "")}
        for image in soup.find_all("img", src=True)
    ]
    structured_data = []
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            structured_data.append(json.loads(script.get_text()))
        except json.JSONDecodeError:
            continue

    for element in soup(["script", "style", "noscript"]):
        element.decompose()
    visible_text = soup.get_text(" ", strip=True)

    return {
        "title": title,
        "meta_description": description,
        "headings": headings,
        "canonical": canonical,
        "robots": _robots_directive(soup),
        "links": links,
        "images": images,
        "structured_data": structured_data,
        "word_count": len(visible_text.split()),
        "character_count": len(visible_text),
        "paragraph_count": len(soup.find_all("p")),
    }


def _robots_directive(soup: BeautifulSoup) -> str:
    tag = soup.find("meta", attrs={"name": lambda value: value and value.lower() == "robots"})
    return tag.get("content", "").strip() if tag else ""
