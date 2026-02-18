import sys
import json
import time
from datetime import datetime, timedelta
from pathlib import Path

# --- Path Setup ---
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(PROJECT_ROOT))
CACHE_FILE = PROJECT_ROOT / "memory" / "endurain_cache.json"

try:
    from skills.strava import get_raw_activities
except ImportError:
    print("Error: Could not import skills.strava")
    raise

def load_cache():
    if CACHE_FILE.exists():
        try:
            return json.loads(CACHE_FILE.read_text())
        except:
            pass
    return {"last_fetch": 0, "activities": []}

def save_cache(data):
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    CACHE_FILE.write_text(json.dumps(data))

def get_activities_smart():
    """Fetches activities with caching strategy."""
    cache = load_cache()
    now = time.time()
    
    # Refresh if cache is older than 6 hours
    is_stale = (now - cache["last_fetch"]) > 21600
    is_empty = len(cache.get("activities", [])) == 0

    if is_stale or is_empty:
        fresh_data = get_raw_activities(days=60)
        if fresh_data is not None:
            cache = {
                "last_fetch": now,
                "activities": fresh_data
            }
            save_cache(cache)
    
    return cache["activities"]

def format_pace(speed_mps):
    """Converts m/s to min/km"""
    if speed_mps <= 0: return "0:00"
    sec_per_km = 1000 / speed_mps
    mins = int(sec_per_km // 60)
    secs = int(sec_per_km % 60)
    return f"{mins}:{secs:02d}/km"

def calculate_metrics():
    """
    Main entry point used by beat.py and mattermost_raw.py
    """
    activities = get_activities_smart()
    
    if not activities:
        return "Endurain: No training data available via Strava."

    today = datetime.now().date()
    daily_load = {} 
    valid_activities_count = 0
    
    # Store today's specific stats
    todays_report = []

    for act in activities:
        try:
            act_date = datetime.strptime(act["start_date_local"], "%Y-%m-%dT%H:%M:%SZ").date()
            days_ago = (today - act_date).days
            
            # --- 1. Capture Today's Details ---
            if days_ago == 0:
                name = act.get("name", "Activity")
                dist_km = act.get("distance", 0) / 1000
                moving_min = act.get("moving_time", 0) / 60
                
                # Heart Rate
                avg_hr = act.get("average_heartrate", "N/A")
                max_hr = act.get("max_heartrate", "N/A")
                
                # Pace/Speed
                avg_speed = act.get("average_speed", 0)
                pace = format_pace(avg_speed)
                
                details = (
                    f"   - **{name}**: {dist_km:.1f}km in {moving_min:.0f}min "
                    f"| HR: {avg_hr}/{max_hr} (Avg/Max) | Pace: {pace}"
                )
                todays_report.append(details)

            # --- 2. Load Calculation for Fatigue ---
            if days_ago < 0: continue 
            
            minutes = act.get("moving_time", 0) / 60
            load = minutes * 1.0 
            
            daily_load[days_ago] = daily_load.get(days_ago, 0) + load
            valid_activities_count += 1
        except:
            continue

    # --- 3. Calculate CTL/ATL ---
    atl = sum(daily_load.get(d, 0) for d in range(7)) / 7.0
    ctl = sum(daily_load.get(d, 0) for d in range(42)) / 42.0
    tsb = ctl - atl

    # --- 4. Insight ---
    status = "Balanced"
    if tsb < -20: status = "High Fatigue"
    elif tsb > 20: status = "Fresh"

    # Format the 'Today' section
    today_section = "\n".join(todays_report) if todays_report else "   - No activities logged today."

    return (
        f"Endurain Status: {status} (TSB {tsb:.1f})\n"
        f"Fitness (CTL): {ctl:.1f} | Fatigue (ATL): {atl:.1f}\n"
        f"**Today's Log:**\n{today_section}"
    )

if __name__ == "__main__":
    print(calculate_metrics())