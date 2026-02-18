import asyncio
import json
import os
import sys
import requests
import websockets
from datetime import datetime
from pathlib import Path
from rich.console import Console
from dotenv import load_dotenv
from openai import OpenAI

# --- Path Setup ---
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(PROJECT_ROOT))

try:
    from memory.ingest import MemorySystem
    from skills.weather import get_current_weather
    # REPLACED: runalyze -> endurain
    from skills.endurain import calculate_metrics
except ImportError:
    print("Error: Could not import internal modules. Check folder structure.")
    sys.exit(1)

# --- Configuration ---
load_dotenv(PROJECT_ROOT / ".env")
API_KEY = os.getenv("DEEPSEEK_API_KEY")
MM_URL = os.getenv("MATTERMOST_URL", "127.0.0.1")
MM_PORT = int(os.getenv("MATTERMOST_PORT", 8065))
MM_TOKEN = os.getenv("MATTERMOST_TOKEN")

# URLs
BASE_API = f"http://{MM_URL}:{MM_PORT}/api/v4"
WS_URL = f"ws://{MM_URL}:{MM_PORT}/api/v4/websocket"

console = Console()
client = OpenAI(api_key=API_KEY, base_url="https://api.deepseek.com")

class RobustGateway:
    def __init__(self):
        self.mem = MemorySystem()
        self.bot_user_id = None
        self.session = requests.Session()
        self.session.headers.update({"Authorization": f"Bearer {MM_TOKEN}"})
        self.processed_posts = set()

    def get_bot_id(self):
        """Get self ID via REST API."""
        try:
            r = self.session.get(f"{BASE_API}/users/me")
            r.raise_for_status()
            user = r.json()
            self.bot_user_id = user['id']
            console.print(f"[green]Authenticated as: {user['username']} ({self.bot_user_id})[/green]")
            return True
        except Exception as e:
            console.print(f"[red]REST API Auth Failed: {e}[/red]")
            return False

    def send_reply(self, channel_id, message, root_id=None):
        """Send message via REST API."""
        payload = {
            "channel_id": channel_id,
            "message": message,
            "root_id": root_id or ""
        }
        try:
            self.session.post(f"{BASE_API}/posts", json=payload)
            console.print(f"[blue]Replied to {channel_id}[/blue]")
        except Exception as e:
            console.print(f"[red]Failed to send reply: {e}[/red]")

    def think(self, user_query):
        """Brain logic with Endurain integration."""
        now_str = datetime.now().strftime("%A, %Y-%m-%d %H:%M")
        weather_str = get_current_weather()
        
        # Calculate Training Status via Endurain
        endurain_str = calculate_metrics()
        
        hits = self.mem.search(user_query, limit=2)
        context = "\n".join([f"- {h['content'][:200]}" for h in hits])
        
        prompt = f"""
        You are cyCoachH, powered by the Endurain engine.
        [SYSTEM STATUS]
        Time: {now_str}
        Weather: {weather_str}
        
        [ENDURAIN METRICS]
        {endurain_str}
        
        [CONTEXT FROM MEMORY]
        {context}
        
        [USER QUERY]
        {user_query}
        
        Reply concisely. Use Markdown.
        If advising on training, strictly follow the Coach's advice in the metrics above.
        """
        
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )
        return response.choices[0].message.content

    async def listen(self):
        """Main WebSocket Loop."""
        console.print(f"[dim]Connecting to WebSocket: {WS_URL}[/dim]")
        
        async for websocket in websockets.connect(WS_URL):
            try:
                auth_payload = {
                    "seq": 1,
                    "action": "authentication_challenge",
                    "data": {"token": MM_TOKEN}
                }
                await websocket.send(json.dumps(auth_payload))
                console.print("[green]WebSocket Connected & Authenticating...[/green]")

                async for message in websocket:
                    data = json.loads(message)
                    if data.get('event') == 'hello':
                        console.print("[bold green]Gateway Active: Listening...[/bold green]")
                        continue
                    if data.get('event') != 'posted':
                        continue

                    post = json.loads(data['data']['post'])
                    post_id = post['id']
                    if post_id in self.processed_posts: continue
                    self.processed_posts.add(post_id)
                    if len(self.processed_posts) > 100: self.processed_posts.pop()
                    
                    if post.get('user_id') == self.bot_user_id: continue

                    msg_text = post.get('message', '')
                    channel_type = data['data'].get('channel_type')
                    
                    if channel_type == 'D' or "@cycoach" in msg_text.lower():
                        console.print(f"[yellow]Incoming: {msg_text}[/yellow]")
                        reply = self.think(msg_text)
                        self.send_reply(post['channel_id'], reply, post['id'])

            except websockets.ConnectionClosed:
                console.print("[red]Connection Lost. Reconnecting in 5s...[/red]")
                await asyncio.sleep(5)
            except Exception as e:
                console.print(f"[red]Error in loop: {e}[/red]")
                await asyncio.sleep(5)

if __name__ == "__main__":
    bot = RobustGateway()
    if bot.get_bot_id():
        try:
            asyncio.run(bot.listen())
        except KeyboardInterrupt:
            print("\nExiting.")