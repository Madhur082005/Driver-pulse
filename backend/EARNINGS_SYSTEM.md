## Earnings Goal System – Driver Pulse Backend

This document explains how the earnings system works in the backend: what data it uses, how we evaluate pace, and how we log/debug it using the demo CSVs.

---

### 1. Core concept

For each driver and shift, we define a **daily earnings goal**:

- **Target earnings**: how much the driver wants to earn this shift (₹).
- **Target hours**: how many hours the driver plans to work.
- As the shift progresses, we track:
  - **Current earnings** (₹ so far)
  - **Current hours** (hours so far)

The system answers one question every time we get an update row:

> “Given how long this driver has worked so far, are they **ahead**, **on track**, or **at risk** of missing their goal?”

We expose this via the `/api/earnings/goal` endpoint and a test harness in `test.py`.

---

### 2. Data model and demo dataset

#### 2.1 `DriverGoal` model

Backend model in `models/driver_goal.py`:

- `goal_id`: unique ID per goal row
- `driver_id`: driver identifier
- `date`: shift date (string, e.g. `2024-02-06`)
- `shift_start_time`: planned shift start time (string)
- `shift_end_time`: planned shift end time (string)
- `target_earnings`: target rupees for the shift (float)
- `target_hours`: planned hours for the shift (float)
- `current_earnings`: rupees earned so far in this shift (float)
- `current_hours`: hours worked so far (float)
- `timestamp`: timestamp of this checkpoint (string)

Each **row** represents a *checkpoint* in the driver’s shift (for every 30 minutes).

#### 2.2 Demo CSVs

Demo data lives under `Driver-pulse/Demo_Data/`:

- `drivers.csv`: 10 demo drivers with:
  - `driver_id`, `name`, `city`
  - `shift_preference`, `avg_hours_per_day`
  - `avg_earnings_per_hour`, `experience_months`, `rating`
- `driver_goal_progress.csv`: time-series of goal checkpoints with:
  - `goal_id, driver_id, date, shift_start_time, shift_end_time`
  - `target_earnings, target_hours`
  - `current_earnings, current_hours`
  - `timestamp`

The backend does **not** depend on the original hackathon `Data/` folder for earnings; the demo CSVs are designed to be small and consistent for 10 drivers.

---

### 3. Earnings evaluation logic

The core logic lives in `services/earnings_engine.py` in `evaluate_goal(goal)`.

#### 3.1 Inputs

`evaluate_goal` expects a goal-like object with at least:

- `goal_id`
- `driver_id`
- `target_earnings`
- `target_hours`
- `current_earnings`
- `current_hours`

This can be a SQLAlchemy `DriverGoal` row, a Pydantic model, or a simple namespace (as in `test.py`).

#### 3.2 Step 1 – Target velocity

We compute the **target earnings velocity** (₹/hour) for the shift:

$$
target\_velocity = \frac{target\_earnings}{target\_hours}
$$

If `target_hours == 0`, we log a warning and fall back to `target_velocity = 0` to avoid division by zero.

#### 3.3 Step 2 – Early shift handling

If `current_hours == 0`, we treat this as “no driving yet”:

- `status = "on_track"`
- `current_velocity = 0`
- `target_velocity` as above
- `velocity_delta = 0`

We log this and return immediately.

#### 3.4 Step 3 – Expected earnings so far

For active shifts (`current_hours > 0`), we compute:

1. **Current velocity** (for logging/analytics):

   $$
   current\_velocity = \frac{current\_earnings}{current\_hours}
   $$

2. **Linear expected earnings** based on target pace and elapsed hours:

   $$
   expected = target\_velocity \times current\_hours
   $$

3. **Early shift softness**: in the first hour we reduce expected slightly to avoid being too harsh when randomness is high (e.g. a couple of short or long trips):

   - If `current_hours < EARLY_HOURS_WINDOW` (1.0 hour by default):

   $$
   expected = expected \times EARLY\_EXPECTED\_SCALE
   $$

   - Default: `EARLY_EXPECTED_SCALE = 0.8` → we only hold them to 80% of the straight-line expectation in the first hour.

