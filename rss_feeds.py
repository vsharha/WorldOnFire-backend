import feedparser
from geotext import GeoText
from data_handlers import get_all_cities
import os
import socket
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import re

def load_rss_feeds(feeds_file="rss_feeds.txt"):
    """
    Load RSS feed URLs from a text file.

    Args:
        feeds_file: Path to the text file containing RSS feed URLs (one per line)

    Returns:
        list: List of RSS feed URLs
    """
    # Get the directory where this script is located
    script_dir = os.path.dirname(os.path.abspath(__file__))
    feeds_path = os.path.join(script_dir, feeds_file)

    feeds = []
    try:
        with open(feeds_path, 'r', encoding='utf-8') as f:
            for line in f:
                # Strip whitespace and skip empty lines or comments
                url = line.strip()
                if url and not url.startswith('#'):
                    feeds.append(url)
        print(f"Loaded {len(feeds)} RSS feeds from {feeds_file}")
    except FileNotFoundError:
        print(f"Error: {feeds_file} not found. Please create it with one RSS feed URL per line.")
        return []
    except Exception as e:
        print(f"Error loading feeds file: {str(e)}")
        return []

    return feeds

def extract_article_content(article_url, timeout=10):
    """
    Extract the first non-logo image and text content from an article page.

    Args:
        article_url: The URL of the article to extract content from
        timeout: Request timeout in seconds (default: 10)

    Returns:
        tuple: (image_url, text_content) where image_url is the first non-logo image
               (or None), and text_content is the extracted article text (or empty string)
    """
    try:
        # Fetch the article page
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        response = requests.get(article_url, timeout=timeout, headers=headers)
        response.raise_for_status()

        # Parse HTML
        soup = BeautifulSoup(response.content, 'html.parser')

        # Extract image
        image_url = None
        exclude_patterns = [
            'logo', 'icon', 'header', 'banner', 'avatar', 'profile', 'badge',
            'favicon', 'sprite', 'placeholder', 'default', 'fallback',
            'navigation', 'nav', 'menu', 'social', 'share', 'button', 'btn',
            'arrow', 'bullet', 'thumbnail', 'thumb', 'ad', 'advertisement',
            'widget', 'sidebar', 'footer', 'sponsor'
        ]

        images = soup.find_all('img')
        for img in images:
            img_url = img.get('src') or img.get('data-src') or img.get('data-lazy-src')
            if not img_url:
                continue

            img_url = urljoin(article_url, img_url)

            if (img_url.startswith('data:') or
                img_url.lower().endswith('.svg') or
                img_url.lower().endswith('.gif')):
                continue

            img_lower = img_url.lower()
            alt_text = (img.get('alt') or '').lower()
            class_names = ' '.join(img.get('class', [])).lower()
            img_id = (img.get('id') or '').lower()

            if any(pattern in img_lower or pattern in alt_text or
                   pattern in class_names or pattern in img_id
                   for pattern in exclude_patterns):
                continue

            width = img.get('width')
            height = img.get('height')

            try:
                if width and int(width) < 200:
                    continue
                if height and int(height) < 150:
                    continue
            except (ValueError, TypeError):
                pass

            image_url = img_url
            break

        # Extract text content
        text_content = ""

        # Try to find article content in common article containers
        article_selectors = [
            'article',
            '[class*="article"]',
            '[class*="content"]',
            '[class*="post"]',
            '[class*="entry"]',
            'main',
            '[role="main"]'
        ]

        article_element = None
        for selector in article_selectors:
            article_element = soup.select_one(selector)
            if article_element:
                break

        # If no article container found, use body
        if not article_element:
            article_element = soup.body

        if article_element:
            # Remove script, style, nav, footer, aside elements
            for element in article_element(['script', 'style', 'nav', 'footer', 'aside', 'header']):
                element.decompose()

            # Get text from paragraphs primarily
            paragraphs = article_element.find_all('p')
            if paragraphs:
                text_content = ' '.join([p.get_text(strip=True) for p in paragraphs])
            else:
                # Fallback to all text
                text_content = article_element.get_text(separator=' ', strip=True)

        return image_url, text_content

    except Exception as e:
        print(f"Error extracting content from {article_url}: {str(e)}")
        return None, ""

def extract_first_image(article_url, timeout=10):
    """
    Extract only the first non-logo image from an article page (lightweight version).

    Args:
        article_url: The URL of the article to extract image from
        timeout: Request timeout in seconds (default: 10)

    Returns:
        str: URL of the first non-logo image, or None if not found
    """
    image_url, _ = extract_article_content(article_url, timeout)
    return image_url

