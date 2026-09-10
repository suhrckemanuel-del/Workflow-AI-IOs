# AI-OS

A local, portable AI workflow runner for business automation.
Connect it to your knowledge base, run structured workflows,
get real outputs.

## What it does
- Runs repeatable AI workflows (research, outreach, meeting prep,
  lead scraping) with a structured reasoning layer
- Saves all outputs as markdown to an Obsidian-native knowledge base
- Keeps full run history with trust/eval scores
- Stays entirely local — no data leaves your machine except
  API calls to Anthropic and Exa

## Stack
- Backend: FastAPI + Python 3.11
- Frontend: Next.js 14 + shadcn/ui + Tailwind CSS
- Storage: SQLite + Obsidian-native markdown KB
- AI: Claude (Anthropic) + Exa (web search)

## Course Library (RAG)
Study material — lecture slides, problem sets, notes — indexed for
question answering with citations back to the page or slide.

```bash
python -m rag add ~/Downloads/Lecture_3.pdf --course "Applied Micro"
python -m rag ask "Why does a Pigouvian tax equal marginal external damage?"
python -m rag quiz "externalities" --week 2
```

See [RAG_COURSE_LIBRARY.md](RAG_COURSE_LIBRARY.md).

## Workflows
- Company Research — structured brief with live signals
- Email Drafting — outreach in your voice
- Meeting Prep — background, questions, recommended outcome
- Portfolio Monitor — weekly digest across portfolio companies
- VC Lead Finder — ranked lead table with contact routes
- VC Outreach Drafts — email + LinkedIn sequences per lead

## Quick start

### Requirements
- Python 3.11+
- Node.js 18+
- API keys: ANTHROPIC_API_KEY, EXA_API_KEY
- Windows (start.bat) or any OS (manual start)

### Setup
```bash
# 1. Clone
git clone <your-repo-url> && cd ai-os

# 2. Environment
cp .env.example .env
# Edit .env and add your API keys

# 3. Python dependencies
pip install -r requirements.txt

# 4. Frontend
cd frontend && npm install && npm run build && cd ..

# 5. Launch
start.bat
# Opens two terminal windows: backend on :8000, frontend on :3000
```

Open http://localhost:3000

### Manual launch (any OS)
```bash
# Terminal 1
uvicorn api.main:app --port 8000

# Terminal 2
cd frontend && npm run start
```

## Architecture
Next.js :3000 → FastAPI :8000 → Python core → Claude / Exa

## Notes
- All data is local. Nothing is sent except API calls to
  Anthropic and Exa.
- knowledge_base/ is your Obsidian vault — open this folder
  in Obsidian directly.
- After changing frontend code, rebuild before restarting:
  cd frontend && npm run build

## Project structure
```text
ai-os/
├── core/          # Engine, DB, registry — do not modify
├── workflows/     # Workflow modules — do not modify
├── api/           # FastAPI routes
├── frontend/      # Next.js app
├── knowledge_base/# Obsidian vault (gitignored)
├── data/          # SQLite DB (gitignored)
├── .env           # API keys (gitignored)
├── .env.example   # Key template
└── start.bat      # One-click launcher (Windows)
```
