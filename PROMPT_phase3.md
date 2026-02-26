# ApiHive — Phase 3: Request Execution

Read `plan.md` fully before doing anything. Pay special attention to:
- "HTTP Client Execution Flow" section
- "Script Engine" section (two-phase pm.sendRequest)
- "Pre-request Script Error Handling" section
- "Request Builder UI" section
- "Response Panel — Console Tab" section

## Prerequisites

Phases 1 and 2 must be complete. If any earlier file is missing or broken, fix it first.

## Your job this iteration

Implement **Phase 3 — Request Execution**. Check every file before writing it.
If it already exists and is partially correct, continue from where it left off.

### Files to create / update

**`core/variables.py`** — ensure it is complete per Phase 1 spec (may already exist)

**`core/http_client.py`**

The core request executor. Implement exactly the 9-step flow from plan.md:

```python
import httpx
from core import db, variables, script_runner

async def execute_request(item_id: str, active_env_id: str | None, ssl_verify: bool) -> dict:
    """
    Returns:
    {
        "response_data": {
            "status": int,
            "headers": dict,
            "body_text": str,
            "body_json": dict | list | None,
            "elapsed_ms": float,
        } | None,
        "console_output": list[str],   # prefixed with [level], errors with [level][ERROR]
        "script_error": str | None,    # set if pre-request aborted
    }
    """
```

Step-by-step (follow plan.md exactly):
1. `get_script_chain(item_id)` → ordered list outermost→innermost
2. Resolve `env_vars`: load local `.env` vars, load active environment values from DB,
   load globals from DB. Build merged dict for variable resolution.
3. For each level in script chain (collection → folder → request):
   - If `pre_request_script` is non-empty, call `run_pre_request(script, current_env_vars)`
   - If `result["error"]` is not None → abort: return `{response_data: None, console_output, script_error: result["error"]}`
   - Merge `result["env_updates"]` into `current_env_vars`
   - Append `result["console_output"]` prefixed with `[{level}]`
4. Resolve `{{variables}}` in item's url, headers (enabled only), params (enabled only),
   and body fields using `variables.resolve()`
5. Send HTTP request via `httpx.AsyncClient` with `verify=ssl_verify`
   - Build query string from enabled params
   - Build headers dict from enabled headers
   - Handle body modes: none, raw (JSON content-type), urlencoded (enabled pairs only)
   - Capture `elapsed_ms` using `response.elapsed.total_seconds() * 1000`
6. Build `response_data` dict
7. For each level (collection → folder → request):
   - If `post_request_script` is non-empty, call `run_post_request(script, current_env_vars, response_data)`
   - Merge `result["env_updates"]` into `current_env_vars` (do NOT abort on error)
   - Append `result["console_output"]` prefixed with `[{level}]`
   - If `result["error"]`: append `[{level}][ERROR] {result["error"]}` to console_output
8. Persist all accumulated `env_updates` to active environment in MongoDB:
   - Load current active env, merge updates into its `values` dict, call `db.update_environment()`
9. Return the result dict

**`ui/request_builder.py`** — replace the Phase 2 stub with full implementation

Layout (vertical column inside the tab panel):

```
[Method ▼] [URL input                              ] [Send]
─────────────────────────────────────────────────────────
[ Params ] [ Headers ] [ Body ] [ Pre-request ] [ Post-request ]
─────────────────────────────────────────────────────────
[tab panel content for selected tab]
```

- Method dropdown: `ui.select(['GET','POST','PUT','PATCH','DELETE','HEAD','OPTIONS'])`
- URL input: `ui.input()` with full width, monospace font
- Send button: calls `on_send()` async handler

**Params tab:**
Key/value table with "Enabled" checkbox, "Key" input, "Value" input, delete button per row,
plus an "Add" button at the bottom. Mirrors `item["params"]` list.

**Headers tab:**
Same key/value table structure as Params.

**Body tab:**
- Mode selector: `ui.radio(['none', 'raw', 'urlencoded'])`
- `none`: empty
- `raw`: `ui.codemirror(language='json')` editor
- `urlencoded`: same key/value table as Params

**Pre-request Script tab:**
`ui.codemirror(language='javascript')` editor, full width, ~300px tall.

**Post-request Script tab:**
Same as pre-request.

**Save behaviour:**
Auto-save to MongoDB on every meaningful change (method, URL, params, headers, body, scripts)
using a 500ms debounce. Show a small "Saved" indicator.

**`on_send()` handler:**
```python
async def on_send():
    # 1. Save current state to DB
    # 2. Call http_client.execute_request(item_id, active_env_id, ssl_verify)
    # 3. Pass result to response_viewer.update_response(result)
```

**`ui/response_viewer.py`** — replace Phase 2 stub with full implementation

Layout (below the request builder, or as a split-pane bottom half):

```
Status: 200 OK  •  Time: 142ms
[ Body ] [ Headers ] [ Console ]
─────────────────────────────
[tab panel content]
```

**Body tab:**
- If `body_json` is not None: pretty-printed JSON using `ui.code(json.dumps(..., indent=2), language='json')`
- Else: plain text in a `ui.textarea` (read-only)
- If pre-request aborted (`response_data` is None): show red error banner with `script_error`

**Headers tab:**
Table of response header key/value pairs.

**Console tab:**
- `ui.log` or a styled scrollable `ui.column` showing each line of `console_output`
- Lines containing `[ERROR]` styled in red
- Cleared on each new request send

**When pre-request aborts:**
- Do not populate Body/Headers tabs
- Switch to Console tab automatically
- Show red banner: "Request aborted: {script_error}"

Export:
```python
def build_response_viewer() -> 'ResponseViewer': ...

class ResponseViewer:
    def update_response(self, result: dict): ...
    def clear(self): ...
```

**Integration in `ui/request_tabs.py`:**
Each tab panel should render both `request_builder` and `response_viewer` stacked vertically
(or use a splitter). Wire the Send button to pass results to the response viewer.

**Integration in `ui/layout.py`:**
Wire the SSL toggle button to actually update `app.state.ssl_verify` and update the label.

## Done when

Verify these scenarios from plan.md's Verification Plan:

1. "Basic run": `python app.py` → no errors
2. "Script basics": Pre-request `pm.environment.set('test','123')` → `{{test}}` resolves in URL
3. "Console output": `console.log('hello')` → Console tab shows `[request] hello`
4. "Pre-request abort": `throw new Error('stop!')` → request NOT sent, Console shows red error,
   no Body/Headers populated
5. "Post-request token extraction": post-request `pm.environment.set('token', pm.response.json().access_token)`
   → token saved in MongoDB
6. "`pm.sendRequest` JWT fetch": Pre-request POSTs to auth endpoint → extracts JWT → sets env var
   → main request uses `{{token}}` → succeeds
7. "Script chain order": Collection logs 'A', folder logs 'B', request logs 'C'
   → Console shows `[collection] A` / `[folder] B` / `[request] C`
8. "Send request": Select GET request → Send → JSON response in Body tab

When you are confident Phase 3 is fully implemented and correct, output exactly:

<promise>PHASE 3 COMPLETE</promise>
