// =========================================================
// Before You Go – Front end
// Talks to our Python server (/api/...) and draws the page.
// =========================================================

const DEFAULT_PLACE = { name: "Ottawa", region: "Ontario", country: "Canada", lat: 45.4215, lon: -75.6972 };

const $ = (id) => document.getElementById(id);
let currentPlace = null;

// ---------- Saved data (kept in this browser) ----------
function readStore(key, fallback) {
  try { return JSON.parse(localStorage.getItem(key)) ?? fallback; }
  catch { return fallback; }
}
function writeStore(key, value) {
  try { localStorage.setItem(key, JSON.stringify(value)); } catch { /* storage blocked: app still works */ }
}
let savedPlaces = readStore("byg_saved", []);

// ---------- Helpers ----------
function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text ?? "";
  return div.innerHTML;
}
const deg = (n) => `${n}°`.replace("-", "−");  // use a real minus sign
const minus = (text) => String(text).replace(/-(?=\d)/g, "−");  // same, inside sentences

// Colour for a temperature: deep blue when freezing, teal when mild, amber when hot
function tempColor(t) {
  const stops = [[-30, [70, 110, 200]], [-10, [96, 160, 214]], [5, [110, 190, 190]], [18, [140, 196, 120]], [28, [233, 162, 59]], [38, [214, 90, 50]]];
  if (t <= stops[0][0]) return `rgb(${stops[0][1]})`;
  for (let i = 1; i < stops.length; i++) {
    const [t1, c1] = stops[i];
    const [t0, c0] = stops[i - 1];
    if (t <= t1) {
      const k = (t - t0) / (t1 - t0);
      return `rgb(${c0.map((c, j) => Math.round(c + (c1[j] - c) * k)).join(",")})`;
    }
  }
  return `rgb(${stops.at(-1)[1]})`;
}

function showToast(message) {
  const toast = $("toast");
  toast.textContent = message;
  toast.hidden = false;
  clearTimeout(showToast.timer);
  showToast.timer = setTimeout(() => (toast.hidden = true), 3200);
}

function placeKey(p) { return `${p.lat.toFixed(2)},${p.lon.toFixed(2)}`; }

