"""Diagnostic: token math + ColBERT truncation analysis + host resources.

Run from WSL2 venv:
    python results/diag-tokens.py
"""

import json
import os
from pathlib import Path

from colbert.infra import ColBERTConfig
from transformers import AutoTokenizer
import psutil

cfg = ColBERTConfig()
print("ColBERTv2 defaults:")
print(f"  doc_maxlen   = {cfg.doc_maxlen} tokens")
print(f"  query_maxlen = {cfg.query_maxlen} tokens")
print(f"  bsize        = {cfg.bsize}  (ColBERTConfig default; our query-time docFromText uses 8)")
print(f"  dim          = {cfg.dim}")
print()

tok = AutoTokenizer.from_pretrained("colbert-ir/colbertv2.0")

idx_dir = Path.home() / ".optimus-spike" / "index-msrepo"
chunks_jsonl = idx_dir / "chunks.jsonl"

print("Sampled chunks (ColBERTv2 tokenizer):")
SAMPLE_IDS = {0, 100, 1000, 2000, 3000, 3417}
with chunks_jsonl.open() as f:
    for line in f:
        s = json.loads(line)
        if s["chunk_id"] not in SAMPLE_IDS:
            continue
        token_ids = tok(s["text"], add_special_tokens=True)["input_ids"]
        chars = len(s["text"])
        tokens = len(token_ids)
        bytes_len = len(s["text"].encode("utf-8"))
        truncated = max(0, tokens - cfg.doc_maxlen)
        cid = s["chunk_id"]
        print(f"  cid={cid:5d}  chars={chars:5d}  tokens={tokens:5d}  bytes={bytes_len:5d}  trunc_at_colbert={truncated:4d}")

print()
print("Aggregate across all chunks:")
total_chars = total_tokens = total_bytes = trunc_total = chunks_truncated = 0
n = 0
with chunks_jsonl.open() as f:
    for line in f:
        s = json.loads(line)
        token_ids = tok(s["text"], add_special_tokens=True)["input_ids"]
        chars = len(s["text"])
        tokens = len(token_ids)
        bytes_len = len(s["text"].encode("utf-8"))
        total_chars += chars
        total_tokens += tokens
        total_bytes += bytes_len
        if tokens > cfg.doc_maxlen:
            chunks_truncated += 1
            trunc_total += tokens - cfg.doc_maxlen
        n += 1

print(f"  total chunks        = {n}")
print(f"  mean chars/chunk    = {total_chars / n:.1f}")
print(f"  mean tokens/chunk   = {total_tokens / n:.1f}")
print(f"  mean bytes/chunk    = {total_bytes / n:.1f}")
print(f"  chars per token     = {total_chars / total_tokens:.2f}")
print(f"  chunks truncated at ColBERT rerank: {chunks_truncated} / {n} ({100*chunks_truncated/n:.1f}%)")
print(f"  total tokens DISCARDED at rerank:   {trunc_total:,} ({100*trunc_total/total_tokens:.1f}% of all tokens)")

print()
print("Host (WSL2) resources:")
print(f"  CPU count (os.cpu_count): {os.cpu_count()}")
print(f"  RAM total (GB):          {psutil.virtual_memory().total / 1e9:.1f}")
print(f"  RAM available (GB):      {psutil.virtual_memory().available / 1e9:.1f}")
