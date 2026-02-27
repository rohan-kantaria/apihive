import uuid
from nicegui import ui
from core import db

_sidebar_container: ui.element | None = None


# ── Tree data helpers ─────────────────────────────────────────────────────────

def _build_tree_data() -> list[dict]:
    result = []
    for col in db.list_collections():
        all_items = db.list_items(col['_id'])
        result.append({
            'id': col['_id'],
            'label': col['name'],
            'type': 'collection',
            'pre_request_script': col.get('pre_request_script', ''),
            'post_request_script': col.get('post_request_script', ''),
            'children': _build_children(all_items, None),
        })
    return result


def _build_children(all_items: list[dict], parent_id) -> list[dict]:
    nodes = []
    for item in sorted(all_items, key=lambda x: x.get('order', 0)):
        if item.get('parent_id') == parent_id:
            node = {
                'id': item['_id'],
                'label': item['name'],
                'type': item['type'],
                'collection_id': item['collection_id'],
                'parent_id': parent_id,
                'pre_request_script': item.get('pre_request_script', ''),
                'post_request_script': item.get('post_request_script', ''),
                'method': item.get('method', 'GET'),
                'url': item.get('url', ''),
            }
            if item['type'] == 'folder':
                node['children'] = _build_children(all_items, item['_id'])
            nodes.append(node)
    return nodes


# ── Tree rendering ────────────────────────────────────────────────────────────

METHOD_COLORS = {
    'GET': 'text-green-600',
    'POST': 'text-yellow-600',
    'PUT': 'text-blue-600',
    'PATCH': 'text-purple-600',
    'DELETE': 'text-red-600',
    'HEAD': 'text-gray-600',
    'OPTIONS': 'text-gray-600',
}


def _render_tree(nodes: list[dict]):
    for node in nodes:
        _render_node(node)


def _render_node(node: dict):
    ntype = node['type']
    nid = node['id']
    label = node['label']

    if ntype == 'collection':
        # Wrap in a div so the context menu attaches to the whole row (including the
        # expansion header), not just the collapsible body where Quasar puts default-slot content.
        with ui.element('div').classes('w-full'):
            with ui.context_menu():
                ui.menu_item('Add Folder',
                             lambda nid=nid: _add_item_dialog('folder', nid, None))
                ui.menu_item('Add Request',
                             lambda nid=nid: _add_item_dialog('request', nid, None))
                ui.separator()
                ui.menu_item('Edit Scripts',
                             lambda nid=nid, lbl=label, nd=node: _edit_scripts_dialog('collection', nid, lbl, nd))
                ui.separator()
                ui.menu_item('Delete Collection',
                             lambda nid=nid, lbl=label: _delete_dialog('collection', nid, lbl))
            with ui.expansion(label, icon='folder').classes('w-full text-sm'):
                for child in node.get('children', []):
                    _render_node(child)

    elif ntype == 'folder':
        col_id = node.get('collection_id', '')
        with ui.element('div').classes('w-full'):
            with ui.context_menu():
                ui.menu_item('Add Request',
                             lambda col_id=col_id, nid=nid: _add_item_dialog('request', col_id, nid))
                ui.separator()
                ui.menu_item('Edit Scripts',
                             lambda nid=nid, lbl=label, nd=node: _edit_scripts_dialog('folder', nid, lbl, nd))
                ui.menu_item('Rename',
                             lambda nid=nid, lbl=label: _rename_dialog(nid, lbl))
                ui.separator()
                ui.menu_item('Delete Folder',
                             lambda nid=nid, lbl=label: _delete_dialog('folder', nid, lbl))
            with ui.expansion(label, icon='folder_open').classes('w-full text-sm pl-3'):
                for child in node.get('children', []):
                    _render_node(child)

    elif ntype == 'request':
        method = node.get('method', 'GET')
        color = METHOD_COLORS.get(method, 'text-gray-600')
        with ui.row().classes(
            'w-full cursor-pointer hover:bg-blue-50 rounded px-2 py-1 items-center gap-1 pl-6'
        ) as row:
            ui.label(method).classes(f'text-xs font-bold w-14 shrink-0 {color}')
            ui.label(label).classes('text-sm flex-grow truncate')
            with ui.context_menu():
                ui.menu_item('Rename',
                             lambda nid=nid, lbl=label: _rename_dialog(nid, lbl))
                ui.menu_item('Duplicate',
                             lambda nid=nid: _duplicate_request(nid))
                ui.separator()
                ui.menu_item('Delete',
                             lambda nid=nid, lbl=label: _delete_dialog('request', nid, lbl))
            row.on('dblclick', lambda _e, nid=nid: _open_request(nid))


# ── Actions ───────────────────────────────────────────────────────────────────

def _open_request(item_id: str):
    from ui.request_tabs import open_request_tab
    open_request_tab(item_id)


def _add_item_dialog(item_type: str, collection_id: str, parent_id):
    type_label = 'Folder' if item_type == 'folder' else 'Request'
    with ui.dialog() as dialog, ui.card().classes('w-80'):
        ui.label(f'New {type_label}').classes('text-lg font-bold')
        name_input = ui.input('Name').classes('w-full')

        def confirm():
            name = name_input.value.strip()
            if not name:
                ui.notify('Name cannot be empty', color='negative')
                return
            data = {
                'collection_id': collection_id,
                'parent_id': parent_id,
                'type': item_type,
                'name': name,
                'order': 0,
                'pre_request_script': '',
                'post_request_script': '',
            }
            if item_type == 'request':
                data.update({
                    'method': 'GET',
                    'url': '',
                    'params': [],
                    'headers': [],
                    'body': {'mode': 'none', 'raw': '', 'urlencoded': []},
                    'auth': {'type': 'none'},
                })
            db.create_item(data)
            dialog.close()
            refresh_tree()

        name_input.on('keydown.enter', lambda _e: confirm())
        with ui.row().classes('mt-2'):
            ui.button('Create', on_click=confirm).props('color=primary')
            ui.button('Cancel', on_click=dialog.close).props('flat')
    dialog.open()


