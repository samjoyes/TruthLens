"""Unit tests for URL safety, trusted domains, and article fetching."""

from unittest.mock import MagicMock, patch

from core.retrieval import fetch_article, is_safe_url, is_trusted_domain, search_web
from core.schemas import Source


def test_is_safe_url_blocks_private_and_local():
    """Verify SSRF protection blocks localhost, loopback, private IPs and non-http."""
    assert is_safe_url("http://localhost:8000") is False
    assert is_safe_url("http://127.0.0.1/admin") is False
    assert is_safe_url("http://192.168.1.1/secret") is False
    assert is_safe_url("http://10.0.0.1/") is False
    assert is_safe_url("ftp://example.com/file") is False
    assert is_safe_url("file:///etc/passwd") is False
    assert is_safe_url("") is False
    assert is_safe_url("invalid-url") is False


def test_is_safe_url_allows_public_urls():
    """Public URLs should pass SSRF check."""
    assert is_safe_url("https://www.bbc.com/news") is True
    assert is_safe_url("http://apnews.com/article/123") is True


def test_trusted_domains():
    """Verify trusted domain classification."""
    assert is_trusted_domain("https://www.reuters.com/world") is True
    assert is_trusted_domain("https://bbc.com/news") is True
    assert is_trusted_domain("https://subdomain.who.int/page") is True
    assert is_trusted_domain("https://unverified-blog.xyz") is False


def test_search_web_ranking():
    """Verify that trusted domain results are ranked before untrusted ones."""
    mock_ddg_results = [
        {"title": "Random Blog", "href": "https://randomblog.xyz/post", "body": "Some snippet"},
        {"title": "BBC News", "href": "https://www.bbc.com/article", "body": "Verified news snippet"},
    ]
    with patch("core.retrieval.DDGS") as mock_ddgs:
        instance = MagicMock()
        instance.text.return_value = mock_ddg_results
        mock_ddgs.return_value.__enter__.return_value = instance

        sources = search_web("test query", max_results=5)
        assert len(sources) == 2
        # BBC should be ranked first because it's a trusted domain
        assert sources[0].url == "https://www.bbc.com/article"
        assert sources[1].url == "https://randomblog.xyz/post"


def test_fetch_article_parses_html():
    """Verify title and paragraph extraction."""
    html = """
    <html>
      <head><title>Space Probe Lands</title></head>
      <body>
        <article>
          <p>The space probe touched down safely after a multi-month journey through deep space.</p>
          <p>Engineers celebrated in the mission control room as telemetry signals confirmed touchdown.</p>
        </article>
      </body>
    </html>
    """
    mock_response = MagicMock()
    mock_response.text = html
    mock_response.status_code = 200

    with patch("core.retrieval.requests.get", return_value=mock_response):
        title, body = fetch_article("https://news.example.com/probe")
        assert title == "Space Probe Lands"
        assert "touched down safely" in body
        assert "celebrated in the mission control room" in body


def test_fetch_article_rejects_unsafe_url():
    """Verify unsafe URLs immediately return empty tuple without network call."""
    with patch("core.retrieval.requests.get") as mock_get:
        title, body = fetch_article("http://127.0.0.1/private")
        assert title == ""
        assert body == ""
        mock_get.assert_not_called()
