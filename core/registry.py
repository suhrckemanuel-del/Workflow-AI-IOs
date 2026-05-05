"""
AI-OS Workflow Registry
-----------------------
Auto-discovers workflows by scanning workflows/*/workflow.json.
The dashboard reads this — run.py is never imported until the user clicks Run.
"""

import importlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

WORKFLOWS_DIR = Path(__file__).parent.parent / "workflows"
CUSTOM_DIR    = Path(__file__).parent.parent / "knowledge_base" / "custom_workflows"


@dataclass
class WorkflowInput:
    key: str
    label: str
    type: str           # "text" | "textarea" | "select" | "multiline"
    required: bool = True
    placeholder: str = ""
    choices: list[str] = field(default_factory=list)


@dataclass
class WorkflowMeta:
    id: str
    name: str
    icon: str
    description: str
    order: int
    entry_function: str
    entry_module: str
    inputs: list[WorkflowInput]
    primary_display_field: str
    stats_label: str
    requires_exa: bool
    demo_available: bool
    output_fields: list[str] = field(default_factory=list)


def _parse_meta(data: dict) -> WorkflowMeta:
    inputs = [
        WorkflowInput(
            key=i["key"],
            label=i["label"],
            type=i["type"],
            required=i.get("required", True),
            placeholder=i.get("placeholder", ""),
            choices=i.get("choices", []),
        )
        for i in data.get("inputs", [])
    ]
    return WorkflowMeta(
        id=data["id"],
        name=data["name"],
        icon=data.get("icon", "⚙️"),
        description=data.get("description", ""),
        order=data.get("order", 99),
        entry_function=data["entry_function"],
        entry_module=data["entry_module"],
        inputs=inputs,
        primary_display_field=data.get("primary_display_field", ""),
        stats_label=data.get("stats_label", ""),
        requires_exa=data.get("requires_exa", False),
        demo_available=data.get("demo_available", False),
        output_fields=data.get("output_fields", []),
    )


def discover_workflows() -> list[WorkflowMeta]:
    """Scan workflows/*/workflow.json and YAML custom workflows."""
    metas = []
    
    # 1. Standard JSON workflows
    for manifest in sorted(WORKFLOWS_DIR.glob("*/workflow.json")):
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
            metas.append(_parse_meta(data))
        except Exception as e:
            print(f"[registry] Warning: could not load {manifest}: {e}")
            
    # 2. Custom YAML workflows
    if CUSTOM_DIR.exists():
        import yaml
        for manifest in sorted(CUSTOM_DIR.glob("*.yaml")):
            try:
                data = yaml.safe_load(manifest.read_text(encoding="utf-8"))
                # Map YAML to WorkflowMeta
                # We add a flag or convention to identify dynamic ones
                data["entry_module"] = "core.dynamic_engine"
                data["entry_function"] = "DynamicWorkflow"
                # Map inputs
                inputs = []
                for i in data.get("inputs", []):
                    inputs.append({
                        "key": i["name"],
                        "label": i.get("label", i["name"]),
                        "type": i.get("type", "text"),
                        "choices": i.get("options", []),
                        "required": True
                    })
                data["inputs"] = inputs
                data["primary_display_field"] = "output"
                data["order"] = data.get("order", 100)
                metas.append(_parse_meta(data))
            except Exception as e:
                print(f"[registry] Warning: could not load custom workflow {manifest}: {e}")
                
    return sorted(metas, key=lambda m: (m.order, m.name))


def get_workflow(workflow_id: str) -> WorkflowMeta | None:
    for meta in discover_workflows():
        if meta.id == workflow_id:
            return meta
    return None


def load_entry_function(meta: WorkflowMeta) -> Callable:
    """Import the workflow module and return the entry function. Called only at run time."""
    if meta.entry_module == "core.dynamic_engine":
        from core.dynamic_engine import DynamicWorkflow
        yaml_path = CUSTOM_DIR / f"{meta.id}.yaml"
        dw = DynamicWorkflow(yaml_path)
        return dw.run
        
    mod = importlib.import_module(meta.entry_module)
    return getattr(mod, meta.entry_function)


if __name__ == "__main__":
    workflows = discover_workflows()
    print(f"Found {len(workflows)} workflow(s):")
    for w in workflows:
        print(f"  [{w.order}] {w.icon} {w.name} (id={w.id}, module={w.entry_module})")
