"""
Generation Service — builds the full trip plan from collected slots.
Uses real place data from OSM/OpenTripMap + Gemini LLM to organize.
"""
import json
import logging
import httpx
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models.trip import Trip, TripStatus, TripDestination
from app.models.itinerary import ItineraryDay, Activity, PackingList, BudgetBreakdown, TransportLeg, TimeSlot
from app.models.place import Accommodation, Restaurant
from app.models.extra import WeatherSnapshot, LocalTip, GenerationLog, EmergencyContact
from app.services import llm_service, places_service, weather_service

logger = logging.getLogger(__name__)

PLAN_SCHEMA = """
{
  "title": "string (e.g. Rajasthan, at your own pace)",
  "thumbnail_description": "string (short description for image search)",
  "days": [
    {
      "day_number": 1,
      "city": "string",
      "theme": "string (e.g. The old city)",
      "summary": "string",
      "activities": [
        {
          "time_slot": "morning|afternoon|evening",
          "slot_order": 0,
          "start_time": "09:00",
          "place_name": "string",
          "place_type": "attraction|food|transport|leisure",
          "description": "2-3 sentences",
          "cost_estimate": 200,
          "duration_minutes": 90,
          "travel_minutes_to_next": 15,
          "tips": "string"
        }
      ]
    }
  ],
  "accommodations": [
    {
      "city": "string",
      "place_name": "string",
      "place_type": "hotel|hostel|guesthouse",
      "cost_per_night": 1500,
      "nights": 3,
      "check_in_day": 1,
      "check_out_day": 4,
      "notes": "string"
    }
  ],
  "restaurants": [
    {
      "city": "string",
      "day_number": 1,
      "meal_type": "breakfast|lunch|dinner",
      "place_name": "string",
      "cuisine": "string",
      "cost_estimate": 300,
      "notes": "string"
    }
  ],
  "packing_list": {
    "clothing": ["item1", "item2"],
    "toiletries": ["item1"],
    "documents": ["item1"],
    "medications": ["item1"],
    "electronics": ["item1"],
    "miscellaneous": ["item1"]
  },
  "budget_breakdown": {
    "stay": 4500,
    "food": 3000,
    "transport": 2000,
    "activities": 1500,
    "buffer": 1000
  },
  "transport_legs": [
    {
      "from_city": "string",
      "to_city": "string",
      "mode": "train|bus|flight|car",
      "duration_minutes": 120,
      "cost_min": 300,
      "cost_max": 800,
      "notes": "string"
    }
  ],
  "local_tips": ["tip1", "tip2", "tip3"],
  "emergency_info": {
    "police": "100",
    "ambulance": "108",
    "tourist_helpline": "1363"
  }
}
"""


