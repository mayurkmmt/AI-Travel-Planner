import secrets
from typing import Optional
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.database import get_db
from app.limiter import limiter
from app.models.user import User
from app.models.trip import Trip, TripDestination, TripShare, TripStatus
from app.models.chat import ChatMessage, ChatSession
from app.models.itinerary import Activity, ItineraryDay, PackingList, BudgetBreakdown, TransportLeg
from app.models.place import Accommodation, Restaurant
from app.models.extra import WeatherSnapshot, LocalTip, EmergencyContact, GenerationLog
from app.core.dependencies import get_current_user
from app.schemas.trip import TripOut, TripListOut
from app.services import places_service

router = APIRouter(prefix="/api/trips", tags=["trips"])


def _own_trip(trip_id: int, user: User, db: Session) -> Trip:
    trip = db.query(Trip).filter(Trip.id == trip_id, Trip.user_id == user.id).first()
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
    return trip


@router.get("/")
def list_trips(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
    status: str = Query("all"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    base_query = db.query(Trip).filter(Trip.user_id == current_user.id)
    status_groups = {
        "created": [TripStatus.CREATED, TripStatus.DONE],
        "drafts": [TripStatus.DRAFT, TripStatus.COLLECTING],
    }

    query = base_query
    if status in status_groups:
        query = query.filter(Trip.status.in_(status_groups[status]))
    elif status == "other":
        query = query.filter(~Trip.status.in_(status_groups["created"] + status_groups["drafts"]))
    elif status != "all":
        raise HTTPException(status_code=400, detail="Invalid trip status filter")

    status_totals = dict(
        db.query(Trip.status, func.count(Trip.id))
        .filter(Trip.user_id == current_user.id)
        .group_by(Trip.status)
        .all()
    )
    counts = {
        "all": sum(status_totals.values()),
        "created": sum(status_totals.get(value, 0) for value in status_groups["created"]),
        "drafts": sum(status_totals.get(value, 0) for value in status_groups["drafts"]),
        "other": sum(count for value, count in status_totals.items() if value not in status_groups["created"] + status_groups["drafts"]),
    }
    total = query.count()
    trips = query.order_by(Trip.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    thumbnails_updated = False
    for trip in trips:
        if not trip.thumbnail_url and trip.destinations:
            destination = trip.destinations[0].city or trip.destinations[0].state
            if destination:
                trip.thumbnail_url = places_service.search_place_image(destination)
                thumbnails_updated = thumbnails_updated or bool(trip.thumbnail_url)
    if thumbnails_updated:
        db.commit()
    return {
        "items": [TripListOut.model_validate(t) for t in trips],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": max(1, (total + page_size - 1) // page_size),
        "counts": counts,
    }


@router.get("/{trip_id}/status/")
def get_trip_status(trip_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Return only the fields needed while the async plan is being generated."""
    trip = _own_trip(trip_id, current_user, db)
    result = {"trip_id": trip.id, "status": trip.status.value}
    if trip.status == TripStatus.FAILED:
        failure = (
            db.query(GenerationLog)
            .filter(GenerationLog.trip_id == trip.id, GenerationLog.success == False)
            .order_by(GenerationLog.id.desc())
            .first()
        )
        if failure and failure.error:
            result["error"] = failure.error
    return result


@router.get("/{trip_id}/")
def get_trip(trip_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    trip = _own_trip(trip_id, current_user, db)
    return TripOut.model_validate(trip)


class TripPatchRequest(BaseModel):
    title: Optional[str] = Field(None, max_length=200)
    special_requests: Optional[str] = Field(None, max_length=1000)


@router.patch("/{trip_id}/")
def patch_trip(
    trip_id: int,
    payload: TripPatchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    trip = _own_trip(trip_id, current_user, db)
    if payload.title is not None:
        trip.title = payload.title
    if payload.special_requests is not None:
        trip.special_requests = payload.special_requests or None
    db.commit()
    return TripOut.model_validate(trip)


@router.delete("/{trip_id}/", status_code=204)
def delete_trip(trip_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    trip = _own_trip(trip_id, current_user, db)

    # Delete dependent rows explicitly. Some older tables (notably packing_lists)
    # do not have an ORM relationship or database-level ON DELETE CASCADE, so
    # deleting only the Trip causes a foreign-key violation.
    itinerary_day_ids = db.query(ItineraryDay.id).filter(ItineraryDay.trip_id == trip_id)
    db.query(Activity).filter(Activity.day_id.in_(itinerary_day_ids)).delete(synchronize_session=False)
    db.query(TripDestination).filter(TripDestination.trip_id == trip_id).delete(synchronize_session=False)
    db.query(ChatMessage).filter(ChatMessage.trip_id == trip_id).delete(synchronize_session=False)
    db.query(ChatSession).filter(ChatSession.trip_id == trip_id).delete(synchronize_session=False)
    db.query(ItineraryDay).filter(ItineraryDay.trip_id == trip_id).delete(synchronize_session=False)
    db.query(PackingList).filter(PackingList.trip_id == trip_id).delete(synchronize_session=False)
    db.query(BudgetBreakdown).filter(BudgetBreakdown.trip_id == trip_id).delete(synchronize_session=False)
    db.query(TransportLeg).filter(TransportLeg.trip_id == trip_id).delete(synchronize_session=False)
    db.query(WeatherSnapshot).filter(WeatherSnapshot.trip_id == trip_id).delete(synchronize_session=False)
    db.query(TripShare).filter(TripShare.trip_id == trip_id).delete(synchronize_session=False)
    db.query(Accommodation).filter(Accommodation.trip_id == trip_id).delete(synchronize_session=False)
    db.query(Restaurant).filter(Restaurant.trip_id == trip_id).delete(synchronize_session=False)
    db.query(GenerationLog).filter(GenerationLog.trip_id == trip_id).delete(synchronize_session=False)
    db.delete(trip)
    db.commit()


@router.post("/{trip_id}/duplicate/")
def duplicate_trip(trip_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    original = _own_trip(trip_id, current_user, db)
    new_trip = Trip(
        user_id=current_user.id,
        title=f"{original.title} (copy)",
        budget=original.budget,
        currency=original.currency,
        budget_scope=original.budget_scope,
        days=original.days,
        start_date=original.start_date,
        start_month=original.start_month,
        starting_city=original.starting_city,
        travelers_adults=original.travelers_adults,
        travelers_children=original.travelers_children,
        child_ages=list(original.child_ages or []),
        travel_style=original.travel_style,
        pace=original.pace,
        interests=list(original.interests or []),
        diet=list(original.diet or []),
        transport_modes=list(original.transport_modes or []),
        special_requests=original.special_requests,
        thumbnail_url=original.thumbnail_url,
        status=TripStatus.DRAFT,
    )
    db.add(new_trip)
    db.flush()  # get new_trip.id before adding destinations
    for dest in original.destinations:
        db.add(TripDestination(
            trip_id=new_trip.id,
            country=dest.country,
            state=dest.state,
            city=dest.city,
            order=dest.order,
            allocated_days=dest.allocated_days,
        ))
    db.commit()
    db.refresh(new_trip)
    return TripOut.model_validate(new_trip)


@router.get("/{trip_id}/itinerary/")
def get_itinerary(trip_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    trip = _own_trip(trip_id, current_user, db)
    days = db.query(ItineraryDay).filter(ItineraryDay.trip_id == trip_id).order_by(ItineraryDay.day_number).all()
    result = []
    for day in days:
        result.append({
            "id": day.id,
            "day_number": day.day_number,
            "city": day.city,
            "theme": day.theme,
            "summary": day.summary,
            "total_travel_minutes": day.total_travel_minutes,
            "activities": [
                {
                    "id": a.id,
                    "time_slot": a.time_slot.value,
                    "start_time": a.start_time,
                    "place_name": a.place_name,
                    "place_type": a.place_type,
                    "description": a.description,
                    "cost_estimate": a.cost_estimate,
                    "duration_minutes": a.duration_minutes,
                    "travel_minutes_to_next": a.travel_minutes_to_next,
                    "tips": a.tips,
                    "lat": a.lat,
                    "lng": a.lng,
                }
                for a in sorted(day.activities, key=lambda x: x.slot_order)
            ],
        })
    return {"trip_id": trip_id, "days": result}


@router.get("/{trip_id}/hotels/")
def get_hotels(trip_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    trip = _own_trip(trip_id, current_user, db)
    hotels = db.query(Accommodation).filter(Accommodation.trip_id == trip_id).all()
    return {"trip_id": trip_id, "hotels": [
        {"id": h.id, "city": h.city, "place_name": h.place_name, "place_type": h.place_type,
         "cost_per_night": h.cost_per_night, "nights": h.nights, "total_cost": h.total_cost,
         "check_in_day": h.check_in_day, "check_out_day": h.check_out_day,
         "lat": h.lat, "lng": h.lng, "rating": h.rating, "notes": h.notes}
        for h in hotels
    ]}


@router.get("/{trip_id}/restaurants/")
def get_restaurants(trip_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    trip = _own_trip(trip_id, current_user, db)
    restaurants = db.query(Restaurant).filter(Restaurant.trip_id == trip_id).all()
    return {"trip_id": trip_id, "restaurants": [
        {"id": r.id, "city": r.city, "day_number": r.day_number, "meal_type": r.meal_type,
         "place_name": r.place_name, "cuisine": r.cuisine, "cost_estimate": r.cost_estimate, "notes": r.notes}
        for r in restaurants
    ]}


@router.get("/{trip_id}/budget/")
def get_budget(trip_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    trip = _own_trip(trip_id, current_user, db)
    bd = db.query(BudgetBreakdown).filter(BudgetBreakdown.trip_id == trip_id).first()
    transport = db.query(TransportLeg).filter(TransportLeg.trip_id == trip_id).all()
    if not bd:
        return {"trip_id": trip_id, "budget_breakdown": None}
    return {
        "trip_id": trip_id,
        "total_budget": trip.budget,
        "budget_breakdown": {
            "stay": bd.stay, "food": bd.food, "transport": bd.transport,
            "activities": bd.activities, "buffer": bd.buffer,
            "total_estimate": bd.total_estimate, "status": bd.status,
        },
        "transport_legs": [
            {"from_city": l.from_city, "to_city": l.to_city, "mode": l.mode,
             "duration_minutes": l.duration_minutes, "cost_min": l.cost_min, "cost_max": l.cost_max, "notes": l.notes}
            for l in transport
        ],
    }


@router.get("/{trip_id}/weather/")
def get_weather(trip_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    trip = _own_trip(trip_id, current_user, db)
    snapshots = db.query(WeatherSnapshot).filter(WeatherSnapshot.trip_id == trip_id).all()
    return {"trip_id": trip_id, "weather": [
        {"city": w.city, "month": w.month, "temp_min": w.temp_min, "temp_max": w.temp_max,
         "rain_probability": w.rain_probability, "condition": w.condition, "advice": w.advice,
         "source_type": w.source_type}
        for w in snapshots
    ]}


@router.get("/{trip_id}/tips/")
def get_tips(trip_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    trip = _own_trip(trip_id, current_user, db)
    destinations = db.query(TripDestination).filter(TripDestination.trip_id == trip_id).all()
    cities = [d.city or d.state or "India" for d in destinations]
    tips = db.query(LocalTip).filter(LocalTip.city.in_(cities)).all()
    return {"trip_id": trip_id, "tips": [
        {"city": t.city, "category": t.category, "text": t.text, "source": t.source}
        for t in tips
    ]}


@router.get("/{trip_id}/emergency/")
def get_emergency(trip_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    trip = _own_trip(trip_id, current_user, db)
    destinations = db.query(TripDestination).filter(TripDestination.trip_id == trip_id).all()
    cities = [d.city or "India" for d in destinations]
    contacts = db.query(EmergencyContact).filter(EmergencyContact.city.in_(cities)).all()
    return {"trip_id": trip_id, "emergency": [
        {"city": e.city, "type": e.contact_type, "name": e.name, "phone": e.phone}
        for e in contacts
    ]}


@router.get("/{trip_id}/packing-list/")
def get_packing_list(trip_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    trip = _own_trip(trip_id, current_user, db)
    pl = db.query(PackingList).filter(PackingList.trip_id == trip_id).first()
    return {"trip_id": trip_id, "packing_list": pl.items if pl else {}}


@router.get("/{trip_id}/map/")
def get_map(trip_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    trip = _own_trip(trip_id, current_user, db)
    days = db.query(ItineraryDay).filter(ItineraryDay.trip_id == trip_id).all()
    features = []
    for day in days:
        for act in day.activities:
            if act.lat and act.lng:
                features.append({
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [act.lng, act.lat]},
                    "properties": {
                        "name": act.place_name, "day": day.day_number,
                        "time_slot": act.time_slot.value, "description": act.description,
                    },
                })
    return {"type": "FeatureCollection", "features": features}


@router.post("/{trip_id}/share/")
def create_share(trip_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    trip = _own_trip(trip_id, current_user, db)
    existing = db.query(TripShare).filter(TripShare.trip_id == trip_id, TripShare.revoked == False).first()
    if existing:
        return {"token": existing.token, "url": f"/shared/{existing.token}"}
    token = secrets.token_urlsafe(24)
    share = TripShare(trip_id=trip_id, token=token)
    db.add(share)
    db.commit()
    return {"token": token, "url": f"/shared/{token}"}


@router.delete("/{trip_id}/share/", status_code=204)
def revoke_share(trip_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    trip = _own_trip(trip_id, current_user, db)
    share = db.query(TripShare).filter(TripShare.trip_id == trip_id).first()
    if share:
        share.revoked = True
        db.commit()


class RegenerateRequest(BaseModel):
    budget: Optional[float] = None
    days: Optional[int] = None
    travelers_adults: Optional[int] = None
    travel_style: Optional[str] = None
    pace: Optional[str] = None
    interests: Optional[list[str]] = None
    diet: Optional[list[str]] = None
    transport_mode: Optional[str] = None
    special_requests: Optional[str] = None


@router.post("/{trip_id}/regenerate/")
@limiter.limit("5/minute")
def regenerate_trip(
    request: Request,
    trip_id: int,
    payload: RegenerateRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    trip = _own_trip(trip_id, current_user, db)

    # Apply updated parameters
    if payload.budget is not None:
        trip.budget = payload.budget
    if payload.days is not None:
        trip.days = payload.days
    if payload.travelers_adults is not None:
        trip.travelers_adults = payload.travelers_adults
    if payload.travel_style is not None:
        from app.models.trip import TravelStyle
        try:
            trip.travel_style = TravelStyle(payload.travel_style.lower().replace("-", "_"))
        except ValueError:
            pass
    if payload.pace is not None:
        from app.models.trip import Pace
        try:
            trip.pace = Pace(payload.pace)
        except ValueError:
            pass
    if payload.interests is not None:
        trip.interests = payload.interests
    if payload.diet is not None:
        trip.diet = payload.diet
    if payload.transport_mode is not None:
        trip.transport_modes = [payload.transport_mode]
    if payload.special_requests is not None:
        trip.special_requests = payload.special_requests or None

    # Clear old plan data so generation starts fresh
    itinerary_day_ids = db.query(ItineraryDay.id).filter(ItineraryDay.trip_id == trip_id)
    db.query(Activity).filter(Activity.day_id.in_(itinerary_day_ids)).delete(synchronize_session=False)
    db.query(ItineraryDay).filter(ItineraryDay.trip_id == trip_id).delete(synchronize_session=False)
    db.query(PackingList).filter(PackingList.trip_id == trip_id).delete(synchronize_session=False)
    db.query(BudgetBreakdown).filter(BudgetBreakdown.trip_id == trip_id).delete(synchronize_session=False)
    db.query(TransportLeg).filter(TransportLeg.trip_id == trip_id).delete(synchronize_session=False)
    db.query(WeatherSnapshot).filter(WeatherSnapshot.trip_id == trip_id).delete(synchronize_session=False)
    db.query(Accommodation).filter(Accommodation.trip_id == trip_id).delete(synchronize_session=False)
    db.query(Restaurant).filter(Restaurant.trip_id == trip_id).delete(synchronize_session=False)

    trip.status = TripStatus.CREATING
    db.commit()

    from app.config import settings
    if settings.DEBUG:
        from app.routers.chat import _generate_plan_in_web_process
        background_tasks.add_task(_generate_plan_in_web_process, trip_id)
    else:
        try:
            from app.workers.tasks import generate_trip_plan
            result = generate_trip_plan.delay(trip_id)
            trip.celery_task_id = result.id
            db.commit()
        except Exception:
            from app.routers.chat import _generate_plan_in_web_process
            background_tasks.add_task(_generate_plan_in_web_process, trip_id)

    return {"trip_id": trip_id, "status": "creating"}
