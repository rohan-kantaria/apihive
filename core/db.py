import os
import time
from pymongo import MongoClient
from pymongo.database import Database
from core.models import Collection, Item, Environment, Globals

_client: MongoClient | None = None


def get_db() -> Database:
    global _client
    mongo_uri = os.getenv("MONGO_URI")
    if not mongo_uri:
        raise RuntimeError(
            "[ApiHive] MONGO_URI is not set. "
            "Copy .env.example to .env and fill in your MongoDB Atlas connection string."
        )
    if _client is None:
        _client = MongoClient(mongo_uri)
    db_name = os.getenv("MONGO_DB", "apihive")
    return _client[db_name]


# ── Collections ───────────────────────────────────────────────────────────────

def list_collections() -> list[dict]:
    return list(get_db().collections.find({}, {"_id": 1, "name": 1, "pre_request_script": 1, "post_request_script": 1, "variables": 1, "auth": 1, "created_at": 1, "updated_at": 1}))


def create_collection(name: str) -> dict:
    doc = Collection(name=name).model_dump(by_alias=True)
    get_db().collections.insert_one(doc)
    return doc


def update_collection(id: str, data: dict) -> None:
    data["updated_at"] = time.time()
    get_db().collections.update_one({"_id": id}, {"$set": data})


def delete_collection(id: str) -> None:
    get_db().collections.delete_one({"_id": id})
    # cascade: delete all items in this collection
    _delete_items_by_collection(id)


def _delete_items_by_collection(collection_id: str) -> None:
    get_db().items.delete_many({"collection_id": collection_id})


# ── Items ─────────────────────────────────────────────────────────────────────

def list_items(collection_id: str) -> list[dict]:
    return list(get_db().items.find({"collection_id": collection_id}).sort("order", 1))


def create_item(data: dict) -> dict:
    item = Item(**{k.lstrip("_") if k == "_id" else k: v for k, v in data.items()})
    doc = item.model_dump(by_alias=True)
    # Override with original data to preserve provided _id if any
    doc.update(data)
    get_db().items.insert_one(doc)
    return doc


def get_item(id: str) -> dict | None:
    return get_db().items.find_one({"_id": id})


def update_item(id: str, data: dict) -> None:
    get_db().items.update_one({"_id": id}, {"$set": data})


def delete_item(id: str) -> None:
    # recursively delete all children first
    children = list(get_db().items.find({"parent_id": id}, {"_id": 1}))
    for child in children:
        delete_item(child["_id"])
    get_db().items.delete_one({"_id": id})


# ── Environments ──────────────────────────────────────────────────────────────

def list_environments() -> list[dict]:
    return list(get_db().environments.find({}))


def create_environment(name: str) -> dict:
    doc = Environment(name=name).model_dump(by_alias=True)
    get_db().environments.insert_one(doc)
    return doc


def get_environment(id: str) -> dict | None:
    return get_db().environments.find_one({"_id": id})


def update_environment(id: str, values: dict) -> None:
    get_db().environments.update_one(
        {"_id": id},
        {"$set": {"values": values, "updated_at": time.time()}}
    )


def delete_environment(id: str) -> None:
    get_db().environments.delete_one({"_id": id})


# ── Globals ───────────────────────────────────────────────────────────────────

def get_globals() -> dict:
    db = get_db()
    doc = db.globals.find_one({"_id": "global"})
    if doc is None:
        doc = Globals().model_dump(by_alias=True)
        db.globals.insert_one(doc)
    return doc


def update_globals(values: dict) -> None:
    get_db().globals.update_one(
        {"_id": "global"},
        {"$set": {"values": values}},
        upsert=True
    )


# ── Script Chain ──────────────────────────────────────────────────────────────

def get_script_chain(item_id: str) -> list[dict]:
    """
    Walks the parent_id chain upward from item_id.
    Returns ordered list outermost → innermost:
    [
      {"pre": "...", "post": "...", "level": "collection"},
      {"pre": "...", "post": "...", "level": "folder"},   # 0 or more
      {"pre": "...", "post": "...", "level": "request"},
    ]
    """
    db = get_db()
    item = db.items.find_one({"_id": item_id})
    if not item:
        return []

    chain = []
    # Walk up the parent chain collecting folders
    current = item
    while current.get("parent_id"):
        parent = db.items.find_one({"_id": current["parent_id"]})
        if not parent:
            break
        chain.append({
            "pre": parent.get("pre_request_script", ""),
            "post": parent.get("post_request_script", ""),
            "level": "folder",
        })
        current = parent

    # Get collection-level scripts
    collection = db.collections.find_one({"_id": item["collection_id"]})
    if collection:
        chain.append({
            "pre": collection.get("pre_request_script", ""),
            "post": collection.get("post_request_script", ""),
            "level": "collection",
        })

    # Reverse so order is outermost (collection) → innermost (request)
    chain.reverse()

    # Append the request itself
    chain.append({
        "pre": item.get("pre_request_script", ""),
        "post": item.get("post_request_script", ""),
        "level": "request",
    })

    return chain
