# AI-OS v2 — Engineering Plan

> This is the master build plan. Read this at the start of every session. Update the status column as phases complete.

---

## Vision
Rebuild AI-OS from a Streamlit prototype into a production-grade, portable automation framework:
- **Next.js + shadcn/ui** frontend (replaces Streamlit)
- **FastAPI** wrapper over the existing Python engine
- **Obsidian** as the knowledge base (point vault at `knowledge_base/`)
- **Multi-client** isolation (one repo, many clients)
- **GitHub-portable** — clone to any PC, works in 5 minutes

**Core principle:** The Python backend (engine, DB, registry, workflows) is production-quality and stays UNCHANGED. Only the frontend is being replaced.

---

## Architecture

```
Next.js (port 3000)  →  FastAPI (port 8000)  →  Python core (unchanged)
     frontend                  api/                  core/ + workflows/
```

**New folder structure (restructure in place):**
```
ai-os/
├── core/              ← UNCHANGED
├── workflows/         ← UNCHANGED
├── knowledge_base/    ← UNCHANGED (also = Obsidian vault)
├── data/aios.db       ← UNCHANGED
├── api/               ← NEW: FastAPI layer
│   ├── main.py
│   ├── models.py
│   └── routes/
│       ├── workflows.py
│       ├── history.py
│       ├── knowledge_base.py
│       ├── architect.py
│       └── settings.py
├── frontend/          ← NEW: Next.js 14 + shadcn/ui
│   ├── src/app/       ← 6 pages
│   ├── src/components/
│   ├── src/lib/api.ts
│   └── src/lib/types.ts
├── clients/           ← NEW: multi-client isolation
│   └── [client_id]/
│       ├── knowledge_base/
│       └── client.json
├── archive/
│   └── dashboard_v1.py   ← archived Streamlit app
└── ENGINEERING_PLAN.md
```

---

## Design Tokens (v2 Visual Identity)

| Token | Value |
|---|---|
| Background | `#09090B` zinc-950 |
| Surface | `#18181B` zinc-900 |
| Border | `#27272A` zinc-800 |
| Text primary | `#FAFAFA` zinc-50 |
| Text muted | `#71717A` zinc-500 |
| Accent | `#7C3AED` violet-700 |
| Font sans | Inter |
| Font mono | JetBrains Mono |

UI/UX Pro Max skill installed at `.claude/skills/ui-ux-pro-max/` — use it for design decisions.

---

## Session Map

| # | Phase | Status | Goal | End State |
|---|---|---|---|---|
| 1 | FastAPI backend | ✅ DONE | Build API layer over existing engine | `GET /api/workflows` returns 4 workflows |
| 2 | Next.js scaffold | ✅ DONE | Project setup, typed API client | `npm run dev` works, API calls succeed |
| 3 | Home + Workflow Runner | ✅ DONE | Core pages, dynamic form rendering | Can run a workflow from the browser |
| 4 | History + KB + Settings | ✅ DONE | Remaining pages | All 6 pages functional |
| 5 | Architect page | ✅ DONE | Chat UI + YAML deploy | Can build custom workflows from UI |
| 6 | Streaming + Polish | ✅ DONE | SSE, skeletons, toasts, Obsidian deep links | Feels like a real product |
| 7 | Multi-client | ✅ DONE | Client switcher, isolated KB | Client workspaces are isolated |
| 8 | Production + GitHub | ✅ DONE | Setup script, README, clone-to-run | Public clonable repo |

---

## Phase 1 — FastAPI Backend

**Files to create:**

### `api/__init__.py`
Empty.

### `api/main.py`
```python
# FastAPI app
# CORS: allow localhost:3000 and localhost:3001
# Startup: init_db(), discover_workflows()
# Include all routers with /api prefix
# Run on port 8000
```

### `api/models.py`
Pydantic models mirroring the existing dataclasses:
- `WorkflowInputSpec` — mirrors WorkflowInput dataclass
- `WorkflowMetaResponse` — id, name, icon, description, order, inputs, primary_display_field, stats_label
- `RunWorkflowRequest` — `{inputs: dict}`
- `RunResponse` — `{status, result, duration_seconds, run_id, error}`
- `RunRecord` — mirrors the `runs` table row
- `ArchitectChatRequest` — `{message: str, history: list}`
- `ArchitectChatResponse` — `{reply: str, yaml_detected: bool, yaml_content: str | None}`
- `KBDirectory` — `{folders: dict[str, list[str]]}`
- `KBFile` — `{folder, filename, content, modified_at}`

### `api/routes/workflows.py`
```
GET  /api/workflows              → list[WorkflowMetaResponse]
GET  /api/workflows/{id}         → WorkflowMetaResponse
POST /api/workflows/{id}/run     → RunResponse
GET  /api/workflows/{id}/run/stream  → SSE (phase 6)
```

### `api/routes/history.py`
```
GET  /api/runs                   → list[RunRecord] (?workflow_id, ?limit, ?offset)
GET  /api/runs/{id}              → RunRecord
```

### `api/routes/knowledge_base.py`
```
GET  /api/kb                     → KBDirectory
GET  /api/kb/{folder}/{filename} → KBFile
```

### `api/routes/architect.py`
```
POST /api/architect/chat         → ArchitectChatResponse
POST /api/architect/deploy       → {success: bool, workflow_id: str}
```

