import os
import sqlite3
import time
import json
import pickle
import numpy as np
from pathlib import Path
from typing import List, Dict, Any
from fastembed import TextEmbedding
from rank_bm25 import BM25Okapi
from rich.console import Console
from rich.table import Table

# --- Configuration ---
DB_PATH = Path("memory/db.sqlite")
VAULT_PATH = Path("memory/vault")
MODEL_NAME = "BAAI/bge-small-en-v1.5"  # Lightweight, high performance
console = Console()

class MemorySystem:
    def __init__(self):
        """Initialize DB connection and Embedding Model."""
        self.conn = sqlite3.connect(DB_PATH)
        self.conn.row_factory = sqlite3.Row
        self._init_db()
        
        console.print(f"[dim]Loading embedding model: {MODEL_NAME}...[/dim]")
        self.embedding_model = TextEmbedding(model_name=MODEL_NAME)
        
        # We load BM25 on startup for the Keyword search part
        self.bm25 = None
        self.bm25_corpus_paths = []
        self._refresh_bm25()

    def _init_db(self):
        """Create the table if it doesn't exist."""
        query = """
        CREATE TABLE IF NOT EXISTS documents (
            filepath TEXT PRIMARY KEY,
            content TEXT,
            modified_at REAL,
            embedding BLOB
        )
        """
        self.conn.execute(query)
        self.conn.commit()

    def _refresh_bm25(self):
        """Load all documents into memory to build the BM25 index."""
        cursor = self.conn.execute("SELECT filepath, content FROM documents")
        rows = cursor.fetchall()
        
        if not rows:
            return

        tokenized_corpus = [row["content"].lower().split() for row in rows]
        self.bm25 = BM25Okapi(tokenized_corpus)
        self.bm25_corpus_paths = [row["filepath"] for row in rows]

    def ingest_vault(self):
        """Scan the vault and update changed files."""
        console.print(f"[bold blue]Scanning vault at {VAULT_PATH}...[/bold blue]")
        
        changes_count = 0
        
        # 1. Walk through all Markdown files
        for file_path in VAULT_PATH.rglob("*.md"):
            # Relative path for ID (e.g., "daily/2024-01-01.md")
            rel_path = str(file_path.relative_to(VAULT_PATH))
            mtime = file_path.stat().st_mtime
            
            # Check if file needs update
            cursor = self.conn.execute(
                "SELECT modified_at FROM documents WHERE filepath = ?", (rel_path,)
            )
            row = cursor.fetchone()
            
            if row and row["modified_at"] == mtime:
                continue  # Skip if unchanged

            # 2. Read and Embed
            try:
                content = file_path.read_text(encoding="utf-8")
                if not content.strip():
                    continue

                console.print(f"Ingesting: [green]{rel_path}[/green]")
                
                # fastembed returns a generator, get the first item
                embedding_gen = self.embedding_model.embed([content])
                embedding = list(embedding_gen)[0] # numpy array
                
                # Store as binary pickle
                embedding_blob = pickle.dumps(embedding)

                # 3. Upsert into DB
                self.conn.execute(
                    """
                    INSERT OR REPLACE INTO documents (filepath, content, modified_at, embedding)
                    VALUES (?, ?, ?, ?)
                    """,
                    (rel_path, content, mtime, embedding_blob)
                )
                changes_count += 1
            except Exception as e:
                console.print(f"[red]Error processing {rel_path}: {e}[/red]")

        self.conn.commit()
        
        if changes_count > 0:
            console.print(f"[bold green]Updated {changes_count} documents.[/bold green]")
            self._refresh_bm25() # Rebuild BM25 index with new data
        else:
            console.print("[dim]No changes detected.[/dim]")

    def search(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Hybrid Search:
        0.7 * Vector Similarity + 0.3 * BM25 Keyword Score
        """
        if not self.bm25:
            console.print("[yellow]Warning: Database is empty.[/yellow]")
            return []

        # 1. Get Vector Scores
        query_embedding = list(self.embedding_model.embed([query]))[0]
        
        cursor = self.conn.execute("SELECT filepath, content, embedding FROM documents")
        rows = cursor.fetchall()
        
        results = []
        
        # 2. Calculate Scores
        # Note: For massive DBs, do this in SQL (sqlite-vec) or vector DB. 
        # For local usage (<10k files), Python loop is fast enough.
        
        # Get BM25 scores for all docs
        tokenized_query = query.lower().split()
        bm25_scores = self.bm25.get_scores(tokenized_query)
        
        # Normalize BM25 scores (0 to 1) to match Vector Cosine range
        if max(bm25_scores) > 0:
            bm25_scores = bm25_scores / max(bm25_scores)
            
        for idx, row in enumerate(rows):
            # Deserialize vector
            doc_vec = pickle.loads(row["embedding"])
            
            # Cosine Similarity (Dot product for normalized vectors)
            # FastEmbed vectors are normalized by default
            vec_score = np.dot(query_embedding, doc_vec)
            
            keyword_score = bm25_scores[idx]
            
            # HYBRID WEIGHTING
            final_score = (0.7 * vec_score) + (0.3 * keyword_score)
            
            results.append({
                "filepath": row["filepath"],
                "content": row["content"],
                "score": final_score,
                "type": "hybrid"
            })

        # 3. Sort and limit
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:limit]

# --- CLI for Testing ---
if __name__ == "__main__":
    mem = MemorySystem()
    
    # 1. Run Ingestion
    mem.ingest_vault()
    
    # 2. Test Search Interaction
    while True:
        try:
            user_query = input("\n🔍 Search Memory (Ctrl+C to exit): ")
            if not user_query.strip(): continue
            
            hits = mem.search(user_query)
            
            table = Table(title=f"Results for: {user_query}")
            table.add_column("Score", justify="right", style="cyan", no_wrap=True)
            table.add_column("File", style="magenta")
            table.add_column("Snippet", style="white")

            for hit in hits:
                snippet = hit["content"][:100].replace("\n", " ") + "..."
                table.add_row(f"{hit['score']:.4f}", hit["filepath"], snippet)
            
            console.print(table)
            
        except KeyboardInterrupt:
            print("\nExiting.")
            break