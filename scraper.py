import re
import requests
from bs4 import BeautifulSoup

BASE_URL = "https://tcbonepiecechapters.com"
MANGA_URL = f"{BASE_URL}/mangas/5/one-piece"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


def get_latest_chapter():
    """
    Fetches the One Piece manga page and returns info about the latest chapter.

    Returns a dict: {"id": str, "title": str, "url": str}
    Returns None on any network or parse error.
    """
    try:
        response = requests.get(MANGA_URL, headers=HEADERS, timeout=15)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"[Scraper] Network error: {e}")
        return None

    try:
        soup = BeautifulSoup(response.text, "html.parser")

        # Chapter links follow the pattern: /chapters/{id}/{slug}
        chapter_links = soup.find_all("a", href=re.compile(r"^/chapters/\d+/"))

        if not chapter_links:
            print("[Scraper] No chapter links found. The page structure may have changed.")
            return None

        # Chapters are listed newest-first, so the first link is the latest
        latest = chapter_links[0]
        href = latest["href"]
        # Normalize whitespace (collapses double spaces, joins subtitle with a space)
        title = " ".join(latest.get_text(separator=" ", strip=True).split())

        # Extract the numeric chapter ID from the URL
        match = re.search(r"/chapters/(\d+)/", href)
        if not match:
            print(f"[Scraper] Could not extract chapter ID from URL: {href}")
            return None

        chapter_id = match.group(1)
        chapter_url = BASE_URL + href

        return {
            "id": chapter_id,
            "title": title,
            "url": chapter_url,
        }

    except Exception as e:
        print(f"[Scraper] Parse error: {e}")
        return None
