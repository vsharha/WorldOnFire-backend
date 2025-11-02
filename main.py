from fastapi import FastAPI, Header, HTTPException, Depends, Request, Body, BackgroundTasks
from supabase import create_client, Client
from eventregistry import *

from pydantic import BaseModel, constr, field_validator, model_validator
from dotenv import load_dotenv
import os
import requests
import json
from typing import Optional

from data_handlers import get_top_100_cities
load_dotenv()

app = FastAPI()
er = EventRegistry(apiKey = os.getenv("NEWS_API"))

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY") # Uses service key that bypasses RLS policies. DO NOT DISCLOSE THE KEY ON THE FRONTEND.
supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


def get_cities_query_or_clause() -> list[dict]: # Generate the $or clause with Wikipedia URIs for top 100 cities
    cities = get_top_100_cities()
    return [{"locationUri": f"http://en.wikipedia.org/wiki/{city}"} for city in cities]

# Pydantic model for news data
class NewsItem(BaseModel):
    title: str
    location: str
    image_url: Optional[str] = None
    description: Optional[str] = None

@app.get("/")
def welcome() -> dict[str, str]:
    return {"welcome_message": "This is a WorldOnFire official API. The World is on Fire right now."}


@app.post("/news") # Add a news event to the Supabase news table
def add_news(news_item: NewsItem):
    try: # Insert news item into the database
        result = supabase.table("news").insert({
            "title": news_item.title,
            "location": news_item.location,
            "image_url": news_item.image_url,
            "description": news_item.description
        }).execute()

        return {
            "status": "success",
            "message": "News item added successfully",
            "data": result.data
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to add news item: {str(e)}")

@app.get("/news") # Fetch news from EventRegistry API and save to database
def get_news():
    try:
        url = "https://eventregistry.org/api/v1/minuteStreamArticles"

        query_obj = {
            "$query": {
                "$and": [
                    {
                        "$or": get_cities_query_or_clause()
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

        # Save articles to database
        saved_count = 0
        errors = []

        if "articles" in data:
            for article in data["articles"]:
                try:
                    # Extract location from article (using the first location if available)
                    location = "Unknown"
                    if "location" in article and article["location"]:
                        if isinstance(article["location"], list) and len(article["location"]) > 0:
                            location = article["location"][0].get("label", {}).get("eng", "Unknown")
                        elif isinstance(article["location"], dict):
                            location = article["location"].get("label", {}).get("eng", "Unknown")

                    # Prepare news item
                    news_data = {
                        "title": article.get("title", "No title"),
                        "location": location,
                        "image_url": article.get("image") or article.get("imageUrl"),
                        "description": article.get("body") or article.get("description")
                    }

                    # Save to database
                    supabase.table("news").insert(news_data).execute()
                    saved_count += 1

                except Exception as article_error:
                    errors.append(str(article_error))
                    continue

        return {
            "status": "success",
            "message": f"Fetched and saved {saved_count} news articles",
            "saved_count": saved_count,
            "total_articles": len(data.get("articles", [])),
            "errors": errors if errors else None
        }

    except requests.exceptions.RequestException as req_error:
        raise HTTPException(status_code=500, detail=f"API request failed: {str(req_error)}")
    except Exception as general_error:
        raise HTTPException(status_code=500, detail=f"Failed to fetch and save news: {str(general_error)}")

@app.get("/news/search") # Retrieve saved news from the database, optionally filtered by city location
def search_news(location: Optional[str] = None):
    try:
        query = supabase.table("news").select("*")

        if location: # If location provided
            query = query.eq("location", location)
        result = query.execute()

        return {
            "status": "success",
            "count": len(result.data),
            "data": result.data
        }
    except Exception as search_error:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve news: {str(search_error)}")