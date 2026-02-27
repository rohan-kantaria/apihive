"""
HTTP request executor — implements the 9-step flow from plan.md.
"""
import httpx
from core import db, variables, script_runner


def _get_active_env_values(active_env_id: str | None) -> dict:
    if not active_env_id:
        return {}
    env = db.get_environment(active_env_id)
    return env.get('values', {}) if env else {}


def _get_global_values() -> dict:
    g = db.get_globals()
    return g.get('values', {})


def _flatten_env(local_env: dict, active_env_values: dict, global_values: dict) -> dict:
    """Build a flat {key: value_string} dict for the script runner (priority: local > active > global)."""
    result = {}
    for k, v in global_values.items():
        if isinstance(v, dict):
            if v.get('enabled', True):
                result[k] = str(v.get('value', ''))
        else:
            result[k] = str(v)
    for k, v in active_env_values.items():
        if isinstance(v, dict):
            if v.get('enabled', True):
                result[k] = str(v.get('value', ''))
        else:
            result[k] = str(v)
    result.update(local_env)  # local always wins
    return result


def _resolve_item_fields(item: dict, local_env: dict, active_env_values: dict, global_values: dict) -> dict:
    """Resolve {{variables}} in url, headers, params, body of an item."""
    def res(text: str) -> str:
        return variables.resolve(text, local_env, active_env_values, global_values)

    resolved = dict(item)
    resolved['url'] = res(item.get('url', ''))

    resolved['params'] = [
        {**p, 'value': res(p.get('value', '')), 'key': res(p.get('key', ''))}
        for p in item.get('params', [])
        if p.get('enabled', True)
    ]

    resolved['headers'] = [
        {**h, 'value': res(h.get('value', '')), 'key': res(h.get('key', ''))}
        for h in item.get('headers', [])
        if h.get('enabled', True)
    ]

    body = dict(item.get('body', {'mode': 'none', 'raw': '', 'urlencoded': []}))
    if body.get('mode') == 'raw':
        body['raw'] = res(body.get('raw', ''))
    elif body.get('mode') == 'urlencoded':
        body['urlencoded'] = [
            {**u, 'key': res(u.get('key', '')), 'value': res(u.get('value', ''))}
            for u in body.get('urlencoded', [])
            if u.get('enabled', True)
        ]
    resolved['body'] = body
    return resolved


async def execute_request(item_id: str, active_env_id: str | None, ssl_verify: bool) -> dict:
    """
    Execute a request following the 9-step flow from plan.md.

    Returns:
    {
        "response_data": {status, headers, body_text, body_json, elapsed_ms} | None,
        "console_output": list[str],
        "script_error": str | None,
    }
    """
    console_output: list[str] = []
    all_env_updates: dict = {}

    # Step 1: get script chain (outermost → innermost)
    chain = db.get_script_chain(item_id)

    # Step 2: resolve env_vars
    local_env = variables.load_local_env()
    active_env_values = _get_active_env_values(active_env_id)
    global_values = _get_global_values()
    current_env_vars = _flatten_env(local_env, active_env_values, global_values)

    # Step 3: run pre-request scripts
    for entry in chain:
        script = entry.get('pre', '')
        level = entry.get('level', 'request')
        if script and script.strip():
            result = script_runner.run_pre_request(script, current_env_vars)
            for line in result.get('console_output', []):
                console_output.append(f'[{level}] {line}')
            if result.get('error'):
                console_output.append(f'[{level}][ERROR] {result["error"]}')
                return {
                    'response_data': None,
                    'console_output': console_output,
                    'script_error': result['error'],
                }
            current_env_vars.update(result.get('env_updates', {}))
            all_env_updates.update(result.get('env_updates', {}))

    # Update active_env_values with script mutations for resolution
    for k, v in current_env_vars.items():
        if k not in local_env:
            if k in active_env_values:
                active_env_values[k] = {'value': v, 'enabled': True}
            elif k in global_values:
                global_values[k] = {'value': v, 'enabled': True}

    # Step 4: resolve variables in item fields
    item = db.get_item(item_id)
    if not item:
        return {
            'response_data': None,
            'console_output': console_output,
            'script_error': f'Item {item_id} not found',
        }
    resolved = _resolve_item_fields(item, local_env, active_env_values, global_values)

    # Step 5: send HTTP request
    method = resolved.get('method', 'GET').upper()
    url = resolved.get('url', '')
    params = {p['key']: p['value'] for p in resolved.get('params', [])}
    headers = {h['key']: h['value'] for h in resolved.get('headers', [])}
    body = resolved.get('body', {})
    body_mode = body.get('mode', 'none')

    content = None
    if body_mode == 'raw':
        raw_text = body.get('raw', '')
        content = raw_text.encode('utf-8')
        if 'content-type' not in {k.lower() for k in headers}:
            headers['Content-Type'] = 'application/json'
    elif body_mode == 'urlencoded':
        pairs = body.get('urlencoded', [])
        content = '&'.join(
            f"{u['key']}={u['value']}" for u in pairs
        ).encode('utf-8')
        if 'content-type' not in {k.lower() for k in headers}:
            headers['Content-Type'] = 'application/x-www-form-urlencoded'

    try:
        async with httpx.AsyncClient(verify=ssl_verify) as client:
            response = await client.request(
                method, url,
                params=params,
                headers=headers,
                content=content,
                timeout=30.0,
            )
        elapsed_ms = response.elapsed.total_seconds() * 1000
        try:
            body_json = response.json()
        except Exception:
            body_json = None

        # Step 6: build response_data
        response_data = {
            'status': response.status_code,
            'headers': dict(response.headers),
            'body_text': response.text,
            'body_json': body_json,
            'elapsed_ms': elapsed_ms,
        }
    except Exception as e:
        response_data = {
            'status': 0,
            'headers': {},
            'body_text': str(e),
            'body_json': None,
            'elapsed_ms': 0.0,
        }

    # Step 7: run post-request scripts (do NOT abort on error)
    for entry in chain:
        script = entry.get('post', '')
        level = entry.get('level', 'request')
        if script and script.strip():
            result = script_runner.run_post_request(script, current_env_vars, response_data)
            for line in result.get('console_output', []):
                console_output.append(f'[{level}] {line}')
            if result.get('error'):
                console_output.append(f'[{level}][ERROR] {result["error"]}')
            current_env_vars.update(result.get('env_updates', {}))
            all_env_updates.update(result.get('env_updates', {}))

    # Step 8: persist env_updates to active environment
    if all_env_updates and active_env_id:
        env = db.get_environment(active_env_id)
        if env:
            values = env.get('values', {})
            for k, v in all_env_updates.items():
                values[k] = {'value': str(v), 'enabled': True}
            db.update_environment(active_env_id, values)

    # Step 9: return
    return {
        'response_data': response_data,
        'console_output': console_output,
        'script_error': None,
    }
