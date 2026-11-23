
from fastapi import APIRouter, HTTPException

from app.schemas.image import ImageRequest, ImageResponse
from app.services.image_service import generate_story_image

router = APIRouter(prefix="/api", tags=["Images"])


@router.post("/image", response_model=ImageResponse)
async def create_image(request: ImageRequest):
    try:
        generated_image = await generate_story_image(
            request.prompt
        )

        return ImageResponse(image=generated_image)

    except Exception as error:
        print(f"Image generation error: {error}")

        raise HTTPException(
            status_code=500,
            detail=f"Image generation failed: {str(error)}"
        )
