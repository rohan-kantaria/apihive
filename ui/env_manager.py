"""
Environment manager dialog — CRUD for environments and global variables.
open_env_manager() is called from the Settings button in layout.py.
"""
from nicegui import ui, app as nicegui_app
from core import db


# ── helpers ────────────────────────────────────────────────────────────────────

def _build_kv_editor(container: ui.element, values: dict, on_change):
    """
    Render editable rows for an environment's values dict:
    { key: {"value": str, "enabled": bool} }
    Mutates *values* in place.
    """
    container.clear()
    with container:
        for key in list(values.keys()):
            _render_kv_row(container, values, key, on_change)
        ui.button('+ Add variable', icon='add',
                  on_click=lambda _: _add_variable(container, values, on_change)).props('flat size=sm')


def _render_kv_row(container, values, key, on_change):
    """Render a single key-value row (not adding to container — called inside _build_kv_editor)."""
    entry = values[key]
    with ui.row().classes('w-full items-center gap-1 no-wrap'):
        cb = ui.checkbox(value=entry.get('enabled', True))
        cb.on('update:model-value',
              lambda e, k=key: (_entry_set(values, k, 'enabled', bool(e.args)), on_change()))

        key_inp = ui.input(value=key, placeholder='Key').classes('flex-grow font-mono text-sm')
        key_inp.on('change', lambda e, k=key: _rename_key(container, values, k, e.value, on_change))

        val_inp = ui.input(value=entry.get('value', ''), placeholder='Value').classes(
            'flex-grow font-mono text-sm'
        )
        val_inp.on('change', lambda e, k=key: (_entry_set(values, k, 'value', e.value), on_change()))

        ui.button(icon='delete',
                  on_click=lambda _, k=key: _delete_key(container, values, k, on_change)).props(
            'flat round dense size=xs color=red-4'
        )


def _entry_set(values, key, field, val):
    if key in values:
        values[key][field] = val


def _rename_key(container, values, old_key, new_key, on_change):
    if not new_key or new_key == old_key:
        return
    entry = values.pop(old_key, {'value': '', 'enabled': True})
    values[new_key] = entry
    _build_kv_editor(container, values, on_change)
    on_change()


def _add_variable(container, values, on_change):
    base = 'new_var'
    name = base
    idx = 1
    while name in values:
        name = f'{base}_{idx}'
        idx += 1
    values[name] = {'value': '', 'enabled': True}
    _build_kv_editor(container, values, on_change)
    on_change()


def _delete_key(container, values, key, on_change):
    values.pop(key, None)
    _build_kv_editor(container, values, on_change)
    on_change()


# ── main dialog ────────────────────────────────────────────────────────────────

