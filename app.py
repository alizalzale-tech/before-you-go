"""
app.py – The Flask web server for Before You Go.

Run it with:   python app.py
Then open:     http://127.0.0.1:5000
"""

from flask import Flask, jsonify, render_template, request

from advice import build_report
from weather import WeatherError, get_forecast, search_places

app = Flask(__name__)


@app.route("/")
def home():
    """Send the main page."""
    return render_template("index.html")


@app.route("/api/search")
def api_search():
    """Search for a city by name: /api/search?q=Ottawa"""
    query = request.args.get("q", "").strip()
    if len(query) < 2:
        return jsonify([])
    try:
        return jsonify(search_places(query))
    except WeatherError as error:
        return jsonify({"error": str(error)}), 502


@app.route("/api/weather")
def api_weather():
    """Weather plus advice for a place: /api/weather?lat=45.42&lon=-75.69&name=Ottawa"""
    try:
        lat = float(request.args["lat"])
        lon = float(request.args["lon"])
    except (KeyError, ValueError):
        return jsonify({"error": "Please give a valid lat and lon."}), 400

    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return jsonify({"error": "Those coordinates are out of range."}), 400

    place = {
        "name": request.args.get("name", "Your location"),
        "region": request.args.get("region", ""),
        "country": request.args.get("country", ""),
        "lat": lat,
        "lon": lon,
    }

    try:
        raw = get_forecast(lat, lon)
        return jsonify(build_report(raw, place))
    except WeatherError as error:
        return jsonify({"error": str(error)}), 502


if __name__ == "__main__":
    # debug=True reloads the server when you save a file (only use this while building)
    app.run(debug=True)