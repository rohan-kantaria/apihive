# ApiHive — Phase 1: Foundation

Read `plan.md` fully before doing anything. It contains all architecture decisions,
data models, field names, and code sketches. Follow it exactly.

## Context

ApiHive is a free, self-hostable Postman alternative. Python + NiceGUI frontend,
MongoDB Atlas backend, httpx for HTTP calls, PyMiniRacer for JS script execution.

## Your job this iteration

Implement **Phase 1 — Foundation** only. Check every file listed below before writing it.
If it already exists and is partially correct, continue from where it left off.
Do NOT implement Phase 2–5 features.

### Files to create

**`requirements.txt`**
```
nicegui>=1.4
pymongo>=4.7
pydantic>=2.0
httpx>=0.27
python-dotenv>=1.0
py-mini-racer>=0.6
```

**`.env.example`**
```
MONGO_URI=mongodb+srv://user:pass@cluster.mongodb.net/
MONGO_DB=apihive
SSL_VERIFY=true
```

**`core/__init__.py`** — empty file

**`ui/__init__.py`** — empty file

**`core/models.py`**

Pydantic v2 models for all 4 MongoDB collections. Use the exact field names and
structures from plan.md's "Data Models" section:

- `Collection` — `_id` (str uuid), `name`, `auth` (dict), `variables` (dict),
  `pre_request_script` (str), `post_request_script` (str), `created_at` (float),
  `updated_at` (float)
- `Item` — `_id`, `collection_id`, `parent_id` (str | None), `type` (Literal["folder","request"]),
  `name`, `order` (int), `pre_request_script`, `post_request_script`,
  plus request-only fields: `method`, `url`, `params` (list[dict]), `headers` (list[dict]),
  `body` (dict with mode/raw/urlencoded), `auth` (dict)
- `Environment` — `_id`, `name`, `values` (dict[str, dict] with `value` and `enabled`),
  `updated_at`
- `Globals` — `_id` (always "global"), `values` (dict[str, dict])

All `_id` fields: use `Field(default_factory=lambda: str(uuid.uuid4()), alias="_id")`.
Configure models with `model_config = ConfigDict(populate_by_name=True)`.

**`core/db.py`**

MongoDB connection and CRUD. Use `pymongo` (synchronous). Expose:

```python
from pymongo import MongoClient
from pymongo.database import Database

def get_db() -> Database: ...
    # reads MONGO_URI and MONGO_DB from env
    # raises RuntimeError with clear message if MONGO_URI is missing

# Collections CRUD
def list_collections() -> list[dict]: ...
def create_collection(name: str) -> dict: ...
def update_collection(id: str, data: dict) -> None: ...
def delete_collection(id: str) -> None: ...
    # also deletes all items where collection_id == id

# Items CRUD
def list_items(collection_id: str) -> list[dict]: ...
def create_item(data: dict) -> dict: ...
def get_item(id: str) -> dict | None: ...
def update_item(id: str, data: dict) -> None: ...
def delete_item(id: str) -> None: ...
    # also recursively deletes all items where parent_id == id

# Environments CRUD
def list_environments() -> list[dict]: ...
def create_environment(name: str) -> dict: ...
def get_environment(id: str) -> dict | None: ...
def update_environment(id: str, values: dict) -> None: ...
def delete_environment(id: str) -> None: ...

# Globals
def get_globals() -> dict: ...
    # upserts {"_id": "global", "values": {}} if not exists, returns it

def update_globals(values: dict) -> None: ...

# Script chain
def get_script_chain(item_id: str) -> list[dict]:
    """
    Walks parent_id chain upward from item_id.
    Returns ordered list outermost → innermost:
    [
      {"pre": "...", "post": "...", "level": "collection"},
      {"pre": "...", "post": "...", "level": "folder"},   # 0 or more
      {"pre": "...", "post": "...", "level": "request"},
    ]
    """
```

**`core/script_runner.py`**

PyMiniRacer JS engine. Implement exactly as described in plan.md's "Script Engine" section.

