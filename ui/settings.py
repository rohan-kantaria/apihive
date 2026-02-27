"""
Settings panel — SSL toggle, environment manager shortcut, and import shortcut.
build_settings_panel() can be called inside any NiceGUI context (e.g. inside a dialog).
"""
from nicegui import ui, app as nicegui_app


def open_settings_dialog():
    """Open the Settings modal dialog."""
    with ui.dialog() as dialog, ui.card().classes('w-96'):
        ui.label('Settings').classes('text-xl font-bold mb-2')

        # ── SSL toggle ───────────────────────────────────────────────────────
        ui.label('SSL Verification').classes('text-sm font-semibold text-gray-600')
        ssl_on = getattr(nicegui_app.state, 'ssl_verify', True)
        ssl_switch = ui.switch('SSL Verification', value=ssl_on)

        def on_ssl_change(e):
            nicegui_app.state.ssl_verify = e.value

        ssl_switch.on('update:model-value', on_ssl_change)

        ui.label(
            'Disable for APIs using self-signed certificates.'
        ).classes('text-xs text-gray-400 mb-3')

        ui.separator()

        # ── Environments ─────────────────────────────────────────────────────
        ui.label('Environments').classes('text-sm font-semibold text-gray-600 mt-3')
        ui.button(
            'Manage Environments',
            icon='tune',
            on_click=lambda: (dialog.close(), _open_env_manager()),
        ).props('flat color=primary').classes('w-full justify-start')

        ui.separator()

        # ── Import ───────────────────────────────────────────────────────────
        ui.label('Data').classes('text-sm font-semibold text-gray-600 mt-3')
        ui.button(
            'Import Postman Collection',
            icon='upload_file',
            on_click=lambda: (dialog.close(), _open_import_dialog()),
        ).props('flat color=primary').classes('w-full justify-start')

        ui.separator()

        ui.button('Close', on_click=dialog.close).props('flat').classes('mt-2')

    dialog.open()


def _open_env_manager():
    from ui.env_manager import open_env_manager
    open_env_manager()


def _open_import_dialog():
    from ui.importer_dialog import open_import_dialog
    open_import_dialog()


def build_settings_panel():
    """Render settings inline (alternative entry point)."""
    open_settings_dialog()
