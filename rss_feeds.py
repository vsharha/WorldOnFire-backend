import feedparser
from geotext import GeoText
from data_handlers import get_all_cities
import os
import socket
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError

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

            # Create article entry (use set for locations)
            articles_dict[article_link] = {
                "title": entry.title,
                "link": article_link,
                "source": feed.feed.get("title", "Unknown"),
                "published": entry.get("published", "Unknown"),
                "summary": entry.get("summary", "")[:200],  # First 200 chars
                "locations": set(cities)
            }

    except Exception as e:
        print(f"Error parsing {url}: {str(e)}")

    return articles_dict

def parse_feeds_by_city(filter_tracked_only=True, feeds_file="rss_feeds.txt", max_workers=5):
    """
    Parse all RSS feeds in parallel and extract city names dynamically.

    Args:
        filter_tracked_only: If True, only returns news for tracked cities (default: True)
        feeds_file: Path to the text file containing RSS feed URLs (default: "rss_feeds.txt")
        max_workers: Maximum number of parallel workers (default: 5)

    Returns:
        list: List of articles, each with related locations
              Example: [
                  {
                      "title": "...",
                      "link": "...",
                      "source": "...",
                      "published": "...",
                      "summary": "...",
                      "locations": ["London", "Paris"]
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
        for future in as_completed(future_to_url, timeout=60):
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