"use client";

import { useEffect, useRef, useState, useCallback } from "react";

// ─── Inline SVG icons ─────────────────────────────────────────────────────────
const Ico = ({ d, size = 20, ...p }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none"
    stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" {...p}>
    {[].concat(d).map((path, i) => <path key={i} d={path} />)}
  </svg>
);
const IPlay = p => <Ico d="M5 3l14 9-14 9V3z" {...p} />;
const IBolt = p => <Ico d="M13 2L3 14h9l-1 8 10-12h-9l1-8z" {...p} />;
const IAlert = p => <Ico d={["M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z", "M12 9v4", "M12 17h.01"]} {...p} />;
const IMap = p => <Ico d="M1 6v16l7-4 8 4 7-4V2l-7 4-8-4-7 4z" {...p} />;
const IChart = p => <Ico d={["M18 20V10", "M12 20V4", "M6 20v-6"]} {...p} />;
const IDash = p => <Ico d={["M3 3h7v7H3z", "M14 3h7v7h-7z", "M14 14h7v7h-7z", "M3 14h7v7H3z"]} {...p} />;
const IFilter = p => <Ico d="M22 3H2l8 9.46V19l4 2v-8.54L22 3z" {...p} />;
const ISpin = p => <Ico d="M23 4v6h-6M1 20v-6h6M3.51 9a9 9 0 0114.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0020.49 15" {...p} />;

// ─── Severity palette — keys match fusion.severity values from backend ────────
const SEV = {
  high: { text: "#FF3B30", bg: "rgba(255,59,48,0.13)", border: "rgba(255,59,48,0.32)" },
  medium: { text: "#FF9500", bg: "rgba(255,149,0,0.13)", border: "rgba(255,149,0,0.32)" },
  low: { text: "#FFD60A", bg: "rgba(255,214,10,0.13)", border: "rgba(255,214,10,0.32)" },
  safe: { text: "#30D158", bg: "rgba(48,209,88,0.10)", border: "rgba(48,209,88,0.25)" },
};
const SEV_RANK = { safe: 0, low: 1, medium: 2, high: 3 };

// Status display map — keys match earnings.status strings from earnings_engine.py
// The label is purely a UI string; the status key itself always comes from backend
const STATUS_DISPLAY = {
  ahead: { color: "#30D158", label: "Ahead of Goal" },
  on_track: { color: "#FFD60A", label: "On Track" },
  at_risk: { color: "#FF3B30", label: "At Risk" },
};
const statusDisplay = s => STATUS_DISPLAY[s] ?? { color: "#888", label: s ?? "—" };

// Currency symbol helper — driven by payload.currency
const currSymbol = c => c === "INR" ? "₹" : (c ?? "");

