# User guide — using UmbraStride

This guide is for **anyone** who wants to use the UmbraStride map app. You do not need to know programming. If you are installing the project on your own machine, start with the [Setup guide](setup.md) first, then return here.

---

## What UmbraStride does for you

Imagine you are walking in Phoenix at 2 p.m. on a hot day. The **shortest** sidewalk route might be in full sun. UmbraStride can suggest a route that stays **more in building shade**, even if it is a bit longer.

You control the trade-off with a slider:

- Move toward **Shade** → route avoids sunny street segments more strongly.
- Move toward **Short** → route behaves like a normal shortest walking path.

The map can also show **3D buildings** and, if configured, **moving shadows** for the time you selected.

---

## Before you open the app

Someone (or you) must have:

1. **Installed** UmbraStride on the computer that runs the servers.
2. **Downloaded street data** for Arizona metros you care about (“bootstrap”).
3. **Created shade data** for those areas (“seed”)—demo data is enough to try routing.

If step 2 or 3 was skipped, the app will show an error like *“No graph for this area”* with a command to run. See [Setup guide — Bootstrap data](setup.md#4-bootstrap-arizona-data).

**Default area:** The app is tuned for **Phoenix metro (wide)** — roughly Phoenix, Tempe, and Scottsdale. You can walk other Arizona metros once their data is prepared (Tucson, Flagstaff, etc.).

---

## Opening the app

1. Make sure the **API** and **web** servers are running (see [Setup — Run the app](setup.md#5-run-the-app)).
2. Open a browser to: **http://localhost:5173**
3. You should see a map (tilted if 3D is enabled) and a **sidebar** on the left.

---

## Step-by-step: plan a walk

### 1. Set your start point (Origin)

- In the sidebar, click the **Origin** button (it highlights when active).
- **Click on the map** where you want to start walking.
- A **green dot** appears.

### 2. Set your end point (Destination)

- Click the **Destination** button.
- **Click on the map** where you want to go.
- A **red dot** appears.

**Tip:** Both points should be **inside the blue metro outline** on the map. If they are outside Arizona or outside a prepared metro, routing may fail.

### 3. Check the active area

Below the title you should see something like:

**Active area: Phoenix metro (wide)**

The app **chooses this automatically** from your two clicks. You do not pick a city from a dropdown.

- If it says **(graph not loaded)**, that area’s street data is missing—see [Troubleshooting](troubleshooting.md).

### 4. Set date and time

Use the **Date & time** field. This matters because:

- **Shade** on streets changes with sun position.
- The app looks up shade data for that time (or the nearest hour available).

**Important:** Shade data must exist for that day/hour. If you see a yellow note about *“nearest cached hour”*, the time you picked does not have exact data; routing still works but may be less accurate. An administrator can run the seed script for your dates (see [Shade cache — Time buckets](shade-cache.md#time-bucket-matching)).

### 5. Adjust the preference slider

- **Shade** side (left): stronger preference for shady segments.
- **Short** side (right): closer to shortest distance.
- The percentage shown (e.g. “65% shade bias”) is how much you lean toward shade.

### 6. Find routes

Click **Find routes**. Wait a few seconds the first time (loading street data). Later clicks are faster.

### 7. Read the results

Three cards may appear:

| Card | Meaning |
|------|---------|
| **Shortest** | Shortest walking distance; shade not prioritized. Orange line on map. |
| **Coolest** | Most shade-friendly path; may be longer. Teal line. |
| **Your route** | Path for your slider setting. Purple line. |

Each card shows:

- **Distance** in meters.
- **% shade** — average fraction of the route considered shady (higher = more shade).
- **Detour** — how much longer than shortest (0% detour = same length as shortest).

---

## Understanding the map view

### Navigation

- **Drag** to pan.
- **Scroll** or pinch to zoom.
- **Right-drag** or two-finger drag to rotate/pitch (3D view).
- Use **+ / −** controls top-left if needed.

### Zoom and 3D buildings

- Zoom to **level 15 or higher** to see **3D gray buildings** (OpenFreeMap data).
- Buildings grow to full height around zoom **16**.

### Live shadows (optional)

If a ShadeMap API key is configured in `apps/web/.env`:

- A banner may show **“2.5D shadows · N buildings”** when shadows are active.
- Shadows update when you change **date/time** or move the map.
- Without a key, you still get 3D buildings and routing; only the **live shadow overlay** is off.

### Route lines

Routes follow **sidewalks and walkable streets** from OpenStreetMap, not straight lines through buildings.

---

## What the app does *not* do (yet)

- **No turn-by-turn GPS navigation** — it shows a path on a map; you follow it yourself.
- **No real-time weather** — shade comes from cached simulation or demo data, not live clouds.
- **Not every address on Earth** — only prepared **Arizona metros** (and optional grid tiles).
- **Shade worker / real ShadeMap cache** — optional; demo seed is synthetic, not measured per building in real time.

---

## Frequently asked questions

### Why are all three routes the same line?

Usually **shade data is missing** for your selected time, so every street looks equally sunny. Fix: seed the cache for that AOI and date, or pick a datetime that matches seeded hours. See [Troubleshooting — Same routes](troubleshooting.md#all-three-routes-look-identical).

### Why does it say “No graph for this area”?

Street data was never downloaded for that metro. Run bootstrap for that preset (technical step in [Setup](setup.md)).

### Can I use this outside Arizona?

The project is built for Arizona presets. Other regions would need new configuration files and bootstrap—see [Arizona coverage](arizona.md) for the model.

### Do I need a ShadeMap account?

**No** for basic routing with demo shade. **Yes** for live shadow visualization on the map and for high-fidelity shade precompute.

### How far apart can origin and destination be?

They must lie in the **same prepared metro graph** and be **connected by walkable streets**. Very long trips may be slow on large graphs (`az-phoenix` is much bigger than downtown-only).

---

## Getting help

1. [Troubleshooting](troubleshooting.md) — common errors and fixes.
2. [Glossary](glossary.md) — term definitions.
3. [Setup guide](setup.md) — install and data preparation.
4. [Documentation index](README.md) — all topics.

---

## For developers

HTTP API details: [API reference](api.md).  
System design: [Architecture](architecture.md).  
Research context: [Paper mapping](paper-mapping.md).
