from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.trip import Trip, TripShare
from app.models.itinerary import ItineraryDay, BudgetBreakdown
from app.models.place import Accommodation, Restaurant
from app.models.extra import WeatherSnapshot

router = APIRouter(prefix="/api/shared", tags=["shared"])


@router.get("/{token}/")
def get_shared_trip(token: str, db: Session = Depends(get_db)):
    share = db.query(TripShare).filter(
        TripShare.token == token,
        TripShare.revoked == False,
    ).first()
    if not share:
        raise HTTPException(status_code=404, detail="Shared trip not found or link expired")

    trip = share.trip
    days = db.query(ItineraryDay).filter(ItineraryDay.trip_id == trip.id).order_by(ItineraryDay.day_number).all()
    bd = db.query(BudgetBreakdown).filter(BudgetBreakdown.trip_id == trip.id).first()
    hotels = db.query(Accommodation).filter(Accommodation.trip_id == trip.id).all()
    weather = db.query(WeatherSnapshot).filter(WeatherSnapshot.trip_id == trip.id).all()

    return {
        "trip": {
            "title": trip.title,
            "days": trip.days,
            "budget": trip.budget,
            "currency": trip.currency,
            "travel_style": trip.travel_style.value if trip.travel_style else None,
            "interests": trip.interests,
            "travelers_adults": trip.travelers_adults,
            "destinations": [
                {"city": d.city, "state": d.state, "allocated_days": d.allocated_days}
                for d in trip.destinations
            ],
        },
        "itinerary": [
            {
                "day_number": day.day_number,
                "city": day.city,
                "theme": day.theme,
                "summary": day.summary,
                "activities": [
                    {"time_slot": a.time_slot.value, "start_time": a.start_time,
                     "place_name": a.place_name, "description": a.description,
                     "cost_estimate": a.cost_estimate}
                    for a in sorted(day.activities, key=lambda x: x.slot_order)
                ],
            }
            for day in days
        ],
        "budget_breakdown": {
            "stay": bd.stay, "food": bd.food, "transport": bd.transport,
            "activities": bd.activities, "buffer": bd.buffer,
            "total_estimate": bd.total_estimate, "status": bd.status,
        } if bd else None,
        "hotels": [
            {"city": h.city, "place_name": h.place_name, "cost_per_night": h.cost_per_night, "nights": h.nights}
            for h in hotels
        ],
        "weather": [
            {"city": w.city, "month": w.month, "temp_min": w.temp_min, "temp_max": w.temp_max,
             "condition": w.condition, "advice": w.advice}
            for w in weather
        ],
        "note": "This is a read-only preview. Place details, star ratings, prices and weather are illustrative estimates.",
    }
