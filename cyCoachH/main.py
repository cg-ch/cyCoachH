import sys
import argparse
from pathlib import Path

# Add project root to path so modules can find each other
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.append(str(PROJECT_ROOT))

def main():
    parser = argparse.ArgumentParser(description="cyCoachH Controller")
    parser.add_argument("mode", choices=["chat", "heartbeat", "ingest"], help="Mode to run the agent in")
    
    args = parser.parse_args()
    
    try:
        if args.mode == "chat":
            from adapters.terminal import start_terminal_chat
            start_terminal_chat()
            
        elif args.mode == "heartbeat":
            from heartbeat.beat import run_heartbeat
            run_heartbeat()
            
        elif args.mode == "ingest":
            from memory.ingest import MemorySystem
            mem = MemorySystem()
            mem.ingest_vault()
            
    except KeyboardInterrupt:
        sys.exit(0)
    except Exception as e:
        print(f"Critical Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()