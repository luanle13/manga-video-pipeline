"""Factory for creating manga scrapers based on URL or source."""

from urllib.parse import urlparse

from src.common.models import MangaSource

from .scrapers.base import BaseMangaScraper
from .scrapers.truyenqq import TruyenQQScraper


# Domain to scraper mapping
DOMAIN_SCRAPERS: dict[str, type[BaseMangaScraper]] = {
    "truyenqqno.com": TruyenQQScraper,
    "truyenqq.com": TruyenQQScraper,
    "truyenqq.net": TruyenQQScraper,
    # NetTruyen and TruyenTranhLH scrapers will be added here
    # "nettruyenfull.com": NetTruyenScraper,
    # "nettruyen.com": NetTruyenScraper,
    # "truyentranhlh.net": TruyenTranhLHScraper,
}

# Source enum to scraper mapping
SOURCE_SCRAPERS: dict[MangaSource, type[BaseMangaScraper]] = {
    MangaSource.truyenqq: TruyenQQScraper,
    # MangaSource.nettruyen: NetTruyenScraper,
    # MangaSource.truyentranhlh: TruyenTranhLHScraper,
}


def get_scraper_for_url(url: str) -> BaseMangaScraper:
    """Get appropriate scraper for a manga URL.

    Args:
        url: URL to manga page

    Returns:
        Scraper instance for the URL's domain

    Raises:
        ValueError: If no scraper is available for the domain
    """
    parsed = urlparse(url)
    domain = parsed.netloc.lower()

    # Remove www. prefix if present
    if domain.startswith("www."):
        domain = domain[4:]

    if domain in DOMAIN_SCRAPERS:
        return DOMAIN_SCRAPERS[domain]()

    # Check if domain contains a known site name
    for known_domain, scraper_class in DOMAIN_SCRAPERS.items():
        if known_domain.split(".")[0] in domain:
            return scraper_class()

    raise ValueError(f"Unsupported manga source: {domain}")


def get_scraper_for_source(source: MangaSource) -> BaseMangaScraper:
    """Get scraper for a specific manga source.

    Args:
        source: MangaSource enum value

    Returns:
        Scraper instance for the source

    Raises:
        ValueError: If no scraper is available for the source
    """
    if source in SOURCE_SCRAPERS:
        return SOURCE_SCRAPERS[source]()

    raise ValueError(f"Unsupported manga source: {source}")


def detect_source_from_url(url: str) -> MangaSource:
    """Detect the manga source from a URL.

    Args:
        url: URL to manga page

    Returns:
        MangaSource enum value

    Raises:
        ValueError: If source cannot be detected
    """
    parsed = urlparse(url)
    domain = parsed.netloc.lower()

    if "truyenqq" in domain:
        return MangaSource.truyenqq
    elif "nettruyen" in domain:
        return MangaSource.nettruyen
    elif "truyentranhlh" in domain:
        return MangaSource.truyentranhlh

    raise ValueError(f"Cannot detect source from URL: {url}")


def get_all_scrapers() -> list[BaseMangaScraper]:
    """Get instances of all available scrapers.

    Returns:
        List of scraper instances
    """
    # Use a set to avoid duplicates (some domains map to same scraper)
    scraper_classes = set(SOURCE_SCRAPERS.values())
    return [cls() for cls in scraper_classes]


def is_supported_url(url: str) -> bool:
    """Check if a URL is from a supported manga site.

    Args:
        url: URL to check

    Returns:
        True if URL is from a supported site
    """
    try:
        get_scraper_for_url(url)
        return True
    except ValueError:
        return False
