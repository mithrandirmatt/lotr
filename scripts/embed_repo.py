import os
from pathlib import Path
import numpy as np
import faiss
from ollama import Client

repo_root = Path("/workspace/lotr")

# Gather all files in the repo (excluding hidden directories)
files = [p for p in repo_root.rglob("*.*") if p.is_file()]

embeddings = []
paths = []
for f in files:
    # Read file content safely
    try:
        text = f.read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        print(f"Skipping {f}: {e}")
        continue
    # Get embedding from Ollama
    # Connect to the host's Ollama server (Docker Desktop for Windows)
    ollama_client = Client(host="http://host.docker.internal:11434")
    emb_resp = ollama_client.embeddings(model="nomic-embed-text", prompt=text)
    embeddings.append(np.array(emb_resp["embedding"], dtype=np.float32))
    paths.append(str(f.relative_to(repo_root)))

# Build FAISS index
if not embeddings:
    raise RuntimeError("No embeddings generated – check repository path or Ollama service.")
index = faiss.IndexFlatL2(len(embeddings[0]))
index.add(np.vstack(embeddings))

# Persist artifacts in the repo root
np.save(repo_root / "repo_embeddings.npy", np.vstack(embeddings))
np.save(repo_root / "repo_paths.npy", np.array(paths, dtype=object))
faiss.write_index(index, repo_root / "repo.index")

print(f"Index built with {len(files)} files. Saved to {repo_root}")