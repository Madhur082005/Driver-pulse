# 🚗 Driver Pulse: Frontend Architecture 

Welcome to the frontend repository for **Driver Pulse**, a hackathon project focused on live shift intelligence, stress event tracking, and earnings velocity for Uber drivers. 

As the primary frontend architect for this project, my goal was to build an interface that isn't just a dashboard, but a **glanceable, driver-centric tool** built with production-grade engineering principles.

## 🛠️ Tech Stack
- **Framework:** Next.js 14 (App Router)
- **Library:** React (with strict TypeScript)
- **Styling:** Tailwind CSS (Dark-mode optimized)
- **Data Visualization:** Recharts
- **Icons:** Lucide-React

---

## 🧠 My Engineering & UX Decisions

When designing and building this frontend, I focused heavily on maintainability and driver psychology. Here are the core principles I implemented:

### 1. Strict Component-Driven Architecture
I deliberately avoided monolithic files. The UI is broken down into highly modular, reusable components (like `<Card />`, `<ProgressBar />`, and `<StatBlock />`). This separation of concerns ensures that the codebase remains scalable and easy to debug.

### 2. The "2-Second Glance" Rule
Drivers are behind the wheel; they cannot afford cognitive overload. I designed the typography hierarchy (massive text for earnings, muted text for secondary stats) so a driver can understand their status (e.g., "Ahead of Goal") in under two seconds.

### 3. Transparent Explainability (Data -> Human)
Instead of just telling a driver they had a "Stress Event," I engineered the `StressEventCard` to display **Raw Signals vs. Thresholds** (e.g., *Max Jerk: 4.5 m/s³ vs Threshold: 3.0*). This fulfills the core hackathon requirement of building an explainable, transparent system.

### 4. Dynamic Color Psychology
Implemented a real-time status banner and color-coded components:
- **Green:** Positive pace / Clean trips.
- **Orange/Yellow:** Moderate stress / Falling behind pace.
- **Red:** High-stress events (like conflict detection) for immediate attention.

---

## 📁 Modular Directory Structure

I structured the `src` directory to decouple UI primitives from business logic and page views:

```text
src/
├── app/                  # Next.js routing, global styles, and layout shell
├── components/           
│   ├── ui/               # Reusable Atomic UI Primitives (Badge, Card, etc.)
│   ├── charts/           # Specialized Recharts wrappers
│   └── timeline/         # Feedback & event timeline components
├── views/                # High-level page orchestrators
│   ├── MidShiftView      # Real-time earnings & velocity tracking
│   └── PostTripView      # Trip quality & stress report
└── lib/                  
    ├── types.ts          # Strict TypeScript interfaces matching Python backend
    └── mockData.ts       # Fallback data for seamless demo presentation

