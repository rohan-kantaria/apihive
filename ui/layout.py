from nicegui import ui, app as nicegui_app


async def build_layout():
    with ui.header().classes('items-center justify-between px-4 py-2 bg-gray-900 text-white'):
        ui.label('ApiHive').classes('text-xl font-bold text-white')
        with ui.row().classes('items-center gap-4'):
            # env dropdown placeholder — replaced in Phase 4
            ui.select(options=['No Environment'], value='No Environment').classes('w-48')
            # ssl toggle
            ssl_on = getattr(nicegui_app.state, 'ssl_verify', True)
            ui.label('SSL: ON' if ssl_on else 'SSL: OFF').classes('text-sm text-white')
            # import / settings buttons
            ui.button('Import', on_click=lambda: ui.notify('Import — Phase 5')).props('flat color=white')
            ui.button('Settings', on_click=lambda: ui.notify('Settings — coming soon')).props('flat color=white')

    with ui.row().classes('w-full flex-grow overflow-hidden').style('height: calc(100vh - 56px)'):
        # sidebar
        with ui.column().classes('border-r border-gray-200 h-full overflow-y-auto p-2').style('width: 280px; min-width: 280px'):
            from ui.sidebar import build_sidebar
            await build_sidebar()
        # main area
        with ui.column().classes('flex-grow h-full overflow-hidden p-2'):
            from ui.request_tabs import build_request_tabs
            await build_request_tabs()
