from fastapi import APIRouter, Query
import httpx

router = APIRouter(prefix="/api/locations", tags=["locations"])

# Static Indian states — can be replaced with a DB table later
INDIAN_STATES = [
    "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chhattisgarh",
    "Goa", "Gujarat", "Haryana", "Himachal Pradesh", "Jharkhand", "Karnataka",
    "Kerala", "Madhya Pradesh", "Maharashtra", "Manipur", "Meghalaya", "Mizoram",
    "Nagaland", "Odisha", "Punjab", "Rajasthan", "Sikkim", "Tamil Nadu", "Telangana",
    "Tripura", "Uttar Pradesh", "Uttarakhand", "West Bengal",
    "Delhi", "Chandigarh", "Jammu and Kashmir", "Ladakh", "Puducherry",
]


@router.get("/states/")
def get_states(country: str = Query(default="IN")):
    return {"country": country, "states": INDIAN_STATES}


@router.get("/cities/")
async def get_cities(state: str = Query(default=""), q: str = Query(default="")):
    """Search cities using Nominatim."""
    query = f"{q}, {state}, India" if state else f"{q}, India"
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                "https://nominatim.openstreetmap.org/search",
                params={
                    "q": query,
                    "format": "json",
                    "limit": 10,
                    "addressdetails": 1,
                    "featuretype": "city",
                },
                headers={"User-Agent": "AITravelPlanner/1.0"},
                timeout=10,
            )
            data = resp.json()
            cities = []
            seen = set()
            for item in data:
                address = item.get("address", {})
                city_name = (
                    address.get("city") or address.get("town") or
                    address.get("village") or item.get("display_name", "").split(",")[0]
                )
                if city_name and city_name not in seen:
                    seen.add(city_name)
                    cities.append({
                        "name": city_name,
                        "display": item.get("display_name"),
                        "lat": item.get("lat"),
                        "lng": item.get("lon"),
                    })
            return {"cities": cities}
    except Exception as e:
        return {"cities": [], "error": str(e)}
