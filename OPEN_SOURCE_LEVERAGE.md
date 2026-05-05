# AI-OS Open Source Leverage Strategy

Research date: 2026-04-29  
Purpose: decide what AI-OS should borrow from leading open-source AI/workflow projects, what it should avoid, and what the next product moves should be.

## Strategic Thesis

AI-OS should win by being the boring, local, Obsidian-native execution layer for repeatable SME workflows, not by becoming another agent platform, RAG/chat app, integration marketplace, or visual automation builder.

Short positioning:

> AI-OS is the Obsidian-native workflow runner for serious SME knowledge work.

The open-source leverage is not "we integrate everything." It is:

> Clone it, point it at your vault, run real business workflows, inspect every step, improve the templates, and keep your knowledge portable.

## Product Contract

Everything should strengthen this loop:

```
Workflow -> Run -> Evidence -> Validation -> Obsidian Output -> Reuse
```

If a feature does not improve one of those steps, it is probably platform creep.

AI-OS is:

- Local-first business workflow infrastructure.
- Obsidian-native knowledge and artifact storage.
- A way to package repeatable knowledge work for investors, operators, and SMEs.
- A system where runs are inspectable, replayable, and improvable.
- A consultancy delivery asset: the template is reusable, but the implementation is the product.

AI-OS is not:

- A chatbot.
- A Dify clone.
- A LangChain wrapper.
- A visual node automation platform.
- A generic RAG app.
- A model-training studio.
- A marketplace for agents.
- A multi-tenant SaaS control plane.

## Core Decision

Use these repos as references, not as the product foundation.

The strongest pattern across all projects is not "add more agents." It is:

1. Define workflows clearly.
2. Make every run observable.
3. Ground outputs in sources.
4. Validate before saving.
5. Keep artifacts portable.
6. Keep custom code behind explicit review.

That is exactly where AI-OS can be sharper than generic platforms.

## Ranked Next Moves

### 1. Make Workflow -> Run -> Obsidian Output the product contract

Every visible feature should serve this chain. Workflow pages, history, knowledge base, architect, evals, and multi-client support should all reinforce the same operational model.

Why it matters: Dify, n8n, Langflow, Flowise, Open WebUI, LibreChat, and AnythingLLM all pull toward generic platforms. AI-OS needs a stronger center of gravity.

### 2. Create a portable workflow spec

Add a small, readable YAML/JSON workflow format with:

- `id`, `name`, `version`, `description`
- `inputs`
- deterministic `steps`
- allowed `tools`
- expected `artifacts`
- `validators`
- `obsidian_output_path`
- `client_scope`
- example inputs and expected outputs

Do not make this a full node-canvas DSL. It should be readable by Manuel, Codex, and a client.

Borrowed from: Dify workflow exports, n8n workflow model, CrewAI flows, Langflow/Flowise templates.

### 3. Build local run tracing in SQLite

Add first-class run steps:

- `run_id`
- `step_name`
- `step_type`
- `status`
- `started_at`, `ended_at`, `duration`
- `model`
- `tokens` and estimated cost where available
- `inputs_hash`
- `sources`
- `artifact_paths`
- `validation_results`
- `error`

Why it matters: this gives AI-OS trust. A user can see what happened, where it failed, what sources were used, and what was saved.

Borrowed from: LangGraph/LangSmith tracing concepts, n8n execution history, Dify logs, CrewAI tracing.

### 4. Add output validation before save

Every serious workflow should have lightweight checks before saving to Obsidian:

- Required sections exist.
- Required fields are present.
- Claims cite sources where needed.
- Source freshness is acceptable.
- Output matches a Pydantic schema where appropriate.
- Tone matches client rules.
- No unsupported financial/legal/medical certainty.

This is more valuable than adding more models.

Borrowed from: CrewAI guardrails, Continue checks, Langflow policy components, AI-OS's existing eval/reliability direction.

### 5. Make Obsidian retrieval simple first

Build an AI-OS-native `kb_index`:

- Markdown files as source of truth.
- SQLite FTS/BM25 first.
- File path, folder, client, modified time, headings, tags.
- Chunk previews and citations.
- Optional embeddings later.

Do not start with RAGFlow, LlamaIndex, Elasticsearch, vector DBs, or a connector zoo.

Borrowed from: LlamaIndex context discipline, RAGFlow ingestion transparency, AnythingLLM local document UX.

### 6. Turn Architect into a constrained workflow builder