// ---------- Weather icons (simple line drawings) ----------
const ICONS = {
  "clear-day": `<circle class="sun-fill" cx="12" cy="12" r="4.2"/><g class="sun"><path d="M12 2.5v2.2M12 19.3v2.2M2.5 12h2.2M19.3 12h2.2M5.3 5.3l1.5 1.5M17.2 17.2l1.5 1.5M5.3 18.7l1.5-1.5M17.2 6.8l1.5-1.5"/></g>`,
  "clear-night": `<path d="M19.5 14.5A8 8 0 0 1 9.5 4.5a8 8 0 1 0 10 10z"/>`,
  "partly-day": `<circle class="sun-fill" cx="9" cy="9" r="3.4"/><g class="sun"><path d="M9 2.5v1.6M2.5 9h1.6M4.4 4.4l1.1 1.1M13.6 4.4l-1.1 1.1"/></g><path d="M8 19h9.5a3.5 3.5 0 0 0 .3-7 5 5 0 0 0-9.6 1.2A3 3 0 0 0 8 19z"/>`,
  "partly-night": `<path d="M13 5.5A5 5 0 0 1 7 10a5 5 0 0 0 4.4-6.9"/><path d="M8 19h9.5a3.5 3.5 0 0 0 .3-7 5 5 0 0 0-9.6 1.2A3 3 0 0 0 8 19z"/>`,
  cloudy: `<path d="M7 18h10.5a4 4 0 0 0 .4-8 6 6 0 0 0-11.4 1.6A3.3 3.3 0 0 0 7 18z"/>`,
  fog: `<path d="M7 13h10.5a4 4 0 0 0 .4-8 6 6 0 0 0-11.4 1.6A3.3 3.3 0 0 0 7 13z"/><path d="M4 17h16M6 20.5h12"/>`,
  drizzle: `<path d="M7 14h10.5a4 4 0 0 0 .4-8 6 6 0 0 0-11.4 1.6A3.3 3.3 0 0 0 7 14z"/><g class="drop"><path d="M9 17.5v1M13 17.5v1M17 17.5v1"/></g>`,
  rain: `<path d="M7 14h10.5a4 4 0 0 0 .4-8 6 6 0 0 0-11.4 1.6A3.3 3.3 0 0 0 7 14z"/><g class="drop"><path d="M8.5 17l-1 3M12.5 17l-1 3M16.5 17l-1 3"/></g>`,
  freezing: `<path d="M7 14h10.5a4 4 0 0 0 .4-8 6 6 0 0 0-11.4 1.6A3.3 3.3 0 0 0 7 14z"/><g class="drop"><path d="M8.5 17l-1 3M16.5 17l-1 3"/></g><path d="M12 17v4M10.3 18l3.4 2M13.7 18l-3.4 2"/>`,
  snow: `<path d="M7 14h10.5a4 4 0 0 0 .4-8 6 6 0 0 0-11.4 1.6A3.3 3.3 0 0 0 7 14z"/><path d="M8 18.5h.01M12 17.5h.01M16 18.5h.01M10 21h.01M14 21h.01" stroke-width="2.4"/>`,
  storm: `<path d="M7 13h10.5a4 4 0 0 0 .4-8 6 6 0 0 0-11.4 1.6A3.3 3.3 0 0 0 7 13z"/><g class="bolt"><path d="M12.5 14l-2.5 4h3l-2 4"/></g>`,
};
function icon(name) {
  return `<svg class="wx" viewBox="0 0 24 24" aria-hidden="true">${ICONS[name] || ICONS.cloudy}</svg>`;
}

// ---------- Sky colour ----------
function setSky(current) {
  let theme = current.kind === "partly" ? "partly" : current.kind;
  if (theme === "drizzle" || theme === "freezing") theme = "rain";
  if (!current.is_day && ["clear", "partly", "cloudy", "fog"].includes(theme)) theme = "night";
  document.body.className = `sky-${theme}`;
}

// ---------- Load weather from our Python server ----------
async function loadPlace(place) {
  currentPlace = place;
  writeStore("byg_last", place);
  document.body.classList.add("is-loading");
  $("placeName").textContent = placeTitle(place);
  updateSaveButton();

  const params = new URLSearchParams({
    lat: place.lat, lon: place.lon,
    name: place.name, region: place.region || "", country: place.country || "",
  });

  try {
    const response = await fetch(`/api/weather?${params}`);
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "The weather service didn't answer.");
    render(data);
  } catch (error) {
    showError(error.message);
  } finally {
    document.body.classList.remove("is-loading");
  }
}

function placeTitle(p) {
  return [p.name, p.region].filter(Boolean).join(", ");
}

function showError(message) {
$("headline").innerHTML = `<span class="state-msg">Couldn't load the weather.</span>`;
  $("nowFeels").textContent = message;
  const retry = document.createElement("button");
  retry.className = "retry-btn";
  retry.textContent = "Try again";
  retry.onclick = () => loadPlace(currentPlace);
  $("nowLabel").replaceChildren(retry);
}

// ---------- Draw the whole page ----------
function render(data) {
  const { current, today, advice } = data;
  setSky(current);

  // Advice sentence, word by word
  $("headline").innerHTML = advice.headline
    .split(" ")
    .map((word, i) => `<span class="word" style="animation-delay:${i * 55}ms">${escapeHtml(minus(word))}</span>`)
    .join(" ");

  // Right now
  $("nowIcon").innerHTML = icon(current.icon);
  $("nowTemp").textContent = deg(current.temp);
  $("nowLabel").textContent = current.label;
  $("nowFeels").textContent = `Feels like ${deg(current.feels)}`;
  $("dayRange").innerHTML = `High <strong>${deg(today.high)}</strong>, low <strong>${deg(today.low)}</strong><br>Updated ${escapeHtml(data.updated)}`;

  renderOutfit(advice);
  renderAlerts(advice.alerts);
  renderBest(advice);
  renderRibbon(data.hourly);
  renderWeek(data.daily);
  renderDetails(current, today);
}

