import enum
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime,
    ForeignKey, Text, JSON, Enum, func, Date
)
from sqlalchemy.orm import relationship
from app.database import Base


class TripStatus(str, enum.Enum):
    DRAFT = "draft"
    CREATING = "creating"
    CREATED = "created"
    # Kept for compatibility with trips created before the status migration.
    COLLECTING = "collecting"
    CONFIRMING = "confirming"
    GENERATING = "generating"
    DONE = "done"
    FAILED = "failed"


class TravelStyle(str, enum.Enum):
    BUDGET = "budget"
    MID_RANGE = "mid_range"
    LUXURY = "luxury"


class Pace(str, enum.Enum):
    RELAXED = "relaxed"
    MODERATE = "moderate"
    PACKED = "packed"


class BudgetScope(str, enum.Enum):
    TOTAL = "total"
    PER_PERSON = "per_person"


class Trip(Base):
    __tablename__ = "trips"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # Core inputs
    title = Column(String, default="My Trip")
    budget = Column(Float, nullable=True)
    currency = Column(String, default="INR")
    budget_scope = Column(Enum(BudgetScope), default=BudgetScope.TOTAL)
    days = Column(Integer, nullable=True)
    start_date = Column(Date, nullable=True)
    start_month = Column(String, nullable=True)
    starting_city = Column(String, nullable=True)

    # Traveler info
    travelers_adults = Column(Integer, default=1)
    travelers_children = Column(Integer, default=0)
    child_ages = Column(JSON, default=list)

    # Preferences
    travel_style = Column(Enum(TravelStyle), default=TravelStyle.MID_RANGE)
    pace = Column(Enum(Pace), default=Pace.MODERATE)
    diet = Column(JSON, default=list)
    transport_modes = Column(JSON, default=list)
    interests = Column(JSON, default=list)
    special_requests = Column(Text, nullable=True)

    # Status
    status = Column(Enum(TripStatus), default=TripStatus.DRAFT)
    thumbnail_url = Column(String, nullable=True)
    celery_task_id = Column(String, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="trips")
    destinations = relationship("TripDestination", back_populates="trip", cascade="all, delete-orphan")
    chat_messages = relationship("ChatMessage", back_populates="trip", cascade="all, delete-orphan")
    chat_session = relationship("ChatSession", back_populates="trip", uselist=False, cascade="all, delete-orphan")
    itinerary_days = relationship("ItineraryDay", back_populates="trip", cascade="all, delete-orphan", order_by="ItineraryDay.day_number")
    budget_breakdown = relationship("BudgetBreakdown", back_populates="trip", uselist=False, cascade="all, delete-orphan")
    transport_legs = relationship("TransportLeg", back_populates="trip", cascade="all, delete-orphan")
    weather_snapshots = relationship("WeatherSnapshot", back_populates="trip", cascade="all, delete-orphan")
    share = relationship("TripShare", back_populates="trip", uselist=False, cascade="all, delete-orphan")
    accommodations = relationship("Accommodation", back_populates="trip", cascade="all, delete-orphan")
    restaurants = relationship("Restaurant", back_populates="trip", cascade="all, delete-orphan")
    generation_logs = relationship("GenerationLog", back_populates="trip", cascade="all, delete-orphan")


class TripDestination(Base):
    __tablename__ = "trip_destinations"

    id = Column(Integer, primary_key=True, index=True)
    trip_id = Column(Integer, ForeignKey("trips.id"), nullable=False)
    country = Column(String, default="India")
    state = Column(String, nullable=True)
    city = Column(String, nullable=True)
    order = Column(Integer, default=0)
    allocated_days = Column(Integer, default=1)

    trip = relationship("Trip", back_populates="destinations")


class TripShare(Base):
    __tablename__ = "trip_shares"

    id = Column(Integer, primary_key=True, index=True)
    trip_id = Column(Integer, ForeignKey("trips.id"), nullable=False)
    token = Column(String, unique=True, index=True, nullable=False)
    revoked = Column(Boolean, default=False)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    trip = relationship("Trip", back_populates="share")
