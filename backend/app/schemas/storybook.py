
from typing import Literal

from pydantic import BaseModel, Field


class StorybookRequest(BaseModel):
    topic: str = Field(min_length=3, max_length=200)
    age: int = Field(ge=3, le=15)
    moral: str = Field(default="", max_length=200)

    # Total pages, including cover and ending page
    pages: Literal[6, 10, 15] = 10

    # Total illustrations, including cover
    image_count: Literal[3, 5, 8, 10] = 5


class StorybookResponse(BaseModel):
    title: str
    story: str
    images: list[str]
    moral: str
    age: int
    pages: int
    image_count: int
