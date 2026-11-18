"""
weather.py – Gets the weather and finds places.

Main sources (free, no API key):
  - Open-Meteo Forecast API:  current, hourly and daily weather
  - Open-Meteo Geocoding API: turns a city name into coordinates

Backup sources, used only if Open-Meteo refuses or doesn't answer:
  - MET Norway (see metno.py) for the forecast
  - Photon (by Komoot) for the place search

Open-Meteo limits how many requests one internet address can make per day.
On shared hosting like Render, other apps use up that limit too, so having
a backup keeps the site working for everyone.
"""

import os
import time

import requests

from metno import fetch_metno, to_open_meteo_shape

# The addresses can be changed with environment variables (handy for testing)
FORECAST_URL = os.environ.get("FORECAST_URL", "https://api.open-meteo.com/v1/forecast")
GEOCODE_URL = os.environ.get("GEOCODE_URL", "https://geocoding-api.open-meteo.com/v1/search")
PHOTON_URL = "https://photon.komoot.io/api/"

CACHE_SECONDS = 30 * 60   # keep a forecast for 30 minutes so we don't ask too often
TIMEOUT = 8               # seconds to wait for a service before giving up
COOL_DOWN = 60 * 60       # after Open-Meteo says "limit exceeded", skip it for an hour

CURRENT_VARS = [
    "temperature_2m", "apparent_temperature", "relative_humidity_2m", "is_day",
    "precipitation", "weather_code", "wind_speed_10m", "wind_gusts_10m",
]
HOURLY_VARS = [
    "temperature_2m", "apparent_temperature", "precipitation_probability",
    "precipitation", "snowfall", "weather_code", "wind_speed_10m",
    "wind_gusts_10m", "uv_index",
]
DAILY_VARS = [
    "weather_code", "temperature_2m_max", "temperature_2m_min",
    "apparent_temperature_max", "apparent_temperature_min", "sunrise", "sunset",
    "uv_index_max", "precipitation_sum", "precipitation_probability_max",
    "snowfall_sum", "wind_gusts_10m_max",
]

_cache = {}               # { (lat, lon): (time_saved, data) }
_open_meteo_paused_until = 0   # a time; before it, we go straight to the backups


class WeatherError(Exception):
    """Raised when no weather service can give us an answer."""


def open_meteo_paused():
    return time.time() < _open_meteo_paused_until


def pause_open_meteo():
    """Open-Meteo told us we're over the limit: stop asking it for a while."""
    global _open_meteo_paused_until
    _open_meteo_paused_until = time.time() + COOL_DOWN


# ---------------------------------------------------------------------------
# Place search
# ---------------------------------------------------------------------------
def search_places(query, count=6):
    """Find places that match a name, e.g. 'Ottawa'. Returns a list of dicts."""
    if not open_meteo_paused():
        try:
            return search_open_meteo(query, count)
        except requests.RequestException as error:
            if getattr(error.response, "status_code", None) == 429:
                pause_open_meteo()
            # fall through and try the backup

    try:
        return search_photon(query, count)
    except requests.RequestException as error:
        raise WeatherError("Place search isn't available right now. Try again in a bit.") from error


def search_open_meteo(query, count):
    response = requests.get(
        GEOCODE_URL,
        params={"name": query, "count": count, "language": "en", "format": "json"},
        timeout=TIMEOUT,
    )
    response.raise_for_status()
    results = response.json().get("results") or []
    return [
        {
            "name": place["name"],
            "region": place.get("admin1", ""),
            "country": place.get("country", ""),
            "lat": place["latitude"],
            "lon": place["longitude"],
        }
        for place in results
    ]


def search_photon(query, count):
    """Backup search. Photon answers in GeoJSON: coordinates are [lon, lat]."""
    response = requests.get(
        PHOTON_URL,
        params={"q": query, "limit": count * 2, "lang": "en", "osm_tag": "place"},
        headers={"User-Agent": "BeforeYouGo/1.0 github.com/alizalzale-tech/before-you-go"},
        timeout=TIMEOUT,
    )
    response.raise_for_status()
    places = []
    for feature in response.json().get("features", []):
        info = feature["properties"]
        lon, lat = feature["geometry"]["coordinates"]
        places.append({
            "name": info.get("name", query),
            "region": info.get("state", ""),
            "country": info.get("country", ""),
            "lat": lat,
            "lon": lon,
        })
    return places[:count]


# ---------------------------------------------------------------------------
# Forecast
# ---------------------------------------------------------------------------
def get_forecast(lat, lon):
    """Get the raw forecast for a location. Tries Open-Meteo, then MET Norway."""
    key = (round(lat, 2), round(lon, 2))
    saved = _cache.get(key)
    if saved and time.time() - saved[0] < CACHE_SECONDS:
        return saved[1]

    data = None
    if not open_meteo_paused():
        try:
            data = forecast_open_meteo(lat, lon)
        except WeatherError:
            data = None  # try the backup below

    if data is None:
        try:
            data = to_open_meteo_shape(fetch_metno(lat, lon, TIMEOUT), lat, lon)
        except (requests.RequestException, KeyError, ValueError) as error:
            raise WeatherError("The weather service is busy right now. Try again in a bit.") from error

    _cache[key] = (time.time(), data)
    return data


def forecast_open_meteo(lat, lon):
    params = {
        "latitude": lat,
        "longitude": lon,
        "current": ",".join(CURRENT_VARS),
        "hourly": ",".join(HOURLY_VARS),
        "daily": ",".join(DAILY_VARS),
        "timezone": "auto",      # times come back in the location's local time
        "forecast_days": 7,
    }
    try:
        response = requests.get(FORECAST_URL, params=params, timeout=TIMEOUT)
        data = response.json()
    except (requests.RequestException, ValueError) as error:
        raise WeatherError("Could not reach Open-Meteo.") from error

    if response.status_code == 429:   # 429 = "Too Many Requests"
        pause_open_meteo()
    if response.status_code != 200 or data.get("error"):
        raise WeatherError(data.get("reason", "Open-Meteo returned an error."))

    data["source"] = "Open-Meteo"
    return data