// ─── Formatting helpers ───────────────────────────────────────────────────────
const fmt = (n, d = 0) => n == null ? "—" : Number(n).toFixed(d);
const fmtC = (n, cur, d = 0) => n == null ? "—" : `${currSymbol(cur)}${fmt(n, d)}`;
const fmtTs = iso => { try { return new Date(iso).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" }); } catch { return iso; } };

// ─── Shared UI atoms ──────────────────────────────────────────────────────────
const Card = ({ children, style, ...p }) => (
  <div style={{
    background: "#0f0f0f", border: "1px solid #1e1e1e",
    borderRadius: 18, padding: "18px 20px", ...style
  }} {...p}>
    {children}
  </div>
);

const Lbl = ({ children }) => (
  <p style={{
    fontSize: 10, fontWeight: 700, letterSpacing: "0.18em",
    textTransform: "uppercase", color: "#555", marginBottom: 6, fontFamily: "monospace"
  }}>
    {children}
  </p>
);

const BigNum = ({ children, color = "#e8e8e8" }) => (
  <div style={{
    fontSize: 38, fontWeight: 900, color, lineHeight: 1.05,
    fontFamily: "Georgia,'Times New Roman',serif", letterSpacing: "-0.02em"
  }}>
    {children}
  </div>
);

const SevBadge = ({ sev, large }) => {
  const c = SEV[sev] ?? SEV.safe;
  return (
    <span style={{
      background: c.bg, color: c.text, border: `1px solid ${c.border}`,
      borderRadius: 99, padding: large ? "4px 14px" : "2px 9px",
      fontSize: large ? 13 : 10, fontWeight: 700,
      letterSpacing: "0.09em", textTransform: "uppercase", fontFamily: "monospace"
    }}>
      {sev ?? "safe"}
    </span>
  );
};

const MiniStat = ({ label, value, color = "#d0d0d0" }) => (
  <div style={{ background: "#141414", borderRadius: 10, padding: "10px 12px" }}>
    <div style={{
      fontSize: 10, color: "#555", textTransform: "uppercase",
      letterSpacing: "0.13em", fontFamily: "monospace"
    }}>{label}</div>
    <div style={{ fontSize: 16, fontWeight: 700, color, marginTop: 4 }}>{value}</div>
  </div>
);

const Sel = ({ value, onChange, options, placeholder }) => (
  <select value={value} onChange={e => onChange(e.target.value)}
    style={{
      background: "#141414", border: "1px solid #2a2a2a", borderRadius: 10,
      color: value ? "#fff" : "#666", fontSize: 13, padding: "8px 12px",
      fontFamily: "monospace", outline: "none", cursor: "pointer", minWidth: 130
    }}>
    <option value="">{placeholder}</option>
    {options.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
  </select>
);

// ─── Earnings SVG chart ───────────────────────────────────────────────────────
// All data (target, projected, currency) comes from backend via props
function EarningsChart({ data, projected, target, currency }) {
  if (!data.length) return null;
  const W = 580, H = 190, PAD = { top: 24, right: 72, bottom: 36, left: 58 };
  const iW = W - PAD.left - PAD.right;
  const iH = H - PAD.top - PAD.bottom;

  const vals = [...data.map(d => d.earnings), projected ?? 0, target ?? 0].filter(v => v > 0);
  const maxV = Math.max(...vals) * 1.12;
  const range = maxV || 1;
  const sym = currSymbol(currency);

  const sx = i => PAD.left + (i / Math.max(data.length - 1, 1)) * iW;
  const sy = v => PAD.top + iH - (v / range) * iH;
  const pts = data.map((d, i) => `${sx(i)},${sy(d.earnings)}`).join(" ");
  const lastX = sx(data.length - 1);
  const lastY = sy(data[data.length - 1].earnings);
  const xStep = Math.max(1, Math.floor(data.length / 5));
  const TICKS = 4;
  const yTicks = Array.from({ length: TICKS + 1 }, (_, i) => (range * i) / TICKS);

  return (
    <svg viewBox={`0 0 ${W} ${H}`} style={{ width: "100%", height: "auto", display: "block" }}>
      <defs>
        <linearGradient id="fillG" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#0A84FF" stopOpacity={0.35} />
          <stop offset="100%" stopColor="#0A84FF" stopOpacity={0} />
        </linearGradient>
      </defs>

      {yTicks.map((v, i) => (
        <g key={i}>
          <line x1={PAD.left} y1={sy(v)} x2={W - PAD.right} y2={sy(v)}
            stroke="rgba(255,255,255,0.05)" strokeWidth={1} />
          <text x={PAD.left - 6} y={sy(v) + 4} fill="#555" fontSize={9}
            textAnchor="end" fontFamily="monospace">{sym}{Math.round(v)}</text>
        </g>
      ))}

      {/* Target line — only drawn if target came from backend */}
      {target != null && (
        <>
          <line x1={PAD.left} y1={sy(target)} x2={W - PAD.right} y2={sy(target)}
            stroke="rgba(48,209,88,0.45)" strokeWidth={1.5} strokeDasharray="5 4" />
          <text x={W - PAD.right + 5} y={sy(target) + 4} fill="#30D158"
            fontSize={9} fontFamily="monospace">Target</text>
        </>
      )}

      {data.length > 1 && (
        <polygon
          points={`${PAD.left},${PAD.top + iH} ${pts} ${lastX},${PAD.top + iH}`}
          fill="url(#fillG)" />
      )}

      {data.length > 1 && (
        <polyline points={pts} fill="none" stroke="#0A84FF"
          strokeWidth={2.5} strokeLinejoin="round" strokeLinecap="round" />
      )}

      {/* Projected line — only drawn if projected came from backend */}
      {projected != null && data.length > 0 && (
        <>
          <line x1={lastX} y1={lastY} x2={W - PAD.right} y2={sy(projected)}
            stroke="#FF9500" strokeWidth={2} strokeDasharray="7 4" />
          <text x={W - PAD.right + 5} y={sy(projected) + 4} fill="#FF9500"
            fontSize={9} fontFamily="monospace">Proj.</text>
        </>
      )}

      {data.map((d, i) => (
        <g key={i}>
          <circle cx={sx(i)} cy={sy(d.earnings)} r={3.5}
            fill="#0A84FF" stroke="#0a0a0a" strokeWidth={1.5} />
          {i % xStep === 0 && (
            <text x={sx(i)} y={sy(d.earnings) - 9} fill="#999"
              fontSize={9} textAnchor="middle" fontFamily="monospace">
              {sym}{Math.round(d.earnings)}
            </text>
          )}
        </g>
      ))}

      {data.map((d, i) =>
        i % xStep === 0 ? (
          <text key={i} x={sx(i)} y={H - 4} fill="#444"
            fontSize={9} textAnchor="middle" fontFamily="monospace">
            {d.timestamp}
          </text>
        ) : null
      )}
    </svg>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// ROOT APP
// ═══════════════════════════════════════════════════════════════════════════════
export default function DriverPulseApp() {
  const [tab, setTab] = useState("dashboard");
  const [running, setRunning] = useState(false);

  /**
   * driverCtx — populated from the FIRST demo_update packet.
   * Every field is read from the payload; nothing is assumed or defaulted.
   */
  const [driverCtx, setDriverCtx] = useState(null);
  const [latest, setLatest] = useState(null);   // last demo_update payload
  const [flagged, setFlagged] = useState([]);     // newest-first flagged events
  const [trips, setTrips] = useState({});     // keyed by trip_id
  const [earningsLog, setEarningsLog] = useState([]);     // one entry per trip_done

  // filter state
  const [fSev, setFSev] = useState("");
  const [fTrip, setFTrip] = useState("");
  const [fMotion, setFMotion] = useState("");
  const [fAudio, setFAudio] = useState("");

  const esRef = useRef(null);
  useEffect(() => () => esRef.current?.close(), []);

  // ── demo_update handler ───────────────────────────────────────────────────
  const handleUpdate = useCallback((data) => {
    // Capture driver context once from the first packet
    if (!driverCtx && data.driver_id) {
      setDriverCtx({
        driverId: data.driver_id,
        name: data.driver_name ?? data.driver_id,
        city: data.city ?? "",
        target: data.shift_target_earnings,
        targetHours: data.shift_target_hours,
        currency: data.currency,
      });
    }

    setLatest(data);

    const sev = data.fusion?.severity ?? "safe";
    const motionType = data.motion?.event_type ?? "normal";
    const audioClass = data.audio?.classification ?? "background";
    const isFlagged = sev !== "safe";
    const isMotionEv = !["normal", "road_noise"].includes(motionType);
    const isAudioEv = audioClass !== "background";

    // Update trip map — always, even for safe events
    setTrips(prev => {
      const ex = prev[data.trip_id] ?? {
        tripId: data.trip_id, flags: 0, worstSev: "safe",
        motionCount: 0, audioCount: 0, motionEvents: [], audioEvents: [],
        maxConflict: 0, fare: null, distKm: null, durationMin: null,
      };
      return {
        ...prev, [data.trip_id]: {
          ...ex,
          flags: isFlagged ? ex.flags + 1 : ex.flags,
          worstSev: SEV_RANK[sev] > SEV_RANK[ex.worstSev] ? sev : ex.worstSev,
          motionCount: isMotionEv ? ex.motionCount + 1 : ex.motionCount,
          audioCount: isAudioEv ? ex.audioCount + 1 : ex.audioCount,
          motionEvents: isMotionEv ? [...ex.motionEvents, motionType].slice(-30) : ex.motionEvents,
          audioEvents: isAudioEv ? [...ex.audioEvents, audioClass].slice(-30) : ex.audioEvents,
          maxConflict: Math.max(ex.maxConflict, data.fusion?.conflict ?? 0),
          latestSpeed: data.sensor?.speed_kmh,
        }
      };
    });

    if (!isFlagged) return;

    // Build flagged event record — every field sourced from payload keys
    setFlagged(prev => [{
      id: `${data.trip_id}-${data.index}`,
      index: data.index,
      timestamp: data.timestamp,
      tripId: data.trip_id,
      elapsedHrs: data.elapsed_shift_hours,
      currency: data.currency,
      // fusion
      severity: data.fusion.severity,
      flagType: data.fusion.flag_type,
      conflict: data.fusion.conflict,
      amplified: data.fusion.amplified,
      // motion
      motionType: data.motion?.event_type,
      motionScore: data.motion?.score,
      motionAxis: data.motion?.axis,
      // audio
      audioClass: data.audio?.classification,
      audioScore: data.audio?.score,
      audioDb: data.audio?.db_level,
      sustainedSec: data.audio?.sustained_sec,
      // sensor
      speedKmh: data.sensor?.speed_kmh,
      accelX: data.sensor?.accel_x,
      accelY: data.sensor?.accel_y,
      accelZ: data.sensor?.accel_z,
      // earnings snapshot at moment of flag — from evaluate_goal output
      earningsAtFlag: data.earnings?.current_earnings,
      earningsStatus: data.earnings?.status,
      velDelta: data.earnings?.velocity_delta,
      dynThreshold: data.earnings?.dynamic_threshold,
    }, ...prev].slice(0, 300));
  }, [driverCtx]);

  // ── trip_done handler ─────────────────────────────────────────────────────
  const handleTripDone = useCallback((data) => {
    // trip_done payload from stream_demo_events():
    //   trip_id, driver_id, timestamp, current_earnings, currency
    setEarningsLog(prev => [...prev, {
      tripId: data.trip_id,
      timestamp: fmtTs(data.timestamp),
      earnings: data.current_earnings,
      currency: data.currency,
    }]);
    setTrips(prev => ({
      ...prev,
      [data.trip_id]: {
        ...(prev[data.trip_id] ?? { tripId: data.trip_id }),
        completedAt: fmtTs(data.timestamp),
        earningsAtClose: data.current_earnings,
        currency: data.currency,
        // fare/distKm/durationMin only present if backend adds them to trip_done
        ...(data.fare != null ? { fare: data.fare } : {}),
        ...(data.distance_km != null ? { distKm: data.distance_km } : {}),
        ...(data.duration_min != null ? { durationMin: data.duration_min } : {}),
      },
    }));
  }, []);

  const handleDone = useCallback(() => setRunning(false), []);

  // ── start (real backend SSE) ──────────────────────────────────────────────
  const startDemo = useCallback(() => {
    if (running) return;
    setRunning(true);
    setDriverCtx(null);
    setLatest(null);
    setFlagged([]);
    setTrips({});
    setEarningsLog([]);

    const base = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";
    const es = new EventSource(`${base}/api/sensor/demo`);
    esRef.current = es;

    es.addEventListener("demo_update", (ev: MessageEvent) =>
      handleUpdate(JSON.parse(ev.data)),
    );
    es.addEventListener("trip_done", (ev: MessageEvent) =>
      handleTripDone(JSON.parse(ev.data)),
    );
    es.addEventListener("done", (ev: MessageEvent) => {
      handleDone(JSON.parse(ev.data));
      es.close();
    });
    es.onerror = () => {
      setRunning(false);
      es.close();
    };
  }, [running, handleUpdate, handleTripDone, handleDone]);

  // ── derived values — nothing assumed, all from payload ────────────────────
  const cur = driverCtx?.currency ?? latest?.currency;
  const target = driverCtx?.target;                                      // from shift_target_earnings
  const projected = latest?.earnings?.projected_shift_earnings;            // from earnings_engine
  const currentE = latest?.earnings?.current_earnings ?? 0;
  const status = latest?.earnings?.status;                              // from earnings_engine
  const sd = statusDisplay(status);
  const pct = target ? Math.min(100, Math.round((currentE / target) * 100)) : 0;

  // filter options built from live data
  const tripIds = Object.keys(trips).sort();
  const motionOpts = [...new Set(flagged.map(e => e.motionType).filter(Boolean))];
  const audioOpts = [...new Set(flagged.map(e => e.audioClass).filter(Boolean))];
  const sevOpts = [...new Set(flagged.map(e => e.severity).filter(Boolean))];

  const filteredFlagged = flagged.filter(e =>
    (!fSev || e.severity === fSev) &&
    (!fTrip || e.tripId === fTrip) &&
    (!fMotion || e.motionType === fMotion) &&
    (!fAudio || e.audioClass === fAudio)
  );

  const TAB = (id, Icon, label) => (
    <button key={id} onClick={() => setTab(id)} style={{
      display: "flex", alignItems: "center", gap: 7,
      padding: "9px 16px", borderRadius: 12, border: "none", cursor: "pointer",
      background: tab === id ? "rgba(10,132,255,0.15)" : "transparent",
      color: tab === id ? "#0A84FF" : "#666",
      fontSize: 14, fontWeight: tab === id ? 700 : 500,
      whiteSpace: "nowrap", transition: "all 0.15s",
    }}>
      <Icon size={15} />{label}
    </button>
  );

  return (
    <div style={{
      minHeight: "100vh", background: "#060606", color: "#e8e8e8",
      fontFamily: "'Helvetica Neue',Arial,sans-serif"
    }}>

      <header style={{
        position: "sticky", top: 0, zIndex: 50,
        background: "rgba(6,6,6,0.93)", backdropFilter: "blur(20px)",
        borderBottom: "1px solid #1a1a1a", padding: "13px 20px",
        display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <div style={{
            width: 40, height: 40, borderRadius: 12,
            background: "linear-gradient(135deg,#0A84FF,#0044bb)",
            display: "flex", alignItems: "center", justifyContent: "center"
          }}>
            <IBolt size={20} color="#fff" />
          </div>
          <div>
            <div style={{
              fontSize: 17, fontWeight: 800, color: "#fff",
              fontFamily: "Georgia,serif"
            }}>Driver Pulse</div>
            <div style={{
              fontSize: 10, color: "#444", letterSpacing: "0.16em",
              textTransform: "uppercase", fontFamily: "monospace"
            }}>
              {driverCtx
                ? `${driverCtx.name}${driverCtx.city ? " · " + driverCtx.city : ""}`
                : "Live Shift Intelligence"}
            </div>
          </div>
        </div>
        <button onClick={startDemo} disabled={running} style={{
          display: "flex", alignItems: "center", gap: 8,
          padding: "11px 22px", borderRadius: 14, border: "none",
          cursor: running ? "not-allowed" : "pointer",
          background: running ? "#1a1a1a" : "linear-gradient(135deg,#0A84FF,#0044cc)",
          color: running ? "#555" : "#fff",
          fontSize: 15, fontWeight: 700, transition: "all 0.2s",
        }}>
          {running ? <ISpin size={16} /> : <IPlay size={16} />}
          {running ? "Running…" : "Start Demo"}
        </button>
      </header>

      <nav style={{
        borderBottom: "1px solid #141414", background: "#080808",
        padding: "8px 20px", display: "flex", gap: 4, overflowX: "auto"
      }}>
        {TAB("dashboard", IDash, "Dashboard")}
        {TAB("events", IAlert, `Flagged Events${flagged.length ? ` (${flagged.length})` : ""}`)}
        {TAB("trips", IMap, "Trip Summaries")}
        {TAB("earnings", IChart, "Earnings")}
      </nav>

      <main style={{ maxWidth: 920, margin: "0 auto", padding: "20px 16px 56px" }}>
        {tab === "dashboard" && (
          <Dashboard sd={sd} pct={pct} currentE={currentE} projected={projected}
            target={target} cur={cur} driverCtx={driverCtx}
            latest={latest} flagged={flagged} trips={trips} running={running} />
        )}
        {tab === "events" && (
          <FlaggedEvents filtered={filteredFlagged} total={flagged.length}
            tripIds={tripIds} motionOpts={motionOpts} audioOpts={audioOpts} sevOpts={sevOpts}
            fSev={fSev} setFSev={setFSev} fTrip={fTrip} setFTrip={setFTrip}
            fMotion={fMotion} setFMotion={setFMotion} fAudio={fAudio} setFAudio={setFAudio} />
        )}
        {tab === "trips" && (
          <TripSummaries
            trips={Object.values(trips).sort((a, b) => a.tripId.localeCompare(b.tripId))}
            cur={cur} />
        )}
        {tab === "earnings" && (
          <Earnings log={earningsLog} latest={latest}
            target={target} projected={projected} cur={cur} />
        )}
      </main>

      <style>{`
        @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.25} }
      `}</style>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// DASHBOARD
// ═══════════════════════════════════════════════════════════════════════════════
function Dashboard({ sd, pct, currentE, projected, target, cur,
  driverCtx, latest, flagged, trips, running }) {

  const totalFlags = flagged.length;
  const highFlags = flagged.filter(e => e.severity === "high").length;
  const tripCount = Object.keys(trips).length;
  const e = latest?.earnings;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>

      {/* Status hero — color driven by backend status string */}
      <Card style={{
        background: `linear-gradient(135deg,${sd.color}15,#0f0f0f)`,
        borderColor: `${sd.color}30`
      }}>
        <Lbl>Shift Status</Lbl>
        <div style={{
          display: "flex", alignItems: "center",
          justifyContent: "space-between", flexWrap: "wrap", gap: 10
        }}>
          <div style={{
            fontSize: 44, fontWeight: 900, color: sd.color,
            fontFamily: "Georgia,serif", lineHeight: 1
          }}>
            {sd.label}
          </div>
          {running && (
            <div style={{ display: "flex", alignItems: "center", gap: 7, color: "#0A84FF" }}>
              <div style={{
                width: 9, height: 9, borderRadius: "50%",
                background: "#0A84FF", animation: "pulse 1.4s infinite"
              }} />
              <span style={{ fontSize: 12, fontWeight: 700, fontFamily: "monospace" }}>LIVE</span>
            </div>
          )}
        </div>
        {driverCtx && (
          <div style={{ marginTop: 8, fontSize: 14, color: "#666" }}>
            Target {fmtC(driverCtx.target, driverCtx.currency)} in {driverCtx.targetHours}h
          </div>
        )}
      </Card>

      {/* 4 stat tiles — values from backend */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
        <Card>
          <Lbl>Earnings Now</Lbl>
          <BigNum color="#0A84FF">{fmtC(currentE, cur)}</BigNum>
          <div style={{ fontSize: 13, color: "#666", marginTop: 4 }}>
            {target != null ? `${pct}% of target` : "—"}
          </div>
        </Card>
        <Card>
          <Lbl>Projected End</Lbl>
          <BigNum color="#FF9500">{fmtC(projected, cur)}</BigNum>
          <div style={{ fontSize: 13, color: "#666", marginTop: 4 }}>at current pace</div>
        </Card>
        <Card>
          <Lbl>Trips Completed</Lbl>
          <BigNum>{tripCount}</BigNum>
          <div style={{ fontSize: 13, color: "#666", marginTop: 4 }}>
            {totalFlags ? `${totalFlags} flag${totalFlags !== 1 ? "s" : ""} total` : "No flags yet"}
          </div>
        </Card>
        <Card>
          <Lbl>High Severity</Lbl>
          <BigNum color={highFlags ? "#FF3B30" : "#30D158"}>{highFlags}</BigNum>
          <div style={{ fontSize: 13, color: "#666", marginTop: 4 }}>
            {highFlags ? "Need attention" : "All clear"}
          </div>
        </Card>
      </div>

      {/* Progress bar */}
      {target != null && (
        <Card>
          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 10 }}>
            <Lbl>Earnings Progress</Lbl>
            <span style={{ fontSize: 12, color: "#555", fontFamily: "monospace" }}>
              {fmtC(currentE, cur)} / {fmtC(target, cur)}
            </span>
          </div>
          <div style={{ height: 10, background: "#1a1a1a", borderRadius: 99, overflow: "hidden" }}>
            <div style={{
              height: "100%", width: `${pct}%`, borderRadius: 99,
              transition: "width 0.5s ease",
              background: pct >= 100 ? "#30D158" : pct >= 60 ? "#0A84FF" : "#FF9500"
            }} />
          </div>

          {/* Velocity metrics from evaluate_goal output */}
          {e && (
            <div style={{
              marginTop: 14, display: "grid",
              gridTemplateColumns: "repeat(2,1fr)", gap: 10
            }}>
              <MiniStat label="Velocity Now"
                value={`${fmtC(e.current_velocity, cur, 1)}/hr`} color="#0A84FF" />
              <MiniStat label="Target Velocity"
                value={`${fmtC(e.target_velocity, cur, 1)}/hr`} />
              <MiniStat label="Delta vs Expected"
                value={`${(e.velocity_delta ?? 0) >= 0 ? "+" : ""}${fmtC(e.velocity_delta, cur, 1)}`}
                color={(e.velocity_delta ?? 0) >= 0 ? "#30D158" : "#FF3B30"} />
              <MiniStat label="Expected So Far"
                value={fmtC(e.expected_earnings, cur)} />
            </div>
          )}
        </Card>
      )}

      {/* Dynamic threshold — from earnings_engine, shown so driver knows the boundary */}
      {e?.dynamic_threshold != null && (
        <Card style={{ padding: "12px 18px" }}>
          <div style={{
            display: "flex", justifyContent: "space-between",
            alignItems: "center", gap: 8
          }}>
            <span style={{ fontSize: 13, color: "#666" }}>
              At-risk boundary (earnings engine)
            </span>
            <span style={{
              fontSize: 15, fontWeight: 700, color: "#FF9500",
              fontFamily: "monospace"
            }}>
              ±{fmtC(e.dynamic_threshold, cur, 0)}
            </span>
          </div>
        </Card>
      )}

      {/* Recent flags */}
      {flagged.length > 0 && (
        <Card>
          <Lbl>Recent Flags</Lbl>
          <div style={{ display: "flex", flexDirection: "column", gap: 8, marginTop: 8 }}>
            {flagged.slice(0, 5).map(ev => (
              <div key={ev.id} style={{
                display: "flex", alignItems: "center",
                justifyContent: "space-between", padding: "10px 14px",
                background: "#141414", borderRadius: 10
              }}>
                <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                  <SevBadge sev={ev.severity} />
                  <div>
                    <div style={{ fontSize: 15, fontWeight: 600, color: "#e0e0e0" }}>
                      {(ev.flagType ?? ev.severity ?? "Event").replace(/_/g, " ")}
                    </div>
                    <div style={{ fontSize: 12, color: "#555", fontFamily: "monospace" }}>
                      {ev.tripId} · {ev.motionType?.replace(/_/g, " ")}
                    </div>
                  </div>
                </div>
                <div style={{ fontSize: 11, color: "#555", fontFamily: "monospace", flexShrink: 0 }}>
                  {fmtTs(ev.timestamp)}
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
}

// FLAGGED EVENTS
function FlaggedEvents({ filtered, total, tripIds, motionOpts, audioOpts, sevOpts,
  fSev, setFSev, fTrip, setFTrip, fMotion, setFMotion, fAudio, setFAudio }) {

  const clearAll = () => { setFSev(""); setFTrip(""); setFMotion(""); setFAudio(""); };
  const hasFilter = fSev || fTrip || fMotion || fAudio;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <Card style={{ padding: "13px 16px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
          <IFilter size={14} color="#555" />
          <span style={{ fontSize: 12, color: "#555", fontFamily: "monospace" }}>Filter:</span>
          {/* Severity options derived from live fusion.severity values */}
          <Sel
            value={fSev}
            onChange={setFSev}
            placeholder="All Severities"
            options={sevOpts.map(v => ({
              value: v,
              label: String(v).charAt(0).toUpperCase() + String(v).slice(1),
            }))}
          />
          {/* Trip IDs from live data */}
          <Sel value={fTrip} onChange={setFTrip} placeholder="All Trips"
            options={tripIds.map(id => ({ value: id, label: id }))} />
          {/* Motion/audio types built from live events */}
          <Sel value={fMotion} onChange={setFMotion} placeholder="All Motion"
            options={motionOpts.map(t => ({ value: t, label: t.replace(/_/g, " ") }))} />
          <Sel value={fAudio} onChange={setFAudio} placeholder="All Audio"
            options={audioOpts.map(t => ({ value: t, label: t.replace(/_/g, " ") }))} />
          {hasFilter && (
            <button onClick={clearAll} style={{
              padding: "7px 12px", borderRadius: 8,
              border: "1px solid #2a2a2a", background: "transparent", color: "#888",
              fontSize: 12, cursor: "pointer", fontFamily: "monospace"
            }}>
              ✕ Clear
            </button>
          )}
          <span style={{ marginLeft: "auto", fontSize: 12, color: "#555", fontFamily: "monospace" }}>
            {filtered.length} / {total}
          </span>
        </div>
      </Card>

      {!filtered.length ? (
        <Card>
          <p style={{ color: "#555", fontSize: 15, textAlign: "center", padding: "24px 0" }}>
            {total ? "No events match your filters." : "No flagged events yet. Start the demo."}
          </p>
        </Card>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          {filtered.map(ev => {
            const c = SEV[ev.severity] ?? SEV.safe;
            // Human-readable labels for motion/audio event types
            const motionLabel: Record<string, string> = {
              emergency_stop: "Emergency Stop",
              harsh_brake: "Hard Brake",
              moderate_brake: "Moderate Brake",
              soft_brake: "Soft Brake",
              harsh_corner: "Sharp Turn",
              moderate_corner: "Moderate Turn",
              road_noise: "Road Noise",
              normal: "Normal",
            };
            const audioLabel: Record<string, string> = {
              argument: "Verbal Conflict",
              very_loud: "Very Loud Cabin",
              elevated: "Elevated Noise",
              background: "Background",
            };
            const whatHappened = [
              ev.motionType && ev.motionType !== "normal" && ev.motionType !== "road_noise"
                ? (motionLabel[ev.motionType] ?? ev.motionType.replace(/_/g, " "))
                : null,
              ev.audioClass && ev.audioClass !== "background"
                ? (audioLabel[ev.audioClass] ?? ev.audioClass.replace(/_/g, " "))
                : null,
            ].filter(Boolean).join(" + ") || (ev.flagType ?? ev.severity ?? "Event").replace(/_/g, " ");

            const earnSd = ev.earningsStatus ? statusDisplay(ev.earningsStatus) : null;

            return (
              <Card key={ev.id} style={{ borderColor: c.border, padding: "16px 18px" }}>
                {/* Header row */}
                <div style={{
                  display: "flex", alignItems: "flex-start",
                  justifyContent: "space-between", gap: 12, flexWrap: "wrap"
                }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 11 }}>
                    <div style={{
                      width: 44, height: 44, borderRadius: 12, background: c.bg,
                      display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0
                    }}>
                      <IAlert size={20} color={c.text} />
                    </div>
                    <div>
                      <div style={{
                        fontSize: 17, fontWeight: 700, color: "#f0f0f0",
                        fontFamily: "Georgia,serif"
                      }}>
                        {whatHappened}
                      </div>
                      <div style={{ fontSize: 12, color: "#555", marginTop: 2, fontFamily: "monospace" }}>
                        {ev.tripId} · {fmtTs(ev.timestamp)}
                      </div>
                    </div>
                  </div>
                  <SevBadge sev={ev.severity} large />
                </div>

                {/* Driver-relevant stats only */}
                <div style={{
                  marginTop: 14, display: "grid",
                  gridTemplateColumns: "repeat(auto-fill,minmax(130px,1fr))", gap: 9
                }}>
                  <MiniStat label="Speed at Moment" value={`${fmt(ev.speedKmh, 0)} km/h`} />
                  <MiniStat label="Earnings Then" value={fmtC(ev.earningsAtFlag, ev.currency)} color="#0A84FF" />
                  {earnSd && (
                    <MiniStat label="Earn Status" value={earnSd.label} color={earnSd.color} />
                  )}
                </div>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// TRIP SUMMARIES
// ═══════════════════════════════════════════════════════════════════════════════
function TripSummaries({ trips, cur }) {
  if (!trips.length) return (
    <Card>
      <p style={{ color: "#555", fontSize: 15, padding: "24px 0", textAlign: "center" }}>
        Trip summaries will appear as the demo progresses.
      </p>
    </Card>
  );

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      {trips.map(t => {
        const c = SEV[t.worstSev] ?? SEV.safe;
        const uniqMotion = [...new Set(t.motionEvents ?? [])];
        const uniqAudio = [...new Set(t.audioEvents ?? [])];
        // earnings velocity only computed if backend sent both fare and duration
        const vel = (t.fare != null && t.durationMin)
          ? `${fmtC(t.fare / t.durationMin, t.currency ?? cur, 1)}/min` : "—";

        return (
          <Card key={t.tripId} style={{ borderColor: t.flags ? c.border : "#1e1e1e" }}>
            <div style={{
              display: "flex", alignItems: "center",
              justifyContent: "space-between", flexWrap: "wrap", gap: 8
            }}>
              <div>
                <div style={{
                  fontSize: 24, fontWeight: 800, color: "#fff",
                  fontFamily: "Georgia,serif"
                }}>{t.tripId}</div>
                {t.completedAt && (
                  <div style={{ fontSize: 12, color: "#555", fontFamily: "monospace" }}>
                    Completed {t.completedAt}
                  </div>
                )}
              </div>
              <SevBadge sev={t.worstSev} large />
            </div>

            <div style={{
              marginTop: 14, display: "grid",
              gridTemplateColumns: "repeat(auto-fill,minmax(115px,1fr))", gap: 9
            }}>
              {[
                ["Flagged Events", t.flags],
                ["Fare", t.fare != null ? fmtC(t.fare, t.currency ?? cur) : "—"],
                ["Distance", t.distKm != null ? `${t.distKm} km` : "—"],
                ["Duration", t.durationMin != null ? `${t.durationMin} min` : "—"],
                ["Earn/min", vel],
                ["Motion Events", t.motionCount ?? 0],
                ["Audio Events", t.audioCount ?? 0],
                ["Max Conflict", fmt(t.maxConflict, 4)],
                ["Earn at Close", t.earningsAtClose != null
                  ? fmtC(t.earningsAtClose, t.currency ?? cur) : "—"],
              ].map(([k, v]) => <MiniStat key={k} label={k} value={v} />)}
            </div>

            {(uniqMotion.length > 0 || uniqAudio.length > 0) && (
              <div style={{ marginTop: 12, display: "flex", gap: 6, flexWrap: "wrap" }}>
                {uniqMotion.map(m => (
                  <span key={m} style={{
                    fontSize: 11, background: "rgba(10,132,255,0.12)",
                    color: "#0A84FF", borderRadius: 6, padding: "3px 9px",
                    fontFamily: "monospace", border: "1px solid rgba(10,132,255,0.25)"
                  }}>
                    {m.replace(/_/g, " ")}
                  </span>
                ))}
                {uniqAudio.map(a => (
                  <span key={a} style={{
                    fontSize: 11, background: "rgba(255,149,0,0.12)",
                    color: "#FF9500", borderRadius: 6, padding: "3px 9px",
                    fontFamily: "monospace", border: "1px solid rgba(255,149,0,0.25)"
                  }}>
                    {a.replace(/_/g, " ")}
                  </span>
                ))}
              </div>
            )}
          </Card>
        );
      })}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// EARNINGS
// ═══════════════════════════════════════════════════════════════════════════════
function Earnings({ log, latest, target, projected, cur }) {
  if (!log.length) return (
    <Card>
      <p style={{ color: "#555", fontSize: 15, padding: "24px 0", textAlign: "center" }}>
        Start the demo to see your earnings chart.
      </p>
    </Card>
  );

  const lastEntry = log[log.length - 1];
  const e = latest?.earnings;
  const sd = statusDisplay(e?.status);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
        <Card>
          <Lbl>Total Earned</Lbl>
          <BigNum color="#0A84FF">{fmtC(lastEntry.earnings, lastEntry.currency ?? cur)}</BigNum>
          <div style={{ fontSize: 14, color: sd.color, marginTop: 6, fontWeight: 600 }}>
            {sd.label}
          </div>
        </Card>
        <Card>
          <Lbl>Projected End-of-Shift</Lbl>
          <BigNum color="#FF9500">{fmtC(projected, cur)}</BigNum>
          <div style={{ fontSize: 13, color: "#666", marginTop: 6 }}>
            Target {fmtC(target, cur)}
          </div>
        </Card>
      </div>

      {/* All velocity/threshold fields from evaluate_goal output */}
      {e && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(2,1fr)", gap: 12 }}>
          {[
            ["Current Velocity", `${fmtC(e.current_velocity, cur, 1)}/hr`],
            ["Target Velocity", `${fmtC(e.target_velocity, cur, 1)}/hr`],
            ["Velocity Delta", `${(e.velocity_delta ?? 0) >= 0 ? "+" : ""}${fmtC(e.velocity_delta, cur, 1)}`],
            ["Expected So Far", fmtC(e.expected_earnings, cur)],
            ["Dynamic Threshold", `±${fmtC(e.dynamic_threshold, cur, 0)}`],
            ["Projected Shift", fmtC(e.projected_shift_earnings, cur)],
          ].map(([k, v]) => (
            <Card key={k} style={{ padding: "13px 16px" }}>
              <Lbl>{k}</Lbl>
              <div style={{
                fontSize: 22, fontWeight: 800, color: "#e0e0e0",
                fontFamily: "Georgia,serif"
              }}>{v}</div>
            </Card>
          ))}
        </div>
      )}

      <Card>
        <div style={{
          display: "flex", justifyContent: "space-between",
          alignItems: "center", marginBottom: 14, flexWrap: "wrap", gap: 8
        }}>
          <Lbl>Earnings Over Shift</Lbl>
          <div style={{ display: "flex", gap: 16, fontSize: 11, fontFamily: "monospace" }}>
            <span style={{ color: "#0A84FF" }}>● Actual</span>
            <span style={{ color: "#FF9500" }}>╌ Projected</span>
            <span style={{ color: "#30D158" }}>╌ Target</span>
          </div>
        </div>
        <EarningsChart data={log} projected={projected} target={target} currency={cur} />
      </Card>

      <Card style={{ padding: 0, overflow: "hidden" }}>
        <div style={{ padding: "13px 18px", borderBottom: "1px solid #1a1a1a" }}>
          <Lbl>Per-Trip Breakdown</Lbl>
        </div>
        <div style={{ overflowX: "auto" }}>
          <table style={{
            width: "100%", borderCollapse: "collapse",
            fontFamily: "monospace", fontSize: 13
          }}>
            <thead>
              <tr style={{ background: "#0d0d0d" }}>
                {["#", "Trip", "Time", "Cumulative", "This Trip"].map(h => (
                  <th key={h} style={{
                    padding: "10px 16px", textAlign: "left",
                    color: "#555", fontSize: 10, letterSpacing: "0.14em",
                    textTransform: "uppercase", fontWeight: 600
                  }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {log.map((row, i) => {
                const step = i > 0 ? row.earnings - log[i - 1].earnings : row.earnings;
                return (
                  <tr key={i} style={{ borderTop: "1px solid #141414" }}>
                    <td style={{ padding: "10px 16px", color: "#444" }}>{i + 1}</td>
                    <td style={{ padding: "10px 16px", color: "#ddd" }}>{row.tripId}</td>
                    <td style={{ padding: "10px 16px", color: "#666" }}>{row.timestamp}</td>
                    <td style={{ padding: "10px 16px", color: "#0A84FF", fontWeight: 700 }}>
                      {fmtC(row.earnings, row.currency ?? cur)}
                    </td>
                    <td style={{ padding: "10px 16px", color: "#30D158", fontWeight: 600 }}>
                      +{fmtC(step, row.currency ?? cur)}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}