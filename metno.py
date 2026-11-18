"""
metno.py – Backup weather source: MET Norway (the Norwegian weather service).

We only use this when Open-Meteo refuses or doesn't answer. MET Norway is
free, needs no API key, and covers the whole world. It just asks every app
to send a User-Agent that says who we are.

Its data comes in a different shape than Open-Meteo's, so this file
converts it into the SAME shape Open-Meteo uses. That way advice.py doesn't
need to change at all – it can't even tell which service answered.
"""

import math
from collections import defaultdict
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import requests
from astral import Observer
from astral.sun import sunrise, sunset
from timezonefinder import TimezoneFinder

METNO_URL = "https://api.met.no/weatherapi/locationforecast/2.0/complete"
HEADERS = {"User-Agent": "BeforeYouGo/1.0 github.com/alizalzale-tech/before-you-go"}

_tz_finder = None  # loaded the first time we need it (it's a big lookup table)

# MET Norway names the weather in words ("lightsnow_day").
# This turns those words into the WMO number codes that advice.py understands.
SYMBOL_CODES = {
    "clearsky": 0, "fair": 1, "partlycloudy": 2, "cloudy": 3, "fog": 45,
    "lightrain": 61, "rain": 63, "heavyrain": 65,
    "lightrainshowers": 80, "rainshowers": 81, "heavyrainshowers": 82,
    "lightsleet": 61, "sleet": 63, "heavysleet": 65,
    "lightsleetshowers": 80, "sleetshowers": 81, "heavysleetshowers": 82,
    "lightsnow": 71, "snow": 73, "heavysnow": 75,
    "lightsnowshowers": 85, "snowshowers": 85, "heavysnowshowers": 86,
}


def symbol_to_code(symbol):
    """'lightsnow_day' -> 71. Anything with thunder becomes a thunderstorm."""
    if not symbol:
        return 3
    name = symbol.split("_")[0]
    if "thunder" in name:
        return 95
    return SYMBOL_CODES.get(name, 3)


def is_snow_code(code):
    """True for the snow weather codes."""
    return code in (71, 73, 75, 77, 85, 86)


def feels_like(temp, humidity, wind_ms):
    """Apparent temperature (Steadman's formula) – how warm or cold it feels."""
    vapour = humidity / 100 * 6.105 * math.exp(17.27 * temp / (237.7 + temp))
    return temp + 0.33 * vapour - 0.70 * wind_ms - 4.00


def local_timezone(lat, lon):
    """Find the time zone for a spot on the map, e.g. Ottawa -> America/Toronto."""
    global _tz_finder
    if _tz_finder is None:
        _tz_finder = TimezoneFinder()
    return ZoneInfo(_tz_finder.timezone_at(lat=lat, lng=lon) or "UTC")


def sun_times(lat, lon, day, tz):
    """Sunrise and sunset for one day. Near the poles the sun may not rise or set."""
    spot = Observer(latitude=lat, longitude=lon)
    try:
        return sunrise(spot, day, tzinfo=tz), sunset(spot, day, tzinfo=tz)
    except ValueError:
        midnight = datetime(day.year, day.month, day.day, tzinfo=tz)
        return midnight, midnight  # treat it as a day with no daylight


def fetch_metno(lat, lon, timeout):
    """Ask MET Norway for a forecast. Raises requests errors if it fails."""
    response = requests.get(
        METNO_URL,
        params={"lat": round(lat, 4), "lon": round(lon, 4)},  # MET wants at most 4 decimals
        headers=HEADERS,
        timeout=timeout,
    )
    response.raise_for_status()
    return response.json()