// What to wear: a checklist you tick off while getting dressed
function renderOutfit(advice) {
  const [low, high] = advice.feels_range;
  $("wearNote").textContent = low === high
    ? `Dressed for feels-like ${deg(low)} over the next 12 hours.`
    : `Dressed for feels-like ${deg(low)} to ${deg(high)} over the next 12 hours.`;

  $("outfitList").innerHTML = advice.outfit.map((item, i) => `
    <li><label>
      <input type="checkbox" data-i="${i}">
      <span class="item-icon" aria-hidden="true">${item.icon}</span>
      <span class="item-name">${escapeHtml(minus(item.name))}</span>
    </label></li>`).join("");
  $("readyNote").hidden = true;

  const extras = advice.extras;
  $("bringBlock").hidden = extras.length === 0;
  $("extrasList").innerHTML = extras.map((item) => `
    <li>
      <span class="item-icon" aria-hidden="true">${item.icon}</span>
      <span>${escapeHtml(item.name)}</span>
      <small>${escapeHtml(item.why)}</small>
    </li>`).join("");
}

$("outfitList").addEventListener("change", () => {
  const boxes = [...$("outfitList").querySelectorAll("input")];
  $("readyNote").hidden = !boxes.every((box) => box.checked);
});

function renderAlerts(alerts) {
  if (alerts.length === 0) {
    $("alertsList").innerHTML = `<li class="clear"><strong>Nothing to worry about</strong><p>No ice, storms or extreme temperatures in the next 12 hours.</p></li>`;
    return;
  }
  $("alertsList").innerHTML = alerts.map((a) => `
    <li class="${a.level}">
      <strong>${escapeHtml(a.title)}</strong>
      <p>${escapeHtml(minus(a.message))}</p>
    </li>`).join("");
}

function renderBest(advice) {
  const best = advice.best_time;
  $("bestBlock").hidden = !best;
  if (best) {
    $("bestTime").textContent = best.label;
    $("bestReason").textContent = minus(`${best.day}. ${best.reason}.`);
  }
  $("scoreValue").textContent = advice.score;
  $("scoreLabel").textContent = advice.score_label.toLowerCase();
  requestAnimationFrame(() => ($("scoreBar").style.width = `${advice.score}%`));
}

// 24-hour ribbon: a smooth temperature line across the hours
function renderRibbon(hours) {
  const COL = 68;                                  // width of one hour column in px
  const H = 60;                                    // height of the curve area
  const temps = hours.map((h) => h.temp);
  const min = Math.min(...temps), max = Math.max(...temps);
  const span = Math.max(max - min, 4);
  const points = hours.map((h, i) => [i * COL + COL / 2, H - ((h.temp - min) / span) * (H - 10) - 5]);

  // Turn the points into a smooth curve
  let path = `M${points[0][0]},${points[0][1]}`;
  for (let i = 0; i < points.length - 1; i++) {
    const [x0, y0] = points[Math.max(i - 1, 0)];
    const [x1, y1] = points[i];
    const [x2, y2] = points[i + 1];
    const [x3, y3] = points[Math.min(i + 2, points.length - 1)];
    path += ` C${x1 + (x2 - x0) / 6},${y1 + (y2 - y0) / 6} ${x2 - (x3 - x1) / 6},${y2 - (y3 - y1) / 6} ${x2},${y2}`;
  }
  const width = hours.length * COL;
  const area = `${path} L${points.at(-1)[0]},${H + 6} L${points[0][0]},${H + 6} Z`;

  const columns = hours.map((h, i) => `
    <div class="hour">
      <span class="h-label ${i === 0 ? "now-label" : ""}">${escapeHtml(h.label)}</span>
      <span class="h-temp">${deg(h.temp)}</span>
      <span class="h-space"></span>
      <span class="h-icon">${icon(h.icon)}</span>
      <span class="h-pop" title="${h.pop}% chance of precipitation"><span style="height:${h.pop}%"></span></span>
      <span class="h-pop-text">${h.pop >= 20 ? h.pop + "%" : ""}</span>
    </div>`).join("");

  $("ribbon").innerHTML = `
    <svg class="curve" width="${width}" height="${H + 6}" viewBox="0 0 ${width} ${H + 6}" aria-hidden="true">
      <defs><linearGradient id="ribbonFade" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0" stop-color="#14202b" stop-opacity=".09"/><stop offset="1" stop-color="#14202b" stop-opacity="0"/>
      </linearGradient></defs>
      <path class="area" d="${area}"/>
      <path d="${path}"/>
      <circle cx="${points[0][0]}" cy="${points[0][1]}" r="4"/>
    </svg>${columns}`;
}

