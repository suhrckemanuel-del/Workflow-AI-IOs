"""
AI-OS Database Layer
--------------------
SQLite persistence for run history, saved inputs, and settings.
DB lives at data/aios.db — created automatically on first init_db() call.
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT   = Path(__file__).parent.parent
DB_PATH = ROOT / "data" / "aios.db"


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db() -> None:
    with _connect() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS runs (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                workflow_id   TEXT    NOT NULL,
                status        TEXT    NOT NULL,
                inputs_json   TEXT    NOT NULL,
                outputs_json  TEXT,
                error_message TEXT,
                duration_s    REAL,
                model_used    TEXT,
                created_at    TEXT    NOT NULL DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_runs_workflow
                ON runs(workflow_id, created_at DESC);

            CREATE TABLE IF NOT EXISTS settings (
                key        TEXT PRIMARY KEY,
                value      TEXT NOT NULL,
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS input_drafts (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                workflow_id TEXT NOT NULL,
                label       TEXT NOT NULL DEFAULT 'last_used',
                inputs_json TEXT NOT NULL,
                updated_at  TEXT NOT NULL DEFAULT (datetime('now')),
                UNIQUE(workflow_id, label)
            );

            CREATE TABLE IF NOT EXISTS automation_projects (
                id                 INTEGER PRIMARY KEY AUTOINCREMENT,
                name               TEXT NOT NULL,
                goal               TEXT NOT NULL,
                owner_type         TEXT NOT NULL,
                current_process    TEXT NOT NULL,
                working_definition TEXT NOT NULL,
                client_context     TEXT NOT NULL DEFAULT '',
                required_tools     TEXT NOT NULL DEFAULT '',
                input_examples     TEXT NOT NULL DEFAULT '',
                output_examples    TEXT NOT NULL DEFAULT '',
                status             TEXT NOT NULL DEFAULT 'idea',
                chosen_repo_url    TEXT,
                created_at         TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at         TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_automation_projects_status
                ON automation_projects(status, updated_at DESC);

            CREATE TABLE IF NOT EXISTS automation_repo_candidates (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id     INTEGER NOT NULL,
                url            TEXT NOT NULL,
                notes          TEXT NOT NULL DEFAULT '',
                rank           INTEGER,
                fit_score      INTEGER,
                recommendation TEXT NOT NULL DEFAULT '',
                license        TEXT NOT NULL DEFAULT '',
                stars          INTEGER,
                last_updated   TEXT NOT NULL DEFAULT '',
                language       TEXT NOT NULL DEFAULT '',
                analysis_json  TEXT NOT NULL DEFAULT '{}',
                created_at     TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY(project_id) REFERENCES automation_projects(id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_repo_candidates_project
                ON automation_repo_candidates(project_id, created_at DESC);

            CREATE TABLE IF NOT EXISTS execution_packages (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id      INTEGER NOT NULL,
                version         INTEGER NOT NULL,
                title           TEXT NOT NULL,
                content_md      TEXT NOT NULL,
                readiness_score INTEGER NOT NULL,
                readiness_json  TEXT NOT NULL,
                planning_mode   TEXT NOT NULL DEFAULT 'quick',
                created_at      TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY(project_id) REFERENCES automation_projects(id) ON DELETE CASCADE,
                UNIQUE(project_id, version)
            );
            CREATE INDEX IF NOT EXISTS idx_execution_packages_project
                ON execution_packages(project_id, version DESC);

            CREATE TABLE IF NOT EXISTS agent_updates (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id    INTEGER NOT NULL,
                agent         TEXT NOT NULL,
                summary       TEXT NOT NULL,
                changed_files TEXT NOT NULL DEFAULT '',
                commands_run  TEXT NOT NULL DEFAULT '',
                test_result   TEXT NOT NULL DEFAULT '',
                blockers      TEXT NOT NULL DEFAULT '',
                next_step     TEXT NOT NULL DEFAULT '',
                created_at    TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY(project_id) REFERENCES automation_projects(id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_agent_updates_project
                ON agent_updates(project_id, created_at DESC);

            CREATE TABLE IF NOT EXISTS eval_cases (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id     INTEGER NOT NULL,
                name           TEXT NOT NULL,
                input_text     TEXT NOT NULL DEFAULT '',
                ideal_output   TEXT NOT NULL DEFAULT '',
                criteria       TEXT NOT NULL,
                weight         REAL NOT NULL DEFAULT 1.0,
                created_at     TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY(project_id) REFERENCES automation_projects(id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_eval_cases_project
                ON eval_cases(project_id, created_at DESC);

            CREATE TABLE IF NOT EXISTS eval_results (
                id                 INTEGER PRIMARY KEY AUTOINCREMENT,
                eval_case_id       INTEGER NOT NULL,
                project_id         INTEGER NOT NULL,
                observed_output    TEXT NOT NULL,
                score              INTEGER NOT NULL,
                verdict            TEXT NOT NULL,
                reasoning          TEXT NOT NULL,
                improvement_prompt TEXT NOT NULL DEFAULT '',
                created_at         TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY(eval_case_id) REFERENCES eval_cases(id) ON DELETE CASCADE,
                FOREIGN KEY(project_id) REFERENCES automation_projects(id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_eval_results_case
                ON eval_results(eval_case_id, created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_eval_results_project
                ON eval_results(project_id, created_at DESC);

            CREATE TABLE IF NOT EXISTS project_eval_configs (
                project_id                  INTEGER PRIMARY KEY,
                workflow_id                 TEXT,
                eval_case_id                INTEGER,
                input_json                  TEXT NOT NULL DEFAULT '{}',
                deterministic_rules_json    TEXT NOT NULL DEFAULT '{}',
                latest_output_ref_json      TEXT NOT NULL DEFAULT '{}',
                updated_at                  TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY(project_id) REFERENCES automation_projects(id) ON DELETE CASCADE,
                FOREIGN KEY(eval_case_id) REFERENCES eval_cases(id) ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS project_eval_runs (
                id                          INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id                  INTEGER NOT NULL,
                workflow_id                 TEXT,
                eval_case_id                INTEGER,
                workflow_run_id             INTEGER,
                eval_result_id              INTEGER,
                output_ref_json             TEXT NOT NULL DEFAULT '{}',
                deterministic_checks_json   TEXT NOT NULL DEFAULT '[]',
                deterministic_passed        INTEGER NOT NULL DEFAULT 0,
                deterministic_total         INTEGER NOT NULL DEFAULT 0,
                status                      TEXT NOT NULL,
                error                       TEXT,
                created_at                  TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY(project_id) REFERENCES automation_projects(id) ON DELETE CASCADE,
                FOREIGN KEY(eval_case_id) REFERENCES eval_cases(id) ON DELETE SET NULL,
                FOREIGN KEY(workflow_run_id) REFERENCES runs(id) ON DELETE SET NULL,
                FOREIGN KEY(eval_result_id) REFERENCES eval_results(id) ON DELETE SET NULL
            );
            CREATE INDEX IF NOT EXISTS idx_project_eval_runs_project
                ON project_eval_runs(project_id, created_at DESC);

            CREATE TABLE IF NOT EXISTS agent_jobs (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                name         TEXT    NOT NULL,
                workflow_id  TEXT    NOT NULL,
                cron_expr    TEXT    NOT NULL,
                inputs_json  TEXT    NOT NULL,
                client_id    TEXT,
                enabled      INTEGER NOT NULL DEFAULT 1,
                last_run_at  TEXT,
                last_status  TEXT,
                created_at   TEXT    NOT NULL DEFAULT (datetime('now'))
            );
        """)
    _migrate()


