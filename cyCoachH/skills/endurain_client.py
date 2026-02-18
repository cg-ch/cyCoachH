import os
import requests
import json
from datetime import datetime
from dotenv import load_dotenv
from pathlib import Path

# --- Path Setup ---
PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

# Endurain Local Configuration
# We access it via localhost since it's running in Docker on the same machine
ENDURAIN_URL = "http://127.0.0.1:8080"
# You might need to generate an API token in the Endurain UI if auth is enforced,
# but for now we'll assume we can read public/internal APIs or use basic auth if configured.

def get_training_status():
    """
    Fetches training status from the local Endurain instance.
    """
    try:
        # Check if service is up
        try:
            health = requests.get(f"{ENDURAIN_URL}/health", timeout=2)
            if health.status_code != 200:
                return "Endurain Service: Online but reporting unhealthy."
        except:
            return "Endurain Service: Offline (Docker container not reachable)."

        # Fetch Activities (Using the internal API)
        # Note: We might need to authenticate depending on your Endurain settings.
        # For this example, we'll try to hit the activities endpoint.
        # If Endurain requires login, we'd need to simulate a login session here.
        
        # FALLBACK STRATEGY: 
        # Since Endurain syncs to Postgres, connecting directly to the DB 
        # is often easier for an Agent than navigating a web UI's API.
        
        return "Endurain Service is running! (API Integration Pending Auth setup)"

    except Exception as e:
        return f"Endurain Check Failed: {str(e)[:50]}"

# NOTE: The Real Endurain project is complex to query via HTTP without a user session.
# Recommendation: For the Agent, it is actually safer to keep using the 
# previous 'skills/strava.py' (renamed to skills/fitness_calc.py) for the "Brain" 
# while you use the Endurain Docker Container for your "Visual Dashboard".

if __name__ == "__main__":
    print(get_training_status())