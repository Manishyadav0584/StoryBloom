
from pydantic import BaseModel, Field


class StoryRequest(BaseModel):
    topic: str = Field(min_length=3, max_length=200)
    age: int = Field(ge=3, le=15)
    moral: str = Field(default="", max_length=200)


class StoryResponse(BaseModel):
    title: str
    story: str
