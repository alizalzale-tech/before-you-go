"""
weather.py – Talks to the Open-Meteo weather service.

Open-Meteo is free and needs no API key.
  - Geocoding API: turns a city name into coordinates
  - Forecast API:  gives current, hourly and daily weather for coordinates
"""

import os
import time

import requests

# The addresses can be changed with environment variables (handy for testing)
FORECAST_URL = os.environ.get("FORECAST_URL", "https://api.open-meteo.com/v1/forecast")
GEOCODE_URL = os.environ.get("GEOCODE_URL", "https://geocoding-api.open-meteo.com/v1/search")

CACHE_SECONDS = 10 * 60   # keep a forecast for 10 minutes so we don't ask too often
TIMEOUT = 8               # seconds to wait for Open-Meteo before giving up

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

_cache = {}  # { (lat, lon): (time_saved, data) }


class WeatherError(Exception):
    """Raised when the weather service can't give us an answer."""


def search_places(query, count=6):
    """Find places that match a name, e.g. 'Ottawa'. Returns a list of dicts."""
    try:
        response = requests.get(
            GEOCODE_URL,
            params={"name": query, "count": count, "language": "en", "format": "json"},
            timeout=TIMEOUT,
        )
        response.raise_for_status()
    except requests.RequestException as error:
        raise WeatherError("Could not reach the place search service.") from error

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


def get_forecast(lat, lon):
    """Get the raw forecast for a location (uses a short cache)."""
    key = (round(lat, 2), round(lon, 2))
    saved = _cache.get(key)
    if saved and time.time() - saved[0] < CACHE_SECONDS:
        return saved[1]

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
    except requests.RequestException as error:
        raise WeatherError("Could not reach the weather service.") from error

    data = response.json()
    if response.status_code != 200 or data.get("error"):
        raise WeatherError(data.get("reason", "The weather service returned an error."))

    _cache[key] = (time.time(), data)
    return data