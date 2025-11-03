from fastapi import FastAPI, Header, HTTPException, Depends, Request, Body, BackgroundTasks
from supabase import create_client, Client

from pydantic import BaseModel
from dotenv import load_dotenv
import os
import json
from typing import Optional, Any
from contextlib import asynccontextmanager
from apscheduler.schedulers.background import BackgroundScheduler
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError
from datetime import datetime

from starlette.middleware.cors import CORSMiddleware
from rss_feeds import parse_feeds_by_city
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

load_dotenv()

# Initialize sentiment analyzer
sentiment_analyzer = SentimentIntensityAnalyzer()

origins = [
    "http://localhost:3000",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "https://world-on-fire.vercel.app"
]

# Initialize scheduler
scheduler = BackgroundScheduler()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Start the scheduler
    scheduler.add_job(get_news, 'interval', minutes=10)
    scheduler.start()

    yield  # App is running

    # Shutdown: Stop the scheduler
    scheduler.shutdown()

app = FastAPI(lifespan=lifespan)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY") # Uses service key that bypasses RLS policies. DO NOT DISCLOSE THE KEY ON THE FRONTEND.
supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

def get_cached_coordinates(location: str) -> Optional[list[float]]:
    """
    Retrieve cached coordinates for a location from the database.

    Args:
        location: The location name to look up

    Returns:
        [latitude, longitude] if found, None otherwise
    """
    try:
        result = supabase.table("location_cache").select("latitude, longitude").eq("location", location).execute()
        if result.data and len(result.data) > 0:
            coord = result.data[0]
            return [coord["latitude"], coord["longitude"]]
        return None
    except Exception as e:
        print(f"Error retrieving cached coordinates for {location}: {str(e)}")
        return None

def cache_coordinates(location: str, latitude: float, longitude: float) -> bool:
    """
    Store coordinates for a location in the database cache.

    Args:
        location: The location name
        latitude: The latitude coordinate
        longitude: The longitude coordinate

    Returns:
        True if successful, False otherwise
    """
    try:
        supabase.table("location_cache").upsert({
            "location": location,
            "latitude": latitude,
            "longitude": longitude,
            "updated_at": datetime.now().isoformat()
        }).execute()
        return True
    except Exception as e:
        print(f"Error caching coordinates for {location}: {str(e)}")
        return False

# Pydantic model for news data
class NewsItem(BaseModel):
    title: str
    locations: list[str]  # Array of city names
    image_url: Optional[str] = None
    description: Optional[str] = None
    url: Optional[str] = None

@app.get("/")
def welcome() -> dict[str, str]:
    return {"welcome_message": "This is a WorldOnFire official API. The World is on Fire right now."}

def fetch_and_save_rss_articles() -> dict:
    """
    Fetch articles from RSS feeds and save to database.
    Uses the parse_feeds_by_city function from rss_feeds.py.

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

@app.get("/news") # Fetch news from RSS feeds and save to database
def get_news() -> dict:
    try:
        # Fetch and save articles from RSS feeds
        result = fetch_and_save_rss_articles()

        return {
            "status": "success",
            "message": f"Fetched and saved {result['saved_count']} news articles from RSS feeds",
            "total_saved": result["saved_count"],
            "total_articles": result["total_articles"],
            "errors": result["errors"] if result["errors"] else None
        }

    except Exception as general_error:
        raise HTTPException(status_code=500, detail=f"Failed to fetch and save news: {str(general_error)}")


@app.get("/news/latest") # Retrieve 10 latest news from the database
def get_latest_news() -> list[dict[str, Any]]:
    try:
        # Order by created_at descending and fetch more to account for duplicates
        result = supabase.table("news").select("*").order("created_at", desc=True).limit(50).execute()

        # Deduplicate by title, keeping the most recent (first occurrence)
        seen_titles = set()
        unique_news = []

        for news_item in result.data:
            title = news_item.get("title")
            if title and title not in seen_titles:
                seen_titles.add(title)
                unique_news.append(news_item)
                if len(unique_news) >= 10:
                    break

        return unique_news
    except Exception as latest_error:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve latest news: {str(latest_error)}")

@app.get("/news/search") # Retrieve 10 latest news from the database, optionally filtered by city location
def search_news(location: Optional[str] = None) -> list[dict[str, Any]]:
    try:
        query = supabase.table("news").select("*")

        if location: # If location provided, search in locations array
            # Use PostgreSQL array contains operator for locations array search
            query = query.contains("locations", [location])

        # Order by created_at descending and fetch more to account for duplicates
        result = query.order("created_at", desc=True).limit(50).execute()

        # Deduplicate by title, keeping the most recent (first occurrence)
        seen_titles = set()
        unique_news = []

        for news_item in result.data:
            title = news_item.get("title")
            if title and title not in seen_titles:
                seen_titles.add(title)
                unique_news.append(news_item)
                if len(unique_news) >= 10:
                    break

        return unique_news
    except Exception as search_error:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve news: {str(search_error)}")

@app.get("/news/heatmap") # Generate heatmap data by averaging sentiment scores for each city
def get_heatmap() -> list[dict[str, Any]]:
    try: # Fetch all news from database with locations array, sentiment, and title
        result = supabase.table("news").select("locations, sentiment, title").execute()

        # Deduplicate by title before calculating intensity
        seen_titles = set()
        unique_articles = []

        for news_item in result.data:
            title = news_item.get("title")
            if title and title not in seen_titles:
                seen_titles.add(title)
                unique_articles.append(news_item)

        heatmap_data = {}

        for news_item in unique_articles:
            sentiment = news_item.get("sentiment")
            locations = news_item.get("locations", [])

            if sentiment is None or not locations:
                continue

            # Count sentiment for each location mentioned in the article
            for location in locations:
                if not location or location == "Unknown":
                    continue

                if location not in heatmap_data:
                    heatmap_data[location] = {"sum": 0, "count": 0}

                heatmap_data[location]["sum"] += sentiment
                heatmap_data[location]["count"] += 1

        # Initialize geocoder (only used if cache miss)
        geolocator = Nominatim(user_agent="worldonfire-backend")

        # Add coordinates to each location and calculate average sentiment
        result_data = []
        cache_hits = 0
        cache_misses = 0

        for location, sentiment_data in heatmap_data.items():
            coordinates = None

            # First, try to get coordinates from cache
            cached_coords = get_cached_coordinates(location)

            if cached_coords:
                coordinates = cached_coords
                cache_hits += 1
            else:
                # Cache miss - geocode the location
                cache_misses += 1
                try:
                    geo_result = geolocator.geocode(location, timeout=10)
                    if geo_result:
                        coordinates = [geo_result.latitude, geo_result.longitude]
                        # Cache the result for future use
                        cache_coordinates(location, geo_result.latitude, geo_result.longitude)
                        print(f"Geocoded and cached: {location}")
                except (GeocoderTimedOut, GeocoderServiceError) as geo_error:
                    # Log error but continue with None coordinates
                    print(f"Geocoding error for {location}: {str(geo_error)}")

            # Calculate average sentiment
            average_sentiment = sentiment_data["sum"] / sentiment_data["count"] if sentiment_data["count"] > 0 else 0

            result_data.append({
                "location": location,
                "intensity": average_sentiment,
                "coordinates": coordinates
            })

        print(f"Coordinate cache stats - Hits: {cache_hits}, Misses: {cache_misses}")
        return result_data

    except Exception as heatmap_error:
        raise HTTPException(status_code=500, detail=f"Failed to generate heatmap: {str(heatmap_error)}")