# ApiHive — Phase 5: Import & Multi-Tab

Read `plan.md` fully before doing anything. Pay attention to:
- "Postman Import" section
- "Multi-Tab State" section
- Verification Plan items 9, 10, 12, 15

## Prerequisites

Phases 1–4 must be complete. If any earlier file is missing or broken, fix it first.

## Your job this iteration

Implement **Phase 5 — Postman Import & Multi-Tab**. Check every file before writing it.
If it already exists and is partially correct, continue from where it left off.
This is the final phase — after it is done, all MVP features are complete.

### Files to create / update

**`core/importer.py`**

Postman v2.1 collection importer. Converts `.postman_collection.json` → MongoDB documents.

```python
import json, uuid
from core import db

def import_postman_v21(filepath: str) -> dict:
    """
    Parses a Postman v2.1 collection JSON file and inserts into MongoDB.
    Returns: {"collection_id": str, "imported_count": int, "errors": list[str]}
    """
```

**Postman v2.1 structure you must handle:**

```json
{
  "info": { "name": "...", "_postman_id": "..." },
  "item": [ ... ],
  "event": [ ... ],
  "variable": [ ... ]
}
```

Mapping rules (follow plan.md exactly):

**Collection level:**
- Create a `collections` document with `name = info.name`
- Parse `event` array at collection root:
  - `"listen": "prerequest"` → `pre_request_script` (join `exec` list with `\n`)
  - `"listen": "test"` → `post_request_script`
- Parse `variable` array → `variables` dict: `{v["key"]: {"value": v["value"], "enabled": not v.get("disabled", False)}}`

**Items (recursive):**
Each element in `item` array is either a folder (has `item` key) or a request (has `request` key).

For **folders:**
- `type = "folder"`
- `name = item["name"]`
- Parse `event` array same as collection level → `pre_request_script`, `post_request_script`
- Recurse into `item["item"]` with this folder as parent

For **requests:**
- `type = "request"`
- `name = item["name"]`
- Parse `event` → `pre_request_script`, `post_request_script`
- `method = item["request"]["method"]`
- `url`: Postman url can be a string or an object:
  ```python
  url_obj = item["request"].get("url", {})
  if isinstance(url_obj, str):
      url = url_obj
  else:
      url = url_obj.get("raw", "")
  ```
- `params`: from `url_obj.get("query", [])` → `[{"key": q["key"], "value": q["value"], "enabled": not q.get("disabled", False)}]`
- `headers`: from `item["request"].get("header", [])` → same shape
- `body`: from `item["request"].get("body", {})`:
  - `mode = body.get("mode", "none")`  (Postman uses "raw", "urlencoded", "formdata", "none")
  - If `mode == "raw"`: `raw = body.get("raw", "")`
  - If `mode == "urlencoded"`: `urlencoded = [{"key": f["key"], "value": f["value"], "enabled": not f.get("disabled", False)} for f in body.get("urlencoded", [])]`
  - `formdata` and other modes: treat as `none` for MVP
- `auth`: from `item["request"].get("auth", {"type": "none"})`
- `order`: use enumerate index

Assign `order` based on position in parent's `item` list.
Generate new UUIDs for all `_id` fields — do NOT use Postman's original IDs.

Handle malformed input gracefully: catch per-item exceptions, append to `errors`, continue.

**`ui/settings.py`**

Settings dialog (or page) that includes:
- SSL verification toggle (global, persisted in `app.state.ssl_verify`)
- "Manage Environments" button → calls `open_env_manager()`
- "Import Postman Collection" button → calls `open_import_dialog()`

```python
def build_settings_panel(): ...
```

**`ui/layout.py`** — wire Import button

Replace the `ui.notify('Import — Phase 5')` placeholder:

```python
from ui.importer_dialog import open_import_dialog
ui.button('Import', on_click=open_import_dialog)
```

**`ui/importer_dialog.py`** (new small file)

