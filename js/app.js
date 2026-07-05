const STORAGE_KEY = "tacobell-visited";
const PAGE_SIZE = 100;

let allLocations = [];
let filteredLocations = [];
let visited = new Set();
let map = null;
let markers = {};
let markerCluster = null;
let listOffset = 0;
let activeId = null;

const $ = (sel) => document.querySelector(sel);

function loadVisited() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) visited = new Set(JSON.parse(raw));
  } catch {
    visited = new Set();
  }
}

function saveVisited() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify([...visited]));
  updateStats();
  renderList();
  updateMarkers();
}

function toggleVisited(id) {
  if (visited.has(id)) {
    visited.delete(id);
  } else {
    visited.add(id);
  }
  saveVisited();
}

function updateStats() {
  const total = allLocations.length;
  const count = visited.size;
  const pct = total ? ((count / total) * 100).toFixed(1) : 0;

  $("#visited-count").textContent = count.toLocaleString();
  $("#total-count").textContent = total.toLocaleString();
  $("#percent-count").textContent = `${pct}%`;
  $("#progress-fill").style.width = `${pct}%`;
}

function formatAddress(loc) {
  const parts = [loc.address, loc.city];
  if (loc.state) parts.push(loc.state);
  if (loc.zip) parts.push(loc.zip);
  return parts.filter(Boolean).join(", ");
}

function countryLabel(code) {
  const names = {
    US: "United States",
    CA: "Canada",
    GB: "United Kingdom",
    AU: "Australia",
    ES: "Spain",
    IN: "India",
    NL: "Netherlands",
    PH: "Philippines",
    FI: "Finland",
    JP: "Japan",
    BR: "Brazil",
    KR: "South Korea",
    TH: "Thailand",
    ID: "Indonesia",
    PT: "Portugal",
    CL: "Chile",
    SV: "El Salvador",
    GU: "Guam",
    BA: "Bosnia and Herzegovina",
    CY: "Cyprus",
    FR: "France",
    AR: "Argentina",
  };
  return names[code] || code;
}

function applyFilters() {
  const query = $("#search").value.toLowerCase().trim();
  const country = $("#country-filter").value;
  const status = $("#status-filter").value;

  filteredLocations = allLocations.filter((loc) => {
    if (country && loc.country !== country) return false;
    if (status === "visited" && !visited.has(loc.id)) return false;
    if (status === "unvisited" && visited.has(loc.id)) return false;
    if (query) {
      const haystack = [
        loc.name, loc.address, loc.city, loc.state, loc.zip, loc.country,
      ].join(" ").toLowerCase();
      if (!haystack.includes(query)) return false;
    }
    return true;
  });

  listOffset = 0;
  renderList();
  $("#list-count").textContent = `${filteredLocations.length.toLocaleString()} locations`;
}

function renderList() {
  const list = $("#location-list");
  const slice = filteredLocations.slice(0, listOffset + PAGE_SIZE);

  list.innerHTML = slice.map((loc) => {
    const isVisited = visited.has(loc.id);
    const isActive = loc.id === activeId;
    return `
      <li class="location-item${isVisited ? " visited" : ""}${isActive ? " active" : ""}"
          data-id="${loc.id}">
        <span class="visit-check">${isVisited ? "✓" : ""}</span>
        <div class="location-info">
          <div class="location-name">${escapeHtml(loc.name)}</div>
          <div class="location-address">${escapeHtml(formatAddress(loc))}</div>
          <div class="location-meta">${countryLabel(loc.country)}${loc.storeNum ? ` · #${loc.storeNum}` : ""}</div>
        </div>
      </li>`;
  }).join("");

  if (slice.length < filteredLocations.length) {
    list.innerHTML += `<li class="list-more"><button type="button" class="btn" id="load-more">Load more (${filteredLocations.length - slice.length} remaining)</button></li>`;
    $("#load-more")?.addEventListener("click", () => {
      listOffset += PAGE_SIZE;
      renderList();
    });
  }
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

function initMap() {
  map = L.map("map", { zoomControl: true }).setView([39.8283, -98.5795], 4);
  L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a> &copy; CARTO',
    subdomains: "abcd",
    maxZoom: 19,
  }).addTo(map);
}

function createMarker(loc) {
  const isVisited = visited.has(loc.id);
  const color = isVisited ? "#4ade80" : "#702283";
  const icon = L.divIcon({
    className: "custom-marker",
    html: `<div style="
      width:12px;height:12px;border-radius:50%;
      background:${color};border:2px solid white;
      box-shadow:0 1px 4px rgba(0,0,0,0.5);
    "></div>`,
    iconSize: [12, 12],
    iconAnchor: [6, 6],
  });

  const marker = L.marker([loc.lat, loc.lng], { icon });
  marker.bindPopup(() => popupContent(loc));
  marker.on("click", () => {
    activeId = loc.id;
    renderList();
    scrollToItem(loc.id);
  });
  return marker;
}

