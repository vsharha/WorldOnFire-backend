"""
News scheduler module - Handles periodic RSS feed fetching and parsing
"""

from contextlib import asynccontextmanager
from apscheduler.schedulers.background import BackgroundScheduler
from supabase import Client, create_client
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from rss_feeds import parse_feeds_by_city
from datetime import datetime, timedelta
from dateutil import parser as date_parser
from dotenv import load_dotenv
from geopy.geocoders import Nominatim
from geo_utils import geocode_and_cache_location
import os

# Initialize scheduler
scheduler = BackgroundScheduler()

# Initialize sentiment analyzer
sentiment_analyzer = SentimentIntensityAnalyzer()

# Initialize geocoder for coordinate caching
geolocator = Nominatim(user_agent="worldonfire-backend")


def fetch_and_save_rss_articles(supabase: Client) -> dict:
    """
    Fetch articles from RSS feeds and save to database.
    Uses the parse_feeds_by_city function from rss_feeds.py.

    Args:
        supabase: Supabase client instance

    Returns:
        dict: Statistics about the saved articles
    """
    saved_count = 0
    errors = []

    try:
        # Parse RSS feeds (already filters for tracked cities)
        articles = parse_feeds_by_city(filter_tracked_only=True)

        print(f"Found {len(articles)} articles from RSS feeds")

        # Save each article to the database
        for article in articles:
            try:
                # Get all locations for this article
                locations = article.get("locations", [])

                if not locations:
                    continue

                # Check if article has a published date
                published_str = article.get("published", "")
                if not published_str or published_str == "Unknown":
                    print(f"Skipping article without published date: {article.get('title', 'Unknown')[:50]}")
                    continue

                # Parse and validate the published date
                try:
                    # Parse the published date
                    published_date = date_parser.parse(published_str)

                    # Make it timezone-aware if it's naive
                    if published_date.tzinfo is None:
                        published_date = published_date.replace(tzinfo=datetime.now().astimezone().tzinfo)

                    # Calculate time difference
                    now = datetime.now().astimezone()
                    time_diff = now - published_date

                    # Skip if older than 24 hours
                    if time_diff > timedelta(hours=24):
                        print(f"Skipping old article (published {time_diff} ago): {article.get('title', 'Unknown')[:50]}")
                        continue
                except (ValueError, TypeError) as date_error:
                    print(f"Skipping article with unparseable date '{published_str}': {article.get('title', 'Unknown')[:50]}")
                    continue

                # Cache coordinates for all locations in this article
                # This runs for each article to ensure coordinates are cached immediately
                for location in locations:
                    try:
                        geocode_and_cache_location(supabase, location, geolocator)
                    except Exception as geo_error:
                        # Don't fail the entire article if geocoding fails
                        print(f"Non-fatal error caching coordinates for {location}: {str(geo_error)}")

                # Calculate sentiment from title and summary
                text_for_sentiment = f"{article.get('title', '')} {article.get('summary', '')}"
                sentiment_scores = sentiment_analyzer.polarity_scores(text_for_sentiment)
                # Use compound score (ranges from -1 to 1)
                sentiment_value = sentiment_scores['compound']

                # Store article once with all locations in array
                news_data = {
                    "title": article.get("title", "No title"),
                    "locations": locations,  # Array of all locations mentioned
                    "image_url": article.get("image_url"),  # Extracted from article page
                    "description": article.get("summary", ""),
                    "sentiment": sentiment_value,  # Calculated using VADER sentiment analysis
                    "url": article.get("link"),
                    "published_at": published_date.isoformat(),  # Store the actual published date
                }

                # Check if this article already exists (by URL or title)
                # First check by URL (most reliable)
                existing_by_url = None
                if news_data["url"]:
                    existing_by_url = supabase.table("news").select("id").eq("url", news_data["url"]).execute()

                # Also check by title to catch duplicates with different URLs
                existing_by_title = supabase.table("news").select("id").eq("title", news_data["title"]).execute()

                # Only insert if not found by URL or title
                if not (existing_by_url and existing_by_url.data) and not (existing_by_title and existing_by_title.data):
                    supabase.table("news").insert(news_data).execute()
                    saved_count += 1

            except Exception as article_error:
                errors.append(f"Error saving article '{article.get('title', 'Unknown')}': {str(article_error)}")
                continue

    except Exception as e:
        errors.append(f"Error parsing RSS feeds: {str(e)}")

    return {
        "saved_count": saved_count,
        "total_articles": len(articles) if 'articles' in locals() else 0,
        "errors": errors
    }


def create_scheduler_job(supabase: Client, interval_hours: int = 12):
    """
    Create and configure the scheduled job for fetching news.

    Args:
        supabase: Supabase client instance
        interval_hours: How often to fetch news (default: 12 hours)
    """
    def scheduled_fetch():
        """Wrapper function for the scheduled job"""
        try:
            result = fetch_and_save_rss_articles(supabase)
            print(f"Scheduled fetch completed: {result['saved_count']} articles saved")
            if result['errors']:
                print(f"Errors during fetch: {result['errors']}")
        except Exception as e:
            print(f"Error in scheduled fetch: {str(e)}")

    # Add the job to the scheduler
    scheduler.add_job(
        scheduled_fetch,
        'interval',
        hours=interval_hours,
        id='fetch_rss_news',
        replace_existing=True
    )


@asynccontextmanager
async def lifespan(app, supabase: Client):
    """
    Lifespan context manager for FastAPI app.
    Starts the scheduler on startup and stops it on shutdown.

    Args:
        app: FastAPI application instance
        supabase: Supabase client instance
    """
    # Startup: Create scheduler job
    print("Starting news scheduler...")

    # Create scheduler job and start the scheduler
    create_scheduler_job(supabase, interval_hours=12)
    scheduler.start()
    print("News scheduler started - fetching RSS feeds every 12 hours")

    yield  # App is running

    # Shutdown: Stop the scheduler
    print("Stopping news scheduler...")
    scheduler.shutdown()
    print("News scheduler stopped")


def main():
    """
    Main function to run RSS feed fetching once for testing purposes.
    """
    # Load environment variables
    load_dotenv()

    # Initialize Supabase client
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        print("Error: SUPABASE_URL and SUPABASE_SERVICE_KEY must be set in environment variables")
        return

    supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

    # Run the fetch once
    print("Starting RSS feed fetch...")
    result = fetch_and_save_rss_articles(supabase)

    # Print results
    print(f"\n{'='*60}")
    print(f"RSS Feed Fetch Complete")
    print(f"{'='*60}")
    print(f"Total articles found: {result['total_articles']}")
    print(f"Articles saved: {result['saved_count']}")
    print(f"Success rate: {result['saved_count']}/{result['total_articles']}")

    if result['errors']:
        print(f"\nErrors encountered ({len(result['errors'])}):")
        for error in result['errors']:
            print(f"  - {error}")
    else:
        print("\nNo errors encountered")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
