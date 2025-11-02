from fastapi import FastAPI, Header, HTTPException, Depends, Request, Body, BackgroundTasks
from supabase import create_client, Client

from pydantic import BaseModel, constr, field_validator, model_validator
from dotenv import load_dotenv
import os
import requests
import json
from typing import Optional

from data_handlers import (
    get_asia_oceania_cities,
    get_europe_africa_middleeast_cities,
    get_americas_cities
)
load_dotenv()

app = FastAPI()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY") # Uses service key that bypasses RLS policies. DO NOT DISCLOSE THE KEY ON THE FRONTEND.
supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


def get_cities_query_or_clause(cities: list[str]) -> list[dict]: # Generate the $or clause with Wikipedia URIs for given cities
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

def fetch_and_save_articles(cities: list[str], region_name: str) -> dict:
    """Helper function to fetch articles for specific cities and save to database"""
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
                    "sentiment": article.get("sentiment", {}).get("label", {}).get("eng", "Unknown"),
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
def get_news():
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