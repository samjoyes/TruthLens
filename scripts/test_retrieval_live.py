"""Manual test script to verify web search and article fetching."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.retrieval import fetch_article, search_web


def main():
    print("1. Testing search_web('Chandrayaan-3 landing date')...")
    sources = search_web("Chandrayaan-3 landing date", max_results=3)
    print(f"   Retrieved {len(sources)} sources:")
    for i, src in enumerate(sources, 1):
        print(f"   [{i}] {src.title}")
        print(f"       URL: {src.url}")
        print(f"       Snippet: {src.snippet[:80]}...")

    print("\n2. Testing fetch_article with real news URLs...")
    test_urls = [
        "https://www.bbc.com/news",
        "https://en.wikipedia.org/wiki/Chandrayaan-3",
        "https://invalid-domain-that-does-not-exist-12345.com",
    ]
    for url in test_urls:
        title, body = fetch_article(url)
        print(f"   URL: {url}")
        print(f"   Title extracted: {title[:60] if title else '[None]'}")
        print(f"   Body length: {len(body)} chars")


if __name__ == "__main__":
    main()
