Origin / Destination UI example

Files:
- origin_destination.html — standalone demo HTML
- origin_destination.js — JS autocomplete + selection logic (Nominatim)
- origin_destination.css — basic styles

Usage
1. Open `origin_destination.html` in a browser (double-click or serve from a local static server).
2. Type into Origin / Destination boxes. Suggestions come from OpenStreetMap Nominatim.
3. Click "Search" to see the selected places; the demo dispatches a `od:search` event with payload `{ origin, destination }`.

Integration notes
- To integrate into a React/Vue app, import the markup and call `attachAutocomplete()` logic from a component mount hook, or convert `origin_destination.js` into a small hook/component.
- For production or heavy usage, add an identifying `email` parameter (see Nominatim usage policy) or use a paid geocoding provider (Mapbox, Google Places).

Next steps
- I can convert this into a React component and insert it into a target file if you tell me the frontend framework and file path.