def _delete_dialog(item_type: str, item_id: str, label: str):
    with ui.dialog() as dialog, ui.card().classes('w-80'):
        ui.label('Confirm Delete').classes('text-lg font-bold')
        ui.label(f'Delete "{label}"?').classes('text-sm text-gray-600')
        if item_type in ('collection', 'folder'):
            ui.label('This will also delete all children.').classes('text-sm text-red-500')

        def confirm():
            if item_type == 'collection':
                db.delete_collection(item_id)
            else:
                db.delete_item(item_id)
            dialog.close()
            refresh_tree()

        with ui.row().classes('mt-2'):
            ui.button('Delete', on_click=confirm).props('color=negative')
            ui.button('Cancel', on_click=dialog.close).props('flat')
    dialog.open()


def _rename_dialog(item_id: str, current_name: str):
    with ui.dialog() as dialog, ui.card().classes('w-80'):
        ui.label('Rename').classes('text-lg font-bold')
        name_input = ui.input('New name', value=current_name).classes('w-full')

        def confirm():
            name = name_input.value.strip()
            if not name:
                ui.notify('Name cannot be empty', color='negative')
                return
            db.update_item(item_id, {'name': name})
            dialog.close()
            refresh_tree()

        name_input.on('keydown.enter', lambda _e: confirm())
        with ui.row().classes('mt-2'):
            ui.button('Rename', on_click=confirm).props('color=primary')
            ui.button('Cancel', on_click=dialog.close).props('flat')
    dialog.open()


def _duplicate_request(item_id: str):
    item = db.get_item(item_id)
    if not item:
        ui.notify('Item not found', color='negative')
        return
    new_item = dict(item)
    new_item['_id'] = str(uuid.uuid4())
    new_item['name'] = item['name'] + ' (copy)'
    db.create_item(new_item)
    refresh_tree()
    ui.notify(f'Duplicated "{item["name"]}"')


def _edit_scripts_dialog(node_type: str, node_id: str, label: str, node: dict):
    pre_script = node.get('pre_request_script', '')
    post_script = node.get('post_request_script', '')

    with ui.dialog() as dialog, ui.card().classes('w-full max-w-3xl'):
        ui.label(f'Edit Scripts: {label}').classes('text-lg font-bold')

        with ui.tabs() as tabs:
            pre_tab = ui.tab('Pre-request Script')
            post_tab = ui.tab('Post-request Script')

        with ui.tab_panels(tabs, value=pre_tab).classes('w-full'):
            with ui.tab_panel(pre_tab):
                pre_editor = ui.codemirror(
                    value=pre_script, language='javascript'
                ).classes('w-full').style('height: 300px')
            with ui.tab_panel(post_tab):
                post_editor = ui.codemirror(
                    value=post_script, language='javascript'
                ).classes('w-full').style('height: 300px')

        def save():
            data = {
                'pre_request_script': pre_editor.value,
                'post_request_script': post_editor.value,
            }
            if node_type == 'collection':
                db.update_collection(node_id, data)
            else:
                db.update_item(node_id, data)
            ui.notify('Scripts saved', color='positive')
            dialog.close()

        with ui.row().classes('mt-2'):
            ui.button('Save', on_click=save).props('color=primary')
            ui.button('Cancel', on_click=dialog.close).props('flat')
    dialog.open()


def _new_collection_dialog():
    with ui.dialog() as dialog, ui.card().classes('w-80'):
        ui.label('New Collection').classes('text-lg font-bold')
        name_input = ui.input('Collection name').classes('w-full')

        def confirm():
            name = name_input.value.strip()
            if not name:
                ui.notify('Name cannot be empty', color='negative')
                return
            db.create_collection(name)
            dialog.close()
            refresh_tree()

        name_input.on('keydown.enter', lambda _e: confirm())
        with ui.row().classes('mt-2'):
            ui.button('Create', on_click=confirm).props('color=primary')
            ui.button('Cancel', on_click=dialog.close).props('flat')
    dialog.open()


# ── Sidebar build / refresh ───────────────────────────────────────────────────

def _render_sidebar_content():
    with ui.row().classes('w-full items-center justify-between mb-2 px-1'):
        ui.label('Collections').classes('font-semibold text-gray-700 text-sm')
        ui.button(icon='add', on_click=_new_collection_dialog).props('flat round dense size=sm')

    nodes = _build_tree_data()
    if nodes:
        _render_tree(nodes)
    else:
        with ui.column().classes('w-full items-center mt-8 gap-2'):
            ui.icon('folder_open').classes('text-4xl text-gray-300')
            ui.label('No collections yet.').classes('text-gray-400 text-sm')
            ui.label('Click + to create one.').classes('text-gray-400 text-sm')


async def build_sidebar():
    global _sidebar_container
    with ui.column().classes('w-full gap-0') as container:
        _sidebar_container = container
        _render_sidebar_content()


def refresh_tree():
    global _sidebar_container
    if _sidebar_container is None:
        return
    _sidebar_container.clear()
    with _sidebar_container:
        _render_sidebar_content()