def _migrate() -> None:
    with _connect() as conn:
        existing = {row[1] for row in conn.execute("PRAGMA table_info(execution_packages)").fetchall()}
        if "planning_mode" not in existing:
            conn.execute("ALTER TABLE execution_packages ADD COLUMN planning_mode TEXT NOT NULL DEFAULT 'quick'")
        project_cols = {row[1] for row in conn.execute("PRAGMA table_info(automation_projects)").fetchall()}
        for column in ("client_context", "required_tools", "input_examples", "output_examples"):
            if column not in project_cols:
                conn.execute(f"ALTER TABLE automation_projects ADD COLUMN {column} TEXT NOT NULL DEFAULT ''")
        repo_cols = {row[1] for row in conn.execute("PRAGMA table_info(automation_repo_candidates)").fetchall()}
        repo_defaults = {
            "fit_score": "INTEGER",
            "recommendation": "TEXT NOT NULL DEFAULT ''",
            "license": "TEXT NOT NULL DEFAULT ''",
            "stars": "INTEGER",
            "last_updated": "TEXT NOT NULL DEFAULT ''",
            "language": "TEXT NOT NULL DEFAULT ''",
            "analysis_json": "TEXT NOT NULL DEFAULT '{}'",
        }
        for column, definition in repo_defaults.items():
            if column not in repo_cols:
                conn.execute(f"ALTER TABLE automation_repo_candidates ADD COLUMN {column} {definition}")


