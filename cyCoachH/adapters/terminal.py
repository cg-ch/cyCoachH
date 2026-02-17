import sys
import os
from datetime import datetime
from pathlib import Path
from rich.console import Console
from rich.markdown import Markdown
from rich.prompt import Prompt
from rich.panel import Panel
from dotenv import load_dotenv
from openai import OpenAI

# --- Path Setup ---
# Get the absolute path to the project root (cyCoachH/)
# adapter/terminal.py -> parent -> parent = root
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
BASE_URL = "https://api.deepseek.com"

console = Console()
client = OpenAI(api_key=API_KEY, base_url=BASE_URL)

def save_interaction(user_input, agent_response):
    """Appends the conversation to today's daily note."""
    today = datetime.now().strftime("%Y-%m-%d")
    daily_path = PROJECT_ROOT / "memory/vault/daily" / f"{today}.md"
    
    # Ensure directory exists
    daily_path.parent.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%H:%M")
    
    # Format suitable for Markdown reading
    entry = f"\n\n### Chat [{timestamp}]\n**User:** {user_input}\n\n**cyCoachH:**\n{agent_response}\n"
    
    try:
        with open(daily_path, "a", encoding="utf-8") as f:
            f.write(entry)
    except Exception as e:
        console.print(f"[red]Failed to auto-journal: {e}[/red]")

def start_terminal_chat():
    mem = MemorySystem()
    
    console.clear()
    console.print(Panel.fit("[bold green]cyCoachH Terminal Interface[/bold green]\n[dim]Model: DeepSeek V3 | Memory: Local Hybrid[/dim]"))
    console.print("[dim]Type 'exit', 'quit', or 'bye' to leave.[/dim]\n")

    while True:
        try:
            user_input = Prompt.ask("[bold cyan]You[/bold cyan]")
            
            if user_input.lower() in ["exit", "quit", "bye"]:
                console.print("[yellow]Session ended.[/yellow]")
                break
                
            if not user_input.strip():
                continue

            with console.status("[bold green]Thinking...[/bold green]", spinner="dots"):
                # 1. Search Memory (The "RAG" part)
                hits = mem.search(user_input, limit=3)
                context_str = "\n".join([f"- {h['content'][:300]}" for h in hits])
                
                # 2. Ask DeepSeek
                system_prompt = f"""
                You are cyCoachH, a helpful, precise assistant on a Debian Linux system.
                
                [RELEVANT MEMORY]
                {context_str}
                
                [INSTRUCTION]
                Answer the user's query. Be concise. If the memory provides specific details, cite them.
                """
                
                response = client.chat.completions.create(
                    model="deepseek-chat",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_input}
                    ],
                    temperature=0.7
                )
                
                reply = response.choices[0].message.content
                
                # 3. Display
                console.print(f"\n[bold magenta]cyCoachH:[/bold magenta]")
                console.print(Markdown(reply))
                console.print("\n" + "-"*30)
                
                # 4. Auto-Journal
                save_interaction(user_input, reply)

        except KeyboardInterrupt:
            console.print("\n[yellow]Interrupted. Exiting.[/yellow]")
            break
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")

if __name__ == "__main__":
    start_terminal_chat()