// This week: each day's range drawn on one shared scale
function renderWeek(days) {
  const lowest = Math.min(...days.map((d) => d.low));
  const highest = Math.max(...days.map((d) => d.high));
  const span = Math.max(highest - lowest, 1);

  $("weekList").innerHTML = days.map((d) => {
    const left = ((d.low - lowest) / span) * 100;
    const width = Math.max(((d.high - d.low) / span) * 100, 4);
    const pop = d.snow >= 1 ? `${d.snow} cm` : d.pop >= 20 ? `${d.pop}%` : "";
    return `
      <li>
        <span class="w-day">${escapeHtml(d.day)}</span>
        <span class="w-icon" title="${escapeHtml(d.label)}">${icon(d.icon)}</span>
        <span class="w-pop">${pop}</span>
        <span class="w-low">${deg(d.low)}</span>
        <span class="range" aria-label="${escapeHtml(d.label)}, low ${d.low}, high ${d.high}"><span style="left:${left}%;width:${width}%;background:linear-gradient(90deg, ${tempColor(d.low)}, ${tempColor(d.high)})"></span></span>
        <span class="w-high">${deg(d.high)}</span>
      </li>`;
  }).join("");
}

function renderDetails(current, today) {
  const items = [
    ["Humidity", `${current.humidity}%`],
    ["Wind", `${current.wind} km/h`],
    ["Gusts", `${current.gusts} km/h`],
    ["UV index", today.uv],
    ["Sunrise", today.sunrise],
    ["Sunset", today.sunset],
  ];
  $("details").innerHTML = items.map(([label, value]) =>
    `<div><dt>${label}</dt><dd>${escapeHtml(String(value))}</dd></div>`).join("");
}

// ---------- Search with suggestions ----------
let searchTimer;
let results = [];
let activeIndex = -1;

$("searchInput").addEventListener("input", (event) => {
  clearTimeout(searchTimer);
  const query = event.target.value.trim();
  if (query.length < 2) return closeResults();
  searchTimer = setTimeout(() => searchPlaces(query), 250);  // wait until typing pauses
});

async function searchPlaces(query) {
  try {
    const response = await fetch(`/api/search?q=${encodeURIComponent(query)}`);
    const data = await response.json();
    if (!response.ok) throw new Error(data.error);
    results = data;
    showResults();
  } catch {
    showToast("Search isn't available right now. Try again in a moment.");
  }
}

function showResults() {
  const list = $("searchResults");
  activeIndex = -1;
  list.innerHTML = results.length
    ? results.map((p, i) => `
        <li role="option" id="opt-${i}" data-i="${i}" aria-selected="false">
          <span>${escapeHtml(p.name)}</span>
          <small>${escapeHtml([p.region, p.country].filter(Boolean).join(", "))}</small>
        </li>`).join("")
    : `<li class="empty">No places match that name</li>`;
  list.hidden = false;
  $("searchInput").setAttribute("aria-expanded", "true");
}

