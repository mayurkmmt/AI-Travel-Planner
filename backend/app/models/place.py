from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text, JSON, Boolean, func, Date
from sqlalchemy.orm import relationship
from app.database import Base


class Place(Base):
    __tablename__ = "places"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    place_type = Column(String, nullable=True)  # attraction | hotel | restaurant
    lat = Column(Float, nullable=True)
    lng = Column(Float, nullable=True)
    city = Column(String, nullable=True)
    state = Column(String, nullable=True)
    country = Column(String, default="India")
    external_id = Column(String, nullable=True)
    rating = Column(Float, nullable=True)
    price_level = Column(Integer, nullable=True)  # 1-4
    opening_hours = Column(JSON, nullable=True)
    diet_tags = Column(JSON, default=list)
    cached_data = Column(JSON, nullable=True)
    source = Column(String, nullable=True)  # osm | opentripmap | google
    fetched_at = Column(DateTime(timezone=True), nullable=True)
    description = Column(Text, nullable=True)
    image_url = Column(String, nullable=True)
    website = Column(String, nullable=True)
    phone = Column(String, nullable=True)


class Accommodation(Base):
    __tablename__ = "accommodations"

    id = Column(Integer, primary_key=True, index=True)
    trip_id = Column(Integer, ForeignKey("trips.id"), nullable=False)
    city = Column(String, nullable=False)
    place_name = Column(String, nullable=False)
    place_type = Column(String, nullable=True)
    address = Column(Text, nullable=True)
    cost_per_night = Column(Float, nullable=True)
    total_cost = Column(Float, nullable=True)
    nights = Column(Integer, default=1)
    check_in_day = Column(Integer, nullable=True)
    check_out_day = Column(Integer, nullable=True)
    lat = Column(Float, nullable=True)
    lng = Column(Float, nullable=True)
    rating = Column(Float, nullable=True)
    image_url = Column(String, nullable=True)
    notes = Column(Text, nullable=True)

    trip = relationship("Trip", back_populates="accommodations")


class Restaurant(Base):
    __tablename__ = "restaurants"

    id = Column(Integer, primary_key=True, index=True)
    trip_id = Column(Integer, ForeignKey("trips.id"), nullable=False)
    city = Column(String, nullable=False)
    day_number = Column(Integer, nullable=True)
    meal_type = Column(String, nullable=True)  # breakfast | lunch | dinner
    place_name = Column(String, nullable=False)
    cuisine = Column(String, nullable=True)
    diet_tags = Column(JSON, default=list)
    cost_estimate = Column(Float, nullable=True)
    lat = Column(Float, nullable=True)
    lng = Column(Float, nullable=True)
    rating = Column(Float, nullable=True)
    diet_verified = Column(Boolean, default=False)
    notes = Column(Text, nullable=True)

    trip = relationship("Trip", back_populates="restaurants")
