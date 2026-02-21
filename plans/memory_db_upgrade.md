# Memory Database Upgrade Plan

## Current Limitations

1. **English‑language embeddings** – The vault has been translated to German, but the existing SQLite database contains embeddings of the original English text.
2. **No chunking** – Each Markdown file is embedded as a single unit; large files (e.g., `SYSTEM.md`) likely exceed the embedding model’s token limit (512 tokens for `BAAI/bge‑small‑en‑v1.5`), causing truncation and loss of information.
3. **Minimal metadata** – The `documents` table only stores `filepath`, `content`, `modified_at`, and `embedding`. There is no way to filter by document type or chunk index.
4. **Linear vector search** – Similarity is computed by iterating over all rows; this is fine for small corpora (<1000 documents) but will not scale.
5. **BM25 index rebuilt on every ingestion** – The entire corpus is reloaded into memory for keyword scoring; this is acceptable for the current volume.

## Upgrade Objectives

1. **Reset and re‑ingest** – Start from a clean database with the German‑language vault.
2. **Introduce chunking** – Split large Markdown files into semantically coherent chunks (based on headings) to stay within the model’s token limit and improve retrieval precision.
3. **Enrich metadata** – Add columns for document type, chunk index, token count, and ingestion timestamp to support filtering and debugging.
4. **Preserve hybrid search** – Maintain the existing 70% vector / 30% BM25 scoring but apply it at the chunk level.
5. **Keep migration simple** – Provide a one‑time migration script that backs up the old database, creates a new schema, and ingests the current vault.
6. **Incorporate all historical daily logs** – Ensure every Markdown file in `memory/vault/daily/` is ingested.

## New Schema

```sql
CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filepath TEXT NOT NULL,               -- relative path from vault/ (e.g., 'daily/2026‑02‑17.md')
    chunk_index INTEGER NOT NULL,         -- 0‑based index of this chunk within the file
    chunk_total INTEGER NOT NULL,         -- total number of chunks in the file
    content TEXT NOT NULL,                -- the text of this chunk
    modified_at REAL NOT NULL,            -- modification time of the source file (seconds since epoch)
    embedding BLOB,                       -- pickle‑serialized numpy array (384‑dimensional vector)
    doc_type TEXT NOT NULL,               -- 'system', 'soul', 'user', or 'daily'
    token_count INTEGER,                  -- approximate token count (for monitoring)
    ingested_at REAL NOT NULL,            -- timestamp when this chunk was added
    UNIQUE(filepath, chunk_index)
);
```

**Indices:**
- `CREATE INDEX idx_doc_type ON documents(doc_type);`
- `CREATE INDEX idx_modified ON documents(modified_at);`

## Chunking Strategy

### Rules
- Split only files larger than 500 tokens (estimated). Small files remain a single chunk.
- Use Markdown headings (`##` and `###`) as natural split points.
- Keep chunk size between 200 and 800 tokens (soft limits).
- Overlap: add the previous heading line to each chunk for context (optional).
- Preserve the original Markdown formatting within each chunk.

### Algorithm (pseudocode)
```
for each .md file in vault:
    text = read_file(file)
    if estimated_tokens(text) <= 500:
        chunks = [text]
    else:
        chunks = []
        lines = text.splitlines()
        current_chunk = []
        for line in lines:
            if line.startswith('##') and len(current_chunk) > 0:
                # finalize previous chunk
                chunks.append('\n'.join(current_chunk))
                current_chunk = [line]
            else:
                current_chunk.append(line)
        if current_chunk:
            chunks.append('\n'.join(current_chunk))
    for i, chunk in enumerate(chunks):
        store_chunk(file, i, len(chunks), chunk)
```

## Ingestion Logic

1. **Detect changes** – Compare file modification times with `modified_at` in the database (using `filepath` and `chunk_index`). If the file hasn’t changed, skip it.
2. **Delete stale chunks** – If a file has fewer chunks than before, remove the extra chunks from the database.
3. **Compute embeddings** – Use the same FastEmbed model (`BAAI/bge‑small‑en‑v1.5`) to embed each chunk individually.
4. **Update BM25 corpus** – After all inserts/deletes, rebuild the in‑memory BM25 index with the `content` of every chunk.