```python
def run_pre_request(script: str, env_vars: dict) -> dict:
    # Returns: {"env_updates": {}, "console_output": [], "error": None | str}

def run_post_request(script: str, env_vars: dict, response_data: dict) -> dict:
    # response_data = {status, headers, body_text, body_json}
    # Returns: {"env_updates": {}, "console_output": [], "error": None | str}
```

JS preamble: inject `__logs`, `__env_updates`, `console.log`, `pm.environment.get/set`,
`pm.response` (None for pre-request), and `pm.sendRequest` using the two-phase model
described in plan.md. The script must end with:
`JSON.stringify({ env_updates: __env_updates, console_output: __logs })`

Two-phase `pm.sendRequest`:
- Phase 1: mock sendRequest captures request params, returns stub response
- Python bridge: execute real HTTP call with httpx (sync, since this is inside JS execution)
- Phase 2: re-run script with real response injected into sendRequest return value
- Use only Phase 2's env_updates and console_output

If PyMiniRacer raises an exception, return `{"env_updates": {}, "console_output": [], "error": str(e)}`.

**`core/variables.py`**

```python
import os
from dotenv import dotenv_values

def load_local_env() -> dict:
    """Load variables from .env file (not os.environ)."""
    return {k: v for k, v in dotenv_values(".env").items()
            if k not in ("MONGO_URI", "MONGO_DB", "SSL_VERIFY")}

def resolve(text: str, local_env: dict, active_env_values: dict, global_values: dict) -> str:
    """Replace {{key}} placeholders. Priority: local_env > active_env_values > global_values."""
    merged = {**global_values, **active_env_values, **local_env}
    for key, val_obj in merged.items():
        # val_obj may be a dict {"value": ..., "enabled": true} or a plain string
        if isinstance(val_obj, dict):
            if not val_obj.get("enabled", True):
                continue
            val = str(val_obj.get("value", ""))
        else:
            val = str(val_obj)
        text = text.replace(f"{{{{{key}}}}}", val)
    return text
```

**`app.py`**

```python
from dotenv import load_dotenv
load_dotenv()  # must be first

import os
from nicegui import ui, app
from core.db import get_db

@ui.page('/')
async def index():
    # temporary placeholder — replaced in Phase 2
    with ui.column().classes('w-full h-screen items-center justify-center'):
        ui.label('ApiHive').classes('text-3xl font-bold')
        ui.label('Phase 1 — Foundation').classes('text-gray-500')

def main():
    try:
        db = get_db()
        db.command('ping')
    except Exception as e:
        print(f"[ApiHive] MongoDB connection failed: {e}")
        raise SystemExit(1)

    ssl_verify = os.getenv("SSL_VERIFY", "true").lower() != "false"
    app.state.ssl_verify = ssl_verify

    ui.run(title='ApiHive', port=8080, reload=False)

if __name__ == '__main__':
    main()
```

## Git Commits

The working directory for all git commands is:
`C:/Users/rohan/Desktop/personal_projects/claude_projects/apihive`

Commit and push at each of the following milestones — do not batch them all at the end.
Use the exact commands below (adjust staged files as needed):

```bash
cd /c/Users/rohan/Desktop/personal_projects/claude_projects/apihive

# After core/models.py and core/db.py are complete and correct:
git add core/__init__.py core/models.py core/db.py
git commit -m "feat(phase1): add Pydantic models and MongoDB CRUD layer"
git push

# After core/script_runner.py and core/variables.py are complete:
git add core/script_runner.py core/variables.py
git commit -m "feat(phase1): add JS script runner (PyMiniRacer) and variable resolver"
git push

# After app.py is complete and python app.py starts without errors:
git add requirements.txt .env.example ui/__init__.py app.py
git commit -m "feat(phase1): foundation complete — app starts and connects to MongoDB"
git push
```

## Done when

- All files above exist and are complete
- `python app.py` starts without errors
- MongoDB ping succeeds (or a clear `RuntimeError` is raised if `MONGO_URI` is missing,
  not a traceback)
- `get_script_chain()` returns the correct outermost→innermost ordered list
- `run_pre_request` and `run_post_request` return the correct dict shape

When you are confident Phase 1 is fully implemented and correct, return control to PROMPT_master.md — the master orchestrator will advance to Phase 2.
