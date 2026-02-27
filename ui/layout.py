from nicegui import ui, app as nicegui_app
from core import db


async def build_layout():
    with ui.header().classes('items-center justify-between px-4 py-2 bg-gray-900 text-white'):
        ui.label('ApiHive').classes('text-xl font-bold text-white')
        with ui.row().classes('items-center gap-4'):

            # ── Live environment dropdown ────────────────────────────────────
            envs = db.list_environments()
            env_options = {'': 'No Environment'} | {e['_id']: e['name'] for e in envs}
            active_id = nicegui_app.storage.user.get('active_env_id', '')

            env_select = ui.select(
                options=env_options,
                value=active_id if active_id in env_options else '',
                label='Environment',
                on_change=lambda e: nicegui_app.storage.user.update({'active_env_id': e.value}),
            ).classes('w-48').props('dark filled dense')

            # ── SSL toggle ───────────────────────────────────────────────────
            ssl_on = getattr(nicegui_app.state, 'ssl_verify', True)
            ssl_btn = ui.button(
                f'SSL: {"ON" if ssl_on else "OFF"}',
            ).props('flat color=white size=sm')

            def toggle_ssl():
                current = getattr(nicegui_app.state, 'ssl_verify', True)
                nicegui_app.state.ssl_verify = not current
                ssl_btn.set_text(f'SSL: {"ON" if nicegui_app.state.ssl_verify else "OFF"}')

            ssl_btn.on('click', toggle_ssl)

            # ── Import ───────────────────────────────────────────────────────
            def open_import():
                from ui.importer_dialog import open_import_dialog
                open_import_dialog()

            ui.button('Import', icon='upload_file', on_click=open_import).props('flat color=white')

            # ── Settings ─────────────────────────────────────────────────────
            def open_settings():
                from ui.settings import open_settings_dialog
                open_settings_dialog()

            ui.button('Settings', icon='settings', on_click=open_settings).props('flat color=white')

    with ui.row().classes('w-full flex-grow overflow-hidden').style('height: calc(100vh - 56px)'):
        # sidebar
        with ui.column().classes('border-r border-gray-200 h-full overflow-y-auto p-2').style('width: 280px; min-width: 280px'):
            from ui.sidebar import build_sidebar
            await build_sidebar()
        # main area
        with ui.column().classes('flex-grow h-full overflow-hidden p-2'):
            from ui.request_tabs import build_request_tabs
            await build_request_tabs()
