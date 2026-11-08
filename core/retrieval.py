"""Web retrieval module for searching claims and fetching article text."""

import ipaddress
import re
import socket
from typing import Optional
from urllib.parse import quote, urlparse

import requests
from bs4 import BeautifulSoup
from ddgs import DDGS

from core.config import MAX_SEARCH_RESULTS, TRUSTED_DOMAINS
from core.schemas import Source

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 TruthLens/1.0"
)


def is_safe_url(url: str) -> bool:
    """Validate that the URL is public http/https and blocks local/private addresses to avoid SSRF."""
    if not url or not isinstance(url, str):
        return False

    try:
        parsed = urlparse(url.strip())
        if parsed.scheme not in ("http", "https"):
            return False

        hostname = parsed.hostname
        if not hostname:
            return False

        hostname_lower = hostname.lower()
        if hostname_lower in ("localhost", "0.0.0.0", "::1"):
            return False

        # Check IP literal directly if hostname is an IP
        try:
            ip_obj = ipaddress.ip_address(hostname_lower)
            if ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_reserved or ip_obj.is_link_local:
                return False
        except ValueError:
            # Not an IP literal, it's a domain name.
            if (
                hostname_lower.endswith(".local")
                or hostname_lower.endswith(".internal")
                or hostname_lower.endswith(".lan")
            ):
                return False

            # Block private IP prefix patterns (e.g. 127.x, 10.x, 192.168.x)
            for private_prefix in ("127.", "10.", "192.168.", "169.254."):
                if hostname_lower.startswith(private_prefix):
                    return False

            # If DNS resolution is available, verify the resolved IP
            try:
                ip_str = socket.gethostbyname(hostname)
                resolved_ip = ipaddress.ip_address(ip_str)
                if resolved_ip.is_private or resolved_ip.is_loopback or resolved_ip.is_reserved:
                    return False
            except socket.error:
                # In sandbox or offline testing, DNS resolution might be unreachable
                pass

        return True
    except Exception:
        return False


def is_trusted_domain(url: str) -> bool:
    """Check if the URL belongs to any configured trusted news or fact-checking domains."""
    try:
        domain = urlparse(url).netloc.lower()
        return any(domain == trusted or domain.endswith("." + trusted) for trusted in TRUSTED_DOMAINS)
    except Exception:
        return False


def _fallback_wikipedia_search(query: str, max_results: int) -> list[Source]:
    """Fallback search using Wikipedia Search API when commercial engines rate-limit."""
    try:
        clean_query = query.strip()
        resp = requests.get(
            "https://en.wikipedia.org/w/api.php",
            params={
                "action": "query",
                "list": "search",
                "srsearch": clean_query,
                "format": "json",
                "srlimit": max_results,
            },
            headers={"User-Agent": USER_AGENT},
            timeout=8,
        )
        if resp.status_code != 200:
            return []

        data = resp.json()
        search_items = data.get("query", {}).get("search", [])
        fallback_sources: list[Source] = []
        for item in search_items:
            page_title = item.get("title", "")
            snippet_html = item.get("snippet", "")
            snippet_clean = BeautifulSoup(snippet_html, "html.parser").get_text(strip=True)
            page_url = f"https://en.wikipedia.org/wiki/{quote(page_title.replace(' ', '_'))}"
            fallback_sources.append(
                Source(
                    title=f"{page_title} - Wikipedia",
                    url=page_url,
                    snippet=snippet_clean,
                    stance="neutral",
                )
            )
        return fallback_sources
    except Exception:
        return []


def search_web(query: str, max_results: int = MAX_SEARCH_RESULTS) -> list[Source]:
    """Search DuckDuckGo for evidence and return ranked Source objects.

    Uses DuckDuckGo (via ddgs) first; if unavailable or challenged, falls back
    to Wikipedia search to guarantee factual evidence is returned.
    """
    if not query or not query.strip():
        return []

    clean_query = query.strip()
    raw_results = []

    # 1. Primary search via ddgs
    try:
        with DDGS() as ddgs:
            raw_results = list(ddgs.text(clean_query, max_results=max_results))
    except Exception:
        raw_results = []

    sources: list[Source] = []
    for item in raw_results:
        href = item.get("href") or ""
        title = item.get("title") or "Untitled"
        body = item.get("body") or ""

        if href and is_safe_url(href):
            sources.append(
                Source(
                    title=title.strip(),
                    url=href.strip(),
                    snippet=body.strip(),
                    stance="neutral",
                )
            )

    # 2. Resilient fallback if ddgs returned no results
    if len(sources) < max_results:
        needed = max_results - len(sources)
        fallback = _fallback_wikipedia_search(clean_query, needed)
        sources.extend(fallback)

    # Rank trusted domains higher
    sources.sort(key=lambda s: 0 if is_trusted_domain(s.url) else 1)
    return sources[:max_results]


def fetch_article(url: str, timeout: int = 10) -> tuple[str, str]:
    """Fetch article content from a safe URL, returning (title, body_text)."""
    if not is_safe_url(url):
        return "", ""

    try:
        headers = {"User-Agent": USER_AGENT}
        response = requests.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        # Extract title: og:title -> <title>
        title = ""
        og_title = soup.find("meta", property="og:title")
        if og_title and og_title.get("content"):
            title = og_title["content"].strip()
        elif soup.title and soup.title.string:
            title = soup.title.string.strip()

        # Extract body text from <article> if available, else all <p>
        article_tag = soup.find("article")
        container = article_tag if article_tag else soup

        # Strip non-content tags
        for tag in container.find_all(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()

        paragraphs = [p.get_text().strip() for p in container.find_all("p")]
        body_text = "\n\n".join(p for p in paragraphs if len(p) > 20)

        # Fallback if paragraphs were sparse
        if not body_text and article_tag:
            body_text = article_tag.get_text(separator="\n", strip=True)

        return title, body_text
    except Exception:
        # Safe fallback on network failure, 403, 404, etc.
        return "", ""