function closeResults() {
  $("searchResults").hidden = true;
  $("searchInput").setAttribute("aria-expanded", "false");
}

function choose(i) {
  const place = results[i];
  if (!place) return;
  $("searchInput").value = "";
  closeResults();
  loadPlace(place);
}

$("searchResults").addEventListener("mousedown", (event) => {
  const li = event.target.closest("li[data-i]");
  if (li) choose(Number(li.dataset.i));
});

// Arrow keys and Enter move through the suggestions
$("searchInput").addEventListener("keydown", (event) => {
  const items = [...$("searchResults").querySelectorAll("li[data-i]")];
  if (event.key === "ArrowDown" || event.key === "ArrowUp") {
    if (!items.length) return;
    event.preventDefault();
    activeIndex = (activeIndex + (event.key === "ArrowDown" ? 1 : -1) + items.length) % items.length;
    items.forEach((li, i) => li.setAttribute("aria-selected", String(i === activeIndex)));
  } else if (event.key === "Enter") {
    event.preventDefault();
    choose(activeIndex >= 0 ? activeIndex : 0);
  } else if (event.key === "Escape") {
    closeResults();
  }
});
$("searchInput").addEventListener("blur", () => setTimeout(closeResults, 150));

// ---------- Use my location ----------
$("locateBtn").addEventListener("click", () => {
  if (!navigator.geolocation) return showToast("Your browser can't share your location.");
  navigator.geolocation.getCurrentPosition(
    (pos) => loadPlace({ name: "Your location", region: "", country: "", lat: pos.coords.latitude, lon: pos.coords.longitude }),
    () => showToast("Location is off. Allow it in your browser, or search for a city."),
    { timeout: 10000 }
  );
});

// ---------- Saved places ----------
function renderSaved() {
  $("savedPlaces").innerHTML = savedPlaces.map((p, i) => `
    <span class="chip">
      <button type="button" data-open="${i}">${escapeHtml(p.name)}</button>
      <button type="button" class="chip-remove" data-remove="${i}" aria-label="Remove ${escapeHtml(p.name)}">×</button>
    </span>`).join("");
}

function updateSaveButton() {
  const saved = currentPlace && savedPlaces.some((p) => placeKey(p) === placeKey(currentPlace));
  $("saveBtn").textContent = saved ? "Saved" : "Save place";
  $("saveBtn").setAttribute("aria-pressed", String(Boolean(saved)));
}

$("saveBtn").addEventListener("click", () => {
  if (!currentPlace) return;
  const key = placeKey(currentPlace);
  if (savedPlaces.some((p) => placeKey(p) === key)) {
    savedPlaces = savedPlaces.filter((p) => placeKey(p) !== key);
    showToast(`Removed ${currentPlace.name} from saved places`);
  } else {
    savedPlaces = [...savedPlaces, currentPlace].slice(-6);
    showToast(`Saved ${currentPlace.name}`);
  }
  writeStore("byg_saved", savedPlaces);
  renderSaved();
  updateSaveButton();
});

$("savedPlaces").addEventListener("click", (event) => {
  const open = event.target.dataset.open;
  const remove = event.target.dataset.remove;
  if (open !== undefined) loadPlace(savedPlaces[Number(open)]);
  if (remove !== undefined) {
    savedPlaces.splice(Number(remove), 1);
    writeStore("byg_saved", savedPlaces);
    renderSaved();
    updateSaveButton();
  }
});

// ---------- Footer ----------
$("year").textContent = new Date().getFullYear();   // keeps the copyright year current
$("backTop").addEventListener("click", (event) => {
  event.preventDefault();
  window.scrollTo({ top: 0, behavior: "smooth" });
});

// ---------- Start ----------
renderSaved();
loadPlace(readStore("byg_last", DEFAULT_PLACE));