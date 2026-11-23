
from typing import Literal

from pydantic import BaseModel, Field


class BookRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)

    story: str = Field(
        min_length=10,
        max_length=30000
    )

    # Backward compatibility with the earlier PDF endpoint
    image: str | None = None

    # All illustrations, including the cover
    images: list[str] = Field(
        default_factory=list,
        max_length=10
    )

    moral: str = Field(
        default="",
        max_length=500
    )

    age: int = Field(ge=3, le=15)

    pages: Literal[6, 10, 15] = 10
