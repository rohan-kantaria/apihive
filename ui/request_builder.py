"""
Request builder panel — method, URL, params, headers, body, pre/post-request script tabs.
Auto-saves to MongoDB on changes (500 ms debounce). Wires Send button to http_client.
"""
import asyncio

from nicegui import ui, app as nicegui_app

from core import db, http_client


# ── Key-value table helper ─────────────────────────────────────────────────────

def _build_kv_table(container: ui.element, pairs: list[dict], on_change):
    """Render editable key-value rows into *container*. Mutates *pairs* in place."""
    container.clear()
    with container:
        for i, pair in enumerate(pairs):
            with ui.row().classes('w-full items-center gap-1 no-wrap'):
                cb = ui.checkbox(value=pair.get('enabled', True))
                cb.on('update:model-value',
                      lambda e, _i=i: (_kv_set(pairs, _i, 'enabled', bool(e.args)), on_change()))

                k_inp = ui.input(value=pair.get('key', ''), placeholder='Key').classes(
                    'flex-grow font-mono text-sm'
                )
                k_inp.on('change',
                         lambda e, _i=i: (_kv_set(pairs, _i, 'key', e.value), on_change()))

                v_inp = ui.input(value=pair.get('value', ''), placeholder='Value').classes(
                    'flex-grow font-mono text-sm'
                )
                v_inp.on('change',
                         lambda e, _i=i: (_kv_set(pairs, _i, 'value', e.value), on_change()))

                ui.button(
                    icon='delete',
                    on_click=lambda _, _i=i: _kv_delete(container, pairs, _i, on_change)
                ).props('flat round dense size=xs color=red-4')

        ui.button('Add row', icon='add', on_click=lambda _: _kv_add(container, pairs, on_change)).props(
            'flat size=sm'
        )


def _kv_set(pairs, i, key, val):
    if 0 <= i < len(pairs):
        pairs[i][key] = val


def _kv_add(container, pairs, on_change):
    pairs.append({'key': '', 'value': '', 'enabled': True})
    _build_kv_table(container, pairs, on_change)
    on_change()


def _kv_delete(container, pairs, i, on_change):
    if 0 <= i < len(pairs):
        pairs.pop(i)
    _build_kv_table(container, pairs, on_change)
    on_change()


# ── Main builder ───────────────────────────────────────────────────────────────