### `api/routes/settings.py`
```
GET  /api/settings               → {sender_name, api_status}
PUT  /api/settings               → {key, value}
GET  /api/health                 → health check dict (reuse scripts/health_check.py)
```

**Add to `requirements.txt`:**
```
fastapi>=0.115.0
uvicorn[standard]>=0.30.0
python-multipart>=0.0.9
```

**Start command:** `uvicorn api.main:app --reload --port 8000` (run from `ai-os/`)

**Verify Phase 1:**
```bash
curl http://localhost:8000/api/workflows
curl http://localhost:8000/api/health
curl -X POST http://localhost:8000/api/workflows/company_research/run \
  -H "Content-Type: application/json" \
  -d '{"inputs": {"company_name": "Stripe", "sector": "fintech"}}'
```

---

## Phase 2 — Next.js Scaffold

**Commands:**
```bash
cd ai-os
npx create-next-app@14 frontend --typescript --tailwind --app --src-dir
cd frontend
npx shadcn-ui@latest init
npx shadcn-ui@latest add button card badge input textarea select separator scroll-area skeleton sonner
npm install react-markdown remark-gfm swr lucide-react
```

**Key files:**

`frontend/src/lib/types.ts` — TypeScript interfaces matching `api/models.py` exactly.

`frontend/src/lib/api.ts` — All fetch functions:
```typescript
export async function getWorkflows(): Promise<WorkflowMeta[]>
export async function runWorkflow(id: string, inputs: Record<string, unknown>): Promise<RunResponse>
export async function getRuns(params?: {workflow_id?: string, limit?: number}): Promise<RunRecord[]>
export async function getKBFolders(): Promise<KBDirectory>
export async function getKBFile(folder: string, filename: string): Promise<KBFile>
export async function architectChat(message: string, history: ChatMessage[]): Promise<ArchitectResponse>
export async function deployWorkflow(yaml: string, id: string): Promise<{success: boolean}>
export async function getSettings(): Promise<Settings>
export async function updateSetting(key: string, value: unknown): Promise<void>
```

`frontend/next.config.ts` — Proxy `/api/*` → `http://localhost:8000/api/*` (eliminates CORS in dev).

`frontend/.env.local`:
```
NEXT_PUBLIC_API_URL=http://localhost:8000
```

---

## Phase 3 — UI Pages

**6 pages to build:**

| Page | Route | Key Components |
|---|---|---|
| Home | `/` | WorkflowCard grid, RecentRuns feed, stats strip |
| Workflow Runner | `/workflows/[id]` | WorkflowForm (dynamic), WorkflowOutput (markdown) |
| History | `/history` | Table with filters, expandable rows, re-run button |
| Knowledge Base | `/knowledge-base` | Folder accordion, file modal with rendered markdown |
| Architect | `/architect` | Full-height chat, YAML deploy card |
| Settings | `/settings` | API key status, profile input, system stats |

**Sidebar:** Fixed 240px, Lucide icons, nav links, client switcher (Phase 7), run stats at bottom.

**WorkflowForm input type mapping:**
```
"text"      → shadcn Input
"textarea"  → shadcn Textarea
"select"    → shadcn Select
"multiline" → Textarea split on newlines
```

**WorkflowOutput:** Render `primary_display_field` with `react-markdown + remark-gfm`. Sources in `<details>`. File path as muted mono text. Copy button. Obsidian deep link: `obsidian://open?vault=knowledge_base&file={filename}`.

---

## Phase 5 — Multi-Client

**New file: `core/client_resolver.py`**
```python
def get_client_kb_root(client_id: str | None) -> Path:
    if client_id is None:
        return ROOT / "knowledge_base"
    return ROOT / "clients" / client_id / "knowledge_base"
```

**`engine.py` change** (backward-compatible): add optional `kb_root: Path | None = None` param to `load_context()` and `save_output()`.

**`client.json` schema:**
```json
{
  "id": "example_client",
  "display_name": "Example Client",
  "active_workflows": ["company_research", "email_drafting", "meeting_prep", "portfolio_monitor"],
  "owner_name": "Client Owner"
}
```

---

## Obsidian Setup
New to Obsidian. Include in README:
```
1. Download Obsidian (obsidian.md)
2. Open Obsidian → "Open folder as vault"
3. Select: ai-os/knowledge_base/
4. Done — every AI output appears in Obsidian automatically
```
For a specific client: point vault at `clients/[client_id]/knowledge_base/` instead.

---

## Key Files (Never Modify Without Reading First)

| File | Purpose |
|---|---|
| `core/engine.py` | Four core primitives — everything builds on these |
| `core/registry.py` | Workflow auto-discovery — frontend depends on this schema |
| `core/db.py` | SQLite schema + CRUD |
| `dashboard/app.py` | Reference implementation — mirror every feature in v2 |
| `workflows/company_research/workflow.json` | Canonical manifest schema |

---

## API Keys (in `.env`)
```
ANTHROPIC_API_KEY   — Claude API
GROQ_API_KEY        — Groq (fast inference)
TAVILY_API_KEY      — Web search
EXA_API_KEY         — Live research
HUNTER_API_KEY      — Email finding
TWITTER_BEARER_TOKEN— Twitter/X signals
GMAIL_SENDER        — Gmail send
GMAIL_APP_PASSWORD  — Gmail app password
```