def parse_single_feed(url, normalized_tracked, filter_tracked_only):
    """
    Parse a single RSS feed and extract articles with locations.

    Args:
        url: The RSS feed URL to parse
        normalized_tracked: Set of normalized tracked city names
        filter_tracked_only: Whether to filter only tracked cities

    Returns:
        dict: Dictionary with article links as keys and article data as values
    """
    articles_dict = {}
    print(f"Parsing feed: {url}")

    try:
        # Set socket timeout to 30 seconds for feed parsing
        socket.setdefaulttimeout(30)
        feed = feedparser.parse(url, request_headers={'User-Agent': 'Mozilla/5.0'})

        for entry in feed.entries:
            # Combine title and summary for better city detection
            text = f"{entry.title} {entry.get('summary', '')} {entry.get('description', '')}"

            # Extract all cities mentioned in the text
            cities = GeoText(text).cities

            # Filter cities if needed
            if filter_tracked_only:
                cities = [city for city in cities if city in normalized_tracked]

            # Skip if no relevant cities found
            if not cities:
                continue

            # Use link as unique identifier for the article
            article_link = entry.link

            # Clean HTML from summary
            raw_summary = entry.get("summary", "") or entry.get("description", "")
            if raw_summary:
                # Strip HTML tags using BeautifulSoup
                clean_summary = BeautifulSoup(raw_summary, 'html.parser').get_text(separator=' ', strip=True)
            else:
                clean_summary = ""

            # Try to extract image from RSS feed entry first
            image_url = None

            # Check for media:content (common in RSS feeds)
            if hasattr(entry, 'media_content') and entry.media_content:
                image_url = entry.media_content[0].get('url')

            # Check for media:thumbnail
            if not image_url and hasattr(entry, 'media_thumbnail') and entry.media_thumbnail:
                image_url = entry.media_thumbnail[0].get('url')

            # Check for enclosures (like in podcasts/media RSS)
            if not image_url and hasattr(entry, 'enclosures') and entry.enclosures:
                for enclosure in entry.enclosures:
                    if enclosure.get('type', '').startswith('image/'):
                        image_url = enclosure.get('href') or enclosure.get('url')
                        break

            # Check for image in description/summary HTML
            if not image_url and raw_summary:
                soup = BeautifulSoup(raw_summary, 'html.parser')
                img_tag = soup.find('img')
                if img_tag:
                    image_url = img_tag.get('src')

            # If no summary or very short summary, fetch article content
            need_fetch = not clean_summary or len(clean_summary.strip()) < 50

            if need_fetch or not image_url:
                # Only fetch if we need summary or image
                if need_fetch:
                    print(f"No description for {article_link}, fetching article content...")
                fetched_image, article_text = extract_article_content(article_link)

                # Use fetched image if we don't have one from RSS
                if not image_url:
                    image_url = fetched_image

                # Use fetched text if we don't have a summary
                if need_fetch and article_text:
                    clean_summary = article_text

            # Create article entry (use set for locations)
            articles_dict[article_link] = {
                "title": entry.title,
                "link": article_link,
                "source": feed.feed.get("title", "Unknown"),
                "published": entry.get("published", "Unknown"),
                "summary": clean_summary[:200],  # First 200 chars of cleaned text
                "locations": set(cities),
                "image_url": image_url
            }

    except Exception as e:
        print(f"Error parsing {url}: {str(e)}")

    return articles_dict

def parse_feeds_by_city(filter_tracked_only=True, feeds_file="rss_feeds.txt", max_workers=15):
    """
    Parse all RSS feeds in parallel and extract city names dynamically.

    Args:
        filter_tracked_only: If True, only returns news for tracked cities (default: True)
        feeds_file: Path to the text file containing RSS feed URLs (default: "rss_feeds.txt")
        max_workers: Maximum number of parallel workers (default: 15)

    Returns:
        list: List of articles, each with related locations and image
              Example: [
                  {
                      "title": "...",
                      "link": "...",
                      "source": "...",
                      "published": "...",
                      "summary": "...",
                      "locations": ["London", "Paris"],
                      "image_url": "https://..."
                  }
              ]
    """
    # Load RSS feeds from file
    feeds = load_rss_feeds(feeds_file)
    if not feeds:
        print("No feeds loaded. Returning empty results.")
        return []

    # Get list of tracked cities for filtering
    tracked_cities = set(get_all_cities())

    # Use dict to store articles by their link (unique identifier)
    # This prevents duplicates and allows us to accumulate locations per article
    articles_dict = {}

    # Parse feeds in parallel using ThreadPoolExecutor
    print(f"Parsing {len(feeds)} feeds in parallel with {max_workers} workers...")
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all feed parsing tasks

        future_to_url = {
            executor.submit(parse_single_feed, url, tracked_cities, filter_tracked_only): url
            for url in feeds
        }

        # Process completed tasks as they finish
        try:
            for future in as_completed(future_to_url, timeout=300):
                url = future_to_url[future]
                try:
                    # Set timeout for individual feed processing (30 seconds)
                    feed_articles = future.result(timeout=30)

                    # Merge articles from this feed into the main dict
                    for article_link, article_data in feed_articles.items():
                        if article_link in articles_dict:
                            # Merge location sets (automatically handles duplicates)
                            articles_dict[article_link]["locations"].update(article_data["locations"])
                        else:
                            articles_dict[article_link] = article_data

                except TimeoutError:
                    print(f"Timeout while processing {url}")
                except Exception as e:
                    print(f"Error processing results from {url}: {str(e)}")
        except TimeoutError:
            # Overall timeout reached - some feeds didn't complete in time
            # Count how many feeds are still pending
            completed = sum(1 for f in future_to_url if f.done())
            pending = len(future_to_url) - completed
            print(f"Overall timeout reached: {completed}/{len(feeds)} feeds completed, {pending} feeds still pending")
            print("Proceeding with articles from completed feeds...")

    # Convert dict to list of articles and convert location sets to lists
    articles_list = []
    for article in articles_dict.values():
        article["locations"] = list(article["locations"])
        articles_list.append(article)

    return articles_list

if __name__ == "__main__":
    articles = parse_feeds_by_city(filter_tracked_only=True)

    unique_cities = set()
    for article in articles:
        unique_cities.update(article["locations"])

    print(articles)