Architect should generate:

- Workflow YAML.
- Markdown SOP.
- Validators.
- Example input/output cases.
- Preview.
- Test run.
- Explicit deploy step.

Architect should not generate arbitrary Python and immediately execute it. Generated workflows should compose whitelisted primitives unless manually reviewed.

Borrowed from: MetaGPT SOPs, Dify/Langflow builder flow, AutoGPT block idea, smolagents security restraint.

### 7. Add eval cases per workflow

For each important workflow, store:

- Golden input examples.
- Expected output traits.
- Failure modes.
- Validation criteria.
- Latest run score.
- Improvement prompt.

AI-OS already has eval-related code. Make this part of the workflow quality loop, not a hidden developer feature.

Borrowed from: Flowise evals, Continue checks, AI-OS reliability playbook.

### 8. Use repo intelligence narrowly

Repo intelligence is useful for:

- Finding implementation precedent for client automations.
- Comparing licenses and maintenance health.
- Improving workflow templates.
- Generating execution packages for Codex/Claude Code.

It should not become the product's main identity. AI-OS is not a coding assistant.

### 9. Add optional provider adapters

Support:

- Anthropic, because the current core uses Claude.
- OpenAI-compatible endpoints.
- Groq where useful.
- Ollama as optional local mode.

Keep this behind settings and health checks. Do not expose a model playground to SME users.

### 10. Add browser capture only as a guarded tool

Browser automation can help with:

- Capturing screenshots.
- Extracting text from pages without APIs.
- Saving visible evidence into Obsidian.
- Portal checks where no API exists.

Keep it disabled by default. Require explicit confirmation for account actions, form submissions, purchases, CRM changes, or anything touching client systems.

## Dependency Strategy

### Adopt Ideas, Not Frameworks

Do not adopt LangChain, CrewAI, AutoGPT, n8n, Dify, Langflow, Flowise, RAGFlow, or LlamaIndex as the core runtime.

Reason: AI-OS's product value is not generic orchestration. It is the local workflow contract, Obsidian artifact layer, client-specific templates, and implementation clarity.

### Build Internally

Build these as AI-OS-native capabilities:

- Workflow spec.
- Run tracing.
- Obsidian KB indexing.
- Output validation.
- Workflow evals.
- Evidence panel.
- Credential health checks.
- Template packs.

These are central product muscles. Outsourcing them would make the system feel like a wrapper.

### Use Optional Adapters

Optional adapters are acceptable when they are thin:

- OpenAI-compatible model provider.
- Ollama local provider.
- Browser capture tool.
- Narrow market/news/search providers.
- Possibly MCP later for controlled external tools.

Adapters must not drag AI-OS into provider sprawl.

### Defer

Defer:

- Embeddings until FTS/BM25 fails clearly.
- LangGraph until workflows truly need durable branching/resume logic.
- LlamaIndex until local Markdown indexing proves insufficient.
- Fine-tuning until there are many approved/rejected workflow examples.
- Visual editing until templates are proven and users ask for it.

## Repo-by-Repo Leverage Map

Metadata below is based on public GitHub/docs review on 2026-04-29. License notes are product-risk flags, not legal advice.