def to_open_meteo_shape(data, lat, lon):
    """Convert a MET Norway answer into the same layout Open-Meteo sends."""
    tz = local_timezone(lat, lon)
    steps = data["properties"]["timeseries"]
    fmt = "%Y-%m-%dT%H:%M"

    def local(step):
        utc = datetime.fromisoformat(step["time"].replace("Z", "+00:00"))
        return utc.astimezone(tz)

    def pop_of(step):
        """Chance of precipitation. Use MET's number if it gives one, otherwise estimate."""
        for block in ("next_1_hours", "next_6_hours", "next_12_hours"):
            chance = step["data"].get(block, {}).get("details", {}).get("probability_of_precipitation")
            if chance is not None:
                return chance
        amount = step["data"].get("next_1_hours", {}).get("details", {}).get("precipitation_amount", 0)
        return 80 if amount >= 0.5 else 50 if amount > 0 else 5

    # ----- Hourly: MET gives hour-by-hour steps for about 2 days, then 6-hour steps -----
    hourly = defaultdict(list)
    for step in steps:
        one_hour = step["data"].get("next_1_hours")
        if not one_hour:
            break  # we've reached the 6-hour steps
        now = step["data"]["instant"]["details"]
        temp = now["air_temperature"]
        wind = now.get("wind_speed", 0)
        precip = one_hour.get("details", {}).get("precipitation_amount", 0)
        code = symbol_to_code(one_hour.get("summary", {}).get("symbol_code"))
        is_snow = is_snow_code(code) or (precip > 0 and temp <= 0)

        hourly["time"].append(local(step).strftime(fmt))
        hourly["temperature_2m"].append(temp)
        hourly["apparent_temperature"].append(round(feels_like(temp, now.get("relative_humidity", 70), wind), 1))
        hourly["relative_humidity_2m"].append(now.get("relative_humidity", 70))
        hourly["precipitation_probability"].append(pop_of(step))
        hourly["precipitation"].append(precip)
        hourly["snowfall"].append(round(precip * 0.7, 2) if is_snow else 0)  # 1 mm of water ≈ 0.7 cm of snow
        hourly["weather_code"].append(code)
        hourly["wind_speed_10m"].append(round(wind * 3.6, 1))                 # m/s -> km/h
        hourly["wind_gusts_10m"].append(round(now.get("wind_speed_of_gust", wind * 1.5) * 3.6, 1))
        hourly["uv_index"].append(now.get("ultraviolet_index_clear_sky", 0))

    if not hourly["time"]:
        raise ValueError("MET Norway sent no hourly data.")

    # ----- Daily: group every step (hourly and 6-hourly) by its local date -----
    days = defaultdict(lambda: defaultdict(list))
    for step in steps:
        when = local(step)
        now = step["data"]["instant"]["details"]
        bucket = days[when.date()]
        temp = now["air_temperature"]
        bucket["temps"].append(temp)
        bucket["feels"].append(feels_like(temp, now.get("relative_humidity", 70), now.get("wind_speed", 0)))
        bucket["gusts"].append(now.get("wind_speed_of_gust", now.get("wind_speed", 0) * 1.5) * 3.6)
        bucket["uv"].append(now.get("ultraviolet_index_clear_sky", 0))
        bucket["pop"].append(pop_of(step))

        # Add up rain/snow without counting the same hours twice
        block = step["data"].get("next_1_hours") or step["data"].get("next_6_hours") or {}
        details = block.get("details", {})
        precip = details.get("precipitation_amount", 0)
        code = symbol_to_code(block.get("summary", {}).get("symbol_code"))
        if "next_1_hours" in step["data"] or when.hour % 6 == 0:
            bucket["precip"].append(precip)
            if is_snow_code(code) or (precip > 0 and temp <= 0):
                bucket["snow"].append(precip * 0.7)
        for key in ("air_temperature_max", "air_temperature_min"):
            if key in details:
                bucket["temps"].append(details[key])
        bucket["codes"].append((when.hour, code))

    daily = defaultdict(list)
    for day in sorted(days)[:7]:
        b = days[day]
        rise, sset = sun_times(lat, lon, day, tz)
        # The day's icon: the weather closest to midday
        midday_code = min(b["codes"], key=lambda hc: abs(hc[0] - 12))[1]
        daily["time"].append(day.isoformat())
        daily["weather_code"].append(midday_code)
        daily["temperature_2m_max"].append(max(b["temps"]))
        daily["temperature_2m_min"].append(min(b["temps"]))
        daily["apparent_temperature_max"].append(round(max(b["feels"]), 1))
        daily["apparent_temperature_min"].append(round(min(b["feels"]), 1))
        daily["sunrise"].append(rise.strftime(fmt))
        daily["sunset"].append(sset.strftime(fmt))
        daily["uv_index_max"].append(max(b["uv"]))
        daily["precipitation_sum"].append(round(sum(b["precip"]), 1))
        daily["precipitation_probability_max"].append(max(b["pop"]))
        daily["snowfall_sum"].append(round(sum(b["snow"]), 1))
        daily["wind_gusts_10m_max"].append(round(max(b["gusts"]), 1))

    # ----- Current: the hour we're in right now -----
    now_local = datetime.now(timezone.utc).astimezone(tz)
    first = datetime.fromisoformat(hourly["time"][0]).replace(tzinfo=tz)
    now_local = max(now_local, first)  # never earlier than the first hour we have
    i = max(n for n, t in enumerate(hourly["time"]) if datetime.fromisoformat(t).replace(tzinfo=tz) <= now_local)
    rise, sset = sun_times(lat, lon, now_local.date(), tz)

    current = {
        "time": now_local.strftime(fmt),
        "temperature_2m": hourly["temperature_2m"][i],
        "apparent_temperature": hourly["apparent_temperature"][i],
        "relative_humidity_2m": hourly["relative_humidity_2m"][i],
        "is_day": int(rise <= now_local < sset),
        "precipitation": hourly["precipitation"][i],
        "weather_code": hourly["weather_code"][i],
        "wind_speed_10m": hourly["wind_speed_10m"][i],
        "wind_gusts_10m": hourly["wind_gusts_10m"][i],
    }

    return {
        "timezone": str(tz),
        "timezone_abbreviation": now_local.strftime("%Z"),
        "current": current,
        "hourly": dict(hourly),
        "daily": dict(daily),
        "source": "MET Norway",
    }