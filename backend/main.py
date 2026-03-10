from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from routers.earnings_router import router as earnings_router
from heuristics.demo_stream import stream_demo_events

app = FastAPI()

# Allow the Next.js dev server to connect to this backend (SSE)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000", "https://driver-pulse-seven.vercel.app/" , "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(earnings_router)


@app.get("/api/sensor/demo")
async def sensor_demo_stream(
    interval: float = Query(
        0.05, ge=0.01, le=1.0, description="Seconds between synthetic demo events"
    ),
):
    """SSE endpoint — streams **synthetic** per-second demo data for live walkthroughs."""
    return StreamingResponse(
        stream_demo_events(interval_sec=interval),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
