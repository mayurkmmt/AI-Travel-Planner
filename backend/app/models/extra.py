from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text, Boolean, func, Date
from sqlalchemy.orm import relationship
from app.database import Base


class WeatherSnapshot(Base):
    __tablename__ = "weather_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    trip_id = Column(Integer, ForeignKey("trips.id"), nullable=False)
    city = Column(String, nullable=False)
    date = Column(Date, nullable=True)
    month = Column(String, nullable=True)
    temp_min = Column(Float, nullable=True)
    temp_max = Column(Float, nullable=True)
    rain_probability = Column(Float, nullable=True)
    condition = Column(String, nullable=True)
    advice = Column(Text, nullable=True)
    source_type = Column(String, default="seasonal_average")  # forecast | seasonal_average

    trip = relationship("Trip", back_populates="weather_snapshots")


class LocalTip(Base):
    __tablename__ = "local_tips"

    id = Column(Integer, primary_key=True, index=True)
    city = Column(String, nullable=False, index=True)
    category = Column(String, nullable=True)  # safety | culture | food | transport
    text = Column(Text, nullable=False)
    source = Column(String, default="ai_generated")  # curated | wikivoyage | ai_generated
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class EmergencyContact(Base):
    __tablename__ = "emergency_contacts"

    id = Column(Integer, primary_key=True, index=True)
    city = Column(String, nullable=False, index=True)
    contact_type = Column(String, nullable=True)  # police | ambulance | hospital | tourist_help
    name = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    last_verified = Column(Date, nullable=True)


class GenerationLog(Base):
    __tablename__ = "generation_logs"

    id = Column(Integer, primary_key=True, index=True)
    trip_id = Column(Integer, ForeignKey("trips.id"), nullable=False)
    prompt_tokens = Column(Integer, nullable=True)
    completion_tokens = Column(Integer, nullable=True)
    latency_ms = Column(Integer, nullable=True)
    success = Column(Boolean, default=True)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    trip = relationship("Trip", back_populates="generation_logs")
