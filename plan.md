# Plan: ApiHive — Python API Collaboration Client

## Context

The team uses Postman for API testing but is blocked by two problems: (1) Postman's Teams feature costs money, and (2) corporate software installation policies (SNOW) block installing Postman on some machines. The goal is a **free, self-hostable, Postman-like API client** that runs as a local Python script and stores shared collections/environments in a MongoDB Atlas free tier, giving the whole team (5–15 people) a synchronized source of truth without any licensing costs.

---

## Architecture Decisions

| Decision | Choice | Reason |
|---|---|---|
| UI Framework | **NiceGUI** (browser-based) | Pure Python, has tree/tab/split-pane components, Postman-like UX, `python app.py` startup |
| Database | **MongoDB Atlas free tier** | No Docker required, connection string in local `.env`, 512MB plenty for medium team |
| HTTP client | **httpx** (async) | Supports form-urlencoded and JSON bodies |
| Script runtime | **PyMiniRacer** (`py-mini-racer`) | Embeds V8 for JS execution; Postman-compatible scripts |
| Real-time sync | **None** (on-interaction refresh) | Not required; team can refresh manually |
| User identity | **None** (anonymous) | Small trusted team, no audit log needed |
| Secret storage | **Plaintext in MongoDB** | Internal tool, team is trusted |
| SSL verification | **Global toggle** in settings | Some internal APIs use self-signed certs |
| Variable priority | **Local .env > Active Env > Global** | Standard Postman order |
| Multi-tab | **Required** | Users need multiple requests open simultaneously |
| Env switching | **Dropdown in top bar** | Global, persistent environment selector |

---

## MVP Features

1. Full CRUD — collections, folders, requests (create/edit/delete in UI)
2. Import Postman `.postman_collection.json` v2.1 (including scripts)
3. Send requests (GET/POST/PUT/DELETE/PATCH) + view JSON response (pretty-printed)
4. Body types: none, raw JSON, form-urlencoded; query params; headers
5. Shared environments stored in Atlas, variable substitution (`{{variable}}`)
6. Multi-tab request builder (multiple requests open at once, within a single browser tab)
7. Environment dropdown in top bar
8. **Pre-request scripts** (JavaScript, runs before HTTP call) — Collection → Folder → Request order
9. **Post-request scripts** (JavaScript, runs after HTTP call) — Collection → Folder → Request order
10. Global SSL verification toggle
11. Local `.env` variable overrides (highest priority in resolution)

## Post-MVP (explicitly deferred)

- Auto-background token refresh heartbeat
- Export to `.postman_collection.json`
- Request history / response logging
- Image and PDF response rendering
- Auth inheritance from parent folder
- `pm.request` modification in pre-request scripts
- Test assertions (`pm.test`)

---

## Project Structure

```
apihive/
├── app.py                   # NiceGUI entry point, layout assembly
├── .env                     # Local: MONGO_URI, MONGO_DB, SSL_VERIFY (gitignored)
├── .env.example             # Template for new team members
├── requirements.txt
├── core/
│   ├── db.py               # MongoDB connection + CRUD wrappers (PyMongo) + get_script_chain()
│   ├── models.py           # Pydantic v2 models for all documents
│   ├── http_client.py      # httpx request executor (async) + script orchestration
│   ├── variables.py        # Variable resolution: local .env > active env > global
│   ├── script_runner.py    # PyMiniRacer JS engine; pm object builder; two-phase sendRequest
│   └── importer.py         # Postman v2.1 JSON → MongoDB import (incl. event scripts)
├── ui/
│   ├── layout.py           # Top-level NiceGUI layout (header + sidebar + main)
│   ├── sidebar.py          # Collection tree (ui.tree), context menus, script editors for collections/folders
│   ├── request_tabs.py     # Tab bar + per-tab request builder state
│   ├── request_builder.py  # URL, method, params, headers, body, pre/post-script editor panels
│   ├── response_viewer.py  # Response status, headers, JSON pretty-print, Console tab
│   ├── env_manager.py      # Environment CRUD dialog/panel
│   └── settings.py         # Global settings (SSL toggle, import/export)
```

---

## Data Models (MongoDB)

### `collections`
```json
{
  "_id": "uuid",
  "name": "Project Alpha API",
  "auth": { "type": "none" },
  "variables": {},
  "pre_request_script": "// collection-level pre-request JS",
  "post_request_script": "// collection-level post-request JS",
  "created_at": 1700000000.0,
  "updated_at": 1700000000.0
}
```

