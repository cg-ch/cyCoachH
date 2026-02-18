import os
import sys
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI
from rich.console import Console

# --- Path Setup ---
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(PROJECT_ROOT))

try:
    from memory.ingest import MemorySystem
    from skills.weather import get_current_weather
    # REPLACED: runalyze -> endurain
    from skills.endurain import calculate_metrics
except ImportError:
    print("Error: Could not import internal modules. Check skills folder.")
    sys.exit(1)

# --- Configuration ---
load_dotenv(PROJECT_ROOT / ".env")
API_KEY = os.getenv("DEEPSEEK_API_KEY")
BASE_URL = "https://api.deepseek.com"
console = Console()

if not API_KEY:
    console.print("[red]Error: DEEPSEEK_API_KEY not found in .env[/red]")
    sys.exit(1)

client = OpenAI(api_key=API_KEY, base_url=BASE_URL)

def get_todays_log():
    today = datetime.now().strftime("%Y-%m-%d")
    log_path = PROJECT_ROOT / "memory/vault/daily" / f"{today}.md"
    if log_path.exists():
        return log_path.read_text(encoding="utf-8")
    return "(No logs for today yet.)"

def run_heartbeat():
    console.print(f"[bold blue]💓 cyCoachH Heartbeat at {datetime.now().strftime('%H:%M')}[/bold blue]")

    mem = MemorySystem()
    current_time = datetime.now().strftime("%A, %Y-%m-%d %H:%M")
    todays_log = get_todays_log()
    weather_str = get_current_weather()
    
    # Calculate Fitness/Fatigue using local Endurain engine
    endurain_str = calculate_metrics()
    
    context_hits = mem.search("current priorities urgent todo project status training plan", limit=3)
    context_str = "\n".join([f"- {h['content'][:200]}..." for h in context_hits])

    prompt = f"""
    You are cyCoachH, powered by Endurain logic.
    
    [STATUS]
    Time: {current_time}
    Weather: {weather_str}
    
    [ENDURAIN METRICS]
    {endurain_str}
    
    [RECENT MEMORY]
    {context_str}
    
    [TODAY'S LOGS]
    {todays_log}
    
    [INSTRUCTIONS]
    Analyze the situation.
    - Morning Check (06:00-09:00): Review Endurain Status. 
      * If 'High Fatigue' or TSB < -20, suggest recovery.
      * If 'Fresh', suggest training adapted to Weather.
    - If nominal, respond "HEARTBEAT_OK".
    - If action needed, provide a short message.
    """

    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "You are a concise system automation agent."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=200
        )
        
        reply = response.choices[0].message.content.strip()
        
        if "HEARTBEAT_OK" in reply:
            console.print("[green]System Nominal.[/green]")
        else:
            console.print("[bold yellow]🔔 ACTION REQUIRED:[/bold yellow]")
            console.print(reply)
            
            log_file = PROJECT_ROOT / "heartbeat" / "events.log"
            with open(log_file, "a") as f:
                f.write(f"[{current_time}] {reply}\n")

    except Exception as e:
        console.print(f"[red]Heartbeat failed: {e}[/red]")

if __name__ == "__main__":
    run_heartbeat()