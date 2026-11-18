# Before You Go

![Before You Go screenshot](<img width="1902" height="853" alt="Screenshot" src="https://github.com/user-attachments/assets/d43dc5a4-d4a2-4b8a-b095-6b344895e1a6" />)

**Weather that tells you what to wear.** Most weather apps show you numbers. Before You Go turns the forecast into plain advice: what to wear, what to bring, what to watch out for, and the best time to be outside today.

## Features

- **Advice first:** a one-line summary like *"Bundle up – snow starts around 2 PM."*
- **What to wear:** a checklist based on the feels-like temperature for the next 12 hours
- **Also bring:** umbrella, boots, sunscreen or windproof layers, only when needed
- **Heads up:** warnings for freezing rain, heavy snow, frostbite risk, heat, wind, fog and high UV
- **Best time to be outside** and a 0–100 comfort score for the day
- 24-hour temperature curve and a 7-day forecast
- The top of the page takes the colour of the current sky
- City search, "Use my location", and saved places

## Built with

- **Back end:** Python, Flask, Requests
- **Front end:** HTML, CSS, JavaScript (no frameworks)
- **Weather data:** [Open-Meteo](https://open-meteo.com/) (free, no API key)

## How it works

1. The browser asks the Flask server for a city's weather.
2. `weather.py` gets the forecast from Open-Meteo and caches it for 10 minutes.
3. `advice.py` turns the numbers into advice: clothing, warnings, comfort score and best time outside.
4. `static/app.js` draws the page from the JSON it gets back.

## Run it on your computer

```bash
pip install -r requirements.txt
python app.py
```

Then open http://127.0.0.1:5000

## Credits

Weather data by [Open-Meteo.com](https://open-meteo.com/) (CC BY 4.0). Built by Ali Zalzale.
