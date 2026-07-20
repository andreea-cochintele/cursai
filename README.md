

Readme · MD
# Wizzard of OS
 
A RAG-powered Linux sysadmin chatbot, built on Azure AI Foundry, with tool-calling and a minimal web chat UI.
 
## Features
 
- **Chat over HTTP** (FastAPI) or **CLI** — same agent, two front ends.
- **RAG**: internal knowledge base (company facts, support procedures) is chunked, embedded, and retrieved by semantic search on every message.
- **Tool calling**: the model can call read-only diagnostic tools (see below) instead of guessing.
- **Session persistence**: conversations are saved to disk as JSON and can be resumed, listed, and exported to Markdown.
- **Web UI**: single-file chat page (`static/index.html`) with quick-action chips, session browser, and live token/cost stats.
## Project structure
 
```
.
├── app.py                     # FastAPI app (web API + serves the chat page)
├── main.py                    # CLI entry point
├── agent.py                   # Orchestrates RAG + tool calls + LLM turns
├── llm_client.py               # Talks to the chat model (Azure AI Foundry via OpenAI SDK)
├── embeddings_client.py       # Talks to the embeddings deployment + cosine similarity search
├── embedding_generator.py     # Builds embeddings.json from the knowledge base (once)
├── document_chunker.py        # Splits knowledge base docs into chunks for embedding
├── conversation_context.py    # Message history, system prompt assembly, context compression
├── session_manager.py         # One Agent per session_id, for the web API
├── utils.py                   # Token counting (tiktoken)
├── config.py                  # Your local config — NOT committed, see Setup
├── config_example.py          # Template for config.py
├── requirements.txt
├── static/
│   └── index.html             # The web chat UI
├── tools/
│   ├── tool.py                 # Base Tool class
│   ├── tools.py                 # Registry — add new tools here
│   ├── lucky_number_tool.py
│   ├── service_status_tool.py   # Windows service status (PowerShell)
│   ├── service_logs_tool.py     # Windows Event Log lookup (PowerShell)
│   └── disk_usage_tool.py       # Disk space usage (PowerShell)
├── knowledge/
│   ├── prompts/identity.md      # The system prompt (persona, scope, rules)
│   ├── facts/                   # always_load:true docs (always in the system prompt)
│   └── procedures/              # always_load:false docs (retrieved via RAG)
├── embeddings.json            # Generated vector DB (gitignore this — regenerated on first run)
└── sessions/                  # Saved conversations, one JSON file per session_id (auto-created)
```
 
## Setup
 
### 1. Create a virtual environment
 
```bash
python3 -m venv .venv
source .venv/bin/activate          # Linux/macOS/WSL
# .venv\Scripts\activate           # Windows cmd/PowerShell
```
 
> **WSL users:** create the venv on the native Linux filesystem (e.g. `~/projects/...`), not under `/mnt/c/...`. Venvs on the Windows-mounted filesystem are unreliable — pip installs can silently land outside the venv ("Defaulting to user installation because normal site-packages is not writeable").
 
### 2. Install dependencies
 
```bash
pip install -r requirements.txt
```
 
> If you hit `error: externally-managed-environment` (PEP 668) even inside an active venv, check `.venv/pyvenv.cfg` for `include-system-site-packages`. As a last resort inside a venv (never on system Python): `pip install --break-system-packages -r requirements.txt`.
 
### 3. Configure
 
```bash
cp config_example.py config.py
```
 
Edit `config.py`:
 
| Setting | Description |
|---|---|
| `PROVIDER` | `"azure"` or `"ollama"` — picks which profile below is active. See section 3b for details. |
| `_PROFILES["azure"/"ollama"]["endpoint"]` | Base URL for the chat/embeddings API |
| `_PROFILES[...]["api_key"]` | API key (Azure) or a dummy string (Ollama ignores it) |
| `_PROFILES[...]["model_name"]` | Chat model/deployment name |
| `_PROFILES[...]["embeddings_model"]` | Embeddings model/deployment name (must be separate from the chat model) |
| `_PROFILES[...]["token_limit_param"]` | `"max_completion_tokens"` (Azure) or `"max_tokens"` (Ollama) — don't change unless you know why |
| `MIN_SIMILARITY` | Cosine similarity threshold for RAG matches (0–1) |
| `MAX_CONTEXT_TOKENS` / `KEEP_RECENT_MESSAGES` | Context window management |
| `INPUT_TOKEN_PRICE_PER_MILLION` / `OUTPUT_TOKEN_PRICE_PER_MILLION` | For the cost estimate shown in stats |
 