| Repo | What It Is | License / Caveat | AI-OS Recommendation |
|---|---|---|---|
| [LangChain](https://github.com/langchain-ai/langchain) | Agent/application framework and integration layer. | MIT. LangSmith is commercial/hosted. | Borrow provider abstraction, tracing vocabulary, LangGraph state ideas. Do not make it a core dependency yet. |
| [Dify](https://github.com/langgenius/dify) | Full agentic workflow/app platform with visual builder and knowledge features. | Modified Apache 2.0; multi-tenant and frontend branding restrictions. | Product benchmark. Borrow workflow DSL, run logs, variable model. Do not compete head-on or copy UI. |
| [Flowise](https://github.com/FlowiseAI/Flowise) | Visual AI agent/workflow builder. | Mostly Apache 2.0 with enterprise/commercial areas; security risks around custom code/MCP have existed. | Borrow templates, API-first execution, HITL ideas. Avoid custom code nodes and builder-as-product. |
| [CrewAI](https://github.com/crewAIInc/crewAI) | Multi-agent and flow orchestration framework. | MIT; telemetry/commercial control-plane caveats. | Borrow deterministic flows, state, guardrails, structured outputs. Avoid multi-agent branding. |
| [AutoGPT](https://github.com/Significant-Gravitas/AutoGPT) | Autonomous-agent platform and block builder. | Platform folder uses PolyForm Shield; classic parts MIT. | Borrow block mental model and import/export concepts. Avoid platform code and continuous autonomous agents. |
| [Ollama](https://github.com/ollama/ollama) | Local model runner with API and OpenAI-compatible endpoints. | MIT; model licenses vary. | Add optional local provider mode with health checks. Do not make local models mandatory. |
| [Open WebUI](https://github.com/open-webui/open-webui) | Self-hosted AI chat UI for local/cloud models. | Custom BSD-like license with branding restrictions. | Borrow local/offline posture and provider abstraction. Do not become a chat frontend or depend on its UI. |
| [AnythingLLM](https://github.com/Mintplex-Labs/anything-llm) | Local-first chat-with-docs/workspace app. | MIT; telemetry can be disabled. | Borrow setup clarity and workspace thinking. Avoid chat-with-docs positioning. |
| [LlamaIndex](https://github.com/run-llama/llama_index) | RAG/context framework for private data. | MIT; LlamaCloud/LlamaParse commercial services. | Borrow context/index/citation discipline. Build simple AI-OS indexing first. |
| [Langflow](https://github.com/langflow-ai/langflow) | Visual AI workflow/agent builder. | MIT; custom component execution is a security concern. | Borrow test loop, versioning, deploy-as-API idea. Avoid visual canvas and arbitrary Python execution. |
| [n8n](https://github.com/n8n-io/n8n) | Source-available workflow automation platform with integrations. | Sustainable Use License; commercial limits for hosting/white-label use. | Borrow run history, replay, credentials UX, templates. Avoid Zapier/integration-platform territory. |
| [RAGFlow](https://github.com/infiniflow/ragflow) | Heavy enterprise RAG engine. | Apache 2.0; heavy Docker/infra footprint. | Borrow ingestion transparency, chunk previews, citations. Do not embed the stack. |
| [MetaGPT](https://github.com/FoundationAgents/MetaGPT) | SOP-based multi-agent software-company framework. | MIT; commercial MGX direction. | Borrow SOP-first workflow design and intermediate artifacts. Avoid roleplay-heavy multi-agent processes. |
| [OpenBB](https://github.com/OpenBB-finance/OpenBB) | Financial data platform for analysts and agents. | AGPL/commercial licensing concerns. | Borrow provider abstraction and domain packaging. Do not embed or become a finance terminal. |
| [Browser Use](https://github.com/browser-use/browser-use) | Python browser automation for agents. | MIT; operational brittleness around login/CAPTCHA/UI changes. | Add guarded browser capture later. Do not market autonomous web ops. |
| [smolagents](https://github.com/huggingface/smolagents) | Minimal agent library from Hugging Face. | Apache 2.0; code execution needs sandboxing. | Borrow small-core restraint and model-agnostic thinking. Avoid arbitrary code agents. |
| [Unsloth](https://github.com/unslothai/unsloth) | Local model fine-tuning and training tooling. | Core Apache 2.0; Studio/UI parts can be AGPL. | Defer. Track approved/rejected outputs now to enable future datasets. |
| [GPT Researcher](https://github.com/assafelovic/gpt-researcher) | Autonomous web/local research agent. | Apache 2.0. | Borrow plan/gather/source-note/synthesize pipeline and depth modes. Do not import full app. |
| [Continue](https://github.com/continuedev/continue) | AI coding agent/checks/IDE tooling. | Apache 2.0; hosted Mission Control is commercial. | Borrow source-controlled checks and context-provider idea. Do not become a dev IDE. |
| [LibreChat](https://github.com/danny-avila/LibreChat) | Self-hosted ChatGPT-style multi-provider app. | MIT; dependency/hosting complexity. | Borrow markdown export, resumable streaming, presets, search. Avoid ChatGPT-clone surface area. |

## What To Build

### Local Run Timeline

History should show more than final output:

```
Input received
Loaded KB context
Collected web sources
Synthesized output
Ran validators
Saved Obsidian note
Logged run
```

Each step should expose duration, status, sources, and errors.

### Evidence Panel

Every serious workflow output should show:

- KB notes used.
- Web sources used.
- Prior runs referenced.
- Source freshness.
- Saved file path.
- Validation status.

This is one of the best ways to make the product feel trustworthy.

### Business Output Checks

Store checks as Markdown or YAML, for example:

```
knowledge_base/system/checks/investment_memo_quality.md
knowledge_base/system/checks/email_tone.md
knowledge_base/system/checks/source_grounding.md
```

These checks should be readable, editable, and tied to workflow validators.

### Workflow Template Packs

Create packs by business use case:

- Investor pack: company research, meeting prep, portfolio monitor, deal watchlist.
- BDR pack: account brief, lead enrichment, outreach email, follow-up.
- Professional services pack: client brief, proposal draft, meeting summary, weekly digest.

Each template should define:

- Required inputs.
- What it produces.
- Where it saves in Obsidian.
- Required API keys.
- Example input/output.
- Validation checks.

### Research Primitive

Add an internal primitive inspired by GPT Researcher:

```
plan_queries()
collect_sources()
extract_source_notes()
synthesize_with_citations()
save_source_notes()
```

Use this inside company research, portfolio monitor, VC lead finder, and future client research workflows.

### Credential Health

Settings should show:

- Anthropic configured: yes/no.
- Exa configured: yes/no.
- Groq configured: yes/no.
- Hunter configured: yes/no.
- Gmail configured: yes/no.
- Ollama reachable: yes/no, optional.

Do not expose secrets. Show only capability readiness.

### Model / License Bill of Materials

For trust and future client work, show:

- Active model provider.
- Model name.
- Cloud or local.
- Search/research provider.
- Local model license status: verified / not verified.
- Data leaves device: yes/no by workflow.

This avoids false "fully local AI" claims.

## What Not To Build

Do not build:

- Node canvas as the main interface.
- Generic chat-with-docs.
- Provider playground.
- Agent marketplace.
- Plugin store.
- Connector zoo.
- Custom code nodes.
- Arbitrary Python execution from Architect.
- Public flow endpoints.
- Continuous autonomous agents.
- Full GPT Researcher clone.
- Full RAGFlow stack.
- OpenBB clone or finance terminal.
- Fine-tuning UI.
- Voice/video/image/model-builder features.
- Enterprise teams/workspaces/auth before real customer pressure.
- Multi-tenant SaaS before the local/client-folder model is proven.

The most dangerous temptation is "Dify plus Obsidian." That is a worse strategy than "AI-OS as a focused business workflow appliance."

## Security Rules

### Architect Safety

Architect may generate YAML and Markdown SOPs. It may not silently generate and execute arbitrary Python.

Deploy flow:

1. Generate workflow spec.
2. Show preview.
3. Run validation.
4. Run test input.
5. Show artifacts and logs.
6. Require explicit deploy.

### Browser Safety

Browser tools must:

- Be disabled by default.
- Save screenshots and extracted text as evidence.
- Ask confirmation before account actions.
- Never handle purchases, sends, deletes, or CRM writes without explicit user approval.

### Tool Safety

Allowed tools should be explicit per workflow. A workflow should not be able to call every provider or every local function by default.

## Suggested Roadmap

### Phase A: Trust Layer

Build:

- Run step tracing.
- Evidence panel.
- Validation checks.
- Credential health.
- Better history detail.

Why first: this makes the current workflows more credible without changing the product surface too much.

### Phase B: Knowledge Layer

Build:

- Markdown KB index with SQLite FTS/BM25.
- Source previews.
- Citation metadata.
- Source notes saved to Obsidian.

Why second: this improves output quality and makes Obsidian the moat.

### Phase C: Workflow Spec Layer

Build:

- Portable workflow YAML/JSON spec.
- Versioned workflow templates.
- SOP Markdown files.
- Test cases and validators per workflow.

Why third: this makes AI-OS portable and teachable.

### Phase D: Constrained Architect

Build:

- Architect generates spec + SOP + validators.
- Preview/test/deploy flow.
- Whitelisted primitives only.

Why fourth: this gives the "build custom workflow" dream without opening the security trapdoor.

### Phase E: Optional Power Tools

Only after the above:

- Ollama provider adapter.
- Browser capture.
- Optional embeddings.
- Research depth modes.
- Thin market data provider.

## Final Recommendation

Do not pivot AI-OS into a generic AI platform.

Make it narrower, more inspectable, and more useful:

> AI-OS turns repeatable business knowledge work into local workflows, produces Obsidian-native artifacts, and gives every client a transparent record of what ran, what sources were used, what passed validation, and what should improve next.

That is a stronger wedge than trying to beat Dify, LangChain, n8n, or Open WebUI at their own games.
