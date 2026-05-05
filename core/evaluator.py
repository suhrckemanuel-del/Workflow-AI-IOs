"""
Automation eval judge
---------------------
Scores automation outputs against explicit project goals and eval criteria.
The loop is intentionally simple: fixed rubric, comparable score, stored result.
"""

from pydantic import BaseModel, Field

from core.engine import call_claude_structured


class EvalJudgement(BaseModel):
    score: int = Field(ge=0, le=100)
    verdict: str
    reasoning: str
    improvement_prompt: str


def judge_output(project: dict, case: dict, observed_output: str) -> EvalJudgement:
    system = """You are an exacting automation evaluator.
Score the observed output against the business goal, working definition, eval criteria, and ideal output.
Use backward induction: start from the user's ultimate desired outcome, identify what the output must prove, then judge whether it does.
Return a strict JSON judgement. Scores:
90-100 excellent and client-ready
75-89 good but has clear improvements
50-74 partially useful, not reliable enough
0-49 failed or unsafe for the intended workflow
Verdict must be one of: pass, needs_work, fail."""

    user = f"""Project goal:
{project.get("goal", "")}

Working definition:
{project.get("working_definition", "")}

Client context:
{project.get("client_context", "")}

Required tools/data:
{project.get("required_tools", "")}

Eval case: {case.get("name", "")}

Input:
{case.get("input_text", "")}

Ideal output:
{case.get("ideal_output", "")}

Criteria:
{case.get("criteria", "")}

Observed output:
{observed_output}

Judge only what matters for the intended automation outcome. In improvement_prompt, write the next best instruction for Codex/Claude Code to improve this automation."""

    return call_claude_structured(system=system, user=user, schema=EvalJudgement, max_tokens=1200)
