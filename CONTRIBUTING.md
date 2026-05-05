# Contributing to AI-OS

The single most useful thing you can contribute is a new workflow.

## How to add a workflow

Adding a workflow requires creating two files. You do not need to touch any existing code.

### 1. Create the folder

```
workflows/your_workflow_name/
├── __init__.py     (empty)
├── workflow.json   (metadata — defines inputs, display, registry entry)
└── run.py          (the workflow function)
```

### 2. Write `workflow.json`

```json
{
  "id": "your_workflow_name",
  "name": "Your Workflow Name",
  "icon": "🚀",
  "description": "What it does in one sentence.",
  "order": 5,
  "entry_function": "your_function_name",
  "entry_module": "workflows.your_workflow_name.run",
  "inputs": [
    {
      "key": "input_text",
      "label": "Input label shown in UI",
      "type": "text",
      "placeholder": "e.g. example value",
      "required": true
    }
  ],
  "primary_display_field": "output",
  "stats_label": "",
  "requires_exa": false,
  "demo_available": false
}
```

**Input types:** `text` | `textarea` | `select` (add `"choices": [...]`) | `multiline` (textarea → list)

### 3. Write `run.py`

Follow the 4-step pattern:

```python
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent))
from core.engine import call_claude, load_context, save_output

def your_function_name(input_text: str) -> dict:

    # STEP 1: CONTEXT — pull from knowledge base
    context = load_context("thesis")

    # STEP 2: INPUT — prepare what goes in
    user_input = f"Do something useful with: {input_text}"

    # STEP 3: PROCESS — call Claude
    system = f"You are a helpful assistant. Context: {context}"
    result = call_claude(system, user_input, max_tokens=1000)

    # STEP 4: OUTPUT — save and return
    save_output(result, "meetings", "my_output.md")
    return {"output": result}
```

For structured outputs (recommended), use `call_claude_structured` with a Pydantic model. See `workflows/meeting_prep/run.py` for a complete example.

### 4. Restart the dashboard

```bash
streamlit run dashboard/app.py
```

Your workflow appears in the sidebar automatically. No other files to touch.

### PR checklist

- [ ] `workflow.json` is valid JSON
- [ ] `run.py` has a docstring with INPUT / CONTEXT / PROCESS / OUTPUT
- [ ] Function returns a dict with at least the field named in `primary_display_field`
- [ ] Tested locally with a real API call

## Code style

- Python only, no new frontend frameworks
- All Claude calls go through `core.engine` functions — never instantiate the client directly in a workflow
- Keep workflow functions pure: no global state, no side effects beyond `save_output`