def log_run(
    workflow_id: str,
    status: str,
    inputs: dict,
    outputs: dict | None,
    error: str | None,
    duration: float,
    model: str,
) -> int:
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO runs
               (workflow_id, status, inputs_json, outputs_json, error_message, duration_s, model_used)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                workflow_id,
                status,
                json.dumps(inputs, default=str),
                json.dumps(outputs, default=str) if outputs is not None else None,
                error,
                duration,
                model,
            ),
        )
        return cur.lastrowid


def get_runs(
    workflow_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    with _connect() as conn:
        if workflow_id:
            rows = conn.execute(
                "SELECT * FROM runs WHERE workflow_id = ? ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (workflow_id, limit, offset),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM runs ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
        return [dict(r) for r in rows]


def get_run(run_id: int) -> dict | None:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
        return dict(row) if row else None


def save_setting(key: str, value: Any) -> None:
    with _connect() as conn:
        conn.execute(
            """INSERT INTO settings (key, value, updated_at) VALUES (?, ?, datetime('now'))
               ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at""",
            (key, json.dumps(value)),
        )


def get_setting(key: str, default: Any = None) -> Any:
    with _connect() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        if row is None:
            return default
        return json.loads(row["value"])


def save_input_draft(workflow_id: str, inputs: dict, label: str = "last_used") -> None:
    with _connect() as conn:
        conn.execute(
            """INSERT INTO input_drafts (workflow_id, label, inputs_json, updated_at)
               VALUES (?, ?, ?, datetime('now'))
               ON CONFLICT(workflow_id, label)
               DO UPDATE SET inputs_json=excluded.inputs_json, updated_at=excluded.updated_at""",
            (workflow_id, label, json.dumps(inputs, default=str)),
        )


def get_input_draft(workflow_id: str, label: str = "last_used") -> dict | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT inputs_json FROM input_drafts WHERE workflow_id = ? AND label = ?",
            (workflow_id, label),
        ).fetchone()
        if row is None:
            return None
        return json.loads(row["inputs_json"])


def create_automation_project(
    name: str,
    goal: str,
    owner_type: str,
    current_process: str,
    working_definition: str,
    client_context: str = "",
    required_tools: str = "",
    input_examples: str = "",
    output_examples: str = "",
) -> dict:
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO automation_projects
               (name, goal, owner_type, current_process, working_definition,
                client_context, required_tools, input_examples, output_examples)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                name,
                goal,
                owner_type,
                current_process,
                working_definition,
                client_context,
                required_tools,
                input_examples,
                output_examples,
            ),
        )
        row = conn.execute(
            "SELECT * FROM automation_projects WHERE id = ?",
            (cur.lastrowid,),
        ).fetchone()
        return dict(row)


def list_automation_projects() -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM automation_projects ORDER BY updated_at DESC, created_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]


def get_automation_project(project_id: int) -> dict | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM automation_projects WHERE id = ?",
            (project_id,),
        ).fetchone()
        return dict(row) if row else None


def update_automation_project(project_id: int, **fields: Any) -> dict | None:
    allowed = {
        "name",
        "goal",
        "owner_type",
        "current_process",
        "working_definition",
        "client_context",
        "required_tools",
        "input_examples",
        "output_examples",
        "status",
        "chosen_repo_url",
    }
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return get_automation_project(project_id)

    assignments = ", ".join(f"{key} = ?" for key in updates)
    values = list(updates.values()) + [project_id]
    with _connect() as conn:
        conn.execute(
            f"""UPDATE automation_projects
                SET {assignments}, updated_at = datetime('now')
                WHERE id = ?""",
            values,
        )
    return get_automation_project(project_id)


