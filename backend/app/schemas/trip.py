from datetime import date
from typing import Optional, List, Any
from pydantic import BaseModel
from app.models.trip import TripStatus, TravelStyle, Pace, BudgetScope


class TripDestinationOut(BaseModel):
    id: int
    country: str
    state: Optional[str]
    city: Optional[str]
    order: int
    allocated_days: int
    model_config = {"from_attributes": True}


class TripOut(BaseModel):
    id: int
    title: str
    status: TripStatus
    budget: Optional[float]
    currency: str
    days: Optional[int]
    travel_style: Optional[TravelStyle]
    travelers_adults: int
    travelers_children: int
    interests: List[str]
    start_date: Optional[date]
    start_month: Optional[str]
    thumbnail_url: Optional[str]
    destinations: List[TripDestinationOut] = []
    model_config = {"from_attributes": True}


class TripListOut(BaseModel):
    id: int
    title: str
    status: TripStatus
    budget: Optional[float]
    days: Optional[int]
    thumbnail_url: Optional[str]
    destinations: List[TripDestinationOut] = []
    model_config = {"from_attributes": True}