## Search Modifications

The `MemorySystem.search()` method must be updated to:

- Retrieve chunks instead of whole files.
- Calculate BM25 scores per chunk (the existing BM25 implementation already works on the corpus of chunks).
- Compute vector similarity per chunk.
- Combine scores with the same weighting (0.7 vector + 0.3 BM25).
- Return the top‑k chunks, each with its own `filepath`, `chunk_index`, `content`, and `score`.

The existing adapter code expects a list of dictionaries with `filepath` and `content`; this will continue to work because we will keep the same dictionary keys (the `content` will be the chunk text). If needed, we can add a `chunk_index` field for debugging.

## Migration Steps

1. **Backup** – Rename `memory/db.sqlite` to `memory/db.sqlite.backup‑<timestamp>`.
2. **Schema creation** – The `MemorySystem` class will create the new table automatically on initialization (via `_init_db`).
3. **Re‑ingestion** – Run `MemorySystem().ingest_vault()` (or a dedicated migration script) to populate the new database from the German vault.
4. **Verification** – Run a few sample searches and compare results with the old database (optional).
5. **Cleanup** – After successful verification, the backup can be archived or deleted.

## Integration of Historical Daily Logs

- The vault’s `daily/` directory already contains all past logs as Markdown files.
- The ingestion process will pick them up automatically.
- No extra steps are required unless there are logs outside the vault (e.g., in other formats). In that case a separate conversion step would be needed, but this is out of scope.

## Testing and Validation

1. **Unit tests** for the chunking logic (edge cases: empty files, files without headings, very large files).
2. **Integration test** that ingests a small test vault and verifies that search returns expected chunks.
3. **Regression test** – Ensure the adapters (terminal, Mattermost, heartbeat) still work with the new search results.
4. **Performance check** – Time ingestion and search with the full vault to confirm no significant degradation.

## Implementation Plan

### Phase 1: Chunking and Schema (Non‑breaking)
- Modify `ingest.py` to support chunking, but keep the old table structure (add new columns as optional). This allows incremental development.
- Write chunking utility functions and tests.

### Phase 2: Search Adaptation
- Update `search()` to work with chunks, maintaining backward compatibility (return chunks as if they were documents).
- Adjust BM25 corpus to be chunk‑based.

### Phase 3: Migration Script
- Create a standalone script `memory/migrate.py` that performs backup, schema migration, and re‑ingestion.
- Document the process in `README.md`.

### Phase 4: Validation
- Run the migration on a copy of the production vault and verify correctness.
- Deploy by running the migration script manually.

## Risks and Mitigations

- **Token‑count estimation** – Simple heuristics (words × 1.3) may be inaccurate. Use the Hugging Face tokenizer for the exact model if needed.
- **Chunk boundaries** – Splitting only at headings may produce uneven chunks. Fallback: split by paragraph when a chunk grows too large.
- **Increased database size** – More rows will slightly slow down linear vector search. Acceptable for now; can be optimized later with a vector index.
- **BM25 memory** – Storing all chunk texts in memory may increase RAM usage. With expected <1000 chunks this is negligible.

## Future Enhancements (Out of Scope)

- **Vector index** – Integrate `sqlite‑vec` or `chroma` for faster similarity search.
- **Multilingual embeddings** – Switch to a multilingual model (e.g., `BAAI/bge‑small‑en‑v1.5` is English‑only; consider `BAAI/bge‑small‑zh‑en‑v1.5` for German). However, the current model still works reasonably well for German.
- **Advanced metadata** – Add tags, authorship, and confidence scores.
- **Incremental embedding updates** – Only re‑embed chunks whose content changed (requires diffing).

## Conclusion

The proposed upgrade addresses the immediate need for German‑language embeddings and introduces chunking to improve retrieval quality. The changes are backward‑compatible and can be implemented in a few focused phases, with minimal disruption to the running system.