def add_repo_candidate(
    project_id: int,
    url: str,
    notes: str = "",
    rank: int | None = None,
    fit_score: int | None = None,
    recommendation: str = "",
    license: str = "",
    stars: int | None = None,
    last_updated: str = "",
    language: str = "",
    analysis_json: str = "{}",
) -> dict:
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO automation_repo_candidates
               (project_id, url, notes, rank, fit_score, recommendation, license,
                stars, last_updated, language, analysis_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                project_id,
                url,
                notes,
                rank,
                fit_score,
                recommendation,
                license,
                stars,
                last_updated,
                language,
                analysis_json,
            ),
        )
        conn.execute(
            "UPDATE automation_projects SET updated_at = datetime('now') WHERE id = ?",
            (project_id,),
        )
        row = conn.execute(
            "SELECT * FROM automation_repo_candidates WHERE id = ?",
            (cur.lastrowid,),
        ).fetchone()
        return dict(row)


def list_repo_candidates(project_id: int) -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            """SELECT * FROM automation_repo_candidates
               WHERE project_id = ?
               ORDER BY COALESCE(rank, 999), created_at DESC""",
            (project_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def delete_repo_candidate(candidate_id: int, project_id: int) -> None:
    with _connect() as conn:
        conn.execute(
            "DELETE FROM automation_repo_candidates WHERE id = ? AND project_id = ?",
            (candidate_id, project_id),
        )
        conn.execute(
            "UPDATE automation_projects SET updated_at = datetime('now') WHERE id = ?",
            (project_id,),
        )


def next_execution_package_version(project_id: int) -> int:
    with _connect() as conn:
        row = conn.execute(
            "SELECT COALESCE(MAX(version), 0) AS max_version FROM execution_packages WHERE project_id = ?",
            (project_id,),
        ).fetchone()
        return int(row["max_version"]) + 1


def create_execution_package(
    project_id: int,
    title: str,
    content_md: str,
    readiness_score: int,
    readiness: dict,
    planning_mode: str = "quick",
) -> dict:
    version = next_execution_package_version(project_id)
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO execution_packages
               (project_id, version, title, content_md, readiness_score, readiness_json, planning_mode)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                project_id,
                version,
                title,
                content_md,
                readiness_score,
                json.dumps(readiness, default=str),
                planning_mode,
            ),
        )
        conn.execute(
            """UPDATE automation_projects
               SET status = CASE WHEN status = 'idea' THEN 'planned' ELSE status END,
                   updated_at = datetime('now')
               WHERE id = ?""",
            (project_id,),
        )
        row = conn.execute(
            "SELECT * FROM execution_packages WHERE id = ?",
            (cur.lastrowid,),
        ).fetchone()
        return dict(row)


def list_execution_packages(project_id: int) -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            """SELECT * FROM execution_packages
               WHERE project_id = ?
               ORDER BY version DESC""",
            (project_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def create_agent_update(
    project_id: int,
    agent: str,
    summary: str,
    changed_files: str = "",
    commands_run: str = "",
    test_result: str = "",
    blockers: str = "",
    next_step: str = "",
) -> dict:
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO agent_updates
               (project_id, agent, summary, changed_files, commands_run, test_result, blockers, next_step)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (project_id, agent, summary, changed_files, commands_run, test_result, blockers, next_step),
        )
        conn.execute(
            "UPDATE automation_projects SET updated_at = datetime('now') WHERE id = ?",
            (project_id,),
        )
        row = conn.execute(
            "SELECT * FROM agent_updates WHERE id = ?",
            (cur.lastrowid,),
        ).fetchone()
        return dict(row)


