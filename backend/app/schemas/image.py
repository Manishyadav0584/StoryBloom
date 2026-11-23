
from pydantic import BaseModel, Field


class ImageRequest(BaseModel):
    prompt: str = Field(
        min_length=10,
        max_length=2048
    )


class ImageResponse(BaseModel):
    image: str
