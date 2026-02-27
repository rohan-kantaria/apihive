from nicegui import ui, app as nicegui_app
from core import db

_tabs_refresh = None


async def build_request_tabs():
    global _tabs_refresh

    @ui.refreshable
    def tabs_ui():
        tabs_data: list[dict] = nicegui_app.storage.user.get('open_tabs', [])

        if not tabs_data:
            with ui.column().classes('w-full h-full items-center justify-center gap-3'):
                ui.icon('open_in_browser').classes('text-6xl text-gray-300')
                ui.label('Double-click a request to open it').classes('text-gray-400 text-lg')
            return

        active_tab = nicegui_app.storage.user.get('active_tab')
        ids = [t['item_id'] for t in tabs_data]
        if not active_tab or active_tab not in ids:
            active_tab = ids[0]
            nicegui_app.storage.user['active_tab'] = active_tab

        def on_tab_change(e):
            nicegui_app.storage.user['active_tab'] = e.value

        with ui.column().classes('w-full h-full overflow-hidden'):
            with ui.tabs(value=active_tab, on_change=on_tab_change).classes('w-full shrink-0') as qtabs:
                for tab in tabs_data:
                    dirty = tab.get('dirty', False)
                    with ui.tab(name=tab['item_id'], label=''):
                        with ui.row().classes('items-center gap-1 no-wrap'):
                            ui.label(tab['label'] + (' ●' if dirty else '')).classes('text-sm')
                            ui.button(
                                icon='close',
                                on_click=lambda _e, tid=tab['item_id']: _close_tab(tid)
                            ).props('flat round dense size=xs').classes('text-gray-400 hover:text-red-500')

            with ui.tab_panels(qtabs, value=active_tab).classes('w-full flex-grow overflow-auto'):
                for tab in tabs_data:
                    with ui.tab_panel(tab['item_id']):
                        item = db.get_item(tab['item_id'])
                        if item:
                            from ui.request_builder import build_request_builder
                            from ui.response_viewer import ResponseViewer
                            # Create viewer object first (no DOM yet) so builder can reference it
                            viewer = ResponseViewer()
                            # Render request builder at top (references viewer for Send wiring)
                            build_request_builder(item, viewer)
                            # Render response viewer DOM below the builder
                            viewer.build()
                        else:
                            ui.label('Request not found.').classes('text-gray-400')

    tabs_ui()
    _tabs_refresh = tabs_ui.refresh


def open_request_tab(item_id: str):
    tabs_data: list[dict] = nicegui_app.storage.user.get('open_tabs', [])

    # Already open — just switch to it
    for tab in tabs_data:
        if tab['item_id'] == item_id:
            nicegui_app.storage.user['active_tab'] = item_id
            if _tabs_refresh:
                _tabs_refresh()
            return

    # Load from DB and open new tab
    item = db.get_item(item_id)
    if not item:
        ui.notify('Request not found', color='negative')
        return

    # Max 10 tabs — close oldest if needed
    if len(tabs_data) >= 10:
        tabs_data.pop(0)

    tabs_data.append({
        'item_id': item_id,
        'label': item['name'],
        'dirty': False,
    })
    nicegui_app.storage.user['open_tabs'] = tabs_data
    nicegui_app.storage.user['active_tab'] = item_id

    if _tabs_refresh:
        _tabs_refresh()


def _close_tab(item_id: str):
    tabs_data: list[dict] = nicegui_app.storage.user.get('open_tabs', [])
    tabs_data = [t for t in tabs_data if t['item_id'] != item_id]
    nicegui_app.storage.user['open_tabs'] = tabs_data

    active = nicegui_app.storage.user.get('active_tab')
    if active == item_id:
        nicegui_app.storage.user['active_tab'] = tabs_data[0]['item_id'] if tabs_data else None

    if _tabs_refresh:
        _tabs_refresh()


def set_tab_dirty(item_id: str, dirty: bool):
    """Mark a tab as having unsaved changes."""
    tabs_data: list[dict] = nicegui_app.storage.user.get('open_tabs', [])
    for tab in tabs_data:
        if tab['item_id'] == item_id:
            tab['dirty'] = dirty
            break
    nicegui_app.storage.user['open_tabs'] = tabs_data
    if _tabs_refresh:
        _tabs_refresh()
