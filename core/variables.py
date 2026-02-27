from dotenv import dotenv_values


def load_local_env() -> dict:
    """Load variables from .env file (not os.environ). Excludes system keys."""
    return {
        k: v
        for k, v in dotenv_values(".env").items()
        if k not in ("MONGO_URI", "MONGO_DB", "SSL_VERIFY")
    }


def resolve(text: str, local_env: dict, active_env_values: dict, global_values: dict) -> str:
    """
    Replace {{key}} placeholders in text.
    Priority: local_env > active_env_values > global_values.
    val_obj may be a dict {"value": ..., "enabled": true} or a plain string.
    One pass only — nested {{vars}} in values are NOT recursively resolved.
    """
    merged = {**global_values, **active_env_values, **local_env}
    for key, val_obj in merged.items():
        if isinstance(val_obj, dict):
            if not val_obj.get("enabled", True):
                continue
            val = str(val_obj.get("value", ""))
        else:
            val = str(val_obj)
        text = text.replace(f"{{{{{key}}}}}", val)
    return text


def get_active_env_values(active_env_id: str | None) -> dict:
    """Returns the values dict from the active environment, or {} if none."""
    if not active_env_id:
        return {}
    from core import db
    env = db.get_environment(active_env_id)
    return env["values"] if env else {}


def get_global_values() -> dict:
    """Returns the values dict from the globals document."""
    from core import db
    g = db.get_globals()
    return g.get("values", {})