### `items` (unified folders + requests, maps cleanly to Postman v2.1)
```json
{
  "_id": "uuid",
  "collection_id": "uuid",
  "parent_id": "uuid_or_null",
  "type": "folder | request",
  "name": "Get User Profile",
  "order": 0,
  "pre_request_script": "// JS code",
  "post_request_script": "// JS code",

  // request-only fields:
  "method": "GET",
  "url": "{{base_url}}/users/{{user_id}}",
  "params": [{ "key": "page", "value": "1", "enabled": true }],
  "headers": [{ "key": "Authorization", "value": "Bearer {{token}}", "enabled": true }],
  "body": {
    "mode": "none | raw | urlencoded",
    "raw": "{ \"key\": \"value\" }",
    "urlencoded": [{ "key": "grant_type", "value": "client_credentials", "enabled": true }]
  },
  "auth": { "type": "bearer", "token": "{{token}}" }

  // NOTE: post_response field is intentionally absent — token extraction is done via post-request scripts
}
```

### `environments`
```json
{
  "_id": "uuid",
  "name": "Dev",
  "values": {
    "base_url": { "value": "https://dev.api.com", "enabled": true },
    "token": { "value": "eyJ...", "enabled": true }
  },
  "updated_at": 1700000000.0
}
```

### `globals`
```json
{
  "_id": "global",
  "values": {
    "api_version": { "value": "v1", "enabled": true }
  }
}
```

---

## Key Implementation Details

### Variable Resolution (`core/variables.py`)
```python
def resolve(text: str, local_env: dict, active_env_values: dict, global_values: dict) -> str:
    merged = {**global_values, **active_env_values, **local_env}
    for key, val in merged.items():
        text = text.replace(f"{{{{{key}}}}}", str(val))
    return text
```
`local_env` is loaded from the user's `.env` file via `python-dotenv` at startup.

---

### Script Engine (`core/script_runner.py`)

Uses **PyMiniRacer** (Google V8 embedded in Python via `py-mini-racer`).

#### `pm` API available to scripts (MVP)

| API | Available in pre-request | Available in post-request |
|---|---|---|
| `pm.environment.get(key)` | ✅ | ✅ |
| `pm.environment.set(key, value)` | ✅ | ✅ |
| `pm.response.json()` | ❌ | ✅ |
| `pm.response.text()` | ❌ | ✅ |
| `pm.response.status` / `.statusCode` | ❌ | ✅ |
| `pm.response.headers` | ❌ | ✅ |
| `pm.sendRequest(opts)` | ✅ | ✅ |
| `console.log(...)` | ✅ | ✅ |

#### JS Preamble (injected before user script)
```javascript
var __logs = [];
var __env_updates = {};
var console = {
  log: function() {
    __logs.push(Array.prototype.slice.call(arguments)
      .map(function(a){ return typeof a === 'object' ? JSON.stringify(a) : String(a); })
      .join(' '));
  }
};
var pm = {
  environment: {
    _vars: <JSON.stringify(env_vars)>,
    get: function(key) { return this._vars[key] || null; },
    set: function(key, value) {
      this._vars[key] = String(value);
      __env_updates[key] = String(value);
    }
  },
  response: <JSON.stringify(response_obj) or undefined for pre-request>,
  sendRequest: <see two-phase implementation below>
};
// --- user script ---
<user_script>
// --- return ---
JSON.stringify({ env_updates: __env_updates, console_output: __logs });
```

#### `pm.response` shape (post-request only)
```javascript
pm.response = {
  status: 200,
  statusCode: 200,
  headers: { "Content-Type": "application/json" },
  text: function() { return "<raw body string>"; },
  json: function() { return <parsed JSON object or null>; }
};
```

#### `pm.sendRequest` — Two-Phase Execution Model

PyMiniRacer (V8 sandbox) has no network access, so HTTP calls are bridged back to Python:

**Phase 1 (Detection):** Run script with mock `pm.sendRequest` that captures request params and returns a mock response `{ json: ()=>{}, text: ()=>'', status: 0 }`. Detect if/what HTTP call was requested.

**Python bridge:** Execute the captured HTTP request using `httpx`.

**Phase 2 (Real run):** Re-run the full script with `pm.sendRequest` returning the real response. Only Phase 2's `env_updates` and `console_output` are used.

