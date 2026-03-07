"""
Edge Sensor Processor — Uber Driver Pulse Hackathon
=====================================================
Modular preprocessing pipeline that ingests raw accelerometer and audio
signals, aligns timestamps, and extracts physics-based features with
rolling-window statistics.  Outputs a clean feature dataset for
downstream rule engines and ML models.

All heavy operations use vectorized Pandas / NumPy — no Python-level loops.
"""

import os
from pathlib import Path

import numpy as np
import pandas as pd


class EdgeSensorProcessor:
    """Preprocesses accelerometer + audio streams from a driver's phone
    and produces a clean feature dataset for downstream analytics."""

    # ── Default configurable parameters ──────────────────────────────────
    DEFAULT_WINDOW_SIZE_SEC: int = 10
    DEFAULT_RESAMPLE_FREQ: str = "1s"
    # Physical ceiling for accelerometer readings (m/s²); anything beyond
    # this is treated as sensor noise / spike and gets clipped.
    ACCEL_MAGNITUDE_MAX: float = 30.0

    def __init__(
        self,
        data_dir: str,
        window_size_sec: int | None = None,
        resample_freq: str | None = None,
    ):
        self.data_dir = Path(data_dir)
        self.window_size_sec = window_size_sec or self.DEFAULT_WINDOW_SIZE_SEC
        self.resample_freq = resample_freq or self.DEFAULT_RESAMPLE_FREQ

        # Internal state — populated during processing
        self._accel: pd.DataFrame | None = None
        self._audio: pd.DataFrame | None = None
        self._merged: pd.DataFrame | None = None

    # ====================================================================
    # 1. DATA INGESTION
    # ====================================================================
    def ingest(self) -> "EdgeSensorProcessor":
        """Load CSVs, parse timestamps, sort, and fill gaps."""

        # ── Accelerometer ────────────────────────────────────────────────
        accel_path = self.data_dir / "accelerometer_data.csv"
        accel = pd.read_csv(accel_path)

        # Normalise column names coming from the raw file
        accel = accel.rename(columns={
            "accel_x": "x",
            "accel_y": "y",
            "accel_z": "z",
        })

        accel["timestamp"] = pd.to_datetime(accel["timestamp"])
        accel = accel.sort_values(["trip_id", "timestamp"]).reset_index(drop=True)

        # Forward-fill missing values within each trip to avoid cross-trip leakage
        accel[["x", "y", "z"]] = accel.groupby("trip_id")[["x", "y", "z"]].ffill()
        # If leading NaNs remain after ffill, back-fill within trip
        accel[["x", "y", "z"]] = accel.groupby("trip_id")[["x", "y", "z"]].bfill()

        self._accel = accel

        # ── Audio ────────────────────────────────────────────────────────
        audio_path = self.data_dir / "audio_intensity_data.csv"
        audio = pd.read_csv(audio_path)

        audio = audio.rename(columns={"audio_level_db": "db_level"})

        audio["timestamp"] = pd.to_datetime(audio["timestamp"])
        audio = audio.sort_values(["trip_id", "timestamp"]).reset_index(drop=True)

        audio["db_level"] = audio.groupby("trip_id")["db_level"].ffill()
        audio["db_level"] = audio.groupby("trip_id")["db_level"].bfill()

        self._audio = audio
        return self

    # ====================================================================
    # 2. TIMESTAMP ALIGNMENT
    #    Resample both streams to a uniform frequency, then merge.
    #    Uniform spacing ensures stable rolling windows and consistent
    #    jerk calculations regardless of original sensor sample rates.
    # ====================================================================
    def align(self) -> "EdgeSensorProcessor":
        """Resample sensors to a uniform grid and merge on timestamp."""

        freq = self.resample_freq

        # ── Resample accelerometer per trip ──────────────────────────────
        accel_groups = []
        for trip_id, grp in self._accel.groupby("trip_id"):
            grp = grp.set_index("timestamp").sort_index()
            # Mean-downsample (or upsample-interpolate) to uniform freq
            resampled = grp[["x", "y", "z"]].resample(freq).mean().interpolate(method="time")
            resampled["trip_id"] = trip_id
            accel_groups.append(resampled)
        accel = pd.concat(accel_groups).reset_index()

        # ── Resample audio per trip ──────────────────────────────────────
        audio_groups = []
        for trip_id, grp in self._audio.groupby("trip_id"):
            grp = grp.set_index("timestamp").sort_index()
            resampled = grp[["db_level"]].resample(freq).mean().interpolate(method="time")
            resampled["trip_id"] = trip_id
            audio_groups.append(resampled)
        audio = pd.concat(audio_groups).reset_index()

        # ── Merge on exact timestamp + trip_id after uniform resampling ──
        accel = accel.sort_values("timestamp")
        audio = audio.sort_values("timestamp")

        merged = pd.merge_asof(
            accel,
            audio,
            on="timestamp",
            by="trip_id",
            direction="nearest",
        )

        # Fill any residual NaNs (trips with no audio data)
        global_median_db = audio["db_level"].median()
        merged["db_level"] = merged["db_level"].fillna(global_median_db)

        merged = merged.sort_values(["trip_id", "timestamp"]).reset_index(drop=True)
        self._merged = merged
        return self

    # ====================================================================
    # 3. PHYSICS-BASED FEATURE ENGINEERING
    # ====================================================================
    def compute_features(self) -> "EdgeSensorProcessor":
        """Derive acceleration magnitude, jerk, normalized jerk, and
        audio rate-of-change from the merged sensor stream."""

        df = self._merged

        # ── Acceleration magnitude (m/s²) ────────────────────────────────
        df["accel_magnitude"] = np.sqrt(df["x"] ** 2 + df["y"] ** 2 + df["z"] ** 2)

        # Clip to a physically plausible range to suppress sensor spikes.
        # Typical phone accelerometers saturate around 20 g ≈ 196 m/s²;
        # 30 m/s² is a conservative ceiling for road driving.
        df["accel_magnitude"] = df["accel_magnitude"].clip(upper=self.ACCEL_MAGNITUDE_MAX)

        # ── Time delta (seconds) between consecutive readings per trip ───
        df["dt"] = df.groupby("trip_id")["timestamp"].diff().dt.total_seconds()

        # ── Jerk = rate of change of acceleration magnitude (m/s³) ───────
        # Captures sudden braking, swerving, or collision forces.
        df["delta_mag"] = df.groupby("trip_id")["accel_magnitude"].diff()
        df["jerk"] = np.where(
            (df["dt"].isna()) | (df["dt"] == 0),
            0.0,
            df["delta_mag"].abs() / df["dt"],
        )

        # ── Audio delta = rate of change of dB level (dB/s) ──────────────
        # Large positive spikes indicate sudden loud events (shouting, horns).
        df["audio_delta_raw"] = df.groupby("trip_id")["db_level"].diff()
        df["audio_delta"] = np.where(
            (df["dt"].isna()) | (df["dt"] == 0),
            0.0,
            df["audio_delta_raw"].abs() / df["dt"],
        )

        self._merged = df
        return self

    # ====================================================================
    # 4. ROLLING WINDOW FEATURE EXTRACTION
    # ====================================================================
    def rolling_features(self) -> "EdgeSensorProcessor":
        """Compute time-based rolling statistics for accel and audio.

        Features produced:
          rolling_mean_acc   – baseline acceleration level
          rolling_std_acc    – motion noise / vibration intensity
          rolling_var_acc    – erratic driving indicator (variance of magnitude)
          rolling_max_jerk   – worst-case jerk in window (harsh manoeuvre proxy)
          rolling_mean_audio – ambient noise baseline
          rolling_std_audio  – audio volatility
          rolling_max_audio  – loudest peak in window (spike detector)
          rolling_audio_energy – mean squared dB (energy proxy)
        """

        df = self._merged.copy()
        win = f"{self.window_size_sec}s"

        # Time-based rolling requires a DatetimeIndex per trip
        results = []
        for _, grp in df.groupby("trip_id"):
            grp = grp.set_index("timestamp").sort_index()

            # ── Acceleration rolling stats ────────────────────────────────
            acc_roll = grp["accel_magnitude"].rolling(win, min_periods=1)
            grp["rolling_mean_acc"] = acc_roll.mean()
            grp["rolling_std_acc"] = acc_roll.std().fillna(0.0)
            grp["rolling_var_acc"] = acc_roll.var().fillna(0.0)

            # ── Jerk rolling stats ────────────────────────────────────────
            grp["rolling_max_jerk"] = (
                grp["jerk"].rolling(win, min_periods=1).max()
            )

            # ── Audio rolling stats ───────────────────────────────────────
            audio_roll = grp["db_level"].rolling(win, min_periods=1)
            grp["rolling_mean_audio"] = audio_roll.mean()
            grp["rolling_std_audio"] = audio_roll.std().fillna(0.0)
            grp["rolling_max_audio"] = audio_roll.max()

            # Mean-squared audio level — proportional to acoustic energy
            grp["rolling_audio_energy"] = (
                (grp["db_level"] ** 2).rolling(win, min_periods=1).mean()
            )

            grp = grp.reset_index()
            results.append(grp)

        df = pd.concat(results, ignore_index=True)

        # ── Normalized jerk ──────────────────────────────────────────────
        # Dividing jerk by rolling_std_acc reduces sensitivity to sensor
        # orientation drift and baseline vibration, highlighting only truly
        # anomalous motion changes.
        df["normalized_jerk"] = np.where(
            df["rolling_std_acc"] > 0,
            df["jerk"] / df["rolling_std_acc"],
            0.0,
        )

        self._merged = df
        return self

    # ====================================================================
    # 5. EXPORT
    # ====================================================================
    def export(self, output_dir: str | None = None) -> Path:
        """Write processed_sensor_features.csv — idempotent (overwrites safely)."""

        out = Path(output_dir) if output_dir else self.data_dir.parent
        out.mkdir(parents=True, exist_ok=True)

        output_columns = [
            "timestamp",
            "trip_id",
            "accel_magnitude",
            "jerk",
            "normalized_jerk",
            "rolling_mean_acc",
            "rolling_std_acc",
            "rolling_var_acc",
            "rolling_max_jerk",
            "rolling_mean_audio",
            "rolling_std_audio",
            "rolling_max_audio",
            "rolling_audio_energy",
            "audio_delta",
        ]

        path = out / "processed_sensor_features.csv"
        self._merged[output_columns].to_csv(path, index=False)
        return path

    # ====================================================================
    # CONVENIENCE — run the full pipeline
    # ====================================================================
    def run(self, output_dir: str | None = None) -> Path:
        """Execute the full pipeline end-to-end and return the output path."""
        self.ingest()
        self.align()
        self.compute_features()
        self.rolling_features()
        return self.export(output_dir)

    # ── Accessor for downstream integration ──────────────────────────────
    @property
    def features(self) -> pd.DataFrame:
        """Return the fully-featured merged dataframe."""
        if self._merged is None:
            raise RuntimeError("Pipeline has not been executed yet. Call .run() first.")
        return self._merged


# ════════════════════════════════════════════════════════════════════════
# CLI entry-point
# ════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    DATA_DIR = os.path.join(os.path.dirname(__file__), "Data", "sensor_data")

    processor = EdgeSensorProcessor(
        data_dir=DATA_DIR,
        window_size_sec=10,
    )
    out_path = processor.run()

    print(f"Pipeline complete. Output → {out_path}")
    print(f"Total feature rows: {len(processor.features)}")
    print("\n── Sample (first 10 rows) ──")
    sample_cols = [
        "timestamp", "trip_id", "accel_magnitude", "jerk",
        "normalized_jerk", "rolling_mean_acc", "rolling_std_acc",
        "rolling_var_acc", "rolling_max_jerk", "rolling_mean_audio",
        "rolling_std_audio", "rolling_max_audio",
        "rolling_audio_energy", "audio_delta",
    ]
    print(processor.features[sample_cols].head(10).to_string(index=False))