function popupContent(loc) {
  const isVisited = visited.has(loc.id);
  const div = document.createElement("div");
  div.className = "popup-content";
  div.innerHTML = `
    <h3>${escapeHtml(loc.name)}</h3>
    <p>${escapeHtml(formatAddress(loc))}</p>
    <button type="button" class="popup-btn mark${isVisited ? " visited" : ""}">
      ${isVisited ? "✓ Visited" : "Mark as visited"}
    </button>`;
  div.querySelector("button").addEventListener("click", () => {
    toggleVisited(loc.id);
    map.closePopup();
  });
  return div;
}

function buildMarkers() {
  if (markerCluster) map.removeLayer(markerCluster);
  markers = {};
  markerCluster = L.markerClusterGroup({
    maxClusterRadius: 50,
    spiderfyOnMaxZoom: true,
    showCoverageOnHover: false,
  });

  allLocations.forEach((loc) => {
    markers[loc.id] = createMarker(loc);
    markerCluster.addLayer(markers[loc.id]);
  });
  map.addLayer(markerCluster);
}

function updateMarkers() {
  allLocations.forEach((loc) => {
    const marker = markers[loc.id];
    if (!marker) return;
    const isVisited = visited.has(loc.id);
    const color = isVisited ? "#4ade80" : "#702283";
    const el = marker.getElement()?.querySelector("div");
    if (el) el.style.background = color;
  });
}

function focusLocation(loc) {
  activeId = loc.id;
  map.setView([loc.lat, loc.lng], 15);
  markers[loc.id]?.openPopup();
  renderList();
  scrollToItem(loc.id);
}

function scrollToItem(id) {
  const item = document.querySelector(`[data-id="${id}"]`);
  item?.scrollIntoView({ block: "nearest", behavior: "smooth" });
}

function populateCountryFilter(countries) {
  const select = $("#country-filter");
  Object.entries(countries)
    .sort((a, b) => b[1] - a[1])
    .forEach(([code, count]) => {
      const opt = document.createElement("option");
      opt.value = code;
      opt.textContent = `${countryLabel(code)} (${count.toLocaleString()})`;
      select.appendChild(opt);
    });
}

function setupEvents() {
  $("#search").addEventListener("input", debounce(applyFilters, 200));
  $("#country-filter").addEventListener("change", applyFilters);
  $("#status-filter").addEventListener("change", applyFilters);

  $("#location-list").addEventListener("click", (e) => {
    const item = e.target.closest(".location-item");
    if (!item) return;
    const id = item.dataset.id;
    const loc = allLocations.find((l) => l.id === id);
    if (!loc) return;

    if (e.target.closest(".visit-check")) {
      toggleVisited(id);
    } else {
      focusLocation(loc);
    }
  });

  $("#btn-near-me").addEventListener("click", () => {
    if (!navigator.geolocation) {
      alert("Geolocation is not supported by your browser.");
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const { latitude, longitude } = pos.coords;
        map.setView([latitude, longitude], 12);
        let nearest = null;
        let minDist = Infinity;
        allLocations.forEach((loc) => {
          const d = haversine(latitude, longitude, loc.lat, loc.lng);
          if (d < minDist) {
            minDist = d;
            nearest = loc;
          }
        });
        if (nearest) focusLocation(nearest);
      },
      () => alert("Could not get your location. Check browser permissions.")
    );
  });

  $("#btn-export").addEventListener("click", () => {
    const data = {
      exported: new Date().toISOString(),
      visited: [...visited],
    };
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "tacobell-visited.json";
    a.click();
    URL.revokeObjectURL(a.href);
  });

  $("#import-file").addEventListener("change", (e) => {
    const file = e.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      try {
        const data = JSON.parse(reader.result);
        const ids = data.visited || data;
        if (!Array.isArray(ids)) throw new Error("Invalid format");
        ids.forEach((id) => visited.add(id));
        saveVisited();
        alert(`Imported ${ids.length} visited locations.`);
      } catch {
        alert("Could not read that file. Expected a JSON export from this app.");
      }
    };
    reader.readAsText(file);
    e.target.value = "";
  });
}

function haversine(lat1, lon1, lat2, lon2) {
  const R = 6371;
  const dLat = ((lat2 - lat1) * Math.PI) / 180;
  const dLon = ((lon2 - lon1) * Math.PI) / 180;
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos((lat1 * Math.PI) / 180) *
      Math.cos((lat2 * Math.PI) / 180) *
      Math.sin(dLon / 2) ** 2;
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

function debounce(fn, ms) {
  let timer;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), ms);
  };
}

async function init() {
  loadVisited();
  initMap();
  setupEvents();

  try {
    const resp = await fetch("data/locations.json");
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const data = await resp.json();
    allLocations = data.locations;
    populateCountryFilter(data.countries);
    filteredLocations = allLocations;
    updateStats();
    buildMarkers();
    applyFilters();
  } catch (err) {
    $("#loading").querySelector("p").textContent =
      `Failed to load locations: ${err.message}`;
    return;
  }

  $("#loading").classList.add("hidden");
}

init();
