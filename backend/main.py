from fastapi import FastAPI, Query
from fastapi.responses import StreamingResponse
from routers.earnings_router import router as earnings_router
from heuristics.stream import stream_sensor_events

app = FastAPI()

app.include_router(earnings_router)


@app.get("/api/sensor/stream")
async def sensor_stream(
    trip_id: str | None = Query(None, description="Filter to a specific trip ID"),
    interval: float = Query(0.5, ge=0.05, le=5.0, description="Seconds between SSE pushes"),
):
    """SSE endpoint — streams classified sensor events to the frontend."""
    return StreamingResponse(
        stream_sensor_events(trip_id=trip_id, interval_sec=interval),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )