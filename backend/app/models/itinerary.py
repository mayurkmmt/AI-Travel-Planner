import enum
from sqlalchemy import (
    Column, Integer, String, Float, DateTime, ForeignKey,
    Text, JSON, Enum, func, Boolean, Date
)
from sqlalchemy.orm import relationship
from app.database import Base


class TimeSlot(str, enum.Enum):
    MORNING = "morning"
    AFTERNOON = "afternoon"
    EVENING = "evening"


class ItineraryDay(Base):
    __tablename__ = "itinerary_days"

    id = Column(Integer, primary_key=True, index=True)
    trip_id = Column(Integer, ForeignKey("trips.id"), nullable=False)
    day_number = Column(Integer, nullable=False)
    date = Column(Date, nullable=True)
    city = Column(String, nullable=True)
    summary = Column(Text, nullable=True)
    theme = Column(String, nullable=True)
    total_travel_minutes = Column(Integer, default=0)

    trip = relationship("Trip", back_populates="itinerary_days")
    activities = relationship("Activity", back_populates="day", cascade="all, delete-orphan", order_by="Activity.slot_order")


class Activity(Base):
    __tablename__ = "activities"

    id = Column(Integer, primary_key=True, index=True)
    day_id = Column(Integer, ForeignKey("itinerary_days.id"), nullable=False)
    time_slot = Column(Enum(TimeSlot), nullable=False)
    slot_order = Column(Integer, default=0)
    start_time = Column(String, nullable=True)
    place_name = Column(String, nullable=False)
    place_type = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    cost_estimate = Column(Float, default=0.0)
    duration_minutes = Column(Integer, default=60)
    travel_minutes_to_next = Column(Integer, default=0)
    lat = Column(Float, nullable=True)
    lng = Column(Float, nullable=True)
    tips = Column(Text, nullable=True)
    can_swap = Column(Boolean, default=True)

    day = relationship("ItineraryDay", back_populates="activities")


class PackingList(Base):
    __tablename__ = "packing_lists"

    id = Column(Integer, primary_key=True, index=True)
    trip_id = Column(Integer, ForeignKey("trips.id"), nullable=False, unique=True)
    items = Column(JSON, default=dict)  # {category: [item, ...]}
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class BudgetBreakdown(Base):
    __tablename__ = "budget_breakdowns"

    id = Column(Integer, primary_key=True, index=True)
    trip_id = Column(Integer, ForeignKey("trips.id"), nullable=False, unique=True)
    stay = Column(Float, default=0.0)
    food = Column(Float, default=0.0)
    transport = Column(Float, default=0.0)
    activities = Column(Float, default=0.0)
    buffer = Column(Float, default=0.0)
    total_estimate = Column(Float, default=0.0)
    status = Column(String, default="comfortable")  # comfortable | tight | unrealistic
    details = Column(JSON, default=dict)

    trip = relationship("Trip", back_populates="budget_breakdown")


class TransportLeg(Base):
    __tablename__ = "transport_legs"

    id = Column(Integer, primary_key=True, index=True)
    trip_id = Column(Integer, ForeignKey("trips.id"), nullable=False)
    from_city = Column(String, nullable=False)
    to_city = Column(String, nullable=False)
    mode = Column(String, nullable=True)
    duration_minutes = Column(Integer, nullable=True)
    cost_min = Column(Float, nullable=True)
    cost_max = Column(Float, nullable=True)
    notes = Column(Text, nullable=True)
    day_number = Column(Integer, nullable=True)

    trip = relationship("Trip", back_populates="transport_legs")