def list_agent_updates(project_id: int) -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            """SELECT * FROM agent_updates
               WHERE project_id = ?
               ORDER BY created_at DESC""",
            (project_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def create_eval_case(
    project_id: int,
    name: str,
    criteria: str,
    input_text: str = "",
    ideal_output: str = "",
    weight: float = 1.0,
) -> dict:
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO eval_cases
               (project_id, name, input_text, ideal_output, criteria, weight)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (project_id, name, input_text, ideal_output, criteria, weight),
        )
        conn.execute(
            "UPDATE automation_projects SET updated_at = datetime('now') WHERE id = ?",
            (project_id,),
        )
        row = conn.execute("SELECT * FROM eval_cases WHERE id = ?", (cur.lastrowid,)).fetchone()
        return dict(row)


def list_eval_cases(project_id: int) -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            """SELECT * FROM eval_cases
               WHERE project_id = ?
               ORDER BY created_at DESC""",
            (project_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_eval_case(case_id: int, project_id: int | None = None) -> dict | None:
    with _connect() as conn:
        if project_id is None:
            row = conn.execute("SELECT * FROM eval_cases WHERE id = ?", (case_id,)).fetchone()
        else:
            row = conn.execute(
                "SELECT * FROM eval_cases WHERE id = ? AND project_id = ?",
                (case_id, project_id),
            ).fetchone()
        return dict(row) if row else None


def delete_eval_case(case_id: int, project_id: int) -> None:
    with _connect() as conn:
        conn.execute(
            "DELETE FROM eval_cases WHERE id = ? AND project_id = ?",
            (case_id, project_id),
        )
        conn.execute(
            "UPDATE automation_projects SET updated_at = datetime('now') WHERE id = ?",
            (project_id,),
        )


def create_eval_result(
    eval_case_id: int,
    project_id: int,
    observed_output: str,
    score: int,
    verdict: str,
    reasoning: str,
    improvement_prompt: str = "",
) -> dict:
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO eval_results
               (eval_case_id, project_id, observed_output, score, verdict, reasoning, improvement_prompt)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (eval_case_id, project_id, observed_output, score, verdict, reasoning, improvement_prompt),
        )
        conn.execute(
            "UPDATE automation_projects SET updated_at = datetime('now') WHERE id = ?",
            (project_id,),
        )
        row = conn.execute("SELECT * FROM eval_results WHERE id = ?", (cur.lastrowid,)).fetchone()
        return dict(row)


