from pydantic import BaseModel

class GoalPayload(BaseModel):

    goal_id: str
    driver_id: str
    date: str

    shift_start_time: str
    shift_end_time: str

    target_earnings: float
    target_hours: float

    current_earnings: float
    current_hours: float

    timestamp: str