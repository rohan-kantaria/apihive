from dotenv import load_dotenv
load_dotenv()  # must be first — loads .env before any other import reads os.environ

import os
from nicegui import ui, app
from core.db import get_db


@ui.page('/')
async def index():
    # temporary placeholder — replaced in Phase 2
    with ui.column().classes('w-full h-screen items-center justify-center'):
        ui.label('ApiHive').classes('text-3xl font-bold')
        ui.label('Phase 1 — Foundation').classes('text-gray-500')


def main():
    try:
        db = get_db()
        db.command('ping')
        print("[ApiHive] MongoDB connection OK")
    except RuntimeError as e:
        print(e)
        raise SystemExit(1)
    except Exception as e:
        print(f"[ApiHive] MongoDB connection failed: {e}")
        raise SystemExit(1)

    ssl_verify = os.getenv("SSL_VERIFY", "true").lower() != "false"
    app.state.ssl_verify = ssl_verify

    ui.run(title='ApiHive', port=8080, reload=False)


if __name__ == '__main__':
    main()
