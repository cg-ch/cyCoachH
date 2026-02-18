import os
import requests
from dotenv import load_dotenv
from pathlib import Path

# --- Path Setup ---
# skills/weather.py -> parent (skills) -> parent (root)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

# Configuration
# We use the key from .env to keep it secure, but it will use the one you tested.
API_KEY = os.getenv("OPENWEATHER")

# Chur Coordinates
LAT = "46.8508"
LON = "9.5320"

def get_current_weather():
    """
    Fetches weather via OpenWeather API 2.5 (Current Weather).
    """
    if not API_KEY:
        return "Weather Error: 'OPENWEATHER' key missing in .env"

    try:
        # Standard 2.5 Endpoint (Current Weather)
        url = "https://api.openweathermap.org/data/2.5/weather"
        params = {
            "lat": LAT,
            "lon": LON,
            "appid": API_KEY,
            "units": "metric"
        }
        
        # 5-second timeout to prevent hanging the bot
        response = requests.get(url, params=params, timeout=5)
        
        if response.status_code == 401:
            return "Weather Error: Invalid API Token. Check .env"
        elif response.status_code != 200:
            return f"Weather Error: HTTP {response.status_code}"

        data = response.json()
        
        # Parse 2.5 Response Structure
        # ----------------------------
        # {
        #   "weather": [{"description": "clear sky", ...}], 
        #   "main": {"temp": 12.5, "feels_like": 11.2, "humidity": 50}, 
        #   "wind": {"speed": 1.5}, 
        #   ...
        # }
        
        main = data.get("main", {})
        weather_list = data.get("weather", [{}])[0]
        wind = data.get("wind", {})
        
        temp = main.get("temp", 0)
        feels_like = main.get("feels_like", 0)
        humidity = main.get("humidity", 0)
        desc = weather_list.get("description", "Unknown")
        wind_speed = wind.get("speed", 0)
        
        # Format the report for the LLM
        report = (
            f"Chur: {desc.capitalize()}, "
            f"{temp:.1f}°C (Feels {feels_like:.1f}°C), "
            f"Humidity {humidity}%, Wind {wind_speed}m/s."
        )
        
        return report

    except Exception as e:
        return f"Weather Check Failed: {str(e)[:50]}"

if __name__ == "__main__":
    print(get_current_weather())