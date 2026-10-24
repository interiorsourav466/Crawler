from app.parser.html_parser import parse_html
from app.seo.analyzer import analyze_seo


def test_parser_extracts_seo_links_images_and_json_ld():
    data = parse_html(
        """
        <html><head><title>Example title</title>
        <meta name='description' content='A description'>
        <link rel='canonical' href='/canonical'>
        <script type='application/ld+json'>{"@type":"Article"}</script></head>
        <body><h1>Main heading</h1><p>Useful text</p>
        <img src='/hero.jpg'><a href='/about'>About</a><a href='https://other.test'>Other</a></body></html>
        """,
        "https://example.com/start",
        "example.com",
    )
    assert data["title"] == "Example title"
    assert data["canonical"] == "https://example.com/canonical"
    assert data["links"][0]["is_internal"] is True
    assert data["links"][1]["is_internal"] is False
    assert data["images"][0]["alt"] == ""
    assert data["structured_data"][0]["@type"] == "Article"


def test_seo_analyzer_returns_explainable_issues_and_score():
    result = analyze_seo(
        {
            "title": "",
            "meta_description": "",
            "headings": {"h1": [], "h2": [], "h3": []},
            "canonical": "",
            "images": [{"alt": ""}],
            "word_count": 3,
        }
    )
    assert result["score"] < 100
    assert {issue["issue_type"] for issue in result["issues"]} >= {
        "missing_title",
        "missing_meta_description",
        "missing_h1",
        "missing_image_alt",
    }
