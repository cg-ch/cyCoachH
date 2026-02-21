import sys
import os
import json
import asyncio
from pathlib import Path
from rich.console import Console
from dotenv import load_dotenv
from openai import OpenAI
from mattermostdriver import Driver

# --- Path Setup ---
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(PROJECT_ROOT))

try:
    from memory.ingest import MemorySystem
except ImportError:
    print("Error: Could not import 'memory.ingest'. Check your folder structure.")
    sys.exit(1)

# --- Configuration ---
load_dotenv(PROJECT_ROOT / ".env")
API_KEY = os.getenv("DEEPSEEK_API_KEY")
# Force IP if 'localhost' causes IPv6 issues
MM_URL = os.getenv("MATTERMOST_URL", "127.0.0.1") 
MM_PORT = int(os.getenv("MATTERMOST_PORT", 8065))
MM_TOKEN = os.getenv("MATTERMOST_TOKEN") 

console = Console()
client = OpenAI(api_key=API_KEY, base_url="https://api.deepseek.com")

class MattermostBot:
    def __init__(self):
        self.driver = Driver({
            'url': MM_URL,
            'token': MM_TOKEN,
            'scheme': 'http',
            'port': MM_PORT,
            'verify': False,
            'debug': False, # Set to True if you need verbose connection logs
            'keepalive': True,
            'keepalive_delay': 5
        })
        self.mem = MemorySystem()
        self.bot_user_id = None

    def get_bot_user_id(self):
        """Fetches the bot's own user ID to ignore its own messages."""
        try:
            # Check connection first
            console.print(f"[dim]Connecting to {MM_URL}:{MM_PORT}...[/dim]")
            self.driver.login()
            
            user = self.driver.users.get_user(user_id='me')
            self.bot_user_id = user['id']
            console.print(f"[green]Bot connected as: {user['username']} ({self.bot_user_id})[/green]")
        except Exception as e:
            console.print(f"[red]Failed to get bot info: {e}[/red]")
            # If login fails, the script should probably stop/retry
            sys.exit(1)

    def think_and_reply(self, user_query, channel_id, root_id=None):
        """Processes the message using Memory + DeepSeek."""
        try:
            # 1. Memory Search
            hits = self.mem.search(user_query, limit=2)
            context = "\n".join([f"- {h['content'][:200]}" for h in hits])

            # 2. LLM Call
            prompt = f"""
            Du bist cyCoachH (über Mattermost).
            [KONTEXT]
            {context}
            [ANFRAGE]
            {user_query}
            
            Antworte prägnant. Verwende Markdown.
            """
            
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7
            )
            reply = response.choices[0].message.content

            # 3. Post Reply
            self.driver.posts.create_post({
                'channel_id': channel_id,
                'message': reply,
                'root_id': root_id or "" 
            })
            
            # 4. Log Interaction
            console.print(f"[blue]Replied to channel {channel_id}[/blue]")

        except Exception as e:
            console.print(f"[red]Error processing message: {e}[/red]")

    def message_handler(self, event):
        """Websocket Event Listener."""
        try:
            data = json.loads(event)
            
            if data.get('event') != 'posted':
                return

            post = json.loads(data['data']['post'])
            
            if post['user_id'] == self.bot_user_id:
                return

            is_dm = data['data'].get('channel_type') == 'D'
            message_text = post.get('message', '')

            if is_dm or "@cycoach" in message_text.lower():
                console.print(f"[yellow]Incoming: {message_text}[/yellow]")
                self.think_and_reply(message_text, post['channel_id'], post['id'])
        except Exception as e:
            # Prevent single message error from crashing the whole loop
            console.print(f"[red]Event Handler Error: {e}[/red]")

    def start(self):
        console.print("[bold green]Starting Mattermost Gateway...[/bold green]")
        # We call login inside get_bot_user_id, but calling it here ensures session exists
        try:
            self.get_bot_user_id()
            # This is the blocking call that keeps the script alive
            self.driver.init_websocket(self.message_handler)
        except Exception as e:
            console.print(f"[red]Websocket Crashed: {e}[/red]")

if __name__ == "__main__":
    bot = MattermostBot()
    bot.start()