`config.py` is your local secrets file — don't commit it.
 
### 3b. Switching between Azure and Ollama
 
`config_example.py` supports both providers side by side. Switching is a **single line**:
 
```python
PROVIDER = "azure"   # or "ollama"
```
 
- **`"azure"`** — for people who have an Azure AI Foundry subscription/API key. Fill in the `"azure"` profile block in `config_example.py`/`config.py` with your real endpoint, key, and deployment names.
- **`"ollama"`** — free, fully local, no API key needed. One-time setup:
```bash
  curl -fsSL https://ollama.com/install.sh | sh
  ollama pull qwen3:1.7b        # small, tool-calling-capable chat model (~1.4 GB)
  ollama pull nomic-embed-text  # an embeddings model
  ollama serve                  # keep this running in a terminal
```
  The `"ollama"` profile block already has sensible defaults (`qwen3:1.7b` / `nomic-embed-text`) — just make sure you've pulled those two models, or change the names to match whatever you pulled. `qwen3:1.7b` was chosen as the default over larger models like `llama3.1` (~4.9 GB) specifically because it's small enough to fit when disk space is tight, while still supporting tool calling — check what a model supports with `ollama show <model>` (look for `tools` under capabilities) before relying on it for this project.
 
This works because Ollama exposes an **OpenAI-compatible API** at `http://localhost:11434/v1`, and both `llm_client.py` and `embeddings_client.py` already talk to whichever endpoint the active profile sets, through the standard `openai` SDK — no code changes needed to switch. If `PROVIDER` is misspelled or set to something undefined, `config.py` raises a clear error immediately on startup instead of failing confusingly later.
 
The one real code-level difference between providers, already handled for you: `TOKEN_LIMIT_PARAM`. Azure/OpenAI's newer models expect `max_completion_tokens`; Ollama's compatibility layer expects the older `max_tokens`. `llm_client.py` reads whichever name the active profile sets — you never need to touch it.
 
**Caveats:**
- Delete `embeddings.json` after switching providers — vectors from one embedding model aren't compatible with another.
- Tool calling (the `service_status`/`service_logs`/`disk_usage`/`lucky_number` tools) needs a model that actually supports it. `qwen3:1.7b`, `llama3.1`, `qwen2.5`, and `mistral-nemo` are known to work; smaller/older models may just silently ignore the `tools` field and never call anything. Even among tool-calling-capable models, smaller ones (like `qwen3:1.7b`) can be less reliable on ambiguous input — e.g. asking to check a service status without giving a name may cause the model to invent a made-up service name and answer in plain text instead of asking for clarification or calling the tool with missing arguments. Larger models handle this more gracefully; for a course/demo project it's a reasonable tradeoff for the disk space and speed you save.

## Running
 
**Web (recommended):**
```bash
uvicorn app:app --reload
```
Open `http://127.0.0.1:8000/` for the chat UI, or `http://127.0.0.1:8000/docs` for the API reference.
 
**CLI:**
```bash
python main.py
```
 
On first run, both entry points build `embeddings.json` from the `knowledge/` folder (skipped on later runs if the file already exists — delete it to force a rebuild after editing knowledge docs).
 
## API endpoints
 
| Method | Path | Description |
|---|---|---|
| `GET` | `/` | Chat UI |
| `POST` | `/chat` | `{session_id, message}` → `{session_id, reply}` |
| `GET` | `/sessions` | Lists saved (disk) and active (in-memory) sessions |
| `GET` | `/sessions/{id}/history` | User/assistant messages for a session |
| `GET` | `/sessions/{id}/stats` | Token usage + estimated cost |
| `GET` | `/sessions/{id}/export` | Downloads the session as Markdown |
| `GET` | `/health` | Liveness check |
 
## Tools
 
