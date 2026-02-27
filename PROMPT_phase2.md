# ApiHive — Phase 2: Collections & CRUD

Read `plan.md` fully before doing anything. It contains all architecture decisions,
layout specs, and UI component choices. Follow it exactly.

## Prerequisites

Phase 1 must be complete:
- `core/db.py`, `core/models.py`, `core/script_runner.py`, `core/variables.py` exist
- `app.py` starts and connects to MongoDB

If any Phase 1 file is missing or broken, fix it before proceeding.

## Your job this iteration

Implement **Phase 2 — Collections & CRUD**. Check every file before writing it.
If it already exists and is partially correct, continue from where it left off.
Do NOT implement HTTP request execution (Phase 3) or environments (Phase 4).

### Files to create / update

**`ui/layout.py`**

Top-level NiceGUI layout. Renders:
- Top bar (header row):
  `[ApiHive logo]  ←→  [Environment: None ▼] [SSL: ON] [Import] [Settings]`
  - Environment dropdown: placeholder for now (populated in Phase 4)
  - SSL toggle: reads `app.state.ssl_verify`, calls `toggle_ssl()` on click
  - Import button: placeholder (wired in Phase 5)
  - Settings button: placeholder
- Two-column body: left sidebar (fixed ~280px wide) + right main area (flex-grow)
- Exports `build_layout()` async function called from `app.py`

```python
from nicegui import ui, app as nicegui_app

async def build_layout():
    with ui.header().classes('items-center justify-between px-4 py-2 bg-gray-900 text-white'):
        ui.label('ApiHive').classes('text-xl font-bold text-white')
        with ui.row().classes('items-center gap-4'):
            # env dropdown placeholder — replaced in Phase 4
            ui.select(options=['No Environment'], value='No Environment').classes('w-48')
            # ssl toggle
            ssl_label = ui.label('SSL: ON' if nicegui_app.state.ssl_verify else 'SSL: OFF')
            # import / settings buttons
            ui.button('Import', on_click=lambda: ui.notify('Import — Phase 5'))
            ui.button('Settings', on_click=lambda: ui.notify('Settings — coming soon'))

    with ui.row().classes('w-full flex-grow overflow-hidden'):
        # sidebar
        with ui.column().classes('w-72 border-r border-gray-200 h-full overflow-y-auto p-2'):
            from ui.sidebar import build_sidebar
            await build_sidebar()
        # main area
        with ui.column().classes('flex-grow h-full overflow-hidden p-2'):
            from ui.request_tabs import build_request_tabs
            await build_request_tabs()
```

Update `app.py` to call `build_layout()` and remove the placeholder content.

**`ui/sidebar.py`**

Collection tree using `ui.tree`. Key behaviours:

- On mount: load all collections from `db.list_collections()`, then for each collection
  load its items from `db.list_items(collection_id)`. Build the tree structure in memory.
- Tree node shape for `ui.tree`:
  ```python
  {"id": str, "label": str, "type": "collection|folder|request", "children": [...]}
  ```
- Use `ui.tree` with `node_key="id"` and `label_key="label"`.
- **Right-click context menus** (use `ui.context_menu` inside each node's slot):
  - Collection node: "Add Folder", "Add Request", "Edit Scripts", "Delete Collection"
  - Folder node: "Add Request", "Edit Scripts", "Rename", "Delete Folder"
  - Request node: "Rename", "Duplicate", "Delete"
- **Double-click** a request node → call `open_request_tab(item_id)` (imported from `ui/request_tabs.py`)
- After any CRUD operation, call `refresh_tree()` to reload from DB and redraw.

**Add Folder / Add Request dialogs:**
Simple `ui.dialog` with a single `ui.input` for the name and a confirm button.
On confirm, call the appropriate `db.create_*` function, then `refresh_tree()`.

**Delete dialogs:**
Confirm dialog: "Are you sure? This will delete all children." On confirm, call `db.delete_*`.

**Rename:**
Inline or dialog — either is fine. On confirm, call `db.update_item` with new name.

**Duplicate:**
Copy the item dict, clear `_id` (generate new uuid), insert via `db.create_item`.

**Edit Scripts dialog** (collections and folders):
```
ui.dialog (large, ~800px wide)
  Title: "Edit: {name}"
  ui.tabs: [Pre-request Script] [Post-request Script]
  ui.tab_panels:
    each panel: ui.codemirror(language='javascript', value=current_script)
  [Save] [Cancel] buttons
```
On Save: call `db.update_collection` or `db.update_item` with updated script fields.

Export:
```python
async def build_sidebar(): ...
def refresh_tree(): ...  # callable from other modules
```

**`ui/request_tabs.py`**

Tab bar in the main panel. Initially shows a welcome placeholder.

- Maintains `_open_tabs: list[dict]` in `app.storage.user` (per-session).
  Each entry: `{"item_id": str, "label": str, "dirty": bool}`
- `open_request_tab(item_id)`: if already open, switch to it; otherwise load item from DB
  and add a new tab.
- Renders `ui.tabs` + `ui.tab_panels` horizontally.
- Each tab panel: renders `ui.request_builder.build_request_builder(item)` (placeholder for Phase 3).
- Close tab button (×) on each tab label.
- If no tabs open: show a centered "Double-click a request to open it" message.

Export:
```python
async def build_request_tabs(): ...
def open_request_tab(item_id: str): ...
```

**`ui/request_builder.py`** — stub only (fleshed out in Phase 3)

```python
from nicegui import ui

def build_request_builder(item: dict):
    """Placeholder — implemented in Phase 3."""
    with ui.column().classes('w-full gap-2'):
        ui.label(f"{item.get('method','GET')}  {item.get('url','')}")
            .classes('text-gray-400 font-mono text-sm')
        ui.label('Request builder — coming in Phase 3').classes('text-gray-400')
```

**`ui/response_viewer.py`** — stub only (fleshed out in Phase 3)

```python
from nicegui import ui

def build_response_viewer():
    """Placeholder — implemented in Phase 3."""
    ui.label('Response viewer — coming in Phase 3').classes('text-gray-400')
```

## Git Commits

The working directory for all git commands is:
`C:/Users/rohan/Desktop/personal_projects/claude_projects/apihive`

Commit and push at each of the following milestones — do not batch them all at the end.

```bash
cd /c/Users/rohan/Desktop/personal_projects/claude_projects/apihive

# After ui/layout.py is complete and app.py is updated to use build_layout():
git add ui/__init__.py ui/layout.py app.py
git commit -m "feat(phase2): add top-bar layout with env dropdown, SSL toggle, and sidebar/main split"
git push

# After ui/sidebar.py is complete with full CRUD and context menus:
git add ui/sidebar.py
git commit -m "feat(phase2): add collection tree with CRUD, context menus, and script editors"
git push

# After ui/request_tabs.py, ui/request_builder.py stub, and ui/response_viewer.py stub are complete:
git add ui/request_tabs.py ui/request_builder.py ui/response_viewer.py
git commit -m "feat(phase2): add request tab bar with open/close and builder/viewer stubs"
git push
```

## Done when

- `python app.py` → browser shows top bar + sidebar + main area layout
- Collections can be created, renamed, deleted from the sidebar
- Folders can be created inside collections, renamed, deleted
- Requests can be created inside collections/folders, renamed, duplicated, deleted
- Double-clicking a request opens it as a tab in the main panel
- Collection and folder Edit Scripts dialogs open and save pre/post scripts to MongoDB
- Tree refreshes correctly after every CRUD operation

When you are confident Phase 2 is fully implemented and correct, return control to PROMPT_master.md — the master orchestrator will advance to Phase 3.
