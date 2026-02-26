# ApiHive — Phase 4: Environments & Variables

Read `plan.md` fully before doing anything. Pay attention to:
- "Data Models" → environments and globals schemas
- "Variable Resolution" section
- "Top Bar Layout" section (environment dropdown)
- Verification Plan items 11, 14

## Prerequisites

Phases 1–3 must be complete. If any earlier file is missing or broken, fix it first.
Specifically, `core/variables.py` and `core/db.py` environment functions must work.

## Your job this iteration

Implement **Phase 4 — Environments & Variables**. Check every file before writing it.
If it already exists and is partially correct, continue from where it left off.

### Files to create / update

**`ui/env_manager.py`**

Full environment CRUD panel, opened as a modal dialog from a toolbar button.

```
┌─ Manage Environments ──────────────────────────────────┐
│ Environments          │ Edit: Dev                      │
│ ─────────────────     │ Name: [Dev              ]      │
│ > Dev          [✓]    │                                │
│   Staging             │ Variables:                     │
│   Production          │ ┌─────────────┬──────────────┐ │
│                       │ │ Key         │ Value        │ │
│ [+ New Env]           │ ├─────────────┼──────────────┤ │
│ [Delete]              │ │ base_url    │ https://...  │ │
│                       │ │ token       │ eyJ...       │ │
│                       │ │ [+ Add row] │              │ │
│                       │ └─────────────┴──────────────┘ │
│                       │ [Save]  [Cancel]               │
└────────────────────────────────────────────────────────┘
```

Behaviour:
- Left panel: list of environments from `db.list_environments()`
- Active environment: shown with a checkmark `✓` next to its name
- Clicking an env selects it for editing (right panel)
- "✓ Activate" button: sets the selected env as active (stored in `app.storage.user["active_env_id"]`)
- "New Environment" button: dialog asking for a name → `db.create_environment(name)` → refresh list
- "Delete" button: confirms deletion → `db.delete_environment(id)` → refresh list
- Right panel (variable editor):
  - Each variable row: Enabled checkbox, Key input, Value input, Delete row button
  - "+ Add variable" button adds a new empty row
  - "Save" button: calls `db.update_environment(id, values_dict)`

Also expose a `Globals` section (can be a separate tab or section within the dialog):
- Edit global key-value pairs via `db.get_globals()` / `db.update_globals()`
- Same key/value table UI as environments

Export:
```python
def open_env_manager(): ...   # opens the dialog
```

**`ui/layout.py`** — update the environment dropdown in the top bar

Replace the placeholder dropdown with a real implementation:

```python
# Load environments on page mount
envs = db.list_environments()
env_options = {"": "No Environment"} | {e["_id"]: e["name"] for e in envs}
active_id = app.storage.user.get("active_env_id", "")

env_select = ui.select(
    options=env_options,
    value=active_id,
    label="Environment",
    on_change=lambda e: app.storage.user.update({"active_env_id": e.value})
).classes('w-48')
```

Also wire the "Settings" button to open a `ui.dialog` or separate page that includes:
- A "Manage Environments" button that calls `open_env_manager()`
- The global variables editor

The env dropdown must reflect the currently active environment name.
When the user switches environments, all subsequent request executions use the new one.

**`core/variables.py`** — verify / complete

Ensure `resolve()` correctly handles:
- `enabled: false` variables: skip them
- Values from all three sources: `local_env` (plain strings from .env) >
  `active_env_values` (dicts with `value`/`enabled`) > `global_values` (dicts with `value`/`enabled`)
- Nested `{{vars}}` in values: do NOT recursively resolve (one pass only)

Add:
```python
def get_active_env_values(active_env_id: str | None) -> dict:
    """Returns the values dict from the active environment, or {} if none."""
    if not active_env_id:
        return {}
    env = db.get_environment(active_env_id)
    return env["values"] if env else {}

def get_global_values() -> dict:
    """Returns the values dict from the globals document."""
    g = db.get_globals()
    return g.get("values", {})
```

**`core/http_client.py`** — update to use active env and globals

Replace any hardcoded empty dicts with calls to:
```python
from core.variables import load_local_env, get_active_env_values, get_global_values

local_env = load_local_env()
active_env_values = get_active_env_values(active_env_id)
global_values = get_global_values()
```

Pass all three to `variables.resolve()`.

**`ui/request_builder.py`** — variable preview

In the URL input row, add a small label below it that shows the resolved URL in real time
as the user types, using the currently active environment:

```python
resolved_label = ui.label('').classes('text-xs text-gray-400 font-mono')

def update_resolved(url: str):
    from nicegui import app as nicegui_app
    from core.variables import resolve, load_local_env, get_active_env_values, get_global_values
    active_env_id = nicegui_app.storage.user.get("active_env_id")
    resolved = resolve(url, load_local_env(), get_active_env_values(active_env_id), get_global_values())
    resolved_label.set_text(resolved if '{{' in url else '')

url_input.on('input', lambda e: update_resolved(e.value))
```

## Git Commits

The working directory for all git commands is:
`C:/Users/rohan/Desktop/personal_projects/claude_projects/apihive`

Commit and push at each of the following milestones — do not batch them all at the end.

```bash
cd /c/Users/rohan/Desktop/personal_projects/claude_projects/apihive

# After ui/env_manager.py is complete with full environment CRUD and globals editor:
git add ui/env_manager.py
git commit -m "feat(phase4): add environment manager dialog with variable CRUD and globals editor"
git push

# After layout.py env dropdown is live and variables.py is updated with helper functions:
git add ui/layout.py core/variables.py core/http_client.py ui/request_builder.py
git commit -m "feat(phase4): wire active environment into top bar, request execution, and URL preview"
git push
```

## Done when

Verify these scenarios from plan.md's Verification Plan:

11. "Variable substitution": Set `base_url` in an environment → activate it → URL resolves correctly
    in both the resolved preview label and in actual request execution
12. "Send request with env vars": Active env has `base_url` → GET `{{base_url}}/health` → sends to correct URL
13. "Environment CRUD": Create environment, add 3 variables, save, reopen dialog → variables persist
14. "Team sync": Two browser sessions → User A edits environment and saves → User B switches to
    that environment → sees updated variable values (note: User B must re-select or refresh)
15. "Globals": Set a global var `api_version=v1` → it resolves in requests (lowest priority)
16. "Env priority": Same key in globals, active env, and local .env → local .env value wins

When you are confident Phase 4 is fully implemented and correct, output exactly:

<promise>PHASE 4 COMPLETE</promise>