**Synchronous API (simpler than Postman's callback style):**
```javascript
// Pre-request script example — fetch a JWT token before the main request
var resp = pm.sendRequest({
  url: pm.environment.get('auth_url'),
  method: 'POST',
  header: [{ key: 'Content-Type', value: 'application/x-www-form-urlencoded' }],
  body: {
    mode: 'urlencoded',
    urlencoded: [
      { key: 'grant_type', value: 'client_credentials' },
      { key: 'client_id', value: pm.environment.get('client_id') },
      { key: 'client_secret', value: pm.environment.get('client_secret') }
    ]
  }
});
pm.environment.set('token', resp.json().access_token);
```

#### Python interface
```python
# core/script_runner.py

def run_pre_request(script: str, env_vars: dict) -> dict:
    # Returns: { "env_updates": {}, "console_output": [], "error": None }

def run_post_request(script: str, env_vars: dict, response_data: dict) -> dict:
    # response_data = { status, headers, body_text, body_json }
    # Returns: { "env_updates": {}, "console_output": [], "error": None }
```

---

### Script Chain Resolution (`core/db.py`)

```python
def get_script_chain(item_id: str, db) -> list[dict]:
    """
    Walks parent_id chain upward to collect scripts from all ancestor levels.
    Returns ordered list outermost → innermost:
    [
      { "pre": "...", "post": "...", "level": "collection" },
      { "pre": "...", "post": "...", "level": "folder" },   # 0 or more
      { "pre": "...", "post": "...", "level": "request" },
    ]
    """
```

---

### HTTP Client Execution Flow (`core/http_client.py`)

```
1.  get_script_chain(item_id)          → ordered list of pre/post scripts
2.  Resolve env_vars (local .env > active env > global)
3.  For each level (collection → folder → request):
      result = run_pre_request(script, current_env_vars)
      if result.error  →  ABORT: return { error, console_output }
      merge result.env_updates into current_env_vars
      append result.console_output (prefixed with [level])
4.  Resolve {{variables}} in URL/headers/params/body using final env_vars
5.  Send HTTP request via httpx (async)
6.  Build response_data dict { status, headers, body_text, body_json }
7.  For each level (collection → folder → request):
      result = run_post_request(script, current_env_vars, response_data)
      merge result.env_updates into current_env_vars
      append result.console_output (prefixed with [level])
      (errors: append to console_output as [level][ERROR], do NOT abort)
8.  Persist all accumulated env_updates to active environment in MongoDB
9.  Return: { response_data, console_output, script_error }
```

---

### Pre-request Script Error Handling

- **Pre-request error** → abort HTTP request, show error in Console tab (no Body/Headers tabs populated)
- **Post-request error** → log in Console tab, Body/Headers still visible (request already completed)

---

### Request Builder UI (`ui/request_builder.py`)

Tabs in the request builder:
```
[ Params ] [ Headers ] [ Body ] [ Pre-request Script ] [ Post-request Script ]
```
Each script tab: `ui.codemirror` editor (JavaScript mode, syntax highlighting).

### Collection & Folder Script Editors (`ui/sidebar.py`)

Right-click → Edit Collection / Edit Folder → dialog with:
- **Pre-request Script** tab (`ui.codemirror`)
- **Post-request Script** tab (`ui.codemirror`)

### Response Panel — Console Tab (`ui/response_viewer.py`)

```
[ Body ] [ Headers ] [ Console ]
```
Console tab shows:
- `console.log` output per script level, prefixed: `[collection]`, `[folder]`, `[request]`
- Script errors in red: `[request][ERROR] ReferenceError: foo is not defined`
- Cleared on each new request send
- If pre-request aborted: shows error banner, Console tab, no Body/Headers

---

### Postman Import (`core/importer.py`)

Postman v2.1 stores scripts in the `event` array at collection, folder, and request level:
```json
"event": [
  { "listen": "prerequest", "script": { "exec": ["line1", "line2"] } },
  { "listen": "test",       "script": { "exec": ["pm.test(...)"] } }
]
```
**Mapping:**
- `"listen": "prerequest"` → `pre_request_script` (join `exec` with `\n`)
- `"listen": "test"` → `post_request_script` (join `exec` with `\n`)

Applied recursively at collection, folder, and request levels.

---

### Multi-Tab State (`ui/request_tabs.py`)
The app runs in **a single browser tab** at `http://localhost:8080`. Inside that single page, a horizontal tab bar (like Postman's) is built using NiceGUI's `ui.tabs` + `ui.tab_panels` components. Double-clicking a request in the sidebar opens it as a new tab in that bar. Tab state (which request ID is loaded, any unsaved edits to URL/body/headers/scripts) is held in a Python list in NiceGUI's `app.storage.user` (per-session in-memory storage). No browser-level multi-tab behavior is involved or required.

### `.env` File Structure (`.env.example`)
```
MONGO_URI=mongodb+srv://user:pass@cluster.mongodb.net/
MONGO_DB=apihive
SSL_VERIFY=true
```

### NiceGUI App Launch
```python
# app.py
from nicegui import ui, app
from ui.layout import build_layout

@ui.page('/')
async def index():
    await build_layout()

ui.run(title='ApiHive', port=8080, reload=False)
```

### Top Bar Layout
```
[ApiHive logo]  ←→  [Environment: Dev ▼] [SSL: ON/OFF] [Import] [Settings]
```

### Sidebar Tree
Use `ui.tree` with lazy-loaded children. Context menu (right-click) per node:
- Collection: Add Folder, Add Request, Edit (opens script editors), Delete Collection
- Folder: Add Request, Edit (opens script editors), Rename, Delete
- Request: Rename, Duplicate, Delete

Double-click a request → open it in a new tab in the main panel.

---

## Implementation Phases

### Phase 1 — Foundation
- `core/db.py`: MongoDB connection, CRUD for all 4 collections, `get_script_chain()`
- `core/models.py`: Pydantic models (with `pre_request_script`, `post_request_script`; no `post_response`)
- `core/script_runner.py`: PyMiniRacer engine, pm preamble, two-phase `pm.sendRequest`
- `.env` loading, `SSL_VERIFY` wiring into httpx
- Basic NiceGUI layout shell (header + sidebar placeholder + main placeholder)

### Phase 2 — Collections & CRUD
- Sidebar tree with `ui.tree`, right-click context menus
- Collection/folder edit dialogs with `ui.codemirror` script editors
- Create/rename/delete collections, folders, requests
- Basic request builder (method dropdown, URL input, tabs for Params/Headers/Body)

### Phase 3 — Request Execution
- `core/http_client.py`: script chain → pre-run → resolve vars → send → post-run → persist env_updates
- `core/variables.py`: variable resolution pipeline
- `ui/request_builder.py`: Pre-request Script + Post-request Script tabs
- `ui/response_viewer.py`: Body + Headers + Console tabs
- Global SSL toggle wired through settings

### Phase 4 — Environments & Variables
- Environment CRUD (create, edit key-values, delete, activate)
- Environment dropdown in top bar
- Variable substitution preview (show resolved URL as user types)
- Env updates from scripts persisted to MongoDB after request

### Phase 5 — Import & Multi-Tab
- `core/importer.py`: Postman v2.1 import including `event` scripts at all levels
- Import dialog with file picker
- Multi-tab request builder (`ui.tabs` in main panel)
- Tab state persistence per NiceGUI session

---

## Verification Plan

1. **Basic run**: `python app.py` → opens at `http://localhost:8080` → no errors in console
2. **Atlas connection**: Remove `.env` → app shows a clear error on startup, not a crash
3. **Script basics**: Pre-request script `pm.environment.set('test', '123')` → `{{test}}` resolves correctly in URL
4. **Console output**: `console.log('hello')` in script → Console tab shows `[request] hello`
5. **Pre-request abort**: `throw new Error('stop!')` in pre-request → request NOT sent, Console shows red error, no Body/Headers
6. **Post-request token extraction**: Post-request script `pm.environment.set('token', pm.response.json().access_token)` → verify token saved in MongoDB environment document
7. **`pm.sendRequest` JWT fetch**: Pre-request script POSTs to auth endpoint → extracts JWT → sets env var → main request uses `{{token}}` → request succeeds
8. **Script chain order**: Collection logs `'A'`, folder logs `'B'`, request logs `'C'` → Console shows `[collection] A / [folder] B / [request] C`
9. **Import test**: Import Postman collection `.json` with `prerequest`/`test` events → scripts appear in editors, tree matches original structure
10. **Send request**: Select imported GET request → click Send → response appears with correct JSON
11. **Variable substitution**: Set `base_url` in environment → switch to it → URL resolves correctly
12. **Multi-tab**: Open 3 different requests in tabs → switch between them → state is preserved
13. **SSL toggle**: Hit endpoint with self-signed cert → toggle SSL off → request succeeds
14. **Team sync**: Two browser sessions → User A edits and saves → User B refreshes → sees updated state
15. **CRUD**: Create collection, add folder, add request, delete folder → tree updates correctly
