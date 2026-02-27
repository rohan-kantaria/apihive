"""
JS script runner using PyMiniRacer (V8 embedded).
Implements the two-phase pm.sendRequest model from plan.md.
"""
import json
import re
import httpx

try:
    from py_mini_racer import MiniRacer
    _RACER_AVAILABLE = True
except ImportError:
    _RACER_AVAILABLE = False


def _make_preamble(env_vars: dict, response_obj: dict | None, send_request_js: str) -> str:
    """Build the JS preamble injected before user scripts."""
    env_json = json.dumps(env_vars)
    response_js = json.dumps(response_obj) if response_obj is not None else "undefined"

    return f"""
var __logs = [];
var __env_updates = {{}};
var console = {{
  log: function() {{
    __logs.push(Array.prototype.slice.call(arguments)
      .map(function(a) {{ return typeof a === 'object' ? JSON.stringify(a) : String(a); }})
      .join(' '));
  }}
}};
var pm = {{
  environment: {{
    _vars: {env_json},
    get: function(key) {{ return this._vars[key] !== undefined ? this._vars[key] : null; }},
    set: function(key, value) {{
      this._vars[key] = String(value);
      __env_updates[key] = String(value);
    }}
  }},
  response: (function() {{
    var _r = {response_js};
    if (!_r) return undefined;
    return {{
      status: _r.status,
      statusCode: _r.status,
      headers: _r.headers,
      text: function() {{ return _r.body_text || ''; }},
      json: function() {{ return _r.body_json !== undefined ? _r.body_json : null; }}
    }};
  }})(),
  sendRequest: {send_request_js},
  require: function(pkg) {{
    __logs.push('[warn] pm.require("' + pkg + '") is not supported in ApiHive');
    return {{}};
  }},
  execution: {{
    runRequest: function(id) {{
      __logs.push('[warn] pm.execution.runRequest is not supported in ApiHive');
      return {{ body: {{}} }};
    }}
  }}
}};
"""


_MOCK_SEND_REQUEST_JS = """
(function() {
  var __captured = null;
  var fn = function(opts) {
    __captured = opts;
    return {
      status: 0, statusCode: 0,
      headers: {},
      text: function() { return ''; },
      json: function() { return null; }
    };
  };
  fn.__captured = function() { return __captured; };
  return fn;
})()
"""


def _make_real_send_request_js(response: dict) -> str:
    """Return JS for pm.sendRequest that always returns the given real response."""
    resp_json = json.dumps(response)
    return f"""
(function() {{
  var _resp = {resp_json};
  return function(opts) {{
    return {{
      status: _resp.status,
      statusCode: _resp.status,
      headers: _resp.headers,
      text: function() {{ return _resp.body_text || ''; }},
      json: function() {{ return _resp.body_json !== undefined ? _resp.body_json : null; }}
    }};
  }};
}})()
"""


_RETURN_SUFFIX = """
JSON.stringify({ env_updates: __env_updates, console_output: __logs });
"""


def _execute_script(script: str, env_vars: dict, response_obj: dict | None) -> dict:
    """
    Run a single-phase execution.
    Returns {"env_updates": {}, "console_output": [], "error": None | str, "_captured_request": None}
    """
    if not _RACER_AVAILABLE:
        return {"env_updates": {}, "console_output": [], "error": "py-mini-racer is not installed", "_captured_request": None}

    if not script or not script.strip():
        return {"env_updates": {}, "console_output": [], "error": None, "_captured_request": None}

    # V8 eval mode doesn't support top-level `await` — strip it as a compatibility shim
    # for Postman collections that use async APIs we don't support anyway.
    script = re.sub(r'\bawait\s+', '', script)

    # Phase 1: use mock sendRequest to detect if pm.sendRequest is called
    phase1_preamble = _make_preamble(env_vars, response_obj, _MOCK_SEND_REQUEST_JS)
    # We need to extract __captured after the script runs
    phase1_full = phase1_preamble + "\n" + script + "\n" + """
var __result = JSON.stringify({ env_updates: __env_updates, console_output: __logs });
var __captured_req = pm.sendRequest.__captured ? pm.sendRequest.__captured() : null;
JSON.stringify({ result: JSON.parse(__result), captured: __captured_req });
"""
    try:
        ctx = MiniRacer()
        raw = ctx.eval(phase1_full)
        phase1_data = json.loads(raw)
        captured_request = phase1_data.get("captured")
    except Exception as e:
        return {"env_updates": {}, "console_output": [], "error": str(e), "_captured_request": None}

    if captured_request is None:
        # No pm.sendRequest call — phase 1 result is final
        r = phase1_data.get("result", {})
        return {
            "env_updates": r.get("env_updates", {}),
            "console_output": r.get("console_output", []),
            "error": None,
            "_captured_request": None,
        }

    # Python bridge: execute the captured HTTP request
    bridge_response = _execute_bridge_request(captured_request)

    # Phase 2: re-run with real response injected into pm.sendRequest
    real_sr_js = _make_real_send_request_js(bridge_response)
    phase2_preamble = _make_preamble(env_vars, response_obj, real_sr_js)
    phase2_full = phase2_preamble + "\n" + script + "\n" + _RETURN_SUFFIX

    try:
        ctx2 = MiniRacer()
        raw2 = ctx2.eval(phase2_full)
        r2 = json.loads(raw2)
        return {
            "env_updates": r2.get("env_updates", {}),
            "console_output": r2.get("console_output", []),
            "error": None,
            "_captured_request": captured_request,
        }
    except Exception as e:
        return {"env_updates": {}, "console_output": [], "error": str(e), "_captured_request": captured_request}


def _execute_bridge_request(opts: dict) -> dict:
    """Execute a pm.sendRequest options dict via httpx (synchronous)."""
    url = opts.get("url", "")
    method = opts.get("method", "GET").upper()

    # Build headers
    headers = {}
    for h in opts.get("header", []):
        if isinstance(h, dict):
            headers[h.get("key", "")] = h.get("value", "")

    # Build body
    content = None
    body_obj = opts.get("body", {})
    if isinstance(body_obj, dict):
        mode = body_obj.get("mode", "none")
        if mode == "raw":
            content = body_obj.get("raw", "").encode()
        elif mode == "urlencoded":
            pairs = body_obj.get("urlencoded", [])
            content = "&".join(
                f"{p.get('key', '')}={p.get('value', '')}"
                for p in pairs if not p.get("disabled", False)
            ).encode()

    try:
        resp = httpx.request(method, url, headers=headers, content=content, timeout=30)
        try:
            body_json = resp.json()
        except Exception:
            body_json = None
        return {
            "status": resp.status_code,
            "headers": dict(resp.headers),
            "body_text": resp.text,
            "body_json": body_json,
        }
    except Exception as e:
        return {
            "status": 0,
            "headers": {},
            "body_text": str(e),
            "body_json": None,
        }


def run_pre_request(script: str, env_vars: dict) -> dict:
    """
    Run a pre-request script.
    Returns: {"env_updates": {}, "console_output": [], "error": None | str}
    """
    result = _execute_script(script, env_vars, response_obj=None)
    return {
        "env_updates": result["env_updates"],
        "console_output": result["console_output"],
        "error": result["error"],
    }


def run_post_request(script: str, env_vars: dict, response_data: dict) -> dict:
    """
    Run a post-request script.
    response_data = {status, headers, body_text, body_json}
    Returns: {"env_updates": {}, "console_output": [], "error": None | str}
    """
    result = _execute_script(script, env_vars, response_obj=response_data)
    return {
        "env_updates": result["env_updates"],
        "console_output": result["console_output"],
        "error": result["error"],
    }
