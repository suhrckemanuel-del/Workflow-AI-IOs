"""
AI-OS Architect
---------------
AI-powered consultant that helps users build no-code workflows.
Maintains full conversation history, researches the user's industry,
and generates YAML configs that deploy directly into the platform.
"""

import os
import re
import yaml
import datetime
from pathlib import Path
from typing import List, Dict, Any

import anthropic
from dotenv import load_dotenv
from core.engine import load_context, ROOT, DEFAULT_MODEL
from workflows.company_research.run import exa_search

load_dotenv()

ARCHITECT_LOGS    = ROOT / "knowledge_base" / "architect_logs"
CUSTOM_WORKFLOWS  = ROOT / "knowledge_base" / "custom_workflows"

ARCHITECT_LOGS.mkdir(parents=True, exist_ok=True)
CUSTOM_WORKFLOWS.mkdir(parents=True, exist_ok=True)

SYSTEM_PROMPT = """You are the AI-OS Architect — an AI integration consultant embedded inside the AI-OS platform.

Your job: help any user (investor, business owner, operator, student) identify a repetitive workflow in their work and turn it into a deployable AI automation.

## The 4-step pattern every workflow follows
1. INPUT   — what information goes in (user provides this each run)
2. CONTEXT — what the AI reads from the knowledge base to personalise the output
3. PROCESS — the Claude instructions (system prompt + user prompt)
4. OUTPUT  — what gets saved and where

## Your approach
- Ask 1-2 clarifying questions before proposing anything. Understand the pain before prescribing the solution.
- Be specific and honest. If a workflow won't save them meaningful time, say so.
- Propose small, high-impact automations. One workflow that runs daily beats a complex system that never gets used.
- When you have enough information, output a deployable YAML config.

## YAML format — you MUST use this exact structure
```yaml
id: snake_case_workflow_id
name: Human Readable Name
icon: 🔧
description: One sentence describing what it does.
order: 10
inputs:
  - name: input_key
    label: Label shown in the UI
    type: text
context:
  folders:
    - thesis
  files:
    - folder: templates
      filename: email_style_guide.md
process:
  system_prompt: |
    You are a helpful assistant for {context}.
    [Your full system prompt here. Use {context} for knowledge base content.]
  user_prompt_template: |
    [Your user prompt here. Reference inputs with {input_key}.]
output:
  save: true
  folder: meetings
  filename_template: workflow_id_{timestamp}.md
```

## Rules for the YAML
- `id` must be snake_case, no spaces
- `inputs[].type` is one of: text, textarea, select, multiline
- `context.folders` lists knowledge base folders to load (thesis, templates, companies, meetings)
- `context.files` lists specific files to load
- In prompts, use {context} for the loaded knowledge base content, and {input_key} for each input
- Only output the YAML when you have enough information to make it genuinely useful
- Wrap YAML in ```yaml code blocks so it can be auto-detected and deployed
"""


class AIArchitect:
    def __init__(self):
        self.client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    def chat(self, user_message: str, history: List[Dict[str, str]] = None) -> str:
        """
        Multi-turn chat. history is a list of {"role": "user"|"assistant", "content": str}.
        Pulls live research when the user describes a domain or requests a workflow.
        """
        if history is None:
            history = []

        # Pull live research when it looks useful
        research_context = ""
        trigger_words = ["automate", "workflow", "build", "industry", "business", "company", "process"]
        if any(w in user_message.lower() for w in trigger_words):
            try:
                signals = exa_search(f"AI automation workflow {user_message}", num_results=3)
                snippets = [f"- {s['title']}: {s['text'][:300]}" for s in signals if s.get("title")]
                if snippets:
                    research_context = "\n\nCurrent industry signals:\n" + "\n".join(snippets)
            except Exception:
                pass

        system = SYSTEM_PROMPT + research_context

        # Build full message history for Claude
        messages = []
        for msg in history:
            role = msg.get("role")
            if role in ("user", "assistant"):
                messages.append({"role": role, "content": msg["content"]})
        messages.append({"role": "user", "content": user_message})

        response = self.client.messages.create(
            model=DEFAULT_MODEL,
            max_tokens=2000,
            system=system,
            messages=messages,
        )
        reply = response.content[0].text

        # Log the exchange
        try:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            log_file  = ARCHITECT_LOGS / f"chat_{timestamp}.md"
            log_file.write_text(f"USER: {user_message}\n\nARCHITECT: {reply}", encoding="utf-8")
        except Exception:
            pass

        return reply

    def extract_yaml(self, text: str) -> str | None:
        """Extract the first ```yaml ... ``` block from a response."""
        match = re.search(r"```yaml\s*(.*?)```", text, re.DOTALL)
        return match.group(1).strip() if match else None

    def save_generated_workflow(self, yaml_content: str, workflow_id: str) -> bool:
        """Validate and save YAML to custom_workflows folder."""
        try:
            config = yaml.safe_load(yaml_content)
            if not isinstance(config, dict):
                return False
            config["id"] = workflow_id
            file_path = CUSTOM_WORKFLOWS / f"{workflow_id}.yaml"
            with open(file_path, "w", encoding="utf-8") as f:
                yaml.dump(config, f, default_flow_style=False, allow_unicode=True)
            return True
        except Exception as e:
            print(f"[architect] Error saving workflow: {e}")
            return False
