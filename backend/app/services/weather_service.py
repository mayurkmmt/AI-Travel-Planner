"""Open-Meteo weather service — completely free."""
import httpx
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Seasonal climate averages for major Indian cities (fallback)
SEASONAL_DATA = {
    "jaipur": {
        "january": {"temp_min": 7, "temp_max": 22, "rain_prob": 5, "condition": "Clear & Pleasant", "advice": "Perfect weather for sightseeing"},
        "february": {"temp_min": 10, "temp_max": 25, "rain_prob": 5, "condition": "Warm & Sunny", "advice": "Ideal travel month"},
        "march": {"temp_min": 15, "temp_max": 30, "rain_prob": 5, "condition": "Getting Warm", "advice": "Great for outdoor exploration"},
        "april": {"temp_min": 22, "temp_max": 38, "rain_prob": 5, "condition": "Hot", "advice": "Carry sunscreen and stay hydrated"},
        "may": {"temp_min": 26, "temp_max": 44, "rain_prob": 5, "condition": "Very Hot", "advice": "Avoid midday outdoor activities"},
        "june": {"temp_min": 27, "temp_max": 42, "rain_prob": 30, "condition": "Hot & Humid", "advice": "Pre-monsoon, carry light rain gear"},
        "july": {"temp_min": 25, "temp_max": 36, "rain_prob": 70, "condition": "Monsoon", "advice": "Carry rain gear; some places may be closed"},
        "august": {"temp_min": 24, "temp_max": 35, "rain_prob": 65, "condition": "Monsoon", "advice": "Lush green but rainy; plan indoor activities"},
        "september": {"temp_min": 23, "temp_max": 36, "rain_prob": 40, "condition": "Post-monsoon", "advice": "Cooling down; good travel window"},
        "october": {"temp_min": 17, "temp_max": 33, "rain_prob": 10, "condition": "Pleasant", "advice": "Excellent travel conditions"},
        "november": {"temp_min": 11, "temp_max": 28, "rain_prob": 5, "condition": "Cool & Pleasant", "advice": "Best month to visit"},
        "december": {"temp_min": 7, "temp_max": 22, "rain_prob": 5, "condition": "Cool", "advice": "Carry a light jacket for evenings"},
    }
}

# Default seasonal data for cities not in database
DEFAULT_SEASONAL = {
    "january": {"temp_min": 12, "temp_max": 24, "rain_prob": 10, "condition": "Pleasant", "advice": "Good travel weather"},
    "february": {"temp_min": 14, "temp_max": 26, "rain_prob": 10, "condition": "Pleasant", "advice": "Good travel weather"},
    "march": {"temp_min": 18, "temp_max": 32, "rain_prob": 10, "condition": "Warm", "advice": "Start carrying water"},
    "april": {"temp_min": 22, "temp_max": 36, "rain_prob": 10, "condition": "Hot", "advice": "Stay hydrated"},
    "may": {"temp_min": 25, "temp_max": 40, "rain_prob": 15, "condition": "Very Hot", "advice": "Avoid midday sun"},
    "june": {"temp_min": 26, "temp_max": 38, "rain_prob": 40, "condition": "Pre-monsoon", "advice": "Carry rain gear"},
    "july": {"temp_min": 24, "temp_max": 32, "rain_prob": 75, "condition": "Monsoon", "advice": "Heavy rains expected"},
    "august": {"temp_min": 23, "temp_max": 31, "rain_prob": 70, "condition": "Monsoon", "advice": "Rain gear essential"},
    "september": {"temp_min": 22, "temp_max": 32, "rain_prob": 45, "condition": "Post-monsoon", "advice": "Cooling down nicely"},
    "october": {"temp_min": 18, "temp_max": 30, "rain_prob": 15, "condition": "Pleasant", "advice": "Great travel season"},
    "november": {"temp_min": 14, "temp_max": 26, "rain_prob": 10, "condition": "Cool & Pleasant", "advice": "Excellent conditions"},
    "december": {"temp_min": 11, "temp_max": 22, "rain_prob": 5, "condition": "Cool", "advice": "Light jacket recommended"},
}


def get_weather(city: str, month: str) -> Optional[dict]:
    """Get weather data — tries Open-Meteo first, falls back to seasonal averages."""
    if not month:
        return None

    month_lower = month.lower()

    # Try Open-Meteo for forecast (only works for near future)
    try:
        geocode_resp = httpx.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": city, "count": 1, "language": "en", "format": "json"},
            timeout=10,
        )
        geo_data = geocode_resp.json()
        if geo_data.get("results"):
            result = geo_data["results"][0]
            lat, lng = result["latitude"], result["longitude"]
            weather_resp = httpx.get(
                "https://api.open-meteo.com/v1/forecast",
                params={
                    "latitude": lat,
                    "longitude": lng,
                    "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max",
                    "forecast_days": 7,
                    "timezone": "Asia/Kolkata",
                },
                timeout=10,
            )
            w_data = weather_resp.json()
            daily = w_data.get("daily", {})
            if daily:
                temps_max = daily.get("temperature_2m_max", [])
                temps_min = daily.get("temperature_2m_min", [])
                rain_probs = daily.get("precipitation_probability_max", [])
                if temps_max and temps_min:
                    avg_max = sum(temps_max) / len(temps_max)
                    avg_min = sum(temps_min) / len(temps_min)
                    avg_rain = sum(rain_probs) / len(rain_probs) if rain_probs else 20
                    return {
                        "temp_min": round(avg_min, 1),
                        "temp_max": round(avg_max, 1),
                        "rain_prob": round(avg_rain),
                        "condition": "Forecast data",
                        "advice": "Check local forecast before travelling",
                        "source": "forecast",
                    }
    except Exception as e:
        logger.warning(f"Open-Meteo forecast failed for {city}: {e}")

    # Fallback to seasonal averages
    city_data = SEASONAL_DATA.get(city.lower(), DEFAULT_SEASONAL)
    seasonal = city_data.get(month_lower, DEFAULT_SEASONAL.get("january"))
    if seasonal:
        return {**seasonal, "source": "seasonal_average"}

    return None
