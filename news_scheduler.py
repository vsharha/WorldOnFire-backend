"""
News scheduler module - Handles periodic RSS feed fetching and parsing
"""

from contextlib import asynccontextmanager
from apscheduler.schedulers.background import BackgroundScheduler
from supabase import Client
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from rss_feeds import parse_feeds_by_city

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

                # Calculate sentiment from title and summary
                text_for_sentiment = f"{article.get('title', '')} {article.get('summary', '')}"
                sentiment_scores = sentiment_analyzer.polarity_scores(text_for_sentiment)
                # Use compound score (ranges from -1 to 1)
                sentiment_value = sentiment_scores['compound']

                # Store article once with all locations in array
                news_data = {
                    "title": article.get("title", "No title"),
                    "locations": locations,  # Array of all locations mentioned
                    "image_url": None,  # RSS feeds typically don't include images
                    "description": article.get("summary", ""),
                    "sentiment": sentiment_value,  # Calculated using VADER sentiment analysis
                    "url": article.get("link"),
                }

                # Check if this article already exists (based on URL only)
                existing = supabase.table("news").select("id").eq("url", news_data["url"]).execute()

                if not existing.data:  # Only insert if not a duplicate
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
    # Startup: Create scheduler job and start the scheduler
    print("Starting news scheduler...")
    create_scheduler_job(supabase, interval_minutes=10)
    scheduler.start()
    print("News scheduler started - fetching RSS feeds every 10 minutes")

    yield  # App is running

    # Shutdown: Stop the scheduler
    print("Stopping news scheduler...")
    scheduler.shutdown()
    print("News scheduler stopped")
