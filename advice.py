"""
advice.py – The "brain" of Before You Go.

Takes a raw forecast from Open-Meteo and turns it into practical advice:
what to wear, what to bring, warnings to watch for, and the best time to
be outside today.
"""

from datetime import datetime, timedelta

# ---------------------------------------------------------------------------
# Weather codes (WMO standard, used by Open-Meteo)
# ---------------------------------------------------------------------------
WEATHER_CODES = {
    0: ("Clear sky", "clear"),
    1: ("Mostly clear", "clear"),
    2: ("Partly cloudy", "partly"),
    3: ("Overcast", "cloudy"),
    45: ("Fog", "fog"),
    48: ("Freezing fog", "fog"),
    51: ("Light drizzle", "drizzle"),
    53: ("Drizzle", "drizzle"),
    55: ("Heavy drizzle", "drizzle"),
    56: ("Freezing drizzle", "freezing"),
    57: ("Heavy freezing drizzle", "freezing"),
    61: ("Light rain", "rain"),
    63: ("Rain", "rain"),
    65: ("Heavy rain", "rain"),
    66: ("Freezing rain", "freezing"),
    67: ("Heavy freezing rain", "freezing"),
    71: ("Light snow", "snow"),
    73: ("Snow", "snow"),
    75: ("Heavy snow", "snow"),
    77: ("Snow grains", "snow"),
    80: ("Light showers", "rain"),
    81: ("Showers", "rain"),
    82: ("Heavy showers", "rain"),
    85: ("Snow showers", "snow"),
    86: ("Heavy snow showers", "snow"),
    95: ("Thunderstorm", "storm"),
    96: ("Thunderstorm with hail", "storm"),
    99: ("Thunderstorm with heavy hail", "storm"),
}

RAIN_KINDS = {"drizzle", "rain", "storm"}
FREEZING_CODES = {56, 57, 66, 67}
STORM_CODES = {95, 96, 99}
FOG_CODES = {45, 48}


def describe(code, is_day=True):
    """Turn a weather code into (label, icon name)."""
    label, kind = WEATHER_CODES.get(code, ("Unknown", "cloudy"))
    if kind in ("clear", "partly"):
        kind += "-day" if is_day else "-night"
    return label, kind


def kind_of(code):
    return WEATHER_CODES.get(code, ("", "cloudy"))[1]


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------
def parse(time_text):
    return datetime.fromisoformat(time_text)


def hour_label(moment):
    """2026-11-18T15:00 -> '3 PM'"""
    return moment.strftime("%I %p").lstrip("0")


def clock_label(moment):
    """2026-11-18T07:24 -> '7:24 AM'"""
    return moment.strftime("%I:%M %p").lstrip("0")


def r(value):
    """Round a number for display (and avoid showing -0)."""
    return int(round(value)) or 0


# ---------------------------------------------------------------------------
# Turning the raw forecast into simple lists we can work with
# ---------------------------------------------------------------------------
def build_hours(raw):
    """Return a list of hour dicts, starting at the current hour, for 24 hours."""
    hourly = raw["hourly"]
    now = parse(raw["current"]["time"])

    # Sunrise/sunset for each day, so we know which hours are in daylight
    daylight = {
        day: (parse(rise), parse(sset))
        for day, rise, sset in zip(raw["daily"]["time"], raw["daily"]["sunrise"], raw["daily"]["sunset"])
    }

    times = [parse(t) for t in hourly["time"]]
    start = max(i for i, t in enumerate(times) if t <= now)  # the hour we're in now

    hours = []
    for i in range(start, min(start + 24, len(times))):
        moment = times[i]
        rise, sset = daylight.get(moment.date().isoformat(), (None, None))
        is_day = bool(rise and rise <= moment < sset)
        code = hourly["weather_code"][i]
        label, icon = describe(code, is_day)
        hours.append({
            "time": moment,
            "temp": hourly["temperature_2m"][i],
            "feels": hourly["apparent_temperature"][i],
            "pop": hourly["precipitation_probability"][i] or 0,   # chance of precipitation %
            "precip": hourly["precipitation"][i] or 0,             # mm
            "snow": hourly["snowfall"][i] or 0,                    # cm
            "code": code,
            "kind": kind_of(code),
            "label": label,
            "icon": icon,
            "wind": hourly["wind_speed_10m"][i] or 0,
            "gusts": hourly["wind_gusts_10m"][i] or 0,
            "uv": hourly["uv_index"][i] or 0,
            "is_day": is_day,
        })
    return hours