def open_env_manager():
    """Open the Environment Manager modal dialog."""

    # Working state
    state = {
        'selected_env_id': None,
        'env_values': {},       # working copy of selected env's values dict
        'global_values': {},    # working copy of globals values dict
        'dirty_env': False,
        'dirty_globals': False,
    }

    with ui.dialog().classes('w-full') as dialog, ui.card().classes('w-full max-w-4xl'):
        ui.label('Manage Environments').classes('text-xl font-bold mb-2')

        # ── Tab: Environments ────────────────────────────────────────────────
        with ui.tabs().classes('w-full') as top_tabs:
            envs_tab = ui.tab('Environments')
            globals_tab = ui.tab('Globals')

        with ui.tab_panels(top_tabs, value=envs_tab).classes('w-full'):

            # ── Environments panel ───────────────────────────────────────────
            with ui.tab_panel(envs_tab):
                active_env_id = nicegui_app.storage.user.get('active_env_id', '')

                with ui.row().classes('w-full gap-4').style('min-height: 350px'):

                    # Left: list of environments
                    with ui.column().classes('gap-2').style('width: 220px; min-width: 220px'):
                        ui.label('Environments').classes('text-sm font-semibold text-gray-600')
                        env_list_container = ui.column().classes('w-full gap-1')

                        def _new_env_dialog():
                            with ui.dialog() as nd, ui.card().classes('w-72'):
                                ui.label('New Environment').classes('text-lg font-bold')
                                name_inp = ui.input('Name').classes('w-full')

                                def do_create():
                                    name = name_inp.value.strip()
                                    if not name:
                                        ui.notify('Name cannot be empty', color='negative')
                                        return
                                    db.create_environment(name)
                                    nd.close()
                                    _refresh_env_list()

                                name_inp.on('keydown.enter', lambda _: do_create())
                                with ui.row():
                                    ui.button('Create', on_click=do_create).props('color=primary')
                                    ui.button('Cancel', on_click=nd.close).props('flat')
                            nd.open()

                        def _delete_selected_env():
                            eid = state['selected_env_id']
                            if not eid:
                                ui.notify('Select an environment first', color='warning')
                                return
                            with ui.dialog() as cd, ui.card().classes('w-72'):
                                ui.label('Delete Environment?').classes('text-lg font-bold')
                                ui.label('This cannot be undone.').classes('text-sm text-gray-600')

                                def do_delete():
                                    db.delete_environment(eid)
                                    if nicegui_app.storage.user.get('active_env_id') == eid:
                                        nicegui_app.storage.user['active_env_id'] = ''
                                    state['selected_env_id'] = None
                                    state['env_values'] = {}
                                    right_container.clear()
                                    cd.close()
                                    _refresh_env_list()

                                with ui.row():
                                    ui.button('Delete', on_click=do_delete).props('color=negative')
                                    ui.button('Cancel', on_click=cd.close).props('flat')
                            cd.open()

                        with ui.row().classes('w-full gap-1'):
                            ui.button('+ New', on_click=_new_env_dialog).props('flat size=sm')
                            ui.button('Delete', on_click=_delete_selected_env).props('flat size=sm color=red')

                    # Right: variable editor for selected env
                    with ui.column().classes('flex-grow gap-2') as right_container:
                        ui.label('Select an environment to edit').classes(
                            'text-gray-400 text-sm'
                        )

                # ── helper: refresh env list ─────────────────────────────────
                def _refresh_env_list():
                    nonlocal active_env_id
                    active_env_id = nicegui_app.storage.user.get('active_env_id', '')
                    env_list_container.clear()
                    with env_list_container:
                        envs = db.list_environments()
                        for env in envs:
                            eid = env['_id']
                            is_active = (eid == active_env_id)
                            label_text = ('✓ ' if is_active else '  ') + env['name']
                            btn = ui.button(label_text, on_click=lambda _, e=env: _select_env(e)).props(
                                'flat align=left'
                            ).classes(
                                'w-full text-left text-sm' + (' font-bold text-blue-600' if is_active else '')
                            )

                def _select_env(env: dict):
                    state['selected_env_id'] = env['_id']
                    state['env_values'] = {
                        k: dict(v) if isinstance(v, dict) else {'value': str(v), 'enabled': True}
                        for k, v in env.get('values', {}).items()
                    }
                    state['dirty_env'] = False
                    _render_env_editor(env)

                def _render_env_editor(env: dict):
                    right_container.clear()
                    with right_container:
                        ui.label(f'Edit: {env["name"]}').classes('text-sm font-semibold text-gray-700')
                        kv_container = ui.column().classes('w-full gap-1')
                        _build_kv_editor(kv_container, state['env_values'],
                                         lambda: state.update({'dirty_env': True}))

                        def activate():
                            nicegui_app.storage.user['active_env_id'] = env['_id']
                            ui.notify(f'Active environment: {env["name"]}', color='positive')
                            _refresh_env_list()

                        def save_env():
                            db.update_environment(env['_id'], state['env_values'])
                            state['dirty_env'] = False
                            ui.notify('Environment saved', color='positive')

                        with ui.row().classes('mt-2 gap-2'):
                            ui.button('✓ Activate', on_click=activate).props('color=primary size=sm')
                            ui.button('Save', on_click=save_env).props('color=positive size=sm')

                _refresh_env_list()

            # ── Globals panel ─────────────────────────────────────────────────
            with ui.tab_panel(globals_tab):
                ui.label('Global Variables').classes('text-sm font-semibold text-gray-600 mb-2')
                ui.label(
                    'Global variables are available in all requests (lowest priority).'
                ).classes('text-xs text-gray-400 mb-2')

                g = db.get_globals()
                state['global_values'] = {
                    k: dict(v) if isinstance(v, dict) else {'value': str(v), 'enabled': True}
                    for k, v in g.get('values', {}).items()
                }

                globals_kv_container = ui.column().classes('w-full gap-1')
                _build_kv_editor(globals_kv_container, state['global_values'],
                                 lambda: state.update({'dirty_globals': True}))

                def save_globals():
                    db.update_globals(state['global_values'])
                    state['dirty_globals'] = False
                    ui.notify('Global variables saved', color='positive')

                ui.button('Save Globals', on_click=save_globals).props('color=positive size=sm').classes('mt-2')

        ui.button('Close', on_click=dialog.close).props('flat').classes('mt-2')

    dialog.open()