4. **Delta in rupees**:

   $$
   velocity\_delta = current\_earnings - expected
   $$

   - Positive delta → earning more than expected so far (ahead).
   - Negative delta → earning less than expected so far (behind).

#### 3.5 Step 4 – Dynamic thresholds (personalized + relative)

We want thresholds that:

- Scale with the size of the goal.
- Are stable as the shift progresses.

We use a **mixed absolute + relative** threshold:

1. **Goal-personalized absolute threshold**:

   $$
   base\_abs\_threshold = \text{clamp}\bigl(target\_earnings \times 0.05,\ 50,\ 250\bigr)
   $$

   - `BASE_ABS_FRACTION_OF_GOAL = 0.05` → 5% of the full-day goal.
   - Clamped between `BASE_ABS_THRESHOLD_MIN = 50` and `BASE_ABS_THRESHOLD_MAX = 250` rupees.
   - This means:
     - Small goals don’t get over-penalized by tiny swings.
     - Big goals get more room for variance.

2. **Relative threshold vs expected earnings so far**:

   $$
   rel\_threshold = |expected| \times REL\_THRESHOLD\_FRACTION
   $$

   - `REL_THRESHOLD_FRACTION = 0.10` → 10% of expected earnings so far.

3. **Dynamic threshold**:

   $$
   dynamic\_threshold = \max(base\_abs\_threshold,\ rel\_threshold)
   $$

This is the minimum ₹-difference we require before calling someone clearly ahead or at risk.

#### 3.6 Step 5 – Status classification

We combine the rupee delta and the threshold into a discrete status:

- **Ahead**:

  $$
  velocity\_delta \ge dynamic\_threshold
  $$

- **At risk**:

  - Only once we’ve seen enough driving time:

    $$
    current\_hours \ge MIN\_HOURS\_FOR\_AT\_RISK
    $$

  - And clearly behind:

    $$
    velocity\_delta \le -dynamic\_threshold
    $$

  - Default: `MIN_HOURS_FOR_AT_RISK = 1.0` hour.

- **On track**:

  - Everything else (including small ups/downs and early-shift noise).

#### 3.7 Step 6 – Forecast / projected shift earnings

To answer “Where will I likely end up by the end of the shift?”, we compute a simple forecast using the current earnings velocity:

1. Only when `current_hours > 0`:

   $$
   current\_velocity = \frac{current\_earnings}{current\_hours}
   $$

2. Remaining hours in the shift (never negative):

   $$
   remaining\_hours = \max(target\_hours - current\_hours,\ 0)
   $$

3. **Projected total shift earnings**:

   $$
   projected\_shift\_earnings = current\_earnings + remaining\_hours \times current\_velocity
   $$

4. **Clamping / safety**:

   - We clamp the projection to be at least `0`.
   - If `target_earnings > 0`, we cap it at:

     $$
     target\_earnings \times MAX\_PROJECTION\_MULTIPLIER
     $$

     with `MAX_PROJECTION_MULTIPLIER = 2.0` by default.

This keeps the forecast lightweight and explainable while avoiding unrealistic projections from a lucky early trip.

We return a result dictionary containing:

- `status`: `"ahead" | "on_track" | "at_risk"`
- `current_velocity`: ₹/hr so far
- `target_velocity`: target ₹/hr
- `velocity_delta`: `current_earnings - expected`
- `expected_earnings`: `expected` (after early-shift scaling)
- `dynamic_threshold`: the threshold used for that evaluation
- `projected_shift_earnings`: simple forecast of full-shift earnings

---

### 4. Alert text and tone

Alert messages are generated in `utils/alert_builder.py` via `build_alert(...)`.

#### 4.1 Function signature

```python
def build_alert(status, delta=None, expected=None):
    ...
```

- `status`: output from `evaluate_goal` (`"ahead"`, `"on_track"`, `"at_risk"`).
- `delta`: `velocity_delta` (₹ ahead/behind expected).
- `expected`: `expected_earnings` used for that evaluation.

#### 4.2 Copy rules

- **Ahead**:

  - `"Great pace! You're ahead of target."`

- **On track**:

  - `"You're on track. Keep going."`