# ---------------------------------------------------------------------------
# Advice: comfort score
# ---------------------------------------------------------------------------
def comfort(hour):
    """How nice is it to be outside this hour? 0 (awful) to 100 (perfect)."""
    score = 100
    gap = hour["feels"] - 18                         # 18°C feels-like is the sweet spot
    if gap < 0:
        score -= min(70, -gap * 1.5)                 # colder: dressing well helps, so cap it
    else:
        score -= gap * 2.5                           # hotter: heat gets uncomfortable fast
    score -= hour["pop"] * 0.5                       # chance of rain or snow
    score -= max(0, hour["wind"] - 15) * 1.2         # wind above 15 km/h
    if hour["precip"] > 0.2:
        score -= 20                                  # actually raining or snowing
    if hour["code"] in STORM_CODES:
        score -= 30
    return max(0, min(100, score))


def score_label(score):
    if score >= 75:
        return "Great day to be outside"
    if score >= 55:
        return "Decent day out"
    if score >= 35:
        return "Manageable, just dress for it"
    return "Stay cozy if you can"


# ---------------------------------------------------------------------------
# Advice: what to wear
# ---------------------------------------------------------------------------
def outfit_for(feels_min, feels_max):
    """Pick clothes for the coldest feels-like temperature you'll face."""
    if feels_min <= -25:
        items = [("🧥", "Heavy parka"), ("🧶", "Thermal base layer"), ("🧤", "Insulated mitts"),
                 ("🧢", "Toque"), ("🧣", "Scarf or neck warmer"), ("🥾", "Winter boots")]
    elif feels_min <= -15:
        items = [("🧥", "Winter parka"), ("🧶", "Warm sweater"), ("🧤", "Mitts or gloves"),
                 ("🧢", "Toque"), ("🧣", "Scarf"), ("🥾", "Winter boots")]
    elif feels_min <= -5:
        items = [("🧥", "Winter coat"), ("🧶", "Sweater"), ("🧤", "Gloves"),
                 ("🧢", "Toque"), ("🥾", "Warm boots")]
    elif feels_min <= 5:
        items = [("🧥", "Warm jacket"), ("👕", "Long sleeves"), ("🧤", "Light gloves"), ("👖", "Long pants")]
    elif feels_min <= 12:
        items = [("🧥", "Light jacket or hoodie"), ("👕", "Long sleeves"), ("👖", "Long pants")]
    elif feels_min <= 20:
        items = [("👕", "T-shirt"), ("🧥", "Light layer for later"), ("👖", "Pants or jeans")]
    elif feels_min <= 26:
        items = [("👕", "T-shirt"), ("🩳", "Shorts or light pants"), ("👟", "Breathable shoes")]
    else:
        items = [("👕", "Light, loose clothes"), ("🩳", "Shorts"), ("💧", "Water bottle"), ("🧢", "Hat")]

    outfit = [{"icon": icon, "name": name} for icon, name in items]

    # Big temperature swing during the day? Suggest layers.
    if feels_max - feels_min >= 10:
        outfit.append({"icon": "🔄", "name": f"Layers – it goes from {r(feels_min)}° to {r(feels_max)}°"})
    return outfit


# ---------------------------------------------------------------------------
# Advice: what to bring
# ---------------------------------------------------------------------------
def extras_for(window):
    extras = []

    rainy = [h for h in window if h["pop"] >= 40 and h["kind"] in RAIN_KINDS | {"freezing"}]
    if rainy:
        extras.append({"icon": "☂️", "name": "Umbrella",
                       "why": f"Rain likely around {hour_label(rainy[0]['time'])}"})

    snow_total = sum(h["snow"] for h in window)
    snowy = [h for h in window if h["pop"] >= 40 and h["kind"] == "snow"]
    if snow_total >= 0.5 or snowy:
        why = f"About {snow_total:.0f} cm of snow coming" if snow_total >= 1 else "Snow on the way"
        extras.append({"icon": "🥾", "name": "Waterproof boots", "why": why})

    day_hours = [h for h in window if h["is_day"]]
    uv_max = max((h["uv"] for h in day_hours), default=0)
    if uv_max >= 6:
        extras.append({"icon": "🧴", "name": "Sunscreen", "why": f"UV index reaches {r(uv_max)} (high)"})
    if uv_max >= 3 and any(h["kind"] == "clear" for h in day_hours):
        extras.append({"icon": "🕶️", "name": "Sunglasses", "why": "Sunny with moderate UV"})

    gust_max = max((h["gusts"] for h in window), default=0)
    if gust_max >= 40:
        extras.append({"icon": "🌬️", "name": "Something windproof", "why": f"Gusts up to {r(gust_max)} km/h"})

    return extras