```python
from nicegui import ui
from core.importer import import_postman_v21
from ui.sidebar import refresh_tree

def open_import_dialog():
    with ui.dialog() as dialog, ui.card().classes('w-96'):
        ui.label('Import Postman Collection').classes('text-lg font-bold')
        ui.label('Select a .postman_collection.json file')

        file_path_input = ui.input('File path', placeholder='/path/to/collection.json').classes('w-full')
        status_label = ui.label('').classes('text-sm')

        async def do_import():
            path = file_path_input.value.strip()
            if not path:
                status_label.set_text('Please enter a file path')
                return
            try:
                result = import_postman_v21(path)
                status_label.set_text(
                    f"Imported {result['imported_count']} items. "
                    + (f"{len(result['errors'])} errors." if result['errors'] else "")
                )
                refresh_tree()
                await asyncio.sleep(1.5)
                dialog.close()
            except Exception as e:
                status_label.set_text(f'Error: {e}')

        with ui.row():
            ui.button('Import', on_click=do_import)
            ui.button('Cancel', on_click=dialog.close)

    dialog.open()
```

**`ui/request_tabs.py`** — complete the multi-tab implementation

Ensure all of the following work correctly:

- `open_request_tab(item_id)`: if item already open, focus its tab; otherwise add new tab
- Tab state persisted in `app.storage.user["open_tabs"]` — list of `{"item_id", "label", "dirty"}`
- Closing a tab (× button): removes from list, switches to nearest remaining tab
- If no tabs remain: show the welcome message
- Tab labels: request name, with unsaved indicator if `dirty = True` (e.g., "Get User •")
- Max 10 tabs open simultaneously; if exceeded, close the oldest

Verify tab state survives a page refresh (NiceGUI `app.storage.user` is session-persistent).

**Auto-save behaviour (request_builder.py)** — verify from Phase 3

Each debounced save should set `dirty = False` on the corresponding tab entry.
On unsaved changes (before debounce fires), set `dirty = True`.

## Git Commits

The working directory for all git commands is:
`C:/Users/rohan/Desktop/personal_projects/claude_projects/apihive`

Commit and push at each of the following milestones — do not batch them all at the end.

```bash
cd /c/Users/rohan/Desktop/personal_projects/claude_projects/apihive

# After core/importer.py is complete and handles collections, folders, requests, and events:
git add core/importer.py
git commit -m "feat(phase5): add Postman v2.1 collection importer with recursive item and event parsing"
git push

# After ui/importer_dialog.py, ui/settings.py, and layout.py Import button are wired:
git add ui/importer_dialog.py ui/settings.py ui/layout.py
git commit -m "feat(phase5): add import dialog, settings panel, and wire Import button in top bar"
git push

# After ui/request_tabs.py multi-tab is fully complete (close, dirty flag, max 10, session persistence):
git add ui/request_tabs.py ui/request_builder.py
git commit -m "feat(phase5): complete multi-tab — close, dirty indicator, max 10 tabs, session persistence"
git push

# After all 15 verification items pass (final MVP commit):
git add -A
git commit -m "feat: ApiHive MVP complete — all 15 verification items passing"
git push
```

## Done when

Verify these scenarios from plan.md's Verification Plan:

9.  "Import test": Import a `.postman_collection.json` with `prerequest`/`test` events
    → scripts appear in the script editors, tree matches original structure, `order` preserved
10. "Send request": Select an imported GET request → Send → response appears with correct JSON
12. "Multi-tab": Open 3 different requests in tabs → switch between them → state is preserved;
    close one → others unaffected; reopen → loads fresh from DB
13. "SSL toggle": SSL toggle in Settings → updates `app.state.ssl_verify` → affects subsequent requests
15. "CRUD": Create collection, add folder, add request, delete folder → tree updates correctly

**Final full-app smoke test (run through all 15 items in plan.md Verification Plan):**
- Items 1–8: covered by Phases 1–3
- Items 11, 14, 16: covered by Phase 4
- Items 9, 10, 12, 13, 15: covered by Phase 5

The app is MVP-complete when all 15 verification items pass.

When you are confident Phase 5 is fully implemented and correct, output exactly:

<promise>PHASE 5 COMPLETE</promise>