All tools are **read-only** — they inspect the system but never restart, stop, or modify anything. They currently run **PowerShell commands on the Windows machine hosting the bot** (there's no Linux host in this setup); if you later get SSH access to a real Linux server, `service_status`/`service_logs`/`disk_usage` are the ones to adapt (swap `subprocess` for an SSH-based call).
 
| Tool | What it does |
|---|---|
| `lucky_number` | Deterministic novelty number from today's date + a birth date. Not a sysadmin tool — kept as a scope/permission test case. |
| `service_status` | `Get-Service` — is a Windows service running, stopped, what's its startup type. |
| `service_logs` | `Get-WinEvent` — recent System/Application log entries mentioning a service. |
| `disk_usage` | `Get-PSDrive` — used/free space per drive. |
 
To add a new tool: create `tools/your_tool.py` following the pattern in `tools/lucky_number_tool.py` (a `Tool(name, description, parameters, callback)` instance), then import and register it in `tools/tools.py`.
 
**Chained tool calls:** `agent.py` loops while the model keeps requesting tools (up to `MAX_TOOL_ITERATIONS = 5`), so it can, for example, check a service's status, see it's failed, and check its logs next — all in one turn — instead of being limited to a single tool call per message. A tool that raises an unexpected exception no longer crashes the whole request; the model just sees a clear failure message for that one tool and can still finish answering with whatever else it knows.
 
**Small models and tool calling:** not every Ollama model that *supports* tool calling uses it *reliably*. Smaller models (e.g. `qwen3:1.7b`) can sometimes invent a plausible-looking answer in plain text instead of calling a tool or asking for a missing parameter — e.g. asked to check a service status with no service name given, it might make one up rather than call `service_status` with an empty argument (which would get a clean validation error) or ask "which service?". This isn't a bug in the tool code; it's a limitation of small-model instruction-following. Larger models are more consistent here.
 
## Knowledge base / RAG
 
- `knowledge/prompts/identity.md` — the system prompt: persona, scope rules (what the bot will/won't answer), style, safety rules. Always sent in full.
- `knowledge/facts/*.md` + `registry.json` — docs with `always_load: true` are always injected into the system prompt (no retrieval needed).
- `knowledge/procedures/*.md` + `registry.json` — docs with `always_load: false` are chunked, embedded, and retrieved via semantic search per message.
To add a knowledge doc: drop a `.md` file in the right folder and add an entry to that folder's `registry.json` with a matching `id`. Delete `embeddings.json` afterwards so it gets rebuilt with the new content.
 
**Chunking:** `document_chunker.py` splits documents into `CHUNK_SIZE`-word chunks (default 150), advancing by `CHUNK_SIZE - CHUNK_OVERLAP` words each step (default overlap: 30) so a sentence that falls right on a chunk boundary still appears whole in at least one chunk, instead of being split in half across two chunks that individually might not be similar enough to a query to get retrieved.
 
**Retrieval tuning:** `RAG_TOP_K` (default 3) controls how many chunks come back per query. `MIN_SIMILARITY` is set *per provider* in `config.py` (0.55 for Azure, 0.45 for Ollama by default) because different embedding models produce different similarity score distributions — if RAG stops finding matches after switching providers, this is the first thing to re-tune, by checking what similarity scores your actual knowledge base docs get against real queries.
 
## Logging
 
All internal diagnostics (RAG misses, LLM/embeddings errors, context compression, tool failures) go through Python's standard `logging` module, not `print()` — set up once via `logging_config.py`'s `setup_logging()`, called from both `app.py` and `main.py`. Every log line is timestamped and tagged with its source module (`agent`, `conversation_context`, `embeddings_client`, etc.), and unexpected exceptions are logged with `logger.exception(...)`, which auto-attaches the full traceback. To see more/less detail, adjust the `level` passed to `setup_logging()`.
 
## Known limitations
 
- **Tools are Windows-only right now.** The persona talks about Linux, but `service_status`/`service_logs`/`disk_usage` run PowerShell against the host machine. There's no real Linux target in this setup.
- **Embeddings need their own Azure deployment.** `EMBEDDINGS_MODEL` in `config.py` must point to an actual embeddings deployment (e.g. `text-embedding-3-large`) — it's a different deployment type than the chat model.
- **No authentication** on the API — fine for local/course use, not production-ready as-is.
- **In-memory session cache** in `session_manager.py` grows for as long as the process runs — nothing currently evicts old sessions from `SessionManager._agents`, so a long-running server with many distinct `session_id`s will accumulate memory over time (they're still recoverable from `sessions/*.json` on disk if the process restarts, just not automatically freed while it's running).
- **No rate limiting or per-user quotas** — nothing currently prevents rapid repeated requests from driving up cost (on a hosted provider) or load.
## Troubleshooting quick reference
 
| Symptom | Likely cause |
|---|---|
| `ModuleNotFoundError: No module named 'config'` | You haven't copied `config.example.py` to `config.py` |
| `TypeError: 'NoneType' object can't be awaited` | A function that should be `async def` still isn't, somewhere in the call chain (check `llm_client.py`, `embeddings_client.py`, `conversation_context.py`, `agent.py`) |
| `404` on `http://127.0.0.1:8000/` | Check you're on the latest `app.py` — it serves `static/index.html` at `/` |
| `externally-managed-environment` on `pip install` | See Setup step 2 above |


