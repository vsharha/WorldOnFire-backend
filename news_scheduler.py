"""
News scheduler module - Handles periodic RSS feed fetching and parsing
"""

from contextlib import asynccontextmanager
from apscheduler.schedulers.background import BackgroundScheduler
from supabase import Client
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from rss_feeds import parse_feeds_by_city
from datetime import datetime, timedelta
from dateutil import parser as date_parser

# Initialize scheduler
scheduler = BackgroundScheduler()

# Initialize sentiment analyzer
sentiment_analyzer = SentimentIntensityAnalyzer()


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

                # Check if article is from the last 20 minutes
                published_str = article.get("published", "")
                if published_str and published_str != "Unknown":
                    try:
                        # Parse the published date
                        published_date = date_parser.parse(published_str)

                        # Make it timezone-aware if it's naive
                        if published_date.tzinfo is None:
                            published_date = published_date.replace(tzinfo=datetime.now().astimezone().tzinfo)

                        # Calculate time difference
                        now = datetime.now().astimezone()
                        time_diff = now - published_date

                        # Skip if older than 20 minutes
                        if time_diff > timedelta(minutes=20):
                            print(f"Skipping old article (published {time_diff} ago): {article.get('title', 'Unknown')[:50]}")
                            continue
                    except (ValueError, TypeError) as date_error:
                        print(f"Could not parse date '{published_str}' for article: {article.get('title', 'Unknown')[:50]}")
                        # Continue processing if date parsing fails

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


def create_scheduler_job(supabase: Client, interval_minutes: int = 10):
    """
    Create and configure the scheduled job for fetching news.

    Args:
        supabase: Supabase client instance
        interval_minutes: How often to fetch news (default: 10 minutes)
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
        minutes=interval_minutes,
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
    # Startup: Fetch news immediately, then create scheduler job
    print("Starting news scheduler...")

    # Fetch news immediately on startup
    print("Fetching news immediately on startup...")
    try:
        result = fetch_and_save_rss_articles(supabase)
        print(f"Initial fetch completed: {result['saved_count']} articles saved out of {result['total_articles']} found")
        if result['errors']:
            print(f"Errors during initial fetch: {result['errors']}")
    except Exception as e:
        print(f"Error in initial fetch: {str(e)}")

    # Create scheduler job and start the scheduler
    create_scheduler_job(supabase, interval_minutes=10)
    scheduler.start()
    print("News scheduler started - fetching RSS feeds every 10 minutes")

    yield  # App is running

    # Shutdown: Stop the scheduler
    print("Stopping news scheduler...")
    scheduler.shutdown()
    print("News scheduler stopped")
