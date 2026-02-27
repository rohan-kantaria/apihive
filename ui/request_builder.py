from nicegui import ui


def build_request_builder(item: dict):
    """Placeholder — implemented in Phase 3."""
    with ui.column().classes('w-full gap-2'):
        ui.label(f"{item.get('method', 'GET')}  {item.get('url', '')}").classes(
            'text-gray-400 font-mono text-sm'
        )
        ui.label('Request builder — coming in Phase 3').classes('text-gray-400')
