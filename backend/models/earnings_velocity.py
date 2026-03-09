from sqlalchemy import Column, Integer, String, Float
from db import Base

class EarningsVelocity(Base):
    __tablename__ = "earnings_velocity"

    log_id = Column(Integer, primary_key=True, index=True)

    driver_id = Column(String)
    date = Column(String)
    timestamp = Column(String)

    cumulative_earnings = Column(Float)
    elapsed_hours = Column(Float)

    current_velocity = Column(Float)
    target_velocity = Column(Float)

    velocity_delta = Column(Float)
    trips_completed = Column(Integer)

    forecast_status = Column(String)