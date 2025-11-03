feeds = [
    "https://feeds.bbci.co.uk/news/world/rss.xml",
    "https://feeds.nbcnews.com/nbcnews/public/news",
    "https://www.cnbc.com/id/100727362/device/rss/rss.html",
    "https://abcnews.go.com/abcnews/internationalheadlines",
    "https://www.aljazeera.com/xml/rss/all.xml",
    "https://www.cbsnews.com/latest/rss/world",
    "https://www.france24.com/en/rss",
    "https://www.nytimes.com/svc/collections/v1/publish/https://www.nytimes.com/section/world/rss.xml",
    "https://feeds.washingtonpost.com/rss/world",
    "https://globalnews.ca/world/feed/",
    "https://feeds.feedburner.com/time/world",
    "https://feeds.npr.org/1004/rss.xml",
    "https://www.washingtontimes.com/rss/headlines/news/world",
    "https://www.smh.com.au/rss/world.xml",
    "https://feeds.skynews.com/feeds/rss/world.xml",
    "https://www.latimes.com/world-nation/rss2.0.xml#nt=1col-7030col1",
    "https://timesofindia.indiatimes.com/rssfeeds/296589292.cms",
    "https://www.rt.com/rss/news/",
    "https://feeds.feedburner.com/ndtvnews-world-news",
    "https://www.e-ir.info/feed/"
]

import feedparser
from geotext import GeoText
from collections import defaultdict
from data_handlers import get_all_cities

def parse_feeds_by_city(filter_tracked_only=True):
    """
    Parse all RSS feeds and extract city names dynamically.

    Args:
        filter_tracked_only: If True, only returns news for tracked cities (default: True)

    Returns:
        dict: Dictionary with city names as keys and list of news items as values
              Example: {
                  "London": [{"title": "...", "link": "...", "source": "..."}],
                  "Paris": [{"title": "...", "link": "...", "source": "..."}]
              }
    """
    # Get list of tracked cities for filtering
    tracked_cities = set(get_all_cities())

    # Normalize city names (replace underscores with spaces for matching)
    # e.g., "New_York_City" becomes "New York City"
    normalized_tracked = {city.replace("_", " ") for city in tracked_cities}
    normalized_tracked.update(tracked_cities)  # Keep original names too

    # Use defaultdict to automatically create lists for new cities
    news_by_city = defaultdict(list)

    for url in feeds:
        print(f"Parsing feed: {url}")
        try:
            feed = feedparser.parse(url)

            for entry in feed.entries:
                # Combine title and summary for better city detection
                text = f"{entry.title} {entry.get('summary', '')} {entry.get('description', '')}"

                # Extract all cities mentioned in the text
                cities = GeoText(text).cities

                # Add this news item to each city it mentions
                for city in cities:
                    # Skip if filtering is enabled and city is not tracked
                    if filter_tracked_only and city not in normalized_tracked:
                        continue

                    news_by_city[city].append({
                        "title": entry.title,
                        "link": entry.link,
                        "source": feed.feed.get("title", "Unknown"),
                        "published": entry.get("published", "Unknown"),
                        "summary": entry.get("summary", "")[:200]  # First 200 chars
                    })

        except Exception as e:
            print(f"Error parsing {url}: {str(e)}")
            continue

    # Convert defaultdict to regular dict for cleaner output
    return dict(news_by_city)

# Parse all feeds and get results organized by city (filtered to tracked cities only)
news_by_city = parse_feeds_by_city(filter_tracked_only=True)

# Get total tracked cities for comparison
total_tracked = len(get_all_cities())

# Display results
print(f"\n{'='*60}")
print(f"TRACKED CITIES: Found news for {len(news_by_city)}/{total_tracked} tracked cities")
print(f"{'='*60}\n")

# Sort cities by number of articles (most mentioned first)
sorted_cities = sorted(news_by_city.items(), key=lambda x: len(x[1]), reverse=True)

for city, articles in sorted_cities:
    print(f"\n{city} ({len(articles)} articles):")
    print("-" * 40)
    for article in articles[:3]:  # Show first 3 articles per city
        print(f"  [{article['source']}] {article['title']}")
        print(f"  Link: {article['link']}")
    if len(articles) > 3:
        print(f"  ... and {len(articles) - 3} more")

# Show summary statistics
total_articles = sum(len(articles) for articles in news_by_city.values())
print(f"\n{'='*60}")
print(f"SUMMARY:")
print(f"  Total tracked cities with news: {len(news_by_city)}/{total_tracked}")
print(f"  Total articles collected: {total_articles}")
print(f"  Average articles per city: {total_articles / len(news_by_city):.1f}" if news_by_city else "  No articles found")
print(f"{'='*60}")

# Example usage: Access the results programmatically
print("\n\n# HOW TO USE THE RESULTS:")
print("# news_by_city is a dict with city names as keys")
print(f"# Example: news_by_city['London'] returns list of {len(news_by_city.get('London', []))} articles" if 'London' in news_by_city else "# Example: 'London' not found in current results")
print(f"# All cities: {list(news_by_city.keys())}")