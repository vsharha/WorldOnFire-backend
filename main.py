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


def get_cities_query_or_clause() -> list[dict]:
    """Generate the $or clause with Wikipedia URIs for top 100 cities"""
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



@app.post("/news")
def add_news(news_item: NewsItem):
    """Add a news event to the Supabase news table"""
    try:
        # Insert news item into the database
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

@app.get("/news")
def get_news(location: Optional[str] = None):
    """Retrieve news from the database, optionally filtered by city location"""
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
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve news: {str(e)}")

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
    "recentActivityArticlesUpdatesAfterMinsAgo": 60,
    "apiKey": os.getenv("NEWS_API")
}

try:
    response = requests.get(url, params=params, timeout=30)
    response.raise_for_status()

    data = response.json()
    print(data)
    print(json.dumps(data, indent=2))

except requests.exceptions.RequestException as e:
    print(f"Request failed: {e}")
except json.JSONDecodeError as e:
    print(f"JSON decode error: {e}")
    print(response.text)