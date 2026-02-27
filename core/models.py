import uuid
import time
from typing import Literal
from pydantic import BaseModel, Field, ConfigDict


class Collection(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), alias="_id")
    name: str
    auth: dict = Field(default_factory=lambda: {"type": "none"})
    variables: dict = Field(default_factory=dict)
    pre_request_script: str = ""
    post_request_script: str = ""
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)


class Item(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), alias="_id")
    collection_id: str
    parent_id: str | None = None
    type: Literal["folder", "request"]
    name: str
    order: int = 0
    pre_request_script: str = ""
    post_request_script: str = ""

    # request-only fields
    method: str = "GET"
    url: str = ""
    params: list[dict] = Field(default_factory=list)
    headers: list[dict] = Field(default_factory=list)
    body: dict = Field(default_factory=lambda: {"mode": "none", "raw": "", "urlencoded": []})
    auth: dict = Field(default_factory=lambda: {"type": "none"})


class Environment(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), alias="_id")
    name: str
    values: dict[str, dict] = Field(default_factory=dict)
    updated_at: float = Field(default_factory=time.time)


class Globals(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(default="global", alias="_id")
    values: dict[str, dict] = Field(default_factory=dict)
