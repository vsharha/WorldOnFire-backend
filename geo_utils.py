"""
Geocoding and coordinate caching utilities
"""

from typing import Optional
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError
from datetime import datetime
from supabase import Client


def get_cached_coordinates(supabase: Client, location: str) -> Optional[list[float]]:
    """
    Retrieve cached coordinates for a location from the database.

    Args:
        supabase: Supabase client instance
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


def cache_coordinates(supabase: Client, location: str, latitude: float, longitude: float) -> bool:
    """
    Store coordinates for a location in the database cache.

    Args:
        supabase: Supabase client instance
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


def geocode_and_cache_location(supabase: Client, location: str, geolocator: Optional[Nominatim] = None) -> Optional[list[float]]:
    """
    Geocode a location and cache its coordinates in the database.
    First checks if coordinates are already cached.

    Args:
        supabase: Supabase client instance
        location: The location name to geocode
        geolocator: Optional Nominatim geolocator instance (creates new one if not provided)

    Returns:
        [latitude, longitude] if successful, None otherwise
    """
    # Skip invalid locations
    if not location or location == "Unknown":
        return None

    # First check cache
    cached_coords = get_cached_coordinates(supabase, location)
    if cached_coords:
        return cached_coords

    # Cache miss - geocode the location
    if geolocator is None:
        geolocator = Nominatim(user_agent="worldonfire-backend")

    try:
        geo_result = geolocator.geocode(location, timeout=10)
        if geo_result:
            coordinates = [geo_result.latitude, geo_result.longitude]
            # Cache the result for future use
            cache_coordinates(supabase, location, geo_result.latitude, geo_result.longitude)
            print(f"Geocoded and cached: {location}")
            return coordinates
    except (GeocoderTimedOut, GeocoderServiceError) as geo_error:
        print(f"Geocoding error for {location}: {str(geo_error)}")
    except Exception as e:
        print(f"Unexpected error geocoding {location}: {str(e)}")

    return None