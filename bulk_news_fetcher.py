from supabase import create_client, Client
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

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

def get_cities_query_or_clause(cities: list[str]) -> list[dict]:
    """Helper to generate the $or clause with Wikipedia URIs for given cities"""
    return [{"locationUri": f"http://en.wikipedia.org/wiki/{city}"} for city in cities]

def fetch_and_save_articles_bulk(cities: list[str], region_name: str, hours: int = 5) -> dict:
    """
    Fetch articles for specific cities from the last N hours and save to database.

    Args:
        cities: List of city names to fetch news for
        region_name: Name of the region (for logging/reporting)
        hours: Number of hours to look back (default: 5)

    Returns:
        Dictionary with fetch results including saved count and errors
    """
    url = "https://eventregistry.org/api/v1/minuteStreamArticles"
    minutes_ago = hours * 60  # Convert hours to minutes

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
        "recentActivityArticlesMaxArticleCount": 100,  # Increased for bulk fetch
        "recentActivityArticlesUpdatesAfterMinsAgo": minutes_ago,
        "apiKey": os.getenv("NEWS_API")
    }

    try:
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        print(f"Fetching {region_name} - Last {hours} hours")

        saved_count = 0
        errors = []

        # Parse the correct structure: recentActivityArticles.activity
        if "recentActivityArticles" in data and "activity" in data["recentActivityArticles"]:
            articles = data["recentActivityArticles"]["activity"]

            for article in articles:
                try:
                    # Extract location from article
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
            "errors": errors,
            "hours_fetched": hours
        }

    except requests.exceptions.RequestException as req_error:
        return {
            "region": region_name,
            "saved_count": 0,
            "total_articles": 0,
            "errors": [f"API request failed: {str(req_error)}"],
            "hours_fetched": hours
        }
    except Exception as general_error:
        return {
            "region": region_name,
            "saved_count": 0,
            "total_articles": 0,
            "errors": [f"Failed to fetch and save news: {str(general_error)}"],
            "hours_fetched": hours
        }

def fetch_bulk_news(hours: int = 5) -> dict:
    """
    Fetch news from the last N hours for all regions.

    Args:
        hours: Number of hours to look back (default: 5)

    Returns:
        Dictionary with aggregated results from all regions
    """
    results = []

    # Fetch from all regions
    asia_result = fetch_and_save_articles_bulk(get_asia_oceania_cities(), "Asia & Oceania", hours)
    results.append(asia_result)

    europe_result = fetch_and_save_articles_bulk(
        get_europe_africa_middleeast_cities(),
        "Europe, Africa & Middle East",
        hours
    )
    results.append(europe_result)

    americas_result = fetch_and_save_articles_bulk(get_americas_cities(), "Americas", hours)
    results.append(americas_result)

    # Aggregate results
    total_saved = sum(r["saved_count"] for r in results)
    total_articles = sum(r["total_articles"] for r in results)
    all_errors = [err for r in results for err in r["errors"]]

    return {
        "status": "success",
        "message": f"Fetched and saved {total_saved} news articles from the last {hours} hours",
        "total_saved": total_saved,
        "total_articles": total_articles,
        "hours_fetched": hours,
        "results_by_region": results,
        "errors": all_errors if all_errors else None
    }

if __name__ == "__main__":
    # Can be run directly to populate database with last 5 hours of news
    print("Fetching news from the last 5 hours...")
    result = fetch_bulk_news(hours=5)
    print(f"\nResults:")
    print(f"Total saved: {result['total_saved']}")
    print(f"Total articles: {result['total_articles']}")
    print(f"\nBy region:")
    for region_result in result['results_by_region']:
        print(f"  {region_result['region']}: {region_result['saved_count']}/{region_result['total_articles']} saved")

    if result['errors']:
        print(f"\nErrors: {len(result['errors'])}")