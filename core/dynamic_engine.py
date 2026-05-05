"""
AI-OS Dynamic Engine
--------------------
Executes workflows defined in YAML files.
Allows for no-code expansion of the platform.
"""

import yaml
from pathlib import Path
from typing import Dict, Any
from core.engine import load_context, call_claude, save_output

class DynamicWorkflow:
    def __init__(self, config_path: Path):
        with open(config_path, "r", encoding="utf-8") as f:
            self.config = yaml.safe_load(f)
        
        self.id = self.config.get("id")
        self.name = self.config.get("name")
        self.description = self.config.get("description")
        self.steps = self.config.get("steps", [])
        self.inputs = self.config.get("inputs", [])

    def run(self, **input_data) -> Dict[str, Any]:
        """
        Executes the 4-step pattern based on YAML config.
        """
        context_data = ""
        
        # STEP 1: CONTEXT
        context_config = self.config.get("context", {})
        if context_config:
            folders = context_config.get("folders", [])
            for folder in folders:
                context_data += load_context(folder=folder)
            
            files = context_config.get("files", [])
            for file_info in files:
                context_data += load_context(folder=file_info.get("folder"), filename=file_info.get("filename"))

        # STEP 2: INPUT (already provided in input_data)
        # We can also have pre-processing here if needed
        
        # STEP 3: PROCESS
        process_config = self.config.get("process", {})
        system_prompt = process_config.get("system_prompt", "You are a helpful assistant.")
        user_prompt_template = process_config.get("user_prompt_template", "Process this: {input_text}")
        
        # Inject inputs and context into prompts
        formatted_system = system_prompt.format(context=context_data, **input_data)
        formatted_user = user_prompt_template.format(context=context_data, **input_data)
        
        result = call_claude(formatted_system, formatted_user)

        # STEP 4: OUTPUT
        output_config = self.config.get("output", {})
        if output_config.get("save", True):
            folder = output_config.get("folder", "meetings")
            # Generate filename based on inputs if possible
            filename_template = output_config.get("filename_template", "dynamic_output_{timestamp}.md")
            import datetime
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = filename_template.format(timestamp=timestamp, **input_data)
            
            save_path = save_output(result, folder, filename)
            return {
                "output": result,
                "save_path": str(save_path)
            }
        
        return {"output": result}

def load_dynamic_workflows(directory: Path) -> Dict[str, DynamicWorkflow]:
    """
    Loads all YAML workflows from a directory.
    """
    workflows = {}
    if not directory.exists():
        return workflows
        
    for yaml_file in directory.glob("*.yaml"):
        try:
            dw = DynamicWorkflow(yaml_file)
            workflows[dw.id] = dw
        except Exception as e:
            print(f"Error loading workflow {yaml_file}: {e}")
            
    return workflows
