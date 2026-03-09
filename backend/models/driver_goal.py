from sqlalchemy import Column, String, Float
from db import Base

class DriverGoal(Base):
    __tablename__ = "driver_goals"

    goal_id = Column(String, primary_key=True)
    driver_id = Column(String)
    date = Column(String)

    shift_start_time = Column(String)
    shift_end_time = Column(String)

    target_earnings = Column(Float)
    target_hours = Column(Float)

    current_earnings = Column(Float)
    current_hours = Column(Float)

    timestamp = Column(String)