# ---------------------------------------------------------------------------
# Advice: warnings
# ---------------------------------------------------------------------------
def alerts_for(window):
    alerts = []

    def add(level, title, message):
        alerts.append({"level": level, "title": title, "message": message})

    freezing = [h for h in window if h["code"] in FREEZING_CODES]
    if freezing:
        add("warning", "Freezing rain",
            f"Starting around {hour_label(freezing[0]['time'])}. Roads and sidewalks can turn to ice – leave extra time.")
    elif any(h["precip"] > 0 and -2 <= h["temp"] <= 2 for h in window):
        add("caution", "Slippery surfaces",
            "Wet snow or rain near 0°C can freeze. Watch your step and drive carefully.")

    snow_total = sum(h["snow"] for h in window)
    if snow_total >= 5:
        add("warning", "Heavy snow", f"About {r(snow_total)} cm expected. Leave early and clear your car before you go.")
    elif snow_total >= 2:
        add("caution", "Snowfall", f"About {r(snow_total)} cm expected. Give yourself a few extra minutes.")

    storms = [h for h in window if h["code"] in STORM_CODES]
    if storms:
        add("warning", "Thunderstorms", f"Possible around {hour_label(storms[0]['time'])}. Head indoors if you hear thunder.")

    feels_min = min(h["feels"] for h in window)
    feels_max = max(h["feels"] for h in window)
    if feels_min <= -28:
        add("warning", "Frostbite risk", f"Feels like {r(feels_min)}°. Exposed skin can freeze in minutes – cover up.")
    elif feels_min <= -20:
        add("caution", "Very cold", f"Feels like {r(feels_min)}°. Cover your face and hands.")

    if feels_max >= 32:
        add("warning", "Extreme heat", f"Feels like {r(feels_max)}°. Drink water, find shade and avoid hard activity midday.")

    gust_max = max(h["gusts"] for h in window)
    if gust_max >= 70:
        add("warning", "Strong winds", f"Gusts up to {r(gust_max)} km/h. Secure loose items outside.")
    elif gust_max >= 50:
        add("caution", "Windy", f"Gusts up to {r(gust_max)} km/h.")

    if any(h["code"] in FOG_CODES for h in window):
        add("caution", "Fog", "Low visibility at times. Use your low beams if you're driving.")

    uv_max = max(h["uv"] for h in window)
    if uv_max >= 8:
        add("caution", "Very high UV", f"UV index {r(uv_max)}. Sunburn can happen in under 15 minutes.")

    # Warnings first, then cautions
    alerts.sort(key=lambda a: a["level"] != "warning")
    return alerts


# ---------------------------------------------------------------------------
# Advice: best time to be outside
# ---------------------------------------------------------------------------
def best_time(hours, today):
    """Find the nicest 2-hour daylight window in the next 24 hours."""
    best = None
    for a, b in zip(hours, hours[1:]):
        if not (a["is_day"] and b["is_day"]):
            continue
        score = (comfort(a) + comfort(b)) / 2
        if best is None or score > best[0]:
            best = (score, a, b)

    if best is None:
        return None

    score, a, b = best
    end = b["time"] + timedelta(hours=1)
    day = "Today" if a["time"].date() == today else "Tomorrow"
    return {
        "label": f"{hour_label(a['time'])} – {hour_label(end)}",
        "day": day,
        "score": r(score),
        "reason": f"Feels like {r((a['feels'] + b['feels']) / 2)}°, "
                  f"{r(max(a['pop'], b['pop']))}% chance of precipitation",
    }


