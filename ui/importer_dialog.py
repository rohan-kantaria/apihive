"""
Import dialog — uses browser-native file picker (ui.upload) to select a
.postman_collection.json file and import it into MongoDB.
"""
from nicegui import ui

from core.importer import import_from_content
from ui.sidebar import refresh_tree


def open_import_dialog():
    """Open the Postman collection import dialog with a browser file picker."""
    with ui.dialog() as dialog, ui.card().classes('w-96'):
        ui.label('Import Postman Collection').classes('text-lg font-bold')
        ui.label('Select a .postman_collection.json file from your computer.').classes(
            'text-sm text-gray-500 mb-2'
        )

        status_label = ui.label('').classes('text-sm min-h-5')

        upload = ui.upload(
            label='Choose file',
            auto_upload=True,
            max_files=1,
        ).props('accept=".json" flat bordered').classes('w-full')

        async def on_upload(e):
            status_label.set_text('Importing…')
            try:
                result = import_from_content(e.content.read())
                msg = f"Imported {result['imported_count']} items."
                if result['errors']:
                    msg += f" ({len(result['errors'])} error(s): {result['errors'][0]})"
                status_label.set_text(msg)
                refresh_tree()
                upload.reset()
                # Close after a short delay so the user can read the result
                import asyncio
                await asyncio.sleep(1.5)
                dialog.close()
            except Exception as exc:
                status_label.set_text(f'Error: {exc}')

        upload.on('upload', on_upload)

        with ui.row().classes('mt-2'):
            ui.button('Cancel', on_click=dialog.close).props('flat')

    dialog.open()
