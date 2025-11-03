import feedparser
from geotext import GeoText
from data_handlers import get_all_cities
import os

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

def parse_feeds_by_city(filter_tracked_only=True, feeds_file="rss_feeds.txt"):
    """
    Parse all RSS feeds and extract city names dynamically.

    Args:
        filter_tracked_only: If True, only returns news for tracked cities (default: True)
        feeds_file: Path to the text file containing RSS feed URLs (default: "rss_feeds.txt")

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

    # Normalize city names (replace underscores with spaces for matching)
    # e.g., "New_York_City" becomes "New York City"
    normalized_tracked = {city.replace("_", " ") for city in tracked_cities}
    normalized_tracked.update(tracked_cities)  # Keep original names too

    # Use dict to store articles by their link (unique identifier)
    # This prevents duplicates and allows us to accumulate locations per article
    articles_dict = {}

    for url in feeds:
        print(f"Parsing feed: {url}")
        try:
            feed = feedparser.parse(url)

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

                # If article already exists, add new cities to its locations
                if article_link in articles_dict:
                    # Add cities that aren't already in the locations list
                    existing_locations = set(articles_dict[article_link]["locations"])
                    for city in cities:
                        if city not in existing_locations:
                            articles_dict[article_link]["locations"].append(city)
                else:
                    # Create new article entry
                    articles_dict[article_link] = {
                        "title": entry.title,
                        "link": article_link,
                        "source": feed.feed.get("title", "Unknown"),
                        "published": entry.get("published", "Unknown"),
                        "summary": entry.get("summary", "")[:200],  # First 200 chars
                        "locations": list(cities)
                    }

        except Exception as e:
            print(f"Error parsing {url}: {str(e)}")
            continue

    # Convert dict to list of articles
    return list(articles_dict.values())

if __name__ == "__main__":
    # Parse all feeds and get results as list of articles (filtered to tracked cities only)
    articles = parse_feeds_by_city(filter_tracked_only=True)

    # Get total tracked cities for comparison
    total_tracked = len(get_all_cities())

    # Count unique cities mentioned across all articles
    unique_cities = set()
    for article in articles:
        unique_cities.update(article["locations"])

    # Display results
    print(f"\n{'='*60}")
    print(f"TRACKED CITIES: Found news mentioning {len(unique_cities)}/{total_tracked} tracked cities")
    print(f"{'='*60}\n")

    # Sort articles by number of locations (most locations first)
    sorted_articles = sorted(articles, key=lambda x: len(x["locations"]), reverse=True)

    # Display first 10 articles
    print(f"Showing first 10 articles (out of {len(articles)} total):\n")
    for i, article in enumerate(sorted_articles[:10], 1):
        print(f"{i}. [{article['source']}] {article['title']}")
        print(f"   Locations: {', '.join(article['locations'])}")
        print(f"   Link: {article['link']}")
        print(f"   Published: {article['published']}")
        if article.get('summary'):
            print(f"   Summary: {article['summary']}")
        print()

    # Show summary statistics
    print(f"{'='*60}")
    print(f"SUMMARY:")
    print(f"  Total tracked cities with news: {len(unique_cities)}/{total_tracked}")
    print(f"  Total articles collected: {len(articles)}")
    if articles:
        avg_locations = sum(len(a["locations"]) for a in articles) / len(articles)
        print(f"  Average locations per article: {avg_locations:.1f}")
    else:
        print("  No articles found")
    print(f"{'='*60}")

    # Example usage: Access the results programmatically
    print("\n\n# HOW TO USE THE RESULTS:")
    print("# articles is a list of article dictionaries")
    print("# Each article has a 'locations' field with list of cities")
    print(f"# Example: articles[0] = {articles[0] if articles else 'No articles'}")
    print(f"# Cities mentioned: {sorted(list(unique_cities))}")