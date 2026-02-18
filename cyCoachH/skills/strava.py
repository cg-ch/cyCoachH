import os
import requests
import time
from datetime import datetime, timedelta
from dotenv import load_dotenv
from pathlib import Path

# --- Path Setup ---
PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

# Configuration
CLIENT_ID = os.getenv("STRAVA_CLIENT_ID")
CLIENT_SECRET = os.getenv("STRAVA_CLIENT_SECRET")
REFRESH_TOKEN = os.getenv("STRAVA_REFRESH_TOKEN")

def get_access_token():
    """Exchanges refresh token for a fresh access token."""
    if not all([CLIENT_ID, CLIENT_SECRET, REFRESH_TOKEN]):
        return None

    auth_url = "https://www.strava.com/oauth/token"
    payload = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "refresh_token": REFRESH_TOKEN,
        "grant_type": "refresh_token"
    }
    
    try:
        response = requests.post(auth_url, data=payload, timeout=5)
        if response.status_code == 200:
            return response.json()["access_token"]
    except:
        pass
    return None

def get_raw_activities(days=42):
    """
    Fetches raw activity list for the last X days (default 42 for CTL).
    Returns list of dicts or None on error.
    """
    token = get_access_token()
    if not token:
        return None

    try:
        url = "https://www.strava.com/api/v3/athlete/activities"
        # Timestamp for X days ago
        after_date = int((datetime.now() - timedelta(days=days)).timestamp())
        
        headers = {"Authorization": f"Bearer {token}"}
        params = {
            "after": after_date,
            "per_page": 100 
        }
        
        response = requests.get(url, headers=headers, params=params, timeout=5)
        if response.status_code == 200:
            return response.json()
    except:
        pass
    return None

def get_training_status():
    """Text summary for simple chat contexts."""
    activities = get_raw_activities(days=7)
    if activities is None:
        return "Strava: Connection Error."
    if not activities:
        return "Strava: No recent activities."

    total_km = sum(a.get("distance", 0) for a in activities) / 1000
    count = len(activities)
    latest = activities[0]
    latest_date = datetime.strptime(latest["start_date_local"], "%Y-%m-%dT%H:%M:%SZ").strftime("%Y-%m-%d")
    
    return f"Last 7 Days: {total_km:.1f}km ({count} runs). Latest: {latest_date} ({latest.get('name')})."

if __name__ == "__main__":
    print(get_training_status())