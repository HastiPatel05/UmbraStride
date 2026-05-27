function debounce(fn, wait = 300) {
  let t;
  return (...args) => {
    clearTimeout(t);
    t = setTimeout(() => fn(...args), wait);
  };
}

const NOMINATIM_BASE = 'https://nominatim.openstreetmap.org/search';

async function fetchPlaces(q) {
  if (!q || !q.trim()) return [];
  const params = new URLSearchParams({ q: q.trim(), format: 'jsonv2', addressdetails: '1', limit: '6' });
  // Optional: add an `email` param to identify your application to the server (recommended for heavy usage)
  // params.set('email', 'your-email@example.com')
  const url = `${NOMINATIM_BASE}?${params.toString()}`;
  try {
    const res = await fetch(url, { headers: { 'Accept-Language': (navigator.language || 'en') } });
    if (!res.ok) return [];
    const data = await res.json();
    return data;
  } catch (err) {
    console.error('Geocode error', err);
    return [];
  }
}

function attachAutocomplete(input, listEl) {
  let items = [];
  let activeIdx = -1;

  function render() {
    listEl.innerHTML = '';
    if (!items.length) {
      listEl.hidden = true;
      input.setAttribute('aria-expanded', 'false');
      return;
    }
    listEl.hidden = false;
    input.setAttribute('aria-expanded', 'true');
    items.forEach((it, i) => {
      const li = document.createElement('li');
      li.textContent = it.display_name;
      li.tabIndex = -1;
      li.setAttribute('role', 'option');
      li.addEventListener('mousedown', (ev) => {
        // mousedown used instead of click to avoid blur before selection
        ev.preventDefault();
        select(i);
      });
      if (i === activeIdx) li.classList.add('active');
      listEl.appendChild(li);
    });
  }

  function select(idx) {
    const choice = items[idx];
    if (!choice) return;
    input.value = choice.display_name;
    input.dataset.lat = choice.lat;
    input.dataset.lon = choice.lon;
    input.dataset.place = JSON.stringify(choice);
    items = [];
    activeIdx = -1;
    render();
  }

  const doSearch = debounce(async () => {
    const q = input.value;
    if (!q || q.length < 2) {
      items = [];
      render();
      return;
    }
    items = await fetchPlaces(q);
    activeIdx = -1;
    render();
  }, 300);

  input.addEventListener('input', () => {
    // clear previous coords when user types
    delete input.dataset.lat;
    delete input.dataset.lon;
    delete input.dataset.place;
    doSearch();
  });

  input.addEventListener('keydown', (ev) => {
    if (listEl.hidden) return;
    if (ev.key === 'ArrowDown') {
      ev.preventDefault();
      activeIdx = Math.min(items.length - 1, activeIdx + 1);
      render();
    } else if (ev.key === 'ArrowUp') {
      ev.preventDefault();
      activeIdx = Math.max(0, activeIdx - 1);
      render();
    } else if (ev.key === 'Enter') {
      ev.preventDefault();
      if (activeIdx >= 0) select(activeIdx);
    } else if (ev.key === 'Escape') {
      items = [];
      activeIdx = -1;
      render();
    }
  });

  // hide suggestions on blur (allow click to register)
  input.addEventListener('blur', () => setTimeout(() => { items = []; activeIdx = -1; render(); }, 150));
}

function readPlaceFromInput(input) {
  const placeJson = input.dataset.place;
  if (placeJson) {
    try { return JSON.parse(placeJson); } catch (e) { }
  }
  return null;
}

async function ensurePlaceForInput(input) {
  const existing = readPlaceFromInput(input);
  if (existing) return existing;
  // attempt a quick forward geocode for the free-text value
  const q = input.value && input.value.trim();
  if (!q) return null;
  const results = await fetchPlaces(q);
  if (results && results.length) {
    const first = results[0];
    input.dataset.lat = first.lat;
    input.dataset.lon = first.lon;
    input.dataset.place = JSON.stringify(first);
    return first;
  }
  return null;
}

document.addEventListener('DOMContentLoaded', () => {
  const originInput = document.getElementById('origin-input');
  const destInput = document.getElementById('destination-input');
  const originList = document.getElementById('origin-list');
  const destList = document.getElementById('destination-list');
  const submitBtn = document.getElementById('od-submit');

  attachAutocomplete(originInput, originList);
  attachAutocomplete(destInput, destList);

  submitBtn.addEventListener('click', async () => {
    const origin = await ensurePlaceForInput(originInput);
    const destination = await ensurePlaceForInput(destInput);
    const payload = { origin, destination };
    console.log('Origin / Destination payload:', payload);
    // Dispatch an event so app code can listen for it and perform routing/search
    document.dispatchEvent(new CustomEvent('od:search', { detail: payload }));
    // Small demo: alert coordinates if available
    const oStr = origin ? `${origin.display_name} (${origin.lat}, ${origin.lon})` : originInput.value || '(none)';
    const dStr = destination ? `${destination.display_name} (${destination.lat}, ${destination.lon})` : destInput.value || '(none)';
    alert(`Origin:\n${oStr}\n\nDestination:\n${dStr}`);
  });
});