# ---------------------------------------------------------------------------
# Advice: one-line summary at the top
# ---------------------------------------------------------------------------
def headline_for(current_feels, current_kind, window):
    if current_feels <= -15:
        lead = "Bundle up"
    elif current_feels <= 0:
        lead = "Dress warm"
    elif current_feels <= 10:
        lead = "Grab a jacket"
    elif current_feels <= 20:
        lead = "Light layers today"
    elif current_feels <= 27:
        lead = "Enjoy the weather"
    else:
        lead = "Stay cool"

    first_wet = next((h for h in window if h["pop"] >= 50 and h["kind"] in RAIN_KINDS | {"snow", "freezing"}), None)
    if current_kind == "snow":
        event = "it's snowing right now"
    elif current_kind == "freezing":
        event = "freezing rain right now"
    elif current_kind in RAIN_KINDS:
        event = "it's raining right now"
    elif first_wet and first_wet["kind"] == "storm":
        event = f"storms possible around {hour_label(first_wet['time'])}"
    elif first_wet and first_wet["kind"] == "freezing":
        event = f"freezing rain starts around {hour_label(first_wet['time'])}"
    elif first_wet and first_wet["kind"] == "snow":
        event = f"snow starts around {hour_label(first_wet['time'])}"
    elif first_wet:
        event = f"rain likely around {hour_label(first_wet['time'])}"
    elif max(h["pop"] for h in window) < 25:
        event = "dry for the next 12 hours"
    else:
        event = "a small chance of showers"
    return f"{lead} – {event}."


# ---------------------------------------------------------------------------
# Put it all together
# ---------------------------------------------------------------------------
def build_report(raw, place):
    current = raw["current"]
    daily = raw["daily"]
    now = parse(current["time"])
    today = now.date()

    hours = build_hours(raw)
    window = hours[:12]  # advice looks at the next 12 hours

    feels_min = min(h["feels"] for h in window)
    feels_max = max(h["feels"] for h in window)
    day_hours = [h for h in hours if h["is_day"]]
    score = r(sum(comfort(h) for h in day_hours) / len(day_hours)) if day_hours else r(comfort(hours[0]))

    label, icon = describe(current["weather_code"], bool(current["is_day"]))

    return {
        "location": place,
        "timezone": raw.get("timezone_abbreviation", ""),
        "updated": clock_label(now),
        "current": {
            "temp": r(current["temperature_2m"]),
            "feels": r(current["apparent_temperature"]),
            "humidity": r(current["relative_humidity_2m"]),
            "wind": r(current["wind_speed_10m"]),
            "gusts": r(current["wind_gusts_10m"]),
            "label": label,
            "icon": icon,
            "kind": kind_of(current["weather_code"]),
            "is_day": bool(current["is_day"]),
        },
        "today": {
            "high": r(daily["temperature_2m_max"][0]),
            "low": r(daily["temperature_2m_min"][0]),
            "sunrise": clock_label(parse(daily["sunrise"][0])),
            "sunset": clock_label(parse(daily["sunset"][0])),
            "uv": r(daily["uv_index_max"][0] or 0),
            "pop": r(daily["precipitation_probability_max"][0] or 0),
        },
        "advice": {
            "headline": headline_for(current["apparent_temperature"], kind_of(current["weather_code"]), window),
            "score": score,
            "score_label": score_label(score),
            "feels_range": [r(feels_min), r(feels_max)],
            "outfit": outfit_for(feels_min, feels_max),
            "extras": extras_for(window),
            "alerts": alerts_for(window),
            "best_time": best_time(hours, today),
        },
        "hourly": [
            {
                "label": "Now" if i == 0 else hour_label(h["time"]),
                "temp": r(h["temp"]),
                "pop": r(h["pop"]),
                "icon": h["icon"],
            }
            for i, h in enumerate(hours)
        ],
        "daily": [
            {
                "day": "Today" if i == 0 else parse(day).strftime("%a"),
                "high": r(daily["temperature_2m_max"][i]),
                "low": r(daily["temperature_2m_min"][i]),
                "label": describe(daily["weather_code"][i])[0],
                "icon": describe(daily["weather_code"][i])[1],
                "pop": r(daily["precipitation_probability_max"][i] or 0),
                "snow": round(daily["snowfall_sum"][i] or 0, 1),
            }
            for i, day in enumerate(daily["time"])
        ],
    }