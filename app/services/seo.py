from __future__ import annotations

from bs4 import BeautifulSoup


def extract_seo_data(html: str, url: str) -> dict[str, object]:
    soup = BeautifulSoup(html, 'html.parser')
    title = soup.title.string.strip() if soup.title and soup.title.string else ''
    meta_description = (
        soup.find('meta', attrs={'name': 'description'})
        or soup.find('meta', attrs={'property': 'description'})
    )
    description = meta_description.get('content', '') if meta_description else ''
    h1s = [h.get_text(' ', strip=True) for h in soup.find_all('h1')]
    canonical = soup.find('link', rel='canonical')
    canonical_url = canonical.get('href', '') if canonical else ''
    return {
        'url': url,
        'title': title,
        'meta_description': description,
        'h1s': h1s,
        'canonical_url': canonical_url,
        'word_count': len(soup.get_text(' ', strip=True).split()),
    }


def calculate_seo_score(data: dict[str, object]) -> int:
    score = 0
    if data.get('title'):
        score += 25
    if data.get('meta_description'):
        score += 25
    if data.get('h1s'):
        score += 25
    if data.get('canonical_url'):
        score += 25
    return min(score, 100)
