"""OSM/OpenTripMap places service — free, no API key needed for basic OSM."""
import httpx
import logging
from typing import Optional

logger = logging.getLogger(__name__)

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
OPENTRIPMAP_URL = "https://api.opentripmap.com/0.1/en/places"

# OSM place type mappings
ATTRACTION_TAGS = ["tourism=attraction", "tourism=museum", "tourism=viewpoint",
                   "historic=fort", "historic=monument", "amenity=place_of_worship"]


def search_place_image(place: str) -> Optional[str]:
    """Return a Wikimedia Commons image for a conversation destination."""
    try:
        response = httpx.get(
            "https://commons.wikimedia.org/w/api.php",
            params={
                "action": "query",
                "generator": "search",
                "gsrsearch": f"{place} India",
                "gsrnamespace": 6,
                "gsrlimit": 1,
                "prop": "imageinfo",
                "iiprop": "url",
                "iiurlwidth": 1200,
                "format": "json",
                "formatversion": 2,
            },
            headers={"User-Agent": "AITravelPlanner/1.0"},
            timeout=8,
        )
        response.raise_for_status()
        pages = response.json().get("query", {}).get("pages", [])
        image_info = pages[0].get("imageinfo", []) if pages else []
        if not image_info:
            return None
        return image_info[0].get("thumburl") or image_info[0].get("url")
    except Exception as e:
        logger.warning("Place image lookup failed for %s: %s", place, e)
        return None


def _geocode_city(city: str) -> Optional[tuple[float, float]]:
    """Get lat/lng for a city using Nominatim."""
    try:
        resp = httpx.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": f"{city}, India", "format": "json", "limit": 1},
            headers={"User-Agent": "AITravelPlanner/1.0"},
            timeout=10,
        )
        data = resp.json()
        if data:
            return float(data[0]["lat"]), float(data[0]["lon"])
    except Exception as e:
        logger.warning(f"Geocode failed for {city}: {e}")
    return None


def search_attractions(city: str, limit: int = 10) -> list[dict]:
    """Search for tourist attractions in a city using Overpass API."""
    coords = _geocode_city(city)
    if not coords:
        return []
    lat, lng = coords
    radius = 25000  # 25km radius

    query = f"""
[out:json][timeout:25];
(
  node["tourism"~"attraction|museum|viewpoint|gallery"]["name"](around:{radius},{lat},{lng});
  node["historic"~"fort|monument|ruins|castle"]["name"](around:{radius},{lat},{lng});
  node["leisure"="park"]["name"](around:{radius},{lat},{lng});
);
out body 20;
"""
    try:
        resp = httpx.post(OVERPASS_URL, data={"data": query}, timeout=30)
        data = resp.json()
        places = []
        for el in data.get("elements", [])[:limit]:
            tags = el.get("tags", {})
            places.append({
                "name": tags.get("name", "Unnamed"),
                "type": tags.get("tourism") or tags.get("historic") or "attraction",
                "lat": el.get("lat"),
                "lng": el.get("lon"),
                "source": "osm",
            })
        return places
    except Exception as e:
        logger.warning(f"Overpass query failed: {e}")
        return []


def search_hotels(city: str, limit: int = 5) -> list[dict]:
    """Search for hotels using Overpass API."""
    coords = _geocode_city(city)
    if not coords:
        return []
    lat, lng = coords

    query = f"""
[out:json][timeout:25];
(
  node["tourism"="hotel"]["name"](around:20000,{lat},{lng});
  node["tourism"="guest_house"]["name"](around:20000,{lat},{lng});
);
out body {limit};
"""
    try:
        resp = httpx.post(OVERPASS_URL, data={"data": query}, timeout=30)
        data = resp.json()
        hotels = []
        for el in data.get("elements", [])[:limit]:
            tags = el.get("tags", {})
            hotels.append({
                "name": tags.get("name", "Unnamed Hotel"),
                "type": tags.get("tourism", "hotel"),
                "lat": el.get("lat"),
                "lng": el.get("lon"),
                "stars": tags.get("stars"),
                "source": "osm",
            })
        return hotels
    except Exception as e:
        logger.warning(f"Hotel search failed: {e}")
        return []


def search_restaurants(city: str, diet: list = None, limit: int = 5) -> list[dict]:
    """Search for restaurants using Overpass API."""
    coords = _geocode_city(city)
    if not coords:
        return []
    lat, lng = coords

    query = f"""
[out:json][timeout:25];
(
  node["amenity"="restaurant"]["name"](around:15000,{lat},{lng});
  node["amenity"="cafe"]["name"](around:15000,{lat},{lng});
);
out body {limit};
"""
    try:
        resp = httpx.post(OVERPASS_URL, data={"data": query}, timeout=30)
        data = resp.json()
        restaurants = []
        for el in data.get("elements", [])[:limit]:
            tags = el.get("tags", {})
            restaurants.append({
                "name": tags.get("name", "Unnamed Restaurant"),
                "cuisine": tags.get("cuisine", ""),
                "diet": tags.get("diet:vegetarian", ""),
                "lat": el.get("lat"),
                "lng": el.get("lon"),
                "source": "osm",
            })
        return restaurants
    except Exception as e:
        logger.warning(f"Restaurant search failed: {e}")
        return []