def list_eval_results(project_id: int, eval_case_id: int | None = None) -> list[dict]:
    with _connect() as conn:
        if eval_case_id is None:
            rows = conn.execute(
                """SELECT * FROM eval_results
                   WHERE project_id = ?
                   ORDER BY created_at DESC""",
                (project_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT * FROM eval_results
                   WHERE project_id = ? AND eval_case_id = ?
                   ORDER BY created_at DESC""",
                (project_id, eval_case_id),
            ).fetchall()
        return [dict(r) for r in rows]


def get_project_eval_config(project_id: int) -> dict | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM project_eval_configs WHERE project_id = ?",
            (project_id,),
        ).fetchone()
        return dict(row) if row else None


def upsert_project_eval_config(
    project_id: int,
    workflow_id: str | None = None,
    eval_case_id: int | None = None,
    input_json: dict | None = None,
    deterministic_rules: dict | None = None,
    latest_output_ref: dict | None = None,
) -> dict:
    existing = get_project_eval_config(project_id)
    input_payload = input_json if input_json is not None else (
        json.loads(existing["input_json"]) if existing else {}
    )
    rules_payload = deterministic_rules if deterministic_rules is not None else (
        json.loads(existing["deterministic_rules_json"]) if existing else {}
    )
    output_payload = latest_output_ref if latest_output_ref is not None else (
        json.loads(existing["latest_output_ref_json"]) if existing else {}
    )
    next_workflow_id = workflow_id if workflow_id is not None else (existing["workflow_id"] if existing else None)
    next_eval_case_id = eval_case_id if eval_case_id is not None else (existing["eval_case_id"] if existing else None)

    with _connect() as conn:
        conn.execute(
            """INSERT INTO project_eval_configs
               (project_id, workflow_id, eval_case_id, input_json,
                deterministic_rules_json, latest_output_ref_json, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
               ON CONFLICT(project_id) DO UPDATE SET
                   workflow_id = excluded.workflow_id,
                   eval_case_id = excluded.eval_case_id,
                   input_json = excluded.input_json,
                   deterministic_rules_json = excluded.deterministic_rules_json,
                   latest_output_ref_json = excluded.latest_output_ref_json,
                   updated_at = excluded.updated_at""",
            (
                project_id,
                next_workflow_id,
                next_eval_case_id,
                json.dumps(input_payload, default=str),
                json.dumps(rules_payload, default=str),
                json.dumps(output_payload, default=str),
            ),
        )
        conn.execute(
            "UPDATE automation_projects SET updated_at = datetime('now') WHERE id = ?",
            (project_id,),
        )
    return get_project_eval_config(project_id) or {}


def create_project_eval_run(
    project_id: int,
    workflow_id: str | None,
    eval_case_id: int | None,
    workflow_run_id: int | None,
    eval_result_id: int | None,
    output_ref: dict,
    deterministic_checks: list[dict],
    deterministic_passed: int,
    deterministic_total: int,
    status: str,
    error: str | None = None,
) -> dict:
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO project_eval_runs
               (project_id, workflow_id, eval_case_id, workflow_run_id, eval_result_id,
                output_ref_json, deterministic_checks_json, deterministic_passed,
                deterministic_total, status, error)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                project_id,
                workflow_id,
                eval_case_id,
                workflow_run_id,
                eval_result_id,
                json.dumps(output_ref, default=str),
                json.dumps(deterministic_checks, default=str),
                deterministic_passed,
                deterministic_total,
                status,
                error,
            ),
        )
        conn.execute(
            "UPDATE automation_projects SET updated_at = datetime('now') WHERE id = ?",
            (project_id,),
        )
        row = conn.execute("SELECT * FROM project_eval_runs WHERE id = ?", (cur.lastrowid,)).fetchone()
        return dict(row)


def list_project_eval_runs(project_id: int, limit: int = 20) -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            """SELECT * FROM project_eval_runs
               WHERE project_id = ?
               ORDER BY created_at DESC, id DESC
               LIMIT ?""",
            (project_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]


def create_agent_job(
    name: str,
    workflow_id: str,
    cron_expr: str,
    inputs_json: str,
    client_id: str | None = None,
) -> dict:
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO agent_jobs (name, workflow_id, cron_expr, inputs_json, client_id)
               VALUES (?, ?, ?, ?, ?)""",
            (name, workflow_id, cron_expr, inputs_json, client_id),
        )
        row = conn.execute("SELECT * FROM agent_jobs WHERE id = ?", (cur.lastrowid,)).fetchone()
        return dict(row)


def list_agent_jobs() -> list[dict]:
    with _connect() as conn:
        rows = conn.execute("SELECT * FROM agent_jobs ORDER BY created_at DESC").fetchall()
        return [dict(r) for r in rows]


def get_agent_job(job_id: int) -> dict | None:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM agent_jobs WHERE id = ?", (job_id,)).fetchone()
        return dict(row) if row else None


def update_agent_job(job_id: int, **kwargs: Any) -> dict | None:
    allowed = {"name", "workflow_id", "cron_expr", "inputs_json", "client_id", "enabled", "last_run_at", "last_status"}
    updates = {k: v for k, v in kwargs.items() if k in allowed}
    if not updates:
        return get_agent_job(job_id)
    assignments = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [job_id]
    with _connect() as conn:
        conn.execute(f"UPDATE agent_jobs SET {assignments} WHERE id = ?", values)
    return get_agent_job(job_id)


def delete_agent_job(job_id: int) -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM agent_jobs WHERE id = ?", (job_id,))


if __name__ == "__main__":
    init_db()
    print(f"DB initialised at {DB_PATH}")
    run_id = log_run("test", "success", {"input": "hello"}, {"output": "world"}, None, 1.23, "claude-sonnet-4-6")
    print(f"Logged test run id={run_id}")
    runs = get_runs()
    print(f"Runs in DB: {len(runs)}")
    save_setting("sender_name", "Alex")
    print(f"Setting read back: {get_setting('sender_name')}")
    save_input_draft("test", {"company": "Stripe"})
    print(f"Draft read back: {get_input_draft('test')}")
    print("All checks passed.")