def build_request_builder(item: dict, response_viewer=None):
    """
    Render the request builder panel for *item*.
    *response_viewer* is a ResponseViewer instance whose update_response() is called on Send.
    """
    item_id = item['_id']

    # Working copies of mutable list/dict fields
    params: list[dict] = [dict(p) for p in item.get('params', [])]
    req_headers: list[dict] = [dict(h) for h in item.get('headers', [])]
    body_src = item.get('body', {'mode': 'none', 'raw': '', 'urlencoded': []})
    ue_pairs: list[dict] = [dict(u) for u in body_src.get('urlencoded', [])]

    # Element references held in single-element lists so nested functions can rebind
    _method_el: list = [None]
    _url_el: list = [None]
    _body_mode_el: list = [None]
    _raw_editor_el: list = [None]
    _pre_editor_el: list = [None]
    _post_editor_el: list = [None]
    _saved_label_el: list = [None]
    _send_btn_el: list = [None]
    _ue_container_el: list = [None]

    _pending_task: list = [None]

    # ── data collection ────────────────────────────────────────────────────────

    def collect_data() -> dict:
        return {
            'method': _method_el[0].value if _method_el[0] else item.get('method', 'GET'),
            'url': _url_el[0].value if _url_el[0] else item.get('url', ''),
            'params': params,
            'headers': req_headers,
            'body': {
                'mode': _body_mode_el[0].value if _body_mode_el[0] else 'none',
                'raw': _raw_editor_el[0].value if _raw_editor_el[0] else '',
                'urlencoded': ue_pairs,
            },
            'pre_request_script': _pre_editor_el[0].value if _pre_editor_el[0] else '',
            'post_request_script': _post_editor_el[0].value if _post_editor_el[0] else '',
        }

    # ── debounced save ─────────────────────────────────────────────────────────

    def schedule_save():
        task = _pending_task[0]
        if task is not None and not task.done():
            task.cancel()
        try:
            loop = asyncio.get_event_loop()
            _pending_task[0] = loop.create_task(_do_save())
        except RuntimeError:
            pass

    async def _do_save():
        await asyncio.sleep(0.5)
        data = collect_data()
        db.update_item(item_id, data)
        if _saved_label_el[0]:
            _saved_label_el[0].set_visibility(True)
            await asyncio.sleep(1.5)
            _saved_label_el[0].set_visibility(False)

    # ── Send handler ───────────────────────────────────────────────────────────

    async def on_send():
        # 1. Save current state
        data = collect_data()
        db.update_item(item_id, data)

        # 2. Execute request
        active_env_id = nicegui_app.storage.user.get('active_env_id')
        ssl_verify = getattr(nicegui_app.state, 'ssl_verify', True)

        if _send_btn_el[0]:
            _send_btn_el[0].props(add='loading')
        try:
            result = await http_client.execute_request(item_id, active_env_id, ssl_verify)
        except Exception as exc:
            result = {
                'response_data': None,
                'console_output': [str(exc)],
                'script_error': str(exc),
            }
        finally:
            if _send_btn_el[0]:
                _send_btn_el[0].props(remove='loading')

        # 3. Pass to response viewer
        if response_viewer is not None:
            response_viewer.update_response(result)

    # ── UI layout ──────────────────────────────────────────────────────────────

    with ui.column().classes('w-full gap-1'):

        # Top row: method + URL + saved indicator + Send
        with ui.row().classes('w-full items-center gap-2 no-wrap'):
            _method_el[0] = ui.select(
                ['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'HEAD', 'OPTIONS'],
                value=item.get('method', 'GET'),
                on_change=lambda _: schedule_save(),
            ).classes('w-28 shrink-0')

            _url_el[0] = ui.input(
                placeholder='https://api.example.com/endpoint',
                value=item.get('url', ''),
                on_change=lambda _: schedule_save(),
            ).classes('flex-grow font-mono text-sm')

            _saved_label_el[0] = ui.label('Saved ✓').classes(
                'text-xs text-green-600 shrink-0'
            )
            _saved_label_el[0].set_visibility(False)

            _send_btn_el[0] = ui.button('Send', icon='send', on_click=on_send).props(
                'color=primary'
            )

        # Variable preview: resolved URL shown below the URL input when {{vars}} are present
        resolved_label = ui.label('').classes('text-xs text-gray-400 font-mono -mt-1')

        def update_resolved(url: str):
            from core.variables import resolve, load_local_env, get_active_env_values, get_global_values
            active_env_id = nicegui_app.storage.user.get('active_env_id')
            resolved = resolve(
                url,
                load_local_env(),
                get_active_env_values(active_env_id),
                get_global_values(),
            )
            resolved_label.set_text(resolved if '{{' in url else '')

        _url_el[0].on('input', lambda e: update_resolved(e.args if isinstance(e.args, str) else _url_el[0].value))

        ui.separator().classes('my-0')

        # Sub-tabs
        with ui.tabs().classes('w-full shrink-0') as req_tabs:
            p_tab = ui.tab('Params')
            h_tab = ui.tab('Headers')
            b_tab = ui.tab('Body')
            pre_tab = ui.tab('Pre-request')
            post_tab = ui.tab('Post-request')

        with ui.tab_panels(req_tabs, value=p_tab).classes('w-full'):

            # Params
            with ui.tab_panel(p_tab).classes('p-0 pt-1'):
                params_container = ui.column().classes('w-full gap-1')
                _build_kv_table(params_container, params, schedule_save)

            # Headers
            with ui.tab_panel(h_tab).classes('p-0 pt-1'):
                headers_container = ui.column().classes('w-full gap-1')
                _build_kv_table(headers_container, req_headers, schedule_save)

            # Body
            with ui.tab_panel(b_tab).classes('p-0 pt-2'):
                _body_mode_el[0] = ui.radio(
                    ['none', 'raw', 'urlencoded'],
                    value=body_src.get('mode', 'none'),
                ).props('inline')

                _raw_editor_el[0] = ui.codemirror(
                    value=body_src.get('raw', ''),
                    language='json',
                    on_change=lambda _: schedule_save(),
                ).classes('w-full mt-1').style('height: 200px')

                _ue_container_el[0] = ui.column().classes('w-full mt-1 gap-1')
                _build_kv_table(_ue_container_el[0], ue_pairs, schedule_save)

                # Set initial visibility
                initial_mode = body_src.get('mode', 'none')
                _raw_editor_el[0].set_visibility(initial_mode == 'raw')
                _ue_container_el[0].set_visibility(initial_mode == 'urlencoded')

                def on_body_mode_change(e):
                    mode = e.value
                    _raw_editor_el[0].set_visibility(mode == 'raw')
                    _ue_container_el[0].set_visibility(mode == 'urlencoded')
                    schedule_save()

                _body_mode_el[0].on('update:model-value', on_body_mode_change)

            # Pre-request Script
            with ui.tab_panel(pre_tab).classes('p-0 pt-1'):
                _pre_editor_el[0] = ui.codemirror(
                    value=item.get('pre_request_script', ''),
                    language='javascript',
                    on_change=lambda _: schedule_save(),
                ).classes('w-full').style('height: 300px')

            # Post-request Script
            with ui.tab_panel(post_tab).classes('p-0 pt-1'):
                _post_editor_el[0] = ui.codemirror(
                    value=item.get('post_request_script', ''),
                    language='javascript',
                    on_change=lambda _: schedule_save(),
                ).classes('w-full').style('height: 300px')
