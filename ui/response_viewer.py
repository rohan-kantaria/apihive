"""
Response viewer panel — status line, Body / Headers / Console tabs.
build_response_viewer() returns a ResponseViewer whose build() adds the DOM elements.
This two-step design lets request_tabs.py render the request builder first (top)
and the response viewer second (bottom) while the builder still holds a reference
to the viewer for Send-button wiring.
"""
import json

from nicegui import ui


class ResponseViewer:
    """Holds references to the response panel DOM elements and handles updates."""

    def __init__(self):
        self._status_label = None
        self._error_banner = None
        self._tabs = None
        self._console_tab = None
        self._body_container = None
        self._headers_container = None
        self._console_container = None
        self._built = False

    # ── DOM construction (called after request builder is rendered) ────────────

    def build(self):
        """Create all DOM elements for the response viewer in the current NiceGUI context."""
        with ui.column().classes('w-full gap-1 border-t border-gray-200 pt-2 mt-1'):

            # Status line
            self._status_label = ui.label('—').classes(
                'text-sm font-medium text-gray-600'
            )

            # Error / abort banner (hidden by default)
            self._error_banner = ui.label('').classes(
                'w-full bg-red-50 text-red-700 border border-red-200 rounded px-3 py-2 text-sm'
            )
            self._error_banner.set_visibility(False)

            # Tab bar
            with ui.tabs().classes('w-full shrink-0') as tabs:
                body_tab = ui.tab('Body')
                ui.tab('Headers')
                console_tab = ui.tab('Console')

            self._tabs = tabs
            self._console_tab = console_tab

            with ui.tab_panels(tabs, value=body_tab).classes('w-full'):
                with ui.tab_panel(body_tab).classes('p-0 pt-1'):
                    self._body_container = ui.column().classes('w-full')

                with ui.tab_panel('Headers').classes('p-0 pt-1'):
                    self._headers_container = ui.column().classes('w-full')

                with ui.tab_panel(console_tab).classes('p-0 pt-1'):
                    self._console_container = ui.column().classes(
                        'w-full bg-gray-900 rounded p-3 min-h-24 overflow-y-auto'
                    ).style('max-height: 300px')

        self._built = True

    # ── Update logic ───────────────────────────────────────────────────────────

    def update_response(self, result: dict):
        if not self._built:
            return

        response_data = result.get('response_data')
        console_output = result.get('console_output', [])
        script_error = result.get('script_error')

        # --- Console (always populated) ---
        self._console_container.clear()
        with self._console_container:
            if console_output:
                for line in console_output:
                    color = 'text-red-400' if '[ERROR]' in line else 'text-gray-300'
                    ui.label(line).classes(f'font-mono text-xs {color}')
            else:
                ui.label('(no console output)').classes('text-gray-500 text-xs italic')

        # --- Pre-request aborted ---
        if script_error or response_data is None:
            msg = script_error or 'Unknown error'
            self._status_label.set_text('Aborted')
            self._error_banner.set_text(f'Request aborted: {msg}')
            self._error_banner.set_visibility(True)
            self._body_container.clear()
            self._headers_container.clear()
            # Switch to Console tab automatically
            self._tabs.set_value(self._console_tab)
            return

        # --- Normal response ---
        self._error_banner.set_visibility(False)

        status = response_data.get('status', 0)
        elapsed = response_data.get('elapsed_ms', 0.0)
        self._status_label.set_text(
            f'Status: {status}  •  Time: {elapsed:.0f} ms'
        )

        # Body
        self._body_container.clear()
        with self._body_container:
            body_json = response_data.get('body_json')
            if body_json is not None:
                ui.code(
                    json.dumps(body_json, indent=2), language='json'
                ).classes('w-full text-sm')
            else:
                ui.textarea(value=response_data.get('body_text', '')).props(
                    'readonly outlined'
                ).classes('w-full font-mono text-sm').style('min-height: 200px')

        # Headers
        self._headers_container.clear()
        with self._headers_container:
            headers = response_data.get('headers', {})
            if headers:
                for key, val in sorted(headers.items()):
                    with ui.row().classes(
                        'w-full gap-2 border-b border-gray-100 py-1 no-wrap'
                    ):
                        ui.label(key).classes(
                            'text-xs font-semibold text-gray-700 shrink-0'
                        ).style('min-width: 180px; max-width: 220px; overflow: hidden; text-overflow: ellipsis')
                        ui.label(val).classes(
                            'text-xs text-gray-600 font-mono flex-grow truncate'
                        )
            else:
                ui.label('(no headers)').classes('text-gray-400 text-xs italic')

    def clear(self):
        if not self._built:
            return
        self._status_label.set_text('—')
        self._error_banner.set_visibility(False)
        self._body_container.clear()
        self._headers_container.clear()
        self._console_container.clear()


def build_response_viewer() -> ResponseViewer:
    """Create a ResponseViewer and immediately build its DOM elements."""
    viewer = ResponseViewer()
    viewer.build()
    return viewer
