"""
Import dialog — lets the user specify a .postman_collection.json file path
and triggers the Postman v2.1 importer.
"""
import asyncio

from nicegui import ui

from core.importer import import_postman_v21
from ui.sidebar import refresh_tree


def open_import_dialog():
    """Open the Postman collection import dialog."""
    with ui.dialog() as dialog, ui.card().classes('w-96'):
        ui.label('Import Postman Collection').classes('text-lg font-bold')
        ui.label('Enter the full path to a .postman_collection.json file').classes(
            'text-sm text-gray-500'
        )

        file_path_input = ui.input(
            'File path', placeholder='/path/to/collection.postman_collection.json'
        ).classes('w-full font-mono text-sm')

        status_label = ui.label('').classes('text-sm')

        async def do_import():
            path = file_path_input.value.strip()
            if not path:
                status_label.set_text('Please enter a file path.')
                return
            status_label.set_text('Importing…')
            try:
                result = import_postman_v21(path)
                msg = f"Imported {result['imported_count']} items."
                if result['errors']:
                    msg += f" ({len(result['errors'])} errors: {result['errors'][0]})"
                status_label.set_text(msg)
                refresh_tree()
                await asyncio.sleep(1.5)
                dialog.close()
            except FileNotFoundError:
                status_label.set_text(f'File not found: {path}')
            except Exception as exc:
                status_label.set_text(f'Error: {exc}')

        with ui.row().classes('mt-2 gap-2'):
            ui.button('Import', on_click=do_import).props('color=primary')
            ui.button('Cancel', on_click=dialog.close).props('flat')

    dialog.open()