- **At risk**:

  - If we know `delta` and `expected`, we compute how far behind the driver is in relative terms:

    $$
    frac = \frac{|delta|}{expected}
    $$

  - If `frac < 0.10` (less than 10% behind expected):

    - `"You're slightly behind pace. A couple of good trips can catch you up."`

  - Otherwise (more than ~10% behind expected):

    - `"You're significantly behind pace. Consider moving to a high-demand area."`

  - If we don’t have `delta`/`expected`, we fall back to:

    - `"You're behind pace. Move to a high-demand area."`

This keeps the logic simple while making the tone more nuanced for drivers who are only slightly behind vs clearly struggling.

---

### 5. API endpoint and logging

#### 5.1 `/api/earnings/goal` endpoint

Defined in `routers/earnings_router.py`:

1. Accepts a `GoalPayload` (Pydantic) matching the `DriverGoal` fields.
2. Creates and persists a `DriverGoal` row to the database.
3. Calls `evaluate_goal(goal_row)`.
4. Inserts an `EarningsVelocity` log row with:
   - `driver_id`, `date`, `timestamp`
   - `cumulative_earnings` (current earnings)
   - `elapsed_hours` (current hours)
   - `current_velocity`, `target_velocity`, `velocity_delta`
   - `trips_completed` currently set to `0`
   - `forecast_status` = `status` from `evaluate_goal`
5. Builds an alert via:

   ```python
   alert = build_alert(
       result["status"],
       delta=result["velocity_delta"],
       expected=result["expected_earnings"],
   )
   ```

6. Returns a simple JSON payload:

   ```json
   {
     "driver_id": "...",
     "status": "ahead | on_track | at_risk",
     "alert": "string or null",
     "projected_shift_earnings": 1480.0
   }
   ```

   - `alert` is `null` when there is **no status change** for that driver since the previous checkpoint.
   - `projected_shift_earnings` is the forecast as described above.

This keeps the API surface small while storing richer logs for analysis and exposing a clear “end-of-shift” prediction signal.

#### 5.2 Structured logging in the engine

`evaluate_goal` logs each evaluation at `INFO` level, including:

- `goal_id`, `driver_id`
- `expected` earnings so far
- `velocity_delta`
- `dynamic_threshold`
- `current_hours`
- `status`

These logs are visible when you run `test.py` or when the service is running with logging enabled.

---

### 6. Testing with demo data (`test.py`)

The file `backend/test.py` is a simple, DB-free harness for the earnings engine using the demo CSV.

#### 6.1 What it does

- Configures console logging.
- Loads `Demo_Data/driver_goal_progress.csv` using `csv.DictReader`.
- Converts each CSV row into a simple goal object via `SimpleNamespace`:
  - Fields: `goal_id`, `driver_id`, `date`, `shift_start_time`, `shift_end_time`, `target_earnings`, `target_hours`, `current_earnings`, `current_hours`, `timestamp`.
- Calls `evaluate_goal(goal)` for each row.
- Calls `build_alert(...)` with `status`, `delta`, and `expected` from the result.
- Logs a structured line for each goal checkpoint:
  - `status`, `delta`, `current_velocity`, `target_velocity`
  - `expected_earnings`, `dynamic_threshold`
- Prints a human-readable summary line to the terminal:

  ```text
  [GOAL_ID] Driver DRV001 | status=on_track | delta=123.45 | alert='...'
  ```

#### 6.2 How to run

From the `backend` directory:

```bash
python test.py
```

You’ll see both structured logs and concise alerts, which is useful for verifying the behavior of the earnings engine against your demo data.

---

### 7. How this helps drivers (without too much complexity)

- Uses **expected earnings so far**, not just raw hourly velocity → more intuitive.
- Thresholds are **personalized per goal** and also scale with **progress so far**.
- Early in the shift, the system is **more forgiving**, reducing noisy “at risk” messages.
- Alerts are **toned** based on how far behind the driver is (slightly vs significantly).
- Implementation stays simple:
  - One pure function `evaluate_goal` with basic math.
  - One alert builder `build_alert` with small branching logic.
  - A single API endpoint + logging model to record everything.

This makes the system practical for a hackathon/demo, but close in spirit to how a real earnings coach for ride-hailing drivers would work.

