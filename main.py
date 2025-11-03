from fastapi import FastAPI, Header, HTTPException, Depends, Request, Body, BackgroundTasks
from supabase import create_client, Client

from pydantic import BaseModel
from dotenv import load_dotenv
import os
import requests
import json
from typing import Optional, Any
from contextlib import asynccontextmanager
from apscheduler.schedulers.background import BackgroundScheduler
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError
from datetime import datetime

from starlette.middleware.cors import CORSMiddleware

origins = [
    "http://localhost:3000",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "https://world-on-fire.vercel.app"
]

from data_handlers import (
    get_asia_oceania_cities,
    get_europe_africa_middleeast_cities,
    get_americas_cities
)
load_dotenv()

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

def get_cities_query_or_clause(cities: list[str]) -> list[dict]: # Helper to generate the $or clause with Wikipedia URIs for given cities
    return [{"locationUri": f"http://en.wikipedia.org/wiki/{city}"} for city in cities]

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
    location: str
    image_url: Optional[str] = None
    description: Optional[str] = None
    url: Optional[str] = None

@app.get("/")
def welcome() -> dict[str, str]:
    return {"welcome_message": "This is a WorldOnFire official API. The World is on Fire right now."}


@app.post("/news") # Add a news event to the Supabase news table
def add_news(news_item: NewsItem) -> dict:
    try: # Insert news item into the database
        result = supabase.table("news").insert({
            "title": news_item.title,
            "location": news_item.location,
            "image_url": news_item.image_url,
            "description": news_item.description,
            "url": news_item.url
        }).execute()

        return {
            "status": "success",
            "message": "News item added successfully",
            "data": result.data
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to add news item: {str(e)}")

def fetch_and_save_articles(cities: list[str], region_name: str) -> dict: # helper to fetch articles for specific cities and save to database
    url = "https://eventregistry.org/api/v1/minuteStreamArticles"

    query_obj = {
        "$query": {
            "$and": [
                {
                    "$or": get_cities_query_or_clause(cities)
                },
                {"lang": "eng"}
            ]
        }
    }

    params = {
        "query": json.dumps(query_obj),
        "recentActivityArticlesMaxArticleCount": 10,
        "recentActivityArticlesUpdatesAfterMinsAgo": 10,
        "apiKey": os.getenv("NEWS_API")
    }

    response = requests.get(url, params=params, timeout=30)
    response.raise_for_status()
    data = response.json()
    print(data)

    saved_count = 0
    errors = []

    # Parse the correct structure: recentActivityArticles.activity
    if "recentActivityArticles" in data and "activity" in data["recentActivityArticles"]:
        articles = data["recentActivityArticles"]["activity"]

        for article in articles:
            try: # Extract location from article
                location = "Unknown"
                if "location" in article and article["location"]:
                    location = article["location"].get("label", {}).get("eng", "Unknown")

                news_data = {
                    "title": article.get("title", "No title"),
                    "location": location,
                    "image_url": article.get("image"),
                    "description": article.get("body"),
                    "sentiment": article.get("sentiment"),
                    "url": article.get("url"),
                }

                supabase.table("news").insert(news_data).execute()
                saved_count += 1

            except Exception as article_error:
                errors.append(str(article_error))
                continue
    else:
        articles = []

    return {
        "region": region_name,
        "saved_count": saved_count,
        "total_articles": len(articles),
        "errors": errors
    }

@app.get("/news") # Fetch news from EventRegistry API and save to database
def get_news() -> dict:
    try:
        results = []
        asia_result = fetch_and_save_articles(get_asia_oceania_cities(), "Asia & Oceania")
        results.append(asia_result)
        europe_result = fetch_and_save_articles(get_europe_africa_middleeast_cities(), "Europe, Africa & Middle East")
        results.append(europe_result)
        americas_result = fetch_and_save_articles(get_americas_cities(), "Americas")
        results.append(americas_result)

        total_saved = sum(r["saved_count"] for r in results)
        total_articles = sum(r["total_articles"] for r in results)
        all_errors = [err for r in results for err in r["errors"]]

        return {
            "status": "success",
            "message": f"Fetched and saved {total_saved} news articles from 3 API calls",
            "total_saved": total_saved,
            "total_articles": total_articles,
            "results_by_region": results,
            "errors": all_errors if all_errors else None
        }

    except requests.exceptions.RequestException as req_error:
        raise HTTPException(status_code=500, detail=f"API request failed: {str(req_error)}")
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

        if location: # If location provided
            query = query.eq("location", location)

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
    try: # Fetch all news from database with location, sentiment, and title
        result = supabase.table("news").select("location, sentiment, title").execute()

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
            location = news_item.get("location", "Unknown")
            sentiment = news_item.get("sentiment")

            if location == "Unknown" or sentiment is None:
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