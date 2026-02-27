"""
Postman v2.1 collection importer.
Converts a .postman_collection.json file into MongoDB documents (collections + items).
"""
import json
import uuid

from core import db


def _parse_events(events: list) -> dict:
    """
    Parse Postman event array → {'pre_request_script': str, 'post_request_script': str}.
    'prerequest' → pre_request_script
    'test'       → post_request_script
    """
    pre_script = ''
    post_script = ''
    for event in events:
        listen = event.get('listen', '')
        exec_lines = event.get('script', {}).get('exec', [])
        code = '\n'.join(exec_lines) if isinstance(exec_lines, list) else str(exec_lines)
        if listen == 'prerequest':
            pre_script = code
        elif listen == 'test':
            post_script = code
    return {'pre_request_script': pre_script, 'post_request_script': post_script}


def _parse_url(url_obj) -> tuple[str, list]:
    """
    Returns (url_string, params_list).
    url_obj can be a plain string or a Postman URL object.
    """
    if isinstance(url_obj, str):
        return url_obj, []
    raw = url_obj.get('raw', '')
    query = url_obj.get('query', [])
    params = [
        {
            'key': q.get('key', ''),
            'value': q.get('value', ''),
            'enabled': not q.get('disabled', False),
        }
        for q in query
    ]
    return raw, params


def _parse_body(body_obj: dict) -> dict:
    if not body_obj:
        return {'mode': 'none', 'raw': '', 'urlencoded': []}

    mode = body_obj.get('mode', 'none')
    if mode == 'raw':
        return {'mode': 'raw', 'raw': body_obj.get('raw', ''), 'urlencoded': []}
    if mode == 'urlencoded':
        ue = [
            {
                'key': f.get('key', ''),
                'value': f.get('value', ''),
                'enabled': not f.get('disabled', False),
            }
            for f in body_obj.get('urlencoded', [])
        ]
        return {'mode': 'urlencoded', 'raw': '', 'urlencoded': ue}
    # formdata and other modes → none for MVP
    return {'mode': 'none', 'raw': '', 'urlencoded': []}


def _import_items(
    postman_items: list,
    collection_id: str,
    parent_id,
    errors: list,
    counter: list,
):
    """Recursively import Postman items (folders and requests)."""
    for order_idx, pm_item in enumerate(postman_items):
        try:
            name = pm_item.get('name', 'Untitled')
            events = _parse_events(pm_item.get('event', []))

            if 'item' in pm_item:
                # ── Folder ────────────────────────────────────────────────────
                folder_id = str(uuid.uuid4())
                folder_doc = {
                    '_id': folder_id,
                    'collection_id': collection_id,
                    'parent_id': parent_id,
                    'type': 'folder',
                    'name': name,
                    'order': order_idx,
                    'pre_request_script': events['pre_request_script'],
                    'post_request_script': events['post_request_script'],
                }
                db.create_item(folder_doc)
                counter[0] += 1
                # Recurse into children
                _import_items(
                    pm_item['item'], collection_id, folder_id, errors, counter
                )

            elif 'request' in pm_item:
                # ── Request ───────────────────────────────────────────────────
                req = pm_item['request']
                method = req.get('method', 'GET').upper()
                url_raw, params_from_url = _parse_url(req.get('url', ''))
                # Merge query params from url object with request-level params (if any)
                params = params_from_url
                headers = [
                    {
                        'key': h.get('key', ''),
                        'value': h.get('value', ''),
                        'enabled': not h.get('disabled', False),
                    }
                    for h in req.get('header', [])
                ]
                body = _parse_body(req.get('body', {}))
                auth = req.get('auth', {'type': 'none'})

                req_doc = {
                    '_id': str(uuid.uuid4()),
                    'collection_id': collection_id,
                    'parent_id': parent_id,
                    'type': 'request',
                    'name': name,
                    'order': order_idx,
                    'pre_request_script': events['pre_request_script'],
                    'post_request_script': events['post_request_script'],
                    'method': method,
                    'url': url_raw,
                    'params': params,
                    'headers': headers,
                    'body': body,
                    'auth': auth,
                }
                db.create_item(req_doc)
                counter[0] += 1

        except Exception as exc:
            errors.append(f'Item "{pm_item.get("name", "?")}": {exc}')


def import_postman_v21(filepath: str) -> dict:
    """
    Parses a Postman v2.1 collection JSON file and inserts into MongoDB.

    Returns:
    {
        "collection_id": str,
        "imported_count": int,
        "errors": list[str]
    }
    """
    errors: list[str] = []

    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)

    info = data.get('info', {})
    col_name = info.get('name', 'Imported Collection')

    # Collection-level scripts and variables
    events = _parse_events(data.get('event', []))
    raw_vars = data.get('variable', [])
    variables = {
        v['key']: {
            'value': str(v.get('value', '')),
            'enabled': not v.get('disabled', False),
        }
        for v in raw_vars
        if v.get('key')
    }

    col_doc = db.create_collection(col_name)
    collection_id = col_doc['_id']

    # Persist collection-level scripts and variables
    db.update_collection(collection_id, {
        'pre_request_script': events['pre_request_script'],
        'post_request_script': events['post_request_script'],
        'variables': variables,
    })

    counter = [0]
    _import_items(data.get('item', []), collection_id, None, errors, counter)

    return {
        'collection_id': collection_id,
        'imported_count': counter[0],
        'errors': errors,
    }