def generate_plan_sync(trip_id: int, db: Session):
    """Synchronous plan generation — called directly or from Celery."""
    started_at = time.perf_counter()
    trip = db.query(Trip).filter(Trip.id == trip_id).first()
    if not trip:
        logger.error(f"Trip {trip_id} not found")
        return

    try:
        trip.status = TripStatus.CREATING
        db.commit()

        # 1. Get destination info
        destinations = db.query(TripDestination).filter(TripDestination.trip_id == trip_id).all()
        dest_str = ", ".join(
            filter(None, [d.city or d.state or d.country for d in destinations])
        ) or "India"

        # 2. Fetch real places from OSM. These requests are independent, so
        # run them concurrently; sequential geocoding + Overpass calls made
        # multi-city trips wait several network timeouts back-to-back.
        places_context = ""
        place_results: dict[str, list[dict]] = {}

        def fetch_places(city: str) -> tuple[str, list[dict]]:
            try:
                return city, places_service.search_attractions(city, limit=8)
            except Exception as e:
                logger.warning(f"Could not fetch places for {city}: {e}")
                return city, []

        cities = list(dict.fromkeys(dest.city or dest.state or "India" for dest in destinations))
        if not trip.thumbnail_url:
            trip.thumbnail_url = places_service.search_place_image(cities[0] if cities else "India")
        with ThreadPoolExecutor(max_workers=min(6, max(1, len(cities)))) as pool:
            futures = [pool.submit(fetch_places, city) for city in cities]
            for future in as_completed(futures):
                city, attractions = future.result()
                place_results[city] = attractions

        for city in cities:
            places_context += f"\nReal attractions in {city}:\n"
            for place in place_results.get(city, []):
                places_context += f"  - {place['name']} ({place.get('type', 'attraction')})\n"

        # 3. Get weather
        weather_context = ""
        try:
            if trip.start_month or trip.start_date:
                month = trip.start_month or (trip.start_date.strftime("%B") if trip.start_date else "")
                weather_context = f"\nWeather context: Travel in {month}. Plan outdoor activities accordingly."
        except Exception as e:
            logger.warning("Weather context build failed for trip %s: %s", trip_id, e)

        # 4. Build prompt
        budget_str = f"₹{trip.budget:,.0f}" if trip.budget else "budget not specified"
        travelers_str = f"{trip.travelers_adults} adult(s)"
        if trip.travelers_children:
            travelers_str += f" + {trip.travelers_children} child(ren)"

        prompt = f"""
You are an expert Indian travel planner. Create a detailed {trip.days}-day trip plan for {dest_str}.

TRIP DETAILS:
- Destination: {dest_str}
- Duration: {trip.days} days
- Budget: {budget_str} (total for group: {travelers_str})
- Travel style: {trip.travel_style.value if trip.travel_style else 'mid_range'}
- Pace: {trip.pace.value if trip.pace else 'moderate'}
- Interests: {', '.join(trip.interests) if trip.interests else 'general sightseeing'}
- Diet: {', '.join(trip.diet) if trip.diet else 'any'}
- Transport: {', '.join(trip.transport_modes) if trip.transport_modes else 'any'}
- Special requests: {trip.special_requests or 'none'}
{places_context}
{weather_context}

INSTRUCTIONS:
1. Use the REAL places listed above when possible. Do NOT invent fictional places.
2. Cluster activities by proximity each day — avoid zig-zagging.
3. Budget breakdown should sum to exactly the stated budget.
4. Keep the pace as specified: {'1-2 activities/day' if trip.pace and trip.pace.value == 'relaxed' else '3 activities/day' if trip.pace and trip.pace.value == 'moderate' else '4-5 activities/day'}.
5. Ensure restaurants match dietary preference: {', '.join(trip.diet) if trip.diet else 'any'}.
6. All cost_estimate values must be in INR.

Respond with ONLY valid JSON matching this exact schema:
{PLAN_SCHEMA}
"""

        # 5. Call LLM
        logger.info(
            "Trip %s preparation finished in %d ms; requesting plan from Gemini",
            trip_id,
            int((time.perf_counter() - started_at) * 1000),
        )
        plan = llm_service.generate_trip_plan_json(prompt)

        # 6. Save itinerary days
        for day_data in plan.get("days", []):
            day = ItineraryDay(
                trip_id=trip_id,
                day_number=day_data["day_number"],
                city=day_data.get("city"),
                theme=day_data.get("theme"),
                summary=day_data.get("summary"),
                total_travel_minutes=sum(a.get("travel_minutes_to_next", 0) for a in day_data.get("activities", [])),
            )
            db.add(day)
            db.flush()

            for act_data in day_data.get("activities", []):
                try:
                    slot = TimeSlot(act_data.get("time_slot", "morning"))
                except ValueError:
                    slot = TimeSlot.MORNING
                act = Activity(
                    day_id=day.id,
                    time_slot=slot,
                    slot_order=act_data.get("slot_order", 0),
                    start_time=act_data.get("start_time"),
                    place_name=act_data["place_name"],
                    place_type=act_data.get("place_type"),
                    description=act_data.get("description"),
                    cost_estimate=float(act_data.get("cost_estimate", 0)),
                    duration_minutes=int(act_data.get("duration_minutes", 60)),
                    travel_minutes_to_next=int(act_data.get("travel_minutes_to_next", 0)),
                    tips=act_data.get("tips"),
                )
                db.add(act)

        # 7. Save accommodations
        for acc_data in plan.get("accommodations", []):
            acc = Accommodation(
                trip_id=trip_id,
                city=acc_data["city"],
                place_name=acc_data["place_name"],
                place_type=acc_data.get("place_type"),
                cost_per_night=float(acc_data.get("cost_per_night", 0)),
                nights=int(acc_data.get("nights", 1)),
                check_in_day=acc_data.get("check_in_day"),
                check_out_day=acc_data.get("check_out_day"),
                notes=acc_data.get("notes"),
            )
            db.add(acc)

        # 8. Save restaurants
        for rest_data in plan.get("restaurants", []):
            rest = Restaurant(
                trip_id=trip_id,
                city=rest_data["city"],
                day_number=rest_data.get("day_number"),
                meal_type=rest_data.get("meal_type"),
                place_name=rest_data["place_name"],
                cuisine=rest_data.get("cuisine"),
                cost_estimate=float(rest_data.get("cost_estimate", 0)),
                notes=rest_data.get("notes"),
            )
            db.add(rest)

        # 9. Budget breakdown
        bd = plan.get("budget_breakdown", {})
        total = sum(bd.values())
        status = "comfortable" if total <= trip.budget * 0.9 else "tight" if total <= trip.budget * 1.05 else "unrealistic"
        budget_obj = BudgetBreakdown(
            trip_id=trip_id,
            stay=float(bd.get("stay", 0)),
            food=float(bd.get("food", 0)),
            transport=float(bd.get("transport", 0)),
            activities=float(bd.get("activities", 0)),
            buffer=float(bd.get("buffer", 0)),
            total_estimate=float(total),
            status=status,
        )
        db.add(budget_obj)

        # 10. Transport legs
        for leg_data in plan.get("transport_legs", []):
            leg = TransportLeg(
                trip_id=trip_id,
                from_city=leg_data["from_city"],
                to_city=leg_data["to_city"],
                mode=leg_data.get("mode"),
                duration_minutes=int(leg_data.get("duration_minutes", 0)),
                cost_min=float(leg_data.get("cost_min", 0)),
                cost_max=float(leg_data.get("cost_max", 0)),
                notes=leg_data.get("notes"),
            )
            db.add(leg)

        # 11. Packing list
        pl = PackingList(trip_id=trip_id, items=plan.get("packing_list", {}))
        db.add(pl)

        # 12. Local tips
        for tip_text in plan.get("local_tips", []):
            tip = LocalTip(
                city=dest_str,
                text=tip_text,
                source="ai_generated",
            )
            db.add(tip)

        # 13. Emergency info
        emergency = plan.get("emergency_info", {})
        for contact_type, phone in emergency.items():
            ec = EmergencyContact(city=dest_str, contact_type=contact_type, phone=str(phone))
            db.add(ec)

        # 14. Update trip title
        if plan.get("title"):
            trip.title = plan["title"]

        # 15. Weather snapshot
        try:
            weather_cities = list(dict.fromkeys(dest.city or dest.state or dest_str for dest in destinations))

            def fetch_weather(city: str) -> tuple[str, dict | None]:
                return city, weather_service.get_weather(city, trip.start_month or "")

            with ThreadPoolExecutor(max_workers=min(6, max(1, len(weather_cities)))) as pool:
                weather_futures = [pool.submit(fetch_weather, city) for city in weather_cities]
                for future in as_completed(weather_futures):
                    city, weather_data = future.result()
                    if weather_data:
                        db.add(WeatherSnapshot(
                            trip_id=trip_id,
                            city=city,
                            month=trip.start_month,
                            temp_min=weather_data.get("temp_min"),
                            temp_max=weather_data.get("temp_max"),
                            rain_probability=weather_data.get("rain_prob"),
                            condition=weather_data.get("condition"),
                            advice=weather_data.get("advice"),
                            source_type="seasonal_average",
                        ))
        except Exception as e:
            logger.warning(f"Weather fetch failed: {e}")

        # The plan and all related records are committed before exposing the
        # created status to clients.
        trip.status = TripStatus.CREATED
        db.commit()
        logger.info(
            "Trip %s generated successfully in %d ms",
            trip_id,
            int((time.perf_counter() - started_at) * 1000),
        )

    except Exception as e:
        logger.error(f"Generation failed for trip {trip_id}: {e}", exc_info=True)
        trip.status = TripStatus.FAILED
        log = GenerationLog(trip_id=trip_id, success=False, error=str(e))
        db.add(log)
        db.commit()
